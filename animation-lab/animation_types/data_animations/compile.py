"""Compile a data animation. No points are added between observations."""
from animation_types.documentary.envelope import cache_key, timed_beats

from .schema import validate_semantic_plan


def compile_plan(plan: dict, passage: str, *, duration_seconds: float) -> dict:
    semantic = validate_semantic_plan(plan, passage)
    compiled = {
        "animation_type": "data_animations",
        "module_version": "1.0",
        "template_version": "1.0",
        "template_id": semantic["template_id"],
        "style_preset": semantic["style_preset"],
        "title": semantic.get("title") or "",
        "language": semantic.get("language") or "hi",
        "duration_seconds": duration_seconds,
        "fps": 30,
        "hold_seconds": 2,
        "unit": semantic["unit"],
        "source_label": semantic["source_label"],
        "baseline": semantic.get("baseline") or "zero",
        "percentage_interpretation": semantic.get("percentage_interpretation"),
        "emphasis_index": semantic.get("emphasis_index", 0),
        "series": semantic["series"],
        "caption": semantic.get("caption") or semantic["source_label"],
        "beats": timed_beats(semantic["beats"], duration_seconds),
        "assets": [],
    }
    compiled["cache_key"] = cache_key(compiled)
    return compiled
