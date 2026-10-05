"""Build CMS story-generation prompts from Drupal master prompt templates."""

from __future__ import annotations

import re

CHARS_PER_MINUTE = 1000
LENGTH_TOLERANCE = 500

_V3_MARKERS = (
    "VERSION 6",
    "INPUT BLOCK — COMPLETE BELOW",
    "TOPIC / CENTRAL QUESTION:",
    "## EXECUTION ORDER",
)

_LEGACY_SOURCE = "[paste here]"
_LEGACY_LENGTH = "[e.g. 12,000 characters or 18 min]"


def is_v3_prompt(master: str) -> bool:
    """True for Astra v6-style prompts (INPUT BLOCK + EXECUTION ORDER)."""
    text = master or ""
    return any(marker in text for marker in _V3_MARKERS)


def _target_chars(duration_minutes: int) -> int:
    return max(0, int(duration_minutes)) * CHARS_PER_MINUTE


def _format_length_line(story_type: str, duration_minutes: int, target_chars: int) -> str:
    if story_type == "english":
        words_low = duration_minutes * 130
        words_high = duration_minutes * 150
        return (
            f"{duration_minutes} min → approximately {words_low:,}–{words_high:,} words "
            f"(~{target_chars:,} characters at narration pace)"
        )
    low = target_chars - LENGTH_TOLERANCE
    high = target_chars + LENGTH_TOLERANCE
    return (
        f"{duration_minutes} min → {target_chars:,} characters "
        f"(acceptable range: {low:,} – {high:,}; priority: character target)"
    )


def _replace_block(text: str, label: str, value: str, *, optional_placeholder: str = "[Optional]") -> str:
    """Replace `LABEL:\\n[placeholder]` with `LABEL:\\nvalue`."""
    if not value.strip():
        return text
    pattern = rf"(?im)(^\s*{re.escape(label)}\s*:?\s*\n)\[[^\]]+\]"
    repl = r"\g<1>" + value.strip()
    updated, count = re.subn(pattern, repl, text, count=1)
    if count:
        return updated
    pattern2 = rf"(?im)(^\s*{re.escape(label)}\s*:?\s*\n){re.escape(optional_placeholder)}"
    updated, count = re.subn(pattern2, repl, text, count=1)
    return updated if count else text


def _build_v3_prompt(
    master: str,
    source_text: str,
    duration: int,
    *,
    custom_instructions: str,
    topic: str,
    story_type: str,
) -> str:
    target_chars = _target_chars(duration)
    length_line = _format_length_line(story_type, duration, target_chars)
    prompt = master
    prompt = _replace_block(prompt, "TOPIC / CENTRAL QUESTION", topic or "Untitled story", optional_placeholder="[Enter topic]")
    prompt = _replace_block(
        prompt,
        "SOURCE MATERIAL",
        source_text.strip(),
        optional_placeholder="[Paste notes, ledger, transcripts or links; preserve source IDs]",
    )
    prompt = _replace_block(
        prompt,
        "REQUESTED LENGTH",
        length_line,
        optional_placeholder="[Minutes or character target; specify priority if supplying both]",
    )
    prompt = _replace_block(prompt, "RESEARCH MODE", "SOURCE-ONLY", optional_placeholder="[SOURCE-ONLY / VERIFY WITH EXTERNAL SOURCES]")
    if custom_instructions.strip():
        prompt = _replace_block(prompt, "ADDITIONAL CONSTRAINTS", custom_instructions.strip())
    return prompt


def _build_legacy_prompt(
    master: str,
    source_text: str,
    duration: int,
    *,
    custom_instructions: str,
    topic: str,
    story_type: str,
) -> str:
    target_chars = _target_chars(duration)
    length_line = _format_length_line(story_type, duration, target_chars)
    prompt = master

    if _LEGACY_SOURCE in prompt:
        prompt = prompt.replace(_LEGACY_SOURCE, source_text.strip(), 1)
    else:
        prompt = _replace_block(prompt, "SOURCE / RAW SCRIPT", source_text.strip())

    if _LEGACY_LENGTH in prompt:
        prompt = prompt.replace(_LEGACY_LENGTH, length_line, 1)
    else:
        prompt = _replace_block(prompt, "REQUESTED LENGTH", length_line)

    if topic.strip():
        prompt = _replace_block(prompt, "OPERATION / CASE NAME", topic.strip())
        prompt = _replace_block(prompt, "TOPIC NAME", topic.strip())

    if custom_instructions.strip():
        prompt = _replace_block(prompt, "ADDITIONAL NOTES", custom_instructions.strip())
        prompt = _replace_block(prompt, "ADDITIONAL CONSTRAINTS", custom_instructions.strip())

    return prompt


def build_cms_prompt(
    master: str,
    source_text: str,
    duration: int,
    *,
    custom_instructions: str = "",
    topic: str = "",
    story_type: str = "general",
) -> str:
    """Fill master prompt placeholders with story inputs."""
    if is_v3_prompt(master):
        return _build_v3_prompt(
            master,
            source_text,
            duration,
            custom_instructions=custom_instructions,
            topic=topic,
            story_type=story_type,
        )
    return _build_legacy_prompt(
        master,
        source_text,
        duration,
        custom_instructions=custom_instructions,
        topic=topic,
        story_type=story_type,
    )
