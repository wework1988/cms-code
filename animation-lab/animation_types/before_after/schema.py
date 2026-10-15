"""Before/after plans. Missing dates and images stay missing."""
from __future__ import annotations

from animation_types.documentary.common import PRESETS, NeedsAssets, PlanError, reject_forbidden, require_file, require_quote

TEMPLATES = ("split_divider", "matched_crossfade", "editorial_panels")


def validate_semantic_plan(plan: dict, passage: str) -> dict:
    reject_forbidden(plan)
    if plan.get("animation_type") != "before_after":
        raise PlanError("animation_type must be before_after")
    if plan.get("template_id") not in TEMPLATES:
        raise PlanError("Unknown before/after template")
    if plan.get("style_preset") not in PRESETS:
        raise PlanError("Unknown style preset")
    for side in ("before", "after"):
        item = plan.get(side)
        if not isinstance(item, dict):
            raise NeedsAssets(f"A {side} asset is required")
        require_file(item.get("path"))
        label = item.get("label")
        if not isinstance(label, str) or not label or label not in passage:
            raise PlanError(f"The {side} label must be an exact substring of the passage")
        date = item.get("date")
        if date is not None and (not isinstance(date, str) or date not in passage):
            raise PlanError("A date is shown only when that date is written in the passage")
    if plan.get("viewpoints_differ") and plan.get("template_id") == "split_divider":
        raise PlanError("Different viewpoints are not shown as a registered split")
    if plan.get("viewpoints_differ") and not plan.get("disclosure"):
        raise PlanError("Different viewpoints need a visible disclosure")
    beats = plan.get("beats")
    if not isinstance(beats, list) or not 3 <= len(beats) <= 4:
        raise PlanError("Use 3 or 4 beats")
    for beat in beats:
        require_quote(beat.get("evidence_quote", ""), passage)
        if beat.get("action") not in {"establish", "reveal_after", "emphasize", "divider"}:
            raise PlanError("Unknown before/after action")
    return plan
