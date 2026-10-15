"""Timeline job runner. Does not import the geographic catalogue or Shapely."""
from __future__ import annotations

import argparse
import json
import os
import traceback
from pathlib import Path

from animation_core.contracts import CONTRACT_VERSION
from animation_core.jobs import contained_dir, load_progress, overall_status, write_progress
from animation_core.outputs import replace_verified, verify_mp4
from animation_core.planning import load_key

from .compile import compile_plan
from .planner import plan_from_passage, plan_with_model, select_local, select_with_model
from .renderer import render_compiled
from .schema import TimelineValidationError, validate_semantic_plan

ROOT = Path(__file__).resolve().parents[3]


def _save(job_dir: Path, progress: dict, status: str, message: str = "") -> None:
    progress["status"] = status
    progress["message"] = message
    progress["contract_version"] = CONTRACT_VERSION
    progress["animation_type"] = "timeline"
    write_progress(job_dir, progress)


def _clip_record(clip: dict, snapshot: dict) -> dict:
    return {
        "animation_type": "timeline",
        "id": clip["id"],
        "clip_id": clip["id"],
        "title": clip.get("title"),
        "status": "queued",
        "source_passage": clip.get("source_passage"),
        "offset_start": clip.get("offset_start"),
        "offset_end": clip.get("offset_end"),
        "reason": clip.get("reason"),
        "beats": clip.get("beats") or [],
        "language": snapshot.get("language") or "hi",
        "duration_seconds": float(snapshot["duration_seconds"]),
        "prompt_id": snapshot.get("prompt_id"),
        "model": snapshot.get("model") or os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"),
        "milestones": [],
        "error": None,
        "video": None,
        "poster": None,
        "representative_frames": [],
    }


def _select(snapshot: dict, client=None) -> dict:
    script = snapshot["script"]
    limit = min(int(snapshot.get("max_clips") or 3), 3)
    duration = float(snapshot["duration_seconds"])
    language = snapshot.get("language") or "hi"
    if snapshot.get("planner") == "local":
        return select_local(script, max_clips=limit, duration_seconds=duration, language=language)
    key = load_key(Path(snapshot.get("env_file") or ROOT / "story-pipeline-worker" / ".env"))
    return select_with_model(
        script,
        master_prompt=snapshot.get("master_prompt") or "",
        max_clips=limit,
        duration_seconds=duration,
        language=language,
        key=key,
        model=snapshot.get("model") or os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"),
        timeout=int(snapshot.get("timeout") or 180),
        client=client,
    )


def _plan_one(snapshot: dict, clip: dict, client=None) -> dict:
    duration = float(snapshot["duration_seconds"])
    language = snapshot.get("language") or "hi"
    if snapshot.get("planner") == "local":
        plan = plan_from_passage(
            clip["source_passage"],
            language=language,
            duration_seconds=duration,
            title=clip.get("title"),
        )
    else:
        key = load_key(Path(snapshot.get("env_file") or ROOT / "story-pipeline-worker" / ".env"))
        plan = plan_with_model(
            clip["source_passage"],
            title=clip.get("title") or "समयरेखा",
            reason=clip.get("reason") or "",
            beats=clip.get("beats") or [],
            master_prompt=snapshot.get("master_prompt") or "",
            language=language,
            duration_seconds=duration,
            key=key,
            model=snapshot.get("model") or os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"),
            timeout=int(snapshot.get("timeout") or 180),
            client=client,
        )
    plan["generation"] = {
        "provider": snapshot.get("planner") or "deepseek",
        "model": snapshot.get("model") or os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"),
        "prompt_id": snapshot.get("prompt_id"),
    }
    return plan


def _render_clip(job_dir: Path, clip_id: str, compiled: dict) -> dict:
    clip_dir = contained_dir(job_dir, clip_id)
    destination = clip_dir / "timeline.mp4"
    rendered = render_compiled(
        compiled,
        destination,
        clip_dir / "frames",
        clip_dir / "contact-sheet.png",
    )
    verification = replace_verified(
        rendered["partial"],
        destination,
        lambda partial: verify_mp4(
            partial,
            width=compiled["width"],
            height=compiled["height"],
            fps=compiled["fps"],
            duration=compiled["duration_seconds"],
        ),
    )
    poster = clip_dir / "poster.png"
    overview = clip_dir / "frames" / "overview.png"
    if overview.is_file():
        poster.write_bytes(overview.read_bytes())
    (clip_dir / "verification.json").write_text(
        json.dumps(verification, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "video": str(destination),
        "poster": str(poster),
        "representative_frames": rendered["stills"],
        "verification": verification,
        "contact_sheet": str(clip_dir / "contact-sheet.png"),
    }


def run_job(
    snapshot_path: Path,
    *,
    retry_clip: str | None = None,
    replan: bool = False,
    client=None,
    stop_before_render: bool = False,
) -> int:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if snapshot.get("animation_type") not in (None, "", "timeline"):
        raise TimelineValidationError("This runner only accepts timeline jobs")
    job_dir = snapshot_path.parent
    progress = load_progress(job_dir)
    progress.setdefault("clips", [])
    progress["prompt_id"] = snapshot.get("prompt_id")
    progress["job_id"] = snapshot.get("job_id")
    by_id = {clip["id"]: clip for clip in progress["clips"] if isinstance(clip, dict) and clip.get("id")}

    _save(job_dir, progress, "analysing_script", "Reading the script")
    selection_path = job_dir / "selection.json"
    if selection_path.is_file() and (retry_clip or not replan):
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
    else:
        selection = _select(snapshot, client=client)
        selection_path.write_text(json.dumps(selection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not selection.get("clips"):
        progress["clips"] = []
        _save(job_dir, progress, "no_suitable_animation", selection.get("explanation") or "No suitable timeline")
        return 0

    ordered = []
    for clip in selection["clips"]:
        current = by_id.get(clip["id"], _clip_record(clip, snapshot))
        current.update({
            "title": clip.get("title"),
            "reason": clip.get("reason"),
            "source_passage": clip.get("source_passage"),
            "offset_start": clip.get("offset_start"),
            "offset_end": clip.get("offset_end"),
            "beats": clip.get("beats") or [],
        })
        ordered.append(current)
    progress["clips"] = ordered

    for clip in ordered:
        clip_id = clip["id"]
        if retry_clip and clip_id != retry_clip:
            continue
        video = Path(clip["video"]) if clip.get("video") else None
        if clip.get("status") == "completed" and video and video.is_file() and not replan:
            continue
        clip_dir = contained_dir(job_dir, clip_id)
        clip_dir.mkdir(parents=True, exist_ok=True)
        semantic_path = clip_dir / "semantic-plan.json"
        compiled_path = clip_dir / "compiled-plan.json"
        try:
            if semantic_path.is_file() and not replan:
                semantic = json.loads(semantic_path.read_text(encoding="utf-8"))
                semantic = validate_semantic_plan(
                    semantic,
                    clip["source_passage"],
                    duration_seconds=float(snapshot["duration_seconds"]),
                )
            else:
                _save(job_dir, progress, "planning_clips", f"Planning {clip_id}")
                semantic = _plan_one(snapshot, clip, client=client)
                semantic_path.write_text(json.dumps(semantic, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            _save(job_dir, progress, "validating_timeline", f"Checking {clip_id}")
            compiled = compile_plan(
                semantic,
                clip["source_passage"],
                duration_seconds=float(snapshot["duration_seconds"]),
            )
            compiled_path.write_text(json.dumps(compiled, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            clip["semantic_plan"] = "clips/" + clip_id + "/semantic-plan.json"
            clip["compiled_plan"] = "clips/" + clip_id + "/compiled-plan.json"
            clip["milestones"] = [
                {
                    "date_label": event["date_label"],
                    "caption": event["caption"],
                    "year": event["year"],
                    "date_precision": event["date_precision"],
                }
                for event in compiled["events"]
            ]
            if stop_before_render:
                clip["status"] = "validated"
                continue
            _save(job_dir, progress, "rendering", f"Rendering {clip_id}")
            produced = _render_clip(job_dir, clip_id, compiled)
            clip.update(produced)
            clip["status"] = "completed"
            clip["error"] = None
            _save(job_dir, progress, "registering_assets", f"Saved {clip_id}")
        except Exception as error:  # noqa: BLE001 — one clip must not discard the others
            clip["status"] = "failed"
            clip["error"] = str(error)
            _save(job_dir, progress, "rendering", str(error))

    if stop_before_render:
        _save(job_dir, progress, "validating_timeline", "Plans are ready")
        return 0
    status, message = overall_status(ordered)
    _save(job_dir, progress, status, message)
    return 0 if status in ("completed", "completed_with_errors", "no_suitable_animation") else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a timeline animation job from its snapshot")
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--retry-clip")
    parser.add_argument("--replan", action="store_true")
    args = parser.parse_args(argv)
    try:
        return run_job(args.snapshot, retry_clip=args.retry_clip, replan=args.replan)
    except Exception as error:  # noqa: BLE001
        job_dir = args.snapshot.expanduser().resolve().parent
        progress = load_progress(job_dir)
        progress["status"] = "failed"
        progress["message"] = str(error)
        progress.setdefault("clips", [])
        write_progress(job_dir, progress)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
