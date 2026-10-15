"""Smooth interpolation for manually supplied anchor keyframes."""
from __future__ import annotations

from documentary_graphics.timing import anchor_at, clock_phase, smoothstep

__all__ = ["anchor_at", "phase", "smoothstep"]


def phase(overlay: dict, seconds: float) -> dict[str, float | bool]:
    """Line progress, label opacity, and the shared exit fade. Out-of-range time is hidden."""
    fade = float(overlay.get("label_fade_duration") or 0)
    if overlay.get("type") != "location_callout":
        fade = 0.0
    return clock_phase(
        float(overlay["start_time"]),
        float(overlay["reveal_duration"]),
        fade,
        float(overlay["hold_duration"]),
        float(overlay["exit_duration"]),
        seconds,
    )
