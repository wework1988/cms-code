"""Compile a relationship diagram. Layout stays in the renderer."""
from animation_types.documentary.envelope import cache_key, timed_beats

from .schema import validate_semantic_plan


def compile_plan(plan: dict, passage: str, *, duration_seconds: float) -> dict:
    semantic = validate_semantic_plan(plan, passage)
    compiled = {
        "animation_type": "relationship_diagrams",
        "module_version": "1.0",
        "template_version": "1.0",
        "template_id": semantic["template_id"],
        "style_preset": semantic["style_preset"],
        "title": semantic.get("title") or "",
        "language": semantic.get("language") or "hi",
        "duration_seconds": duration_seconds,
        "fps": 30,
        "hold_seconds": 2,
        "focus": semantic.get("focus") or semantic["entities"][0]["id"],
        "entities": semantic["entities"],
        "edges": semantic["edges"],
        "beats": timed_beats(semantic["beats"], duration_seconds),
        "assets": [],
    }
    compiled["cache_key"] = cache_key(compiled)
    return compiled
