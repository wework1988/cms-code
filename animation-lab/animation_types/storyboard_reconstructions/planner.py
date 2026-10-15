"""Storyboard planning. Flow and signed-in Chrome are not launched."""
from __future__ import annotations

import os
from pathlib import Path

from animation_core.planning import load_key
from animation_types.documentary.common import NeedsAssets
from animation_types.documentary.fixtures import ensure_assets
from animation_types.documentary.planning import POLICY, ask_json
from animation_types.timeline.planner import split_sentences, validate_selection

from .schema import validate_semantic_plan

PASSAGE = (
    "रात को चौकी पर पहरा शुरू हुआ।\n"
    "सुबह नदी का मोड़ साफ दिखा।\n"
    "शाम तक रास्ता फिर खुल गया।"
)
ROOT = Path(__file__).resolve().parents[2]
INSTRUCTIONS = """
Animation type storyboard_reconstructions.
Templates: cinematic_sequence, panel_expand, detail_focus.
Use approved local images. Do not request a new image generator job.
If the pictures are reconstructions, keep provenance and the label "Illustrative reconstruction".
Do not describe character movement. Captions must be exact substrings.
""".strip()


def sample_plan() -> tuple[dict, str]:
    assets = ensure_assets()
    sentences = PASSAGE.split("\n")
    images = []
    for key, sentence, caption in (
        ("scene_a", sentences[0], "रात को चौकी"),
        ("scene_b", sentences[1], "नदी का मोड़"),
        ("scene_c", sentences[2], "रास्ता फिर खुल गया"),
    ):
        images.append({
            "path": str(assets[key]),
            "caption": caption,
            "evidence_quote": sentence,
            "provenance": "synthetic-fixture",
        })
    images[2]["focus"] = {"x": 0.56, "y": 0.62, "width": 0.3, "height": 0.22}
    plan = {
        "animation_type": "storyboard_reconstructions",
        "template_id": "detail_focus",
        "style_preset": "cinematic_dark",
        "title": "दृश्य क्रम",
        "language": "hi",
        "duration_seconds": 12,
        "provider": "local",
        "illustrative": True,
        "label": "Illustrative reconstruction",
        "images": images,
        "beats": [
            {"action": "show", "image_index": 0, "evidence_quote": sentences[0]},
            {"action": "show", "image_index": 1, "evidence_quote": sentences[1]},
            {"action": "detail", "image_index": 2, "evidence_quote": sentences[2]},
        ],
    }
    return validate_semantic_plan(plan, PASSAGE), PASSAGE


def select_clips(snapshot: dict) -> dict:
    if snapshot.get("planner") != "local":
        return _model(snapshot, None)
    sentences = split_sentences(snapshot["script"])
    if len(sentences) < 2:
        return {"clips": [], "explanation": "No passage has scenes to reconstruct."}
    chosen = sentences[:3]
    passage = snapshot["script"][chosen[0][1]:chosen[-1][2]]
    return {"clips": [{
        "id": "clip_01",
        "title": "दृश्य",
        "reason": "The passage has ordered scenes with approved pictures.",
        "source_passage": passage,
        "offset_start": chosen[0][1],
        "offset_end": chosen[-1][2],
        "beats": ["Open on the first scene", "Move to the next scene", "Hold the last detail"],
    }], "explanation": ""}


def plan_clip(snapshot: dict, selected: dict) -> dict:
    if snapshot.get("planner") != "local":
        return _model(snapshot, selected)
    inputs = snapshot.get("inputs") or {}
    if inputs.get("provider") == "flow":
        raise NeedsAssets("External image generation is not launched for this render")
    paths = inputs.get("images") or []
    if len(paths) < 2:
        raise NeedsAssets("Attach 2 or 3 approved scene images")
    passage = selected["source_passage"]
    sentences = [item[0] for item in split_sentences(passage)]
    images = []
    for index, path in enumerate(paths[:3]):
        sentence = sentences[min(index, len(sentences) - 1)]
        images.append({
            "path": path,
            "caption": sentence,
            "evidence_quote": sentence,
            "provenance": "supplied",
        })
    plan = {
        "animation_type": "storyboard_reconstructions",
        "template_id": inputs.get("template_id") or "cinematic_sequence",
        "style_preset": inputs.get("style_preset") or "cinematic_dark",
        "title": selected.get("title") or "दृश्य",
        "language": snapshot.get("language") or "hi",
        "duration_seconds": float(snapshot["duration_seconds"]),
        "provider": "local",
        "illustrative": bool(inputs.get("illustrative", True)),
        "label": "Illustrative reconstruction",
        "images": images,
        "beats": [
            {"action": "show", "image_index": index, "evidence_quote": image["evidence_quote"]}
            for index, image in enumerate(images)
        ],
    }
    if len(plan["beats"]) == 2:
        plan["beats"].append({
            "action": "detail",
            "image_index": 1,
            "evidence_quote": images[-1]["evidence_quote"],
        })
    return validate_semantic_plan(plan, passage)


def _model(snapshot: dict, selected: dict | None) -> dict:
    key = load_key(Path(snapshot.get("env_file") or ROOT.parent / "story-pipeline-worker" / ".env"))
    system = f"{POLICY}\n\n{snapshot.get('master_prompt') or ''}\n\n{INSTRUCTIONS}"
    if selected is None:
        limit = min(int(snapshot.get("max_clips") or 1), 3)
        return ask_json(
            key=key,
            model=snapshot.get("model") or os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"),
            timeout=int(snapshot.get("timeout") or 180),
            system=system,
            user={"script": snapshot["script"], "max_clips": limit},
            validate=lambda doc: validate_selection(doc, snapshot["script"], max_clips=limit),
            client=snapshot.get("_client"),
        )
    return ask_json(
        key=key,
        model=snapshot.get("model") or os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"),
        timeout=int(snapshot.get("timeout") or 180),
        system=system,
        user={"passage": selected["source_passage"], "inputs": snapshot.get("inputs") or {}},
        validate=lambda doc: validate_semantic_plan(doc, selected["source_passage"]),
        client=snapshot.get("_client"),
    )
