#!/usr/bin/env python3
"""
Generate ElevenLabs narration for a Drupal story and upload MP3s.

Does NOT re-run the storyboard pipeline — only TTS from full_story.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

from asset_store import asset_root, finalize_drupal_payload
from audio_languages import generate_story_audio, parse_audio_languages, sync_generated_audio
from drupal_client import DrupalStoryClient
from secrets import apply_asset_root_from_bundle, load_all_env, resolve_keys
from workspace import prepare_storyboard_workspace


def automation_repo() -> Path:
    p = Path(os.environ.get("AUTOMATION_REPO", "")).expanduser()
    if not p.is_dir():
        sys.exit(f"error: AUTOMATION_REPO not found: {p}")
    return p.resolve()


def run_elevenlabs(
    story_id: int,
    keep_workspace: bool = False,
    audio: str | None = None,
) -> None:
    repo = automation_repo()
    load_all_env(repo)
    client = DrupalStoryClient()

    print(f"[drupal] GET story {story_id}")
    story = client.get_story(story_id)
    print(f"  title: {story.get('title')}")

    print(f"[drupal] GET bundle")
    bundle = client.get_bundle(story_id, pipeline="storyboard")
    apply_asset_root_from_bundle(bundle)
    keys = resolve_keys(bundle)
    if not (bundle.get("api_keys") or {}).get("elevenlabs_api_key"):
        print("[keys] using eleven_labs_api_key from automation repo .env")

    if audio:
        from audio_languages import normalize_audio_languages

        langs = normalize_audio_languages([audio])
    else:
        langs = parse_audio_languages(bundle)
    print(f"[elevenlabs] languages: {', '.join(langs)}")

    workspace_parent = Path(__file__).resolve().parent / ".workspace"
    workspace_parent.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f"elevenlabs-{story_id}-", dir=workspace_parent))

    try:
        root, slug = prepare_storyboard_workspace(bundle, tmp)
        story_dir = root / "stories" / slug
        if "hindi" in langs and not (story_dir / "FULL_STORY.txt").is_file():
            sys.exit("error: story has no full_story text in Drupal")
        if "english" in langs and not (story_dir / "FULL_STORY_ENGLISH.txt").is_file():
            sys.exit("error: story has no full_story_english text in Drupal")

        update_payload: dict = {}
        if not generate_story_audio(repo, story_dir, bundle, keys, update_payload, languages=langs):
            sys.exit("error: no MP3 files were produced")

        assets_on_disk = sync_generated_audio(
            story_dir,
            slug,
            story_id,
            story.get("title") or "",
            story.get("story_type") or "general",
            update_payload,
        )

        if assets_on_disk and asset_root() is not None:
            update_payload = finalize_drupal_payload(update_payload, assets_on_disk=True)
            print(f"[drupal] POST update story {story_id} (audio on disk)")
        else:
            print(f"[drupal] POST update story {story_id} (inline MP3 payload)")

        result = client.update_story(story_id, update_payload)
        print(f"  eleven_labs_file_urls: {len(result.get('eleven_labs_file_urls') or [])} file(s)")
        for url in result.get("eleven_labs_file_urls") or []:
            print(f"    {url}")
        print(f"  eleven_labs_file_urls_english: {len(result.get('eleven_labs_file_urls_english') or [])} file(s)")
        for url in result.get("eleven_labs_file_urls_english") or []:
            print(f"    {url}")
        print("done.")

    finally:
        if keep_workspace:
            print(f"[workspace] kept at {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ElevenLabs audio for a Drupal story")
    parser.add_argument("story_id", type=int, help="Drupal node ID (e.g. 1)")
    parser.add_argument("--keep-workspace", action="store_true")
    parser.add_argument(
        "--audio",
        choices=["hindi", "english", "both"],
        help="Override narration languages (default: read from last Drupal job, or both for bilingual stories)",
    )
    args = parser.parse_args()
    run_elevenlabs(args.story_id, keep_workspace=args.keep_workspace, audio=args.audio)


if __name__ == "__main__":
    main()
