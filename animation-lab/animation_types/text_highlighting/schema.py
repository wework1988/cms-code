"""Text-highlighting plan. Phrases stay whole so Hindi shaping is preserved."""
from __future__ import annotations

from animation_types.documentary.common import PRESETS, PlanError, reject_forbidden, require_quote

TEMPLATES = ("editorial_statement", "quote_annotation", "contrast_reveal")


def validate_semantic_plan(plan: dict, passage: str) -> dict:
    reject_forbidden(plan)
    if plan.get("animation_type") != "text_highlighting":
        raise PlanError("animation_type must be text_highlighting")
    if plan.get("template_id") not in TEMPLATES:
        raise PlanError("Choose editorial_statement, quote_annotation, or contrast_reveal")
    if plan.get("style_preset") not in PRESETS:
        raise PlanError("Unknown style preset")
    lines = plan.get("lines")
    if not isinstance(lines, list) or not 2 <= len(lines) <= 4:
        raise PlanError("A text clip uses 2 to 4 faithful lines")
    for line in lines:
        text = line.get("text") if isinstance(line, dict) else None
        if not isinstance(text, str) or text not in passage:
            raise PlanError("Each display line must be an exact substring of the passage")
        emphasis = line.get("emphasis")
        if emphasis is not None and (not isinstance(emphasis, str) or emphasis not in text or len(emphasis) < 2):
            raise PlanError("Emphasis must be a phrase inside its line, not a broken character")
    if plan.get("template_id") == "quote_annotation":
        speaker = plan.get("speaker")
        if speaker and speaker not in passage:
            raise PlanError("Ordinary narration is not presented as a quotation from a named person")
    beats = plan.get("beats")
    if not isinstance(beats, list) or not 3 <= len(beats) <= 4:
        raise PlanError("Use 3 or 4 beats")
    for beat in beats:
        require_quote(beat.get("evidence_quote", ""), passage)
        if beat.get("action") not in {"reveal", "emphasize", "dim"}:
            raise PlanError("Text beats only reveal, emphasize, or dim")
    return plan
