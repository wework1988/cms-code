"""Local SQLite gazetteer. Geometry stays in the database; prompts get summaries."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shapely.geometry import Point, mapping, shape
from shapely.prepared import prep
from shapely.strtree import STRtree

from .countries import (
    COUNTRIES,
    GEONAMES_URLS,
    NATURAL_EARTH,
    SHARED_GEONAMES,
    admin_label_for,
    admin_name_forms,
    all_download_urls,
    dataset_namespace_for_geonames,
    geonames_urls,
    include_settlement,
    iso_for_token,
    MAJOR_POPULATION_FLOOR,
    level_label,
    parse_country_list,
)
from .geo import GeoResolveError, bbox_of, child_within_parent, geometry_of, normalize_name, representative_lonlat

LAB = Path(__file__).resolve().parent.parent
CATALOG_DIR = LAB / "assets/maps" / "catalog"
ACTIVE_PATH = CATALOG_DIR / "geography.sqlite"
STATUS_PATH = CATALOG_DIR / "status.json"
CURATED_PATH = CATALOG_DIR / "curated_aliases.json"
DIAGNOSTICS_PATH = CATALOG_DIR / "crosswalk-diagnostics.json"
PROVENANCE_PATH = CATALOG_DIR / "provenance.json"
DOWNLOADS = CATALOG_DIR / "downloads"

SCHEMA_VERSION = 1
POINT_CODES = frozenset({
    "PPL", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLC", "PPLF", "PPLG", "PPLL", "PPLR", "PPLS", "STLMT",
})

# Spelling similarity proposes candidates. It does not prove identity.
FUZZY_CANDIDATE_SCORE = 72
_FETCH_USER_AGENT = "cms-map-catalog/1.0 (local geography import)"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_diagnostics(*, boundaries: list | None = None, settlements: list | None = None) -> None:
    """Merge boundary and settlement diagnostics so one import does not erase the other."""
    current: dict = {}
    if DIAGNOSTICS_PATH.is_file():
        try:
            loaded = json.loads(DIAGNOSTICS_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                current = loaded
        except json.JSONDecodeError:
            current = {}
    if boundaries is not None:
        current["boundaries"] = boundaries
    if settlements is not None:
        current["settlements"] = settlements
    current["updated_at"] = _utc_now()
    DIAGNOSTICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    DIAGNOSTICS_PATH.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _download_file(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": _FETCH_USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = response.read()
    except Exception as error:  # noqa: BLE001 — surface the URL that failed
        raise GeoResolveError(f"Could not download {url}: {error}") from error
    if len(data) < 1000 or data.lstrip().startswith(b"<"):
        raise GeoResolveError(f"Download for {url} was not a usable dataset file ({len(data)} bytes)")
    temporary.write_bytes(data)
    temporary.replace(path)


def _provenance_record(path: Path, url: str, *, downloaded: bool, extra: dict | None = None) -> dict:
    extra = extra or {}
    retrieved = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat()
    if downloaded:
        retrieved = _utc_now()
    return {
        "path": str(path.relative_to(LAB)),
        "source_url": url,
        "sha256": file_sha256(path),
        "bytes": path.stat().st_size,
        "retrieved_at": retrieved,
        "downloaded_this_run": downloaded,
        "licence": extra.get("licence"),
        "version": extra.get("version"),
        "boundary_year": extra.get("boundary_year"),
        "attribution": extra.get("attribution"),
        "limitations": extra.get("limitations"),
    }


def fetch_sources(country: str = "IN,PK,AF") -> list[dict]:
    """Download missing pinned files for the requested countries and record checksums.

    Files already in the cache are not downloaded again. Natural Earth countries
    stay as the local file; the dataset page is not a GeoJSON download.
    """
    codes = parse_country_list(country)
    jobs: list[dict] = []
    for name, url in SHARED_GEONAMES.items():
        jobs.append({"path": DOWNLOADS / name, "url": url, "extra": {"licence": "CC BY 4.0", "version": "GeoNames export dump"}})
    for iso in codes:
        for name, url in geonames_urls(iso).items():
            if name in SHARED_GEONAMES:
                continue
            jobs.append({
                "path": DOWNLOADS / name,
                "url": url,
                "extra": {"licence": "CC BY 4.0", "version": f"GeoNames {iso} export dump"},
            })
        for level in ("adm1", "adm2"):
            spec = COUNTRIES[iso][level]
            jobs.append({"path": spec["path"], "url": spec["source_url"], "extra": spec})
    records = []
    if NATURAL_EARTH["path"].is_file():
        records.append(_provenance_record(
            NATURAL_EARTH["path"], NATURAL_EARTH["source_url"], downloaded=False, extra=NATURAL_EARTH,
        ))
    for job in jobs:
        path = job["path"]
        downloaded = not path.is_file() or path.stat().st_size < 1000
        if downloaded:
            _download_file(job["url"], path)
        records.append(_provenance_record(path, job["url"], downloaded=downloaded, extra=job["extra"]))
    current = {}
    if PROVENANCE_PATH.is_file():
        try:
            loaded = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                current = loaded
        except json.JSONDecodeError:
            current = {}
    files = current.get("files") if isinstance(current.get("files"), dict) else {}
    for record in records:
        files[record["path"]] = record
    current["files"] = files
    current["updated_at"] = _utc_now()
    current["countries"] = codes
    PROVENANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROVENANCE_PATH.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return records


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA user_version = 1;
        CREATE TABLE dataset (
          id INTEGER PRIMARY KEY,
          namespace TEXT NOT NULL UNIQUE,
          source_url TEXT NOT NULL,
          licence TEXT NOT NULL,
          downloaded_at TEXT NOT NULL,
          version TEXT,
          boundary_year TEXT,
          checksum TEXT NOT NULL,
          attribution TEXT,
          limitations TEXT
        );
        CREATE TABLE place (
          id TEXT PRIMARY KEY,
          source_namespace TEXT NOT NULL,
          source_feature_id TEXT NOT NULL,
          canonical_name TEXT NOT NULL,
          level TEXT NOT NULL,
          feature_type TEXT NOT NULL,
          country_code TEXT,
          admin1_code TEXT,
          admin2_code TEXT,
          parent_id TEXT,
          parent_status TEXT,
          state_place_id TEXT,
          district_place_id TEXT,
          state_name TEXT,
          district_name TEXT,
          representation TEXT NOT NULL,
          dataset_id INTEGER NOT NULL,
          population INTEGER,
          active INTEGER NOT NULL DEFAULT 1,
          note TEXT,
          UNIQUE(source_namespace, source_feature_id)
        );
        CREATE TABLE alias (
          place_id TEXT NOT NULL,
          alias TEXT NOT NULL,
          normalized TEXT NOT NULL,
          language TEXT,
          source TEXT NOT NULL,
          UNIQUE(place_id, normalized, language, source)
        );
        CREATE TABLE geometry (
          place_id TEXT PRIMARY KEY,
          geojson TEXT NOT NULL,
          bbox_w REAL, bbox_s REAL, bbox_e REAL, bbox_n REAL,
          anchor_lon REAL, anchor_lat REAL
        );
        CREATE TABLE crosswalk (
          from_namespace TEXT NOT NULL,
          from_code TEXT NOT NULL,
          to_place_id TEXT NOT NULL,
          method TEXT NOT NULL,
          UNIQUE(from_namespace, from_code)
        );
        """
    )


def _ensure_indexes(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_alias_norm ON alias(normalized);
        CREATE INDEX IF NOT EXISTS idx_place_level ON place(level);
        CREATE INDEX IF NOT EXISTS idx_place_state ON place(state_place_id);
        CREATE INDEX IF NOT EXISTS idx_place_name ON place(canonical_name);
        """
    )


def connect(path: Path | None = None, *, readonly: bool = True) -> sqlite3.Connection:
    target = path or ACTIVE_PATH
    if readonly:
        if not target.is_file():
            raise GeoResolveError(
                "Geographic catalogue is not installed. Run geography_catalog.py import-boundaries "
                "and import-geonames outside the CMS."
            )
        conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(target)
        conn.execute("PRAGMA journal_mode=DELETE")
    conn.row_factory = sqlite3.Row
    return conn


def validate_database(path: Path, *, require_cities: bool = False) -> None:
    conn = sqlite3.connect(path)
    try:
        check = conn.execute("PRAGMA integrity_check").fetchone()
        if not check or check[0] != "ok":
            raise GeoResolveError(f"Catalogue integrity check failed: {check}")
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version != SCHEMA_VERSION:
            raise GeoResolveError(f"Catalogue schema version {version} is not supported ({SCHEMA_VERSION})")
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = {"dataset", "place", "alias", "geometry", "crosswalk"} - tables
        if missing:
            raise GeoResolveError(f"Catalogue is missing tables: {sorted(missing)}")
        _require_country_coverage(conn, require_cities=require_cities)
    finally:
        conn.close()


def activate_database(building: Path, active: Path = ACTIVE_PATH) -> None:
    """Swap in a validated catalogue. On failure the previous file stays active."""
    validate_database(building, require_cities=_has_cities(building))
    previous = active.with_name("geography.sqlite.previous")
    moved = False
    try:
        if active.exists():
            os.replace(active, previous)
            moved = True
        os.replace(building, active)
    except Exception:
        if moved and previous.exists() and not active.exists():
            os.replace(previous, active)
        raise
    write_status(active)


def _has_cities(path: Path) -> bool:
    conn = sqlite3.connect(path)
    try:
        return conn.execute(
            "SELECT 1 FROM dataset WHERE namespace='geonames' OR namespace LIKE 'geonames_%' LIMIT 1"
        ).fetchone() is not None
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def _require_country_coverage(conn: sqlite3.Connection, *, require_cities: bool) -> None:
    """India keeps its historical minimums. Other installed countries use their own floors."""
    for iso, spec in COUNTRIES.items():
        present = conn.execute(
            "SELECT COUNT(*) FROM place WHERE country_code=? AND level='country' AND active=1",
            (iso,),
        ).fetchone()[0]
        if iso == "IN" and present < 1:
            raise GeoResolveError("Boundary catalogue is missing India")
        if not present:
            continue
        states = conn.execute(
            "SELECT COUNT(*) FROM place WHERE country_code=? AND level='state' AND active=1",
            (iso,),
        ).fetchone()[0]
        districts = conn.execute(
            "SELECT COUNT(*) FROM place WHERE country_code=? AND level='district' AND active=1",
            (iso,),
        ).fetchone()[0]
        if states < spec["min_adm1"] or (spec["require_adm2"] and districts < spec["min_adm2"]):
            raise GeoResolveError(
                f"{iso} boundary catalogue looks incomplete (states={states}, districts={districts})"
            )
        if not require_cities:
            continue
        has_settlements = conn.execute(
            "SELECT 1 FROM dataset WHERE namespace=? LIMIT 1",
            (dataset_namespace_for_geonames(iso),),
        ).fetchone()
        if not has_settlements:
            if iso == "IN":
                raise GeoResolveError("India settlement dataset is missing")
            continue
        cities = conn.execute(
            "SELECT COUNT(*) FROM place WHERE country_code=? AND level='city' AND active=1",
            (iso,),
        ).fetchone()[0]
        if cities < spec["min_cities"]:
            raise GeoResolveError(f"{iso} settlement catalogue looks incomplete (cities={cities})")


def write_status(path: Path = ACTIVE_PATH) -> dict:
    conn = connect(path, readonly=True)
    try:
        counts = {
            row["level"]: row["n"]
            for row in conn.execute("SELECT level, COUNT(*) AS n FROM place WHERE active=1 GROUP BY level")
        }
        counts["alias"] = conn.execute("SELECT COUNT(*) FROM alias").fetchone()[0]
        by_country = {}
        for row in conn.execute(
            "SELECT country_code, level, COUNT(*) AS n FROM place WHERE active=1 GROUP BY country_code, level"
        ):
            by_country.setdefault(row["country_code"] or "", {})[row["level"]] = row["n"]
        unmatched = conn.execute(
            """
            SELECT COUNT(*) FROM place
            WHERE active=1 AND parent_status IN ('unresolved', 'conflict', 'unresolved_boundary', 'inferred_spatial')
            """
        ).fetchone()[0]
        datasets = []
        for row in conn.execute("SELECT * FROM dataset ORDER BY id"):
            datasets.append({
                "namespace": row["namespace"],
                "source_url": row["source_url"],
                "licence": row["licence"],
                "downloaded_at": row["downloaded_at"],
                "version": row["version"],
                "boundary_year": row["boundary_year"],
                "checksum": row["checksum"],
                "attribution": row["attribution"],
                "limitations": row["limitations"],
            })
    finally:
        conn.close()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "installed": True,
        "built_at": _utc_now(),
        "counts": counts,
        "by_country": by_country,
        "unmatched_hierarchy": unmatched,
        "admin_labels": {iso: spec["admin_label"] for iso, spec in COUNTRIES.items()},
        "levels": ["country", "state", "district", "city"],
        "datasets": datasets,
        "limitations": [
            "Story text is still sent to DeepSeek. Polygons, coordinates, and the catalogue dump are not.",
            "Coverage is India (IN), Pakistan (PK), and Afghanistan (AF): Natural Earth admin-0, geoBoundaries ADM1 and ADM2, and GeoNames populated places.",
            "India imports every GeoNames populated place. Pakistan and Afghanistan import national and provincial seats, second-order seats, and other populated places with population of at least 25000.",
            "Natural Earth country outlines are not merged with geoBoundaries polygons. A first-level unit keeps its source country code even when the outlines disagree.",
            "Afghanistan ADM1 is boundary year 2007 and ADM2 is 2014. Overlap between them is inferred_spatial, not a verified administrative code.",
            "Historical boundary lines are not included. Historic GeoNames spellings for Pakistan and Afghanistan are aliases only.",
            "Delhi ADM1 is the National Capital Territory, separate from populated-place points named Delhi. Islamabad Capital Territory is the same kind of distinction.",
            "Fuzzy name matches are suggestions only. A fallback may choose one supplied candidate; it cannot add geometry.",
            "A place with only a point is renderable with show_marker. No city polygon is invented.",
            "Population is stored as a ranking hint and is not used by itself to pick an ambiguous place.",
            "South Asia relief is Natural Earth II 50m across 45–115E, 0–50N. It covers India, Pakistan, and Afghanistan. It is not high-resolution imagery.",
        ],
    }
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATUS_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(STATUS_PATH)
    return payload


def _insert_dataset(conn: sqlite3.Connection, spec: dict, checksum: str, downloaded_at: str) -> int:
    conn.execute("DELETE FROM dataset WHERE namespace=?", (spec["namespace"],))
    cur = conn.execute(
        """
        INSERT INTO dataset (namespace, source_url, licence, downloaded_at, version, boundary_year, checksum, attribution, limitations)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            spec["namespace"], spec["source_url"], spec["licence"], downloaded_at,
            spec.get("version"), spec.get("boundary_year"), checksum,
            spec.get("attribution"), spec.get("limitations"),
        ),
    )
    return int(cur.lastrowid)


def _add_alias(conn: sqlite3.Connection, place_id: str, alias: str, language: str | None, source: str) -> None:
    text = (alias or "").strip()
    if not text:
        return
    normalized = normalize_name(text)
    if len(normalized) < 2:
        return
    conn.execute(
        "INSERT OR IGNORE INTO alias (place_id, alias, normalized, language, source) VALUES (?, ?, ?, ?, ?)",
        (place_id, text, normalized, language or "", source),
    )


def _store_geometry(conn: sqlite3.Connection, place_id: str, geom) -> None:
    if not geom.is_valid:
        geom = geom.buffer(0)
    if geom.is_empty:
        raise GeoResolveError(f"Empty geometry for {place_id}")
    west, south, east, north = bbox_of(geom)
    anchor = representative_lonlat(geom)
    conn.execute(
        """
        INSERT OR REPLACE INTO geometry (place_id, geojson, bbox_w, bbox_s, bbox_e, bbox_n, anchor_lon, anchor_lat)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (place_id, json.dumps(mapping(geom)), west, south, east, north, anchor[0], anchor[1]),
    )


def _display_name(value: str) -> str:
    stripped = "".join(
        ch for ch in unicodedata_normalize(value)
        if unicodedata_category(ch) != "Mn"
    )
    return stripped.replace("  ", " ").strip()


def unicodedata_normalize(value: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", value or "")


def unicodedata_category(ch: str) -> str:
    import unicodedata
    return unicodedata.category(ch)


def _copy_settlements(source: Path, dest: sqlite3.Connection) -> None:
    """Copy settlement rows onto new dataset ids so a boundary rebuild cannot overwrite them."""
    if not source.is_file():
        return
    dest.execute("ATTACH DATABASE ? AS old", (str(source),))
    try:
        listing = dest.execute(
            """
            SELECT namespace FROM old.dataset
            WHERE namespace='geonames' OR namespace LIKE 'geonames_%'
            ORDER BY namespace
            """
        )
        namespaces = [row[0] for row in listing]
        listing.close()
        for namespace in namespaces:
            found = dest.execute("SELECT * FROM old.dataset WHERE namespace=?", (namespace,))
            dataset = found.fetchone()
            found.close()
            if not dataset:
                continue
            country = "IN" if namespace == "geonames" else namespace.split("_", 1)[1]
            cur = dest.execute(
                """
                INSERT INTO dataset (
                  namespace, source_url, licence, downloaded_at, version, boundary_year, checksum, attribution, limitations
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dataset["namespace"], dataset["source_url"], dataset["licence"], dataset["downloaded_at"],
                    dataset["version"], dataset["boundary_year"], dataset["checksum"], dataset["attribution"],
                    dataset["limitations"],
                ),
            )
            new_id = int(cur.lastrowid)
            cur.close()
            copied = dest.execute(
                """
                INSERT OR REPLACE INTO place (
                  id, source_namespace, source_feature_id, canonical_name, level, feature_type,
                  country_code, admin1_code, admin2_code, parent_id, parent_status, state_place_id,
                  district_place_id, state_name, district_name, representation, dataset_id, population, active, note
                )
                SELECT
                  id, source_namespace, source_feature_id, canonical_name, level, feature_type,
                  country_code, admin1_code, admin2_code, parent_id, parent_status, state_place_id,
                  district_place_id, state_name, district_name, representation, ?, population, active, note
                FROM old.place
                WHERE source_namespace='geonames' AND country_code=?
                """,
                (new_id, country),
            )
            copied.close()
            copied = dest.execute(
                """
                INSERT OR REPLACE INTO alias
                SELECT alias.* FROM old.alias AS alias
                JOIN old.place AS place ON place.id = alias.place_id
                WHERE place.source_namespace='geonames' AND place.country_code=?
                """,
                (country,),
            )
            copied.close()
            copied = dest.execute(
                """
                INSERT OR REPLACE INTO geometry
                SELECT geometry.* FROM old.geometry AS geometry
                JOIN old.place AS place ON place.id = geometry.place_id
                WHERE place.source_namespace='geonames' AND place.country_code=?
                """,
                (country,),
            )
            copied.close()
        copied = dest.execute(
            """
            INSERT OR IGNORE INTO crosswalk
            SELECT * FROM old.crosswalk WHERE from_namespace LIKE 'geonames%'
            """
        )
        copied.close()
        dest.commit()
    except Exception:
        try:
            dest.execute("DETACH DATABASE old")
        except sqlite3.OperationalError:
            pass
        raise
    dest.execute("DETACH DATABASE old")


def import_boundaries(*, refresh: bool = False) -> None:
    """Rebuild boundary tables for IN, PK, and AF and keep settlement rows."""
    del refresh  # both imports are explicit rebuilds of their own namespace
    building = CATALOG_DIR / "geography.sqlite.building"
    if building.exists():
        building.unlink()
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    conn = connect(building, readonly=False)
    diagnostics = []
    try:
        init_schema(conn)
        _import_countries(conn)
        states = _import_all_adm1(conn, diagnostics)
        _import_all_adm2(conn, states, diagnostics)
        if ACTIVE_PATH.is_file():
            _copy_settlements(ACTIVE_PATH, conn)
        _apply_curated(conn)
        _ensure_indexes(conn)
        conn.commit()
        _write_diagnostics(boundaries=diagnostics)
    except Exception:
        conn.close()
        if building.exists():
            building.unlink()
        raise
    conn.close()
    activate_database(building)


def _shape_country(shape_iso: str) -> str | None:
    token = shape_iso.replace("_", "-").split("-", 1)[0].upper()
    return token if token in COUNTRIES else None


def _capital_territory(iso2: str, shape_iso: str, name: str) -> bool:
    if iso2 == "IN" and shape_iso == "IN-DL":
        return True
    if iso2 == "PK" and (shape_iso == "PK-IS" or normalize_name(name) in {"islamabad", "islamabad capital territory"}):
        return True
    return False


def _import_countries(conn: sqlite3.Connection) -> None:
    spec = NATURAL_EARTH
    path = spec["path"]
    if not path.is_file():
        raise GeoResolveError(f"Missing cached country file: {path.name}")
    data = json.loads(path.read_text(encoding="utf-8"))
    by_iso = {}
    for feature in data.get("features") or []:
        props = feature.get("properties") or {}
        iso = str(props.get("ISO_A2") or "").upper()
        if iso in COUNTRIES:
            by_iso[iso] = feature
    missing = [iso for iso in COUNTRIES if iso not in by_iso]
    if missing:
        raise GeoResolveError(f"countries.geojson is missing {', '.join(missing)}")
    dataset_id = _insert_dataset(conn, spec, file_sha256(path), _utc_now())
    for iso, feature in by_iso.items():
        country = COUNTRIES[iso]
        props = feature["properties"]
        geom = geometry_of(feature)
        if geom.geom_type not in {"Polygon", "MultiPolygon"}:
            raise GeoResolveError(f"{iso} country geometry is {geom.geom_type}")
        place_id = country["place_id"]
        name = str(props.get("ADMIN") or props.get("NAME") or iso)
        conn.execute(
            """
            INSERT INTO place (
              id, source_namespace, source_feature_id, canonical_name, level, feature_type,
              country_code, representation, dataset_id, population, active, note
            ) VALUES (?, 'naturalearth', ?, ?, 'country', 'country', ?, ?, ?, ?, 1, ?)
            """,
            (
                place_id,
                str(props.get("NE_ID") or props.get("ISO_A3") or country["iso3"]),
                name,
                iso,
                geom.geom_type.lower(),
                dataset_id,
                int(props["POP_EST"]) if str(props.get("POP_EST") or "").replace(".0", "").isdigit() else None,
                f"Natural Earth admin-0 {name}. This outline is not merged with geoBoundaries polygons.",
            ),
        )
        _store_geometry(conn, place_id, geom)
        aliases = [
            (name, "en", "naturalearth"),
            (props.get("NAME") or "", "en", "naturalearth"),
            (props.get("NAME_LONG") or "", "en", "naturalearth"),
            (props.get("FORMAL_EN") or "", "en", "naturalearth"),
            (country["iso2"], "", "naturalearth_iso2"),
            (country["iso3"], "", "naturalearth_iso3"),
            (props.get("NAME_HI") or "", "hi", "naturalearth_NAME_HI"),
            (props.get("NAME_UR") or "", "ur", "naturalearth_NAME_UR"),
            (props.get("NAME_FA") or "", "fa", "naturalearth_NAME_FA"),
            (props.get("NAME_PS") or "", "ps", "naturalearth_NAME_PS"),
        ]
        if iso == "IN":
            aliases.append(("Bharat", "en", "naturalearth"))
        for alias, language, source in aliases:
            _add_alias(conn, place_id, str(alias), language, source)


def _import_all_adm1(conn: sqlite3.Connection, diagnostics: list) -> dict[str, dict]:
    states: dict[str, dict] = {}
    for iso, country in COUNTRIES.items():
        spec = country["adm1"]
        path = spec["path"]
        if not path.is_file():
            raise GeoResolveError(f"Missing {path}. Run geography_catalog.py fetch before import-boundaries.")
        data = json.loads(path.read_text(encoding="utf-8"))
        features = data.get("features") or []
        if len(features) < country["min_adm1"]:
            raise GeoResolveError(f"{path.name} has {len(features)} features; expected at least {country['min_adm1']}")
        keys = set((features[0].get("properties") or {}))
        for required in ("shapeName", "shapeISO", "shapeID", "shapeType"):
            if required not in keys:
                raise GeoResolveError(f"{path.name} is missing {required}")
        dataset_id = _insert_dataset(conn, spec, file_sha256(path), _utc_now())
        country_id = country["place_id"]
        country_geom = shape(json.loads(conn.execute("SELECT geojson FROM geometry WHERE place_id=?", (country_id,)).fetchone()[0]))
        imported = 0
        for feature in features:
            props = feature["properties"]
            if props.get("shapeType") != "ADM1":
                continue
            shape_iso = str(props.get("shapeISO") or "").strip()
            owner = _shape_country(shape_iso)
            if owner != iso:
                if country["strict_iso"]:
                    raise GeoResolveError(f"Unexpected ADM1 ISO {shape_iso}")
                diagnostics.append({
                    "country": iso, "level": "ADM1", "code": shape_iso,
                    "name": props.get("shapeName"), "reason": "iso_prefix_does_not_match_file",
                })
                continue
            try:
                geom = geometry_of(feature)
            except GeoResolveError as error:
                diagnostics.append({"country": iso, "level": "ADM1", "code": shape_iso, "name": props.get("shapeName"), "reason": str(error)})
                continue
            if geom.geom_type not in {"Polygon", "MultiPolygon"}:
                diagnostics.append({"country": iso, "level": "ADM1", "code": shape_iso, "name": props.get("shapeName"), "reason": f"geometry {geom.geom_type}"})
                continue
            place_id = f"gb-adm1-{shape_iso}"
            name = _display_name(str(props["shapeName"]))
            capital = _capital_territory(iso, shape_iso, name)
            feature_type = "national_capital_territory" if capital else "adm1_territory"
            if capital and iso == "IN":
                note = "National Capital Territory of Delhi. This polygon is the union territory, not a municipal city or a district named New Delhi."
            elif capital:
                note = "Capital territory polygon from geoBoundaries. This is not a municipal city boundary."
            else:
                note = f"geoBoundaries ADM1. Display label: {country['admin_label']}."
            overlaps = child_within_parent(geom, country_geom, min_overlap=0.5) or country_geom.buffer(0.4).intersects(geom)
            parent_status = "source_group" if overlaps else "unresolved"
            if not overlaps:
                diagnostics.append({
                    "country": iso, "level": "ADM1", "code": shape_iso, "name": name,
                    "reason": "does_not_overlap_natural_earth_country",
                    "parent_status": "unresolved",
                })
            conn.execute(
                """
                INSERT INTO place (
                  id, source_namespace, source_feature_id, canonical_name, level, feature_type,
                  country_code, parent_id, parent_status, state_place_id, state_name,
                  representation, dataset_id, active, note
                ) VALUES (?, ?, ?, ?, 'state', ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    place_id, spec["place_namespace"], str(props["shapeID"]), name, feature_type, iso,
                    country_id if parent_status == "source_group" else None,
                    parent_status, place_id, name, geom.geom_type.lower(), dataset_id, note,
                ),
            )
            _store_geometry(conn, place_id, geom)
            _add_alias(conn, place_id, name, "en", "geoboundaries")
            _add_alias(conn, place_id, str(props["shapeName"]), "", "geoboundaries_source")
            _add_alias(conn, place_id, shape_iso, "", "geoboundaries_iso")
            if shape_iso == "IN-DL":
                _add_alias(conn, place_id, "National Capital Territory of Delhi", "en", "curated:administrative_title")
            if capital and iso == "PK":
                _add_alias(conn, place_id, "Islamabad", "en", "geoboundaries_short_name")
            states[place_id] = {
                "name": name, "norm": normalize_name(name), "geom": geom, "iso": shape_iso,
                "country": iso, "containment_status": country["containment_status"],
            }
            imported += 1
        if imported < country["min_adm1"]:
            raise GeoResolveError(f"Too few {iso} ADM1 features imported ({imported})")
    return states


def _import_all_adm2(conn: sqlite3.Connection, states: dict[str, dict], diagnostics: list) -> None:
    for iso, country in COUNTRIES.items():
        spec = country["adm2"]
        path = spec["path"]
        if not path.is_file():
            if country["require_adm2"]:
                raise GeoResolveError(f"Missing {path}. Run geography_catalog.py fetch before import-boundaries.")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        features = data.get("features") or []
        if len(features) < country["min_adm2"]:
            raise GeoResolveError(f"{path.name} has {len(features)} features; expected at least {country['min_adm2']}")
        keys = set((features[0].get("properties") or {}))
        for required in ("shapeName", "shapeID", "shapeType"):
            if required not in keys:
                raise GeoResolveError(f"{path.name} is missing {required}")
        dataset_id = _insert_dataset(conn, spec, file_sha256(path), _utc_now())
        country_states = {state_id: state for state_id, state in states.items() if state["country"] == iso}
        ids = list(country_states)
        geoms = [country_states[state_id]["geom"] for state_id in ids]
        tree = STRtree(geoms) if geoms else None
        prepared = {state_id: prep(state["geom"]) for state_id, state in country_states.items()}
        containment = country["containment_status"]
        imported = 0
        for feature in features:
            props = feature["properties"]
            if props.get("shapeType") != "ADM2":
                continue
            try:
                geom = geometry_of(feature)
            except GeoResolveError as error:
                diagnostics.append({"country": iso, "level": "ADM2", "code": props.get("shapeID"), "name": props.get("shapeName"), "reason": str(error)})
                continue
            if geom.geom_type not in {"Polygon", "MultiPolygon"}:
                diagnostics.append({"country": iso, "level": "ADM2", "code": props.get("shapeID"), "name": props.get("shapeName"), "reason": geom.geom_type})
                continue
            place_id = "gb-adm2-" + str(props["shapeID"])
            name = _display_name(str(props["shapeName"]))
            parent_id = None
            parent_status = "unresolved"
            if tree is not None:
                hits = list(tree.query(geom.representative_point(), predicate="intersects"))
                if len(hits) == 1:
                    candidate = ids[int(hits[0])]
                    if prepared[candidate].intersects(geom):
                        parent_id = candidate
                        parent_status = containment
                elif len(hits) > 1:
                    contained = []
                    for hit in hits:
                        candidate = ids[int(hit)]
                        if child_within_parent(geom, country_states[candidate]["geom"], min_overlap=0.8):
                            contained.append(candidate)
                    if len(contained) == 1:
                        parent_id = contained[0]
                        parent_status = containment
                    else:
                        parent_status = "unresolved_boundary"
            if parent_status in {"unresolved", "unresolved_boundary"}:
                diagnostics.append({
                    "country": iso, "level": "ADM2", "code": props.get("shapeID"), "name": name,
                    "reason": parent_status,
                })
            state_name = country_states[parent_id]["name"] if parent_id else None
            note = "geoBoundaries ADM2 district polygon."
            if containment == "inferred_spatial" and parent_id:
                note = (
                    "geoBoundaries ADM2 polygon. Parent province is inferred from spatial overlap only. "
                    "ADM1 and ADM2 boundary years differ, so this is not a verified code crosswalk."
                )
            conn.execute(
                """
                INSERT INTO place (
                  id, source_namespace, source_feature_id, canonical_name, level, feature_type,
                  country_code, parent_id, parent_status, state_place_id, district_place_id,
                  state_name, district_name, representation, dataset_id, active, note
                ) VALUES (?, ?, ?, ?, 'district', 'district', ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    place_id, spec["place_namespace"], str(props["shapeID"]), name, iso,
                    parent_id, parent_status, parent_id, place_id, state_name, name,
                    geom.geom_type.lower(), dataset_id, note,
                ),
            )
            _store_geometry(conn, place_id, geom)
            _add_alias(conn, place_id, name, "en", "geoboundaries")
            _add_alias(conn, place_id, str(props["shapeName"]), "", "geoboundaries_source")
            imported += 1
        if imported < country["min_adm2"]:
            raise GeoResolveError(f"Too few {iso} ADM2 features imported ({imported})")


def _load_admin_codes(iso2: str) -> tuple[dict[str, dict], dict[tuple[str, str], dict]]:
    spec = COUNTRIES[iso2]
    admin1_path = DOWNLOADS / "admin1CodesASCII.txt"
    admin2_path = DOWNLOADS / "admin2Codes.txt"
    for path in (admin1_path, admin2_path):
        if not path.is_file():
            raise GeoResolveError(f"Missing {path.name}. Download it from GeoNames before import-geonames.")
    prefix = iso2 + "."
    admin1 = {}
    for line in admin1_path.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) < 4 or not parts[0].startswith(prefix):
            continue
        code = parts[0].split(".", 1)[1]
        if not code.isdigit():
            continue
        admin1[code] = {"name": parts[1], "ascii": parts[2], "geonameid": parts[3]}
    if len(admin1) < spec["min_admin1_codes"]:
        raise GeoResolveError(f"admin1CodesASCII.txt does not contain the {iso2} division list")
    admin2 = {}
    for line in admin2_path.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) < 4 or not parts[0].startswith(prefix):
            continue
        bits = parts[0].split(".")
        if len(bits) != 3:
            continue
        admin2[(bits[1], bits[2])] = {"name": parts[1], "ascii": parts[2], "geonameid": parts[3]}
    if len(admin2) < spec["min_admin2_codes"]:
        raise GeoResolveError(f"admin2Codes.txt does not contain the {iso2} district list")
    return admin1, admin2


def _match_admin(
    conn: sqlite3.Connection,
    name: str,
    *,
    level: str,
    country_code: str,
    state_id: str | None = None,
) -> tuple[str | None, str]:
    """Match one administrative name inside one country. A tie stays unmatched."""
    saw_ambiguous = False
    for index, form in enumerate(admin_name_forms(name)):
        sql = """
            SELECT DISTINCT place.id
            FROM place
            JOIN alias ON alias.place_id = place.id
            WHERE place.level=? AND place.active=1 AND place.country_code=? AND alias.normalized=?
        """
        params: list[object] = [level, country_code, form]
        if level == "district" and state_id:
            sql += " AND place.state_place_id=?"
            params.append(state_id)
        ids = sorted({row[0] for row in conn.execute(sql, params)})
        if len(ids) == 1:
            return ids[0], "normalized_name" if index == 0 else "normalized_name_suffix"
        if len(ids) > 1:
            saw_ambiguous = True
    return None, "ambiguous_name" if saw_ambiguous else "unmatched_name"


def import_geonames(country: str = "IN") -> None:
    codes = parse_country_list(country)
    if not ACTIVE_PATH.is_file():
        raise GeoResolveError("Import boundaries before GeoNames so settlements can be attached to provinces")
    for iso in codes:
        _require_geonames_files(iso)
    building = CATALOG_DIR / "geography.sqlite.building"
    if building.exists():
        building.unlink()
    import shutil
    shutil.copy2(ACTIVE_PATH, building)
    conn = connect(building, readonly=False)
    diagnostics = []
    try:
        for iso in codes:
            _delete_country_settlements(conn, iso)
            _import_geonames_rows(conn, iso, diagnostics)
        _apply_curated(conn)
        _ensure_indexes(conn)
        conn.commit()
        _write_diagnostics(settlements=diagnostics)
    except Exception:
        conn.close()
        if building.exists():
            building.unlink()
        raise
    conn.close()
    activate_database(building)


def _delete_country_settlements(conn: sqlite3.Connection, iso2: str) -> None:
    """Remove one country's settlement rows. Other countries and user alias files stay."""
    conn.execute(
        "DELETE FROM geometry WHERE place_id IN (SELECT id FROM place WHERE source_namespace='geonames' AND country_code=?)",
        (iso2,),
    )
    conn.execute(
        "DELETE FROM alias WHERE place_id IN (SELECT id FROM place WHERE source_namespace='geonames' AND country_code=?)",
        (iso2,),
    )
    conn.execute("DELETE FROM place WHERE source_namespace='geonames' AND country_code=?", (iso2,))
    namespaces = [dataset_namespace_for_geonames(iso2)]
    if iso2 == "IN":
        namespaces.append("geonames_IN")
    marks = ",".join("?" for _ in namespaces)
    conn.execute(f"DELETE FROM dataset WHERE namespace IN ({marks})", namespaces)
    crosswalk = [f"geonames_admin1_{iso2}", f"geonames_admin2_{iso2}"]
    if iso2 == "IN":
        crosswalk.extend(["geonames_admin1", "geonames_admin2"])
    marks = ",".join("?" for _ in crosswalk)
    conn.execute(f"DELETE FROM crosswalk WHERE from_namespace IN ({marks})", crosswalk)


def _require_geonames_files(iso2: str) -> None:
    names = (f"{iso2}.zip", f"alternatenames-{iso2}.zip", "admin1CodesASCII.txt", "admin2Codes.txt", "readme.txt")
    for name in names:
        path = DOWNLOADS / name
        if not path.is_file() or path.stat().st_size < 1000:
            raise GeoResolveError(
                f"Missing GeoNames download {name}. Run geography_catalog.py fetch --country {iso2}."
            )
    readme = (DOWNLOADS / "readme.txt").read_text(encoding="utf-8", errors="replace")
    if "Creative Commons Attribution 4.0" not in readme:
        raise GeoResolveError("GeoNames readme does not advertise the expected CC BY 4.0 licence")
    with zipfile.ZipFile(DOWNLOADS / f"{iso2}.zip") as archive:
        if f"{iso2}.txt" not in archive.namelist():
            raise GeoResolveError(f"{iso2}.zip does not contain {iso2}.txt")


def _import_geonames_rows(conn: sqlite3.Connection, iso2: str, diagnostics: list) -> None:
    spec = COUNTRIES[iso2]
    admin1, admin2 = _load_admin_codes(iso2)
    state_by_code: dict[str, str] = {}
    geoname_to_place: dict[str, str] = {}
    for code, row in admin1.items():
        place_id, method = _match_admin(conn, row["ascii"], level="state", country_code=iso2)
        if not place_id:
            place_id, method = _match_admin(conn, row["name"], level="state", country_code=iso2)
        if not place_id:
            diagnostics.append({
                "country": iso2, "level": "admin1", "code": code, "name": row["name"],
                "ascii": row["ascii"], "reason": method,
            })
            continue
        state_by_code[code] = place_id
        geoname_to_place[row["geonameid"]] = place_id
        conn.execute(
            "INSERT OR REPLACE INTO crosswalk (from_namespace, from_code, to_place_id, method) VALUES (?, ?, ?, ?)",
            (f"geonames_admin1_{iso2}", code, place_id, method),
        )
        _add_alias(conn, place_id, row["name"], "en", "geonames_admin1")
        _add_alias(conn, place_id, row["ascii"], "en", "geonames_admin1_ascii")
    if len(state_by_code) < spec["min_admin1_crosswalk"]:
        raise GeoResolveError(f"{iso2} admin1 crosswalk matched only {len(state_by_code)} first-level areas")
    district_by_code: dict[tuple[str, str], str] = {}
    for key, row in admin2.items():
        state_id = state_by_code.get(key[0])
        if not state_id:
            diagnostics.append({
                "country": iso2, "level": "admin2", "code": f"{key[0]}.{key[1]}",
                "name": row["name"], "reason": "admin1_unmatched",
            })
            continue
        place_id, method = _match_admin(conn, row["ascii"], level="district", country_code=iso2, state_id=state_id)
        if not place_id:
            place_id, method = _match_admin(conn, row["name"], level="district", country_code=iso2, state_id=state_id)
        if not place_id:
            diagnostics.append({
                "country": iso2, "level": "admin2", "code": f"{key[0]}.{key[1]}",
                "name": row["name"], "state_place_id": state_id, "reason": method,
            })
            continue
        district_by_code[key] = place_id
        geoname_to_place[row["geonameid"]] = place_id
        conn.execute(
            "INSERT OR REPLACE INTO crosswalk (from_namespace, from_code, to_place_id, method) VALUES (?, ?, ?, ?)",
            (f"geonames_admin2_{iso2}", f"{key[0]}.{key[1]}", place_id, method),
        )
    archive_path = DOWNLOADS / f"{iso2}.zip"
    downloaded = datetime.fromtimestamp(archive_path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat()
    policy = (
        "Every GeoNames populated-place point. No settlement polygon is invented."
        if spec["settlement_policy"] == "all_populated_places"
        else (
            "National capitals, first-order seats, second-order seats, and other populated places "
            f"with population >= {MAJOR_POPULATION_FLOOR}. Smaller settlements are omitted. No city polygon is invented."
        )
    )
    dataset_id = _insert_dataset(conn, {
        "namespace": dataset_namespace_for_geonames(iso2),
        "source_url": geonames_urls(iso2)[f"{iso2}.zip"],
        "licence": "Creative Commons Attribution 4.0 (CC BY 4.0)",
        "version": f"GeoNames {iso2} dump",
        "boundary_year": downloaded[:10],
        "attribution": "GeoNames (https://www.geonames.org/)",
        "limitations": policy + " Alternate names are incomplete.",
    }, file_sha256(archive_path), downloaded)
    state_names = {
        row["id"]: row["canonical_name"]
        for row in conn.execute("SELECT id, canonical_name FROM place WHERE level='state' AND country_code=?", (iso2,))
    }
    district_names = {
        row["id"]: row["canonical_name"]
        for row in conn.execute("SELECT id, canonical_name FROM place WHERE level='district' AND country_code=?", (iso2,))
    }
    prepared_states = {}
    for place_id in state_by_code.values():
        geom = shape(json.loads(conn.execute("SELECT geojson FROM geometry WHERE place_id=?", (place_id,)).fetchone()[0]))
        prepared_states[place_id] = prep(geom)
    prepared_districts = {}
    district_geoms = []
    district_ids = []
    district_state: dict[str, str] = {}
    for (admin1_code, _admin2_code), place_id in district_by_code.items():
        geom = shape(json.loads(conn.execute("SELECT geojson FROM geometry WHERE place_id=?", (place_id,)).fetchone()[0]))
        prepared_districts[place_id] = prep(geom)
        district_geoms.append(geom)
        district_ids.append(place_id)
        owner = state_by_code.get(admin1_code)
        if owner:
            district_state[place_id] = owner
    district_tree = STRtree(district_geoms) if district_geoms else None
    containment = spec["containment_status"]
    place_rows = []
    alias_rows = []
    geometry_rows = []
    seen = 0
    with zipfile.ZipFile(archive_path) as archive:
        with archive.open(f"{iso2}.txt") as handle:
            for raw in handle:
                parts = raw.decode("utf-8").rstrip("\n").split("\t")
                if len(parts) < 19:
                    raise GeoResolveError(f"GeoNames {iso2}.txt row does not have the documented 19 columns")
                if parts[6] != "P" or parts[7] not in POINT_CODES or parts[8] != iso2:
                    continue
                try:
                    lat = float(parts[4])
                    lon = float(parts[5])
                except ValueError:
                    continue
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    continue
                population = int(parts[14]) if parts[14].isdigit() else None
                if not include_settlement(spec, parts[7], population):
                    continue
                geonameid = parts[0]
                if not geonameid.isdigit():
                    raise GeoResolveError("GeoNames geonameid column is not numeric")
                place_id = f"gn-{geonameid}"
                admin1_code = parts[10]
                admin2_code = parts[11]
                state_id = state_by_code.get(admin1_code)
                state_status = "source_code" if state_id else "unresolved"
                if state_id and not prepared_states[state_id].covers(Point(lon, lat)):
                    state_id = None
                    state_status = "conflict"
                district_id = district_by_code.get((admin1_code, admin2_code)) if admin2_code else None
                district_status = "source_code" if district_id else "unresolved"
                if district_id and not prepared_districts[district_id].covers(Point(lon, lat)):
                    district_id = None
                    district_status = "conflict"
                elif not district_id and district_tree is not None:
                    hits = list(district_tree.query(Point(lon, lat), predicate="covers"))
                    if iso2 == "IN":
                        owned = [district_ids[int(hit)] for hit in hits]
                    elif state_id:
                        owned = [
                            district_ids[int(hit)]
                            for hit in hits
                            if district_state.get(district_ids[int(hit)]) == state_id
                        ]
                    else:
                        owned = []
                    if len(owned) == 1:
                        district_id = owned[0]
                        district_status = "verified_pip" if iso2 == "IN" else containment
                    elif len(owned) > 1:
                        district_status = "unresolved_boundary"
                if state_status == "conflict" or district_status in {"conflict", "unresolved_boundary"}:
                    diagnostics.append({
                        "country": iso2,
                        "level": "city",
                        "code": geonameid,
                        "name": parts[1],
                        "admin1": admin1_code,
                        "admin2": admin2_code,
                        "reason": state_status if state_status == "conflict" else district_status,
                    })
                parent_id = district_id or state_id
                parent_status = district_status if district_id else state_status
                feature_type = "administrative_seat" if parts[7] in {"PPLC", "PPLA", "PPLA2", "PPLA3", "PPLA4"} else "populated_place"
                place_rows.append((
                    place_id, "geonames", geonameid, parts[1], "city", feature_type, iso2,
                    admin1_code, admin2_code, parent_id, parent_status, state_id, district_id,
                    state_names.get(state_id or ""), district_names.get(district_id or ""),
                    "point", dataset_id, population, 1,
                    f"GeoNames {parts[7]} point. No municipal polygon is stored.",
                ))
                geometry_rows.append((
                    place_id,
                    json.dumps({"type": "Point", "coordinates": [lon, lat]}),
                    lon, lat, lon, lat, lon, lat,
                ))
                alias_rows.append((place_id, parts[1], normalize_name(parts[1]), "", "geonames"))
                if parts[2] and normalize_name(parts[2]) != normalize_name(parts[1]):
                    alias_rows.append((place_id, parts[2], normalize_name(parts[2]), "en", "geonames_ascii"))
                geoname_to_place[geonameid] = place_id
                seen += 1
                if seen % 100000 == 0:
                    print(f"read {seen} {iso2} populated places", flush=True)
    if seen < spec["min_cities"]:
        raise GeoResolveError(f"Only {seen} populated places were read from {iso2}.txt")
    conn.executemany(
        """
        INSERT INTO place (
          id, source_namespace, source_feature_id, canonical_name, level, feature_type,
          country_code, admin1_code, admin2_code, parent_id, parent_status, state_place_id,
          district_place_id, state_name, district_name, representation, dataset_id, population, active, note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        place_rows,
    )
    conn.executemany(
        "INSERT INTO geometry (place_id, geojson, bbox_w, bbox_s, bbox_e, bbox_n, anchor_lon, anchor_lat) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        geometry_rows,
    )
    conn.executemany(
        "INSERT OR IGNORE INTO alias (place_id, alias, normalized, language, source) VALUES (?, ?, ?, ?, ?)",
        [row for row in alias_rows if row[2]],
    )
    _import_alternate_names(conn, geoname_to_place, iso2)
    print(f"imported {seen} {iso2} populated places", flush=True)


def _import_alternate_names(conn: sqlite3.Connection, geoname_to_place: dict[str, str], iso2: str) -> None:
    spec = COUNTRIES[iso2]
    rows = []
    with zipfile.ZipFile(DOWNLOADS / f"alternatenames-{iso2}.zip") as archive:
        member = f"{iso2}.txt" if f"{iso2}.txt" in archive.namelist() else archive.namelist()[-1]
        with archive.open(member) as handle:
            for raw in handle:
                parts = raw.decode("utf-8").rstrip("\n").split("\t")
                if len(parts) < 8:
                    raise GeoResolveError("GeoNames alternate-name row is missing the documented columns")
                if not parts[1].isdigit():
                    continue
                language = parts[2]
                if language not in spec["alternate_languages"]:
                    continue
                historic = parts[7] if len(parts) > 7 else ""
                if historic == "1" and not spec["include_historic_aliases"]:
                    continue
                place_id = geoname_to_place.get(parts[1])
                if not place_id:
                    continue
                normalized = normalize_name(parts[3])
                if len(normalized) < 2:
                    continue
                if historic == "1":
                    source = "geonames_alternate_historic"
                elif language:
                    source = "geonames_alternate"
                else:
                    source = "geonames_alternate_unspecified"
                rows.append((place_id, parts[3], normalized, language, source))
    conn.executemany(
        "INSERT OR IGNORE INTO alias (place_id, alias, normalized, language, source) VALUES (?, ?, ?, ?, ?)",
        rows,
    )



def reindex_aliases(path: Path | None = None) -> int:
    """Recompute normalised aliases in place. Alias text, language, and source stay put."""
    conn = connect(path or ACTIVE_PATH, readonly=False)
    try:
        rows = conn.execute("SELECT rowid, alias FROM alias").fetchall()
        conn.execute("BEGIN")
        conn.executemany(
            "UPDATE alias SET normalized=? WHERE rowid=?",
            [(normalize_name(row["alias"]), row["rowid"]) for row in rows if normalize_name(row["alias"])],
        )
        conn.commit()
        return conn.execute("SELECT COUNT(*) FROM alias").fetchone()[0]
    finally:
        conn.close()


def _apply_curated(conn: sqlite3.Connection) -> None:
    if not CURATED_PATH.is_file():
        return
    document = json.loads(CURATED_PATH.read_text(encoding="utf-8"))
    for entry in document.get("aliases") or []:
        row = conn.execute(
            "SELECT id FROM place WHERE source_namespace=? AND source_feature_id=?",
            (entry["source_namespace"], str(entry["source_feature_id"])),
        ).fetchone()
        if not row:
            continue
        _add_alias(conn, row["id"], entry["alias"], entry.get("language"), entry.get("source") or "curated")


def _row_to_summary(row: sqlite3.Row, aliases: list[dict] | None = None) -> dict:
    summary = {
        "id": row["id"],
        "name": row["canonical_name"],
        "level": row["level"],
        "feature_type": row["feature_type"],
        "country_code": row["country_code"],
        "admin_label": admin_label_for(row["country_code"]),
        "level_label": level_label(row["level"], row["country_code"]),
        "parent_id": row["parent_id"],
        "parent_status": row["parent_status"],
        "state_name": row["state_name"],
        "state_place_id": row["state_place_id"],
        "district_name": row["district_name"],
        "representation": "point" if row["representation"] == "point" else "boundary",
        "geometry_kind": row["representation"],
        "source_namespace": row["source_namespace"],
        "source_feature_id": row["source_feature_id"],
        "note": row["note"],
        "aliases": aliases or [],
    }
    return summary


def _aliases_for(conn: sqlite3.Connection, place_id: str, limit: int = 8) -> list[dict]:
    rows = conn.execute(
        """
        SELECT alias, language, source FROM alias
        WHERE place_id=?
        ORDER BY CASE language WHEN 'hi' THEN 0 WHEN 'en' THEN 1 ELSE 2 END, alias
        LIMIT ?
        """,
        (place_id, limit),
    ).fetchall()
    return [{"alias": row["alias"], "language": row["language"] or None, "source": row["source"]} for row in rows]


def _load_places(conn: sqlite3.Connection, ids: list[str]) -> list[sqlite3.Row]:
    if not ids:
        return []
    marks = ",".join("?" for _ in ids)
    return list(conn.execute(f"SELECT * FROM place WHERE id IN ({marks}) AND active=1", ids))


def lookup(
    name: str,
    *,
    country: str | None = None,
    state: str | None = None,
    district: str | None = None,
    level: str | None = None,
    catalog_path: Path | None = None,
) -> dict:
    """Exact alias match. Similar spellings stay suggestions until a fallback accepts one."""
    conn = connect(catalog_path, readonly=True)
    try:
        return _lookup(conn, name, country=country, state=state, district=district, level=level)
    finally:
        conn.close()


def resolve_country_token(conn: sqlite3.Connection, value: str | None) -> dict:
    """Map a country name or ISO code to one installed country. ISO-3 becomes ISO-2."""
    empty = {"country_code": None, "place_id": None, "recognized": False, "ambiguous": False}
    if not value or not str(value).strip():
        return empty
    token_iso = iso_for_token(value)
    ids = _ids_at_level(conn, value, "country")
    if token_iso:
        spec = COUNTRIES[token_iso]
        row = conn.execute(
            "SELECT id, country_code FROM place WHERE id=? AND active=1 AND level='country'",
            (spec["place_id"],),
        ).fetchone()
        if row:
            return {"country_code": row["country_code"], "place_id": row["id"], "recognized": True, "ambiguous": False}
        matched = []
        for place_id in ids:
            row = conn.execute("SELECT id, country_code FROM place WHERE id=?", (place_id,)).fetchone()
            if row and row["country_code"] == token_iso:
                matched.append(row)
        if len(matched) == 1:
            return {"country_code": matched[0]["country_code"], "place_id": matched[0]["id"], "recognized": True, "ambiguous": False}
        return {"country_code": token_iso, "place_id": None, "recognized": True, "ambiguous": False}
    if len(ids) == 1:
        row = conn.execute("SELECT country_code FROM place WHERE id=?", (ids[0],)).fetchone()
        return {
            "country_code": row["country_code"] if row else None,
            "place_id": ids[0],
            "recognized": bool(row and row["country_code"]),
            "ambiguous": False,
        }
    if len(ids) > 1:
        return {"country_code": None, "place_id": None, "recognized": True, "ambiguous": True}
    return empty


def _country_ok(place: sqlite3.Row, country: str | None, resolved: dict | None = None) -> bool:
    if not country:
        return True
    if not resolved or not resolved.get("recognized") or resolved.get("ambiguous") or not resolved.get("country_code"):
        return False
    return place["country_code"] == resolved["country_code"]


def _text_ok(value: str | None, expected: str | None) -> bool:
    if not expected:
        return True
    if not value:
        return False
    return normalize_name(value) == normalize_name(expected)


def _state_ids_for_name(conn: sqlite3.Connection, state: str, country_code: str | None = None) -> list[str]:
    """Canonical state ids for a name. More than one id stays unresolved."""
    return _ids_at_level(conn, state, "state", country_code)


def _alias_hit(conn: sqlite3.Connection, place_id: str | None, expected: str | None) -> bool:
    """True when expected is an alias of place_id, including a Hindi name for an English canonical row."""
    if not place_id or not expected:
        return False
    return conn.execute(
        "SELECT 1 FROM alias WHERE place_id=? AND normalized=? LIMIT 1",
        (place_id, normalize_name(expected)),
    ).fetchone() is not None


def _lookup(conn: sqlite3.Connection, name: str, *, country, state, district, level) -> dict:
    query = {"name": name, "country": country, "state": state, "district": district, "level": level}
    normalized = normalize_name(name)
    if len(normalized) < 2:
        return {"status": "not_found", "reason": "The place name is too short to match.", "query": query, "place": None, "candidates": []}
    ids = [row["place_id"] for row in conn.execute("SELECT DISTINCT place_id FROM alias WHERE normalized=?", (normalized,))]
    places = _load_places(conn, ids)
    if not places:
        suggestion_country = None
        if country:
            suggestion = resolve_country_token(conn, country)
            if not suggestion["recognized"] or suggestion["ambiguous"]:
                return _not_found("The catalogue has no single country matching that constraint.", query, [], conn)
            suggestion_country = suggestion["country_code"]
        return {
            "status": "not_found",
            "reason": "No exact canonical name or alias matched. Similar spellings are suggestions, not identity.",
            "query": query,
            "place": None,
            "candidates": _fuzzy_candidates(conn, normalized, suggestion_country),
        }
    resolved_country = resolve_country_token(conn, country) if country else None
    if country and (not resolved_country or not resolved_country.get("recognized") or resolved_country.get("ambiguous")):
        return _not_found("The catalogue has no single country matching that constraint.", query, [], conn)
    places = [place for place in places if _country_ok(place, country, resolved_country)]
    if not places:
        return _not_found("No match is in the requested country.", query, [], conn)
    country_code = resolved_country.get("country_code") if resolved_country else None
    if state:
        state_ids = _state_ids_for_name(conn, state, country_code)
        if len(state_ids) == 1:
            state_id = state_ids[0]
            state_hits = [
                place for place in places
                if place["id"] == state_id
                or place["state_place_id"] == state_id
                or place["parent_id"] == state_id
            ]
        else:
            state_hits = [
                place for place in places
                if _text_ok(place["state_name"], state)
                or _text_ok(place["canonical_name"], state)
                or _alias_hit(conn, place["state_place_id"], state)
                or (place["level"] == "state" and _alias_hit(conn, place["id"], state))
            ]
        if state_hits:
            places = state_hits
        else:
            return _not_found("None of the exact matches are in the requested state.", query, places, conn)
    if district:
        district_hits = [
            place for place in places
            if _text_ok(place["district_name"], district)
            or (place["level"] == "district" and (_text_ok(place["canonical_name"], district) or _alias_hit(conn, place["id"], district)))
            or _alias_hit(conn, place["district_place_id"], district)
        ]
        if district_hits:
            places = district_hits
        else:
            return _not_found("None of the exact matches are in the requested district.", query, places, conn)
    if level:
        level_hits = [place for place in places if place["level"] == level]
        if level_hits:
            places = level_hits
        else:
            return _not_found(
                f"Exact matches exist, but not at the requested level '{level}'. A district is not being substituted for a city.",
                query, places, conn,
            )
    if len(places) == 1:
        place = places[0]
        if place["representation"] not in {"point", "polygon", "multipolygon"}:
            return {
                "status": "unsupported_representation",
                "reason": f"{place['canonical_name']} has representation {place['representation']}, which the renderer cannot draw.",
                "query": query,
                "place": _row_to_summary(place, _aliases_for(conn, place["id"])),
                "candidates": [],
            }
        reason = f"Exact alias match for {place['canonical_name']} ({place['level']}, {place['representation']})."
        if place["feature_type"] == "national_capital_territory":
            reason += " This is the National Capital Territory boundary, not a city or municipal polygon."
        if place["representation"] == "point":
            reason += " Only a verified point is available; no city boundary is invented."
        return {
            "status": "resolved",
            "reason": reason,
            "query": query,
            "place": _row_to_summary(place, _aliases_for(conn, place["id"])),
            "candidates": [],
        }
    summaries = [_row_to_summary(place, _aliases_for(conn, place["id"], 4)) for place in places[:8]]
    return {
        "status": "ambiguous",
        "reason": "More than one exact match remains after country, state, district, and level filters. Population was not used to choose.",
        "query": query,
        "place": None,
        "candidates": summaries,
    }


def _not_found(reason: str, query: dict, places: list[sqlite3.Row], conn: sqlite3.Connection) -> dict:
    return {
        "status": "not_found",
        "reason": reason,
        "query": query,
        "place": None,
        "candidates": [_row_to_summary(place, _aliases_for(conn, place["id"], 3)) for place in places[:8]],
    }


def _fuzzy_hits(
    conn: sqlite3.Connection,
    normalized: str,
    *,
    level: str | None = None,
    country_code: str | None = None,
    min_score: float = FUZZY_CANDIDATE_SCORE,
) -> list[tuple[int, sqlite3.Row, str]]:
    """Places whose best alias reaches min_score. Highest score first. Not an identity."""
    from rapidfuzz import fuzz
    if len(normalized) < 2:
        return []
    prefix = normalized[:2]
    upper = prefix[:-1] + chr(ord(prefix[-1]) + 1)
    shortest = max(2, (len(normalized) * 2) // 3)
    longest = (len(normalized) * 3) // 2 + 1
    sql = """
        SELECT alias.place_id, alias.alias, alias.normalized
        FROM alias
        JOIN place ON place.id = alias.place_id
        WHERE place.active = 1
          AND alias.normalized >= ? AND alias.normalized < ?
          AND length(alias.normalized) BETWEEN ? AND ?
    """
    params: list[object] = [prefix, upper, shortest, longest]
    if level:
        sql += " AND place.level = ?"
        params.append(level)
    if country_code:
        sql += " AND place.country_code = ?"
        params.append(country_code)
    best: dict[str, tuple[float, str]] = {}
    for row in conn.execute(sql, params):
        score = float(fuzz.ratio(normalized, row["normalized"]))
        if score < min_score:
            continue
        current = best.get(row["place_id"])
        if current is None or score > current[0]:
            best[row["place_id"]] = (score, row["alias"])
    if not best:
        return []
    loaded = {row["id"]: row for row in _load_places(conn, list(best))}
    hits = []
    for place_id, (score, alias) in best.items():
        place = loaded.get(place_id)
        if place is not None:
            hits.append((int(round(score)), place, alias))
    hits.sort(key=lambda item: item[0], reverse=True)
    return hits


def _fuzzy_candidates(conn: sqlite3.Connection, normalized: str, country_code: str | None = None) -> list[dict]:
    from rapidfuzz import fuzz
    prefix = normalized[:2]
    span = max(2, len(normalized))
    rows = conn.execute(
        """
        SELECT place_id, alias, normalized FROM alias
        WHERE normalized >= ? AND normalized < ?
          AND length(normalized) BETWEEN ? AND ?
        LIMIT 1500
        """,
        (prefix, prefix[:-1] + chr(ord(prefix[-1]) + 1) if prefix else prefix, span - 2, span + 2),
    ).fetchall()
    scored = []
    for row in rows:
        score = fuzz.ratio(normalized, row["normalized"])
        if score >= 70:
            scored.append((score, row["place_id"], row["alias"]))
    scored.sort(key=lambda item: item[0], reverse=True)
    results = []
    seen = set()
    for score, place_id, alias in scored:
        if place_id in seen:
            continue
        seen.add(place_id)
        place = conn.execute("SELECT * FROM place WHERE id=? AND active=1", (place_id,)).fetchone()
        if not place:
            continue
        if country_code and place["country_code"] != country_code:
            continue
        summary = _row_to_summary(place, [{"alias": alias, "language": None, "source": "fuzzy_suggestion"}])
        summary["fuzzy_score"] = score
        summary["suggestion_only"] = True
        results.append(summary)
        if len(results) >= 5:
            break
    return results


_LEVEL_CUES = {
    "district": "district",
    "dist": "district",
    "जिला": "district",
    "ज़िला": "district",
    "city": "city",
    "शहर": "city",
    "state": "state",
    "राज्य": "state",
    "territory": "state",
}
# Single tokens that are ordinary English words. Longer aliases such as
# "New York City" are still matched.
_MENTION_STOPWORDS = {
    "area", "capital", "city", "district", "east", "inside", "map", "named",
    "north", "northern", "region", "route", "south", "southern", "state",
    "stop", "west",
}


def exact_mentions(text: str, *, catalog_path: Path | None = None) -> list[dict]:
    """Exact alias mentions in reading order. Short tokens such as 'in' are ignored."""
    conn = connect(catalog_path, readonly=True)
    try:
        return _exact_mentions(conn, text)
    finally:
        conn.close()


def _exact_mentions(conn: sqlite3.Connection, text: str) -> list[dict]:
    tokens = [
        (match.group(0), match.start(), match.end())
        for match in re.finditer(r"(?:[^\W\d_]|[\u0900-\u0963\u0966-\u097F])+", text or "", flags=re.UNICODE)
    ]
    candidates = []
    for size in range(1, 6):
        for index in range(0, len(tokens) - size + 1):
            words = tokens[index:index + size]
            raw = [word for word, _start, _end in words]
            level = None
            end = words[-1][2]
            if raw[-1].casefold() in _LEVEL_CUES and len(raw) > 1:
                level = _LEVEL_CUES[raw[-1].casefold()]
                raw = raw[:-1]
            elif index + size < len(tokens) and tokens[index + size][0].casefold() in _LEVEL_CUES:
                level = _LEVEL_CUES[tokens[index + size][0].casefold()]
                end = tokens[index + size][2]
            phrase = " ".join(raw)
            if len(raw) == 1 and phrase.casefold() in _MENTION_STOPWORDS:
                continue
            if len(normalize_name(phrase)) < 4:
                continue
            normalized = normalize_name(phrase)
            hit = conn.execute(
                "SELECT 1 FROM alias WHERE normalized=? LIMIT 1",
                (normalized,),
            ).fetchone()
            if not hit:
                continue
            candidates.append((words[0][1], end, len(raw), phrase, level))
    candidates.sort(key=lambda item: (item[0], -item[2]))
    chosen = []
    cursor = -1
    for start, end, _size, phrase, level in candidates:
        if start < cursor:
            continue
        chosen.append({"name": phrase, "level": level, "start": start, "end": end})
        cursor = end
    return chosen


_ESSENTIAL_LEVELS = {"country", "state", "district", "city"}
_SUPPORTING_CUES = (
    "नदी", "खाड़ी", "खाडी", "सागर", "पुल", "ब्रिज", "मंदिर", "मन्दिर",
    "झील", "पैलेस", "महल", "चोटी", "किला",
    "river", "bay", "bridge", "temple", "lake", "gulf", "strait",
    "palace", "peak", "sea", "fort",
)


def _supporting_tokens(name: str) -> bool:
    """Match a feature word as its own token, including when selection stored it as a city."""
    cues = {cue.casefold() for cue in _SUPPORTING_CUES}
    tokens = re.findall(r"[a-z]+|[\u0900-\u097F]+", name.casefold())
    return any(token in cues for token in tokens)


def is_supporting_detail(result: dict) -> bool:
    """Rivers, bays, bridges, temples, and unnamed-level landmarks are optional.

    Selection only allows country, state, district and city, so a river can arrive
    with level=city. The name token decides; a real city name does not match.
    A request with no administrative level, such as a peak, is context only.
    """
    requested = result.get("requested") or result.get("query") or {}
    if _supporting_tokens(str(requested.get("name") or "")):
        return True
    return requested.get("level") not in _ESSENTIAL_LEVELS


def supporting_mentions(text: str) -> list[str]:
    """Supporting phrases named in narration, such as हावड़ा ब्रिज or स्वर्ण मंदिर."""
    cues = {cue.casefold() for cue in _SUPPORTING_CUES}
    leading = {
        "के", "की", "में", "और", "से", "पर", "जो", "यह", "यहाँ", "वहाँ", "का", "को",
        "ने", "है", "हैं", "एक", "जहाँ", "the", "of", "a", "an", "in", "on", "and", "here",
    }
    tokens = list(re.finditer(r"[A-Za-z]+|[\u0900-\u097F]+", text or ""))
    connectors = {"की", "के", "का", "of"}
    found = []
    for index, token in enumerate(tokens):
        if token.group(0).casefold() not in cues:
            continue
        start = index
        taken = 0
        cursor = index - 1
        while cursor >= 0 and taken < 3:
            word = tokens[cursor].group(0).casefold()
            if word in leading and word not in connectors:
                break
            if word in connectors:
                previous = tokens[cursor - 1].group(0).casefold() if cursor else ""
                if not previous or previous in leading:
                    break
            start = cursor
            taken += 1
            cursor -= 1
        words = [tokens[pos].group(0) for pos in range(start, index + 1)]
        while len(words) > 1 and words[0].casefold() in leading:
            words.pop(0)
        phrase = " ".join(words)
        if phrase and phrase not in found:
            found.append(phrase)
    return found


def passage_omissions(passage: str, covered_names: list[str]) -> tuple[list[str], list[dict]]:
    """Warnings for supporting phrases that were not resolved and must not be drawn."""
    covered = [str(name) for name in covered_names if name]
    warnings = []
    omitted = []
    for phrase in supporting_mentions(passage):
        if any(phrase in name or name in phrase for name in covered):
            continue
        warnings.append(
            f"Omitted {phrase}: supporting detail is not in the catalogue. "
            "No geometry was invented and nothing was drawn for it."
        )
        omitted.append({
            "name": phrase,
            "status": "omitted",
            "reason": "Supporting detail is not in the catalogue.",
        })
        covered.append(phrase)
    return warnings, omitted


def apply_feature_policy(results: list[dict]) -> dict:
    """Keep a resolved city when a river or bay is missing. Do not invent that feature."""
    review_statuses = {"needs_review", "fallback_unavailable"}
    resolved = [item for item in results if item.get("status") == "resolved"]
    review_items = [item for item in results if item.get("status") in review_statuses]
    optional_review = [item for item in review_items if is_supporting_detail(item)]
    essential_review = [item for item in review_items if not is_supporting_detail(item)]
    omitted = [
        item for item in results
        if item.get("status") not in {"resolved", *review_statuses} and is_supporting_detail(item)
    ]
    blockers = [
        item for item in results
        if item.get("status") not in {"resolved", *review_statuses} and not is_supporting_detail(item)
    ]
    subjects = [
        item for item in resolved
        if (item.get("place") or {}).get("level") in {"city", "state", "district"}
    ]
    warnings = [
        (
            f"Omitted {((item.get('requested') or {}).get('name') or 'feature')}: "
            f"{str(item.get('reason') or 'not in the catalogue').rstrip('.')}. "
            "No geometry was invented and nothing was drawn for it."
        )
        for item in omitted
    ]
    for item in optional_review:
        warnings.append(
            f"{((item.get('requested') or {}).get('name') or 'feature')}: "
            f"{str(item.get('reason') or item.get('status')).rstrip('.')}. "
            "The feature was left off the map."
        )
    omitted_features = [
        {
            "name": (item.get("requested") or {}).get("name"),
            "status": item.get("status"),
            "reason": item.get("reason"),
        }
        for item in omitted + optional_review
    ]
    if essential_review:
        status = (
            "fallback_unavailable"
            if any(item.get("status") == "fallback_unavailable" for item in essential_review)
            else "needs_review"
        )
        return {
            "status": status,
            "resolved": resolved,
            "omitted": omitted + optional_review,
            "omitted_features": omitted_features,
            "blockers": essential_review + blockers,
            "warnings": warnings,
            "explanation": essential_review[0].get("reason") or status,
        }
    if blockers:
        return {
            "status": "blocked",
            "resolved": resolved,
            "omitted": omitted,
            "omitted_features": omitted_features,
            "blockers": blockers,
            "warnings": warnings,
            "explanation": None,
        }
    if not subjects:
        names = ", ".join(
            str((item.get("requested") or {}).get("name") or "")
            for item in omitted
            if (item.get("requested") or {}).get("name")
        )
        return {
            "status": "review",
            "resolved": resolved,
            "omitted": omitted,
            "omitted_features": omitted_features,
            "blockers": [],
            "warnings": warnings,
            "explanation": (
                "This passage has no city, state, or district in the catalogue. "
                + (f"Unsupported details ({names}) were not used as a substitute." if names else "Nothing mappable was resolved.")
            ),
        }
    return {
        "status": "ready",
        "resolved": resolved,
        "omitted": omitted,
        "omitted_features": omitted_features,
        "blockers": blockers,
        "warnings": warnings,
        "explanation": None,
    }


_ADMIN_LEVELS = ("country", "state", "district")


def _ids_at_level(conn: sqlite3.Connection, name: str, level: str, country_code: str | None = None) -> list[str]:
    normalized = normalize_name(name or "")
    if len(normalized) < 2:
        return []
    sql = """
        SELECT DISTINCT place.id
        FROM place
        JOIN alias ON alias.place_id = place.id
        WHERE place.level=? AND place.active=1 AND alias.normalized=?
    """
    params: list[object] = [level, normalized]
    if country_code:
        sql += " AND place.country_code=?"
        params.append(country_code)
    return [row["id"] for row in conn.execute(sql, params)]


def classify_request_constraints(conn: sqlite3.Connection, request: dict) -> dict:
    """Turn a parent hint into a country, state, or district constraint.

    An exact administrative match is verified. A hint that does not match
    exactly stays inferred and is not applied as a hard filter.
    """
    parent = str(request.get("parent_name") or "").strip() or None
    country = str(request.get("country") or "").strip() or None
    state = str(request.get("state") or "").strip() or None
    district = str(request.get("district") or "").strip() or None
    level = request.get("level")
    country_id = state_id = district_id = None
    country_code = None
    inferred = None
    contradiction = None
    verified = {"country": False, "state": False, "district": False}

    def take_country(value: str | None, *, explicit: bool) -> None:
        nonlocal country, country_id, country_code
        if not value or verified["country"]:
            return
        resolved = resolve_country_token(conn, value)
        if resolved["recognized"] and not resolved["ambiguous"]:
            country = value
            country_id = resolved["place_id"]
            country_code = resolved["country_code"]
            verified["country"] = True
            return
        if explicit:
            country = value
            verified["country"] = True

    take_country(country, explicit=True)
    if state:
        ids = _ids_at_level(conn, state, "state", country_code)
        if len(ids) == 1:
            state_id = ids[0]
            verified["state"] = True
        else:
            verified["state"] = True
    if district:
        ids = _ids_at_level(conn, district, "district", country_code)
        if len(ids) == 1:
            district_id = ids[0]
            verified["district"] = True
        else:
            verified["district"] = True

    parent_entity = None
    membership_verified = bool(verified["state"] or verified["district"])
    relationship_source = "user_confirmed" if membership_verified else "none"
    if parent:
        parent_ids = {
            admin: _ids_at_level(conn, parent, admin, None if admin == "country" else country_code)
            for admin in _ADMIN_LEVELS
        }
        unique = {admin: ids[0] for admin, ids in parent_ids.items() if len(ids) == 1}
        if len(unique) == 1:
            admin, admin_id = next(iter(unique.items()))
            if admin == "country":
                if verified["country"] and country_id and country_id != admin_id:
                    contradiction = "Verified country contradicts the parent hint."
                elif not verified["country"]:
                    country, country_id = parent, admin_id
                    row = conn.execute("SELECT country_code FROM place WHERE id=?", (admin_id,)).fetchone()
                    country_code = row["country_code"] if row else None
                    verified["country"] = True
            elif admin == "state" and level != "country":
                parent_entity = {"id": admin_id, "level": "state", "name": parent, "relationship": "mentioned_with"}
                inferred = parent
                if membership_verified and verified["state"] and state_id and state_id != admin_id:
                    contradiction = "The confirmed state conflicts with the named parent. The confirmed state was kept."
            elif admin == "district" and level in {None, "city", "settlement", "district"}:
                parent_entity = {"id": admin_id, "level": "district", "name": parent, "relationship": "mentioned_with"}
                inferred = parent
                if membership_verified and verified["district"] and district_id and district_id != admin_id:
                    contradiction = "The confirmed district conflicts with the named parent. The confirmed district was kept."
        else:
            inferred = parent
        if relationship_source == "none" and (parent_entity or inferred):
            relationship_source = "inferred"
    return {
        "country": country,
        "state": state if verified["state"] else None,
        "district": district if verified["district"] else None,
        "country_id": country_id,
        "country_code": country_code,
        "state_id": state_id,
        "district_id": district_id,
        "inferred_parent": inferred,
        "parent_entity": parent_entity,
        "relationship_source": relationship_source,
        "membership_verified": membership_verified,
        "verified": verified,
        "contradiction": contradiction,
    }


def resolve_requests(requests: list[dict], *, catalog_path: Path | None = None) -> list[dict]:
    """Resolve place requests offline. A parent hint is used only when it matches one admin unit."""
    conn = connect(catalog_path, readonly=True)
    try:
        resolved_state_ids: list[str] = []
        output = []
        for request in requests:
            name = str(request.get("name") or "").strip()
            level = request.get("level")
            parent_name = request.get("parent_name")
            country = request.get("country")
            context = classify_request_constraints(conn, request)
            result = _lookup(
                conn, name,
                country=context["country"],
                state=context["state"],
                district=context["district"],
                level=level,
            )
            if result["status"] == "ambiguous" and resolved_state_ids and not context["state_id"]:
                narrowed = [
                    candidate for candidate in result["candidates"]
                    if candidate.get("state_place_id") in resolved_state_ids or candidate.get("id") in resolved_state_ids
                ]
                if len(narrowed) == 1:
                    result = {
                        "status": "resolved",
                        "reason": result["reason"] + " Narrowed using the canonical parent already resolved in this clip.",
                        "query": result["query"],
                        "place": narrowed[0],
                        "candidates": [],
                    }
            result["requested"] = {
                "name": name,
                "level": level,
                "parent_name": parent_name,
                "country": country,
                "state": request.get("state"),
                "district": request.get("district"),
                "request_id": request.get("request_id"),
                "fingerprint": request.get("fingerprint"),
            }
            result["context"] = context
            result["local_status"] = result["status"]
            output.append(result)
            place = result.get("place")
            if result["status"] == "resolved" and place and place.get("level") == "state" and place.get("id"):
                resolved_state_ids.append(place["id"])
        return output
    finally:
        conn.close()


def planner_summaries(results: list[dict], *, catalog_path: Path | None = None) -> list[dict]:
    """Verified place cards for DeepSeek. No coordinates and no geometry."""
    conn = connect(catalog_path, readonly=True)
    try:
        cards = []
        seen = set()
        for result in results:
            place = result.get("place")
            if result.get("status") != "resolved" or not place:
                continue
            if place.get("source") == "user_provided":
                if place["id"] not in seen:
                    cards.append({
                        "id": place["id"],
                        "name": place.get("name"),
                        "level": place.get("level") or "city",
                        "feature_type": "user_provided_point",
                        "parent_id": None,
                        "state_name": None,
                        "district_name": None,
                        "representation": "point",
                        "country_code": place.get("country_code"),
                        "aliases": [],
                        "role": "subject",
                        "source": "user_provided",
                        "supported_actions": ["show_marker", "show_label", "show_callout"],
                    })
                    seen.add(place["id"])
                continue
            if place["id"] not in seen:
                cards.append(_planner_card(place, role="subject"))
                seen.add(place["id"])
            for ancestor in _ancestors(conn, place["id"]):
                if ancestor["id"] in seen:
                    continue
                cards.append(ancestor)
                seen.add(ancestor["id"])
        return cards
    finally:
        conn.close()


def _planner_card(place: dict, *, role: str) -> dict:
    return {
        "id": place["id"],
        "name": place["name"],
        "level": place["level"],
        "feature_type": place["feature_type"],
        "parent_id": place.get("parent_id"),
        "state_name": place.get("state_name"),
        "district_name": place.get("district_name"),
        "representation": place.get("representation"),
        "country_code": place.get("country_code"),
        "aliases": [item.get("alias") for item in place.get("aliases") or []][:6],
        "role": role,
        "supported_actions": ["show_marker", "show_label", "show_callout", "zoom_to_boundary"]
        if place.get("representation") == "point"
        else ["highlight", "zoom_to_boundary", "show_label", "show_callout"],
    }


def _ancestors(conn: sqlite3.Connection, place_id: str) -> list[dict]:
    cards = []
    current = place_id
    guard = 0
    while current and guard < 5:
        guard += 1
        row = conn.execute("SELECT * FROM place WHERE id=?", (current,)).fetchone()
        if not row or not row["parent_id"] or row["parent_status"] in {"conflict", "unresolved", "unresolved_boundary"}:
            # Still expose a verified state/country orientation when those ids exist.
            if row and row["state_place_id"] and row["state_place_id"] != current:
                state = conn.execute("SELECT * FROM place WHERE id=?", (row["state_place_id"],)).fetchone()
                if state:
                    cards.append(_planner_card(_row_to_summary(state, _aliases_for(conn, state["id"])), role="orientation"))
            break
        parent = conn.execute("SELECT * FROM place WHERE id=?", (row["parent_id"],)).fetchone()
        if not parent:
            break
        cards.append(_planner_card(_row_to_summary(parent, _aliases_for(conn, parent["id"])), role="orientation"))
        current = parent["id"]
    origin = conn.execute("SELECT country_code FROM place WHERE id=?", (place_id,)).fetchone()
    if origin and origin["country_code"]:
        country = conn.execute(
            "SELECT * FROM place WHERE level='country' AND country_code=? AND active=1",
            (origin["country_code"],),
        ).fetchone()
        if country and all(card["id"] != country["id"] for card in cards):
            cards.append(_planner_card(_row_to_summary(country, _aliases_for(conn, country["id"])), role="orientation"))
    return cards


def resolve_catalog_places(
    semantic: dict,
    catalog_path: Path | None = None,
    extras: dict | None = None,
) -> dict[str, dict]:
    conn = connect(catalog_path, readonly=True)
    try:
        resolved: dict[str, dict] = {}
        remaining = {place["id"]: place for place in semantic["places"]}
        supplied = extras or {}
        progress = True
        while remaining and progress:
            progress = False
            for pid, spec in list(remaining.items()):
                parent = spec.get("parent")
                if parent and parent in remaining:
                    continue
                if pid in supplied:
                    resolved[pid] = _resolve_user_point(spec, supplied[pid])
                else:
                    resolved[pid] = _resolve_catalog_place(conn, spec, resolved)
                del remaining[pid]
                progress = True
        if remaining:
            raise GeoResolveError(f"Could not resolve catalogue places: {list(remaining)}")
        return resolved
    finally:
        conn.close()


def _resolve_user_point(spec: dict, extra: dict) -> dict:
    """A manually supplied coordinate. No polygon is created for it."""
    from shapely.geometry import Point, mapping, shape

    geometry = extra.get("geometry") or {}
    if geometry.get("type") != "Point":
        raise GeoResolveError(f"Custom place '{spec.get('id')}' must be a point.")
    coordinates = geometry.get("coordinates") or []
    if len(coordinates) != 2:
        raise GeoResolveError(f"Custom place '{spec.get('id')}' needs longitude and latitude.")
    lon, lat = float(coordinates[0]), float(coordinates[1])
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise GeoResolveError(f"Custom place '{spec.get('id')}' has coordinates outside the valid range.")
    geom = shape(geometry)
    if geom.geom_type != "Point":
        raise GeoResolveError(f"Custom place '{spec.get('id')}' is not a point.")
    name = extra.get("name") or spec.get("name")
    feature = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"id": spec["id"], "name": name, "level": "city", "source": "user_provided"},
            "geometry": mapping(geom if geom.equals(Point(lon, lat)) else Point(lon, lat)),
        }],
    }
    point = Point(lon, lat)
    return {
        "id": spec["id"],
        "requested_id": spec["id"],
        "name": name,
        "level": "city",
        "parent": None,
        "source_id": "user_provided",
        "source": "user_provided",
        "representation": "point",
        "geometry_kind": "point",
        "feature_type": "user_provided_point",
        "geojson": None,
        "feature": feature,
        "bbox": bbox_of(point),
        "anchor": representative_lonlat(point),
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "disambiguation": "Manually supplied point. Administrative context was not spatially verified.",
        "spatial_membership_verified": False,
    }


def _resolve_catalog_place(conn: sqlite3.Connection, spec: dict, resolved: dict[str, dict]) -> dict:
    pid = spec["id"]
    row = conn.execute("SELECT * FROM place WHERE id=? AND active=1", (pid,)).fetchone()
    if not row:
        raise GeoResolveError(f"Catalogue has no active place '{pid}'")
    aliases = {normalize_name(row["canonical_name"])}
    aliases.update(
        normalize_name(item["normalized"])
        for item in conn.execute("SELECT normalized FROM alias WHERE place_id=?", (pid,))
    )
    if normalize_name(spec.get("name") or "") not in aliases:
        raise GeoResolveError(
            f"Place id '{pid}' conflicts with name '{spec.get('name')}'. Catalogue name is '{row['canonical_name']}'."
        )
    if spec.get("level") != row["level"]:
        raise GeoResolveError(
            f"Place '{row['canonical_name']}' is level {row['level']}, not requested level {spec.get('level')}"
        )
    geom_row = conn.execute("SELECT geojson FROM geometry WHERE place_id=?", (pid,)).fetchone()
    if not geom_row:
        raise GeoResolveError(f"No geometry stored for {pid}")
    geom = shape(json.loads(geom_row["geojson"]))
    if row["representation"] == "point":
        if geom.geom_type != "Point":
            raise GeoResolveError(f"{pid} is marked as a point but the geometry is {geom.geom_type}")
    elif geom.geom_type not in {"Polygon", "MultiPolygon"}:
        raise GeoResolveError(f"Unsupported geometry {geom.geom_type} for {pid}")
    parent = spec.get("parent")
    if parent:
        if parent not in resolved:
            raise GeoResolveError(f"Parent '{parent}' must be resolved before '{pid}'")
        parent_geom = shape(resolved[parent]["geometry"])
        if geom.geom_type == "Point":
            if not parent_geom.buffer(0.15).covers(geom):
                raise GeoResolveError(f"Point '{pid}' does not lie within parent '{parent}'")
        elif not child_within_parent(geom, parent_geom):
            raise GeoResolveError(f"Feature '{pid}' does not lie within parent '{parent}'")
    feature = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"id": row["id"], "name": row["canonical_name"], "level": row["level"]},
            "geometry": mapping(geom),
        }],
    }
    anchor = representative_lonlat(geom)
    return {
        "id": row["id"],
        "requested_id": pid,
        "name": row["canonical_name"],
        "level": row["level"],
        "parent": parent or row["parent_id"],
        "source_id": f"{row['source_namespace']}:{row['source_feature_id']}",
        "representation": "point" if row["representation"] == "point" else "boundary",
        "geometry_kind": row["representation"],
        "feature_type": row["feature_type"],
        "geojson": None,
        "feature": feature,
        "bbox": bbox_of(geom),
        "anchor": anchor,
        "geometry": mapping(geom),
        "disambiguation": row["note"],
    }


def catalog_status(path: Path | None = None) -> dict:
    if STATUS_PATH.is_file() and path is None:
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    if not (path or ACTIVE_PATH).is_file():
        return {"installed": False, "limitations": ["Catalogue has not been imported."]}
    return write_status(path or ACTIVE_PATH)


def create_fixture(path: Path) -> None:
    """Small catalogue used by tests. Not the production India import."""
    if path.exists():
        path.unlink()
    conn = connect(path, readonly=False)
    init_schema(conn)
    dataset_id = _insert_dataset(conn, {
        "namespace": "fixture",
        "source_url": "fixture://local",
        "licence": "test",
        "version": "fixture",
        "boundary_year": "test",
        "attribution": "test",
        "limitations": "synthetic",
    }, "0" * 64, _utc_now())

    def add_poly(pid, name, level, feature_type, coords, parent, state_name, district_name, aliases):
        geom = shape({"type": "Polygon", "coordinates": [coords]})
        conn.execute(
            """
            INSERT INTO place (
              id, source_namespace, source_feature_id, canonical_name, level, feature_type,
              country_code, parent_id, parent_status, state_name, district_name, representation,
              dataset_id, active, note
            ) VALUES (?, 'fixture', ?, ?, ?, ?, 'IN', ?, 'verified', ?, ?, 'polygon', ?, 1, '')
            """,
            (pid, pid, name, level, feature_type, parent, state_name, district_name, dataset_id),
        )
        _store_geometry(conn, pid, geom)
        for alias, language in aliases:
            _add_alias(conn, pid, alias, language, "fixture")

    def add_point(pid, name, lon, lat, parent, state_id, state_name, district_name, aliases):
        conn.execute(
            """
            INSERT INTO place (
              id, source_namespace, source_feature_id, canonical_name, level, feature_type,
              country_code, parent_id, parent_status, state_place_id, state_name, district_name,
              representation, dataset_id, population, active, note
            ) VALUES (?, 'fixture', ?, ?, 'city', 'populated_place', 'IN', ?, 'verified', ?, ?, ?, 'point', ?, 1000, 1, 'point only')
            """,
            (pid, pid, name, parent, state_id, state_name, district_name, dataset_id),
        )
        _store_geometry(conn, pid, Point(lon, lat))
        for alias, language in aliases:
            _add_alias(conn, pid, alias, language, "fixture")

    india = [(68, 8), (78, 8), (78, 32), (68, 32), (68, 8)]
    gujarat = [(68.5, 20), (74.5, 20), (74.5, 24.5), (68.5, 24.5), (68.5, 20)]
    up = [(77, 24), (84, 24), (84, 30), (77, 30), (77, 24)]
    delhi = [(76.8, 28.4), (77.4, 28.4), (77.4, 28.9), (76.8, 28.9), (76.8, 28.4)]
    gorakhpur = [(83.1, 26.3), (83.8, 26.3), (83.8, 27.1), (83.1, 27.1), (83.1, 26.3)]
    add_poly("ne-adm0-ind", "India", "country", "country", india, None, None, None, [("India", "en"), ("भारत", "hi")])
    add_poly("gb-adm1-IN-GJ", "Gujarat", "state", "adm1_territory", gujarat, "ne-adm0-ind", "Gujarat", None, [("Gujarat", "en"), ("गुजरात", "hi")])
    add_poly("gb-adm1-IN-UP", "Uttar Pradesh", "state", "adm1_territory", up, "ne-adm0-ind", "Uttar Pradesh", None, [("Uttar Pradesh", "en"), ("उत्तर प्रदेश", "hi")])
    jk = [(74.2, 30.2), (76.2, 30.2), (76.2, 31.5), (74.2, 31.5), (74.2, 30.2)]
    add_poly("gb-adm1-IN-JK", "Jammu and Kashmir", "state", "adm1_territory", jk, "ne-adm0-ind", "Jammu and Kashmir", None, [("Jammu and Kashmir", "en"), ("जम्मू और कश्मीर", "hi")])
    add_poly("gb-adm1-IN-DL", "Delhi", "state", "national_capital_territory", delhi, "ne-adm0-ind", "Delhi", None, [("Delhi", "en"), ("दिल्ली", "hi"), ("National Capital Territory of Delhi", "en")])
    new_delhi = [(76.9, 28.5), (77.25, 28.5), (77.25, 28.75), (76.9, 28.75), (76.9, 28.5)]
    add_poly("gb-adm2-new-delhi", "New Delhi", "district", "district", new_delhi, "gb-adm1-IN-DL", "Delhi", "New Delhi", [("New Delhi", "en"), ("नई दिल्ली", "hi")])
    add_poly("gb-adm2-gorakhpur", "Gorakhpur", "district", "district", gorakhpur, "gb-adm1-IN-UP", "Uttar Pradesh", "Gorakhpur", [("Gorakhpur", "en"), ("गोरखपुर", "hi")])
    add_point("gn-vadnagar", "Vadnagar", 72.64, 23.79, "gb-adm1-IN-GJ", "gb-adm1-IN-GJ", "Gujarat", "Mahesana", [("Vadnagar", "en"), ("वडनगर", "hi")])
    add_point("gn-srinagar", "Srinagar", 74.8, 30.8, "gb-adm1-IN-JK", "gb-adm1-IN-JK", "Jammu and Kashmir", None, [("Srinagar", "en"), ("श्रीनगर", "hi")])
    add_point("gn-delhi-city", "Delhi", 77.1, 28.6, "gb-adm1-IN-DL", "gb-adm1-IN-DL", "Delhi", None, [("Delhi", "en"), ("दिल्ली", "hi")])
    add_point("gn-gorakhpur-city", "Gorakhpur", 83.37, 26.76, "gb-adm2-gorakhpur", "gb-adm1-IN-UP", "Uttar Pradesh", "Gorakhpur", [("Gorakhpur", "en"), ("गोरखपुर", "hi")])
    add_point("gn-rampur-up", "Rampur", 79.0, 28.8, "gb-adm1-IN-UP", "gb-adm1-IN-UP", "Uttar Pradesh", None, [("Rampur", "en")])
    add_point("gn-rampur-gj", "Rampur", 71.2, 22.2, "gb-adm1-IN-GJ", "gb-adm1-IN-GJ", "Gujarat", None, [("Rampur", "en")])
    add_point("gn-yamunanagar", "Yamunanagar", 80.0, 27.0, "gb-adm1-IN-UP", "gb-adm1-IN-UP", "Uttar Pradesh", None, [("Yamunanagar", "en"), ("यमुनानगर", "hi")])
    punjab = [(76.3, 29.2), (77.8, 29.2), (77.8, 31.2), (76.3, 31.2), (76.3, 29.2)]
    haryana = [(74.6, 27.2), (76.2, 27.2), (76.2, 28.2), (74.6, 28.2), (74.6, 27.2)]
    chandigarh = [(76.7, 30.6), (77.0, 30.6), (77.0, 30.9), (76.7, 30.9), (76.7, 30.6)]
    madhya = [(75.4, 21.4), (77.6, 21.4), (77.6, 23.6), (75.4, 23.6), (75.4, 21.4)]
    add_poly("gb-adm1-IN-PB", "Punjab", "state", "adm1_territory", punjab, "ne-adm0-ind", "Punjab", None, [("Punjab", "en"), ("पंजाब", "hi")])
    add_poly("gb-adm1-IN-HR", "Haryana", "state", "adm1_territory", haryana, "ne-adm0-ind", "Haryana", None, [("Haryana", "en"), ("हरियाणा", "hi")])
    add_poly("gb-adm1-IN-CH", "Chandigarh", "state", "union_territory", chandigarh, "ne-adm0-ind", "Chandigarh", None, [("Chandigarh", "en"), ("चंडीगढ़", "hi")])
    add_poly("gb-adm1-IN-MP", "Madhya Pradesh", "state", "adm1_territory", madhya, "ne-adm0-ind", "Madhya Pradesh", None, [("Madhya Pradesh", "en"), ("मध्य प्रदेश", "hi")])
    add_point("gn-chandigarh", "Chandigarh", 76.78, 30.74, "gb-adm1-IN-CH", "gb-adm1-IN-CH", "Chandigarh", None, [("Chandigarh", "en"), ("चंडीगढ़", "hi")])
    add_point("gn-gandhinagar", "Gandhinagar", 72.68, 23.22, "gb-adm1-IN-GJ", "gb-adm1-IN-GJ", "Gujarat", "Gandhinagar", [("Gandhinagar", "en")])
    add_point("gn-indore", "Indore", 75.86, 22.72, "gb-adm1-IN-MP", "gb-adm1-IN-MP", "Madhya Pradesh", "Indore", [("Indore", "en")])
    _ensure_indexes(conn)
    conn.commit()
    conn.close()


def add_regional_fixture(path: Path) -> None:
    """Pakistan and Afghanistan rows for tests. Does not alter the India fixture."""
    conn = connect(path, readonly=False)
    dataset_id = _insert_dataset(conn, {
        "namespace": "fixture-regional",
        "source_url": "fixture://regional",
        "licence": "test",
        "version": "fixture-regional",
        "boundary_year": "test",
        "attribution": "test",
        "limitations": "synthetic polygons and points",
    }, "1" * 64, _utc_now())

    def add_poly(pid, name, level, feature_type, country, coords, parent, state_name, aliases, note=""):
        geom = shape({"type": "Polygon", "coordinates": [coords]})
        conn.execute(
            """
            INSERT INTO place (
              id, source_namespace, source_feature_id, canonical_name, level, feature_type,
              country_code, parent_id, parent_status, state_name, representation,
              dataset_id, active, note
            ) VALUES (?, 'fixture', ?, ?, ?, ?, ?, ?, 'verified', ?, 'polygon', ?, 1, ?)
            """,
            (pid, pid, name, level, feature_type, country, parent, state_name, dataset_id, note),
        )
        _store_geometry(conn, pid, geom)
        for alias, language in aliases:
            _add_alias(conn, pid, alias, language, "fixture")

    def add_point(pid, name, country, lon, lat, parent, state_id, state_name, aliases):
        conn.execute(
            """
            INSERT INTO place (
              id, source_namespace, source_feature_id, canonical_name, level, feature_type,
              country_code, parent_id, parent_status, state_place_id, state_name,
              representation, dataset_id, population, active, note
            ) VALUES (?, 'fixture', ?, ?, 'city', 'populated_place', ?, ?, 'verified', ?, ?, 'point', ?, 100000, 1, 'point only')
            """,
            (pid, pid, name, country, parent, state_id, state_name, dataset_id),
        )
        _store_geometry(conn, pid, Point(lon, lat))
        for alias, language in aliases:
            _add_alias(conn, pid, alias, language, "fixture")

    pakistan = [(60, 23), (75, 23), (75, 37), (60, 37), (60, 23)]
    punjab = [(70, 28), (75, 28), (75, 33), (70, 33), (70, 28)]
    baloch = [(61, 24), (68, 24), (68, 31), (61, 31), (61, 24)]
    ict = [(72.8, 33.4), (73.4, 33.4), (73.4, 33.9), (72.8, 33.9), (72.8, 33.4)]
    afghanistan = [(60.2, 29.2), (74.8, 29.2), (74.8, 38.4), (60.2, 38.4), (60.2, 29.2)]
    kabul_province = [(68.5, 34.2), (70.2, 34.2), (70.2, 35.2), (68.5, 35.2), (68.5, 34.2)]
    herat_province = [(61.5, 33.5), (63.5, 33.5), (63.5, 35.2), (61.5, 35.2), (61.5, 33.5)]
    add_poly("ne-adm0-pak", "Pakistan", "country", "country", "PK", pakistan, None, None, [
        ("Pakistan", "en"), ("PAK", ""), ("PK", ""), ("पाकिस्तान", "hi"),
    ])
    add_poly("ne-adm0-afg", "Afghanistan", "country", "country", "AF", afghanistan, None, None, [
        ("Afghanistan", "en"), ("AFG", ""), ("AF", ""), ("अफगानिस्तान", "hi"), ("अफ़ग़ानिस्तान", "hi"),
    ])
    add_poly("gb-adm1-PK-PB", "Punjab", "state", "adm1_territory", "PK", punjab, "ne-adm0-pak", "Punjab", [
        ("Punjab", "en"), ("پنجاب", "ur"),
    ])
    add_poly("gb-adm1-PK-BA", "Balochistan", "state", "adm1_territory", "PK", baloch, "ne-adm0-pak", "Balochistan", [
        ("Balochistan", "en"), ("بلوچستان", "ur"), ("बलूचिस्तान", "hi"),
    ])
    add_poly(
        "gb-adm1-PK-IS", "Islamabad Capital Territory", "state", "national_capital_territory", "PK", ict,
        "ne-adm0-pak", "Islamabad Capital Territory",
        [("Islamabad Capital Territory", "en"), ("Islamabad", "en"), ("इस्लामाबाद", "hi")],
        note="Capital territory polygon. Not a municipal city boundary.",
    )
    add_poly("gb-adm1-AF-KAB", "Kabul", "state", "adm1_territory", "AF", kabul_province, "ne-adm0-afg", "Kabul", [
        ("Kabul", "en"), ("Kabul province", "en"), ("काबुल", "hi"),
    ])
    add_poly("gb-adm1-AF-HER", "Herat", "state", "adm1_territory", "AF", herat_province, "ne-adm0-afg", "Herat", [
        ("Herat", "en"), ("Herat province", "en"), ("हेरात", "hi"),
    ])
    add_point("gn-lahore", "Lahore", "PK", 74.3, 31.5, "gb-adm1-PK-PB", "gb-adm1-PK-PB", "Punjab", [
        ("Lahore", "en"), ("لاہور", "ur"), ("लाहौर", "hi"),
    ])
    add_point("gn-quetta", "Quetta", "PK", 66.9, 30.2, "gb-adm1-PK-BA", "gb-adm1-PK-BA", "Balochistan", [
        ("Quetta", "en"), ("کوئٹہ", "ur"), ("क्वेटा", "hi"),
    ])
    add_point("gn-islamabad", "Islamabad", "PK", 73.05, 33.7, "gb-adm1-PK-IS", "gb-adm1-PK-IS", "Islamabad Capital Territory", [
        ("Islamabad", "en"), ("اسلام آباد", "ur"), ("इस्लामाबाद", "hi"),
    ])
    add_point("gn-kabul", "Kabul", "AF", 69.2, 34.55, "gb-adm1-AF-KAB", "gb-adm1-AF-KAB", "Kabul", [
        ("Kabul", "en"), ("کابل", "fa"), ("काबुल", "hi"),
    ])
    add_point("gn-herat", "Herat", "AF", 62.2, 34.35, "gb-adm1-AF-HER", "gb-adm1-AF-HER", "Herat", [
        ("Herat", "en"), ("هرات", "fa"), ("हेरात", "hi"),
    ])
    add_point("gn-kandahar", "Kandahar", "AF", 65.7, 31.6, "ne-adm0-afg", None, None, [
        ("Kandahar", "en"), ("کندهار", "ps"), ("कंधार", "hi"),
    ])
    add_point("gn-mazar", "Mazar-i-Sharif", "AF", 67.1, 36.7, "ne-adm0-afg", None, None, [
        ("Mazar-i-Sharif", "en"), ("مزار شریف", "fa"), ("मजार-ए-शरीफ", "hi"),
    ])
    _ensure_indexes(conn)
    conn.commit()
    conn.close()
