"""Durable per-story generation manifest under images/generation-manifest.json."""

from __future__ import annotations

import json
import threading
import uuid
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .prompts import ScenePrompt, scene_filename_stem
from .security import resolve_under_roots

MANIFEST_NAME = "generation-manifest.json"
LOCKS: dict[str, threading.RLock] = {}
LOCKS_GUARD = threading.Lock()

STATUSES = (
    "queued",
    "configuring",
    "submitting",
    "generating",
    "upscaling",
    "downloading",
    "saving",
    "completed",
    "failed",
    "needs_review",
    "paused",
    "stopped",
)

DEFAULT_SETTINGS = {
    "model": "Nano Banana 2.1",
    "aspect_ratio": "16:9",
    "outputs_per_prompt": 1,
    "download_variant": "2K Upscaled",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _lock_for(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with LOCKS_GUARD:
        if key not in LOCKS:
            LOCKS[key] = threading.RLock()
        return LOCKS[key]


@dataclass
class SceneState:
    scene: int
    prompt_hash: str
    status: str = "queued"
    attempt_count: int = 0
    flow_project_url: str | None = None
    flow_result_id: str | None = None
    download_id: str | None = None
    download_path: str | None = None
    saved_path: str | None = None
    image_format: str | None = None
    width: int | None = None
    height: int | None = None
    started_at: str | None = None
    completed_at: str | None = None
    error_category: str | None = None
    error_message: str | None = None
    model: str = DEFAULT_SETTINGS["model"]
    aspect_ratio: str = DEFAULT_SETTINGS["aspect_ratio"]
    download_variant: str = DEFAULT_SETTINGS["download_variant"]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SceneState":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class JobManifest:
    job_id: str
    story_key: str
    story_path: str
    images_dir: str
    prompt_file: str
    settings: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_SETTINGS))
    control: str = "idle"  # idle|running|paused|stopped
    scene_from: int | None = None
    scene_to: int | None = None
    scenes: dict[str, dict[str, Any]] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    active_scene: int | None = None
    lock_owner: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobManifest":
        return cls(
            job_id=data["job_id"],
            story_key=data["story_key"],
            story_path=data["story_path"],
            images_dir=data["images_dir"],
            prompt_file=data["prompt_file"],
            settings=data.get("settings") or dict(DEFAULT_SETTINGS),
            control=data.get("control", "idle"),
            scene_from=data.get("scene_from"),
            scene_to=data.get("scene_to"),
            scenes=data.get("scenes") or {},
            created_at=data.get("created_at") or _utc_now(),
            updated_at=data.get("updated_at") or _utc_now(),
            active_scene=data.get("active_scene"),
            lock_owner=data.get("lock_owner"),
        )


def manifest_path(images_dir: Path) -> Path:
    return images_dir / MANIFEST_NAME


def load_manifest(images_dir: Path, roots: list[Path]) -> JobManifest | None:
    images_dir = resolve_under_roots(images_dir, roots)
    path = manifest_path(images_dir)
    if not path.is_file():
        return None
    with _lock_for(path):
        data = json.loads(path.read_text(encoding="utf-8"))
    return JobManifest.from_dict(data)


def save_manifest(manifest: JobManifest, roots: list[Path]) -> Path:
    images_dir = resolve_under_roots(Path(manifest.images_dir), roots)
    images_dir.mkdir(parents=True, exist_ok=True)
    path = manifest_path(images_dir)
    manifest.updated_at = _utc_now()
    payload = json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n"
    with _lock_for(path):
        tmp = path.with_suffix(".tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    return path


def create_or_resume_job(
    *,
    story_key: str,
    story_path: Path,
    images_dir: Path,
    prompt_file: Path,
    selected: list[ScenePrompt],
    roots: list[Path],
    regenerate: bool = False,
    settings: dict[str, Any] | None = None,
) -> JobManifest:
    images_dir = resolve_under_roots(images_dir, roots)
    existing = load_manifest(images_dir, roots)
    # Block only when a runner still holds the lock. Orphaned control=running
    # (e.g. SIGPIPE / killed CLI) must be resumable without a manual stop.
    if existing and existing.control == "running" and existing.lock_owner and existing.active_scene is not None:
        raise RuntimeError(
            f"Job {existing.job_id} is already running for this story "
            f"(active scene {existing.active_scene}). Pause/stop it first."
        )

    if existing is None:
        manifest = JobManifest(
            job_id=str(uuid.uuid4()),
            story_key=story_key,
            story_path=str(story_path),
            images_dir=str(images_dir),
            prompt_file=str(prompt_file),
            settings=settings or dict(DEFAULT_SETTINGS),
            scene_from=selected[0].scene if selected else None,
            scene_to=selected[-1].scene if selected else None,
        )
    else:
        manifest = existing
        manifest.settings = settings or manifest.settings or dict(DEFAULT_SETTINGS)
        manifest.scene_from = selected[0].scene if selected else manifest.scene_from
        manifest.scene_to = selected[-1].scene if selected else manifest.scene_to

    for prompt in selected:
        key = str(prompt.scene)
        prev = SceneState.from_dict(manifest.scenes[key]) if key in manifest.scenes else None
        stem = scene_filename_stem(prompt.scene)
        existing_file = None
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            candidate = images_dir / f"{stem}{ext}"
            if candidate.is_file() and candidate.stat().st_size > 0:
                existing_file = candidate
                break

        if (
            not regenerate
            and prev
            and prev.status == "completed"
            and prev.prompt_hash == prompt.prompt_hash
            and existing_file is not None
        ):
            # Keep completed state
            continue

        if not regenerate and existing_file is not None and (prev is None or prev.prompt_hash == prompt.prompt_hash):
            # File present from prior run — mark completed if settings match or unknown.
            state = prev or SceneState(scene=prompt.scene, prompt_hash=prompt.prompt_hash)
            state.status = "completed"
            state.prompt_hash = prompt.prompt_hash
            state.saved_path = str(existing_file)
            state.completed_at = state.completed_at or _utc_now()
            manifest.scenes[key] = state.to_dict()
            continue

        if prev and prev.prompt_hash != prompt.prompt_hash and prev.status == "completed":
            # Prompt changed — require re-queue (do not auto-delete completed file).
            state = SceneState(
                scene=prompt.scene,
                prompt_hash=prompt.prompt_hash,
                status="queued",
                attempt_count=0,
                error_category="prompt_changed",
                error_message="Prompt hash changed since completed image; queued for regenerate.",
            )
            manifest.scenes[key] = state.to_dict()
            continue

        state = SceneState(
            scene=prompt.scene,
            prompt_hash=prompt.prompt_hash,
            status="queued",
            attempt_count=prev.attempt_count if prev and not regenerate else 0,
            model=(settings or DEFAULT_SETTINGS)["model"],
            aspect_ratio=(settings or DEFAULT_SETTINGS)["aspect_ratio"],
            download_variant=(settings or DEFAULT_SETTINGS)["download_variant"],
        )
        if regenerate and existing_file is not None:
            # Explicit regenerate: leave file until successful save overwrites.
            state.error_message = "Regenerate requested"
        manifest.scenes[key] = state.to_dict()

    # If every selected scene is already completed, stay idle (resume skip).
    selected_keys = {str(p.scene) for p in selected}
    all_done = selected_keys and all(
        (manifest.scenes.get(k) or {}).get("status") == "completed" for k in selected_keys
    )
    manifest.control = "idle" if all_done else "running"
    manifest.lock_owner = None
    if all_done:
        manifest.active_scene = None
    save_manifest(manifest, roots)
    return manifest


def summarize(manifest: JobManifest) -> dict[str, int]:
    counts = {
        "completed": 0,
        "failed": 0,
        "needs_review": 0,
        "queued": 0,
        "in_progress": 0,
        "remaining": 0,
    }
    for scene in manifest.scenes.values():
        status = scene.get("status")
        if status == "completed":
            counts["completed"] += 1
        elif status == "failed":
            counts["failed"] += 1
        elif status == "needs_review":
            counts["needs_review"] += 1
        elif status == "queued":
            counts["queued"] += 1
            counts["remaining"] += 1
        else:
            counts["in_progress"] += 1
            counts["remaining"] += 1
    return counts


def next_queued_scene(manifest: JobManifest) -> SceneState | None:
    items = sorted(
        (SceneState.from_dict(v) for v in manifest.scenes.values()),
        key=lambda s: s.scene,
    )
    for item in items:
        if manifest.scene_from is not None and item.scene < manifest.scene_from:
            continue
        if manifest.scene_to is not None and item.scene > manifest.scene_to:
            continue
        if item.status in ("queued", "failed") and item.error_category != "policy_rejection":
            if item.status == "failed" and item.error_category == "policy_rejection":
                continue
            if item.status == "failed":
                # Retry-failed is explicit; next_queued only picks queued unless retry mode.
                continue
            return item
    return None


def next_retryable_scene(manifest: JobManifest) -> SceneState | None:
    items = sorted(
        (SceneState.from_dict(v) for v in manifest.scenes.values()),
        key=lambda s: s.scene,
    )
    for item in items:
        if item.status == "queued":
            return item
        if item.status == "failed" and item.error_category != "policy_rejection":
            return item
    return None


def update_scene(
    manifest: JobManifest,
    scene: int,
    roots: list[Path],
    **fields: Any,
) -> JobManifest:
    key = str(scene)
    if key not in manifest.scenes:
        raise KeyError(f"Scene {scene} not in job")
    state = SceneState.from_dict(deepcopy(manifest.scenes[key]))
    for name, value in fields.items():
        if not hasattr(state, name):
            raise ValueError(f"Unknown scene field: {name}")
        setattr(state, name, value)
    if state.status == "submitting" and not state.started_at:
        state.started_at = _utc_now()
    if state.status == "completed":
        state.completed_at = _utc_now()
        state.error_category = None
        state.error_message = None
    manifest.scenes[key] = state.to_dict()
    if state.status in ("submitting", "generating", "upscaling", "downloading", "saving", "configuring"):
        manifest.active_scene = scene
    elif manifest.active_scene == scene and state.status in ("completed", "failed", "needs_review", "queued"):
        manifest.active_scene = None
    save_manifest(manifest, roots)
    return manifest
