"""Devanagari spellings turned into Latin forms for candidate retrieval only.

No extra package is required. The forms are a lookup aid. They do not prove
that a catalogue row is the requested place.
"""

from __future__ import annotations

import re
import unicodedata

_INDEPENDENT = {
    "अ": "a", "आ": "a", "इ": "i", "ई": "i", "उ": "u", "ऊ": "u",
    "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au",
    "ऋ": "ri",
}
_VOWEL = {
    "ा": "a", "ि": "i", "ी": "i", "ु": "u", "ू": "u",
    "े": "e", "ै": "ai", "ो": "o", "ौ": "au", "ृ": "ri",
}
_CONSONANT = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "ng",
    "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "ny",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "v", "श": "sh",
    "ष": "sh", "स": "s", "ह": "h",
    "क़": "q", "ख़": "kh", "ग़": "g", "ज़": "z", "फ़": "f",
    "ड़": "r", "ढ़": "rh",
}
_VIRAMA = "्"
_NASAL = {"ं", "ँ"}
_NUKTA = "़"


def _consume_nasal(text: str, index: int) -> tuple[str, int]:
    if index < len(text) and text[index] in _NASAL:
        return "n", index + 1
    return "", index


def latin_forms(name: str) -> list[str]:
    """Scholarly and practical Latin spellings. Empty when the name is not Devanagari."""
    text = unicodedata.normalize("NFC", name or "")
    if not re.search(r"[\u0900-\u097F]", text):
        return []
    scholarly: list[str] = []
    practical: list[str] = []
    last_inherent = False
    index = 0
    while index < len(text):
        char = text[index]
        if char in {" ", "-", "–", "—"}:
            scholarly.append(" ")
            practical.append(" ")
            last_inherent = False
            index += 1
            continue
        if char in _INDEPENDENT:
            nasal, index = _consume_nasal(text, index + 1)
            scholarly.append(_INDEPENDENT[char] + nasal)
            practical.append(_INDEPENDENT[char] + nasal)
            last_inherent = False
            continue
        base = _CONSONANT.get(char)
        if base is None:
            index += 1
            continue
        index += 1
        if index < len(text) and text[index] == _NUKTA:
            index += 1
        mark = ""
        if index < len(text) and text[index] in _VOWEL:
            mark = _VOWEL[text[index]]
            index += 1
        nasal, index = _consume_nasal(text, index)
        virama = index < len(text) and text[index] == _VIRAMA
        if virama:
            index += 1
        inherent = not mark and not virama
        scholarly.append(base + (mark or ("" if virama else "a")) + nasal)
        spoken = "o" if mark == "au" else mark
        if not spoken and not virama:
            spoken = "a"
        practical.append(base + ("" if virama else spoken) + nasal)
        last_inherent = inherent
    if last_inherent and practical and practical[-1].endswith("a") and not practical[-1].endswith("aa"):
        practical[-1] = practical[-1][:-1]
    forms = []
    for parts in (scholarly, practical):
        rendered = re.sub(r"\s+", " ", "".join(parts)).strip()
        if rendered and rendered not in forms:
            forms.append(rendered)
    return forms
