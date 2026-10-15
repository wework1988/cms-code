"""Plan or render a documentary clip without launching a browser account."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LAB))

from animation_types.documentary.browser import render_compiled  # noqa: E402
from animation_types.documentary.runner import _module  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Documentary animation commands")
    parser.add_argument("command", choices=["plan-local", "render-plan"])
    parser.add_argument("--type", required=True)
    parser.add_argument("--story", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "plan-local":
        if args.story is None:
            raise SystemExit("--story is required")
        module = _module(args.type)
        script = args.story.read_text(encoding="utf-8")
        snapshot = {
            "animation_type": args.type,
            "planner": "local",
            "script": script,
            "duration_seconds": 12,
            "language": "hi",
            "max_clips": 1,
            "inputs": {},
        }
        selection = module.planner.select_clips(snapshot)
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "selection.json").write_text(json.dumps(selection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"clips": len(selection.get("clips") or []), "explanation": selection.get("explanation")}, ensure_ascii=False))
        return 0
    if args.plan is None:
        raise SystemExit("--plan is required")
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    print(render_compiled(plan, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
