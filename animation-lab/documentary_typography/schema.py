"""Typography plans. Text, dates, and numbers must be supplied. Coordinates are frame fractions."""
from __future__ import annotations

from documentary_graphics.errors import GraphicsPlanError, UnsupportedCapability
from documentary_graphics.fields import (
    coordinate_source,
    placement_mode,
    point,
    rect,
    reject_forbidden,
    timing_block,
    unit,
)
from documentary_graphics.tokens import PRESET_NAMES

TYPES = (
    "location_title",
    "impact_word",
    "impact_phrase",
    "date_year",
    "key_number",
    "chapter_title",
    "quote_translation",
)
NUMBER_KINDS = {"count", "percentage", "distance", "duration", "estimate"}
TEMPLATES = {"upper_left", "lower_left", "centered"}


class TypePlanError(GraphicsPlanError):
    pass


def _raise(exc: GraphicsPlanError) -> None:
    if isinstance(exc, UnsupportedCapability):
        raise exc
    raise TypePlanError(str(exc)) from exc


def validate_plan(plan: dict, *, duration: float | None = None) -> dict:
    try:
        reject_forbidden(plan)
    except GraphicsPlanError as exc:
        _raise(exc)
    if plan.get("schema_version") not in {None, "1.0"}:
        raise TypePlanError("Unsupported schema_version")
    preset = plan.get("preset")
    if preset and preset not in PRESET_NAMES:
        raise TypePlanError(f"Unknown preset {preset!r}")
    overlays = plan.get("overlays")
    if not isinstance(overlays, list) or not overlays:
        raise TypePlanError("Add at least one typography graphic")
    cleaned = []
    for index, overlay in enumerate(overlays, start=1):
        try:
            coordinate_source(overlay)
            kind = overlay.get("type")
            if kind not in TYPES:
                raise TypePlanError(f"Unknown typography treatment {kind!r}")
            mode = placement_mode(overlay)
            if mode == "manual_anchor":
                raise TypePlanError("Typography stays screen-fixed. Attach objects with a cinematic overlay.")
            block = timing_block(overlay, duration=duration, default_fade=0.0)
        except GraphicsPlanError as exc:
            _raise(exc)
            raise
        item = {
            "id": overlay.get("id") or f"type_{index:02d}",
            "module": "documentary_typography",
            "type": kind,
            "purpose": overlay.get("purpose") or "",
            "placement_mode": "screen_fixed",
            "label_placement": overlay.get("label_placement") or ("auto" if not overlay.get("label") else "screen_fixed"),
            "prefer": overlay.get("prefer") or overlay.get("template") or "upper_left",
            "template": overlay.get("template") or overlay.get("prefer") or "upper_left",
            "badge": overlay.get("badge") or "",
            **block,
        }
        if item["template"] not in TEMPLATES and item["template"] not in {"upper_right", "lower_right"}:
            raise TypePlanError("Template must be upper_left, lower_left, or centered")
        if overlay.get("label"):
            item["label"] = point(overlay["label"], "label")
        if kind == "location_title":
            region = str(overlay.get("region") or "").strip()
            place = str(overlay.get("place") or "").strip()
            if not region or not place:
                raise TypePlanError("A location title needs a supplied region and a supplied place. Hierarchy is not guessed.")
            item["region"] = region
            item["place"] = place
            item["text"] = place
        elif kind == "impact_word":
            word = str(overlay.get("text") or "").strip()
            if not word or " " in word:
                raise TypePlanError("An impact word is one supplied word.")
            item["text"] = word
        elif kind == "impact_phrase":
            runs = overlay.get("runs")
            if not isinstance(runs, list) or not runs:
                raise TypePlanError("An impact phrase needs structured text runs.")
            parsed = []
            for run in runs:
                if not isinstance(run, dict) or not str(run.get("text") or ""):
                    raise TypePlanError("Each run needs text")
                parsed.append({"text": str(run["text"]), "emphasis": bool(run.get("emphasis"))})
            if not any(run["emphasis"] for run in parsed):
                raise TypePlanError("Mark the emphasized run explicitly.")
            item["runs"] = parsed
            item["text"] = "".join(run["text"] for run in parsed)
        elif kind == "date_year":
            year = str(overlay.get("year") or "").strip()
            explanation = str(overlay.get("explanation") or "").strip()
            if not year or not explanation:
                raise TypePlanError("A date needs a supplied year and a supplied explanation.")
            item["year"] = year
            item["explanation"] = explanation
            item["text"] = year
        elif kind == "key_number":
            value = str(overlay.get("value") or "").strip()
            number_unit = str(overlay.get("unit") or "").strip()
            context = str(overlay.get("context") or "").strip()
            number_kind = overlay.get("kind")
            if not value or not number_unit or not context:
                raise TypePlanError("A key number needs a supplied value, unit, and context.")
            if number_kind not in NUMBER_KINDS:
                raise TypePlanError("Number kind must be count, percentage, distance, duration, or estimate.")
            item["value"] = value
            item["unit"] = number_unit
            item["context"] = context
            item["kind"] = number_kind
            item["text"] = f"{value} {unit}"
        elif kind == "chapter_title":
            title = str(overlay.get("text") or "").strip()
            if not title:
                raise TypePlanError("A chapter title needs text.")
            if overlay.get("quotation") and not str((overlay.get("provenance") or {}).get("note") or "").strip():
                raise TypePlanError("A quotation needs provenance. An editorial title is not a quotation.")
            item["text"] = title
            item["editorial_demonstration"] = bool(overlay.get("editorial_demonstration"))
        elif kind == "quote_translation":
            quote = str(overlay.get("text") or "").strip()
            attribution = str(overlay.get("attribution") or "").strip()
            provenance = overlay.get("provenance") or {}
            if not quote or not attribution:
                raise TypePlanError("A quote needs supplied text and attribution.")
            if provenance.get("kind") not in {"quotation", "translation"}:
                raise TypePlanError("Provenance kind must be quotation or translation.")
            if not str(provenance.get("note") or "").strip():
                raise TypePlanError("Quote provenance needs a note.")
            item["text"] = quote
            item["attribution"] = attribution
            item["provenance"] = {"kind": provenance["kind"], "note": str(provenance["note"])}
        cleaned.append(item)
    if not plan.get("allow_overlap"):
        for index, earlier in enumerate(cleaned):
            for later in cleaned[index + 1:]:
                if earlier["start_time"] < later["end_time"] and later["start_time"] < earlier["end_time"]:
                    raise TypePlanError("Overlapping graphics compete. Keep one primary message at a time.")
    try:
        protected = []
        for region in plan.get("protected_regions") or []:
            protected.append({"id": region.get("id") or "region", **rect(region, "protected")})
        subtitle = plan.get("subtitle_area") or {"y": 0.86, "height": 0.14}
        subtitle_area = {"y": unit(subtitle.get("y", 0.86), "subtitle.y"), "height": unit(subtitle.get("height", 0.14), "subtitle.height")}
    except GraphicsPlanError as exc:
        _raise(exc)
        raise
    return {
        "schema_version": plan.get("schema_version") or "1.0",
        "module": "documentary_typography",
        "input": plan.get("input"),
        "preset": preset,
        "overlays": cleaned,
        "protected_regions": protected,
        "subtitle_area": subtitle_area,
        "factual_claim": bool(plan.get("factual_claim", False)),
        "sample_note": plan.get("sample_note") or "",
        "timing_source": plan.get("timing_source") or "manual",
        "style": plan.get("style") if isinstance(plan.get("style"), dict) else {},
    }
