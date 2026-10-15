"""Hindi text checks and sentence-aware chunking.

Chunking is deterministic and lossless: joining the chunks rebuilds the
input string. The installed Chatterbox generate() call caps speech at
max_new_tokens=1000, which is 40 seconds at 25 tokens/second. Chunks stay
under MAX_CHUNK_CHARS so a typical Hindi sentence is unlikely to hit that cap.
"""

from __future__ import annotations

import re

MAX_CHUNK_CHARS = 180
MAX_TEXT_CHARS = 20000

SAMPLE_HINDI = (
    "नमस्कार। यह मेरी आवाज़ का एक परीक्षण है। आज हम एक नई कहानी "
    "सुनाने जा रहे हैं। इस कहानी में उम्मीद, मेहनत और विश्वास की बात होगी।"
)

_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
_LATIN = re.compile(r"[A-Za-z]")
_SENTENCE_MARKS = set("।॥?!！？")
_SECONDARY_MARKS = set(",，;:、—–")


def script_notice(text: str) -> str | None:
    """Recommend Devanagari without translating or rewriting the text."""
    devanagari = len(_DEVANAGARI.findall(text))
    latin = len(_LATIN.findall(text))
    if latin >= 6 and devanagari == 0:
        return (
            "This looks like Roman Hindi or another Latin-script language. "
            "Devanagari is recommended. The text is sent unchanged and is not "
            "translated or transliterated."
        )
    if latin > 0 and devanagari > 0 and latin > devanagari:
        return (
            "The text mixes Latin letters with Devanagari. Devanagari is "
            "recommended for Hindi. Nothing is translated automatically."
        )
    return None


def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split text on Hindi and common sentence boundaries without dropping characters."""
    if max_chars < 8:
        raise ValueError("max_chars must be at least 8.")
    if text == "":
        return []
    pieces: list[str] = []
    for sentence in _primary_sentences(text):
        pieces.extend(_split_oversized(sentence, max_chars))
    return _merge_blanks(pieces)


def _primary_sentences(text: str) -> list[str]:
    parts: list[str] = []
    start = 0
    index = 0
    while index < len(text):
        if _is_boundary(text, index):
            end = index + 1
            while end < len(text) and text[end] in " \t":
                end += 1
            parts.append(text[start:end])
            start = end
            index = end
            continue
        index += 1
    if start < len(text):
        parts.append(text[start:])
    return [part for part in parts if part]


def _is_boundary(text: str, index: int) -> bool:
    char = text[index]
    if char in _SENTENCE_MARKS or char == "\n":
        return True
    if char != ".":
        return False
    previous = text[index - 1] if index else ""
    nxt = text[index + 1] if index + 1 < len(text) else ""
    if previous.isdigit() and nxt.isdigit():
        return False
    if nxt == ".":
        return False
    return True


def _split_oversized(piece: str, limit: int) -> list[str]:
    if len(piece) <= limit:
        return [piece]
    parts: list[str] = []
    start = 0
    while start < len(piece):
        remaining = len(piece) - start
        if remaining <= limit:
            parts.append(piece[start:])
            break
        window = piece[start : start + limit]
        cut = _preferred_cut(window)
        if cut <= 0:
            cut = limit
        parts.append(piece[start : start + cut])
        start += cut
    return parts


def _preferred_cut(window: str) -> int:
    for index in range(len(window) - 1, 0, -1):
        if window[index] in _SECONDARY_MARKS or window[index].isspace():
            return index + 1
    return 0


def _merge_blanks(parts: list[str]) -> list[str]:
    merged: list[str] = []
    prefix = ""
    for part in parts:
        if part.strip() == "":
            if merged:
                merged[-1] += part
            else:
                prefix += part
            continue
        merged.append(prefix + part)
        prefix = ""
    if prefix:
        if merged:
            merged[-1] += prefix
        else:
            merged.append(prefix)
    return merged
