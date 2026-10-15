"""Compile typography into the shared browser plan."""
from __future__ import annotations

from documentary_graphics.assemble import place_card, tokens_for

ENTRANCE = {
    "location_title": "fade_rise",
    "impact_word": "scale_settle",
    "impact_phrase": "underline",
    "date_year": "fade_rise",
    "key_number": "number_reveal",
    "chapter_title": "fade_rise",
    "quote_translation": "mask_reveal",
}
ROLE = {
    "location_title": "title",
    "impact_word": "impact",
    "impact_phrase": "impact",
    "date_year": "number",
    "key_number": "number",
    "chapter_title": "title",
    "quote_translation": "body",
}


def compile_typography(plan: dict, media: dict) -> dict:
    tokens = tokens_for(plan)
    plan = {**plan, "_placed": []}
    graphics = []
    for overlay in plan["overlays"]:
        kind = overlay["type"]
        role = ROLE[kind]
        font = tokens[role]
        width = 0.72 if kind in {"impact_phrase", "location_title", "chapter_title"} else 0.46
        if overlay.get("template") == "centered":
            overlay = {**overlay, "allow_center": True, "prefer": "center", "template": "centered"}
        placed = place_card(overlay["text"], overlay, plan, media, tokens, font_px=font, max_width=width)
        plan["_placed"].append(placed)
        graphic = {
            "id": overlay["id"],
            "treatment": kind,
            "entrance": ENTRANCE[kind],
            "start": overlay["start_time"],
            "reveal": overlay["reveal_duration"],
            "label_fade": overlay["label_fade_duration"],
            "hold": overlay["hold_duration"],
            "exit": overlay["exit_duration"],
            "placement_mode": "screen_fixed",
            "placement": placed,
            "primary": overlay.get("text") or "",
            "kicker": "",
            "secondary": "",
            "runs": overlay.get("runs"),
            "badge": overlay.get("badge") or "",
            "underline": kind in {"impact_phrase", "location_title"},
            "size_role": role,
            "rect": None,
            "points": None,
            "arrow": False,
            "image": None,
            "elbow": None,
            "anchor": None,
            "anchor_keyframes": None,
            "dim": False,
            "measure": None,
            "source_label": "",
        }
        if kind == "location_title":
            graphic["kicker"] = overlay["region"]
            graphic["primary"] = overlay["place"]
        elif kind == "date_year":
            graphic["primary"] = overlay["year"]
            graphic["secondary"] = overlay["explanation"]
        elif kind == "key_number":
            graphic["primary"] = overlay["value"]
            graphic["secondary"] = f"{overlay['unit']}  {overlay['context']}"
            graphic["measure"] = {"kind": overlay["kind"]}
        elif kind == "quote_translation":
            graphic["secondary"] = overlay["attribution"]
            graphic["kicker"] = "अनुवाद" if overlay["provenance"]["kind"] == "translation" else "उद्धरण"
        elif kind == "chapter_title" and overlay.get("editorial_demonstration"):
            graphic["badge"] = overlay.get("badge") or "प्रदर्शन"
        graphics.append(graphic)
    return {
        "module": "documentary_typography",
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
        "asset_roots": [],
    }
