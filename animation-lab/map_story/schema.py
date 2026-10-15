"""Semantic map-focus plan schema validation (engine-independent)."""
from __future__ import annotations

import math
import re
from typing import Any

from map_story.themes import DEFAULT_STYLE, theme_ids

SUPPORTED_ACTIONS = frozenset({
    "establish_view",
    "highlight",
    "zoom_to_boundary",
    "show_label",
    "show_callout",
    "show_marker",
    "hold",
})

SUPPORTED_LEVELS = frozenset({"country", "state", "district", "city", "region"})
SUPPORTED_STYLES = theme_ids()
MEANINGFUL_ACTIONS = frozenset({
    "establish_view", "highlight", "zoom_to_boundary", "show_callout", "show_marker", "show_label",
})
SUPPORTED_FRAMES = frozenset({"world", "place", "auto"})
HEX = re.compile(r"^#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})$")

# Action persistence (documented for planners and compilers):
# - highlight: remains active until a later shot replaces that place's primary
#   highlight, or until parent_context="subdued" demotes a prior primary to context.
# - show_label: visible from its shot start (with short fade-in) until the shot
#   end unless a later label for the same place supersedes it; faded before callout
#   text that repeats the same string.
# - zoom_to_boundary / establish_view: drive camera keyframes; movement is
#   interpolated across the shot interval (not an instantaneous jump).
# - show_callout: appears at shot start, holds through shot end.
# - hold: keeps the current camera framing and active styles; no new motion.


class PlanValidationError(ValueError):
    pass


def require(ok: bool, message: str) -> None:
    if not ok:
        raise PlanValidationError(message)


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def is_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_color(value: Any) -> bool:
    return isinstance(value, str) and bool(HEX.match(value.strip()))


def validate_semantic_plan(plan: dict, *, duration_seconds: float | None = None, enforce_beats: bool = False) -> dict:
    require(isinstance(plan, dict), "Plan must be a JSON object")
    require(plan.get("schema_version") == "1.0", "schema_version must be '1.0'")
    require(plan.get("type") == "map_focus_sequence", "type must be 'map_focus_sequence'")

    duration = plan.get("duration_seconds")
    require(is_number(duration) and duration > 0, "duration_seconds must be a positive number")
    if duration_seconds is not None:
        require(
            abs(float(duration) - float(duration_seconds)) < 0.51,
            f"duration_seconds {duration} does not match requested {duration_seconds}",
        )

    require(is_string(plan.get("language")), "language must be a non-empty string")
    style = plan.get("style")
    custom_style = isinstance(style, str) and style.startswith("custom_")
    require(style in SUPPORTED_STYLES or custom_style,
            f"Unsupported style '{style}'. Supported: {', '.join(sorted(SUPPORTED_STYLES))}")

    ambiguity = plan.get("ambiguity") or []
    require(isinstance(ambiguity, list), "ambiguity must be a list")
    unresolved = [a for a in ambiguity if isinstance(a, dict) and a.get("unresolved")]
    require(not unresolved, f"Unresolved ambiguity must be fixed before render: {unresolved}")

    places = plan.get("places")
    require(isinstance(places, list) and places, "places must be a non-empty list")
    place_ids: set[str] = set()
    for place in places:
        require(isinstance(place, dict), "Each place must be an object")
        pid = place.get("id")
        require(is_string(pid), "Place id required")
        require(pid not in place_ids, f"Duplicate place id: {pid}")
        place_ids.add(pid)
        require(is_string(place.get("name")), f"Place {pid} missing name")
        require(place.get("level") in SUPPORTED_LEVELS, f"Place {pid} has unsupported level")
        parent = place.get("parent")
        if parent is not None:
            require(is_string(parent), f"Place {pid} parent must be a string id")
            require(parent in place_ids or any(p.get("id") == parent for p in places),
                    f"Place {pid} parent '{parent}' is unknown")
        # Forbid coordinate invention in the semantic plan.
        for banned in ("coordinates", "bbox", "geometry", "polygon", "lon", "lat", "zoom"):
            require(banned not in place, f"Place {pid} must not include '{banned}' (resolver owns geography)")

    # Second pass: parents must exist.
    for place in places:
        parent = place.get("parent")
        if parent is not None:
            require(parent in place_ids, f"Place {place['id']} parent '{parent}' is unknown")

    shots = plan.get("shots")
    require(isinstance(shots, list) and shots, "shots must be a non-empty list")
    shot_ids: set[str] = set()
    cursor = 0.0
    for i, shot in enumerate(shots):
        require(isinstance(shot, dict), "Each shot must be an object")
        sid = shot.get("id")
        require(is_string(sid), "Shot id required")
        require(sid not in shot_ids, f"Duplicate shot id: {sid}")
        shot_ids.add(sid)
        start = shot.get("start")
        end = shot.get("end")
        require(is_number(start) and is_number(end), f"Shot {sid} needs numeric start/end")
        require(end > start, f"Shot {sid} end must be greater than start")
        require(abs(start - cursor) < 1e-6, f"Shot {sid} starts at {start}, expected {cursor} (no gaps/overlaps)")
        cursor = float(end)
        frame = shot.get("frame")
        require(is_string(frame), f"Shot {sid} missing frame")
        # frame may be 'world' or a place id
        require(frame == "world" or frame in place_ids, f"Shot {sid} frame '{frame}' is unknown")

        actions = shot.get("actions")
        require(isinstance(actions, list) and actions, f"Shot {sid} needs actions")
        for action in actions:
            require(isinstance(action, dict), f"Shot {sid} action must be an object")
            atype = action.get("type")
            require(atype in SUPPORTED_ACTIONS, f"Unsupported action '{atype}' in shot {sid}. "
                    f"Supported: {', '.join(sorted(SUPPORTED_ACTIONS))}")
            if atype in ("highlight", "zoom_to_boundary", "show_label", "show_callout", "show_marker"):
                place = action.get("place")
                require(place in place_ids, f"Action {atype} in shot {sid} references unknown place")
            if atype == "show_marker":
                if "color" in action:
                    require(is_color(action.get("color")), f"show_marker in {sid} needs a hex color")
                if "size" in action:
                    size = action["size"]
                    require(is_number(size) and 4 <= float(size) <= 24, f"show_marker size in {sid} must be 4–24")
                if "pulse" in action:
                    require(isinstance(action["pulse"], bool), f"show_marker pulse in {sid} must be true or false")
                if "text" in action:
                    require(is_string(action.get("text")), f"show_marker text in {sid} must be a non-empty string")
            if atype in ("zoom_to_boundary", "establish_view") and "padding" in action:
                pad = action["padding"]
                require(is_number(pad) and 0.02 <= float(pad) <= 0.45,
                        f"padding in {sid} must be between 0.02 and 0.45")
            if atype == "highlight":
                color = action.get("color")
                require(is_color(color), f"highlight in {sid} needs a hex color")
                if "fill_opacity" in action:
                    fo = action["fill_opacity"]
                    require(is_number(fo) and 0 <= fo <= 1, f"fill_opacity in {sid} must be 0–1")
                if "parent_context" in action:
                    require(action["parent_context"] in ("subdued", "hidden", "none"),
                            f"parent_context in {sid} must be subdued|hidden|none")
            if atype in ("show_label", "show_callout"):
                require(is_string(action.get("text")), f"{atype} in {sid} needs text")
            if atype == "show_callout":
                if "presentation" in action:
                    require(action["presentation"] in ("text_box_with_arrow", "label_only"),
                            f"Unsupported callout presentation in {sid}")
                if "position" in action:
                    require(action["position"] in ("auto", "left", "right", "top", "bottom"),
                            f"Unsupported callout position in {sid}")
            for banned in ("coordinates", "bbox", "geometry", "lon", "lat", "zoom", "center"):
                require(banned not in action,
                        f"Action in {sid} must not include '{banned}' (compiler owns geography)")

    require(abs(cursor - float(duration)) < 1e-6,
            f"Shot timeline ends at {cursor}s but duration_seconds is {duration}")

    if enforce_beats:
        beats = meaningful_beat_count(plan)
        expected = plan.get("target_focus_count")
        if expected is not None:
            require(int(expected) == beats, f"Expected {expected} focus stages; found {beats}")
        else:
            require(3 <= beats <= 4, f"A map clip needs 3–4 meaningful focus beats; found {beats}")

    return plan


def style_from_snapshot(snapshot: dict) -> str:
    """New snapshots name a style. Older snapshots keep cinematic_terrain."""
    if "style" not in snapshot:
        return "cinematic_terrain"
    style = snapshot.get("style")
    if style not in SUPPORTED_STYLES:
        raise PlanValidationError(f"Unsupported map style '{style}'")
    return style


def meaningful_beat_count(plan: dict) -> int:
    """Count focus stages. Zoom, highlight, and label in one shot are one stage."""
    count = 0
    for shot in plan.get("shots") or []:
        actions = shot.get("actions") or []
        if any(isinstance(action, dict) and action.get("type") in MEANINGFUL_ACTIONS for action in actions):
            count += 1
    return count
