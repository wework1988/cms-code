#!/usr/bin/env python3
"""
Generate scene breakdown from a story using updated-scene-breakdown.md.

Separate from the main storyboard pipeline (no Stage A, B, or C).
Calls DeepSeek once with the story + prompt and writes scene-breakdown.txt.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

from asset_store import sync_scene_breakdown_outputs
from drupal_client import DrupalStoryClient
from scene_breakdown_export import export_scene_breakdown_file
from scene_breakdown_llm import call_deepseek_scene_breakdown, write_breakdown
from secrets import apply_asset_root_from_bundle, leased_deepseek_key, load_all_env, resolve_keys
from workspace import (
    default_scene_breakdown_prompt_path,
    load_scene_breakdown_prompt,
    prepare_scene_breakdown_story,
)


def _safe_int(value: object, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def run_scene_breakdown(
    story_id: int,
    *,
    keep_workspace: bool = False,
    force: bool = False,
    export_only: bool = False,
    breakdown_path: Path | None = None,
) -> None:
    automation_repo = Path(os.environ.get("AUTOMATION_REPO", "")).expanduser()
    if automation_repo.is_dir():
        load_all_env(automation_repo)
    else:
        load_all_env(None)

    client = DrupalStoryClient()

    print(f"[drupal] GET story {story_id}")
    story = client.get_story(story_id)
    title = story.get("title") or ""
    story_type = story.get("story_type") or "general"
    print(f"  title: {title}")
    print(f"  type:  {story_type}")

    print(f"[drupal] GET bundle (settings + keys)")
    bundle = client.get_bundle(story_id, pipeline="storyboard")
    apply_asset_root_from_bundle(bundle)

    keys = resolve_keys(bundle)
    if not (bundle.get("api_keys") or {}).get("deepseek_api_key"):
        print("[keys] using DEEPSEEK_API_KEY/DEEPSEEK_API_KEYS from .env (Drupal Crime key not set)")

    prompt_path = default_scene_breakdown_prompt_path()
    print(f"[scene-breakdown] prompt: {prompt_path}")

    workspace_parent = Path(__file__).resolve().parent / ".workspace"
    workspace_parent.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f"scene-breakdown-{story_id}-", dir=workspace_parent))

    try:
        root, slug, full_story = prepare_scene_breakdown_story(bundle, tmp)
        story_dir = root / "stories" / slug
        breakdown_file = story_dir / f"output_scene_breakdown_{slug}.md"
        scene_file = story_dir / "scene-breakdown.txt"

        print(f"[workspace] {root}")
        print(f"[workspace] slug={slug}")
        print(f"[story] {len(full_story)} chars")

        if export_only:
            src = breakdown_path or breakdown_file
            if not src.is_file():
                sys.exit(
                    f"error: --export-only needs an existing breakdown at {src}. "
                    "Run without --export-only first, or pass --breakdown PATH."
                )
            if breakdown_path and breakdown_path.is_file():
                shutil.copy2(breakdown_path, breakdown_file)
            scene_count = export_scene_breakdown_file(breakdown_file, scene_file)
            print(f"[scene-breakdown] exported {scene_count} scene(s) → {scene_file}")
        else:
            if breakdown_file.is_file() and not force:
                print(f"[scene-breakdown] using cached breakdown: {breakdown_file.name} (pass --force to redo)")
            else:
                prompt_template = load_scene_breakdown_prompt()
                settings = bundle.get("settings") or {}
                model = settings.get("model", "deepseek-v4-pro")
                configured = _safe_int(settings.get("max_tokens_b"), 131072)
                max_tokens = _safe_int(
                    os.environ.get("DEEPSEEK_MAX_TOKENS_BREAKDOWN")
                    or os.environ.get("DEEPSEEK_MAX_TOKENS_VALIDATE"),
                    configured,
                )
                max_tokens = max(131072, max_tokens)

                print(f"[llm] calling DeepSeek ({model}, max_tokens={max_tokens})...")
                with leased_deepseek_key(keys) as deepseek_key:
                    raw = call_deepseek_scene_breakdown(
                        deepseek_key,
                        prompt_template,
                        full_story,
                        model=model,
                        max_tokens=max_tokens,
                    )
                write_breakdown(breakdown_file, raw)
                print(f"[scene-breakdown] wrote breakdown → {breakdown_file}")

            scene_count = export_scene_breakdown_file(breakdown_file, scene_file)
            print(f"[scene-breakdown] exported {scene_count} scene(s) → {scene_file}")

        asset_dest = sync_scene_breakdown_outputs(story_dir, slug, story_id, title, story_type)
        if asset_dest is not None:
            print(f"[assets] scene breakdown → {asset_dest / 'scenes'}")
        else:
            print("[assets] STORY_ASSET_ROOT not set — outputs kept in workspace only")

        print("done.")

    finally:
        if keep_workspace:
            print(f"[workspace] kept at {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate scene breakdown from story (updated-scene-breakdown.md)"
    )
    parser.add_argument("story_id", type=int, help="Drupal node ID (e.g. 98)")
    parser.add_argument("--keep-workspace", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run DeepSeek even if a cached breakdown exists in the workspace",
    )
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="Convert an existing breakdown to scene-breakdown.txt without calling DeepSeek",
    )
    parser.add_argument(
        "--breakdown",
        type=Path,
        default=None,
        help="Breakdown markdown path (with --export-only)",
    )
    args = parser.parse_args()
    run_scene_breakdown(
        args.story_id,
        keep_workspace=args.keep_workspace,
        force=args.force,
        export_only=args.export_only,
        breakdown_path=args.breakdown,
    )


if __name__ == "__main__":
    main()
