"""Build a map focus sequence from resolved places.

Parents are orientation context. A stage is one shot, even when that shot
zooms, highlights, and labels the same place. Colors come from the
documentary palette, not from model output.
"""
from __future__ import annotations

from .narration import duration_for_focuses
from .schema import meaningful_beat_count, validate_semantic_plan
from .themes import applies_palette, palette_roles, theme_for

LEVEL_ORDER = {"country": 0, "state": 1, "district": 2, "city": 3, "region": 4}


def palette_roles_for(style: str | None = None, theme: dict | None = None) -> dict:
    chosen = theme or theme_for(style or "documentary_relief_bold")
    return palette_roles(chosen)


def accept_focus_plan(
    plan: dict,
    selection: dict,
    style: str,
    theme: dict | None = None,
    summaries: list[dict] | None = None,
) -> dict:
    """Keep verified places. Reallocate stages from the administrative hierarchy."""
    from .hierarchy import (
        allocate_focus_stages,
        cards_from_semantic_plan,
        dedupe_labels,
        merge_verified_ancestors,
        ordered_subjects,
    )
    from .opening import normalize_semantic_opening

    plan = merge_verified_ancestors(plan, summaries)
    cards = cards_from_semantic_plan(plan)
    subjects = ordered_subjects(plan, cards)
    subject_ids = {str(card["id"]) for card in subjects}
    orientations = [card for card in cards if str(card["id"]) not in subject_ids]
    target = int(selection["target_focus_count"])
    stages, report = allocate_focus_stages(subjects, orientations, target)
    language = selection.get("language") or plan.get("language") or "hi"
    duration = float(selection.get("duration_seconds") or plan.get("duration_seconds") or 14)
    places = _place_rows(subjects, orientations, stages)
    has_point = any(card.get("representation") == "point" for card in subjects)
    accepted = dict(plan)
    accepted["places"] = places
    accepted["shots"] = _shots(stages, places, duration, language, has_point)
    accepted["hierarchy"] = report
    accepted = dedupe_labels(accepted)
    job_settings = {
        "opening_override": selection.get("opening_override"),
        "opening_policy_override": selection.get("opening_policy_override"),
        "presentation_settings": selection.get("presentation_settings"),
    }
    accepted = normalize_semantic_opening(
        accepted,
        language=language,
        job_settings=job_settings,
    )
    accepted = dedupe_labels(accepted)
    accepted["style"] = style
    accepted["target_focus_count"] = int(selection["target_focus_count"])
    accepted["narration_unit_count"] = int(selection["narration_unit_count"])
    accepted["counting_method"] = selection.get("counting_method") or "sentences"
    accepted["focus_decision"] = selection.get("focus_decision")
    chosen = theme or theme_for(style)
    if applies_palette(chosen):
        apply_palette(accepted, style, chosen)
    from .schema import validate_semantic_plan
    validate_semantic_plan(
        accepted,
        duration_seconds=float(selection["duration_seconds"]),
        enforce_beats=True,
    )
    return accepted


def apply_palette(plan: dict, style: str | None = None, theme: dict | None = None) -> dict:
    """Assign semantic highlight roles. The same place keeps one role for the clip."""
    chosen = theme or theme_for(style or plan.get("style") or "documentary_relief_bold")
    if not applies_palette(chosen):
        return plan
    roles = palette_roles(chosen)
    levels = {place["id"]: place.get("level") for place in plan.get("places") or []}
    assigned: dict[str, dict] = {}
    cursor = 0

    def role_for(place_id: str) -> dict:
        nonlocal cursor
        if place_id not in assigned:
            if levels.get(place_id) == "country":
                assigned[place_id] = roles["country"]
            else:
                assigned[place_id] = roles["focus"][cursor % len(roles["focus"])]
                cursor += 1
        return assigned[place_id]

    for shot in plan.get("shots") or []:
        for action in shot.get("actions") or []:
            place_id = action.get("place")
            if not place_id:
                continue
            role = role_for(place_id)
            if action.get("color_source") == "user":
                continue
            if action.get("type") == "highlight":
                action["color"] = role["color"]
                action["fill_opacity"] = role["fill_opacity"]
            elif action.get("type") == "show_marker":
                if role["marker"]:
                    action["color"] = role["marker"]
                action["pulse"] = bool((chosen.get("marker") or {}).get("pulse"))
    return plan


def build_focus_plan(
    cards: list[dict],
    *,
    language: str,
    style: str,
    target_focus_count: int,
    narration_unit_count: int,
    counting_method: str,
    focus_decision: str,
    duration_seconds: float | None = None,
) -> dict:
    """One visual stage per shot. Do not invent a place to fill the target."""
    subjects = [card for card in cards if card.get("role") != "orientation"]
    orientations = [card for card in cards if card.get("role") == "orientation"]
    if not subjects and not orientations:
        raise ValueError("A map plan needs at least one resolved place")
    target = int(target_focus_count)
    duration = float(duration_seconds or duration_for_focuses(target))
    from .hierarchy import allocate_focus_stages, dedupe_labels

    stages, hierarchy = allocate_focus_stages(subjects, orientations, target)
    if len(stages) != target:
        focus_decision = f"{focus_decision};stages_{len(stages)}_without_invented_places"
    places = _place_rows(subjects, orientations, stages)
    shots = _shots(stages, places, duration, language, any(card.get("representation") == "point" for card in subjects))
    plan = {
        "schema_version": "1.0",
        "type": "map_focus_sequence",
        "duration_seconds": duration,
        "language": language,
        "style": style,
        "ambiguity": [],
        "narration_unit_count": narration_unit_count,
        "target_focus_count": target,
        "counting_method": counting_method,
        "focus_decision": focus_decision,
        "hierarchy": hierarchy,
        "places": places,
        "shots": shots,
    }
    plan = dedupe_labels(plan)
    plan["qa_frames"] = [
        {
            "t": round((shot["start"] + shot["end"]) / 2.0, 3),
            "name": shot["id"],
        }
        for shot in shots
    ]
    if applies_palette(theme_for(style)):
        apply_palette(plan, style)
    from .opening import normalize_semantic_opening

    plan = normalize_semantic_opening(plan, language=language, job_settings=None)
    plan = dedupe_labels(plan)
    validate_semantic_plan(plan, duration_seconds=duration, enforce_beats=True)
    found = meaningful_beat_count(plan)
    if found != target and found != len(stages):
        raise ValueError(f"Compiled {found} focus stages; target was {target}")
    return plan


def _place_rows(subjects: list[dict], orientations: list[dict], stages: list[tuple[str, dict | None]]) -> list[dict]:
    used = []
    seen = set()
    for _kind, card in stages:
        if card and card["id"] not in seen:
            used.append(card)
            seen.add(card["id"])
    for card in list(orientations) + list(subjects):
        parent = card.get("parent_id") or card.get("parent")
        if parent and parent not in seen:
            source = next((item for item in orientations + subjects if item["id"] == parent), None)
            if source:
                used.append(source)
                seen.add(parent)
    rows = []
    for card in used:
        parent = card.get("parent_id") or card.get("parent")
        if parent not in seen:
            parent = None
        rows.append({
            "id": card["id"],
            "name": card["name"],
            "level": card["level"],
            "parent": parent,
            "role": "orientation" if card.get("role") == "orientation" and card not in subjects else card.get("role") or "subject",
        })
    # Parents must appear before children for the schema's single pass.
    rows.sort(key=lambda row: LEVEL_ORDER.get(row["level"], 9))
    return rows


def _shots(stages: list[tuple[str, dict | None]], places: list[dict], duration: float, language: str, has_point: bool) -> list[dict]:
    weights = []
    for index, (kind, _card) in enumerate(stages):
        weights.append(3.2 if index == 0 and kind in {"overview", "world"} else 1.0)
    slot = max(0.1, (duration - weights[0]) / max(1, sum(weights[1:]) or 1))
    shots = []
    cursor = 0.0
    named = {place["id"] for place in places}
    for index, (kind, card) in enumerate(stages):
        start = round(cursor, 3)
        if index == len(stages) - 1:
            end = float(duration)
        elif index == 0 and kind in {"overview", "world"}:
            end = round(min(duration, weights[0]), 3)
        else:
            end = round(min(duration, cursor + slot), 3)
        cursor = end
        frame = "world" if card is None else card["id"]
        if frame != "world" and frame not in named:
            frame = "world"
        actions = _actions(kind, card, language, index == len(stages) - 1, has_point)
        shots.append({
            "id": f"focus_{index + 1}",
            "start": start,
            "end": end,
            "frame": frame if frame == "world" or frame in named else places[0]["id"],
            "actions": actions,
        })
    shots[-1]["end"] = float(duration)
    return shots


def _actions(kind: str, card: dict | None, language: str, final: bool, has_point: bool) -> list[dict]:
    if kind == "world" or card is None:
        return [{"type": "establish_view", "scope": "countries"}]
    place_id = card["id"]
    point = card.get("representation") == "point"
    text = _label(card, language)
    if kind == "overview":
        return [
            {"type": "zoom_to_boundary", "place": place_id, "padding": 0.10, "motion": "hold"},
            {"type": "highlight", "place": place_id, "color": "#A32320", "fill_opacity": 0.72, "from_offset": 0.8},
            {"type": "show_label", "place": place_id, "text": text, "from_offset": 1.6, "rest_opacity": 0},
        ]
    if kind == "label":
        actions: list[dict] = [{"type": "hold"}]
        actions.extend(_name_actions(card, text, final, point))
        return actions
    padding = 0.18 if kind == "closer" else 0.16
    actions = [{"type": "zoom_to_boundary", "place": place_id, "padding": padding}]
    if point:
        actions.extend(_name_actions(card, text, final, True))
    else:
        actions.append({
            "type": "highlight",
            "place": place_id,
            "color": "#D4B300",
            "fill_opacity": 0.34,
            "parent_context": "subdued",
        })
        offset_y = -110 if has_point and card.get("level") in {"state", "district"} else 0
        actions.append({
            "type": "show_label",
            "place": place_id,
            "text": text,
            "hold_focus": final,
            "offset_y": offset_y,
        })
    return actions


def _name_actions(card: dict, text: str, final: bool, point: bool) -> list[dict]:
    actions = []
    if point:
        actions.append({
            "type": "show_marker",
            "place": card["id"],
            "color": "#FFF400",
            "size": 8,
            "pulse": False,
        })
        actions.append({
            "type": "show_label",
            "place": card["id"],
            "text": text,
            "hold_focus": final,
            "offset_y": -40,
        })
    else:
        actions.append({
            "type": "show_label",
            "place": card["id"],
            "text": text,
            "hold_focus": final,
        })
    return actions


def _label(card: dict, language: str) -> str:
    aliases = [alias for alias in card.get("aliases") or [] if isinstance(alias, str)]
    if language.lower().startswith("hi"):
        for alias in aliases:
            if any("\u0900" <= char <= "\u097F" for char in alias):
                return alias
    return card.get("name") or aliases[0]
