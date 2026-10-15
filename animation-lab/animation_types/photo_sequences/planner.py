"""Local photo plans use supplied files only."""
from __future__ import annotations

import os
from pathlib import Path

from animation_core.planning import load_key
from animation_types.documentary.fixtures import ensure_assets
from animation_types.documentary.planning import POLICY, ask_json
from animation_types.timeline.planner import split_sentences, validate_selection

from .schema import validate_semantic_plan

PASSAGE = (
    "बाजार के द्वार पर भीड़ शाम को जुटती थी।\n"
    "भीतर गली में दुकानें देर तक खुली रहती थीं।\n"
    "पुल के किनारे रोशनी पानी पर गिरती थी।"
)
ROOT = Path(__file__).resolve().parents[2]
INSTRUCTIONS = """
Animation type photo_sequences.
Templates: fullscreen_caption, archival_frame, paired_annotation.
Use only supplied image paths. Say which image supports each beat.
Captions must be exact substrings. Do not describe unseen parts of a photograph
and do not request 3D parallax. If fewer than two images were supplied, say assets are required.
""".strip()


def sample_plan() -> tuple[dict, str]:
    assets = ensure_assets()
    sentences = [line for line in PASSAGE.split("\n") if line]
    images = [
        {"path": str(assets["photo_a"]), "caption": "बाजार के द्वार", "focus": None},
        {"path": str(assets["photo_b"]), "caption": "भीतर गली", "focus": None},
        {"path": str(assets["photo_c"]), "caption": "पुल के किनारे", "focus": {"x": 0.56, "y": 0.62, "width": 0.3, "height": 0.22}},
    ]
    plan = {
        "animation_type": "photo_sequences",
        "template_id": "archival_frame",
        "style_preset": "archival_paper",
        "title": "तीन दृश्य",
        "language": "hi",
        "duration_seconds": 12,
        "images": images,
        "beats": [
            {"action": "show", "image_index": 0, "evidence_quote": sentences[0]},
            {"action": "show", "image_index": 1, "evidence_quote": sentences[1]},
            {"action": "show", "image_index": 2, "evidence_quote": sentences[2]},
            {"action": "detail", "image_index": 2, "evidence_quote": sentences[2]},
        ],
    }
    return validate_semantic_plan(plan, PASSAGE), PASSAGE


def _images_from(snapshot: dict, passage: str) -> list[dict]:
    supplied = (snapshot.get("inputs") or {}).get("images") or []
    sentences = [item[0] for item in split_sentences(passage)]
    if len(supplied) < 2:
        from animation_types.documentary.common import NeedsAssets
        raise NeedsAssets("Choose 2 to 4 images before rendering a photo sequence")
    images = []
    for index, path in enumerate(supplied[:4]):
        sentence = sentences[min(index, len(sentences) - 1)]
        caption = sentence.split(" में ")[0].split(" पर ")[0]
        if caption not in passage:
            caption = sentence
        images.append({"path": path, "caption": caption})
    return images


def select_clips(snapshot: dict) -> dict:
    script = snapshot["script"]
    if snapshot.get("planner") == "local":
        sentences = split_sentences(script)
        if len(sentences) < 2:
            return {"clips": [], "explanation": "No passage is long enough for a photo sequence."}
        chosen = sentences[: min(3, len(sentences))]
        passage = script[chosen[0][1]:chosen[-1][2]]
        return {"clips": [{
            "id": "clip_01",
            "title": "तस्वीरों का क्रम",
            "reason": "The passage moves across distinct views.",
            "source_passage": passage,
            "offset_start": chosen[0][1],
            "offset_end": chosen[-1][2],
            "beats": ["Show the first view", "Move to the next view", "Hold the last detail"],
        }], "explanation": ""}
    return _model_select(snapshot)


def plan_clip(snapshot: dict, selected: dict) -> dict:
    passage = selected["source_passage"]
    if snapshot.get("planner") == "local":
        images = _images_from(snapshot, passage)
        sentences = [item[0] for item in split_sentences(passage)]
        beats = []
        for index, sentence in enumerate(sentences[:3]):
            beats.append({"action": "show", "image_index": min(index, len(images) - 1), "evidence_quote": sentence})
        if len(beats) < 3:
            beats.append({"action": "detail", "image_index": len(images) - 1, "evidence_quote": sentences[-1]})
        plan = {
            "animation_type": "photo_sequences",
            "template_id": "archival_frame" if len(images) != 2 else "paired_annotation",
            "style_preset": (snapshot.get("inputs") or {}).get("style_preset") or "archival_paper",
            "title": selected.get("title") or "तस्वीरें",
            "language": snapshot.get("language") or "hi",
            "duration_seconds": float(snapshot["duration_seconds"]),
            "images": images[:2] if len(images) == 2 else images,
            "beats": beats[:4],
            "bridge": images[0]["caption"] if len(images) == 2 else "",
            "caption": images[-1]["caption"],
        }
        return validate_semantic_plan(plan, passage)
    return _model_plan(snapshot, selected)


def _model_select(snapshot: dict) -> dict:
    key = load_key(Path(snapshot.get("env_file") or ROOT.parent / "story-pipeline-worker" / ".env"))
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


def _model_plan(snapshot: dict, selected: dict) -> dict:
    key = load_key(Path(snapshot.get("env_file") or ROOT.parent / "story-pipeline-worker" / ".env"))
    return ask_json(
        key=key,
        model=snapshot.get("model") or os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"),
        timeout=int(snapshot.get("timeout") or 180),
        system=f"{POLICY}\n\n{snapshot.get('master_prompt') or ''}\n\n{INSTRUCTIONS}",
        user={"passage": selected["source_passage"], "images": (snapshot.get("inputs") or {}).get("images") or []},
        validate=lambda doc: validate_semantic_plan(doc, selected["source_passage"]),
        client=snapshot.get("_client"),
    )
