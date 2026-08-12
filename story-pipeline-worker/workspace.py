#!/usr/bin/env python3
"""Build a temporary --crime-root workspace from a Drupal bundle."""

from __future__ import annotations

import html
import os
import re
import textwrap
from pathlib import Path
from typing import Any

STORY_TYPE_TEMPLATE_DIRS = {
    "general": "general-story",
    "crime": "crime-section",
    "english": "english-story",
    "god_story": "general-story",
}

PART3_MARKER = "PART 3 — INPUT SLOTS"


def slugify(text: str, fallback: str = "story") -> str:
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:64] or fallback


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p>\s*<p>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def add_paragraph_breaks(text: str) -> str:
    """
    Insert paragraph breaks after Hindi/Hinglish sentence-ending punctuation
    (। ? !) so the Stage B segment splitter always cuts at sentence boundaries
    rather than at arbitrary character positions inside words.

    Without this, a story stored as one long line causes the splitter to
    produce fragments like 'ें बैठे दो लोग…' at the start of a segment,
    corrupting the first scene of each DeepSeek slice.
    """
    text = re.sub(r"([।?!])\s*(?=\S)", r"\1\n\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_ini(settings: dict[str, Any]) -> str:
    model = settings.get("model", "deepseek-v4-pro")
    batch = settings.get("scene_batch", 8)
    a = settings.get("max_tokens_a", 65536)
    b = settings.get("max_tokens_b", 131072)
    c = settings.get("max_tokens_c", 65536)
    return textwrap.dedent(
        f"""\
        [pipeline]
        folder_name = workspace
        max_step = 4
        force = false
        use_character_library = true

        [deepseek_connection]
        base_url = https://api.deepseek.com
        model = {model}
        api_max_retries = 12

        [temperature]
        value = 0.3

        [thinking]
        enabled = true
        reasoning_effort = max

        [token_budget]
        max_tokens_stage_a = {a}
        max_tokens_stage_b = {b}
        max_tokens_stage_c = {c}
        scene_batch = {batch}
        stage_c_parallel_batches = 4
        stage_c_batch_retries = 3
        stage_c_min_chars_per_scene = 1200
        stage_b_story_segments = 6
        stage_b_parallel_calls = 4
        stage_b_segment_overlap_chars = 220
        stage_b_segment_hard_cap = 24
        stage_b_cap_segments_by_story_length = true

        [smart_search]
        internet_enabled = false
        """
    )


def default_scene_breakdown_prompt_path() -> Path:
    import os

    override = (
        (os.environ.get("SCENE_BREAKDOWN_PROMPT") or "").strip()
        or (os.environ.get("SCENE_VALIDATE_PROMPT") or "").strip()
    )
    if override:
        return Path(override).expanduser().resolve()
    return Path("/Applications/MAMP/htdocs/myresearch2/docs/updated-scene-breakdown.md")


def load_scene_breakdown_prompt() -> str:
    path = default_scene_breakdown_prompt_path()
    if not path.is_file():
        raise FileNotFoundError(f"Scene breakdown prompt not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if "FULL STORY:" not in text or "REQUIRED OUTPUT FORMAT" not in text:
        raise ValueError(f"Scene breakdown prompt looks invalid (missing FULL STORY / output format): {path}")
    return text


def prepare_scene_breakdown_story(bundle: dict[str, Any], root: Path) -> tuple[Path, str, str]:
    """
    Prepare minimal workspace for scene breakdown generation: story text only.

    Returns (root_path, slug, full_story).
    """
    story = bundle["story"]
    story_id = story.get("id", "0")
    slug = slugify(story.get("title") or "", fallback=f"story-{story_id}")

    story_dir = root / "stories" / slug
    story_dir.mkdir(parents=True, exist_ok=True)

    full_story = strip_html(story.get("full_story") or "")
    if not full_story:
        raise ValueError("Story has no full_story — paste script in Drupal or run generate-story first.")
    full_story = add_paragraph_breaks(full_story)
    (story_dir / "FULL_STORY.txt").write_text(full_story + "\n", encoding="utf-8")

    return root, slug, full_story


def automation_repo() -> Path | None:
    import os

    raw = (os.environ.get("AUTOMATION_REPO") or "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    return path if path.is_dir() else None


def resolve_prompt_text(
    story_type: str,
    prompt_key: str,
    drupal_text: str,
    filename: str,
) -> str:
    """
    Prefer automation-repo template (source of truth), then Drupal taxonomy field.
    Drupal stores a copy for admin editing; repo file wins when present so prompt
    fixes in git apply immediately without a drush import-prompts step.
    """
    repo = automation_repo()
    folder = STORY_TYPE_TEMPLATE_DIRS.get((story_type or "general").strip().lower(), "general-story")
    if repo is not None:
        path = repo / folder / "bifuracted-template" / filename
        if path.is_file():
            fallback = path.read_text(encoding="utf-8").strip()
            if fallback and PART3_MARKER in fallback:
                return fallback

    text = (drupal_text or "").strip()
    if text and PART3_MARKER in text:
        return text
    return text


def prepare_storyboard_workspace(bundle: dict[str, Any], root: Path) -> tuple[Path, str]:
    """
    Write bundle into a temp package root for deepseek_pipeline.py --crime-root.

    Returns (root_path, slug).
    """
    story = bundle["story"]
    prompts = bundle["prompts"]
    settings = bundle.get("settings") or {}

    story_id = story.get("id", "0")
    slug = slugify(story.get("title") or "", fallback=f"story-{story_id}")
    story_type = story.get("story_type") or "general"

    stage_a = resolve_prompt_text(story_type, "stage_a", prompts.get("stage_a") or "", "stage-a-story-config.md")
    stage_b = resolve_prompt_text(story_type, "stage_b", prompts.get("stage_b") or "", "stage-b-scene-breakdown.md")
    stage_c = resolve_prompt_text(story_type, "stage_c", prompts.get("stage_c") or "", "stage-c-image-motion.md")

    tmpl = root / "bifuracted-template"
    tmpl.mkdir(parents=True, exist_ok=True)
    (tmpl / "stage-a-story-config.md").write_text(stage_a, encoding="utf-8")
    (tmpl / "stage-b-scene-breakdown.md").write_text(stage_b, encoding="utf-8")
    (tmpl / "stage-c-image-motion.md").write_text(stage_c, encoding="utf-8")

    characters = (story.get("characters_info") or prompts.get("characters") or "").strip()
    if not characters:
        repo = automation_repo()
        folder = STORY_TYPE_TEMPLATE_DIRS.get(story_type.strip().lower(), "general-story")
        if repo is not None:
            char_path = repo / folder / "bifuracted-template" / "character.txt"
            if char_path.is_file():
                characters = char_path.read_text(encoding="utf-8").strip()
    (tmpl / "character.txt").write_text(characters, encoding="utf-8")

    story_dir = root / "stories" / slug
    (story_dir / "template").mkdir(parents=True, exist_ok=True)
    full_story = strip_html(story.get("full_story") or "")
    if not full_story:
        raise ValueError("Story has no full_story — paste script in Drupal or run generate-story first.")
    full_story = add_paragraph_breaks(full_story)
    (story_dir / "FULL_STORY.txt").write_text(full_story + "\n", encoding="utf-8")

    full_story_english = strip_html(story.get("full_story_english") or "")
    if not full_story_english:
        asset_root = (os.environ.get("STORY_ASSET_ROOT") or "").strip()
        if asset_root:
            eng_asset = (
                Path(asset_root).expanduser()
                / story_type
                / slug
                / "script"
                / "FULL_STORY_ENGLISH.txt"
            )
            if eng_asset.is_file():
                full_story_english = eng_asset.read_text(encoding="utf-8").strip()
    if full_story_english:
        full_story_english = add_paragraph_breaks(full_story_english)
        (story_dir / "FULL_STORY_ENGLISH.txt").write_text(full_story_english + "\n", encoding="utf-8")

    (story_dir / "template" / "character.txt").write_text(characters, encoding="utf-8")

    # Engine syncs from story-to-run/story.txt on every run (full_story already paragraph-normalised).
    story_to_run = root / "story-to-run"
    story_to_run.mkdir(parents=True, exist_ok=True)
    (story_to_run / "story.txt").write_text(full_story + "\n", encoding="utf-8")

    (root / "deepseek.config.example.ini").write_text(build_ini(settings), encoding="utf-8")
    return root, slug
