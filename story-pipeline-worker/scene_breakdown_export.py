#!/usr/bin/env python3
"""Convert scene breakdown markdown to simplified scene-breakdown.txt format."""

from __future__ import annotations

import re
from pathlib import Path

SCENE_HEADING_LINE = re.compile(r"(?m)^\s*--- Scene [^\n]+ ---\s*$")


def split_scenes(text: str) -> list[str]:
    """Split breakdown text into per-scene blocks (each starts with --- Scene … ---)."""
    ms = list(SCENE_HEADING_LINE.finditer(text))
    if not ms:
        return []
    scenes: list[str] = []
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        scenes.append(text[m.start() : end])
    return scenes


def _scene_heading_line(block: str) -> str:
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("--- Scene ") and stripped.endswith(" ---"):
            return stripped
    return ""


def _scene_number(heading: str) -> str | None:
    m = re.search(r"Scene\s+(\d+[a-zA-Z]?)\b", heading)
    return m.group(1) if m else None


def _total_from_heading(heading: str) -> int | None:
    m = re.search(r"/ ~(\d+) ---", heading)
    return int(m.group(1)) if m else None


def extract_hindi_line(block: str) -> str:
    inline = re.search(r"(?m)^Hindi line:\s+(\S.+)$", block)
    if inline:
        return inline.group(1).strip()
    m = re.search(
        r"(?m)^Hindi line:\s*\n(.+?)(?=\n\n|\nCharacter count:|\nScene context label:|\n--- Scene |\Z)",
        block,
        re.DOTALL,
    )
    return m.group(1).strip() if m else ""


def breakdown_to_scene_text(breakdown: str) -> str:
    """
    Produce simplified scene breakdown output:

    --- Scene 1 / ~36 ---
    Hindi line:
    {text}
    """
    scenes = split_scenes(breakdown)
    if not scenes:
        raise ValueError("No '--- Scene … ---' headings found in breakdown")

    first_heading = _scene_heading_line(scenes[0])
    total = _total_from_heading(first_heading) or len(scenes)

    parts: list[str] = []
    for idx, block in enumerate(scenes, start=1):
        heading = _scene_heading_line(block)
        scene_num = _scene_number(heading) if heading else str(idx)
        hindi = extract_hindi_line(block)
        if not hindi:
            raise ValueError(f"Scene {scene_num or idx} is missing a Hindi line")
        parts.append(f"--- Scene {scene_num} / ~{total} ---\nHindi line:\n{hindi}")

    return "\n\n".join(parts) + "\n"


def export_scene_breakdown_file(breakdown_path: Path, out_path: Path) -> int:
    """Write scene-breakdown.txt; return scene count."""
    breakdown = breakdown_path.read_text(encoding="utf-8")
    text = breakdown_to_scene_text(breakdown)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return text.count("--- Scene ")
