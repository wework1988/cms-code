from __future__ import annotations

import json
from pathlib import Path

import pytest

from helper.manifest import create_or_resume_job, load_manifest, next_queued_scene, summarize
from helper.prompts import ScenePrompt, prompt_hash


def _prompt(scene: int, text: str) -> ScenePrompt:
    return ScenePrompt(scene=scene, text=text, prompt_hash=prompt_hash(text))


def test_resume_skips_completed(tmp_path: Path):
    roots = [tmp_path]
    story = tmp_path / "general" / "1-demo"
    images = story / "images"
    images.mkdir(parents=True)
    prompt_file = story / "image-prompts" / "image-prompts-only.txt"
    prompt_file.parent.mkdir(parents=True)
    p1 = _prompt(1, "Scene 1. one")
    p2 = _prompt(2, "Scene 2. two")
    (images / "001.jpg").write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)
    prompt_file.write_text("Scene 1. one||\nScene 2. two||\n", encoding="utf-8")

    job = create_or_resume_job(
        story_key="general/1-demo",
        story_path=story,
        images_dir=images,
        prompt_file=prompt_file,
        selected=[p1, p2],
        roots=roots,
    )
    assert job.scenes["1"]["status"] == "completed"
    assert job.scenes["2"]["status"] == "queued"
    assert next_queued_scene(job).scene == 2
    counts = summarize(job)
    assert counts["completed"] == 1
    assert counts["queued"] == 1


def test_prompt_hash_change_queues_again(tmp_path: Path):
    roots = [tmp_path]
    story = tmp_path / "general" / "1-demo"
    images = story / "images"
    images.mkdir(parents=True)
    prompt_file = story / "image-prompts" / "image-prompts-only.txt"
    prompt_file.parent.mkdir(parents=True)
    prompt_file.write_text("x", encoding="utf-8")
    (images / "001.jpg").write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)

    old = _prompt(1, "Scene 1. old")
    job = create_or_resume_job(
        story_key="k",
        story_path=story,
        images_dir=images,
        prompt_file=prompt_file,
        selected=[old],
        roots=roots,
    )
    assert job.scenes["1"]["status"] == "completed"

    new = _prompt(1, "Scene 1. new text")
    job2 = create_or_resume_job(
        story_key="k",
        story_path=story,
        images_dir=images,
        prompt_file=prompt_file,
        selected=[new],
        roots=roots,
    )
    assert job2.scenes["1"]["status"] == "queued"
    assert job2.scenes["1"]["error_category"] == "prompt_changed"


def test_duplicate_running_job_rejected(tmp_path: Path):
    roots = [tmp_path]
    story = tmp_path / "s"
    images = story / "images"
    images.mkdir(parents=True)
    prompt_file = story / "p.txt"
    prompt_file.write_text("x", encoding="utf-8")
    p1 = _prompt(1, "Scene 1. a")
    job = create_or_resume_job(
        story_key="k",
        story_path=story,
        images_dir=images,
        prompt_file=prompt_file,
        selected=[p1],
        roots=roots,
    )
    job.control = "running"
    job.lock_owner = "extension"
    job.active_scene = 1
    from helper.manifest import save_manifest

    save_manifest(job, roots)
    with pytest.raises(RuntimeError, match="already running"):
        create_or_resume_job(
            story_key="k",
            story_path=story,
            images_dir=images,
            prompt_file=prompt_file,
            selected=[p1],
            roots=roots,
        )


def test_manifest_persists(tmp_path: Path):
    roots = [tmp_path]
    story = tmp_path / "s"
    images = story / "images"
    images.mkdir(parents=True)
    prompt_file = story / "p.txt"
    prompt_file.write_text("x", encoding="utf-8")
    job = create_or_resume_job(
        story_key="k",
        story_path=story,
        images_dir=images,
        prompt_file=prompt_file,
        selected=[_prompt(3, "Scene 3. c")],
        roots=roots,
    )
    loaded = load_manifest(images, roots)
    assert loaded is not None
    assert loaded.job_id == job.job_id
    assert "3" in loaded.scenes
    raw = json.loads((images / "generation-manifest.json").read_text(encoding="utf-8"))
    assert raw["scenes"]["3"]["status"] == "queued"
