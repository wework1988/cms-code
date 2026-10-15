"""Publish completed map clips as animation/scene_<n>.mp4 without touching video/."""
from __future__ import annotations

import json
import os
from pathlib import Path

MANIFEST_VERSION = "1.0"


class StalePublishError(RuntimeError):
    """An older job tried to replace a newer scene revision."""


def mp4_complete(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        size = path.stat().st_size
        if size < 1000:
            return False
        with path.open("rb") as handle:
            return b"ftyp" in handle.read(4096)
    except OSError:
        return False


def publish_scene_mp4(
    story_root: Path,
    *,
    scene_number: int,
    rendered: Path,
    entry: dict,
    job_created: int,
) -> Path:
    """Validate, then replace the public file. The previous file stays until the new one is ready."""
    if scene_number < 1:
        raise ValueError(f"Scene number {scene_number} cannot be published.")
    if not mp4_complete(rendered):
        raise RuntimeError(f"Refusing to publish an incomplete MP4 for scene {scene_number}.")
    animation = (story_root / "animation").resolve()
    animation.mkdir(parents=True, exist_ok=True)
    lock_path = animation / ".publish.lock"
    with _file_lock(lock_path):
        manifest = _read_manifest(animation / "manifest.json")
        current = _scene_entry(manifest, scene_number)
        if current and int(current.get("job_created") or 0) > int(job_created):
            raise StalePublishError(
                f"Scene {scene_number} already has a newer published map. This job was not published."
            )
        incoming = animation / ".incoming"
        incoming.mkdir(parents=True, exist_ok=True)
        temporary = incoming / f"scene_{scene_number}.{job_created}.mp4"
        _copy_file(rendered, temporary)
        if not mp4_complete(temporary):
            temporary.unlink(missing_ok=True)
            raise RuntimeError(f"Published copy for scene {scene_number} failed validation.")
        public = animation / f"scene_{scene_number}.mp4"
        os.replace(temporary, public)
        stored = dict(entry)
        stored.update({
            "scene_number": scene_number,
            "status": "completed",
            "output_path": f"animation/scene_{scene_number}.mp4",
            "job_created": int(job_created),
        })
        _upsert_scene(manifest, stored)
        _write_manifest(animation / "manifest.json", manifest)
        return public


def update_manifest_scene(story_root: Path, entry: dict) -> None:
    """Record a non-video status without replacing a completed MP4."""
    animation = (story_root / "animation").resolve()
    animation.mkdir(parents=True, exist_ok=True)
    with _file_lock(animation / ".publish.lock"):
        manifest = _read_manifest(animation / "manifest.json")
        number = int(entry["scene_number"])
        current = _scene_entry(manifest, number)
        if current and current.get("status") == "completed" and entry.get("status") != "completed":
            if int(current.get("job_created") or 0) > int(entry.get("job_created") or 0):
                return
        _upsert_scene(manifest, entry)
        _write_manifest(animation / "manifest.json", manifest)


def ensure_manifest(story_root: Path, header: dict) -> None:
    animation = (story_root / "animation").resolve()
    animation.mkdir(parents=True, exist_ok=True)
    with _file_lock(animation / ".publish.lock"):
        manifest = _read_manifest(animation / "manifest.json")
        manifest.update({key: value for key, value in header.items() if key != "scenes"})
        manifest["schema_version"] = MANIFEST_VERSION
        manifest.setdefault("scenes", [])
        _write_manifest(animation / "manifest.json", manifest)


def _scene_entry(manifest: dict, scene_number: int) -> dict | None:
    for entry in manifest.get("scenes") or []:
        if int(entry.get("scene_number") or 0) == scene_number:
            return entry
    return None


def _upsert_scene(manifest: dict, entry: dict) -> None:
    number = int(entry["scene_number"])
    scenes = [item for item in manifest.get("scenes") or [] if int(item.get("scene_number") or 0) != number]
    scenes.append(entry)
    scenes.sort(key=lambda item: int(item.get("scene_number") or 0))
    manifest["scenes"] = scenes
    manifest["schema_version"] = MANIFEST_VERSION


def _read_manifest(path: Path) -> dict:
    if not path.is_file():
        return {"schema_version": MANIFEST_VERSION, "scenes": []}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"schema_version": MANIFEST_VERSION, "scenes": []}
    if not isinstance(loaded, dict):
        return {"schema_version": MANIFEST_VERSION, "scenes": []}
    loaded.setdefault("scenes", [])
    return loaded


def _write_manifest(path: Path, manifest: dict) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _copy_file(source: Path, destination: Path) -> None:
    data = source.read_bytes()
    temporary = destination.with_suffix(destination.suffix + ".partial")
    temporary.write_bytes(data)
    os.replace(temporary, destination)


def _file_lock(path: Path):
    import fcntl
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")

    class _Lock:
        def __enter__(self):
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            return handle

        def __exit__(self, *_args):
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()

    return _Lock()
