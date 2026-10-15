"""Compile a before/after comparison."""
from pathlib import Path

from animation_types.documentary.envelope import finish, timed_beats

from .schema import validate_semantic_plan


def compile_plan(plan: dict, passage: str, *, duration_seconds: float) -> dict:
    semantic = validate_semantic_plan(plan, passage)
    compiled = {
        "animation_type": "before_after",
        "module_version": "1.0",
        "template_version": "1.0",
        "template_id": semantic["template_id"],
        "style_preset": semantic["style_preset"],
        "title": semantic.get("title") or "",
        "language": semantic.get("language") or "hi",
        "duration_seconds": duration_seconds,
        "fps": 30,
        "hold_seconds": 2,
        "viewpoints_differ": bool(semantic.get("viewpoints_differ")),
        "disclosure": semantic.get("disclosure") or "",
        "before": semantic["before"],
        "after": semantic["after"],
        "beats": timed_beats(semantic["beats"], duration_seconds),
    }
    return finish(compiled, [Path(semantic["before"]["path"]), Path(semantic["after"]["path"])])
