"""Local narration plan: pause tags, sentence pauses, and paragraph pauses.

Pause markup is removed before any model call. The original text is kept
separately from the spoken pieces.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_PAUSE_MS = 10_000
PIPELINE_VERSION = 2

NARRATION_EXAMPLE = (
    "वडनगर का एक छोटा-सा रेलवे स्टेशन। [pause=600ms]\n"
    "यहीं से शुरू हुई एक यात्रा। [pause=800ms]\n"
    "एक छोटे शहर से... देश के सबसे बड़े मंच तक। [pause=600ms]\n"
    "यह कहानी है उम्मीद की, मेहनत की, और विश्वास की।"
)

_TAG = re.compile(r"\[([^\[\]]*)\]")
_PAUSE = re.compile(r"pause=(\d+)\s*(ms|s)\s*", re.IGNORECASE)
_PARAGRAPH_BREAK = re.compile(r"(\n[ \t]*\n)")
_SENTENCE_MARKS = set("।॥?!！？")


class NarrationError(ValueError):
    """The script contains pause markup the lab will not speak."""


@dataclass(frozen=True)
class SpeechPiece:
    raw: str
    model_text: str
    boundary: str

    def as_dict(self) -> dict:
        return {
            "type": "speech",
            "text": self.model_text,
            "raw": self.raw,
            "boundary": self.boundary,
        }


@dataclass(frozen=True)
class PauseMark:
    ms: int
    source: str

    def as_dict(self) -> dict:
        return {"type": "pause", "ms": self.ms, "source": self.source}


@dataclass(frozen=True)
class NarrationPlan:
    original: str
    spoken_text: str
    events: tuple[tuple[str, SpeechPiece | PauseMark], ...]

    def speech(self) -> list[SpeechPiece]:
        return [item for kind, item in self.events if kind == "speech" and isinstance(item, SpeechPiece)]

    def model_segments(self) -> list[SpeechPiece]:
        return [piece for piece in self.speech() if piece.model_text]

    def to_dict(self) -> list[dict]:
        return [item.as_dict() for _, item in self.events]


def plan_narration(
    text: str,
    sentence_pause_ms: int,
    paragraph_pause_ms: int,
    max_chars: int = 180,
) -> NarrationPlan:
    """Turn the original script into spoken pieces and silence marks."""
    if max_chars < 8:
        raise NarrationError("max_chars must be at least 8.")
    _check_pause_range("Sentence pause", sentence_pause_ms, 5_000)
    _check_pause_range("Paragraph pause", paragraph_pause_ms, 5_000)
    tokens = _tokenize(text or "")
    spoken = "".join(value for kind, value in tokens if kind == "text")
    events: list[tuple[str, SpeechPiece | PauseMark]] = []
    for kind, value in tokens:
        if kind == "pause":
            events.append(("pause", PauseMark(int(value), "explicit")))
            continue
        events.extend(_events_for_block(str(value), sentence_pause_ms, paragraph_pause_ms, max_chars))
    events = _label_explicit_boundaries(events)
    _reject_stacked_pauses(events)
    for piece in (item for kind, item in events if kind == "speech" and isinstance(item, SpeechPiece)):
        assert_model_text(piece.model_text)
    if "".join(piece.raw for piece in (item for kind, item in events if kind == "speech")) != spoken:
        raise NarrationError("The spoken plan dropped or repeated part of the script.")
    return NarrationPlan(original=text or "", spoken_text=spoken, events=tuple(events))


def assert_model_text(text: str) -> None:
    """Refuse markup that was supposed to stay out of the model call."""
    if "[" in text or "]" in text or "pause=" in text.lower():
        raise NarrationError("Pause markup was about to be sent to the speech model.")


def format_preview(plan: NarrationPlan, settings: dict, preset_label: str) -> str:
    """Describe the spoken pieces, pauses, and the settings that will be used."""
    lines = [
        f"Preset: {preset_label}",
        (
            "Model settings: "
            f"exaggeration={_num(settings.get('exaggeration'))}, "
            f"cfg_weight={_num(settings.get('cfg_weight'))}, "
            f"temperature={_num(settings.get('temperature'))}, "
            f"repetition_penalty={_num(settings.get('repetition_penalty'))}, "
            f"min_p={_num(settings.get('min_p'))}, "
            f"top_p={_num(settings.get('top_p'))}."
        ),
        (
            f"Sentence pause: {int(settings.get('sentence_pause_ms', 0))} ms. "
            f"Paragraph pause: {int(settings.get('paragraph_pause_ms', 0))} ms. "
            "Explicit [pause=...] tags are additional and replace the automatic pause at that boundary."
        ),
        "These presets only change the settings above. They are not emotion controls.",
        "",
        "Text that will be spoken:",
    ]
    spoken_bits = [piece.model_text for piece in plan.model_segments()]
    lines.append("\n".join(spoken_bits) if spoken_bits else "(no spoken text)")
    lines.append("")
    lines.append("Segments:")
    number = 0
    for kind, item in plan.events:
        if kind == "speech" and isinstance(item, SpeechPiece):
            if not item.model_text:
                continue
            number += 1
            lines.append(f"{number}. {item.model_text}")
            if item.boundary == "length":
                lines.append("   length split: automatic pause 0 ms (not a sentence pause)")
            else:
                lines.append(f"   boundary after this segment: {item.boundary}")
        elif kind == "pause" and isinstance(item, PauseMark):
            lines.append(f"   {item.source} pause: {item.ms} ms")
    if number == 0:
        lines.append("(nothing to speak)")
    return "\n".join(lines)


def _tokenize(text: str) -> list[tuple[str, str | int]]:
    tokens: list[tuple[str, str | int]] = []
    cursor = 0
    for match in _TAG.finditer(text):
        _append_text(tokens, text[cursor : match.start()])
        tokens.append(("pause", _parse_tag(match.group(0), match.group(1))))
        cursor = match.end()
    _append_text(tokens, text[cursor:])
    return tokens


def _append_text(tokens: list[tuple[str, str | int]], chunk: str) -> None:
    if "[" in chunk or "]" in chunk:
        raise NarrationError(
            "There is an unclosed or stray bracket. Pause tags look like [pause=300ms] or "
            "[pause=1s]. Malformed tags are rejected instead of being spoken."
        )
    if chunk:
        tokens.append(("text", chunk))


def _parse_tag(raw: str, inner: str) -> int:
    match = _PAUSE.fullmatch(inner.strip())
    if match is None:
        raise NarrationError(
            f"Unsupported tag {raw}. Only [pause=300ms], [pause=700ms], or [pause=1s] is accepted. "
            "This tag was not sent to the speech model."
        )
    amount = int(match.group(1))
    unit = match.group(2).lower()
    milliseconds = amount if unit == "ms" else amount * 1000
    if milliseconds < 1 or milliseconds > MAX_PAUSE_MS:
        raise NarrationError(
            f"{raw} is {milliseconds} ms. Explicit pauses must be from 1 ms to {MAX_PAUSE_MS} ms (10 seconds)."
        )
    return milliseconds


def _check_pause_range(name: str, value: int, limit: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise NarrationError(f"{name} must be a whole number of milliseconds.")
    if value < 0 or value > limit:
        raise NarrationError(f"{name} must be between 0 and {limit} ms.")


def _events_for_block(
    text: str,
    sentence_pause_ms: int,
    paragraph_pause_ms: int,
    max_chars: int,
) -> list[tuple[str, SpeechPiece | PauseMark]]:
    if text == "":
        return []
    paragraphs, separators = _paragraphs(text)
    events: list[tuple[str, SpeechPiece | PauseMark]] = []
    for index, paragraph in enumerate(paragraphs):
        sentences = _sentences(paragraph)
        last_paragraph = index == len(paragraphs) - 1
        for sentence_index, sentence in enumerate(sentences):
            pieces = _split_oversized(sentence, max_chars)
            last_sentence = sentence_index == len(sentences) - 1
            for piece_index, piece in enumerate(pieces):
                last_piece = piece_index == len(pieces) - 1
                raw = piece
                if last_piece and last_sentence and separators[index]:
                    raw += separators[index]
                if not last_piece:
                    boundary = "length"
                    pause: tuple[str, int] | None = None
                elif not last_sentence:
                    boundary = "sentence"
                    pause = ("sentence", sentence_pause_ms)
                elif not last_paragraph:
                    boundary = "paragraph"
                    pause = ("paragraph", paragraph_pause_ms)
                else:
                    boundary = "end"
                    pause = None
                events.append(("speech", SpeechPiece(raw=raw, model_text=raw.strip(), boundary=boundary)))
                if pause is not None:
                    events.append(("pause", PauseMark(pause[1], pause[0])))
    return events


def _paragraphs(text: str) -> tuple[list[str], list[str]]:
    parts = _PARAGRAPH_BREAK.split(text)
    paragraphs: list[str] = []
    separators: list[str] = []
    buffer = ""
    for index, part in enumerate(parts):
        if index % 2 == 0:
            buffer += part
            continue
        if buffer == "":
            buffer += part
            continue
        paragraphs.append(buffer)
        separators.append(part)
        buffer = ""
    if buffer != "" or not paragraphs:
        paragraphs.append(buffer)
        separators.append("")
    return paragraphs, separators


def _sentences(text: str) -> list[str]:
    if text == "":
        return []
    parts: list[str] = []
    start = 0
    index = 0
    while index < len(text):
        if _is_sentence_end(text, index):
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


def _is_sentence_end(text: str, index: int) -> bool:
    char = text[index]
    if char in _SENTENCE_MARKS:
        return True
    if char != ".":
        return False
    previous = text[index - 1] if index else ""
    nxt = text[index + 1] if index + 1 < len(text) else ""
    if previous == "." or nxt == ".":
        return False
    if previous.isdigit() and nxt.isdigit():
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
        if window[index] in ",，;:、—–" or window[index].isspace():
            return index + 1
    return 0


def _label_explicit_boundaries(
    events: list[tuple[str, SpeechPiece | PauseMark]],
) -> list[tuple[str, SpeechPiece | PauseMark]]:
    labeled: list[tuple[str, SpeechPiece | PauseMark]] = []
    for index, (kind, item) in enumerate(events):
        if kind == "speech" and isinstance(item, SpeechPiece) and item.boundary == "end":
            nxt = events[index + 1] if index + 1 < len(events) else None
            if nxt and nxt[0] == "pause" and isinstance(nxt[1], PauseMark) and nxt[1].source == "explicit":
                item = SpeechPiece(raw=item.raw, model_text=item.model_text, boundary="explicit")
        labeled.append((kind, item))
    return labeled


def _reject_stacked_pauses(events: list[tuple[str, SpeechPiece | PauseMark]]) -> None:
    """An explicit pause replaces the automatic pause at the same boundary."""
    for index, (kind, item) in enumerate(events):
        if kind != "speech" or not isinstance(item, SpeechPiece):
            continue
        if item.boundary not in {"sentence", "paragraph"}:
            continue
        following = events[index + 1] if index + 1 < len(events) else None
        if following and following[0] == "pause" and isinstance(following[1], PauseMark):
            if following[1].source == "explicit":
                raise NarrationError(
                    "An automatic pause was stacked on an explicit pause. This should not be generated."
                )
