"""Overlay plans. Coordinates are fractions of the displayed frame, not tracking output."""
from __future__ import annotations

from documentary_graphics.errors import GraphicsPlanError, UnsupportedCapability
from documentary_graphics.fields import (
    coordinate_source,
    keyframes,
    placement_mode,
    point,
    rect,
    reject_cut_crossing,
    reject_forbidden,
    timing_block,
    unit,
)
from documentary_graphics.tokens import PRESET_NAMES

TYPES = (
    "location_callout",
    "identity_callout",
    "detail_highlight",
    "detail_spotlight",
    "date_label",
    "key_fact",
    "evidence_inset",
    "route_line",
    "route_direction",
    "measurement",
)
ANCHOR_MODES = ("fixed", "manual_keyframes", "manual_anchor")
CALLOUTS = {"location_callout", "identity_callout"}
MEASURE_KINDS = {"count", "percentage", "distance", "duration", "estimate"}


class OverlayPlanError(GraphicsPlanError):
    pass


def _raise(exc: GraphicsPlanError) -> None:
    if isinstance(exc, UnsupportedCapability):
        raise exc
    raise OverlayPlanError(str(exc)) from exc


def _protected(plan: dict) -> list[dict]:
    regions = []
    for region in plan.get("protected_regions") or []:
        if region.get("keyframes"):
            keys = []
            for key in region["keyframes"]:
                keys.append({"t": float(key["t"]), **rect(key, "protected")})
            keys.sort(key=lambda item: item["t"])
            regions.append({"id": region.get("id") or "region", "keyframes": keys})
        else:
            regions.append({"id": region.get("id") or "region", **rect(region, "protected")})
    return regions


def validate_plan(plan: dict, *, duration: float | None = None) -> dict:
    try:
        reject_forbidden(plan)
    except GraphicsPlanError as exc:
        _raise(exc)
    if not isinstance(plan, dict):
        raise OverlayPlanError("Plan must be an object")
    if plan.get("schema_version") not in {None, "1.0"}:
        raise OverlayPlanError("Unsupported schema_version")
    if plan.get("automatic_tracking") is True:
        raise OverlayPlanError("Automatic tracking is not available. Place a fixed anchor or manual keyframes.")
    preset = plan.get("preset")
    if preset and preset not in PRESET_NAMES:
        raise OverlayPlanError(f"Unknown preset {preset!r}")
    overlays = plan.get("overlays")
    if not isinstance(overlays, list) or not overlays:
        raise OverlayPlanError("Add at least one overlay")
    cleaned = []
    for index, overlay in enumerate(overlays, start=1):
        if not isinstance(overlay, dict):
            raise OverlayPlanError("Each overlay must be an object")
        try:
            coordinate_source(overlay)
            kind = overlay.get("type")
            if kind not in TYPES:
                raise OverlayPlanError(f"Unknown overlay type {kind!r}")
            mode = placement_mode(overlay)
            fade = 0.35 if kind in CALLOUTS and "label_fade_duration" not in overlay else 0.0
            block = timing_block(overlay, duration=duration, default_fade=fade)
            if mode == "manual_anchor":
                keys = keyframes(overlay)
                reject_cut_crossing(keys, plan.get("cuts") or [])
                if not str(overlay.get("limitation") or plan.get("limitation") or "").strip():
                    raise OverlayPlanError("Manual keyframes need a limitation note. They are not automatic tracking.")
            anchor_mode = overlay.get("anchor_mode") or ("manual_keyframes" if mode == "manual_anchor" else "fixed")
            if anchor_mode not in ANCHOR_MODES:
                raise OverlayPlanError("Anchor mode must be fixed or manual_keyframes")
        except GraphicsPlanError as exc:
            _raise(exc)
            raise
        item = {
            "id": overlay.get("id") or f"overlay_{index:02d}",
            "module": "cinematic_overlays",
            "type": kind,
            "purpose": overlay.get("purpose") or "",
            "text": overlay.get("text") or "",
            "context": overlay.get("context") or "",
            "badge": overlay.get("badge") or "",
            "placement_mode": mode,
            "anchor_mode": "manual_keyframes" if mode == "manual_anchor" else "fixed",
            "label_placement": overlay.get("label_placement") or ("auto" if not overlay.get("label") else "screen_fixed"),
            **block,
        }
        if mode == "manual_anchor":
            item["anchor_keyframes"] = keys
            item["limitation"] = str(overlay.get("limitation") or plan.get("limitation")).strip()
        elif kind in CALLOUTS | {"detail_highlight", "detail_spotlight", "date_label", "key_fact"}:
            if overlay.get("camera_motion") == "moves" and not overlay.get("fixed_anchor_acknowledged") and overlay.get("anchor"):
                raise OverlayPlanError(
                    "The camera moves. A fixed anchor is not tracking. "
                    "Supply manual keyframes, or acknowledge that the anchor stays fixed in the frame."
                )
            if overlay.get("anchor"):
                item["anchor"] = point(overlay.get("anchor"), "anchor")
        if kind in CALLOUTS:
            if not str(item["text"]).strip():
                raise OverlayPlanError("This overlay needs display text")
            if overlay.get("label"):
                item["label"] = point(overlay.get("label"), "label")
            elif item["label_placement"] != "auto":
                raise OverlayPlanError("A callout needs a label position or label_placement auto")
            prefer = overlay.get("prefer") or "upper_left"
            item["prefer"] = prefer
        elif kind == "date_label":
            if not str(item["text"]).strip():
                raise OverlayPlanError("This overlay needs display text")
            item["label"] = point(overlay.get("label") or {}, "label")
        elif kind in {"detail_highlight", "detail_spotlight"}:
            item["rect"] = rect(overlay.get("rect") or {}, "rect")
            item["template"] = overlay.get("template") or ("focus_rect" if kind == "detail_highlight" else "outline")
            if item["template"] not in {"outline", "ring", "focus_rect"}:
                raise OverlayPlanError("Spotlight template must be outline, ring, or focus_rect")
            item["dim"] = bool(overlay.get("dim"))
            if overlay.get("label"):
                item["label"] = point(overlay["label"], "label")
        elif kind == "key_fact":
            if not str(item["text"]).strip():
                raise OverlayPlanError("A fact panel needs text")
            item["context"] = overlay.get("context") or ""
            if overlay.get("label"):
                item["label"] = point(overlay["label"], "label")
            item["prefer"] = overlay.get("prefer") or "lower_left"
        elif kind == "evidence_inset":
            if not str(overlay.get("asset") or "").strip():
                raise OverlayPlanError("An evidence inset needs a supplied asset")
            if not str(overlay.get("source_label") or "").strip():
                raise OverlayPlanError("An evidence inset needs a source label")
            item["asset"] = str(overlay["asset"])
            item["source_label"] = str(overlay["source_label"])
            item["provenance"] = overlay.get("provenance") or {}
            if not str(item["provenance"].get("note") or "").strip():
                raise OverlayPlanError("Evidence provenance needs a note")
            item["prefer"] = overlay.get("prefer") or "lower_right"
            if overlay.get("label"):
                item["label"] = point(overlay["label"], "label")
        elif kind in {"route_line", "route_direction"}:
            points = overlay.get("points")
            if not isinstance(points, list) or len(points) < 2:
                raise OverlayPlanError("A route needs at least two supplied points")
            item["points"] = [point(entry, "route") for entry in points]
            item["arrow"] = bool(overlay.get("arrow") or kind == "route_direction")
            item["limitation"] = overlay.get("limitation") or "Screen-space points. This is not perspective tracking."
        elif kind == "measurement":
            points = overlay.get("points")
            if not isinstance(points, list) or len(points) != 2:
                raise OverlayPlanError("A measurement needs two supplied screen points")
            item["points"] = [point(entry, "measurement") for entry in points]
            if not str(overlay.get("value") or "").strip() or not str(overlay.get("unit") or "").strip():
                raise OverlayPlanError("A measurement needs a supplied value and unit")
            measure_kind = overlay.get("kind")
            if measure_kind not in MEASURE_KINDS:
                raise OverlayPlanError("Measurement kind must be count, percentage, distance, duration, or estimate")
            item["value"] = str(overlay["value"])
            item["unit"] = str(overlay["unit"])
            item["kind"] = measure_kind
            item["context"] = overlay.get("context") or ""
            item["limitation"] = "Screen bracket between supplied points. Pixel distance is not a real-world measurement."
        cleaned.append(item)
    try:
        protected = _protected(plan)
        subtitle = plan.get("subtitle_area") or {"y": 0.86, "height": 0.14}
        subtitle_area = {"y": unit(subtitle.get("y", 0.86), "subtitle.y"), "height": unit(subtitle.get("height", 0.14), "subtitle.height")}
    except GraphicsPlanError as exc:
        _raise(exc)
        raise
    if not plan.get("allow_overlap"):
        for index, earlier in enumerate(cleaned):
            for later in cleaned[index + 1:]:
                if earlier["start_time"] < later["end_time"] and later["start_time"] < earlier["end_time"]:
                    raise OverlayPlanError("Overlapping graphics compete. Keep one primary message at a time.")
    style = plan.get("style") if isinstance(plan.get("style"), dict) else {}
    return {
        "schema_version": plan.get("schema_version") or "1.0",
        "input": plan.get("input"),
        "preset": preset,
        "overlays": cleaned,
        "protected_regions": protected,
        "subtitle_area": subtitle_area,
        "cuts": [float(cut) for cut in (plan.get("cuts") or [])],
        "style": {
            "line": style.get("line") or "",
            "backing": style.get("backing") or "",
            "ink": style.get("ink") or "",
        },
        "limitation": plan.get("limitation") or "",
        "factual_claim": bool(plan.get("factual_claim", False)),
        "sample_note": plan.get("sample_note") or "",
        "timing_source": plan.get("timing_source") or "manual",
    }
