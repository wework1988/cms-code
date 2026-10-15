"""Compile a document highlight. Provenance stays on the plan."""
from pathlib import Path

from animation_types.documentary.envelope import finish, timed_beats

from .schema import validate_semantic_plan


def compile_plan(plan: dict, passage: str, *, duration_seconds: float) -> dict:
    semantic = validate_semantic_plan(plan, passage)
    compiled = {
        "animation_type": "document_highlighting",
        "module_version": "1.0",
        "template_version": "1.0",
        "template_id": semantic["template_id"],
        "style_preset": semantic["style_preset"],
        "title": semantic.get("title") or "",
        "language": semantic.get("language") or "hi",
        "duration_seconds": duration_seconds,
        "fps": 30,
        "hold_seconds": 2,
        "asset": semantic["asset"],
        "page": semantic.get("page") or semantic["asset"].get("page") or 1,
        "region": semantic["region"],
        "excerpt": semantic["excerpt"],
        "annotation": semantic["annotation"],
        "disclosure": semantic.get("disclosure") or "",
        "beats": timed_beats(semantic["beats"], duration_seconds),
    }
    return finish(compiled, [Path(semantic["asset"]["path"])])
