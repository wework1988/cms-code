"""Before/after planning. Dates are never invented."""
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
    "पहले किनारा नीचा था।\n"
    "बाद में किनारा ऊँचा किया गया।\n"
    "बाढ़ के बाद रास्ता बदल गया।"
)
ROOT = Path(__file__).resolve().parents[2]
INSTRUCTIONS = """
Animation type before_after.
Templates: split_divider, matched_crossfade, editorial_panels.
Use editorial_panels when the two pictures are different viewpoints.
Do not invent a before image, an after image, or a date.
If a date is not written in the passage, leave it null.
""".strip()


def sample_plan() -> tuple[dict, str]:
    assets = ensure_assets()
    sentences = PASSAGE.split("\n")
    plan = {
        "animation_type": "before_after",
        "template_id": "editorial_panels",
        "style_preset": "clean_editorial",
        "title": "किनारे का बदलाव",
        "language": "hi",
        "duration_seconds": 12,
        "viewpoints_differ": True,
        "disclosure": "ये अलग दृष्टिकोण की प्रदर्शन तस्वीरें हैं। इन्हें एक ही कैमरे की परत न समझें।",
        "before": {"path": str(assets["before"]), "label": "पहले", "date": None},
        "after": {"path": str(assets["after"]), "label": "बाद में", "date": None},
        "beats": [
            {"action": "establish", "evidence_quote": sentences[0]},
            {"action": "reveal_after", "evidence_quote": sentences[1]},
            {"action": "emphasize", "evidence_quote": sentences[2]},
        ],
    }
    return validate_semantic_plan(plan, PASSAGE), PASSAGE


def select_clips(snapshot: dict) -> dict:
    script = snapshot["script"]
    if snapshot.get("planner") != "local":
        return _model(snapshot, None)
    sentences = split_sentences(script)
    if len(sentences) < 2:
        return {"clips": [], "explanation": "No passage compares a before and after state."}
    chosen = sentences[:3] if len(sentences) >= 3 else sentences
    passage = script[chosen[0][1]:chosen[-1][2]]
    return {"clips": [{
        "id": "clip_01",
        "title": "पहले और बाद",
        "reason": "The passage states a change between two conditions.",
        "source_passage": passage,
        "offset_start": chosen[0][1],
        "offset_end": chosen[-1][2],
        "beats": ["Establish the earlier state", "Reveal the later state", "Hold the comparison"],
    }], "explanation": ""}


def plan_clip(snapshot: dict, selected: dict) -> dict:
    if snapshot.get("planner") != "local":
        return _model(snapshot, selected)
    inputs = snapshot.get("inputs") or {}
    if not inputs.get("before") or not inputs.get("after"):
        raise NeedsAssets("Attach the before and after assets")
    passage = selected["source_passage"]
    sentences = [item[0] for item in split_sentences(passage)]
    plan = {
        "animation_type": "before_after",
        "template_id": inputs.get("template_id") or "editorial_panels",
        "style_preset": inputs.get("style_preset") or "clean_editorial",
        "title": selected.get("title") or "तुलना",
        "language": snapshot.get("language") or "hi",
        "duration_seconds": float(snapshot["duration_seconds"]),
        "viewpoints_differ": bool(inputs.get("viewpoints_differ", True)),
        "disclosure": inputs.get("disclosure") or "ये अलग दृष्टिकोण हैं।",
        "before": {"path": inputs["before"], "label": inputs.get("before_label") or "पहले", "date": inputs.get("before_date")},
        "after": {"path": inputs["after"], "label": inputs.get("after_label") or "बाद में", "date": inputs.get("after_date")},
        "beats": [
            {"action": "establish", "evidence_quote": sentences[0]},
            {"action": "reveal_after", "evidence_quote": sentences[min(1, len(sentences) - 1)]},
            {"action": "emphasize", "evidence_quote": sentences[-1]},
        ],
    }
    return validate_semantic_plan(plan, passage)


def _model(snapshot: dict, selected: dict | None) -> dict:
    key = load_key(Path(snapshot.get("env_file") or ROOT.parent / "story-pipeline-worker" / ".env"))
    if selected is None:
        limit = min(int(snapshot.get("max_clips") or 1), 3)
        return ask_json(
            key=key,
            model=snapshot.get("model") or os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"),
            timeout=int(snapshot.get("timeout") or 180),
            system=f"{POLICY}\n\n{snapshot.get('master_prompt') or ''}\n\n{INSTRUCTIONS}",
            user={"script": snapshot["script"], "max_clips": limit},
            validate=lambda doc: validate_selection(doc, snapshot["script"], max_clips=limit),
            client=snapshot.get("_client"),
        )
    return ask_json(
        key=key,
        model=snapshot.get("model") or os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"),
        timeout=int(snapshot.get("timeout") or 180),
        system=f"{POLICY}\n\n{snapshot.get('master_prompt') or ''}\n\n{INSTRUCTIONS}",
        user={"passage": selected["source_passage"], "inputs": snapshot.get("inputs") or {}},
        validate=lambda doc: validate_semantic_plan(doc, selected["source_passage"]),
        client=snapshot.get("_client"),
    )
