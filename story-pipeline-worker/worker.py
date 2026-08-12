#!/usr/bin/env python3
"""
Poll Drupal for queued stories or run a specific story pipeline.

Queue detection: story_meta starts with QUEUE: or JSON with QUEUE key.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from dotenv import load_dotenv

from drupal_client import DrupalStoryClient
from run_generate_story import run_generate
from run_storyboard import run_storyboard
from workspace import strip_html


def detect_pipeline(story: dict) -> str | None:
    meta = story.get("story_meta") or ""
    if meta.startswith("QUEUE:generate-story"):
        return "generate"
    if meta.startswith("QUEUE:"):
        return "storyboard"
    try:
        data = json.loads(meta)
        q = data.get("QUEUE", "")
        if q == "generate-story":
            return "generate"
        if q == "run-storyboard":
            return "storyboard"
    except json.JSONDecodeError:
        pass
    return None


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Drupal story pipeline worker")
    parser.add_argument("--story-id", type=int, help="Process this story ID directly")
    parser.add_argument(
        "--pipeline",
        choices=["generate", "storyboard", "auto"],
        default="auto",
        help="Pipeline to run (auto = detect from story meta or full_story)",
    )
    parser.add_argument("--max-step", type=int, default=4)
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--interval", type=int, default=30, help="Poll seconds when looping")
    args = parser.parse_args()

    if args.story_id:
        _run_one(args.story_id, args.pipeline, args.max_step)
        return

    print("error: provide --story-id N (queue polling API not implemented yet)")
    sys.exit(1)


def _run_one(story_id: int, pipeline: str, max_step: int) -> None:
    client = DrupalStoryClient()
    story = client.get_story(story_id)

    if pipeline == "auto":
        detected = detect_pipeline(story)
        if detected:
            pipeline = detected
        elif story.get("full_story") and strip_html(story.get("full_story") or ""):
            pipeline = "storyboard"
        elif story.get("youtube_urls"):
            pipeline = "generate"
        else:
            sys.exit("error: cannot detect pipeline — use --pipeline generate|storyboard")

    if pipeline == "generate":
        run_generate(story_id)
    else:
        run_storyboard(story_id, max_step=max_step)


if __name__ == "__main__":
    main()
