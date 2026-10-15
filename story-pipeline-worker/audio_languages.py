#!/usr/bin/env python3
"""Shared Hindi/English narration helpers for ElevenLabs jobs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from asset_store import sync_audio, sync_audio_english
from elevenlabs_runner import collect_mp3_payload, generate_eleven_labs
from secrets import require_elevenlabs


def normalize_audio_languages(languages: list[str]) -> list[str]:
    """Normalize hindi / english / both into a unique language list."""
    normalized: list[str] = []
    for lang in languages:
        key = str(lang).strip().lower()
        if key == "both":
            normalized.extend(["hindi", "english"])
        elif key in {"hindi", "english"} and key not in normalized:
            normalized.append(key)
    return normalized or ["hindi"]


def _bilingual_default(bundle: dict[str, Any]) -> list[str] | None:
    story = bundle.get("story") or {}
    english = (story.get("full_story_english") or "").strip()
    if not english:
        return None
    return ["hindi", "english"]


def parse_audio_languages(bundle: dict[str, Any]) -> list[str]:
    """Read requested narration languages from story_meta.last_job.audio_languages."""
    raw = (bundle.get("story") or {}).get("story_meta") or ""
    if not isinstance(raw, str) or not raw.strip().startswith("{"):
        return _bilingual_default(bundle) or ["hindi"]

    try:
        meta = json.loads(raw)
    except json.JSONDecodeError:
        return _bilingual_default(bundle) or ["hindi"]

    langs = meta.get("last_job", {}).get("audio_languages")
    if not isinstance(langs, list) or not langs:
        return _bilingual_default(bundle) or ["hindi"]

    normalized = normalize_audio_languages([str(lang) for lang in langs])
    if normalized == ["hindi"]:
        bilingual = _bilingual_default(bundle)
        if bilingual is not None:
            return bilingual
    return normalized


def _apply_voice_type_filename(audio_out: Path, voice_type: str) -> None:
    """Rename a single full_narration.mp3 to {voice_type}.mp3 for the audio/ folder."""
    slug = (voice_type or "").strip().lower().replace("_", "-").replace(" ", "-")
    if not slug or not audio_out.is_dir():
        return
    mp3s = sorted(p for p in audio_out.glob("*.mp3") if p.is_file())
    if len(mp3s) != 1:
        return
    target = audio_out / f"{slug}.mp3"
    if mp3s[0].resolve() == target.resolve():
        return
    if target.exists():
        target.unlink()
    mp3s[0].replace(target)
    print(f"[elevenlabs] renamed → {target.name}")


def generate_story_audio(
    repo: Path,
    story_dir: Path,
    bundle: dict[str, Any],
    keys: dict[str, str],
    payload: dict[str, Any],
    languages: list[str] | None = None,
) -> bool:
    """
    Generate Hindi and/or English MP3s based on last_job.audio_languages.

    Returns True when at least one language produced MP3s.
    """
    langs = languages or parse_audio_languages(bundle)
    settings = bundle.get("settings") or {}
    hindi_voice = (settings.get("voice_id") or "").strip() or None
    english_voice = (settings.get("english_voice_id") or "").strip() or None
    voice_type = (settings.get("voice_type") or "").strip()

    api_key = require_elevenlabs(keys)
    produced = False

    if "hindi" in langs:
        full_story = story_dir / "FULL_STORY.txt"
        if not full_story.is_file():
            print("[elevenlabs] skipped hindi — no FULL_STORY.txt")
        else:
            audio_out = story_dir / "eleven-labs"
            print(f"[elevenlabs] hindi MP3s → {audio_out}")
            if voice_type:
                print(f"[elevenlabs] voice_type: {voice_type}")
            if hindi_voice:
                print(f"[elevenlabs] hindi voice_id: {hindi_voice}")
            else:
                print(
                    "[elevenlabs] hindi voice_id: (default from config — "
                    "set Voice type on the Story, or voice ID on Story Type)"
                )
            generate_eleven_labs(
                repo,
                full_story,
                audio_out,
                api_key,
                voice_id=hindi_voice,
                language_code="hi",
            )
            _apply_voice_type_filename(audio_out, voice_type)
            mp3_payload = collect_mp3_payload(audio_out)
            if mp3_payload:
                payload["eleven_labs_files"] = mp3_payload
                print(f"[elevenlabs] hindi: {len(mp3_payload)} MP3(s)")
                produced = True
            else:
                print("[elevenlabs] warning — no hindi MP3 files produced")

    if "english" in langs:
        english_story = story_dir / "FULL_STORY_ENGLISH.txt"
        if not english_story.is_file():
            print("[elevenlabs] skipped english — no FULL_STORY_ENGLISH.txt")
        else:
            if not english_voice:
                print(
                    "[elevenlabs] error — english_voice_id missing. "
                    "Set ElevenLabs voice ID on the English Story Type term in Drupal."
                )
            else:
                audio_out = story_dir / "eleven-labs-english"
                print(f"[elevenlabs] english MP3s → {audio_out}")
                print(f"[elevenlabs] english voice_id: {english_voice}")
                generate_eleven_labs(
                    repo,
                    english_story,
                    audio_out,
                    api_key,
                    voice_id=english_voice,
                    language_code="en",
                )
                mp3_payload = collect_mp3_payload(audio_out)
                if mp3_payload:
                    payload["eleven_labs_files_english"] = mp3_payload
                    print(f"[elevenlabs] english: {len(mp3_payload)} MP3(s)")
                    produced = True
                else:
                    print("[elevenlabs] warning — no english MP3 files produced")

    return produced


def sync_generated_audio(
    story_dir: Path,
    slug: str,
    story_id: int | str,
    title: str,
    story_type: str,
    payload: dict[str, Any],
) -> bool:
    """Copy generated MP3s to STORY_ASSET_ROOT and return True if anything synced."""
    assets_on_disk = False
    if "eleven_labs_files" in payload:
        if sync_audio(story_dir, slug, story_id, title, story_type) is not None:
            assets_on_disk = True
    if "eleven_labs_files_english" in payload:
        if sync_audio_english(story_dir, slug, story_id, title, story_type) is not None:
            assets_on_disk = True
    return assets_on_disk
