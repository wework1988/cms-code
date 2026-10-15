"""Compile a validated overlay plan into a browser frame plan."""
from __future__ import annotations

from pathlib import Path

from documentary_graphics.assemble import elbow_for, place_card, tokens_for
from documentary_graphics.errors import GraphicsPlanError
from documentary_graphics.timing import anchor_at

from .schema import CALLOUTS, OverlayPlanError

REPO = Path(__file__).resolve().parents[2]


def _asset(value: str) -> str:
    path = Path(value)
    if not path.is_file():
        path = REPO / value
    if not path.is_file():
        raise OverlayPlanError(f"Evidence asset is missing: {value}")
    return str(path.resolve())


def _graphic(overlay: dict, placed: dict | None, entrance: str) -> dict:
    return {
        "id": overlay["id"],
        "treatment": overlay["type"],
        "entrance": entrance,
        "start": overlay["start_time"],
        "reveal": overlay["reveal_duration"],
        "label_fade": overlay["label_fade_duration"],
        "hold": overlay["hold_duration"],
        "exit": overlay["exit_duration"],
        "placement_mode": overlay["placement_mode"],
        "placement": placed,
        "anchor_keyframes": overlay.get("anchor_keyframes"),
        "anchor": overlay.get("anchor"),
        "primary": overlay.get("text") or "",
        "kicker": "",
        "secondary": overlay.get("context") or "",
        "runs": None,
        "badge": overlay.get("badge") or "",
        "underline": False,
        "size_role": "body",
        "rect": overlay.get("rect"),
        "template": overlay.get("template") or "",
        "dim": bool(overlay.get("dim")),
        "points": overlay.get("points"),
        "arrow": bool(overlay.get("arrow")),
        "measure": None,
        "image": None,
        "source_label": overlay.get("source_label") or "",
        "elbow": None,
    }


def compile_overlay(plan: dict, media: dict) -> dict:
    tokens = tokens_for(plan)
    plan = {**plan, "_placed": []}
    graphics = []
    for overlay in plan["overlays"]:
        kind = overlay["type"]
        placed = None
        entrance = "fade_rise"
        if kind in CALLOUTS:
            placed = place_card(overlay["text"], overlay, plan, media, tokens, font_px=tokens["body"], max_width=0.46)
            entrance = "line_draw"
        elif kind == "key_fact":
            text = overlay["text"] if not overlay.get("context") else f"{overlay['text']} {overlay['context']}"
            placed = place_card(text, overlay, plan, media, tokens, font_px=tokens["body"], max_width=0.34)
        elif kind == "evidence_inset":
            placed = place_card(overlay["source_label"], overlay, plan, media, tokens, font_px=tokens["kicker"], max_width=0.28, extra_height=180 / media["height"])
            entrance = "mask_reveal"
        elif kind == "date_label":
            placed = place_card(overlay["text"], overlay, plan, media, tokens, font_px=tokens["title"], max_width=0.4)
        if placed:
            plan["_placed"].append(placed)
        graphic = _graphic(overlay, placed, entrance)
        if kind in CALLOUTS:
            anchor = anchor_at(overlay, overlay["start_time"])
            graphic["elbow"] = elbow_for(placed, anchor, plan, overlay)
        if kind == "evidence_inset":
            graphic["image"] = _asset(overlay["asset"])
            graphic["secondary"] = overlay["source_label"]
            graphic["primary"] = ""
        if kind == "measurement":
            graphic["measure"] = {"value": overlay["value"], "unit": overlay["unit"], "kind": overlay["kind"], "context": overlay["context"]}
            graphic["primary"] = f"{overlay['value']} {overlay['unit']}".strip()
            graphic["secondary"] = overlay["context"]
            midpoint = {
                "x": (overlay["points"][0]["x"] + overlay["points"][1]["x"]) / 2 - 0.07,
                "y": min(overlay["points"][0]["y"], overlay["points"][1]["y"]) - 0.2,
            }
            synthetic = {**overlay, "label": midpoint, "label_placement": "screen_fixed"}
            try:
                graphic["placement"] = place_card(graphic["primary"], synthetic, plan, media, tokens, font_px=tokens["body"], max_width=0.28)
            except GraphicsPlanError:
                graphic["placement"] = place_card(graphic["primary"], {**overlay, "label_placement": "auto", "prefer": "upper_left"}, plan, media, tokens, font_px=tokens["body"], max_width=0.28)
        if kind == "key_fact":
            graphic["secondary"] = overlay.get("context") or ""
            graphic["size_role"] = "body"
        graphics.append(graphic)
    return {
        "module": "cinematic_overlays",
        "preset": tokens["name"],
        "tokens": tokens,
        "width": media["width"],
        "height": media["height"],
        "fps": media["fps"],
        "frames": media["frames"],
        "duration": media["duration"],
        "has_audio": media["has_audio"],
        "graphics": graphics,
        "factual_claim": plan.get("factual_claim", False),
        "sample_note": plan.get("sample_note") or "",
        "timing_source": plan.get("timing_source") or "manual",
        "limitation": plan.get("limitation") or "",
        "asset_roots": sorted({str(Path(graphic["image"]).parent) for graphic in graphics if graphic.get("image")}),
    }
