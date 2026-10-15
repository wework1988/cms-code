"""Manual location choices for one animation job.

Catalogue geometry is loaded again from the catalogue at resolve time.
Coordinates posted for a catalogue selection are ignored.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .geo import normalize_name

OVERRIDE_FILE = "location-overrides.json"


def request_fingerprint(request: dict, passage: str) -> str:
    material = {
        "name": normalize_name(str(request.get("name") or "")),
        "level": request.get("level") or "",
        "parent": normalize_name(str(request.get("parent_name") or "")),
        "country": normalize_name(str(request.get("country") or "")),
        "state": normalize_name(str(request.get("state") or "")),
        "district": normalize_name(str(request.get("district") or "")),
        "passage": hashlib.sha256((passage or "").encode("utf-8")).hexdigest(),
    }
    encoded = json.dumps(material, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def load_overrides(path: Path) -> dict:
    if not path.is_file():
        return {"revision": 0, "overrides": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {"revision": 0, "overrides": []}
    rows = payload.get("overrides") if isinstance(payload.get("overrides"), list) else []
    return {"revision": int(payload.get("revision") or 0), "overrides": rows}


def clip_override_revision(overrides: list[dict], clip_id: str) -> int:
    revisions = [int(item.get("revision") or 0) for item in overrides if item.get("clip_id") == clip_id]
    return max(revisions) if revisions else 0


def should_preserve_completed(clip: dict, revision: int) -> bool:
    """A finished clip stays unless a newer mapping targets it."""
    video = clip.get("video")
    if clip.get("status") != "completed" or not video or not Path(video).is_file():
        return False
    return revision <= int(clip.get("override_revision") or 0)


def publish_still_current(started_revision: int, current_revision: int) -> bool:
    return int(current_revision) == int(started_revision)


def acquire_clip_lock(path: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            pid = int(path.read_text(encoding="utf-8").strip())
            os.kill(pid, 0)
            return False
        except (OSError, ValueError):
            pass
    path.write_text(str(os.getpid()), encoding="utf-8")
    return True


def release_clip_lock(path: Path) -> None:
    try:
        if path.is_file() and path.read_text(encoding="utf-8").strip() == str(os.getpid()):
            path.unlink()
    except OSError:
        return


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _feature_error(name: str, level: str | None, selected_level: str, type_correction: bool) -> str | None:
    from .identity import ADMIN_LEVELS, UNSUPPORTED_KINDS, requested_kind

    kind = requested_kind(name, level)
    if kind in UNSUPPORTED_KINDS:
        return f"Requested feature type '{kind}' cannot be mapped to a catalogue {selected_level}."
    if kind in ADMIN_LEVELS and selected_level != kind and not type_correction:
        return (
            f"Selected {selected_level} does not match the requested {kind}. "
            "Confirm a type correction to use this record."
        )
    return None


def validate_catalogue_selection(
    conn: sqlite3.Connection,
    *,
    place_id: str,
    requested_name: str,
    requested_level: str | None,
    type_correction: bool = False,
    expected_country_code: str | None = None,
) -> dict:
    from .catalog import _aliases_for, _row_to_summary

    row = conn.execute("SELECT * FROM place WHERE id=? AND active=1", (place_id,)).fetchone()
    if not row:
        raise ValueError(f"Catalogue place '{place_id}' was not found.")
    geometry = conn.execute("SELECT geojson FROM geometry WHERE place_id=?", (place_id,)).fetchone()
    if not geometry or not geometry["geojson"]:
        raise ValueError(f"Catalogue place '{place_id}' has no usable geometry.")
    payload = json.loads(geometry["geojson"])
    if payload.get("type") not in {"Point", "Polygon", "MultiPolygon"}:
        raise ValueError(f"Catalogue place '{place_id}' has geometry that cannot be drawn.")
    error = _feature_error(requested_name, requested_level, row["level"], type_correction)
    if error:
        raise ValueError(error)
    if expected_country_code and row["country_code"] not in {None, expected_country_code}:
        raise ValueError(
            f"Selected place is in {row['country_code']}, not the verified country {expected_country_code}."
        )
    summary = _row_to_summary(row, _aliases_for(conn, row["id"]))
    summary["geometry_type"] = payload.get("type")
    return summary


def validate_custom_point(*, name: str, latitude: float, longitude: float) -> dict:
    label = str(name or "").strip()
    if len(label) < 2:
        raise ValueError("A custom point needs a display name.")
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError) as error:
        raise ValueError("Latitude and longitude must be numbers.") from error
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("Latitude must be between -90 and 90 and longitude between -180 and 180.")
    return {
        "type": "Point",
        "coordinates": [lon, lat],
    }


def user_point_id(job_id: str, request_id: str) -> str:
    digest = hashlib.sha256(f"{job_id}:{request_id}".encode("utf-8")).hexdigest()[:16]
    return f"user-point-{digest}"


def apply_manual_override(conn: sqlite3.Connection, result: dict, override: dict) -> dict:
    """Replace a resolution with a validated manual choice. Hierarchy comes from the catalogue."""
    source = override.get("source")
    requested = result.get("requested") or {}
    if source == "manual_catalogue_selection":
        context = result.get("context") or {}
        expected_country = context.get("country_code") if (context.get("verified") or {}).get("country") else None
        place = validate_catalogue_selection(
            conn,
            place_id=str(override.get("place_id") or ""),
            requested_name=str(requested.get("name") or override.get("original_name") or ""),
            requested_level=requested.get("level") if isinstance(requested.get("level"), str) else override.get("original_level"),
            type_correction=bool(override.get("type_correction")),
            expected_country_code=expected_country,
        )
        return {
            "status": "resolved",
            "reason": f"Manual catalogue selection {place['name']} ({place['id']}).",
            "query": result.get("query") or {},
            "place": place,
            "candidates": [],
            "requested": requested,
            "context": result.get("context") or {},
            "local_status": result.get("local_status") or result.get("status"),
            "match_method": "manual_catalogue_selection",
            "fallback": {
                "attempted": False,
                "skipped_reason": "manual_override",
                "reason": "Manual catalogue selection",
                "candidate_ids": [],
                "error_kind": None,
            },
        }
    if source == "manual_custom_point":
        geometry = validate_custom_point(
            name=str(override.get("display_name") or ""),
            latitude=override.get("latitude"),
            longitude=override.get("longitude"),
        )
        point_id = str(override.get("place_id") or "")
        if not point_id.startswith("user-point-"):
            raise ValueError("A custom point id must be a user-point id.")
        place = {
            "id": point_id,
            "name": str(override.get("display_name") or "").strip(),
            "level": "city",
            "feature_type": "user_provided_point",
            "representation": "point",
            "geometry_kind": "point",
            "source": "user_provided",
            "country_code": None,
            "parent_id": None,
            "state_name": None,
            "state_place_id": None,
            "district_name": None,
            "aliases": [],
            "user_geometry": geometry,
            "stated_admin_id": override.get("stated_admin_id") or None,
            "spatial_membership_verified": False,
            "note": "Manually supplied point. No boundary was created.",
        }
        return {
            "status": "resolved",
            "reason": "Manually supplied point. No city, district, or state boundary was created.",
            "query": result.get("query") or {},
            "place": place,
            "candidates": [],
            "requested": requested,
            "context": result.get("context") or {},
            "local_status": result.get("local_status") or result.get("status"),
            "match_method": "manual_custom_point",
            "fallback": {
                "attempted": False,
                "skipped_reason": "manual_custom_point",
                "reason": "Manually supplied point",
                "candidate_ids": [],
                "error_kind": None,
            },
        }
    raise ValueError("Unknown manual location source.")


def user_point_extras(results: list[dict]) -> dict[str, dict]:
    extras = {}
    for result in results:
        place = result.get("place") or {}
        geometry = place.get("user_geometry")
        if place.get("source") != "user_provided" or not geometry:
            continue
        extras[place["id"]] = {
            "id": place["id"],
            "name": place.get("name"),
            "level": place.get("level") or "city",
            "geometry": geometry,
            "stated_admin_id": place.get("stated_admin_id"),
        }
    return extras


def selection_requests(selection: dict) -> dict[str, dict]:
    found = {}
    for clip in selection.get("clips") or []:
        if not isinstance(clip, dict):
            continue
        raw = clip.get("place_requests")
        if not isinstance(raw, list) or not raw:
            raw = []
            for place in clip.get("places") or []:
                if isinstance(place, dict) and place.get("name"):
                    raw.append(place)
        passage = clip.get("source_passage") or ""
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                continue
            request_id = item.get("request_id") or f"{clip.get('id')}:{index}"
            request = {
                "name": item.get("name"),
                "level": item.get("level"),
                "parent_name": item.get("parent_name"),
                "country": item.get("country"),
                "state": item.get("state"),
                "district": item.get("district"),
                "request_id": request_id,
            }
            request["fingerprint"] = request_fingerprint(request, passage)
            request["clip_id"] = clip.get("id")
            request["passage"] = passage
            found[request_id] = request
    return found


def _same_choice(existing: dict, incoming: dict) -> bool:
    keys = ("place_id", "source", "fingerprint", "display_name", "type_correction")
    return all(existing.get(key) == incoming.get(key) for key in keys)


def save_override_document(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
