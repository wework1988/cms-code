"""Recompile a saved map clip with another appearance theme.

Geography, camera keyframes, and narration timing stay. DeepSeek is not called.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from map_story.compile import compile_resolved_plan
from map_story.sequence import apply_palette
from map_story.themes import applies_palette, resolve_theme


def places_from_resolved(resolved: dict) -> dict:
    places = {}
    for pid, feature in (resolved.get("features") or {}).items():
        if not isinstance(feature, dict):
            continue
        row = {
            "id": feature.get("id") or pid,
            "name": feature.get("name") or pid,
            "level": feature.get("level") or "region",
            "parent": feature.get("parent"),
            "source_id": feature.get("source_id") or pid,
            "representation": feature.get("representation") or "boundary",
            "bbox": feature.get("bbox"),
            "anchor": feature.get("anchor"),
        }
        if feature.get("feature"):
            row["feature"] = feature["feature"]
        if feature.get("geojson"):
            row["geojson"] = feature["geojson"]
        places[pid] = row
    return places


def camera_signature(resolved: dict) -> list:
    signature = []
    for frame in (resolved.get("camera") or {}).get("keyframes") or []:
        signature.append([
            round(float(frame.get("t", 0)), 3),
            [round(float(v), 5) for v in frame.get("center") or []],
            round(float(frame.get("zoom", 0)), 4),
        ])
    return signature


def restyle_plan(semantic: dict, resolved: dict, theme: dict, *, engine: str = "maplibre") -> dict:
    plan = copy.deepcopy(semantic)
    style = theme.get("base_id") or theme.get("id") or plan.get("style")
    if str(theme.get("id") or "").startswith("custom_"):
        plan["style"] = theme["id"]
    else:
        plan["style"] = theme.get("id") or style
    if applies_palette(theme):
        apply_palette(plan, plan["style"], theme)
    places = places_from_resolved(resolved)
    compiled = compile_resolved_plan(
        plan,
        places,
        engine_hint=engine,
        job_settings={"map_theme": theme},
        width=int(resolved.get("width") or 1920),
        height=int(resolved.get("height") or 1080),
        fps=int(resolved.get("fps") or 30),
    )
    compiled["theme_hash"] = theme.get("theme_hash")
    compiled["restyle"] = {
        "source_style": semantic.get("style"),
        "theme_id": theme.get("id"),
        "theme_revision": theme.get("revision"),
        "theme_hash": theme.get("theme_hash"),
        "deepseek": False,
    }
    return compiled


def load_theme(style: str, snapshot: dict | None = None) -> dict:
    return resolve_theme(style, snapshot)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
