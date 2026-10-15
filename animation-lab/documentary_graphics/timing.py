"""Frame clock. State is a pure function of the requested time."""
from __future__ import annotations


def smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


def frame_time(index: int, fps: float) -> float:
    return index / fps


def interpolate_keys(keys: list[dict], seconds: float) -> dict[str, float]:
    """Smoothstep between hand-placed keyframes. Holds the ends. This is not a tracker."""
    if seconds <= keys[0]["t"]:
        return {"x": float(keys[0]["x"]), "y": float(keys[0]["y"])}
    if seconds >= keys[-1]["t"]:
        return {"x": float(keys[-1]["x"]), "y": float(keys[-1]["y"])}
    for earlier, later in zip(keys, keys[1:]):
        if earlier["t"] <= seconds <= later["t"]:
            weight = smoothstep((seconds - earlier["t"]) / (later["t"] - earlier["t"]))
            return {
                "x": earlier["x"] + (later["x"] - earlier["x"]) * weight,
                "y": earlier["y"] + (later["y"] - earlier["y"]) * weight,
            }
    return {"x": float(keys[-1]["x"]), "y": float(keys[-1]["y"])}


def anchor_at(overlay: dict, seconds: float) -> dict[str, float]:
    if overlay.get("anchor_mode") in {"manual_keyframes", "manual_anchor"} or overlay.get("placement_mode") == "manual_anchor":
        keys = overlay.get("anchor_keyframes")
        if keys:
            return interpolate_keys(keys, seconds)
    anchor = overlay.get("anchor") or {"x": 0.5, "y": 0.5}
    return {"x": float(anchor["x"]), "y": float(anchor["y"])}


def rect_at(region: dict, seconds: float) -> dict[str, float]:
    keys = region.get("keyframes")
    if not keys:
        return {
            "x": float(region["x"]),
            "y": float(region["y"]),
            "width": float(region["width"]),
            "height": float(region["height"]),
        }
    if seconds <= keys[0]["t"]:
        chosen = keys[0]
    elif seconds >= keys[-1]["t"]:
        chosen = keys[-1]
    else:
        for earlier, later in zip(keys, keys[1:]):
            if earlier["t"] <= seconds <= later["t"]:
                weight = smoothstep((seconds - earlier["t"]) / (later["t"] - earlier["t"]))
                return {
                    "x": earlier["x"] + (later["x"] - earlier["x"]) * weight,
                    "y": earlier["y"] + (later["y"] - earlier["y"]) * weight,
                    "width": earlier["width"] + (later["width"] - earlier["width"]) * weight,
                    "height": earlier["height"] + (later["height"] - earlier["height"]) * weight,
                }
        chosen = keys[-1]
    return {
        "x": float(chosen["x"]),
        "y": float(chosen["y"]),
        "width": float(chosen["width"]),
        "height": float(chosen["height"]),
    }


def clock_phase(start: float, reveal: float, fade: float, hold: float, exit_time: float, seconds: float) -> dict[str, float | bool]:
    """Line draw, then label fade, then hold, then a shared exit.

    During the line reveal the label stays hidden when a separate fade is set.
    When fade is 0, the text appears with the reveal progress.
    """
    line_end = start + reveal
    label_end = line_end + fade
    hold_end = label_end + hold
    end = hold_end + exit_time
    hidden = {"line": 0.0, "label": 0.0, "opacity": 0.0, "active": False, "appear": 0.0}
    if seconds < start or seconds >= end:
        return hidden
    if seconds < line_end:
        line = smoothstep((seconds - start) / reveal) if reveal else 1.0
        label = 0.0
    elif fade and seconds < label_end:
        line = 1.0
        label = smoothstep((seconds - line_end) / fade)
    else:
        line = 1.0
        label = 1.0
    if seconds < hold_end:
        opacity = 1.0
    else:
        opacity = 1.0 - smoothstep((seconds - hold_end) / exit_time)
    appear = line if fade == 0 else label
    return {"line": line, "label": label, "opacity": opacity, "active": True, "appear": appear}
