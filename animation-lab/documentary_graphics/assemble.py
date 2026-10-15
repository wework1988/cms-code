"""Turn a validated graphic into a browser card with a stable screen position."""
from __future__ import annotations

from .errors import GraphicsPlanError
from .placement import choose_placement, fit_text, inside_safe, leader_elbow, safe_bounds
from .timing import rect_at
from .tokens import preset


def tokens_for(plan: dict) -> dict:
    chosen = preset(plan.get("preset"))
    style = plan.get("style") or {}
    for key, token in (("line", "line"), ("backing", "backing"), ("ink", "ink")):
        if style.get(key):
            chosen[token] = style[key]
    return chosen


def blocked_regions(regions: list[dict], start: float, end: float) -> list[dict]:
    """Sample protected rectangles across the graphic so a later drift still counts."""
    blocked = []
    times = [start, (start + end) / 2, end]
    for region in regions:
        for moment in times:
            blocked.append(rect_at(region, moment))
    return blocked


def place_card(
    text: str,
    overlay: dict,
    plan: dict,
    media: dict,
    tokens: dict,
    *,
    font_px: float,
    max_width: float,
    extra_height: float = 0.0,
) -> dict:
    fitted = fit_text(
        text,
        frame_w=media["width"],
        frame_h=media["height"],
        font_px=font_px,
        min_px=tokens["min_size"],
        max_width_frac=max_width,
    )
    height = fitted["height"] + extra_height
    safe = safe_bounds(tokens["margin"], plan.get("subtitle_area"))
    blocked = blocked_regions(plan.get("protected_regions") or [], overlay["start_time"], overlay["end_time"])
    others = plan.get("_placed") or []
    if overlay.get("label") and overlay.get("label_placement") != "auto":
        box = {"x": overlay["label"]["x"], "y": overlay["label"]["y"], "width": fitted["width"], "height": height}
        if not inside_safe(box, safe):
            raise GraphicsPlanError("The label sits outside the safe area.")
        if any(_hit(box, block) for block in blocked):
            raise GraphicsPlanError("The label overlaps a protected region. Move it.")
        placed = {"candidate": "manual", "heuristic": False, **box}
    else:
        placed = choose_placement(
            prefer=overlay.get("prefer") or "upper_left",
            width=fitted["width"],
            height=height,
            safe=safe,
            blocked=[*blocked, *others],
            allow_center=overlay.get("template") == "centered" or overlay.get("allow_center") is True,
        )
    placed["max_width"] = max_width
    placed["align"] = "center" if placed.get("candidate") == "center" or overlay.get("template") == "centered" else "left"
    placed["font_px"] = fitted["font_px"]
    return placed


def _hit(box: dict, block: dict) -> bool:
    from .placement import overlaps
    return overlaps(box, block)


def elbow_for(placement: dict, anchor: dict, plan: dict, overlay: dict) -> dict | None:
    start = {"x": placement["x"] + placement["width"], "y": placement["y"] + placement["height"] * 0.5}
    blocked = blocked_regions(plan.get("protected_regions") or [], overlay["start_time"], overlay["end_time"])
    return leader_elbow(start, anchor, blocked)
