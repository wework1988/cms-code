#!/usr/bin/env python3
"""
Seed Pakistan Army scenes 1–2 from already-downloaded Flow 2K files (no new generation).

Uses the latest matching Downloads files observed from the user's Flow session.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIBS = ROOT / ".python-libs"
sys.path.insert(0, str(LIBS))
sys.path.insert(0, str(ROOT))

from helper.config import load_config
from helper.images import copy_validated_download
from helper.manifest import create_or_resume_job, load_manifest, summarize
from helper.prompts import filter_scene_range, parse_image_prompts_file
from helper.stories import resolve_story

DOWNLOADS = Path.home() / "Downloads"


def latest_match(pattern_substr: str) -> Path:
    candidates = sorted(
        DOWNLOADS.glob("*.jpg"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        name = path.name
        if "2K" in name and pattern_substr.lower() in name.lower():
            return path
    raise SystemExit(f"No 2K jpg in Downloads matching {pattern_substr!r}")


def main() -> None:
    config = load_config(ROOT / "config.json")
    roots = config["story_roots_resolved"]
    story = resolve_story("165-pakistan-army", roots)
    prompts = parse_image_prompts_file(story.prompt_file)
    selected = filter_scene_range(prompts, 1, 2)

    # Scene 1 / 2 downloads from the live Flow session (parliamentary chamber prompts).
    mapping = {
        1: latest_match("parliamentary_chamber"),
        2: latest_match("parliamentary_assembly"),
    }
    # If naming flipped, prefer newest chamber then assembly by mtime order among 2K parliament files.
    parliament = [
        p for p in sorted(DOWNLOADS.glob("*2K*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
        if "parliament" in p.name.lower()
    ]
    if len(parliament) >= 2:
        mapping = {1: parliament[0], 2: parliament[1]}

    results = []
    for scene, src in mapping.items():
        saved = copy_validated_download(
            src,
            story.images_dir,
            scene,
            roots,
            overwrite=False,
            min_width=int(config["min_landscape_width"]),
            aspect_tolerance=float(config["aspect_tolerance"]),
        )
        results.append(
            {
                "scene": scene,
                "source": str(src),
                "saved": str(saved.path),
                "width": saved.width,
                "height": saved.height,
                "format": saved.format,
            }
        )
        print(f"Scene {scene}: {src.name} → {saved.path} ({saved.width}x{saved.height})")

    job = create_or_resume_job(
        story_key=story.key,
        story_path=story.path,
        images_dir=story.images_dir,
        prompt_file=story.prompt_file,
        selected=selected,
        roots=roots,
        regenerate=False,
        settings={
            "model": config["model"],
            "aspect_ratio": config["aspect_ratio"],
            "outputs_per_prompt": config["outputs_per_prompt"],
            "download_variant": config["download_variant"],
        },
    )
    # Mark idle after seeding
    job.control = "idle"
    job.lock_owner = None
    from helper.manifest import save_manifest

    save_manifest(job, roots)
    summary = summarize(job)
    print(json.dumps({"results": results, "summary": summary, "job_id": job.job_id}, indent=2))

    # Resume simulation: next queued should be none for range 1-2
    job2 = create_or_resume_job(
        story_key=story.key,
        story_path=story.path,
        images_dir=story.images_dir,
        prompt_file=story.prompt_file,
        selected=selected,
        roots=roots,
        regenerate=False,
    )
    assert job2.scenes["1"]["status"] == "completed"
    assert job2.scenes["2"]["status"] == "completed"
    print("Resume check: scenes 1 and 2 skipped as completed.")


if __name__ == "__main__":
    main()
