"""Stage A: choose map-animation passages from a full script snapshot."""
from __future__ import annotations

import json
import re
from typing import Any

from .geo import load_registry, normalize_name
from .narration import count_narration_units, duration_for_focuses, sentence_spans
from .schema import MEANINGFUL_ACTIONS, PlanValidationError, meaningful_beat_count, validate_semantic_plan
from .sequence import build_focus_plan

MAX_CLIPS = 3


class SelectionError(ValueError):
    pass


def require(ok: bool, message: str) -> None:
    if not ok:
        raise SelectionError(message)


def coverage_summary(registry: dict | None = None) -> list[dict]:
    reg = registry or load_registry()
    return [
        {
            "id": entry["id"],
            "name": entry["name"],
            "level": entry["level"],
            "parent": entry.get("parent"),
            "aliases": entry.get("aliases", []),
        }
        for entry in reg["places"].values()
    ]


def validate_selection_document(doc: dict, script: str, *, max_clips: int) -> dict:
    require(isinstance(doc, dict), "Selection must be an object")
    require(doc.get("schema_version") == "1.0", "selection schema_version must be 1.0")
    clips = doc.get("clips")
    require(isinstance(clips, list), "clips must be a list")
    require(len(clips) <= max_clips, f"Selection has {len(clips)} clips; maximum is {max_clips}")
    if not clips:
        require(isinstance(doc.get("explanation"), str) and doc["explanation"].strip(),
                "Empty selections need an explanation")
        return doc

    ids = set()
    for clip in clips:
        require(isinstance(clip, dict), "Each clip must be an object")
        cid = clip.get("id")
        require(isinstance(cid, str) and re.fullmatch(r"clip_\d{2}", cid),
                f"Clip id must look like clip_01, got {cid!r}")
        require(cid not in ids, f"Duplicate selection id {cid}")
        ids.add(cid)
        require(clip.get("animation_type") == "map", "Only map animations are supported")
        passage = clip.get("source_passage")
        require(isinstance(passage, str) and passage.strip(), "source_passage required")
        require(passage in script, "source_passage must be an exact contiguous copy of the script snapshot")
        start = script.find(passage)
        require(clip.get("offset_start") == start, "offset_start does not match the script snapshot")
        require(clip.get("offset_end") == start + len(passage), "offset_end does not match the script snapshot")
        require(isinstance(clip.get("reason"), str) and clip["reason"].strip(), "reason required")
        require(isinstance(clip.get("title"), str) and clip["title"].strip(), "title required")
        duration = clip.get("duration_seconds")
        require(isinstance(duration, (int, float)) and 6 <= float(duration) <= 30, "duration_seconds must be 6–30")
        requests = clip.get("place_requests")
        places = clip.get("places")
        if isinstance(requests, list) and requests:
            for request in requests:
                require(isinstance(request, dict), "Each place request must be an object")
                require(isinstance(request.get("name"), str) and request["name"].strip(), "place request name required")
                for banned in ("coordinates", "geometry", "bbox", "polygon", "lon", "lat", "zoom"):
                    require(banned not in request, f"Place request must not include '{banned}'")
        else:
            require(isinstance(places, list) and places, "place_requests or places required")
        beats = clip.get("beats")
        target = clip.get("target_focus_count")
        if target is not None:
            require(target in (3, 4), "target_focus_count must be 3 or 4")
            require(isinstance(clip.get("narration_unit_count"), int), "narration_unit_count required")
            require(clip.get("counting_method") in {"sentences", "scene_lines"}, "counting_method required")
            clip["beats"] = _advisory_beats(beats)
        else:
            require(isinstance(beats, list) and 3 <= len(beats) <= 4, "Each clip needs 3–4 focus beats")
            normalized_beats = []
            for beat in beats:
                if isinstance(beat, str) and beat.strip():
                    beat = {"purpose": beat.strip()}
                require(isinstance(beat, dict), "Each beat needs a purpose")
                purpose = beat.get("purpose") or beat.get("description") or beat.get("text") or beat.get("focus")
                require(isinstance(purpose, str) and purpose.strip(), "Each beat needs a purpose")
                beat["purpose"] = purpose.strip()
                if beat.get("action") is not None:
                    require(beat.get("action") in MEANINGFUL_ACTIONS, f"Unsupported beat action {beat.get('action')}")
                normalized_beats.append(beat)
            clip["beats"] = normalized_beats
        # Narration times must not be invented.
        require(clip.get("narration_start") in (None,), "Do not invent narration timestamps")
        require(clip.get("narration_end") in (None,), "Do not invent narration timestamps")
    return doc


def first_clips(doc: dict, script: str, *, max_clips: int = MAX_CLIPS) -> dict:
    """Keep the earliest passages in script order, never more than max_clips."""
    limit = min(max_clips, MAX_CLIPS)
    clips = sorted(doc.get("clips") or [], key=lambda clip: int(clip.get("offset_start") or 0))
    doc = {**doc, "clips": clips[:limit]}
    return validate_selection_document(doc, script, max_clips=limit)


def heuristic_select(script: str, *, max_clips: int = MAX_CLIPS, duration_seconds: float = 18, language: str = "hi") -> dict:
    """Deterministic selector for tests and offline coverage checks. Not a model."""
    registry = load_registry()
    # Walk the script from the top and take the first suitable passages.
    chunks = [c.strip() for c in re.split(r"\n\s*\n", script) if c.strip()] or [script.strip()]
    ordered = []
    for chunk in chunks:
        norm = normalize_name(chunk)
        hits = []
        for entry in registry["places"].values():
            names = [entry["name"], *entry.get("aliases", [])]
            if any(normalize_name(n) and normalize_name(n) in norm for n in names):
                hits.append(entry)
        if len(hits) >= 2:
            ordered.append((chunk, hits))
    clips = []
    limit = min(max_clips, MAX_CLIPS)
    for chunk, hits in ordered:
        if len(clips) >= limit:
            break
        start = script.find(chunk)
        # Stable parent-before-child order.
        order = {"country": 0, "state": 1, "district": 2, "city": 3, "region": 4}
        hits = sorted(hits, key=lambda e: order.get(e["level"], 9))
        ids = {h["id"] for h in hits}
        hits = [h for h in hits if not h.get("parent") or h["parent"] in ids]
        if len(hits) < 2:
            continue
        focus = hits[-1]
        counted = count_narration_units(chunk)
        clips.append({
            "id": f"clip_{len(clips) + 1:02d}",
            "animation_type": "map",
            "title": focus["name"],
            "source_passage": chunk,
            "offset_start": start,
            "offset_end": start + len(chunk),
            "reason": "The passage names a place chain that a map can show more clearly than narration alone.",
            "language": language,
            "duration_seconds": duration_for_focuses(counted["target"]),
            "narration_unit_count": counted["count"],
            "target_focus_count": counted["target"],
            "counting_method": counted["method"],
            "focus_decision": counted["decision"],
            "places": [
                {"id": h["id"], "name": h["name"], "level": h["level"], "parent": h.get("parent")}
                for h in hits
            ],
            "beats": _purpose_beats(counted["target"], [h["name"] for h in hits]),
            "narration_start": None,
            "narration_end": None,
        })
    if not clips:
        return {
            "schema_version": "1.0",
            "clips": [],
            "explanation": "No passage is supported by the installed geographic coverage.",
        }
    doc = {"schema_version": "1.0", "clips": clips, "explanation": None}
    return validate_selection_document(doc, script, max_clips=limit)


def plan_from_selection(
    selection: dict,
    *,
    language: str = "hi",
    style: str = "documentary_relief_bold",
    summaries: list[dict] | None = None,
) -> dict:
    """Build the focus sequence locally from resolved places. No coordinates."""
    if selection.get("review_status"):
        raise SelectionError(selection.get("review_reason") or "This passage needs review before a map is drawn.")
    cards = summaries if summaries else _cards_from_places(selection.get("places") or [])
    counted_target = int(selection.get("target_focus_count") or 3)
    plan = build_focus_plan(
        cards,
        language=language or selection.get("language") or "hi",
        style=style,
        target_focus_count=counted_target,
        narration_unit_count=int(selection.get("narration_unit_count") or counted_target),
        counting_method=selection.get("counting_method") or "sentences",
        focus_decision=selection.get("focus_decision") or "selection",
        duration_seconds=float(selection["duration_seconds"]),
    )
    if meaningful_beat_count(plan) != counted_target and meaningful_beat_count(plan) != len(plan["shots"]):
        raise PlanValidationError("Compiled plan did not keep the narration focus target")
    return plan


def _cards_from_places(places: list[dict]) -> list[dict]:
    cards = []
    for place in places:
        cards.append({
            "id": place["id"],
            "name": place.get("name"),
            "level": place.get("level"),
            "parent_id": place.get("parent") or place.get("parent_id"),
            "representation": place.get("representation") or ("point" if place.get("level") == "city" else "polygon"),
            "role": place.get("role") or "subject",
            "aliases": place.get("aliases") or [],
            "feature_type": place.get("feature_type"),
            "country_code": place.get("country_code"),
        })
    return cards


def _stated_level(passage: str) -> str | None:
    """Level the passage itself states. City and district together stay unresolved."""
    city = any(cue in passage for cue in ("शहर", "नगर", "राजधानी"))
    district = any(cue in passage for cue in ("जिला", "ज़िला", "जिले"))
    if city and not district:
        return "city"
    if district and not city:
        return "district"
    return None


def _narrow_stated_level(result: dict, passage: str, state_names: set[str]) -> dict:
    """Use an explicit शहर/जिला cue. Do not pick a geometry by population."""
    if result.get("status") != "ambiguous":
        return result
    level = _stated_level(passage)
    if not level:
        return result
    narrowed = [item for item in result.get("candidates") or [] if item.get("level") == level]
    if state_names:
        in_state = [
            item for item in narrowed
            if item.get("state_name") in state_names or item.get("name") in state_names
        ]
        if in_state:
            narrowed = in_state
    if len(narrowed) != 1:
        return result
    chosen = narrowed[0]
    return {
        "status": "resolved",
        "reason": f"{result.get('reason', '')} The passage calls it a {level}.",
        "query": result.get("query"),
        "requested": result.get("requested"),
        "place": chosen,
        "candidates": [],
        "stated_level": level,
    }


def _record_stated_level(requests: list[dict], result: dict) -> None:
    level = result.get("stated_level")
    place = result.get("place") or {}
    requested = (result.get("requested") or {}).get("name")
    if not level or not requested:
        return
    for request in requests:
        if request.get("name") == requested and not request.get("level"):
            request["level"] = level
            if place.get("state_name"):
                request["state"] = place["state_name"]


def _purpose_beats(target: int, names: list[str]) -> list[dict]:
    label = ", ".join(names[:3]) or "the verified places"
    purposes = [
        f"Show the verified geographic context for {label}",
        f"Focus the narrated place in {label}",
        f"Move closer and keep the name readable for {label}",
        f"Hold the final composition for {label}",
    ]
    return [{"purpose": purposes[index]} for index in range(target)]


def selection_prompt(master_prompt: str, coverage: list[dict], max_clips: int, language: str, duration: float) -> str:
    del coverage  # Names are resolved locally after selection. Do not paste the catalogue.
    technical = {
        "animation_type": "map",
        "max_clips": min(max_clips, MAX_CLIPS),
        "order": "earliest suitable passages in script order; return fewer when fewer passages deserve a map",
        "language": language,
        "duration_seconds": duration,
        "focus_policy": (
            "Suggest the meaningful focus stages you see in the passage. "
            "Those beat suggestions are advisory. Local code counts narration units and sets target_focus_count. "
            "A different suggestion count does not reject the passage. "
            "More than 3 narration units must be split into exact contiguous quotations of at most 3 sentences. "
            "Do not invent places."
        ),
        "coverage": (
            "Map a city inside its state, province, or territory. "
            "Rivers, bays, bridges, temples and other landmarks are optional supporting details. "
            "Still request the city and its state when the sentence also names one of those details. "
            "Do not skip a city passage because a river, bay or building is absent from the catalogue."
        ),
        "place_requests": {
            "fields": ["name", "level", "parent_name", "country"],
            "levels": ["country", "state", "district", "city"],
            "do_not_include": ["id", "coordinates", "geometry", "bbox", "catalogue"],
        },
        "output_fields": [
            "id", "animation_type", "title", "source_passage", "offset_start", "offset_end",
            "reason", "place_requests", "beats", "duration_seconds",
        ],
    }
    return (
        master_prompt.strip()
        + "\n\nTechnical constraints (not editable, do not override): return JSON only. "
        + "The clips field must be a JSON list, possibly empty. "
        + "Ignore any earlier instruction that limits geography to a short pre-approved place list. "
        + "Extract place names from the script as place_requests. Do not invent feature ids, coordinates, "
        + "polygons, or timestamps. A local catalogue resolves names after this response. "
        + "Do not refuse a passage only because its places were absent from a coverage list. "
        + "Return at most the configured maximum, using the earliest suitable passages. "
        + "Fewer clips is correct; do not invent extra clips to fill the maximum. "
        + "Clip ids must be clip_01, clip_02, or clip_03. "
        + json.dumps(technical, ensure_ascii=False)
    )


def clip_planning_payload(master_prompt: str, clip: dict, summaries: list[dict], language: str, duration: float) -> dict:
    """Stage B input. Summaries must already exclude geometry and coordinates."""
    return {
        "master_prompt": master_prompt,
        "passage": clip.get("source_passage"),
        "reason": clip.get("reason"),
        "advisory_beats": clip.get("beats"),
        "unavailable_supporting_features": clip.get("omitted_features") or [],
        "places": summaries,
        "duration_seconds": duration,
        "language": language,
        "target_focus_count": clip.get("target_focus_count"),
        "narration_unit_count": clip.get("narration_unit_count"),
        "counting_method": clip.get("counting_method"),
        "style": "documentary_relief_bold",
        "rules": [
            "Selection beats are advisory and do not set the stage count.",
            "Return one map_focus_sequence JSON object with exactly target_focus_count meaningful focus stages.",
            "A shot that zooms, highlights, and labels one place is one stage.",
            "Use only the supplied place ids. Do not invent ids, coordinates, bounding boxes, geometry, or colors.",
            "representation boundary: highlight and zoom_to_boundary.",
            "representation point: show_marker, zoom_to_boundary, and label. Do not invent a city polygon.",
            "Orientation places are verified parents for geographic context, not new story claims or a travel route.",
            "Do not draw route arrows between cities.",
            "Do not invent an extra place to satisfy the focus count. A closer view or a label hold can be its own stage.",
            "Do not draw a river, bay, bridge, temple, or other feature listed in unavailable_supporting_features.",
            "Do not invent geometry for an omitted feature. Map the resolved city inside its state.",
            "When the subject is a city, highlight its state, province, or territory and mark the city point.",
            "Do not highlight a district that merely shares the city name unless the passage is about that district.",
        ],
    }


def select_story(
    script: str,
    *,
    max_clips: int = MAX_CLIPS,
    language: str = "hi",
    catalog_path=None,
    scenes: list | None = None,
) -> dict:
    """Choose map passages from a full story using the local catalogue. Not a model."""
    from .catalog import exact_mentions, resolve_requests

    paragraphs = _paragraphs(script)
    clips = []
    limit = min(max_clips, MAX_CLIPS)
    for paragraph, base in paragraphs:
        mentions = exact_mentions(paragraph, catalog_path=catalog_path)
        if not mentions:
            continue
        pieces = _coherent_pieces(script, paragraph, base, mentions)
        for passage, start in pieces:
            if len(clips) >= limit:
                break
            piece_mentions = exact_mentions(passage, catalog_path=catalog_path)
            if not piece_mentions:
                continue
            requests = [{"name": item["name"], "level": item["level"]} for item in piece_mentions]
            results = resolve_requests(requests, catalog_path=catalog_path)
            resolved_ids = set()
            resolved_state_names: set[str] = set()
            blockers = []
            for result in results:
                place = result.get("place") or {}
                if result.get("status") == "ambiguous":
                    result = _narrow_stated_level(result, passage, resolved_state_names)
                    _record_stated_level(requests, result)
                    place = result.get("place") or {}
                if result.get("status") == "resolved" and place.get("id") in resolved_ids:
                    continue
                if result.get("status") == "ambiguous":
                    already = [
                        candidate.get("id") for candidate in result.get("candidates") or []
                        if candidate.get("id") in resolved_ids
                    ]
                    if len(already) == 1:
                        continue
                    blockers.append(result)
                    continue
                if result.get("status") != "resolved":
                    blockers.append(result)
                    continue
                resolved_ids.add(place["id"])
                if place.get("level") == "state":
                    if place.get("name"):
                        resolved_state_names.add(place["name"])
                    if place.get("state_name"):
                        resolved_state_names.add(place["state_name"])
            resolved = [item for item in results if item.get("status") == "resolved" and (item.get("place") or {}).get("id") in resolved_ids]
            subnational = [item for item in resolved if (item.get("place") or {}).get("level") != "country"]
            if not blockers and not subnational and len(resolved) < 2:
                continue
            counted = count_narration_units(passage, scenes)
            names = [item["name"] for item in piece_mentions]
            clip = {
                "id": f"clip_{len(clips) + 1:02d}",
                "animation_type": "map",
                "title": names[-1],
                "source_passage": passage,
                "offset_start": start,
                "offset_end": start + len(passage),
                "reason": "The passage locates a place, a hierarchy, or several places a map can show together.",
                "language": language,
                "duration_seconds": duration_for_focuses(counted["target"]),
                "narration_unit_count": counted["count"],
                "target_focus_count": counted["target"],
                "counting_method": counted["method"],
                "focus_decision": counted["decision"],
                "place_requests": requests,
                "beats": _purpose_beats(counted["target"], names),
                "narration_start": None,
                "narration_end": None,
            }
            if blockers:
                kind = "ambiguous" if any(item.get("status") == "ambiguous" for item in blockers) else "not_found"
                clip["review_status"] = "needs_location_clarification" if kind == "ambiguous" else "needs_geographic_data"
                clip["review_reason"] = blockers[0].get("reason")
            clips.append(clip)
        if len(clips) >= limit:
            break
    if not clips:
        return {
            "schema_version": "1.0",
            "clips": [],
            "explanation": "No passage is supported by the installed geographic coverage.",
        }
    return validate_selection_document({"schema_version": "1.0", "clips": clips, "explanation": None}, script, max_clips=limit)


def narrow_results(results: list[dict], passage: str) -> list[dict]:
    """Apply a शहर/जिला cue from this passage. Leave other ambiguities unresolved."""
    narrowed = []
    state_names: set[str] = set()
    for result in results:
        current = _narrow_stated_level(result, passage, state_names)
        place = current.get("place") or {}
        if current.get("status") == "resolved" and place.get("level") == "state":
            if place.get("name"):
                state_names.add(place["name"])
            if place.get("state_name"):
                state_names.add(place["state_name"])
        narrowed.append(current)
    return narrowed


def _advisory_beats(beats) -> list:
    """Keep usable stage suggestions. Drop a suggestion with no purpose instead of failing selection."""
    if not isinstance(beats, list):
        return []
    kept = []
    for beat in beats:
        if isinstance(beat, str) and beat.strip():
            beat = {"purpose": beat.strip()}
        if not isinstance(beat, dict):
            continue
        purpose = beat.get("purpose") or beat.get("description") or beat.get("text") or beat.get("focus")
        if not isinstance(purpose, str) or not purpose.strip():
            continue
        if beat.get("action") is not None and beat.get("action") not in MEANINGFUL_ACTIONS:
            continue
        item = dict(beat)
        item["purpose"] = purpose.strip()
        kept.append(item)
    return kept


def finalize_selection(doc: dict, script: str, scenes: list | None = None) -> dict:
    """Count narration units locally. Beat suggestions stay advisory, including a different count."""
    clips = []
    for clip in doc.get("clips") or []:
        passage = clip.get("source_passage") or ""
        counted = count_narration_units(passage, scenes)
        if counted["count"] > 3:
            raise SelectionError(
                "Passage has "
                f"{counted['count']} narration units. Split it into exact contiguous quotations of at most 3 sentences."
            )
        beats = clip.get("beats")
        clip = dict(clip)
        clip["narration_unit_count"] = counted["count"]
        clip["target_focus_count"] = counted["target"]
        clip["counting_method"] = counted["method"]
        clip["focus_decision"] = counted["decision"]
        clip["duration_seconds"] = duration_for_focuses(counted["target"])
        clip["advisory_beat_count"] = len(beats) if isinstance(beats, list) else 0
        clip["beats"] = beats if isinstance(beats, list) else []
        clips.append(clip)
    for index, clip in enumerate(clips, start=1):
        clip["id"] = f"clip_{index:02d}"
    return {"schema_version": "1.0", "clips": clips, "explanation": doc.get("explanation")}


def _paragraphs(script: str) -> list[tuple[str, int]]:
    parts = []
    for match in re.finditer(r"(?:^|\n\s*\n)(.+?)(?=\n\s*\n|\Z)", script, flags=re.S):
        raw = match.group(1)
        text = raw.strip()
        if not text:
            continue
        offset = script.find(text, match.start())
        if offset >= 0:
            parts.append((text, offset))
    if not parts and script.strip():
        text = script.strip()
        parts.append((text, script.find(text)))
    return parts


def _coherent_pieces(script: str, paragraph: str, base: int, mentions: list[dict]) -> list[tuple[str, int]]:
    counted = count_narration_units(paragraph)
    if counted["count"] <= 3:
        return [(paragraph, base)]
    pieces = _slices_from_spans(paragraph, base)
    if len(pieces) <= 1:
        return [(paragraph, base)]
    kept = []
    for passage, start in pieces:
        if any(item["start"] >= (start - base) and item["start"] < (start - base + len(passage)) for item in mentions) or any(
            item["name"] in passage for item in mentions
        ):
            kept.append((passage, start))
    return kept or [(paragraph, base)]


def _slices_from_spans(paragraph: str, base: int) -> list[tuple[str, int]]:
    spans = sentence_spans(paragraph)
    if len(spans) <= 3:
        return []
    groups = []
    index = 0
    while index < len(spans):
        size = 3 if len(spans) - index >= 3 else len(spans) - index
        if size <= 0:
            break
        # Keep a leftover sentence with the previous group only when it would stand alone past the cap.
        if len(spans) - index == 4:
            size = 2
        start, _end = spans[index]
        _start, end = spans[index + size - 1]
        passage = paragraph[start:end].strip()
        offset = base + paragraph.find(passage, start)
        groups.append((passage, offset if offset >= 0 else base + start))
        index += size
    return groups if len(groups) > 1 else []
