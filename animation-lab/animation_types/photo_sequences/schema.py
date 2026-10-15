"""Photo-sequence plans. Captions stay tied to passage quotes."""
from __future__ import annotations

from animation_types.documentary.common import PRESETS, NeedsAssets, PlanError, reject_forbidden, require_file, require_quote

TEMPLATES = ("fullscreen_caption", "archival_frame", "paired_annotation")


def validate_semantic_plan(plan: dict, passage: str) -> dict:
    reject_forbidden(plan)
    if plan.get("animation_type") != "photo_sequences":
        raise PlanError("animation_type must be photo_sequences")
    if plan.get("template_id") not in TEMPLATES:
        raise PlanError("Unknown photo template")
    if plan.get("style_preset") not in PRESETS:
        raise PlanError("Unknown style preset")
    images = plan.get("images")
    if not isinstance(images, list) or not 2 <= len(images) <= 4:
        raise NeedsAssets("A photo sequence needs 2 to 4 supplied images")
    if plan["template_id"] == "paired_annotation" and len(images) != 2:
        raise PlanError("The paired template uses exactly two images")
    for image in images:
        require_file(image.get("path") if isinstance(image, dict) else None)
        caption = image.get("caption") if isinstance(image, dict) else None
        if not isinstance(caption, str) or not caption or caption not in passage:
            raise PlanError("Each caption must be an exact substring of the passage")
        focus = image.get("focus")
        if focus is not None:
            _box(focus)
    beats = plan.get("beats")
    if not isinstance(beats, list) or not 3 <= len(beats) <= 4:
        raise PlanError("Use 3 or 4 beats")
    for beat in beats:
        require_quote(beat.get("evidence_quote", ""), passage)
        index = beat.get("image_index")
        if not isinstance(index, int) or not 0 <= index < len(images):
            raise PlanError("Each beat must name one of the supplied images")
    return plan


def _box(box: dict) -> None:
    needed = ("x", "y", "width", "height")
    if not isinstance(box, dict) or any(key not in box for key in needed):
        raise PlanError("A focus rectangle needs x, y, width, and height")
    if any(not isinstance(box[key], (int, float)) or box[key] < 0 or box[key] > 1 for key in needed):
        raise PlanError("Focus rectangles stay inside the photograph")
    if box["x"] + box["width"] > 1 or box["y"] + box["height"] > 1:
        raise PlanError("Focus rectangles stay inside the photograph")
