"""Data plans. Values come from the passage and are not interpolated."""
from __future__ import annotations

import math
import re

from animation_types.documentary.common import PRESETS, PlanError, number_in_text, reject_forbidden, require_quote

TEMPLATES = ("bar_comparison", "line_trend", "number_counter")
YEAR = re.compile(r"^\d{4}$")


def validate_semantic_plan(plan: dict, passage: str) -> dict:
    reject_forbidden(plan)
    if plan.get("animation_type") != "data_animations":
        raise PlanError("animation_type must be data_animations")
    if plan.get("template_id") not in TEMPLATES:
        raise PlanError("Unknown data template")
    if plan.get("style_preset") not in PRESETS:
        raise PlanError("Unknown style preset")
    series = plan.get("series")
    if not isinstance(series, list) or len(series) < 1:
        raise PlanError("A chart needs the supplied values")
    if plan["template_id"] != "number_counter" and len(series) < 2:
        raise PlanError("A comparison needs at least two supplied values")
    unit = plan.get("unit")
    if not isinstance(unit, str) or not unit:
        raise PlanError("The unit is required")
    if unit == "%" and plan.get("percentage_interpretation") not in {"proportion_of_whole", "percentage_points"}:
        raise PlanError("A percentage needs a stated interpretation")
    if not isinstance(plan.get("source_label"), str) or not plan["source_label"]:
        raise PlanError("A readable source label is required")
    if plan["template_id"] == "bar_comparison" and plan.get("baseline", "zero") != "zero":
        if plan.get("baseline") != "disclosed" or "baseline" not in (plan.get("disclosure") or "").lower():
            raise PlanError("A bar chart uses a zero baseline unless an alternative is configured and disclosed")
    labels = []
    for row in series:
        value = row.get("value") if isinstance(row, dict) else None
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise PlanError("Every value must be a finite number")
        label = row.get("label") if isinstance(row, dict) else None
        if not isinstance(label, str) or not label:
            raise PlanError("Every value needs a category or date label")
        quote = require_quote(row.get("evidence_quote", ""), passage)
        if not number_in_text(value, quote):
            raise PlanError(f"The value {value} is not a standalone number in its evidence quote")
        if unit not in quote and unit not in passage:
            raise PlanError("The unit must appear in the passage")
        labels.append(label)
    if all(YEAR.match(label) for label in labels):
        years = [int(label) for label in labels]
        if years != sorted(years):
            raise PlanError("Dated points must stay in chronological order")
    beats = plan.get("beats")
    if not isinstance(beats, list) or not 3 <= len(beats) <= 4:
        raise PlanError("Use 3 or 4 beats")
    for beat in beats:
        require_quote(beat.get("evidence_quote", ""), passage)
    return plan
