#!/usr/bin/env python3
"""
Full pipeline for one Drupal story: optional script generation, then storyboard + ElevenLabs.

1. If no full_story but YouTube URLs exist → generate script
2. Storyboard (Stages A–C) + image prompts
3. ElevenLabs narration MP3s
"""

from __future__ import annotations

import argparse
import sys

from drupal_client import DrupalStoryClient
from run_generate_story import run_generate
from run_storyboard import automation_repo, run_storyboard
from secrets import load_all_env
from workspace import strip_html


def run_full_pipeline(story_id: int, skip_elevenlabs: bool = False) -> None:
    load_all_env(automation_repo())
    client = DrupalStoryClient()

    print(f"[full-pipeline] story {story_id}")
    story = client.get_story(story_id)
    print(f"  title: {story.get('title')}")

    script = strip_html(story.get("full_story") or "")
    urls = story.get("youtube_urls") or []

    if not script:
        if not urls:
            sys.exit("error: story needs full_story text or YouTube URLs")
        print("[full-pipeline] step 1/2 — generate script from YouTube")
        run_generate(story_id)
        story = client.get_story(story_id)
        script = strip_html(story.get("full_story") or "")
        if not script:
            sys.exit("error: generate-story did not produce full_story")

    print("[full-pipeline] step 2/2 — storyboard" + (" + ElevenLabs" if not skip_elevenlabs else ""))
    run_storyboard(story_id, max_step=4, keep_workspace=False, elevenlabs=not skip_elevenlabs)
    print("[full-pipeline] done.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Full pipeline for a Drupal story node")
    parser.add_argument("story_id", type=int)
    parser.add_argument("--no-elevenlabs", action="store_true", help="Storyboard only, skip audio")
    args = parser.parse_args()
    run_full_pipeline(args.story_id, skip_elevenlabs=args.no_elevenlabs)


if __name__ == "__main__":
    main()
