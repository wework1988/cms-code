"""Render a cinematic overlay sample without DeepSeek or the CMS."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
REPO = LAB.parent
if str(LAB) not in sys.path:
    sys.path.insert(0, str(LAB))

from cinematic_overlays.compile import compile_overlay  # noqa: E402
from cinematic_overlays.schema import validate_plan  # noqa: E402
from documentary_graphics.compose import probe_video  # noqa: E402
from documentary_graphics.render_job import render_job  # noqa: E402

SAMPLE = LAB / "cinematic_overlays" / "samples" / "scene-1-callout.json"


def resolve_input(value: str) -> Path:
    path = Path(value)
    if path.is_file():
        return path.resolve()
    candidate = (REPO / value).resolve()
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(f"Source video is missing: {value}")


def render_plan(plan_path: Path, output_dir: Path) -> dict:
    raw = json.loads(plan_path.read_text(encoding="utf-8"))
    source = resolve_input(raw["input"])
    media = probe_video(source)
    validated = validate_plan(raw, duration=media["duration"])
    compiled = compile_overlay(validated, media)
    output_dir.mkdir(parents=True, exist_ok=True)
    return render_job(
        source=source,
        compiled=compiled,
        destination=output_dir / "scene-1-overlay.mp4",
        raw_plan=raw,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render cinematic overlays onto a copy of an MP4")
    parser.add_argument("command", choices=["render-sample", "render"])
    parser.add_argument("--plan", type=Path, default=SAMPLE)
    parser.add_argument("--output", type=Path, default=LAB / "output" / "cinematic-overlays")
    args = parser.parse_args(argv)
    print(render_plan(args.plan, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
