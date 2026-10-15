"""Scene-breakdown map jobs. Separate from the full-story selector and from video generation."""
from __future__ import annotations

import json
from pathlib import Path

from map_story.scene_run import run_saved_scene_job
from map_story.scene_select import SELECT_SYSTEM


def run_scene_breakdown_job(snapshot_path: Path, *, retry_clip: str | None = None) -> int:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    job_dir = snapshot_path.parent
    return run_saved_scene_job(
        snapshot,
        job_dir,
        complete=_complete_from_snapshot(snapshot),
        render_scene=lambda clip, clip_dir: _render_scene(snapshot, job_dir, clip, clip_dir),
        retry_clip=retry_clip,
    )


def _complete_from_snapshot(snapshot: dict):
    from map_story.planner import call_api, load_key

    key = load_key(Path(snapshot.get("env_file") or Path(__file__).resolve().parent / ".env"))
    model = snapshot.get("model") or "deepseek-flash"
    timeout = int(snapshot.get("timeout") or 180)

    def complete(payload: dict) -> dict:
        response = call_api(key, {
            "model": model,
            "messages": [
                {"role": "system", "content": SELECT_SYSTEM},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "max_tokens": 4000,
            "temperature": 0,
        }, timeout)
        message = ((response.get("choices") or [{}])[0].get("message") or {})
        content = message.get("content") or ""
        return json.loads(content)

    return complete


def _render_scene(snapshot: dict, job_dir: Path, clip: dict, clip_dir: Path) -> dict:
    from map_story.catalog import planner_summaries, resolve_catalog_places
    from map_story.compile import atomic_write_json, compile_resolved_plan
    from map_story.identity import DeepSeekIdentityClient, IdentityResolver, fallback_from_snapshot
    from map_story.overrides import AliasStore
    from run_map_animations import plan_clip, public_resolution, render_clip, requests_from_clip

    requests = requests_from_clip(clip)
    overrides = []
    override_path = job_dir / "location-overrides.json"
    if override_path.is_file():
        loaded = json.loads(override_path.read_text(encoding="utf-8"))
        overrides = loaded.get("overrides") or []
    identity_client = None
    if fallback_from_snapshot(snapshot):
        from map_story.planner import load_key
        identity_client = DeepSeekIdentityClient(
            load_key(Path(snapshot.get("env_file") or Path(__file__).resolve().parent / ".env")),
            snapshot.get("model") or "deepseek-flash",
        )
    resolver = IdentityResolver(
        enabled=fallback_from_snapshot(snapshot),
        client=identity_client,
        model=snapshot.get("model") or "deepseek-flash",
        max_calls=int(snapshot.get("identity_fallback_max_calls") or 24),
        overrides=[item for item in overrides if item.get("clip_id") in {None, clip["id"]}],
        alias_store=AliasStore(),
    )
    results = resolver.resolve(requests, passage=clip.get("source_passage") or "")
    blockers = [item for item in results if item.get("status") != "resolved"]
    places_public = [public_resolution(item) for item in results]
    if blockers:
        kind = "needs_location_clarification" if any(item.get("status") == "ambiguous" for item in blockers) else "needs_geographic_data"
        return {
            "status": kind,
            "error": blockers[0].get("reason"),
            "places": places_public,
            "warnings": [],
        }
    summaries = planner_summaries(results)
    atomic_write_json(clip_dir / "place-summaries.json", summaries)
    plan = plan_clip(snapshot, clip, summaries)
    atomic_write_json(clip_dir / "semantic-plan.json", plan)
    resolved_places = resolve_catalog_places(plan)
    settings = snapshot.get("renderer_settings") or {}
    resolved = compile_resolved_plan(
        plan,
        resolved_places,
        engine_hint=snapshot.get("renderer") or "maplibre",
        job_settings=snapshot,
        width=int(settings.get("width") or 1920),
        height=int(settings.get("height") or 1080),
        fps=int(settings.get("fps") or 30),
    )
    resolved_path = clip_dir / "resolved-plan.json"
    atomic_write_json(resolved_path, resolved)
    if snapshot.get("render") is False:
        return {
            "status": "planned",
            "places": places_public,
            "resolved_plan": str(resolved_path),
            "warnings": [],
        }
    engine = snapshot.get("renderer") or "maplibre"
    render_clip(resolved_path, engine, clip_dir, job_dir / "cache" / clip["id"])
    return {
        "status": "completed",
        "video": str(clip_dir / f"{engine}.mp4"),
        "places": places_public,
        "resolved_plan": str(resolved_path),
        "warnings": [],
    }
