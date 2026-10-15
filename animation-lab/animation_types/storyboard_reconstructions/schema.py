"""Storyboard plans. Local samples do not launch an image generator."""
from __future__ import annotations

from animation_types.documentary.common import PRESETS, NeedsAssets, PlanError, reject_forbidden, require_file, require_quote

TEMPLATES = ("cinematic_sequence", "panel_expand", "detail_focus")


def validate_semantic_plan(plan: dict, passage: str) -> dict:
    reject_forbidden(plan)
    if plan.get("animation_type") != "storyboard_reconstructions":
        raise PlanError("animation_type must be storyboard_reconstructions")
    if plan.get("template_id") not in TEMPLATES:
        raise PlanError("Unknown storyboard template")
    if plan.get("style_preset") not in PRESETS:
        raise PlanError("Unknown style preset")
    provider = plan.get("provider") or "local"
    if provider not in {"local", "existing"}:
        raise NeedsAssets("This renderer does not launch an external image generator")
    images = plan.get("images")
    if not isinstance(images, list) or not 2 <= len(images) <= 3:
        raise NeedsAssets("A reconstruction needs 2 or 3 approved images")
    for image in images:
        require_file(image.get("path") if isinstance(image, dict) else None)
        caption = image.get("caption") if isinstance(image, dict) else None
        if not isinstance(caption, str) or caption not in passage:
            raise PlanError("Each caption must be an exact substring of the passage")
        require_quote(image.get("evidence_quote", "") if isinstance(image, dict) else "", passage)
    if plan.get("illustrative") and not plan.get("label"):
        raise PlanError("An illustrative reconstruction needs its visible label")
    beats = plan.get("beats")
    if not isinstance(beats, list) or not 3 <= len(beats) <= 4:
        raise PlanError("Use 3 or 4 beats")
    for beat in beats:
        require_quote(beat.get("evidence_quote", ""), passage)
        index = beat.get("image_index")
        if not isinstance(index, int) or not 0 <= index < len(images):
            raise PlanError("Each beat must use one of the approved images")
    return plan
