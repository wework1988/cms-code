"""Editable style tokens. Presets share one schema and differ in color, scale, and weight of the backing."""
from __future__ import annotations

PRESET_NAMES = ("documentary_bold", "cinematic_minimal", "archival_editorial")

# Noto Sans and Noto Sans Devanagari are bundled as Regular only.
# Hierarchy comes from size and color. The renderer does not synthesize a bold face.
PRESETS = {
    "documentary_bold": {
        "ink": "#f7f1e4",
        "accent": "#e2b657",
        "emphasis": "#d24b3a",
        "line": "#f4efe4",
        "backing": "linear-gradient(180deg, rgba(8,10,14,0.84), rgba(8,10,14,0.70))",
        "line_width": 2.0,
        "margin": 0.06,
        "kicker": 26,
        "body": 34,
        "title": 72,
        "impact": 84,
        "number": 120,
        "min_size": 24,
        "pad_x": 18,
        "pad_y": 12,
        "shadow": "0 12px 28px rgba(0,0,0,0.30)",
        "radius": 8,
        "entrance": 0.5,
        "exit": 0.45,
    },
    "cinematic_minimal": {
        "ink": "#f4f0e8",
        "accent": "#e6c98a",
        "emphasis": "#e6c98a",
        "line": "#f4f0e8",
        "backing": "linear-gradient(180deg, rgba(8,12,18,0.62), rgba(8,12,18,0.46))",
        "line_width": 1.5,
        "margin": 0.055,
        "kicker": 20,
        "body": 32,
        "title": 60,
        "impact": 68,
        "number": 104,
        "min_size": 22,
        "pad_x": 14,
        "pad_y": 8,
        "shadow": "0 8px 18px rgba(0,0,0,0.22)",
        "radius": 6,
        "entrance": 0.45,
        "exit": 0.4,
    },
    "archival_editorial": {
        "ink": "#f3ead7",
        "accent": "#c4a574",
        "emphasis": "#c4a574",
        "line": "#f3ead7",
        "backing": "linear-gradient(180deg, rgba(32,24,16,0.78), rgba(32,24,16,0.62))",
        "line_width": 1.5,
        "margin": 0.07,
        "kicker": 22,
        "body": 32,
        "title": 64,
        "impact": 76,
        "number": 112,
        "min_size": 22,
        "pad_x": 16,
        "pad_y": 10,
        "shadow": "0 8px 20px rgba(20,12,6,0.28)",
        "radius": 2,
        "entrance": 0.55,
        "exit": 0.45,
    },
}


def preset(name: str | None) -> dict:
    key = name or "cinematic_minimal"
    if key not in PRESETS:
        raise KeyError(key)
    return {"name": key, **PRESETS[key]}
