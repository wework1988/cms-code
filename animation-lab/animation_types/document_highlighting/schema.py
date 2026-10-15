"""Document plans. Scans are not treated as selectable PDF text."""
from __future__ import annotations

from animation_types.documentary.common import (
    PRESETS,
    NeedsAssets,
    NeedsReview,
    PlanError,
    reject_forbidden,
    require_file,
    require_quote,
)

TEMPLATES = ("archival_desk", "full_frame", "excerpt_panel")


def _box(box: dict) -> None:
    needed = ("x", "y", "width", "height")
    if not isinstance(box, dict) or any(key not in box for key in needed):
        raise NeedsReview("A highlight needs a supplied region or a reliable text position")
    if any(not isinstance(box[key], (int, float)) or box[key] < 0 or box[key] > 1 for key in needed):
        raise PlanError("The highlight region must stay on the page")
    if box["x"] + box["width"] > 1.001 or box["y"] + box["height"] > 1.001:
        raise PlanError("The highlight region must stay on the page")


def validate_semantic_plan(plan: dict, passage: str) -> dict:
    reject_forbidden(plan)
    if plan.get("animation_type") != "document_highlighting":
        raise PlanError("animation_type must be document_highlighting")
    if plan.get("template_id") not in TEMPLATES:
        raise PlanError("Unknown document template")
    if plan.get("style_preset") not in PRESETS:
        raise PlanError("Unknown style preset")
    asset = plan.get("asset")
    if not isinstance(asset, dict):
        raise NeedsAssets("Attach a PDF or a scanned page")
    path = require_file(asset.get("path"))
    kind = asset.get("kind")
    if kind not in {"pdf", "scan"}:
        raise PlanError("Document kind must be pdf or scan")
    if kind == "scan" and path.suffix.lower() == ".pdf":
        raise PlanError("A PDF is not a scan")
    if kind == "pdf" and path.suffix.lower() != ".pdf":
        raise PlanError("This file is not a PDF")
    if asset.get("text_source") == "pdf_text" and kind == "scan":
        raise NeedsReview("A scanned page does not contain selectable PDF text")
    if asset.get("text_source") == "ocr" and not asset.get("ocr_confidence"):
        raise NeedsReview("OCR text needs a confidence check before it is highlighted")
    _box(plan.get("region"))
    excerpt = plan.get("excerpt")
    if not isinstance(excerpt, str) or excerpt not in passage:
        raise PlanError("The excerpt must be an exact substring of the passage")
    annotation = plan.get("annotation")
    if not isinstance(annotation, str) or annotation not in passage:
        raise PlanError("The annotation must be an exact substring of the passage")
    beats = plan.get("beats")
    if not isinstance(beats, list) or not 3 <= len(beats) <= 4:
        raise PlanError("Use 3 or 4 beats")
    actions = [beat.get("action") for beat in beats]
    if "highlight" not in actions:
        raise PlanError("The sequence needs a highlight beat")
    for beat in beats:
        require_quote(beat.get("evidence_quote", ""), passage)
        if beat.get("action") not in {"establish", "zoom", "highlight", "annotate"}:
            raise PlanError("Unknown document action")
    return plan
