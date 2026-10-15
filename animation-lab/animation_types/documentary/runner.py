"""Job runner shared by the documentary modules."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

from animation_core.contracts import CONTRACT_VERSION
from animation_core.jobs import contained_dir, load_progress, overall_status, write_progress

from .browser import render_compiled
from .common import NeedsAssets, NeedsReview, PlanError

MODULES = {
    "text_highlighting": "animation_types.text_highlighting",
    "photo_sequences": "animation_types.photo_sequences",
    "before_after": "animation_types.before_after",
    "document_highlighting": "animation_types.document_highlighting",
    "relationship_diagrams": "animation_types.relationship_diagrams",
    "data_animations": "animation_types.data_animations",
    "storyboard_reconstructions": "animation_types.storyboard_reconstructions",
}


def _module(animation_type: str):
    name = MODULES[animation_type]
    return SimpleNamespace(
        planner=importlib.import_module(f"{name}.planner"),
        compile=importlib.import_module(f"{name}.compile"),
    )


def _save(job_dir: Path, progress: dict, status: str, message: str, animation_type: str) -> None:
    progress["status"] = status
    progress["message"] = message
    progress["animation_type"] = animation_type
    progress["contract_version"] = CONTRACT_VERSION
    write_progress(job_dir, progress)


def run_job(snapshot_path: Path, *, retry_clip: str | None = None, replan: bool = False) -> int:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    animation_type = snapshot["animation_type"]
    module = _module(animation_type)
    job_dir = snapshot_path.parent
    progress = load_progress(job_dir)
    progress.setdefault("clips", [])
    progress["prompt_id"] = snapshot.get("prompt_id")
    _save(job_dir, progress, "analysing_script", "Reading the script", animation_type)
    selection_path = job_dir / "selection.json"
    if selection_path.is_file() and not replan:
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
    else:
        selection = module.planner.select_clips(snapshot)
        selection_path.write_text(json.dumps(selection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not selection.get("clips"):
        progress["clips"] = []
        _save(job_dir, progress, "no_suitable_animation", selection.get("explanation") or "No suitable animation", animation_type)
        return 0
    ordered = []
    for clip in selection["clips"]:
        ordered.append({
            "animation_type": animation_type,
            "id": clip["id"],
            "title": clip.get("title"),
            "status": "queued",
            "source_passage": clip.get("source_passage"),
            "offset_start": clip.get("offset_start"),
            "offset_end": clip.get("offset_end"),
            "reason": clip.get("reason"),
            "language": snapshot.get("language") or "hi",
            "duration_seconds": float(snapshot["duration_seconds"]),
            "prompt_id": snapshot.get("prompt_id"),
            "error": None,
        })
    progress["clips"] = ordered
    for clip, selected in zip(ordered, selection["clips"]):
        if retry_clip and clip["id"] != retry_clip:
            continue
        clip_dir = contained_dir(job_dir, clip["id"])
        clip_dir.mkdir(parents=True, exist_ok=True)
        try:
            _save(job_dir, progress, "planning_clips", f"Planning {clip['id']}", animation_type)
            semantic = module.planner.plan_clip(snapshot, selected) if not (clip_dir / "semantic-plan.json").is_file() or replan else json.loads((clip_dir / "semantic-plan.json").read_text(encoding="utf-8"))
            (clip_dir / "semantic-plan.json").write_text(json.dumps(semantic, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            compiled = module.compile.compile_plan(semantic, selected["source_passage"], duration_seconds=float(snapshot["duration_seconds"]))
            _save(job_dir, progress, "rendering", f"Rendering {clip['id']}", animation_type)
            verification = render_compiled(compiled, clip_dir)
            clip["status"] = "completed"
            clip["video"] = str(clip_dir / "sample.mp4")
            clip["poster"] = str(clip_dir / "frames" / "hold.jpg")
            clip["verification"] = verification
            clip["beats"] = [beat.get("action") for beat in compiled.get("beats", [])]
        except NeedsAssets as error:
            clip["status"] = "needs_assets"
            clip["error"] = str(error)
        except NeedsReview as error:
            clip["status"] = "needs_review"
            clip["error"] = str(error)
        except (PlanError, Exception) as error:  # noqa: BLE001
            clip["status"] = "failed"
            clip["error"] = str(error)
    status, message = overall_status(ordered)
    _save(job_dir, progress, status, message, animation_type)
    return 0 if status in {"completed", "completed_with_errors", "no_suitable_animation", "needs_assets", "needs_review"} else 1


def render_sample(animation_type: str, output_dir: Path) -> dict:
    module = _module(animation_type)
    semantic, passage = module.planner.sample_plan()
    compiled = module.compile.compile_plan(semantic, passage, duration_seconds=float(semantic["duration_seconds"]))
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "semantic-plan.json").write_text(json.dumps(semantic, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return render_compiled(compiled, output_dir)
