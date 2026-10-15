#!/usr/bin/env python3
"""Background map-animation job. Reads an immutable snapshot; does not re-read the CMS story."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "animation-lab"
sys.path.insert(0, str(LAB))

CLIP_ID = __import__("re").compile(r"^clip_\d{2}$")


def write_progress_file(job_dir: Path, payload: dict) -> None:
    """Write progress without importing geographic libraries."""
    job_dir.mkdir(parents=True, exist_ok=True)
    path = job_dir / "progress.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def snapshot_dir_from_argv(argv: list[str]) -> Path | None:
    if "--snapshot" not in argv:
        return None
    index = argv.index("--snapshot")
    if index + 1 >= len(argv):
        return None
    return Path(argv[index + 1]).expanduser().resolve().parent


def mark_startup_failure(message: str) -> None:
    job_dir = snapshot_dir_from_argv(sys.argv)
    if job_dir is not None:
        previous = {}
        progress_path = job_dir / "progress.json"
        if progress_path.is_file():
            try:
                previous = json.loads(progress_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                previous = {}
        previous.update({"status": "failed", "message": message})
        previous.setdefault("clips", [])
        write_progress_file(job_dir, previous)
    print(f"Error: {message}", file=sys.stderr)


try:
    from map_story.compile import atomic_write_json, compile_resolved_plan  # noqa: E402
    from map_story.geo import GeoResolveError, load_registry, resolve_plan_places  # noqa: E402
    from map_story.planner import generate_semantic_plan, load_key  # noqa: E402
    from map_story.scenes import parse_scene_text, scene_numbers_for_passage, scene_video_name  # noqa: E402
    from map_story.schema import PlanValidationError, style_from_snapshot, validate_semantic_plan  # noqa: E402
    from map_story.selection import (  # noqa: E402
        SelectionError,
        MAX_CLIPS,
        clip_planning_payload,
        finalize_selection,
        first_clips,
        narrow_results,
        plan_from_selection,
        select_story,
        selection_prompt,
        validate_selection_document,
    )
except Exception as startup_error:  # noqa: BLE001 — record import failures before planning
    mark_startup_failure(f"Animation runtime failed to start: {startup_error}")
    raise SystemExit(1) from None

ACTIVE = {
    "queued",
    "analysing_script",
    "planning_clips",
    "resolving_geography",
    "rendering",
    "uploading_assets",
}


def write_progress(job_dir: Path, payload: dict) -> None:
    write_progress_file(job_dir, payload)


def contained_dir(job_dir: Path, clip_id: str) -> Path:
    if not isinstance(clip_id, str) or not CLIP_ID.fullmatch(clip_id):
        raise ValueError(f"Clip id must look like clip_01, got {clip_id!r}")
    root = job_dir.resolve()
    destination = (root / "clips" / clip_id).resolve()
    if destination.parent != (root / "clips").resolve():
        raise ValueError("Clip directory escaped the job folder")
    return destination


def overall_status(clip_states: list[dict]) -> tuple[str, str]:
    """Final job status from every clip, including clips not retried this attempt."""
    statuses = [clip.get("status") for clip in clip_states]
    failed = statuses.count("failed")
    needs_geo = statuses.count("needs_geographic_data") + statuses.count("needs_location_clarification")
    completed = statuses.count("completed")
    if not statuses:
        return "no_suitable_animation", "No clips were selected."
    if failed and (completed or needs_geo):
        return "completed_with_errors", "Some clips failed"
    if failed:
        return "failed", "All clips failed"
    if needs_geo and completed:
        return "completed_with_errors", "Some clips need geographic data or a clearer place"
    if needs_geo and "needs_location_clarification" in statuses:
        return "needs_location_clarification", "One or more places are ambiguous or missing"
    if needs_geo:
        return "needs_geographic_data", "Installed geography does not cover the selected places"
    return "completed", "Animation clips are ready"


def job_providers(snapshot: dict) -> tuple[str, str]:
    local = snapshot.get("planner") == "local"
    if snapshot.get("selection"):
        selection = "saved_selection"
    else:
        selection = "local" if local else "deepseek"
    focus = "local" if local else "deepseek"
    return selection, focus


def write_job_record(job_dir: Path, snapshot: dict, clips: dict) -> Path:
    selection_provider, focus_provider = job_providers(snapshot)
    prompt = snapshot.get("master_prompt") or ""
    record = {
        "job_id": snapshot.get("job_id"),
        "script_source": snapshot.get("script_source"),
        "script_field": snapshot.get("script_field"),
        "script_path": snapshot.get("script_path"),
        "script_hash": snapshot.get("script_hash"),
        "prompt_source": snapshot.get("prompt_source"),
        "prompt_id": snapshot.get("prompt_id"),
        "prompt_path": snapshot.get("prompt_path"),
        "prompt_hash": snapshot.get("prompt_hash"),
        "selection_provider": selection_provider,
        "focus_planning_provider": focus_provider,
        "style": snapshot.get("style"),
        "planner": snapshot.get("planner"),
        "passages": [
            {
                "id": clip.get("id"),
                "title": clip.get("title"),
                "source_passage": clip.get("source_passage"),
                "narration_unit_count": clip.get("narration_unit_count"),
                "target_focus_count": clip.get("target_focus_count"),
                "focus_count": clip.get("focus_count"),
                "status": clip.get("status"),
                "video": clip.get("video"),
                "error": clip.get("error"),
            }
            for clip in clips.values()
        ],
        "errors": [
            {"id": clip.get("id"), "status": clip.get("status"), "error": clip.get("error")}
            for clip in clips.values()
            if clip.get("error")
        ],
    }
    if record["prompt_hash"] is None and prompt:
        import hashlib
        record["prompt_hash"] = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    path = job_dir / "job-record.json"
    atomic_write_json(path, record)
    return path


def load_progress(job_dir: Path) -> dict:
    path = job_dir / "progress.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def node_bin() -> str:
    from map_story.runtime import resolve_node_executable
    return resolve_node_executable()


def lab_python() -> str:
    candidate = LAB / ".venv" / "bin" / "python"
    return str(candidate if candidate.is_file() else Path(sys.executable))


def render_clip(resolved: Path, engine: str, out_dir: Path, cache_dir: Path) -> None:
    from map_story.render_slot import renderer_slot
    lock = LAB.parent / "story-pipeline-worker" / ".map-renderer.lock"
    with renderer_slot(lock):
        _render_clip_unlocked(resolved, engine, out_dir, cache_dir)


def _render_clip_unlocked(resolved: Path, engine: str, out_dir: Path, cache_dir: Path) -> None:
    cmd = [
        node_bin(),
        str(LAB / "map-story" / "render.mjs"),
        "--plan",
        str(resolved),
        "--engine",
        engine,
        "--output-dir",
        str(out_dir),
        "--cache-dir",
        str(cache_dir),
    ]
    env = os.environ.copy()
    env.pop("PLAYWRIGHT_CHROME_CDP", None)
    node_dir = str(Path(cmd[0]).parent)
    env["PATH"] = node_dir + os.pathsep + (env.get("PATH") or "/usr/bin:/bin")
    proc = subprocess.run(cmd, cwd=str(LAB / "map-story"), env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"Renderer exited {proc.returncode}")
    video = out_dir / f"{engine}.mp4"
    if not video.is_file() or video.stat().st_size < 1000:
        raise RuntimeError("Renderer did not leave a verified MP4")


def public_resolution(result: dict) -> dict:
    place = result.get("place") or {}
    candidates = []
    for candidate in result.get("candidates") or []:
        candidates.append({
            "name": candidate.get("name"),
            "level": candidate.get("level"),
            "state_name": candidate.get("state_name"),
            "district_name": candidate.get("district_name"),
            "representation": candidate.get("representation"),
            "feature_type": candidate.get("feature_type"),
        })
    return {
        "requested": (result.get("requested") or {}).get("name") or (result.get("query") or {}).get("name"),
        "status": result.get("status"),
        "reason": result.get("reason"),
        "name": place.get("name"),
        "level": place.get("level"),
        "representation": place.get("representation"),
        "feature_type": place.get("feature_type"),
        "state_name": place.get("state_name"),
        "district_name": place.get("district_name"),
        "candidates": candidates[:5],
    }


def align_selection_offsets(doc: dict, script: str) -> None:
    """Trust an exact quotation and compute offsets locally. Do not repair a paraphrase."""
    for clip in doc.get("clips") or []:
        if not isinstance(clip, dict):
            continue
        passage = clip.get("source_passage")
        if isinstance(passage, str) and passage in script:
            start = script.find(passage)
            clip["offset_start"] = start
            clip["offset_end"] = start + len(passage)


def requests_from_clip(clip: dict) -> list[dict]:
    raw = clip.get("place_requests")
    if not isinstance(raw, list) or not raw:
        raw = []
        for place in clip.get("places") or []:
            if not isinstance(place, dict) or not place.get("name"):
                continue
            parent = place.get("parent_name")
            if parent is None and isinstance(place.get("parent"), str) and " " in place["parent"]:
                parent = place["parent"]
            raw.append({
                "name": place.get("name"),
                "level": place.get("level"),
                "parent_name": parent,
                "country": place.get("country"),
                "state": place.get("state"),
                "district": place.get("district"),
            })
    cleaned = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        cleaned.append({
            "name": item.get("name"),
            "level": item.get("level"),
            "parent_name": item.get("parent_name"),
            "country": item.get("country"),
            "state": item.get("state"),
            "district": item.get("district"),
        })
    return cleaned


def select_clips(snapshot: dict) -> dict:
    script = snapshot["script"]
    limit = min(int(snapshot.get("max_clips") or MAX_CLIPS), MAX_CLIPS)
    scenes = parse_scene_text(snapshot.get("scene_text") or "")
    if snapshot.get("planner") != "local":
        prompt = (snapshot.get("master_prompt") or "").strip()
        if not prompt:
            raise SelectionError(
                "This job has no master prompt. Refusing to substitute a generic prompt."
            )
    if snapshot.get("planner") == "local":
        return first_clips(select_story(
            script,
            max_clips=limit,
            language=snapshot.get("language") or "hi",
            scenes=scenes,
        ), script, max_clips=limit)
    key = load_key(Path(snapshot.get("env_file") or ROOT / "story-pipeline-worker" / ".env"))
    from map_story.planner import call_api
    messages = [
        {"role": "system", "content": selection_prompt(
            snapshot["master_prompt"],
            [],
            limit,
            snapshot.get("language") or "hi",
            float(snapshot["duration_seconds"]),
        )},
        {"role": "user", "content": json.dumps({"script": script}, ensure_ascii=False)},
    ]
    content = ""
    for attempt in range(2):
        response = call_api(key, {
            "model": snapshot.get("model") or os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"),
            "messages": messages,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "max_tokens": 4000,
            "temperature": 0.2,
        }, int(snapshot.get("timeout") or 180))
        choice = (response.get("choices") or [{}])[0]
        content = ((choice.get("message") or {}).get("content") or "").strip()
        if not content:
            raise SelectionError(
                f"Selection response was empty (finish_reason={choice.get('finish_reason')})"
            )
        try:
            doc = json.loads(content)
            align_selection_offsets(doc, script)
            doc = finalize_selection(doc, script, scenes)
            return first_clips(validate_selection_document(doc, script, max_clips=limit), script, max_clips=limit)
        except (json.JSONDecodeError, SelectionError, TypeError, ValueError) as error:
            if attempt:
                raise SelectionError(f"Selection failed validation after repair: {error}") from None
            messages += [
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": (
                        "Return corrected JSON only. The source_passage must be an exact contiguous copy of the script. "
                        "Include place_requests and a reason. Leave beat suggestions as proposed. "
                        f"Validation error: {error}"
                    ),
                },
            ]
    raise SelectionError("Selection failed")


def plan_clip(snapshot: dict, selection: dict, summaries: list[dict] | None = None) -> dict:
    """DeepSeek proposes stages. Local code checks the count, colors, and camera later."""
    style = style_from_snapshot(snapshot)
    language = snapshot.get("language") or "hi"
    if snapshot.get("planner") == "local":
        plan = plan_from_selection(selection, language=language, style=style, summaries=summaries)
        plan["focus_planning_provider"] = "local"
        return plan
    if not summaries:
        raise PlanValidationError(
            "No resolved places were available for focus planning. A local sequence was not substituted."
        )
    prompt = (snapshot.get("master_prompt") or "").strip()
    if not prompt:
        raise PlanValidationError(
            "This job has no master prompt. Refusing to plan focuses with a generic prompt."
        )
    from map_story.sequence import accept_focus_plan
    from map_story.themes import resolve_theme
    key = load_key(Path(snapshot.get("env_file") or ROOT / "story-pipeline-worker" / ".env"))
    payload = clip_planning_payload(
        prompt,
        selection,
        summaries,
        language,
        float(selection["duration_seconds"]),
    )
    allowed = {card["id"] for card in summaries}
    plan = generate_semantic_plan(
        json.dumps(payload, ensure_ascii=False),
        key,
        model=snapshot.get("model") or os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"),
        duration_seconds=float(selection["duration_seconds"]),
        language=language,
        style=style,
        timeout=int(snapshot.get("timeout") or 180),
        allowed_place_ids=allowed,
        enforce_beats=True,
        expected_focus_count=int(selection["target_focus_count"]),
    )
    accepted = accept_focus_plan(plan, selection, style, resolve_theme(style, snapshot), summaries)
    accepted["focus_planning_provider"] = "deepseek"
    generation = accepted.get("generation") if isinstance(accepted.get("generation"), dict) else {}
    generation["provider"] = "deepseek"
    accepted["generation"] = generation
    return accepted


def run_job(snapshot_path: Path, *, retry_clip: str | None = None, reresolve: bool = False) -> int:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if snapshot.get("input_mode") == "scene_breakdown":
        from scene_map_job import run_scene_breakdown_job
        return run_scene_breakdown_job(snapshot_path, retry_clip=retry_clip)
    job_dir = snapshot_path.parent
    progress = load_progress(job_dir)
    clips = {c["id"]: c for c in progress.get("clips") or []}
    engine = snapshot.get("renderer") or "maplibre"
    if engine not in ("maplibre", "openlayers"):
        raise RuntimeError("Unsupported renderer")
    selection_provider, focus_provider = job_providers(snapshot)
    style = snapshot.get("style")

    def save(status: str, message: str = "") -> None:
        progress["status"] = status
        progress["message"] = message
        progress["job_id"] = snapshot["job_id"]
        progress["script_source"] = snapshot.get("script_source")
        progress["script_hash"] = snapshot["script_hash"]
        progress["prompt_source"] = snapshot.get("prompt_source")
        progress["prompt_id"] = snapshot.get("prompt_id")
        progress["prompt_hash"] = snapshot.get("prompt_hash")
        progress["selection_provider"] = selection_provider
        progress["focus_planning_provider"] = focus_provider
        progress["style"] = style
        progress["clips"] = list(clips.values())
        write_progress(job_dir, progress)

    print(
        f"Script source: {snapshot.get('script_source') or 'unspecified'} "
        f"hash={snapshot.get('script_hash')}",
        flush=True,
    )
    print(
        f"Prompt source: {snapshot.get('prompt_source') or 'snapshot'} "
        f"revision={snapshot.get('prompt_id')} hash={snapshot.get('prompt_hash')}",
        flush=True,
    )
    print(
        f"Style: {style}  selection={selection_provider}  focus={focus_provider}",
        flush=True,
    )

    if retry_clip:
        save("planning_clips", f"Retrying {retry_clip}")
    else:
        save("analysing_script", "Reading the script snapshot")
        try:
            if snapshot.get("selection"):
                selected = snapshot["selection"]
                if not isinstance(selected, dict):
                    raise SelectionError("Saved selection must be an object.")
                align_selection_offsets(selected, snapshot["script"])
                scenes = parse_scene_text(snapshot.get("scene_text") or "")
                selected = finalize_selection(selected, snapshot["script"], scenes)
                limit = min(int(snapshot.get("max_clips") or MAX_CLIPS), MAX_CLIPS)
                selected = first_clips(
                    validate_selection_document(selected, snapshot["script"], max_clips=limit),
                    snapshot["script"],
                    max_clips=limit,
                )
            else:
                selected = select_clips(snapshot)
        except (SelectionError, RuntimeError, OSError) as error:
            save("failed", str(error))
            clips["selection"] = {
                "id": "selection",
                "status": "failed",
                "error": str(error),
            }
            record_path = write_job_record(job_dir, snapshot, clips)
            print(f"Job record: {record_path}", flush=True)
            print(f"Error: {error}", file=sys.stderr)
            return 1
        atomic_write_json(job_dir / "selection.json", selected)
        if not selected.get("clips"):
            save("no_suitable_animation", selected.get("explanation") or "No suitable map passage.")
            write_job_record(job_dir, snapshot, clips)
            print(f"Job record: {job_dir / 'job-record.json'}", flush=True)
            return 0
        for clip in selected["clips"]:
            if clip["id"] not in clips or clips[clip["id"]].get("status") != "completed":
                clips[clip["id"]] = {
                    "id": clip["id"],
                    "title": clip.get("title"),
                    "status": "planned",
                    "source_passage": clip.get("source_passage"),
                    "reason": clip.get("reason"),
                    "beats": clip.get("beats"),
                    "narration_unit_count": clip.get("narration_unit_count"),
                    "target_focus_count": clip.get("target_focus_count"),
                    "counting_method": clip.get("counting_method"),
                    "video": None,
                    "error": None,
                }

    save("planning_clips", "Planning clips")
    from map_story.catalog import catalog_status, planner_summaries, resolve_catalog_places, resolve_requests
    catalogue = catalog_status()
    progress["catalogue"] = {
        "built_at": catalogue.get("built_at"),
        "counts": catalogue.get("counts"),
        "datasets": [
            {
                "namespace": item.get("namespace"),
                "version": item.get("version"),
                "checksum": item.get("checksum"),
                "boundary_year": item.get("boundary_year"),
            }
            for item in catalogue.get("datasets") or []
        ],
    }
    selection_doc = json.loads((job_dir / "selection.json").read_text(encoding="utf-8"))
    needs_geo = 0
    failed = 0
    for clip in selection_doc["clips"]:
        cid = clip["id"]
        if retry_clip and cid != retry_clip:
            continue
        current = clips.get(cid) or {"id": cid}
        if current.get("status") == "completed" and current.get("video") and Path(current["video"]).is_file():
            continue
        clip_dir = contained_dir(job_dir, cid)
        clip_dir.mkdir(parents=True, exist_ok=True)
        resolved_path = clip_dir / "resolved-plan.json"
        try:
            if resolved_path.is_file() and not reresolve and retry_clip:
                save("rendering", cid)
                render_clip(resolved_path, engine, clip_dir, job_dir / "cache" / cid)
            else:
                summaries = None
                requests = requests_from_clip(clip)
                if clip.get("review_status"):
                    current.update({
                        "status": clip["review_status"],
                        "error": clip.get("review_reason"),
                        "title": clip.get("title"),
                        "source_passage": clip.get("source_passage"),
                        "reason": clip.get("reason"),
                        "narration_unit_count": clip.get("narration_unit_count"),
                        "target_focus_count": clip.get("target_focus_count"),
                        "counting_method": clip.get("counting_method"),
                    })
                    clips[cid] = current
                    needs_geo += 1
                    save("resolving_geography", clip.get("review_reason") or clip["review_status"])
                    continue
                if requests:
                    save("resolving_geography", cid)
                    results = narrow_results(
                        resolve_requests(requests),
                        clip.get("source_passage") or "",
                    )
                    current["places"] = [public_resolution(item) for item in results]
                    blockers = [item for item in results if item.get("status") != "resolved"]
                    if blockers:
                        kind = "needs_location_clarification" if any(item.get("status") == "ambiguous" for item in blockers) else "needs_geographic_data"
                        current.update({
                            "status": kind,
                            "error": blockers[0].get("reason"),
                            "title": clip.get("title"),
                            "source_passage": clip.get("source_passage"),
                            "reason": clip.get("reason"),
                        })
                        clips[cid] = current
                        needs_geo += 1
                        save("resolving_geography", blockers[0].get("reason") or kind)
                        continue
                    summaries = planner_summaries(results)
                    atomic_write_json(clip_dir / "place-summaries.json", summaries)
                plan = plan_clip(snapshot, clip, summaries)
                atomic_write_json(clip_dir / "semantic-plan.json", plan)
                current["focus_count"] = plan.get("target_focus_count")
                current["focus_planning_provider"] = plan.get("focus_planning_provider")
                current["semantic_plan"] = str(clip_dir / "semantic-plan.json")
                save("resolving_geography", cid)
                places = resolve_catalog_places(plan)
                renderer_settings = snapshot.get("renderer_settings") or {}
                resolved = compile_resolved_plan(
                    plan,
                    places,
                    engine_hint=engine,
                    job_settings=snapshot,
                    width=int(renderer_settings.get("width") or 1920),
                    height=int(renderer_settings.get("height") or 1080),
                    fps=int(renderer_settings.get("fps") or 30),
                )
                atomic_write_json(resolved_path, resolved)
                current["resolved_plan"] = str(resolved_path)
                if snapshot.get("render") is False:
                    current.update({
                        "status": "planned",
                        "error": None,
                        "title": clip.get("title"),
                        "source_passage": clip.get("source_passage"),
                        "narration_unit_count": clip.get("narration_unit_count"),
                        "target_focus_count": clip.get("target_focus_count"),
                    })
                    clips[cid] = current
                    save("planning_clips", cid)
                    continue
                save("rendering", cid)
                render_clip(resolved_path, engine, clip_dir, job_dir / "cache" / cid)
            engine_video = clip_dir / f"{engine}.mp4"
            scene_numbers = scene_numbers_for_passage(
                clip.get("source_passage") or "",
                parse_scene_text(snapshot.get("scene_text") or ""),
            )
            label = scene_video_name(scene_numbers)
            video = engine_video
            if label:
                named = (job_dir.resolve() / f"{label}.mp4").resolve()
                if named.parent != job_dir.resolve():
                    raise RuntimeError("Scene video path escaped the job folder")
                named.write_bytes(engine_video.read_bytes())
                video = named
            current.update({
                "status": "completed",
                "error": None,
                "title": clip.get("title"),
                "source_passage": clip.get("source_passage"),
                "reason": clip.get("reason"),
                "beats": clip.get("beats"),
                "narration_unit_count": clip.get("narration_unit_count"),
                "target_focus_count": clip.get("target_focus_count"),
                "counting_method": clip.get("counting_method"),
                "scene_numbers": scene_numbers,
                "filename": video.name,
                "video": str(video),
                "poster": str(clip_dir / "qa" / f"{engine}-callout.png"),
            })
            clips[cid] = current
            save("uploading_assets", cid)
        except (PlanValidationError, SelectionError, RuntimeError, OSError, ValueError) as error:
            current.update({"status": "failed", "error": str(error), "title": clip.get("title")})
            clips[cid] = current
            failed += 1
            save("rendering", str(error))
            traceback.print_exc()

    status, message = overall_status(list(clips.values()))
    if status == "completed" and snapshot.get("render") is False:
        status, message = "planned", "Plans are ready. Rendering was not requested."
    save(status, message)
    record_path = write_job_record(job_dir, snapshot, clips)
    print(f"Job record: {record_path}", flush=True)
    for clip in clips.values():
        detail = clip.get("error") or clip.get("video") or ""
        print(f"  {clip.get('id')}: {clip.get('status')} {detail}", flush=True)
    return 0 if status in {
        "completed", "planned", "no_suitable_animation", "needs_geographic_data",
        "needs_location_clarification", "completed_with_errors",
    } else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--retry-clip", default=None)
    parser.add_argument("--reresolve", action="store_true")
    parser.add_argument("--replan", action="store_true")
    parser.add_argument("--regenerate-presentation", action="store_true")
    parser.add_argument("--resume-locations", action="store_true")
    parser.add_argument("--restyle-variant", action="store_true")
    args = parser.parse_args()
    try:
        code = run_job(args.snapshot, retry_clip=args.retry_clip, reresolve=args.reresolve)
    except Exception as error:  # noqa: BLE001 — last-resort job failure
        job_dir = args.snapshot.parent
        write_progress(job_dir, {"status": "failed", "message": str(error), "clips": []})
        print(f"Error: {error}", file=sys.stderr)
        code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()
