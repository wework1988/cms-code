"""Relationship planning. Unsupported links stay in review."""
from __future__ import annotations

import os
from pathlib import Path

from animation_core.planning import load_key
from animation_types.documentary.common import NeedsReview
from animation_types.documentary.planning import POLICY, ask_json
from animation_types.timeline.planner import split_sentences, validate_selection

from .schema import validate_semantic_plan

PASSAGE = (
    "सिंधु नगर परिषद ने नदी बोर्ड बनाया।\n"
    "नदी बोर्ड ने बाढ़ कोष को धन दिया।\n"
    "बाढ़ कोष ने तट की मरम्मत कराई।"
)
ROOT = Path(__file__).resolve().parents[2]
INSTRUCTIONS = """
Animation type relationship_diagrams.
Templates: chain, radial, hierarchy.
Use only entities and edges the editor supplied, and only when one quote names both entities and the relationship.
Never infer cause, ownership, or affiliation because two names appear near each other.
If support is missing, ask for review. Do not add an edge to complete a shape.
""".strip()


def sample_plan() -> tuple[dict, str]:
    sentences = PASSAGE.split("\n")
    plan = {
        "animation_type": "relationship_diagrams",
        "template_id": "chain",
        "style_preset": "cinematic_dark",
        "title": "तीन संस्थाएँ",
        "language": "hi",
        "duration_seconds": 12,
        "focus": "council",
        "entities": [
            {"id": "council", "label": "सिंधु नगर परिषद", "type": "organization"},
            {"id": "board", "label": "नदी बोर्ड", "type": "organization"},
            {"id": "fund", "label": "बाढ़ कोष", "type": "organization"},
        ],
        "edges": [
            {"from": "council", "to": "board", "label": "बनाया", "evidence_quote": sentences[0]},
            {"from": "board", "to": "fund", "label": "धन दिया", "evidence_quote": sentences[1]},
        ],
        "beats": [
            {"action": "reveal_node", "target": "council", "evidence_quote": sentences[0]},
            {"action": "reveal_nodes", "targets": ["board", "fund"], "evidence_quote": sentences[1]},
            {"action": "draw_edge", "indexes": [0, 1], "evidence_quote": sentences[0] + "\n" + sentences[1]},
            {"action": "reveal_node", "target": "fund", "evidence_quote": sentences[2]},
        ],
    }
    return validate_semantic_plan(plan, PASSAGE), PASSAGE


def select_clips(snapshot: dict) -> dict:
    if snapshot.get("planner") != "local":
        return _model(snapshot, None)
    sentences = split_sentences(snapshot["script"])
    if len(sentences) < 2:
        return {"clips": [], "explanation": "No passage states a relationship."}
    chosen = sentences[:3] if len(sentences) >= 3 else sentences
    passage = snapshot["script"][chosen[0][1]:chosen[-1][2]]
    return {"clips": [{
        "id": "clip_01",
        "title": "संबंध",
        "reason": "The passage can be checked against supplied entities.",
        "source_passage": passage,
        "offset_start": chosen[0][1],
        "offset_end": chosen[-1][2],
        "beats": ["Show the main entity", "Show the related entities", "Draw the supported links"],
    }], "explanation": ""}


def plan_clip(snapshot: dict, selected: dict) -> dict:
    if snapshot.get("planner") != "local":
        return _model(snapshot, selected)
    inputs = snapshot.get("inputs") or {}
    if not inputs.get("entities") or not inputs.get("edges"):
        raise NeedsReview("Relationships were not supplied. Mentioning two names is not enough.")
    passage = selected["source_passage"]
    plan = {
        "animation_type": "relationship_diagrams",
        "template_id": inputs.get("template_id") or "chain",
        "style_preset": inputs.get("style_preset") or "cinematic_dark",
        "title": selected.get("title") or "संबंध",
        "language": snapshot.get("language") or "hi",
        "duration_seconds": float(snapshot["duration_seconds"]),
        "focus": inputs["entities"][0]["id"],
        "entities": inputs["entities"],
        "edges": inputs["edges"],
        "beats": inputs.get("beats") or [
            {"action": "reveal_node", "target": inputs["entities"][0]["id"], "evidence_quote": inputs["edges"][0]["evidence_quote"]},
            {"action": "reveal_nodes", "targets": [item["id"] for item in inputs["entities"][1:]], "evidence_quote": inputs["edges"][0]["evidence_quote"]},
            {"action": "draw_edge", "indexes": list(range(len(inputs["edges"]))), "evidence_quote": inputs["edges"][0]["evidence_quote"]},
        ],
    }
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
            user={"script": snapshot["script"], "max_clips": limit, "inputs": snapshot.get("inputs") or {}},
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
