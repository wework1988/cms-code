"""Launch Hindi Voice Studio on localhost. The CMS is not started or modified."""

from __future__ import annotations

import socket

from src.config import HOST, configure_runtime, port
from src.generation import mark_abandoned_jobs
from src.http_app import create_app

configure_runtime()


def _port_is_free(host: str, chosen_port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, chosen_port))
        except OSError:
            return False
    return True


def main() -> None:
    chosen = port()
    if not _port_is_free(HOST, chosen):
        raise SystemExit(
            f"Port {chosen} on {HOST} is already in use. "
            "This app will not stop the other process. Set HINDI_VOICE_PORT in hindi-voice-lab/.env to a free port."
        )
    mark_abandoned_jobs()
    try:
        import uvicorn
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "The studio server is missing from hindi-voice-lab/.venv. Run scripts/setup.sh. "
            f"Detail: {exc}"
        ) from exc
    uvicorn.run(
        create_app(),
        host=HOST,
        port=chosen,
        log_level="info",
        access_log=False,
        server_header=False,
        date_header=False,
    )


if __name__ == "__main__":
    main()
