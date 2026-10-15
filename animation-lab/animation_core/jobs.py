"""Progress files, clip directories, and status aggregation shared by animation types."""
from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path

CLIP_ID = re.compile(r"^clip_\d{2}$")

ACTIVE = {
    "queued",
    "analysing_script",
    "planning_clips",
    "resolving_geography",
    "validating_timeline",
    "rendering",
    "uploading_assets",
    "registering_assets",
}


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def write_progress(job_dir: Path, payload: dict) -> None:
    atomic_write_json(job_dir / "progress.json", payload)


def load_progress(job_dir: Path) -> dict:
    path = job_dir / "progress.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def contained_dir(job_dir: Path, clip_id: str) -> Path:
    if not isinstance(clip_id, str) or not CLIP_ID.fullmatch(clip_id):
        raise ValueError(f"Clip id must look like clip_01, got {clip_id!r}")
    root = job_dir.resolve()
    destination = (root / "clips" / clip_id).resolve()
    if destination.parent != (root / "clips").resolve():
        raise ValueError("Clip directory escaped the job folder")
    return destination


def overall_status(clip_states: list[dict]) -> tuple[str, str]:
    statuses = [clip.get("status") for clip in clip_states]
    if not statuses:
        return "no_suitable_animation", "No clips were selected."
    blocked = {
        "failed",
        "needs_geographic_data",
        "needs_location_clarification",
        "needs_assets",
        "needs_review",
    }
    bad = [status for status in statuses if status in blocked]
    completed = statuses.count("completed")
    if bad and completed:
        return "completed_with_errors", "Some clips failed"
    if bad and not completed:
        kinds = set(bad)
        if kinds <= {"needs_geographic_data", "needs_location_clarification"}:
            if "needs_location_clarification" in kinds:
                return "needs_location_clarification", "One or more places are ambiguous or missing"
            return "needs_geographic_data", "Installed geography does not cover the selected places"
        if kinds == {"needs_assets"}:
            return "needs_assets", "A clip is missing required images or documents"
        if kinds == {"needs_review"}:
            return "needs_review", "A clip needs a location or relationship checked before rendering"
        return "failed", "All clips failed"
    if completed == len(statuses):
        return "completed", "Animation clips are ready"
    return "failed", "Animation job did not finish every clip"
