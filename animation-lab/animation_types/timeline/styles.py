"""One documentary preset. Colours are validated hex values, not CSS."""
from __future__ import annotations

PRESET = "documentary"

DEFAULT_STYLE = {
    "preset": PRESET,
    "background": "#10161E",
    "background_end": "#1A2432",
    "accent": "#E2C48A",
    "text": "#F4F0E8",
    "muted": "#8E99A6",
    "track": "#3C4654",
    "layout": "horizontal",
    "transition_seconds": 0.5,
    "final_hold_seconds": 4.5,
}

LIMITS = {
    "title": 80,
    "caption": 64,
    "date_label": 24,
    "title_lines": 2,
    "caption_lines": 2,
    "margin_x": 140,
    "min_caption_width": 280,
}
