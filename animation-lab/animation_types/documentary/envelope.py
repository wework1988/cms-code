"""Compiled render envelope. Times are explicit; the browser does not invent motion."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .common import fingerprint, schedule


def timed_beats(actions: list[dict], duration: float, hold: float = 2.0) -> list[dict]:
    slots = schedule(len(actions), duration, hold)
    beats = []
    for action, slot in zip(actions, slots):
        beats.append({**action, **slot})
    return beats


def cache_key(payload: dict) -> str:
    material = {
        "module_version": payload.get("module_version"),
        "template_version": payload.get("template_version"),
        "template_id": payload.get("template_id"),
        "style_preset": payload.get("style_preset"),
        "duration_seconds": payload.get("duration_seconds"),
        "fps": payload.get("fps"),
        "beats": payload.get("beats"),
        "assets": payload.get("assets"),
    }
    raw = json.dumps(material, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def finish(plan: dict, files: list[Path]) -> dict:
    assets = []
    for file in files:
        assets.append({"path": str(file.resolve()), "sha256": fingerprint(file)})
    plan["assets"] = assets
    plan["cache_key"] = cache_key(plan)
    return plan
