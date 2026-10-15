"""Run a saved-scene map job: select, plan each scene, publish scene_<n>.mp4."""
from __future__ import annotations

import json
from pathlib import Path

from map_story.scene_publish import ensure_manifest, publish_scene_mp4, update_manifest_scene
from map_story.scene_select import SceneSelectionIncomplete, select_suitable_scenes
from map_story.scene_source import SceneSourceError, load_scene_breakdown
from map_story.scene_timing import resolve_scene_timing


def run_saved_scene_job(
    snapshot: dict,
    job_dir: Path,
    *,
    complete,
    render_scene,
    retry_clip: str | None = None,
) -> int:
    """Select the first suitable scenes, then render only those. Failures stay on those scenes."""
    job_dir.mkdir(parents=True, exist_ok=True)
    source = snapshot.get("scene_source") if isinstance(snapshot.get("scene_source"), dict) else {}
    text = source.get("text") or snapshot.get("scene_text") or ""
    try:
        document = load_scene_breakdown(text, source_path=source.get("path"))
    except SceneSourceError as error:
        _write_progress(job_dir, snapshot, "failed", str(error), [])
        return 1
    if document.source_hash != (source.get("sha256") or document.source_hash) and source.get("sha256"):
        _write_progress(job_dir, snapshot, "failed", "Scene snapshot hash does not match the saved scene text.", [])
        return 1

    limit = int(snapshot.get("max_selected_scenes") or snapshot.get("max_clips") or 10)
    story_root = Path(snapshot["story_root"]) if snapshot.get("story_root") else None
    configured = float(snapshot.get("duration_seconds") or 14)
    job_created = int(snapshot.get("created_unix") or 0)
    header = {
        "story_id": snapshot.get("nid"),
        "input_mode": "scene_breakdown",
        "source_scene_file_hash": document.source_hash,
        "parser_version": document.parser_version,
        "selection_limit": limit,
        "selection_policy": "first_suitable_in_story_order",
        "active_job_id": snapshot.get("job_id"),
        "prompt_revision": snapshot.get("prompt_revision") or snapshot.get("prompt_id"),
        "prompt_hash": snapshot.get("prompt_hash"),
    }
    if story_root is not None:
        ensure_manifest(story_root, header)

    progress_path = job_dir / "progress.json"
    previous = _read_json(progress_path)
    clips = {item.get("id"): item for item in previous.get("clips") or [] if item.get("id")}
    _write_progress(job_dir, snapshot, "scanning", "Scanning saved scenes.", list(clips.values()))

    def wrapped_complete(payload: dict) -> dict:
        return complete(payload)

    try:
        selection = select_suitable_scenes(
            document,
            wrapped_complete,
            limit=limit,
            batch_scenes=int(snapshot.get("scene_batch_scenes") or 12),
            batch_chars=int(snapshot.get("scene_batch_chars") or 12000),
            state_path=job_dir / "scene-scan.json",
        )
    except SceneSelectionIncomplete as error:
        _write_progress(job_dir, snapshot, "selection_incomplete", str(error), list(clips.values()))
        return 1

    _write_progress(job_dir, snapshot, "selected", selection.progress_message, list(clips.values()))
    if story_root is not None:
        ensure_manifest(story_root, {**header, "scan_progress": selection.progress_message, "scanned": selection.scanned, "scene_total": selection.total})

    for index, decision in enumerate(selection.selected, start=1):
        clip_id = f"clip_{index:02d}"
        if retry_clip and clip_id != retry_clip:
            continue
        existing = clips.get(clip_id) or {}
        if not retry_clip and existing.get("status") == "completed" and existing.get("video") and Path(str(existing["video"])).is_file():
            continue
        timing = resolve_scene_timing(story_root, decision.scene_number, configured)
        clip = {
            "id": clip_id,
            "animation_type": "map",
            "title": f"Scene {decision.scene_number}",
            "scene_number": decision.scene_number,
            "scene_id": decision.scene_id,
            "scene_text_hash": next(scene.text_hash for scene in document.scenes if scene.scene_id == decision.scene_id),
            "source_passage": decision.passage or next(scene.text for scene in document.scenes if scene.scene_id == decision.scene_id),
            "reason": decision.reason,
            "purpose": decision.purpose,
            "place_requests": decision.places,
            "target_focus_count": 3,
            "narration_unit_count": 1,
            "counting_method": "sentences",
            "focus_decision": "scene_breakdown",
            "duration_seconds": timing["map_duration_seconds"],
            "timing": timing,
            "language": snapshot.get("language") or "hi",
        }
        record = {
            "id": clip_id,
            "scene_number": decision.scene_number,
            "scene_id": decision.scene_id,
            "scene_text_hash": clip["scene_text_hash"],
            "title": clip["title"],
            "source_passage": clip["source_passage"],
            "reason": decision.reason,
            "status": "planning",
            "timing": timing,
            "animation_type": "map",
            "filename": f"scene_{decision.scene_number}.mp4",
        }
        clips[clip_id] = record
        _write_progress(job_dir, snapshot, "planning", selection.progress_message, list(clips.values()))
        clip_dir = job_dir / "clips" / clip_id
        clip_dir.mkdir(parents=True, exist_ok=True)
        try:
            outcome = render_scene(clip, clip_dir)
        except Exception as error:  # noqa: BLE001 — one scene must not discard the others
            outcome = {"status": "failed", "error": str(error)}
        record.update({key: value for key, value in outcome.items() if key != "video"})
        status = outcome.get("status") or "failed"
        record["status"] = status
        if status == "completed" and outcome.get("video") and story_root is not None:
            published = publish_scene_mp4(
                story_root,
                scene_number=decision.scene_number,
                rendered=Path(outcome["video"]),
                entry={
                    "scene_id": decision.scene_id,
                    "scene_text_hash": clip["scene_text_hash"],
                    "source_passage": clip["source_passage"],
                    "selection_reason": decision.reason,
                    "animation_type": "map",
                    "job_id": snapshot.get("job_id"),
                    "clip_id": clip_id,
                    "duration": timing["map_duration_seconds"],
                    "timing": timing,
                    "theme_id": (snapshot.get("map_theme") or {}).get("id") if isinstance(snapshot.get("map_theme"), dict) else snapshot.get("style"),
                    "theme_hash": (snapshot.get("map_theme") or {}).get("theme_hash") if isinstance(snapshot.get("map_theme"), dict) else None,
                    "prompt_revision": snapshot.get("prompt_revision") or snapshot.get("prompt_id"),
                    "prompt_hash": snapshot.get("prompt_hash"),
                    "resolved_plan": outcome.get("resolved_plan"),
                    "warnings": outcome.get("warnings") or [],
                    "error": None,
                },
                job_created=job_created,
            )
            record["video"] = str(published)
            record["status"] = "completed"
        elif story_root is not None:
            update_manifest_scene(story_root, {
                "scene_number": decision.scene_number,
                "scene_id": decision.scene_id,
                "scene_text_hash": clip["scene_text_hash"],
                "source_passage": clip["source_passage"],
                "selection_reason": decision.reason,
                "status": status,
                "job_id": snapshot.get("job_id"),
                "clip_id": clip_id,
                "job_created": job_created,
                "error": outcome.get("error"),
                "timing": timing,
            })
        clips[clip_id] = record
        _write_progress(job_dir, snapshot, "rendering", selection.progress_message, list(clips.values()))

    final = list(clips.values())
    failed = [item for item in final if item.get("status") in {"failed", "needs_geographic_data", "needs_location_clarification"}]
    if not selection.selected:
        message = selection.progress_message + " No suitable map scenes."
        _write_progress(job_dir, snapshot, "no_suitable_animation", message, final)
        return 0
    if failed and any(item.get("status") == "completed" for item in final):
        _write_progress(job_dir, snapshot, "completed_with_errors", selection.progress_message, final)
        return 0
    if failed:
        _write_progress(job_dir, snapshot, "completed_with_errors", selection.progress_message, final)
        return 0
    _write_progress(job_dir, snapshot, "completed", selection.progress_message, final)
    return 0


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write_progress(job_dir: Path, snapshot: dict, status: str, message: str, clips: list[dict]) -> None:
    payload = {
        "status": status,
        "message": message,
        "job_id": snapshot.get("job_id"),
        "input_mode": "scene_breakdown",
        "script_source": "scenes/scene.txt",
        "script_hash": (snapshot.get("scene_source") or {}).get("sha256"),
        "clips": clips,
    }
    path = job_dir / "progress.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
