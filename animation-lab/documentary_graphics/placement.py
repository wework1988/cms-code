"""Safe-area placement.

Automatic placement is a geometric heuristic. It does not look at the picture.
Without a detector or supplied protected regions, it only avoids margins,
the subtitle band, and other overlay boxes.
"""
from __future__ import annotations

from .errors import GraphicsPlanError

CANDIDATES = ("upper_left", "upper_right", "lower_left", "lower_right")


def wrap_lines(text: str, max_chars: int) -> list[str]:
    """Wrap on spaces. A Devanagari word stays whole so matras are not split."""
    words = [part for part in str(text).split(" ") if part]
    if not words:
        return []
    if len(words) == 1:
        return [words[0]]
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if len(trial) <= max(1, max_chars):
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def fit_text(
    text: str,
    *,
    frame_w: int,
    frame_h: int,
    font_px: float,
    min_px: float,
    max_width_frac: float,
    char_factor: float = 0.62,
) -> dict:
    size = float(font_px)
    floor = float(min_px)
    while size >= floor:
        char_w = size * char_factor
        max_chars = max(1, int((max_width_frac * frame_w) / char_w))
        lines = wrap_lines(text, max_chars)
        width_px = max((len(line) for line in lines), default=0) * char_w
        height_px = max(1, len(lines)) * size * 1.35 + size * 0.45
        if width_px <= max_width_frac * frame_w + 1 and height_px <= frame_h * 0.42:
            return {
                "lines": lines,
                "font_px": size,
                "width": width_px / frame_w,
                "height": height_px / frame_h,
            }
        size -= 2
    raise GraphicsPlanError("Text does not fit in the safe area. Shorten it or place it manually.")


def safe_bounds(margin: float, subtitle: dict | None) -> dict[str, float]:
    bottom = margin
    if subtitle:
        bottom = max(bottom, float(subtitle.get("height") or 0))
        if "y" in subtitle:
            bottom = max(bottom, 1 - float(subtitle["y"]))
    return {"left": margin, "top": margin, "right": margin, "bottom": bottom}


def _origin(name: str, width: float, height: float, safe: dict) -> dict[str, float]:
    if name == "upper_left":
        return {"x": safe["left"], "y": safe["top"]}
    if name == "upper_right":
        return {"x": 1 - safe["right"] - width, "y": safe["top"]}
    if name == "lower_left":
        return {"x": safe["left"], "y": 1 - safe["bottom"] - height}
    if name == "lower_right":
        return {"x": 1 - safe["right"] - width, "y": 1 - safe["bottom"] - height}
    if name == "center":
        return {"x": 0.5 - width / 2, "y": 0.5 - height / 2}
    raise GraphicsPlanError(f"Unknown placement candidate {name}")


def overlaps(a: dict, b: dict, pad: float = 0.008) -> bool:
    return not (
        a["x"] + a["width"] <= b["x"] + pad
        or b["x"] + b["width"] <= a["x"] + pad
        or a["y"] + a["height"] <= b["y"] + pad
        or b["y"] + b["height"] <= a["y"] + pad
    )


def inside_safe(rect: dict, safe: dict) -> bool:
    return (
        rect["x"] >= safe["left"] - 1e-6
        and rect["y"] >= safe["top"] - 1e-6
        and rect["x"] + rect["width"] <= 1 - safe["right"] + 1e-6
        and rect["y"] + rect["height"] <= 1 - safe["bottom"] + 1e-6
    )


def choose_placement(
    *,
    prefer: str,
    width: float,
    height: float,
    safe: dict,
    blocked: list[dict],
    allow_center: bool = False,
) -> dict:
    """Pick one corner and keep it. Candidates are not reconsidered per frame."""
    order = [prefer] + [name for name in CANDIDATES if name != prefer]
    if allow_center:
        order.append("center")
    for name in order:
        if name == "center" and not allow_center:
            continue
        origin = _origin(name, width, height, safe)
        rect = {"x": origin["x"], "y": origin["y"], "width": width, "height": height}
        if not inside_safe(rect, safe):
            continue
        if any(overlaps(rect, block) for block in blocked):
            continue
        return {"candidate": name, "x": origin["x"], "y": origin["y"], "width": width, "height": height, "heuristic": True}
    raise GraphicsPlanError("No safe corner fits this graphic. Place it manually or reduce the text.")


def _cross(ax, ay, bx, by, cx, cy) -> float:
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _segments_cross(p1, p2, q1, q2) -> bool:
    d1 = _cross(*p1, *p2, *q1)
    d2 = _cross(*p1, *p2, *q2)
    d3 = _cross(*q1, *q2, *p1)
    d4 = _cross(*q1, *q2, *p2)
    return d1 * d2 < 0 and d3 * d4 < 0


def point_in_rect(x: float, y: float, rect: dict) -> bool:
    return rect["x"] <= x <= rect["x"] + rect["width"] and rect["y"] <= y <= rect["y"] + rect["height"]


def segment_hits_rect(x1: float, y1: float, x2: float, y2: float, rect: dict) -> bool:
    if point_in_rect(x1, y1, rect) or point_in_rect(x2, y2, rect):
        return True
    corners = [
        (rect["x"], rect["y"]),
        (rect["x"] + rect["width"], rect["y"]),
        (rect["x"] + rect["width"], rect["y"] + rect["height"]),
        (rect["x"], rect["y"] + rect["height"]),
    ]
    edges = list(zip(corners, corners[1:] + corners[:1]))
    return any(_segments_cross((x1, y1), (x2, y2), start, end) for start, end in edges)


def leader_elbow(start: dict, end: dict, blocked: list[dict]) -> dict | None:
    """Bend a leader around protected rectangles. The target rectangle may contain the end point."""
    obstacles = [rect for rect in blocked if not point_in_rect(end["x"], end["y"], rect)]
    if not any(segment_hits_rect(start["x"], start["y"], end["x"], end["y"], rect) for rect in obstacles):
        return None
    elbow = {"x": end["x"], "y": start["y"]}
    if any(segment_hits_rect(start["x"], start["y"], elbow["x"], elbow["y"], rect) or segment_hits_rect(elbow["x"], elbow["y"], end["x"], end["y"], rect) for rect in obstacles):
        elbow = {"x": start["x"], "y": end["y"]}
    if any(segment_hits_rect(start["x"], start["y"], elbow["x"], elbow["y"], rect) or segment_hits_rect(elbow["x"], elbow["y"], end["x"], end["y"], rect) for rect in obstacles):
        raise GraphicsPlanError("The leader line crosses a protected region. Move the label or the anchor.")
    return elbow
