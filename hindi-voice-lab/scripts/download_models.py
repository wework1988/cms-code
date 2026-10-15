#!/usr/bin/env python3
"""Download the pinned Chatterbox Multilingual checkpoint into this folder."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import configure_runtime  # noqa: E402
from src.model_adapter import ModelError, ModelService  # noqa: E402


def main() -> int:
    configure_runtime(offline=False)
    try:
        manifest = ModelService().download()
    except ModelError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Downloaded {manifest['t3_filename']} ({manifest['t3_sha256']})")
    print(f"Snapshot: {manifest['snapshot_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
