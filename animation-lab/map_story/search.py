"""Bounded catalogue search for the CMS. Geometry is loaded only for a preview."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from rapidfuzz import fuzz

from .catalog import (
    FUZZY_CANDIDATE_SCORE,
    _aliases_for,
    _fuzzy_hits,
    _ids_at_level,
    _load_places,
    connect,
    resolve_country_token,
)
from .countries import admin_label_for, level_label
from .geo import normalize_name
from .transliterate import latin_forms


def search_places(
    query: str,
    *,
    level: str | None = None,
    country: str | None = None,
    state: str | None = None,
    limit: int = 8,
    offset: int = 0,
    catalog_path: Path | None = None,
) -> dict:
    text = str(query or "").strip()
    limit = max(1, min(int(limit or 8), 20))
    offset = max(0, int(offset or 0))
    if len(normalize_name(text)) < 2:
        return {"results": [], "limit": limit, "offset": offset, "reason": "Enter at least two characters."}
    conn = connect(catalog_path, readonly=True)
    try:
        ranked = _ranked(conn, text, level=level, country=country, state=state)
        page = ranked[offset:offset + limit]
        return {
            "results": [_compact(conn, row, method, score) for row, method, score, _population in page],
            "limit": limit,
            "offset": offset,
            "total_window": len(ranked),
        }
    finally:
        conn.close()


def place_preview(place_id: str, *, catalog_path: Path | None = None) -> dict:
    conn = connect(catalog_path, readonly=True)
    try:
        row = conn.execute("SELECT * FROM place WHERE id=? AND active=1", (place_id,)).fetchone()
        if not row:
            raise ValueError("Catalogue place was not found.")
        geometry = conn.execute("SELECT geojson FROM geometry WHERE place_id=?", (place_id,)).fetchone()
        if not geometry:
            raise ValueError("This catalogue place has no geometry to preview.")
        payload = json.loads(geometry["geojson"])
        aliases = _aliases_for(conn, row["id"], 4)
        alternate = next((item.get("alias") for item in aliases if item.get("alias") and item.get("alias") != row["canonical_name"]), None)
        return {
            "id": row["id"],
            "name": row["canonical_name"],
            "alternate_name": alternate,
            "level": row["level"],
            "feature_type": row["feature_type"],
            "country_code": row["country_code"],
            "country_name": _country_name(conn, row["country_code"]),
            "admin_label": admin_label_for(row["country_code"]),
            "level_label": level_label(row["level"], row["country_code"]),
            "state_name": row["state_name"],
            "state_place_id": row["state_place_id"],
            "district_name": row["district_name"],
            "district_place_id": row["district_place_id"],
            "parent_id": row["parent_id"],
            "representation": "point" if row["representation"] == "point" else "boundary",
            "source_namespace": row["source_namespace"],
            "geometry": payload,
        }
    finally:
        conn.close()


def _ranked(conn: sqlite3.Connection, text: str, *, level: str | None, country: str | None, state: str | None) -> list[tuple]:
    normalized = normalize_name(text)
    found: dict[str, tuple] = {}

    def add(place_id: str, method: str, score: int, population: int = 0) -> None:
        current = found.get(place_id)
        if current is None or score > current[1]:
            found[place_id] = (method, score, population)

    for row in conn.execute("SELECT DISTINCT place_id FROM alias WHERE normalized=?", (normalized,)):
        add(row["place_id"], "exact_alias", 100)
    prefix = normalized + "%"
    for row in conn.execute(
        """
        SELECT alias.place_id AS place_id
        FROM alias
        JOIN place ON place.id = alias.place_id
        WHERE place.active = 1 AND alias.normalized LIKE ? ESCAPE '\\'
        LIMIT 40
        """,
        (prefix,),
    ):
        add(row["place_id"], "prefix", 80)
    forms = []
    for form in latin_forms(text):
        folded = normalize_name(form)
        if folded and folded not in forms:
            forms.append(folded)
    practical = forms[-1] if forms else ""
    for form in forms:
        cap = 100 if form == practical else 84
        for row in conn.execute("SELECT DISTINCT place_id, alias FROM alias WHERE normalized=?", (form,)):
            add(row["place_id"], "transliteration", min(cap, int(round(fuzz.ratio(form, normalize_name(row["alias"]))))))
        for score, place, _alias in _fuzzy_hits(conn, form, min_score=FUZZY_CANDIDATE_SCORE):
            add(place["id"], "transliteration", min(score, cap), int(place["population"] or 0))
    if not forms:
        for score, place, _alias in _fuzzy_hits(conn, normalized, min_score=FUZZY_CANDIDATE_SCORE):
            add(place["id"], "fuzzy", score, int(place["population"] or 0))
    if not found:
        return []
    rows = {row["id"]: row for row in _load_places(conn, list(found))}
    ranked = []
    for place_id, (method, score, population) in found.items():
        row = rows.get(place_id)
        if row is None:
            continue
        population = int(row["population"] or population or 0)
        if level and row["level"] != level:
            continue
        if country:
            resolved = resolve_country_token(conn, country)
            if not resolved.get("recognized") or resolved.get("ambiguous") or row["country_code"] != resolved.get("country_code"):
                continue
        if state and not _state_match(conn, row, state):
            continue
        ranked.append((row, method, score, population))
    ranked.sort(key=lambda item: (-item[2], -item[3], item[0]["canonical_name"], item[0]["id"]))
    return _spread_states(ranked, 40)


def catalogue_filters(catalog_path: Path | None = None) -> dict:
    """Countries and feature types the CMS can offer. Comes from the installed catalogue."""
    conn = connect(catalog_path, readonly=True)
    try:
        countries = []
        for row in conn.execute(
            "SELECT id, canonical_name, country_code FROM place WHERE level='country' AND active=1 ORDER BY canonical_name"
        ):
            countries.append({
                "id": row["id"],
                "name": row["canonical_name"],
                "country_code": row["country_code"],
                "admin_label": admin_label_for(row["country_code"]),
            })
        return {
            "countries": countries,
            "levels": [
                {"id": "country", "label": "Country"},
                {"id": "state", "label": "State, province, or territory"},
                {"id": "district", "label": "District"},
                {"id": "city", "label": "City"},
            ],
        }
    finally:
        conn.close()


def _country_name(conn: sqlite3.Connection, country_code: str | None) -> str | None:
    if not country_code:
        return None
    row = conn.execute(
        "SELECT canonical_name FROM place WHERE level='country' AND country_code=? AND active=1",
        (country_code,),
    ).fetchone()
    return row["canonical_name"] if row else None


def _state_match(conn: sqlite3.Connection, row: sqlite3.Row, state: str) -> bool:
    token = normalize_name(state)
    if token in {normalize_name(row["state_name"] or ""), normalize_name(row["canonical_name"] or "")}:
        return True
    ids = set(_ids_at_level(conn, state, "state", row["country_code"]))
    return row["id"] in ids or (row["state_place_id"] or "") in ids


def _spread_states(ranked: list[tuple], limit: int, per_state: int = 2) -> list[tuple]:
    """Keep a high-scoring place from more than one state in the window.

    Population only orders equal scores. It does not accept a place.
    """
    picked = []
    deferred = []
    counts: dict[str, int] = {}
    for item in ranked:
        state = item[0]["state_place_id"] or item[0]["state_name"] or ""
        if counts.get(state, 0) >= per_state:
            deferred.append(item)
            continue
        picked.append(item)
        counts[state] = counts.get(state, 0) + 1
        if len(picked) >= limit:
            return picked
    for item in deferred:
        if len(picked) >= limit:
            break
        picked.append(item)
    return picked


def _compact(conn: sqlite3.Connection, row: sqlite3.Row, method: str, score: int) -> dict:
    aliases = _aliases_for(conn, row["id"], 3)
    alternate = next((item.get("alias") for item in aliases if item.get("alias") and item.get("alias") != row["canonical_name"]), None)
    return {
        "id": row["id"],
        "name": row["canonical_name"],
        "alternate_name": alternate,
        "level": row["level"],
        "feature_type": row["feature_type"],
        "country_code": row["country_code"],
        "country_name": _country_name(conn, row["country_code"]),
        "admin_label": admin_label_for(row["country_code"]),
        "level_label": level_label(row["level"], row["country_code"]),
        "state_name": row["state_name"],
        "district_name": row["district_name"],
        "representation": "point" if row["representation"] == "point" else "boundary",
        "source_namespace": row["source_namespace"],
        "match_method": method,
        "score": score,
    }
