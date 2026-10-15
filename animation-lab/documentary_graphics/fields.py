"""Shared plan fields. Coordinates are fractions of the displayed frame.

Origin is the top-left. x increases to the right, y increases downward.
Both axes run from 0 to 1, including any encoder padding in the frame height.
"""
from __future__ import annotations

from .errors import GraphicsPlanError, UnsupportedCapability

FORBIDDEN = {"javascript", "script", "css", "html", "shell", "command", "url"}
PLACEMENT_MODES = ("screen_fixed", "manual_anchor", "tracked_anchor", "scene_aligned")


def reject_forbidden(payload) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if str(key).lower() in FORBIDDEN:
                raise GraphicsPlanError(f"Unsupported field {key}")
            reject_forbidden(value)
    elif isinstance(payload, list):
        for item in payload:
            reject_forbidden(item)


def unit(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GraphicsPlanError(f"{name} must be a number from 0 to 1")
    number = float(value)
    if not 0 <= number <= 1:
        raise GraphicsPlanError(f"{name} must stay inside the frame")
    return number


def positive(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or float(value) <= 0:
        raise GraphicsPlanError(f"{name} must be greater than zero")
    return float(value)


def point(value: dict, name: str) -> dict:
    if not isinstance(value, dict):
        raise GraphicsPlanError(f"{name} needs x and y")
    return {"x": unit(value.get("x"), f"{name}.x"), "y": unit(value.get("y"), f"{name}.y")}


def rect(value: dict, name: str) -> dict:
    if not isinstance(value, dict):
        raise GraphicsPlanError(f"{name} needs x, y, width, and height")
    parsed = {
        "x": unit(value.get("x"), f"{name}.x"),
        "y": unit(value.get("y"), f"{name}.y"),
        "width": unit(value.get("width"), f"{name}.width"),
        "height": unit(value.get("height"), f"{name}.height"),
    }
    if parsed["x"] + parsed["width"] > 1 or parsed["y"] + parsed["height"] > 1:
        raise GraphicsPlanError(f"{name} must stay inside the frame")
    return parsed


def placement_mode(overlay: dict) -> str:
    requested = overlay.get("placement_mode")
    anchor_mode = overlay.get("anchor_mode")
    if requested in {"tracked_anchor", "scene_aligned"} or anchor_mode in {"tracked", "tracked_anchor", "scene_aligned"}:
        raise UnsupportedCapability(
            f"{requested or anchor_mode} is not implemented. "
            "Supply a screen position or manual keyframes. The renderer will not substitute a fixed point."
        )
    if requested and requested not in PLACEMENT_MODES:
        raise GraphicsPlanError(f"Unknown placement mode {requested!r}")
    if anchor_mode in {"manual_keyframes", "manual_anchor"}:
        return "manual_anchor"
    if requested:
        return requested
    return "screen_fixed"


def timing_block(overlay: dict, *, duration: float | None, default_fade: float) -> dict:
    start = overlay.get("start_time", 0)
    if isinstance(start, bool) or not isinstance(start, (int, float)) or float(start) < 0:
        raise GraphicsPlanError("start_time cannot be negative")
    reveal = positive(overlay.get("reveal_duration"), "reveal_duration")
    hold = positive(overlay.get("hold_duration"), "hold_duration")
    exit_time = positive(overlay.get("exit_duration"), "exit_duration")
    if "label_fade_duration" in overlay and overlay.get("label_fade_duration") is not None:
        fade = float(overlay.get("label_fade_duration"))
    else:
        fade = default_fade
    if fade < 0:
        raise GraphicsPlanError("label_fade_duration cannot be negative")
    end = float(start) + reveal + fade + hold + exit_time
    if duration is not None and end > duration + 0.02:
        raise GraphicsPlanError("The graphic runs past the end of the source video")
    source = overlay.get("timing_source") or "manual"
    if source == "narration_text":
        raise GraphicsPlanError(
            "Narration text alone does not provide timing. Supply manual times or an alignment reference."
        )
    if source not in {"manual", "alignment"}:
        raise GraphicsPlanError("timing_source must be manual or alignment")
    reference = overlay.get("timing_reference") or {}
    if source == "alignment":
        if not reference.get("scene_id") or reference.get("occurrence") in (None, ""):
            raise GraphicsPlanError("Alignment timing needs a scene id and an occurrence so a repeated phrase is not ambiguous.")
    return {
        "start_time": float(start),
        "reveal_duration": reveal,
        "label_fade_duration": fade,
        "hold_duration": hold,
        "exit_duration": exit_time,
        "end_time": end,
        "timing_source": source,
        "timing_reference": reference,
        "review_state": overlay.get("review_state") or ("needs_review" if source == "manual" else "aligned"),
    }


def keyframes(overlay: dict) -> list[dict]:
    keys = overlay.get("anchor_keyframes")
    if not isinstance(keys, list) or len(keys) < 2:
        raise GraphicsPlanError("Manual keyframes need at least two timestamped anchors")
    parsed = []
    for key in keys:
        if not isinstance(key, dict) or isinstance(key.get("t"), bool) or not isinstance(key.get("t"), (int, float)):
            raise GraphicsPlanError("Each keyframe needs t, x, and y")
        parsed.append({"t": float(key["t"]), **point(key, "keyframe")})
    parsed.sort(key=lambda item: item["t"])
    for earlier, later in zip(parsed, parsed[1:]):
        if later["t"] <= earlier["t"]:
            raise GraphicsPlanError("Keyframe times must increase")
    return parsed


def reject_cut_crossing(keys: list[dict], cuts: list) -> None:
    for cut in cuts or []:
        moment = float(cut)
        for earlier, later in zip(keys, keys[1:]):
            if earlier["t"] < moment < later["t"]:
                raise GraphicsPlanError("An anchor keyframe span crosses a scene cut. Split the graphic at the cut.")


def coordinate_source(overlay: dict) -> None:
    if str(overlay.get("coordinate_source") or "").lower() in {"model", "deepseek", "text", "narration"}:
        raise GraphicsPlanError(
            "Coordinates cannot come from a language model or the narration. "
            "Use a manual selection, a visual measurement, or a tracker."
        )
    if overlay.get("emphasis_substring"):
        raise GraphicsPlanError("Mark emphasis with structured text runs. Substring matching is ambiguous when a word repeats.")
