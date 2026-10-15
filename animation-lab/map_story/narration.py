"""Narration units and the focus-count policy for map clips.

Units follow scene lines when those lines sit inside the passage.
Otherwise they are sentences. Line breaks are spacing, not units.
"""
from __future__ import annotations

import re

from .scenes import SceneLine, _squash

ABBREVIATIONS = (
    "mr", "mrs", "ms", "dr", "prof", "st", "sr", "jr", "vs", "etc", "fig",
    "no", "nos", "smt", "shri", "gen", "col", "ltd", "inc", "approx",
)
_ABBR = re.compile(
    r"\b(?:" + "|".join(ABBREVIATIONS) + r")\.",
    re.IGNORECASE,
)
_DECIMAL = re.compile(r"(?<=\d)\.(?=\d)")
_INITIALS = re.compile(r"\b(?:[A-Za-z]\.){2,}")
_DOT = "\u0001"


def _protect(text: str) -> str:
    protected = _ABBR.sub(lambda match: match.group(0).replace(".", _DOT), text)
    protected = _INITIALS.sub(lambda match: match.group(0).replace(".", _DOT), protected)
    return _DECIMAL.sub(_DOT, protected)


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Spans of sentences in the original text, including their punctuation."""
    if not text or not text.strip():
        return []
    protected = _protect(text)
    spans: list[tuple[int, int]] = []
    start = 0
    for match in re.finditer(r"[।॥!?？]+|\.(?!\d)", protected):
        end = match.end()
        if text[start:end].strip():
            spans.append((start, end))
        start = end
    if start < len(text) and text[start:].strip():
        spans.append((start, len(text)))
    if not spans and text.strip():
        spans.append((0, len(text)))
    return spans


def split_sentences(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", text[start:end]).strip() for start, end in sentence_spans(text)]


def count_narration_units(passage: str, scenes: list[SceneLine] | None = None) -> dict:
    """Count meaningful narration units, not physical lines."""
    matched: list[SceneLine] = []
    if scenes:
        passage_sq = _squash(passage)
        for scene in scenes:
            line = _squash(scene.hindi)
            if len(line) >= 8 and line in passage_sq:
                matched.append(scene)
    if matched:
        units = [scene.hindi.strip() for scene in matched]
        counted = _target(len(units))
        counted.update({
            "units": units,
            "count": len(units),
            "method": "scene_lines",
        })
        return counted
    units = split_sentences(passage)
    counted = _target(len(units))
    counted.update({
        "units": units,
        "count": len(units),
        "method": "sentences",
    })
    return counted


def _target(count: int) -> dict:
    if count <= 1:
        decision = "one_unit_three_focuses"
        target = 3
    elif count == 2:
        decision = "two_units_three_focuses"
        target = 3
    elif count == 3:
        decision = "three_units_four_focuses"
        target = 4
    else:
        decision = "longer_passage_capped_at_four"
        target = 4
    return {"target": target, "decision": decision}


def duration_for_focuses(target: int) -> float:
    """Reading time for the focus stages. Not a narration timestamp."""
    return 18.0 if int(target) >= 4 else 14.0
