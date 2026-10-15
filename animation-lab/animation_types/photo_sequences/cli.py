"""Render the photo-sequence sample without an API key."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LAB))

from animation_types.documentary.runner import render_sample  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the photo sequence sample")
    parser.add_argument("command", choices=["render-sample"])
    parser.add_argument("--output", type=Path, default=LAB / "output" / "animation-samples" / "photo_sequences")
    args = parser.parse_args(argv)
    print(render_sample("photo_sequences", args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
