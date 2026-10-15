"""Relationship plans. Co-mention is not evidence of a connection."""
from __future__ import annotations

from animation_types.documentary.common import PRESETS, NeedsReview, PlanError, reject_forbidden, require_quote

TEMPLATES = ("chain", "radial", "hierarchy")


def validate_semantic_plan(plan: dict, passage: str) -> dict:
    reject_forbidden(plan)
    if plan.get("animation_type") != "relationship_diagrams":
        raise PlanError("animation_type must be relationship_diagrams")
    if plan.get("template_id") not in TEMPLATES:
        raise PlanError("Unknown relationship template")
    if plan.get("style_preset") not in PRESETS:
        raise PlanError("Unknown style preset")
    entities = plan.get("entities")
    edges = plan.get("edges")
    if not isinstance(entities, list) or not 2 <= len(entities) <= 6:
        raise PlanError("A diagram needs 2 to 6 supplied entities")
    if not isinstance(edges, list) or not edges:
        raise NeedsReview("No supported relationship was supplied")
    ids = []
    labels = {}
    for entity in entities:
        if not isinstance(entity, dict) or not entity.get("id") or not entity.get("label"):
            raise PlanError("Each entity needs a stable id and a display label")
        if entity["id"] in ids:
            raise PlanError("Entity ids must be stable and unique")
        if entity["label"] not in passage:
            raise NeedsReview(f"The label {entity['label']!r} is not supported by the passage")
        ids.append(entity["id"])
        labels[entity["id"]] = entity["label"]
    for edge in edges:
        if edge.get("from") not in ids or edge.get("to") not in ids:
            raise PlanError("An edge must connect known entity ids")
        if not edge.get("label"):
            raise PlanError("Each relationship needs a label")
        quote = require_quote(edge.get("evidence_quote", ""), passage)
        if labels[edge["from"]] not in quote or labels[edge["to"]] not in quote:
            raise NeedsReview("A relationship needs a quote that names both entities")
        if edge["label"] not in quote:
            raise NeedsReview("The relationship label must appear in its evidence quote")
    beats = plan.get("beats")
    if not isinstance(beats, list) or not 3 <= len(beats) <= 4:
        raise PlanError("Use 3 or 4 beats")
    for beat in beats:
        require_quote(beat.get("evidence_quote", ""), passage)
        if beat.get("action") not in {"reveal_node", "reveal_nodes", "draw_edge"}:
            raise PlanError("Unknown relationship action")
    return plan
