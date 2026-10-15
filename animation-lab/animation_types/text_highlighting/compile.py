"""Turn a text plan into timed render instructions."""
from __future__ import annotations

from animation_types.documentary.common import PlanError
from animation_types.documentary.envelope import cache_key, timed_beats

from .schema import validate_semantic_plan


def compile_plan(plan: dict, passage: str, *, duration_seconds: float) -> dict:
    semantic = validate_semantic_plan(plan, passage)
    beats = timed_beats(semantic["beats"], duration_seconds)
    for beat in beats:
        if beat["action"] == "emphasize":
            line = next(item for item in semantic["lines"] if item["id"] == beat["target"])
            if not line.get("emphasis"):
                raise PlanError("An emphasize beat needs a phrase that is already in the line")
    compiled = {
        "animation_type": "text_highlighting",
        "module_version": "1.0",
        "template_version": "1.0",
        "template_id": semantic["template_id"],
        "style_preset": semantic["style_preset"],
        "title": semantic.get("title") or "",
        "kicker": semantic.get("kicker") or "Statement",
        "language": semantic.get("language") or "hi",
        "duration_seconds": duration_seconds,
        "fps": 30,
        "hold_seconds": 2,
        "lines": semantic["lines"],
        "quote": semantic["lines"][0]["text"] if semantic["template_id"] == "quote_annotation" else None,
        "emphasis": next((line.get("emphasis") for line in semantic["lines"] if line.get("emphasis")), None),
        "margin_note": semantic.get("margin_note") or "",
        "beats": beats,
        "assets": [],
    }
    if semantic["template_id"] == "quote_annotation":
        compiled["quote"] = "\n".join(line["text"] for line in semantic["lines"])
    compiled["cache_key"] = cache_key(compiled)
    return compiled
