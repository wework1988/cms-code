"""Scene duration for map clips. Missing audio timing stays provisional."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def resolve_scene_timing(
    story_root: Path | None,
    scene_number: int,
    configured_duration: float,
) -> dict:
    """Use audio/scene-durations.json when it lists this scene. Never invent an insert time."""
    configured = float(configured_duration)
    missing = {
        "scene_duration_seconds": None,
        "map_duration_seconds": configured,
        "timing_source": "configured_map_duration",
        "timing_source_hash": None,
        "provisional": True,
        "placement": None,
        "role": "alternative_scene_visual",
    }
    if story_root is None:
        return missing
    path = story_root / "audio" / "scene-durations.json"
    if not path.is_file():
        return missing
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return missing
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    for item in payload.get("scenes") or []:
        if int(item.get("number") or 0) != int(scene_number):
            continue
        duration = item.get("duration_seconds")
        if not isinstance(duration, (int, float)) or duration <= 0:
            return missing
        map_duration = min(configured, float(duration))
        return {
            "scene_duration_seconds": float(duration),
            "map_duration_seconds": map_duration,
            "timing_source": "audio/scene-durations.json",
            "timing_source_hash": digest,
            "provisional": False,
            "placement": None,
            "role": "shorter_insert" if map_duration < float(duration) else "scene_visual",
        }
    return missing


def timing_update_available(entry: dict, story_root: Path | None) -> bool:
    """A newer timing file is noted. It does not replace the rendered file."""
    if story_root is None:
        return False
    path = story_root / "audio" / "scene-durations.json"
    if not path.is_file():
        return False
    current = hashlib.sha256(path.read_bytes()).hexdigest()
    recorded = (entry.get("timing") or {}).get("timing_source_hash")
    if not recorded:
        return entry.get("status") == "completed"
    return recorded != current
