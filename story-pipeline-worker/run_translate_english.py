#!/usr/bin/env python3
"""
Translate Hindi scene.txt to English scene.txt via DeepSeek, then merge into full_story_english.

Flow:
  Hindi scene.txt → English scene.txt → FULL_STORY_ENGLISH (merged lines)
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from drupal_client import DrupalStoryClient
from run_generate_story import log
from scene_english import (
    build_english_scene_txt,
    load_hindi_scene_text,
    merge_english_scenes_to_full_story,
    parse_hindi_scene_txt,
    save_english_scene_assets,
    translate_scenes_to_english,
)
from secrets import apply_asset_root_from_bundle, leased_deepseek_key, load_all_env, resolve_keys
from workspace import strip_html


def resolve_restore_status(story: dict) -> str:
    meta_raw = story.get("story_meta") or ""
    try:
        meta = json.loads(meta_raw) if meta_raw else {}
    except json.JSONDecodeError:
        meta = {}
    previous = (meta.get("last_job") or {}).get("previous_status")
    if isinstance(previous, str) and previous.strip() and previous != "storyboard_running":
        return previous.strip()

    status = (story.get("status") or "").strip()
    if status in {"storyboard_done", "live", "story_generated"}:
        return status
    return "story_generated"


def run_translate_english(story_id: int, *, force: bool = False) -> None:
    load_all_env()
    client = DrupalStoryClient()

    log("[progress] stage=boot")
    log(f"[drupal] GET story {story_id}")
    story = client.get_story(story_id)
    title = story.get("title") or ""
    log(f"  title: {title}")

    existing_english = strip_html(story.get("full_story_english") or "").strip()
    if existing_english and not force:
        log(f"[translate] English already present ({len(existing_english)} chars). Use --force to overwrite.")
        sys.exit(0)

    log("[drupal] GET bundle")
    bundle = client.get_bundle(story_id, pipeline="storyboard")
    apply_asset_root_from_bundle(bundle)
    keys = resolve_keys(bundle)
    settings = bundle.get("settings") or {}
    model = settings.get("model", "deepseek-v4-pro")

    log("[progress] stage=load_scenes")
    hindi_scene_raw = load_hindi_scene_text(story, bundle)
    scenes = parse_hindi_scene_txt(hindi_scene_raw)
    if not scenes:
        sys.exit("error: Hindi scene.txt parsed zero scenes")

    log(f"[translate] parsed {len(scenes)} Hindi scene(s)")
    batch_size = int(os.environ.get("TRANSLATE_SCENE_BATCH", "20"))
    request_timeout_s = int(os.environ.get("DEEPSEEK_REQUEST_TIMEOUT_SECONDS", "180"))
    retries = int(os.environ.get("DEEPSEEK_REQUEST_RETRIES", "4"))

    log(f"[progress] stage=translate_scenes batches={(len(scenes) + batch_size - 1) // batch_size}")
    log(f"[translate] model={model} batch_size={batch_size}")

    with leased_deepseek_key(keys) as api_key:
        english_lines = translate_scenes_to_english(
            scenes,
            api_key=api_key,
            model=model,
            batch_size=batch_size,
            request_timeout_s=request_timeout_s,
            retries=retries,
        )

    scene_english_txt = build_english_scene_txt(scenes, english_lines)
    english_full = merge_english_scenes_to_full_story(english_lines)
    if not english_full:
        sys.exit("error: merged English full story is empty")

    restore_status = resolve_restore_status(story)
    payload = {
        "full_story_english": english_full,
        "scene_file_english_content": scene_english_txt,
        "status": restore_status,
    }

    save_english_scene_assets(
        story_id,
        title,
        story.get("story_type"),
        scene_english_txt,
        english_full,
    )

    log(f"[progress] stage=save scenes={len(scenes)} english_chars={len(english_full)}")
    log(f"[drupal] POST update story {story_id}")
    result = client.update_story(story_id, payload)
    result_len = len(strip_html(result.get("full_story_english") or ""))
    log(f"  full_story_english length: {result_len} chars")
    log(f"  scene-english.txt scenes: {len(scenes)}")
    log(f"  status restored: {result.get('status')}")
    log("done.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Translate Hindi scene.txt to English scene.txt and merge full_story_english"
    )
    parser.add_argument("story_id", type=int, help="Drupal node ID (e.g. 96)")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing English script if present",
    )
    args = parser.parse_args()
    run_translate_english(args.story_id, force=args.force)


if __name__ == "__main__":
    main()
