#!/usr/bin/env python3
"""Report whether this machine can run the local Hindi voice lab."""

from __future__ import annotations

import importlib.metadata
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.audio_processing import decoder_status, ffmpeg_available  # noqa: E402
from src.config import PACKAGE_VERSION, configure_runtime, port  # noqa: E402
from src.model_adapter import checkpoints_present, resolve_device  # noqa: E402


def main() -> int:
    configure_runtime()
    print(f"Python {sys.version.split()[0]} at {sys.executable}")
    print(f"Lab root: {ROOT}")
    print(decoder_status())
    print(f"FFmpeg: {'yes' if ffmpeg_available() else 'no'}")
    print(f"ffprobe: {'yes' if shutil.which('ffprobe') else 'no'}")
    problems = []
    if sys.version_info[:2] != (3, 11):
        problems.append(f"Python {sys.version_info.major}.{sys.version_info.minor} is not 3.11.")
    try:
        installed = importlib.metadata.version("chatterbox-tts")
        print(f"chatterbox-tts {installed} (pinned {PACKAGE_VERSION})")
        if installed != PACKAGE_VERSION:
            problems.append(f"chatterbox-tts {installed} does not match the pin {PACKAGE_VERSION}.")
    except importlib.metadata.PackageNotFoundError:
        problems.append("chatterbox-tts is not installed. Run scripts/setup.sh.")
    try:
        import torch

        print(f"torch {torch.__version__}")
        print(f"cuda available: {torch.cuda.is_available()}")
        mps = getattr(torch.backends, "mps", None)
        print(f"mps built: {bool(mps and mps.is_built())}")
        print(f"mps available: {bool(mps and mps.is_available())}")
        print(f"auto device would select: {resolve_device('auto')}")
    except Exception as exc:
        problems.append(f"PyTorch could not be imported: {exc}")
    print(f"checkpoint cached: {checkpoints_present()}")
    print(f"browser URL when launched: http://127.0.0.1:{port()}/")
    if problems:
        print("Problems:")
        for item in problems:
            print(f"- {item}")
        return 1
    if not checkpoints_present():
        print("Weights are not downloaded yet. Run scripts/download_models.py while online.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
