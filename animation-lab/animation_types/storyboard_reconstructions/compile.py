"""Compile a storyboard sequence from approved stills."""
from pathlib import Path

from animation_types.documentary.envelope import finish, timed_beats

from .schema import validate_semantic_plan


def compile_plan(plan: dict, passage: str, *, duration_seconds: float) -> dict:
    semantic = validate_semantic_plan(plan, passage)
    compiled = {
        "animation_type": "storyboard_reconstructions",
        "module_version": "1.0",
        "template_version": "1.0",
        "template_id": semantic["template_id"],
        "style_preset": semantic["style_preset"],
        "title": semantic.get("title") or "",
        "language": semantic.get("language") or "hi",
        "duration_seconds": duration_seconds,
        "fps": 30,
        "hold_seconds": 2,
        "provider": semantic.get("provider") or "local",
        "illustrative": bool(semantic.get("illustrative")),
        "label": semantic.get("label") or "",
        "images": semantic["images"],
        "beats": timed_beats(semantic["beats"], duration_seconds),
    }
    return finish(compiled, [Path(image["path"]) for image in semantic["images"]])
