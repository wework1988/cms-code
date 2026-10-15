"""Document planning. Unlocated targets are sent back for review."""
from __future__ import annotations

import os
from pathlib import Path

from animation_core.planning import load_key
from animation_types.documentary.common import NeedsAssets, NeedsReview
from animation_types.documentary.fixtures import ensure_assets
from animation_types.documentary.planning import POLICY, ask_json
from animation_types.timeline.planner import split_sentences, validate_selection

from .schema import validate_semantic_plan

PASSAGE = (
    "यह पृष्ठ एक सिंथेटिक प्रदर्शन है।\n"
    "The river changed course after the flood.\n"
    "हाशिये की टिप्पणी उसी वाक्य को दिखाती है।"
)
ROOT = Path(__file__).resolve().parents[2]
INSTRUCTIONS = """
Animation type document_highlighting.
Templates: archival_desk, full_frame, excerpt_panel.
Use a supplied PDF or scan. A scan has no selectable PDF text.
If the target region is missing or uncertain, ask for review.
Do not invent a masthead, seal, or excerpt. Keep the asset, page, excerpt, and region.
""".strip()


def sample_plan() -> tuple[dict, str]:
    assets = ensure_assets()
    sentences = PASSAGE.split("\n")
    plan = {
        "animation_type": "document_highlighting",
        "template_id": "excerpt_panel",
        "style_preset": "archival_paper",
        "title": "सिंथेटिक पृष्ठ",
        "language": "hi",
        "duration_seconds": 12,
        "asset": {
            "path": str(assets["pdf"]),
            "kind": "pdf",
            "page": 1,
            "text_source": "supplied_region",
        },
        "page": 1,
        "region": {"x": 0.1, "y": 0.15, "width": 0.8, "height": 0.08},
        "excerpt": "The river changed course after the flood.",
        "annotation": "The river changed course after the flood.",
        "disclosure": "Synthetic demonstration",
        "beats": [
            {"action": "establish", "evidence_quote": sentences[0]},
            {"action": "zoom", "evidence_quote": sentences[1]},
            {"action": "highlight", "evidence_quote": sentences[1]},
            {"action": "annotate", "evidence_quote": sentences[2]},
        ],
    }
    return validate_semantic_plan(plan, PASSAGE), PASSAGE


def select_clips(snapshot: dict) -> dict:
    if snapshot.get("planner") != "local":
        return _model(snapshot, None)
    sentences = split_sentences(snapshot["script"])
    if len(sentences) < 2:
        return {"clips": [], "explanation": "No passage points at a document."}
    chosen = sentences[:3] if len(sentences) >= 3 else sentences
    passage = snapshot["script"][chosen[0][1]:chosen[-1][2]]
    return {"clips": [{
        "id": "clip_01",
        "title": "दस्तावेज़",
        "reason": "The passage refers to a page that can be shown.",
        "source_passage": passage,
        "offset_start": chosen[0][1],
        "offset_end": chosen[-1][2],
        "beats": ["Show the page", "Move to the passage", "Hold the annotation"],
    }], "explanation": ""}


def plan_clip(snapshot: dict, selected: dict) -> dict:
    if snapshot.get("planner") != "local":
        return _model(snapshot, selected)
    inputs = snapshot.get("inputs") or {}
    if not inputs.get("document"):
        raise NeedsAssets("Attach a PDF or scanned page")
    if not inputs.get("region"):
        raise NeedsReview("The highlight region is not located confidently")
    passage = selected["source_passage"]
    sentences = [item[0] for item in split_sentences(passage)]
    path = str(inputs["document"])
    kind = "pdf" if path.lower().endswith(".pdf") else "scan"
    plan = {
        "animation_type": "document_highlighting",
        "template_id": inputs.get("template_id") or "excerpt_panel",
        "style_preset": inputs.get("style_preset") or "archival_paper",
        "title": selected.get("title") or "दस्तावेज़",
        "language": snapshot.get("language") or "hi",
        "duration_seconds": float(snapshot["duration_seconds"]),
        "asset": {
            "path": path,
            "kind": kind,
            "page": int(inputs.get("page") or 1),
            "text_source": inputs.get("text_source") or "supplied_region",
        },
        "page": int(inputs.get("page") or 1),
        "region": inputs["region"],
        "excerpt": inputs.get("excerpt") or sentences[0],
        "annotation": inputs.get("annotation") or sentences[-1],
        "disclosure": "Synthetic demonstration" if inputs.get("synthetic") else "",
        "beats": [
            {"action": "establish", "evidence_quote": sentences[0]},
            {"action": "zoom", "evidence_quote": sentences[min(1, len(sentences) - 1)]},
            {"action": "highlight", "evidence_quote": sentences[min(1, len(sentences) - 1)]},
            {"action": "annotate", "evidence_quote": sentences[-1]},
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
