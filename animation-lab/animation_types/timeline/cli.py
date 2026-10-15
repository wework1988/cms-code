"""Plan and render a timeline sample without DeepSeek or the map catalogue."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[2]
if str(LAB) not in sys.path:
    sys.path.insert(0, str(LAB))

from animation_core.jobs import atomic_write_json  # noqa: E402
from animation_core.outputs import verify_mp4  # noqa: E402
from animation_types.timeline.compile import compile_plan  # noqa: E402
from animation_types.timeline.planner import plan_from_passage, select_local  # noqa: E402
from animation_types.timeline.renderer import render_compiled  # noqa: E402

SAMPLE = LAB / "examples" / "timeline-story.txt"
OUTPUT = LAB / "output" / "timeline-sample"


def render_sample(output_dir: Path = OUTPUT) -> dict:
    script = SAMPLE.read_text(encoding="utf-8").strip() + "\n"
    selection = select_local(script, max_clips=3, duration_seconds=18, language="hi")
    if len(selection["clips"]) != 1:
        raise SystemExit(f"Expected one sample clip, got {len(selection['clips'])}")
    clip = selection["clips"][0]
    if len(clip["beats"]) != 3:
        raise SystemExit("The sample must stay at three milestones")
    semantic = plan_from_passage(clip["source_passage"], language="hi", duration_seconds=18, title=clip["title"])
    compiled = compile_plan(semantic, clip["source_passage"], duration_seconds=18)
    output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output_dir / "selection.json", selection)
    atomic_write_json(output_dir / "semantic-plan.json", semantic)
    atomic_write_json(output_dir / "compiled-plan.json", compiled)
    video = output_dir / "timeline.mp4"
    rendered = render_compiled(compiled, video, output_dir / "frames", output_dir / "contact-sheet.png")
    verification = verify_mp4(rendered["partial"], width=1920, height=1080, fps=30, duration=18)
    rendered["partial"].replace(video)
    atomic_write_json(output_dir / "verification.json", verification)
    print(json.dumps({"video": str(video), "verification": verification}, ensure_ascii=False, indent=2))
    return verification


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("render-sample",))
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    args = parser.parse_args()
    render_sample(args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
