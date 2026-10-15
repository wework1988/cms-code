"""Select a statement worth emphasizing. Local mode does not call DeepSeek."""
from __future__ import annotations

import os
from pathlib import Path

from animation_core.planning import load_key
from animation_types.documentary.planning import POLICY, ask_json
from animation_types.timeline.planner import split_sentences, validate_selection

from .schema import validate_semantic_plan

PASSAGE = (
    "यह बदलाव एक दिन में नहीं आया।\n"
    "सदियों तक पुरानी पहचान कायम रही।\n"
    "धीरे-धीरे सत्ता और समाज दोनों बदलने लगे।"
)
ROOT = Path(__file__).resolve().parents[2]

INSTRUCTIONS = """
Animation type text_highlighting.
Templates: editorial_statement, quote_annotation, contrast_reveal.
Use editorial_statement for narration. Use quote_annotation only when the
passage itself names the speaker. Use contrast_reveal for two opposed ideas
and a takeaway. Emphasize a phrase that already appears. Do not split Hindi
letters, conjuncts, or vowel marks. Keep a shorter caption's supporting quote.
""".strip()


def _emphasis(sentence: str) -> str | None:
    words = sentence.replace("।", "").split()
    if "नहीं" in words:
        index = words.index("नहीं")
        start = max(0, index - 2)
        return " ".join(words[start:index + 1])
    if len(words) >= 2:
        return " ".join(words[:2])
    return None


def sample_plan() -> tuple[dict, str]:
    lines = [part for part in PASSAGE.split("\n") if part.strip()]
    plan = {
        "animation_type": "text_highlighting",
        "template_id": "editorial_statement",
        "style_preset": "cinematic_dark",
        "title": "बदलाव का क्रम",
        "kicker": "Statement",
        "language": "hi",
        "duration_seconds": 12,
        "lines": [
            {"id": "line_1", "text": lines[0], "emphasis": "एक दिन में नहीं"},
            {"id": "line_2", "text": lines[1], "emphasis": None},
            {"id": "line_3", "text": lines[2], "emphasis": None, "role": "takeaway"},
        ],
        "beats": [
            {"action": "reveal", "target": "line_1", "evidence_quote": lines[0]},
            {"action": "emphasize", "target": "line_1", "evidence_quote": lines[0]},
            {"action": "reveal", "target": "line_2", "evidence_quote": lines[1]},
            {"action": "reveal", "target": "line_3", "evidence_quote": lines[2]},
        ],
    }
    return validate_semantic_plan(plan, PASSAGE), PASSAGE


def _from_passage(passage: str, *, title: str, preset: str, template: str) -> dict:
    sentences = [item[0] for item in split_sentences(passage)]
    if not 3 <= len(sentences) <= 4:
        raise ValueError("This passage does not have 3 or 4 statements to emphasize")
    lines = []
    beats = []
    for index, sentence in enumerate(sentences, start=1):
        line_id = f"line_{index}"
        emphasis = _emphasis(sentence) if index == 1 else None
        if emphasis and emphasis not in sentence:
            emphasis = None
        lines.append({
            "id": line_id,
            "text": sentence,
            "emphasis": emphasis,
            "role": "takeaway" if index == len(sentences) else "statement",
        })
        beats.append({"action": "reveal", "target": line_id, "evidence_quote": sentence})
    if lines[0]["emphasis"]:
        beats.insert(1, {"action": "emphasize", "target": "line_1", "evidence_quote": sentences[0]})
    if len(beats) > 4:
        beats = [beats[0], beats[1], beats[2], beats[-1]]
    plan = {
        "animation_type": "text_highlighting",
        "template_id": template if template in {"editorial_statement", "contrast_reveal"} else "editorial_statement",
        "style_preset": preset,
        "title": title,
        "kicker": "Statement",
        "language": "hi",
        "duration_seconds": 12,
        "lines": lines[:4],
        "beats": beats[:4],
    }
    return validate_semantic_plan(plan, passage)


def select_clips(snapshot: dict) -> dict:
    script = snapshot["script"]
    limit = min(int(snapshot.get("max_clips") or 1), 3)
    if snapshot.get("planner") == "local":
        sentences = split_sentences(script)
        if len(sentences) < 3:
            return {"clips": [], "explanation": "No passage has three statements to emphasize."}
        chosen = sentences[:3]
        passage = script[chosen[0][1]:chosen[-1][2]]
        return {
            "clips": [{
                "id": "clip_01",
                "title": "मुख्य कथन",
                "reason": "The passage turns on one statement rather than a list of facts.",
                "source_passage": passage,
                "offset_start": chosen[0][1],
                "offset_end": chosen[-1][2],
                "beats": ["Reveal the opening line", "Emphasize its key phrase", "Reveal the following lines"],
            }],
            "explanation": "",
        }
    key = load_key(Path(snapshot.get("env_file") or ROOT.parent / "story-pipeline-worker" / ".env"))
    system = f"{POLICY}\n\n{snapshot.get('master_prompt') or ''}\n\n{INSTRUCTIONS}"
    return ask_json(
        key=key,
        model=snapshot.get("model") or os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"),
        timeout=int(snapshot.get("timeout") or 180),
        system=system,
        user={"script": script, "max_clips": limit, "duration_seconds": snapshot.get("duration_seconds")},
        validate=lambda doc: validate_selection(doc, script, max_clips=limit),
        client=snapshot.get("_client"),
    )


def plan_clip(snapshot: dict, selected: dict) -> dict:
    passage = selected["source_passage"]
    preset = (snapshot.get("inputs") or {}).get("style_preset") or "cinematic_dark"
    template = (snapshot.get("inputs") or {}).get("template_id") or "editorial_statement"
    if snapshot.get("planner") == "local":
        plan = _from_passage(passage, title=selected.get("title") or "कथन", preset=preset, template=template)
        plan["duration_seconds"] = float(snapshot["duration_seconds"])
        return validate_semantic_plan(plan, passage)
    key = load_key(Path(snapshot.get("env_file") or ROOT.parent / "story-pipeline-worker" / ".env"))
    system = f"{POLICY}\n\n{snapshot.get('master_prompt') or ''}\n\n{INSTRUCTIONS}"
    return ask_json(
        key=key,
        model=snapshot.get("model") or os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"),
        timeout=int(snapshot.get("timeout") or 180),
        system=system,
        user={"passage": passage, "title": selected.get("title"), "duration_seconds": snapshot["duration_seconds"]},
        validate=lambda doc: validate_semantic_plan(doc, passage),
        client=snapshot.get("_client"),
    )
