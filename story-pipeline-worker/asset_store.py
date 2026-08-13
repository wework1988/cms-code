#!/usr/bin/env python3
"""Persist pipeline outputs under STORY_ASSET_ROOT/{type}/{node-id}-{title-slug}/."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from workspace import slugify

VALID_STORY_TYPES = frozenset({"general", "crime", "english", "god_story"})


def normalize_story_type(story_type: str | None) -> str:
    """Map API story_type to a folder name (general, crime, english, god_story)."""
    key = (story_type or "general").strip().lower()
    return key if key in VALID_STORY_TYPES else "general"


def asset_root() -> Path | None:
    """Root folder for story assets (from STORY_ASSET_ROOT env)."""
    raw = (os.environ.get("STORY_ASSET_ROOT") or "").strip()
    if not raw:
        return None
    root = Path(raw).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def folder_name(story_id: int | str, title: str) -> str:
    """CMS folder name: {node-id}-{title-slug}."""
    story_id = str(story_id)
    title_slug = slugify(title or "", fallback=f"story-{story_id}")
    return f"{story_id}-{title_slug}"


def _legacy_story_folder(root: Path, slug: str) -> Path:
    """Pre-category layout: {root}/{slug}/."""
    return root / slug


def _read_node_id(meta_file: Path) -> str:
    if not meta_file.is_file():
        return ""
    return meta_file.read_text(encoding="utf-8").strip()


def _find_existing_folder_by_node_id(type_root: Path, story_id: str) -> Path | None:
    """Locate an existing asset folder for this Drupal node (any naming scheme)."""
    if not type_root.is_dir():
        return None
    for child in sorted(type_root.iterdir()):
        if not child.is_dir():
            continue
        existing = _read_node_id(child / "meta" / "drupal-node-id.txt")
        if existing == story_id:
            return child
    return None


def _resolve_story_folder(
    slug: str,
    story_id: int | str,
    story_type: str | None = "general",
    title: str = "",
) -> Path | None:
    """Compute asset folder path without creating directories."""
    root = asset_root()
    if root is None:
        return None

    story_id = str(story_id)
    category = normalize_story_type(story_type)
    type_root = root / category
    preferred = type_root / folder_name(story_id, title or slug)

    existing = _find_existing_folder_by_node_id(type_root, story_id)
    if existing is not None:
        return existing

    legacy_candidates = [
        type_root / slug,
        type_root / f"{slug}-{story_id}",
        _legacy_story_folder(root, slug),
    ]
    for candidate in legacy_candidates:
        if not candidate.is_dir():
            continue
        meta = candidate / "meta" / "drupal-node-id.txt"
        existing_id = _read_node_id(meta)
        if existing_id == story_id or (not existing_id and candidate == type_root / slug):
            return candidate

    return preferred


def _ensure_story_folder(
    dest: Path,
    story_id: int | str,
    title: str = "",
    story_type: str | None = "general",
) -> Path:
    """Create subdirs + meta files when about to write assets."""
    category = normalize_story_type(story_type)
    for sub in ("meta", "script", "prompts", "scenes", "image-prompts", "audio"):
        (dest / sub).mkdir(parents=True, exist_ok=True)
    (dest / "audio" / "english").mkdir(parents=True, exist_ok=True)

    meta_dir = dest / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / "drupal-node-id.txt").write_text(str(story_id) + "\n", encoding="utf-8")
    if title:
        (meta_dir / "story-title.txt").write_text(title.strip() + "\n", encoding="utf-8")
    (meta_dir / "story-type.txt").write_text(category + "\n", encoding="utf-8")
    return dest


def story_folder(
    slug: str,
    story_id: int | str,
    title: str = "",
    story_type: str | None = "general",
    *,
    ensure: bool = True,
) -> Path | None:
    """Return asset folder path; optionally create layout (only when writing files)."""
    dest = _resolve_story_folder(slug, story_id, story_type, title)
    if dest is None:
        return None
    if ensure:
        return _ensure_story_folder(dest, story_id, title, story_type)
    return dest


def _copy_if_exists(src: Path, dest: Path) -> bool:
    if not src.is_file():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return True


def sync_script(
    story_id: int | str,
    title: str,
    full_story: str,
    story_meta: str = "",
    story_type: str | None = "general",
) -> Path | None:
    """Save generated script text."""
    slug = slugify(title or "", fallback=f"story-{story_id}")
    dest = story_folder(slug, story_id, title, story_type)
    if dest is None:
        return None

    if full_story.strip():
        (dest / "script" / "FULL_STORY.txt").write_text(full_story.strip() + "\n", encoding="utf-8")
    if story_meta.strip():
        (dest / "script" / "story_meta.txt").write_text(story_meta.strip() + "\n", encoding="utf-8")

    raw = dest / "script" / "raw-story.txt"
    if raw.is_file():
        print(f"[assets] raw-story present → {raw}")

    print(f"[assets] script → {dest / 'script'}")
    return dest


def sync_storyboard_outputs(
    story_dir: Path,
    slug: str,
    story_id: int | str,
    title: str = "",
    story_type: str | None = "general",
) -> Path | None:
    """Copy storyboard text artifacts from temp workspace to story-asset."""
    dest = story_folder(slug, story_id, title, story_type, ensure=False)
    if dest is None:
        return None

    copied = 0
    mapping = [
        (story_dir / "FULL_STORY.txt", dest / "script" / "FULL_STORY.txt"),
        (story_dir / "prompt.txt", dest / "prompts" / "prompt.txt"),
        (story_dir / f"output_config_{slug}.md", dest / "prompts" / f"output_config_{slug}.md"),
        (story_dir / "scene.txt", dest / "scenes" / "scene.txt"),
        (story_dir / f"output_story_breakdown_{slug}.md", dest / "scenes" / f"output_story_breakdown_{slug}.md"),
        (story_dir / "image-prompts-only.txt", dest / "image-prompts" / "image-prompts-only.txt"),
    ]
    for src, out in mapping:
        if _copy_if_exists(src, out):
            copied += 1

    if copied == 0:
        return None

    _ensure_story_folder(dest, story_id, title, story_type)

    raw_story = dest / "script" / "raw-story.txt"
    if raw_story.is_file():
        print(f"[assets] raw-story → {raw_story}")

    print(f"[assets] storyboard ({copied} file(s)) → {dest}")
    return dest


def sync_scene_breakdown_outputs(
    story_dir: Path,
    slug: str,
    story_id: int | str,
    title: str = "",
    story_type: str | None = "general",
) -> Path | None:
    """Copy scene breakdown artifacts to story assets."""
    dest = story_folder(slug, story_id, title, story_type, ensure=False)
    if dest is None:
        return None

    copied = 0
    mapping = [
        (story_dir / "FULL_STORY.txt", dest / "script" / "FULL_STORY.txt"),
        (
            story_dir / f"output_scene_breakdown_{slug}.md",
            dest / "scenes" / f"output_scene_breakdown_{slug}.md",
        ),
        (story_dir / "scene-breakdown.txt", dest / "scenes" / "scene-breakdown.txt"),
    ]
    for src, out in mapping:
        if _copy_if_exists(src, out):
            copied += 1

    if copied == 0:
        return None

    _ensure_story_folder(dest, story_id, title, story_type)
    print(f"[assets] scene breakdown ({copied} file(s)) → {dest}")
    return dest


def sync_audio(
    story_dir: Path,
    slug: str,
    story_id: int | str,
    title: str = "",
    story_type: str | None = "general",
) -> Path | None:
    """Copy eleven-labs MP3s to story-asset/audio/."""
    audio_src = story_dir / "eleven-labs"
    if not audio_src.is_dir():
        return None
    mp3s = sorted(audio_src.glob("*.mp3"))
    if not mp3s:
        return None

    dest = story_folder(slug, story_id, title, story_type, ensure=False)
    if dest is None:
        return None

    audio_dest = dest / "audio"
    audio_dest.mkdir(parents=True, exist_ok=True)

    count = 0
    for mp3 in mp3s:
        shutil.copy2(mp3, audio_dest / mp3.name)
        count += 1

    if count == 0:
        return None

    _ensure_story_folder(dest, story_id, title, story_type)
    print(f"[assets] audio ({count} MP3(s)) → {audio_dest}")
    return dest


def sync_audio_english(
    story_dir: Path,
    slug: str,
    story_id: int | str,
    title: str = "",
    story_type: str | None = "general",
) -> Path | None:
    """Copy eleven-labs-english MP3s to story-asset/audio/english/."""
    audio_src = story_dir / "eleven-labs-english"
    if not audio_src.is_dir():
        return None
    mp3s = sorted(audio_src.glob("*.mp3"))
    if not mp3s:
        return None

    dest = story_folder(slug, story_id, title, story_type, ensure=False)
    if dest is None:
        return None

    audio_dest = dest / "audio" / "english"
    audio_dest.mkdir(parents=True, exist_ok=True)

    count = 0
    for mp3 in mp3s:
        shutil.copy2(mp3, audio_dest / mp3.name)
        count += 1

    if count == 0:
        return None

    _ensure_story_folder(dest, story_id, title, story_type)
    print(f"[assets] english audio ({count} MP3(s)) → {audio_dest}")
    return dest


# Drupal POST body keys omitted when files already exist under STORY_ASSET_ROOT.
# Drupal syncAssetFilesToNodeFields() reads prompt/scene/image-prompts/audio from disk.
_ASSET_DISK_ONLY_KEYS = (
    "prompt_file_content",
    "scene_file_content",
    "image_prompts_file_content",
    "eleven_labs_files",
    "eleven_labs_files_english",
)


def seed_workspace_from_assets(
    story_dir: Path,
    slug: str,
    story_id: int | str,
    title: str = "",
    story_type: str | None = "general",
) -> list[str]:
    """
    Copy saved Stage A/B (and partial Stage C) from STORY_ASSET_ROOT into a temp workspace.

    Used with --resume so deepseek_pipeline skips completed stages and continues from Stage C.
    """
    dest = _resolve_story_folder(slug, story_id, story_type, title)
    if dest is None or not dest.is_dir():
        return []

    story_dir.mkdir(parents=True, exist_ok=True)
    restored: list[str] = []
    mapping = [
        (dest / "prompts" / f"output_config_{slug}.md", story_dir / f"output_config_{slug}.md"),
        (dest / "scenes" / f"output_story_breakdown_{slug}.md", story_dir / f"output_story_breakdown_{slug}.md"),
        (dest / "prompts" / "prompt.txt", story_dir / "prompt.txt"),
        (dest / "scenes" / "scene.txt", story_dir / "scene.txt"),
        (dest / "image-prompts" / "image-prompts-only.txt", story_dir / "image-prompts-only.txt"),
        (dest / "script" / "FULL_STORY.txt", story_dir / "FULL_STORY.txt"),
    ]
    for src, out in mapping:
        if _copy_if_exists(src, out):
            restored.append(out.name)

    if restored:
        print(f"[resume] restored from {dest}: {', '.join(restored)}")
    else:
        print(f"[resume] no saved artifacts found under {dest}")
    return restored


def finalize_drupal_payload(payload: dict, *, assets_on_disk: bool) -> dict:
    """
    Shrink the worker → Drupal update payload when outputs were synced to disk.

    Base64 MP3s alone can exceed PHP post_max_size (~17 MB for a typical story).
    """
    if not assets_on_disk or asset_root() is None:
        return payload

    slim = dict(payload)
    removed = [key for key in _ASSET_DISK_ONLY_KEYS if key in slim]
    for key in removed:
        del slim[key]

    if removed:
        print(f"[drupal] payload slimmed — Drupal will sync from disk: {', '.join(removed)}")
    return slim
