#!/usr/bin/env python3
"""Parse Hindi scene.txt, translate to English scene.txt, merge full English story."""

from __future__ import annotations

import re
from dataclasses import dataclass

import requests

from asset_store import story_folder
from run_generate_story import generate_with_continuation, log
from workspace import slugify

SCENE_HEADING_RE = re.compile(r"^--- Scene \d+ / ~\d+ ---\s*$", re.MULTILINE)
HINDI_BLOCK_RE = re.compile(
    r"(--- Scene \d+ / ~\d+ ---\s*\nHindi line:\s*\n(.*?))(?=\n--- Scene \d+ / ~\d+ ---|\Z)",
    re.DOTALL,
)
HINDI_INLINE_RE = re.compile(
    r"--- Scene (\d+) / ~(\d+) ---\s*\nHindi line:\s*(.+?)(?=\n--- Scene|\Z)",
    re.DOTALL,
)


@dataclass(frozen=True)
class SceneEntry:
    number: int
    heading: str
    hindi_line: str


BATCH_SYSTEM_PROMPT = """You translate Hindi documentary narration scene lines into English for voice-over.
This is a narrated story/video script — preserve its tone and pacing.

For EVERY scene in the input, output:
1. The EXACT same scene heading line unchanged (--- Scene N / ~M ---)
2. Then this label on its own line: English line:
3. Then ONE English narration line (natural spoken English)

Strict rules:
- Same number of scenes as input, same scene numbers, same headings
- Translate the FULL Hindi line for each scene — do not summarize, condense, or skip any part
- One English line per Hindi line only; translate only the Hindi line shown under each heading
- Do NOT add any sentence, explanation, or conclusion not present in that scene's Hindi
- If the Hindi line ends with an open question, the English must also end with an open question — do not answer it
- Preserve all specific details exactly: dates, names, numbers, quoted dialogue, and any foreign phrase with its meaning
- Keep rhetorical/direct-address lines aimed at the viewer (e.g. "In your view, what was the biggest weakness...") with ALL options given — do not drop or shorten them
- Keep full closing/outro lines faithfully (like, subscribe, weekly content, thank you, "Jai Hind", etc.) — do not omit them as filler
- Do not romanticize, dramatize, or editorialize beyond what the Hindi says — faithful translation only
- Do NOT add commentary, notes, or markdown
- Do NOT skip, merge, or reuse text from other scenes
"""

SINGLE_SCENE_SYSTEM_PROMPT = """You translate ONE Hindi documentary narration line into English for voice-over.
This is a narrated story/video script — preserve tone and pacing.

Strict rules:
- Translate the FULL Hindi line — do not summarize, condense, or skip any part
- Do NOT add any sentence, explanation, or conclusion not present in the Hindi
- If the Hindi ends with an open question, the English must also end with an open question — do not answer it
- Preserve dates, names, numbers, quoted dialogue, and any foreign phrase with its meaning
- Keep rhetorical/direct-address lines and all options given — do not drop or shorten
- Keep outro/CTA lines faithfully (like, subscribe, thank you, "Jai Hind", etc.)
- Do not romanticize, dramatize, or editorialize beyond what the Hindi says

Output ONLY the English line text. No heading, no label, no commentary."""


def _collapse_ws(text: str) -> str:
    return " ".join((text or "").split())


def parse_hindi_scene_txt(text: str) -> list[SceneEntry]:
    """Parse scene.txt (headings + Hindi line blocks)."""
    raw = (text or "").strip()
    if not raw:
        return []

    entries: list[SceneEntry] = []
    for match in HINDI_BLOCK_RE.finditer(raw):
        block = match.group(1)
        lines = block.strip().splitlines()
        heading = lines[0].strip()
        hindi = match.group(2).strip()
        num_match = re.search(r"Scene (\d+)", heading)
        number = int(num_match.group(1)) if num_match else len(entries) + 1
        entries.append(SceneEntry(number=number, heading=heading, hindi_line=hindi))

    if entries:
        return entries

    # Fallback: inline "Hindi line: text" on one line.
    for match in HINDI_INLINE_RE.finditer(raw):
        number = int(match.group(1))
        chars = match.group(2)
        hindi = match.group(3).strip()
        heading = f"--- Scene {number} / ~{chars} ---"
        entries.append(SceneEntry(number=number, heading=heading, hindi_line=hindi))

    return entries


def format_batch_input(scenes: list[SceneEntry]) -> str:
    parts: list[str] = []
    for scene in scenes:
        parts.append(f"{scene.heading}\nHindi line:\n{scene.hindi_line.strip()}\n")
    return "\n".join(parts)


def parse_english_batch_response(text: str, expected: list[SceneEntry]) -> list[str]:
    """Extract English lines from model output; align by scene number."""
    raw = (text or "").strip()
    by_number: dict[int, str] = {}

    pattern = re.compile(
        r"--- Scene (\d+) / ~\d+ ---\s*\nEnglish line:\s*\n(.*?)(?=\n--- Scene \d+ / ~\d+ ---|\Z)",
        re.DOTALL,
    )
    for match in pattern.finditer(raw):
        num = int(match.group(1))
        english = _collapse_ws(match.group(2))
        if english:
            by_number[num] = english

    if not by_number:
        pattern_inline = re.compile(
            r"--- Scene (\d+) / ~\d+ ---\s*\nEnglish line:\s*(.+?)(?=\n--- Scene|\Z)",
            re.DOTALL,
        )
        for match in pattern_inline.finditer(raw):
            num = int(match.group(1))
            english = _collapse_ws(match.group(2))
            if english:
                by_number[num] = english

    out: list[str] = []
    missing: list[int] = []
    for scene in expected:
        english = by_number.get(scene.number, "").strip()
        if not english:
            missing.append(scene.number)
        out.append(english)
    if missing:
        raise ValueError(f"batch response missing English for scene(s): {missing[:10]}")
    return out


def _looks_misaligned(scene: SceneEntry, english: str) -> bool:
    """Heuristic: English clearly not a translation of this Hindi line."""
    hindi = _collapse_ws(scene.hindi_line)
    english = _collapse_ws(english)
    if not hindi or not english:
        return True

    hindi_lower = hindi.lower()
    english_lower = english.lower()

    cta_markers = (
        "subscribe", "comment", "like the video", "thank you", "jai hind",
        "weekly", "channel", "your view", "in your opinion", "tell us",
        "धन्यवाद", "जय हिंद", "सब्सक्राइब", "कमेंट", "लाइक", "राय", "बताइए",
    )
    hindi_is_cta = any(m in hindi_lower for m in cta_markers)
    narrative_markers = ("sewer", "tunnel", "pump", "vault", "digging", "water flow")
    if hindi_is_cta and any(m in english_lower for m in narrative_markers):
        return True

    # Very short Hindi outro but long unrelated English narration.
    if len(hindi) < 80 and len(english) > max(160, len(hindi) * 3):
        if hindi_is_cta:
            return True

    return False


def translate_single_scene(
    scene: SceneEntry,
    *,
    api_key: str,
    model: str,
    request_timeout_s: int = 180,
    retries: int = 4,
) -> str:
    user = (
        f"Scene {scene.number}\n"
        f"Hindi line:\n{scene.hindi_line.strip()}\n\n"
        "English line:"
    )
    raw, _finish = generate_with_continuation(
        api_key=api_key,
        model=model,
        system=SINGLE_SCENE_SYSTEM_PROMPT,
        user=user,
        max_tokens=min(2048, max(512, len(scene.hindi_line) * 4)),
        max_continuations=1,
        request_timeout_s=request_timeout_s,
        retries=retries,
    )
    english = _collapse_ws(raw.split("English line:")[-1] if "English line:" in raw else raw)
    if not english:
        raise ValueError(f"empty English for scene {scene.number}")
    return english


def _translate_scene_batch_once(
    batch: list[SceneEntry],
    *,
    api_key: str,
    model: str,
    request_timeout_s: int,
    retries: int,
) -> tuple[list[str], str | None]:
    user = (
        f"Translate scenes {batch[0].number}–{batch[-1].number} to English.\n"
        f"Output exactly {len(batch)} scene block(s) in the required format.\n\n"
        f"{format_batch_input(batch)}"
    )
    max_tokens = min(65536, max(8192, sum(len(s.hindi_line) for s in batch) * 3))
    raw, finish = generate_with_continuation(
        api_key=api_key,
        model=model,
        system=BATCH_SYSTEM_PROMPT,
        user=user,
        max_tokens=max_tokens,
        max_continuations=2,
        request_timeout_s=request_timeout_s,
        retries=retries,
    )
    english_lines = parse_english_batch_response(raw, batch)
    return english_lines, finish_reason_str(finish)


def finish_reason_str(finish: object) -> str | None:
    if finish is None:
        return None
    return str(finish).lower()


def translate_scene_batch_recursive(
    batch: list[SceneEntry],
    *,
    api_key: str,
    model: str,
    request_timeout_s: int,
    retries: int,
    depth: int = 0,
) -> list[str]:
    if not batch:
        return []

    if len(batch) == 1:
        return [translate_single_scene(batch[0], api_key=api_key, model=model, request_timeout_s=request_timeout_s, retries=retries)]

    try:
        english_lines, finish = _translate_scene_batch_once(
            batch,
            api_key=api_key,
            model=model,
            request_timeout_s=request_timeout_s,
            retries=retries,
        )
        misaligned = [
            scene.number
            for scene, english in zip(batch, english_lines)
            if _looks_misaligned(scene, english)
        ]
        if misaligned:
            raise ValueError(f"misaligned English for scene(s): {misaligned[:10]}")
        if finish == "length" and len(batch) > 4:
            raise ValueError("batch truncated; retry smaller")
        return english_lines
    except ValueError as exc:
        if len(batch) <= 4:
            log(f"[translate] batch scenes {batch[0].number}-{batch[-1].number} fallback to single-scene ({exc})")
            out: list[str] = []
            for scene in batch:
                out.append(
                    translate_single_scene(
                        scene,
                        api_key=api_key,
                        model=model,
                        request_timeout_s=request_timeout_s,
                        retries=retries,
                    )
                )
            return out
        mid = len(batch) // 2
        log(f"[translate] batch scenes {batch[0].number}-{batch[-1].number} split ({exc})")
        left = translate_scene_batch_recursive(
            batch[:mid],
            api_key=api_key,
            model=model,
            request_timeout_s=request_timeout_s,
            retries=retries,
            depth=depth + 1,
        )
        right = translate_scene_batch_recursive(
            batch[mid:],
            api_key=api_key,
            model=model,
            request_timeout_s=request_timeout_s,
            retries=retries,
            depth=depth + 1,
        )
        return left + right


def translate_scenes_to_english(
    scenes: list[SceneEntry],
    *,
    api_key: str,
    model: str,
    batch_size: int = 20,
    request_timeout_s: int = 180,
    retries: int = 4,
) -> list[str]:
    """Translate all Hindi scene lines in batches."""
    if not scenes:
        return []

    english_all: list[str] = []
    total_batches = (len(scenes) + batch_size - 1) // batch_size

    for batch_index in range(total_batches):
        start = batch_index * batch_size
        batch = scenes[start : start + batch_size]
        batch_num = batch_index + 1
        log(f"[translate] scene batch {batch_num}/{total_batches} ({len(batch)} scene(s))")

        english_lines = translate_scene_batch_recursive(
            batch,
            api_key=api_key,
            model=model,
            request_timeout_s=request_timeout_s,
            retries=retries,
        )
        english_all.extend(english_lines)
        log(f"[translate] scene batch {batch_num}/{total_batches} done")

    return english_all


def build_english_scene_txt(scenes: list[SceneEntry], english_lines: list[str]) -> str:
    if len(scenes) != len(english_lines):
        raise ValueError(f"scene count mismatch: {len(scenes)} headings vs {len(english_lines)} english lines")
    parts: list[str] = []
    for scene, english in zip(scenes, english_lines):
        parts.append(f"{scene.heading}\nEnglish line:\n{english.strip()}\n")
    return "\n".join(parts)


def merge_english_scenes_to_full_story(english_lines: list[str]) -> str:
    """Build continuous narration script from per-scene English lines."""
    parts = [_collapse_ws(line) for line in english_lines if _collapse_ws(line)]
    return " ".join(parts).strip()


def load_hindi_scene_text(story: dict, bundle: dict | None = None) -> str:
    """Load Hindi scene.txt from asset folder or Drupal file URL."""
    story_id = story.get("id") or ""
    title = story.get("title") or ""
    story_type = story.get("story_type") or "general"
    slug = slugify(title, fallback=f"story-{story_id}")

    folder = story_folder(slug, story_id, title, story_type, ensure=False)
    if folder is not None:
        scene_path = folder / "scenes" / "scene.txt"
        if scene_path.is_file():
            text = scene_path.read_text(encoding="utf-8").strip()
            if text:
                log(f"[translate] loaded Hindi scene.txt from asset: {scene_path}")
                return text

    url = (story.get("scene_file_url") or "").strip()
    if url:
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        text = resp.text.strip()
        if text:
            log("[translate] loaded Hindi scene.txt from URL")
            return text

    raise FileNotFoundError(
        "Hindi scene.txt not found. Run storyboard first so scene.txt exists on the story."
    )


def save_english_scene_assets(
    story_id: int | str,
    title: str,
    story_type: str | None,
    scene_english_txt: str,
    english_full: str,
) -> None:
    """Mirror English scene + merged script to story-asset folder."""
    slug = slugify(title or "", fallback=f"story-{story_id}")
    folder = story_folder(slug, story_id, title, story_type)
    if folder is None:
        return
    if scene_english_txt.strip():
        out = folder / "scenes" / "scene-english.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(scene_english_txt.strip() + "\n", encoding="utf-8")
        log(f"[assets] scene-english.txt → {out}")
    if english_full.strip():
        script_out = folder / "script" / "FULL_STORY_ENGLISH.txt"
        script_out.parent.mkdir(parents=True, exist_ok=True)
        script_out.write_text(english_full.strip() + "\n", encoding="utf-8")
        log(f"[assets] FULL_STORY_ENGLISH.txt → {script_out}")
