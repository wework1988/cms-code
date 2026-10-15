"""Dispatch an animation snapshot to its type. Timeline never imports map geography."""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "animation-lab"
sys.path.insert(0, str(LAB))

from animation_core.jobs import load_progress, write_progress  # noqa: E402
from animation_core.registry import UnsupportedAnimationType, canonical_type  # noqa: E402


def dispatch_target(snapshot: dict) -> str:
    return canonical_type(snapshot.get("animation_type"))


def _fail(snapshot_path: Path | None, message: str) -> int:
    print(f"Error: {message}", file=sys.stderr)
    if snapshot_path is not None and snapshot_path.is_file():
        job_dir = snapshot_path.parent
        progress = load_progress(job_dir)
        progress["status"] = "failed"
        progress["message"] = message
        progress.setdefault("clips", [])
        write_progress(job_dir, progress)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a map, timeline, or documentary animation job")
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--retry-clip")
    parser.add_argument("--reresolve", action="store_true")
    parser.add_argument("--replan", action="store_true")
    parser.add_argument("--regenerate-presentation", action="store_true")
    parser.add_argument("--resume-locations", action="store_true")
    parser.add_argument("--restyle-variant", action="store_true")
    args = parser.parse_args(argv)
    snapshot_path = args.snapshot.expanduser().resolve()
    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        kind = dispatch_target(snapshot)
    except (OSError, json.JSONDecodeError, UnsupportedAnimationType) as error:
        return _fail(snapshot_path if snapshot_path.is_file() else None, str(error))

    if kind == "map":
        script = Path(__file__).with_name("run_map_animations.py")
        os.execv(sys.executable, [sys.executable, str(script), *sys.argv[1:]])
    if kind == "timeline":
        from animation_types.timeline.runner import run_job
        try:
            return run_job(snapshot_path, retry_clip=args.retry_clip, replan=args.replan)
        except Exception as error:  # noqa: BLE001
            traceback.print_exc()
            return _fail(snapshot_path, str(error))
    if kind in {
        "text_highlighting",
        "photo_sequences",
        "before_after",
        "document_highlighting",
        "relationship_diagrams",
        "data_animations",
        "storyboard_reconstructions",
    }:
        from animation_types.documentary.runner import run_job
        try:
            return run_job(snapshot_path, retry_clip=args.retry_clip, replan=args.replan)
        except Exception as error:  # noqa: BLE001
            traceback.print_exc()
            return _fail(snapshot_path, str(error))
    return _fail(snapshot_path, f"Unsupported animation type {kind}")


if __name__ == "__main__":
    raise SystemExit(main())
