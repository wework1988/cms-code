"""Data planning. The model may choose a chart and may not invent values."""
from __future__ import annotations

import os
from pathlib import Path

from animation_core.planning import load_key
from animation_types.documentary.common import PlanError
from animation_types.documentary.planning import POLICY, ask_json
from animation_types.timeline.planner import split_sentences, validate_selection

from .schema import validate_semantic_plan

PASSAGE = (
    "पहले स्तर 2 मीटर था।\n"
    "बाद में स्तर 5 मीटर हो गया।\n"
    "माप शून्य मीटर से दिखाई गई है।"
)
ROOT = Path(__file__).resolve().parents[2]
INSTRUCTIONS = """
Animation type data_animations.
Templates: bar_comparison, line_trend, number_counter.
Use only the supplied values. Do not invent numbers or intermediate observations.
Every value must appear as its own number in an evidence quote.
State the unit, the source, and, for percentages, whether they are a share of a whole
or a difference in percentage points. Bar charts start at zero unless the editor
explicitly configures and discloses another baseline.
""".strip()


def sample_plan() -> tuple[dict, str]:
    sentences = PASSAGE.split("\n")
    plan = {
        "animation_type": "data_animations",
        "template_id": "bar_comparison",
        "style_preset": "cinematic_dark",
        "title": "स्तर",
        "language": "hi",
        "duration_seconds": 12,
        "unit": "मीटर",
        "source_label": "Synthetic demonstration",
        "baseline": "zero",
        "emphasis_index": 1,
        "series": [
            {"label": "2 मीटर", "value": 2, "evidence_quote": sentences[0]},
            {"label": "5 मीटर", "value": 5, "evidence_quote": sentences[1]},
        ],
        "beats": [
            {"action": "axes", "evidence_quote": sentences[2]},
            {"action": "reveal_bar", "index": 0, "evidence_quote": sentences[0]},
            {"action": "reveal_bar", "index": 1, "evidence_quote": sentences[1]},
            {"action": "emphasize", "index": 1, "evidence_quote": sentences[1]},
        ],
    }
    return validate_semantic_plan(plan, PASSAGE), PASSAGE


def select_clips(snapshot: dict) -> dict:
    if snapshot.get("planner") != "local":
        return _model(snapshot, None)
    sentences = split_sentences(snapshot["script"])
    if not sentences:
        return {"clips": [], "explanation": "No passage contains data to show."}
    chosen = sentences[:3] if len(sentences) >= 3 else sentences
    passage = snapshot["script"][chosen[0][1]:chosen[-1][2]]
    return {"clips": [{
        "id": "clip_01",
        "title": "आँकड़ा",
        "reason": "The passage states numbers that can be checked.",
        "source_passage": passage,
        "offset_start": chosen[0][1],
        "offset_end": chosen[-1][2],
        "beats": ["Show the scale", "Reveal the values", "Hold the comparison"],
    }], "explanation": ""}


def plan_clip(snapshot: dict, selected: dict) -> dict:
    if snapshot.get("planner") != "local":
        return _model(snapshot, selected)
    inputs = snapshot.get("inputs") or {}
    series = inputs.get("series")
    if not series:
        raise PlanError("No numerical series was supplied")
    passage = selected["source_passage"]
    plan = {
        "animation_type": "data_animations",
        "template_id": inputs.get("template_id") or "bar_comparison",
        "style_preset": inputs.get("style_preset") or "cinematic_dark",
        "title": selected.get("title") or "आँकड़ा",
        "language": snapshot.get("language") or "hi",
        "duration_seconds": float(snapshot["duration_seconds"]),
        "unit": inputs.get("unit") or "",
        "source_label": inputs.get("source_label") or "",
        "baseline": inputs.get("baseline") or "zero",
        "percentage_interpretation": inputs.get("percentage_interpretation"),
        "disclosure": inputs.get("disclosure") or "",
        "emphasis_index": 0,
        "series": series,
        "beats": inputs.get("beats") or _beats(series),
    }
    return validate_semantic_plan(plan, passage)


def _beats(series: list[dict]) -> list[dict]:
    beats = [{"action": "axes", "evidence_quote": series[0]["evidence_quote"]}]
    for index, row in enumerate(series[:3]):
        beats.append({"action": "reveal_bar", "index": index, "evidence_quote": row["evidence_quote"]})
    return beats[:4]


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
