"""One map renderer at a time, across jobs."""
from __future__ import annotations

import fcntl
import time
from pathlib import Path


class RendererBusy(TimeoutError):
    """Another map render is still using the single renderer slot."""


def renderer_slot(lock_path: Path, timeout: float = 7200):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+")

    class _Slot:
        def __enter__(self):
            deadline = time.monotonic() + timeout
            while True:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return handle
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        handle.close()
                        raise RendererBusy("A map renderer is already running. This clip will retry when that render finishes.")
                    time.sleep(0.05)

        def __exit__(self, *_args):
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()

    return _Slot()
