"""Country-centered opening policy for map focus sequences."""
from __future__ import annotations

from typing import Any

OPENING_POLICY_ID = "country_centered"
DEFAULT_COUNTRY_PADDING = 0.10
PRESENTATION_VERSION = "2026.03-country-opening-v1"
COMPOSITION_VERSION = "1.2"
# Zoom below this with a country policy usually means an accidental world frame.
COUNTRY_OPENING_MIN_ZOOM = 2.2
WORLD_REFERENCE_CENTER = (20.0, 20.0)
WORLD_REFERENCE_ZOOM = 1.35

JOINT_MAX_LON_SPAN_DEG = 28.0
JOINT_MAX_LAT_SPAN_DEG = 22.0

TRUSTED_WORLD_VALUES = frozenset({"world", "world_overview", "global", "planet"})


def job_settings_from_snapshot(snapshot: dict | None) -> dict:
    if not snapshot:
        return {}
    return {
        "opening_override": snapshot.get("opening_override"),
        "opening_policy_override": snapshot.get("opening_policy_override"),
        "presentation_settings": snapshot.get("presentation_settings"),
        "presentation_version": snapshot.get("presentation_version"),
        "opening_policy_default": snapshot.get("opening_policy_default"),
    }


def trusted_world_opening_requested(job_settings: dict | None) -> bool:
    """Only explicit job / user settings authorize a world opening — not model scope fields."""
    settings = job_settings or {}
    for key in ("opening_override", "opening_policy_override"):
        token = str(settings.get(key) or "").lower()
        if token in TRUSTED_WORLD_VALUES:
            return True
    prefs = settings.get("presentation_settings")
    if isinstance(prefs, dict):
        token = str(prefs.get("opening") or "").lower()
        if token in TRUSTED_WORLD_VALUES:
            return True
    return False


def explicit_world_overview_requested(shot: dict, job_settings: dict | None = None) -> bool:
    """Backward-compatible alias; world openings require trusted job settings."""
    return trusted_world_opening_requested(job_settings)


def _places_index(plan: dict) -> dict[str, dict]:
    return {str(p["id"]): p for p in plan.get("places") or [] if p.get("id")}


def _walk_to_country(place_id: str, places: dict[str, dict]) -> str | None:
    seen: set[str] = set()
    current = place_id
    while current and current not in seen:
        seen.add(current)
        row = places.get(current)
        if not row:
            return None
        if row.get("level") == "country":
            return current
        current = row.get("parent") or row.get("parent_id")
    return None


def resolve_primary_country_id(plan: dict) -> tuple[str | None, str]:
    """Pick the opening country from verified plan geography (not language)."""
    places = _places_index(plan)
    if not places:
        return None, "no_places"

    countries = [pid for pid, row in places.items() if row.get("level") == "country"]
    subjects = [row for row in places.values() if row.get("role") not in ("orientation",)]

    for shot in plan.get("shots") or []:
        frame = shot.get("frame")
        if frame and frame != "world" and frame in places:
            cid = _walk_to_country(str(frame), places)
            if cid:
                return cid, "first_shot_focus_parent_country"
        for action in shot.get("actions") or []:
            pid = action.get("place")
            if pid and str(pid) in places:
                cid = _walk_to_country(str(pid), places)
                if cid:
                    return cid, "first_country_action_in_timeline"

    if len(countries) == 1:
        return countries[0], "sole_verified_country"

    if subjects:
        ordered = sorted(
            subjects,
            key=lambda row: {"country": 0, "state": 1, "district": 2, "city": 3, "region": 4}.get(
                str(row.get("level")), 9
            ),
        )
        for row in ordered:
            if row.get("level") == "country":
                return str(row["id"]), "first_narrative_country_subject"
            cid = _walk_to_country(str(row["id"]), places)
            if cid:
                return cid, "first_narrative_subject_parent_country"

    if countries:
        return countries[0], "first_country_row_fallback"

    return None, "no_verified_country"


def _overview_actions(country_id: str, label_text: str | None = None) -> list[dict]:
    return [
        {"type": "zoom_to_boundary", "place": country_id, "padding": DEFAULT_COUNTRY_PADDING, "motion": "hold"},
        {
            "type": "highlight",
            "place": country_id,
            "color": "#A32320",
            "fill_opacity": 0.72,
            "from_offset": 0.8,
        },
        {
            "type": "show_label",
            "place": country_id,
            "text": label_text or country_id,
            "from_offset": 1.6,
            "rest_opacity": 0,
        },
    ]


def normalize_semantic_opening(
    plan: dict,
    *,
    language: str | None = None,
    job_settings: dict | None = None,
) -> dict:
    """Replace generic or model-proposed world openings with country-centered framing."""
    accepted = dict(plan)
    shots = [dict(s) for s in accepted.get("shots") or []]
    if not shots:
        accepted["opening_policy"] = {"mode": "unchanged", "reason": "no_shots"}
        return accepted

    primary_id, reason = resolve_primary_country_id(accepted)
    first = dict(shots[0])
    first_actions = [dict(a) for a in first.get("actions") or []]

    if trusted_world_opening_requested(job_settings):
        accepted["opening_policy"] = {
            "mode": "world_overview",
            "primary_country_id": primary_id,
            "selection_reason": reason,
            "override": "trusted_job_setting",
        }
        accepted["presentation_version"] = PRESENTATION_VERSION
        return accepted

    if not primary_id:
        accepted["opening_policy"] = {"mode": "unchanged", "reason": reason}
        accepted["presentation_version"] = PRESENTATION_VERSION
        return accepted

    places = _places_index(accepted)
    country_row = places.get(primary_id) or {}
    label = country_row.get("name") or primary_id
    lang = (language or accepted.get("language") or "hi").lower()
    if lang.startswith("hi"):
        for alias in country_row.get("aliases") or []:
            if isinstance(alias, str) and any("\u0900" <= ch <= "\u097F" for ch in alias):
                label = alias
                break

    model_world = first.get("frame") == "world" or any(
        a.get("type") == "establish_view" for a in first_actions
    )
    # Only generic world / establish_view openings are rewritten.
    # A verified geographic first stage from the hierarchy planner stays as allocated.
    if model_world:
        first["frame"] = primary_id
        if first.get("id") in (None, "world", "world_overview"):
            first["id"] = "focus_1"
        first["actions"] = _overview_actions(primary_id, label)

    shots[0] = first
    accepted["shots"] = shots
    accepted["opening_policy"] = {
        "mode": OPENING_POLICY_ID,
        "primary_country_id": primary_id,
        "selection_reason": reason,
        "padding": DEFAULT_COUNTRY_PADDING,
        "normalized_from_model_world": bool(model_world),
        "presentation_version": PRESENTATION_VERSION,
    }
    accepted["presentation_version"] = PRESENTATION_VERSION
    return accepted


def joint_country_opening_ids(
    plan: dict,
    resolved_places: dict[str, dict],
    *,
    primary_id: str | None,
) -> list[str] | None:
    """Nearby multi-country comparison: union fit when geography stays regional."""
    if not primary_id:
        return None
    places = _places_index(plan)
    country_ids = [pid for pid, row in places.items() if row.get("level") == "country"]
    if len(country_ids) < 2:
        return None
    boxes = []
    for cid in country_ids:
        place = resolved_places.get(cid)
        if place and place.get("bbox"):
            boxes.append(place["bbox"])
    if len(boxes) < 2:
        return None

    west = min(b[0] for b in boxes)
    south = min(b[1] for b in boxes)
    east = max(b[2] for b in boxes)
    north = max(b[3] for b in boxes)
    lon_span = east - west
    if lon_span < 0:
        lon_span += 360.0
    if lon_span > 180.0:
        lon_span = 360.0 - lon_span
    lat_span = north - south
    if lon_span > JOINT_MAX_LON_SPAN_DEG or lat_span > JOINT_MAX_LAT_SPAN_DEG:
        return None
    return country_ids


def opening_policy_record(
    plan: dict,
    resolved_places: dict[str, dict],
    *,
    width: int,
    height: int,
    engine_hint: str,
    first_camera: dict | None,
    job_settings: dict | None = None,
) -> dict[str, Any]:
    primary_id, reason = resolve_primary_country_id(plan)
    stored = plan.get("opening_policy") if isinstance(plan.get("opening_policy"), dict) else {}
    trusted_world = trusted_world_opening_requested(job_settings)
    mode = "world_overview" if trusted_world else stored.get("mode") or OPENING_POLICY_ID
    joint = joint_country_opening_ids(plan, resolved_places, primary_id=primary_id)
    record: dict[str, Any] = {
        "policy": OPENING_POLICY_ID if mode != "world_overview" else "world_overview",
        "primary_country_id": primary_id or stored.get("primary_country_id"),
        "selection_reason": stored.get("selection_reason") or reason,
        "joint_country_ids": joint,
        "padding": DEFAULT_COUNTRY_PADDING,
        "viewport": {"width": width, "height": height},
        "engine": engine_hint,
        "presentation_version": PRESENTATION_VERSION,
    }
    if first_camera:
        record["effective_camera"] = {
            "center": [round(first_camera["center"][0], 6), round(first_camera["center"][1], 6)],
            "zoom": round(float(first_camera["zoom"]), 5),
            "pitch": round(float(first_camera.get("pitch", 0.0)), 3),
            "bearing": round(float(first_camera.get("bearing", 0.0)), 3),
        }
    limitations: list[str] = []
    if primary_id:
        place = resolved_places.get(primary_id)
        if place and place.get("bbox"):
            west, south, east, north = place["bbox"]
            if (east - west) > 50 or (north - south) > 40:
                limitations.append("primary_country_bbox_is_very_large")
    if not primary_id:
        limitations.append("no_primary_country_for_opening")
    if limitations:
        record["framing_limitations"] = limitations
    return record


def resolved_plan_needs_recompile(resolved_path, expected_version: str = PRESENTATION_VERSION) -> bool:
    from pathlib import Path

    path = Path(resolved_path)
    if not path.is_file():
        return True
    try:
        import json

        resolved = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    if resolved.get("presentation_version") != expected_version:
        return True
    opening = (resolved.get("composition") or {}).get("opening") or {}
    if opening.get("presentation_version") != expected_version:
        return True
    if opening.get("policy") not in (OPENING_POLICY_ID, "world_overview"):
        return True
    kfs = (resolved.get("camera") or {}).get("keyframes") or []
    if not kfs:
        return True
    if trusted_world_opening_requested({}):
        return False
    return not country_centered_camera(kfs[0])


def country_centered_camera(camera: dict) -> bool:
    zoom = float(camera.get("zoom", 0))
    if zoom < COUNTRY_OPENING_MIN_ZOOM:
        return False
    center = camera.get("center") or [0, 0]
    if (
        abs(float(center[0]) - WORLD_REFERENCE_CENTER[0]) < 8.0
        and abs(float(center[1]) - WORLD_REFERENCE_CENTER[1]) < 8.0
        and zoom <= WORLD_REFERENCE_ZOOM + 0.05
    ):
        return False
    return True


def validate_country_centered_opening(
    resolved: dict,
    *,
    job_settings: dict | None = None,
) -> None:
    """Fail compilation when country-centered policy did not reach the first camera."""
    if trusted_world_opening_requested(job_settings):
        return
    opening = (resolved.get("composition") or {}).get("opening") or {}
    if opening.get("policy") == "world_overview":
        return
    kfs = (resolved.get("camera") or {}).get("keyframes") or []
    if not kfs:
        raise ValueError("Resolved plan has no camera keyframes")
    first = kfs[0]
    if not country_centered_camera(first):
        raise ValueError(
            "Opening camera is still world-scale after country-centered policy "
            f"(center={first.get('center')}, zoom={first.get('zoom')})"
        )
