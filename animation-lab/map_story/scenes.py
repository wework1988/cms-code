"""Map a selected script passage onto scene numbers from scene.txt."""
from __future__ import annotations

import re
from dataclasses import dataclass

HEADING_RE = re.compile(
    r"--- Scene\s+(\d+)\s*/\s*~(\d+)\s*---\s*\nHindi line:\s*\n(.*?)(?=\n--- Scene\s+\d+\s*/|\Z)",
    re.DOTALL,
)


@dataclass(frozen=True)
class SceneLine:
    number: int
    hindi: str


def parse_scene_text(text: str) -> list[SceneLine]:
    scenes: list[SceneLine] = []
    for match in HEADING_RE.finditer(text or ""):
        hindi = match.group(3).strip()
        if not hindi:
            continue
        scenes.append(SceneLine(number=int(match.group(1)), hindi=hindi))
    return scenes


def _squash(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _sentences(value: str) -> list[str]:
    parts = re.split(r"[।.!?]+", value or "")
    out = []
    for part in parts:
        squashed = _squash(part)
        if len(squashed) >= 8:
            out.append(squashed)
    if not out:
        whole = _squash(value)
        if len(whole) >= 8:
            out.append(whole)
    return out


def scene_numbers_for_passage(passage: str, scenes: list[SceneLine]) -> list[int]:
    """Scene numbers whose narration overlaps this exact passage, in scene order."""
    passage_sq = _squash(passage)
    if len(passage_sq) < 8 or not scenes:
        return []
    found: list[int] = []
    for scene in scenes:
        if any(sentence in passage_sq for sentence in _sentences(scene.hindi)):
            found.append(scene.number)
    return found


def scene_video_name(numbers: list[int]) -> str | None:
    """scene_1_2_3 for scenes 1, 2 and 3."""
    if not numbers:
        return None
    unique = []
    for number in numbers:
        if number not in unique:
            unique.append(number)
    return "scene_" + "_".join(str(number) for number in unique)
