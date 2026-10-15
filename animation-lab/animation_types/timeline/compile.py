"""Compiler-owned reveal times. DeepSeek does not place events on the clock or the frame."""
from __future__ import annotations

from .schema import TimelineValidationError, validate_semantic_plan
from .styles import LIMITS


def reveal_times(count: int, duration: float, hold: float) -> tuple[list[float], float]:
    """Equal steps through the clip, then a still overview. Not historical scale."""
    overview = round(duration - hold, 3)
    first = 1.0
    last = round(overview - 2.0, 3)
    if last <= first or overview <= last:
        raise TimelineValidationError(
            "Duration is too short for this milestone count and the final hold. "
            "Use a longer clip or a shorter final hold."
        )
    if count == 1:
        return [first], overview
    step = (last - first) / (count - 1)
    if step < 1.6:
        raise TimelineValidationError(
            "Milestones would be closer than 1.6 seconds. "
            "The horizontal timeline cannot reveal them clearly at this duration."
        )
    times = [round(first + index * step, 3) for index in range(count)]
    return times, overview


def layout_slots(count: int, width: int = 1920) -> list[dict]:
    """Keep every caption box inside the frame and clear of its neighbours."""
    caption = 520 if count <= 3 else 430
    edge = caption / 2 + 48
    span = width - 2 * edge
    if count < 2 or span <= 0:
        raise TimelineValidationError("The horizontal layout cannot fit these milestones")
    gap = span / (count - 1)
    if caption > gap - 36:
        caption = gap - 36
        edge = caption / 2 + 48
        span = width - 2 * edge
        gap = span / (count - 1)
    if caption < LIMITS["min_caption_width"]:
        raise TimelineValidationError(
            "The horizontal layout cannot fit these captions without overlap or clipping. "
            "Shorten the captions or use fewer milestones."
        )
    slots = []
    for index in range(count):
        slots.append({
            "x": round(edge + index * gap, 2),
            "caption_width": round(caption, 2),
        })
    return slots


def compile_plan(plan: dict, passage: str, *, duration_seconds: float, fps: int = 30) -> dict:
    semantic = validate_semantic_plan(plan, passage, duration_seconds=duration_seconds)
    style = semantic["style"]
    times, overview = reveal_times(len(semantic["events"]), semantic["duration_seconds"], style["final_hold_seconds"])
    slots = layout_slots(len(semantic["events"]))
    emphasis = semantic["emphasis_event"] or semantic["events"][len(semantic["events"]) // 2]["id"]
    any_undated = any(event["date_precision"] == "undated" for event in semantic["events"])
    events = []
    for event, reveal, slot in zip(semantic["events"], times, slots):
        events.append({
            **event,
            "reveal": reveal,
            "x": slot["x"],
            "caption_width": slot["caption_width"],
        })
    return {
        **semantic,
        "emphasis_event": emphasis,
        "fps": fps,
        "width": 1920,
        "height": 1080,
        "overview_start": overview,
        "events": events,
        "spacing_note": (
            "Undated stages keep narrative order. Equal steps are not elapsed time."
            if any_undated
            else "Equal steps show milestone order, not proportional historical time. "
            "The clip duration is not a scale of the years."
        ),
    }
