"""Local geographic registry + place resolution (no invented coordinates)."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from shapely.geometry import shape, mapping, Point
from shapely.ops import unary_union

LAB = Path(__file__).resolve().parent.parent
REGISTRY_PATH = Path(__file__).resolve().parent / "registry.json"


class GeoResolveError(ValueError):
    pass


def normalize_name(value: str) -> str:
    """Fold case, Latin accents, and punctuation without stripping Devanagari vowel signs."""
    text = unicodedata.normalize("NFKC", value or "").strip().casefold()
    kept = []
    for ch in unicodedata.normalize("NFD", text):
        category = unicodedata.category(ch)
        # Drop Latin combining accents. Devanagari matras are at U+0900 and above.
        if category == "Mn" and ord(ch) < 0x0900:
            continue
        if category.startswith(("P", "S")):
            kept.append(" ")
        else:
            kept.append(ch)
    text = "".join(kept).replace("जिला", " ")
    text = re.sub(r"\s+", " ", text).strip()
    parts = [part for part in text.split(" ") if part not in {"district", "dist", "distt"}]
    text = " ".join(parts).strip()
    # "तमिलनाडु" and "तमिल नाडु" are the same Devanagari name. Latin words keep their spaces.
    return re.sub(r"(?<=[\u0900-\u097F])\s+(?=[\u0900-\u097F])", "", text)


def load_registry(path: Path | None = None) -> dict:
    data = json.loads((path or REGISTRY_PATH).read_text(encoding="utf-8"))
    if "places" not in data:
        raise GeoResolveError("Registry missing places")
    return data


def _load_feature_collection(rel_path: str) -> dict:
    path = LAB / rel_path
    if not path.is_file():
        raise GeoResolveError(f"Missing geographic file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _pick_feature(fc: dict, match: dict | None) -> dict:
    features = fc.get("features") or []
    if not features:
        raise GeoResolveError("GeoJSON has no features")
    if not match:
        if len(features) == 1:
            return features[0]
        raise GeoResolveError("Multiple features and no match filter")
    hits = []
    for feat in features:
        props = feat.get("properties") or {}
        if all(props.get(k) == v for k, v in match.items()):
            hits.append(feat)
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise GeoResolveError(f"No feature matched {match}")
    raise GeoResolveError(f"Ambiguous match for {match}: {len(hits)} features")


def geometry_of(feature: dict):
    geom = shape(feature["geometry"])
    if not geom.is_valid:
        geom = geom.buffer(0)
    if geom.is_empty:
        raise GeoResolveError("Empty geometry")
    return geom


def representative_lonlat(geom) -> list[float]:
    """Interior anchor; bbox centre is not assumed inside the polygon."""
    pt = geom.representative_point()
    return [float(pt.x), float(pt.y)]


def bbox_of(geom) -> list[float]:
    minx, miny, maxx, maxy = geom.bounds
    return [float(minx), float(miny), float(maxx), float(maxy)]


def child_within_parent(child, parent, *, min_overlap: float = 0.85) -> bool:
    if parent.buffer(0.35).contains(child.centroid):
        inter = parent.buffer(0.25).intersection(child)
        if child.area <= 0:
            return False
        return (inter.area / child.area) >= min_overlap
    return False


def resolve_place(place_spec: dict, registry: dict, resolved: dict[str, dict]) -> dict:
    """Resolve one semantic place entry against the local registry."""
    pid = place_spec["id"]
    name = place_spec["name"]
    level = place_spec["level"]
    parent_id = place_spec.get("parent")

    candidates = []
    needle = normalize_name(name)
    for entry in registry["places"].values():
        names = [entry["name"], *entry.get("aliases", [])]
        norms = {normalize_name(n) for n in names}
        if needle in norms or needle == normalize_name(entry["id"].replace("_", " ")):
            candidates.append(entry)
        elif any(needle in n or n in needle for n in norms if len(needle) >= 4):
            candidates.append(entry)

    # A known id must agree with the requested name. Do not let the id override a conflict.
    if pid in registry["places"]:
        named = registry["places"][pid]
        names = {normalize_name(named["name"]), normalize_name(named["id"].replace("_", " "))}
        names.update(normalize_name(a) for a in named.get("aliases", []))
        name_ok = needle in names or any(
            needle in n or n in needle for n in names if len(needle) >= 4 and len(n) >= 4
        )
        if not name_ok:
            raise GeoResolveError(
                f"Place id '{pid}' conflicts with name '{name}'. "
                f"Registry name for '{pid}' is '{named['name']}'."
            )
        candidates = [named]

    # Filter by administrative level.
    level_hits = [c for c in candidates if c["level"] == level]
    if level_hits:
        candidates = level_hits

    # Filter by parent when provided.
    if parent_id:
        parent_hits = [c for c in candidates if c.get("parent") == parent_id]
        if parent_hits:
            candidates = parent_hits

    # Deduplicate by id
    uniq = {}
    for c in candidates:
        uniq[c["id"]] = c
    candidates = list(uniq.values())

    if not candidates:
        available = ", ".join(sorted(registry["places"]))
        raise GeoResolveError(
            f"Cannot resolve '{name}' (id={pid}, level={level}). "
            f"Installed places: {available}. Add data + registry entry to support more locations."
        )
    if len(candidates) > 1:
        # City vs district: if user said district, never pick a city entry.
        if level == "district":
            districts = [c for c in candidates if c["level"] == "district"]
            if len(districts) == 1:
                candidates = districts
            else:
                raise GeoResolveError(
                    f"Ambiguous place '{name}' at level={level}. Candidates: "
                    f"{[c['id'] for c in candidates]}. Specify district explicitly and ensure "
                    f"only one ADM2 feature is registered."
                )
        else:
            raise GeoResolveError(
                f"Ambiguous place '{name}'. Candidates: {[c['id'] for c in candidates]}"
            )

    entry = candidates[0]
    if entry["level"] != level:
        raise GeoResolveError(
            f"Resolved '{name}' to {entry['id']} at level={entry['level']}, "
            f"but plan requested level={level}"
        )

    fc = _load_feature_collection(entry["geojson"])
    feature = _pick_feature(fc, entry.get("match"))
    geom = geometry_of(feature)

    if parent_id:
        if parent_id not in resolved:
            raise GeoResolveError(f"Parent '{parent_id}' must be resolved before '{pid}'")
        parent_geom = shape(resolved[parent_id]["geometry"])
        if not child_within_parent(geom, parent_geom):
            raise GeoResolveError(
                f"Feature '{entry['id']}' does not lie plausibly within parent '{parent_id}'. "
                f"Check dataset mismatch or wrong place."
            )

    out = {
        "id": entry["id"],
        "requested_id": pid,
        "name": entry["name"],
        "level": entry["level"],
        "parent": entry.get("parent"),
        "source_id": entry["source_id"],
        "geojson": "/" + entry["geojson"].lstrip("/"),
        "geojson_path": entry["geojson"],
        "bbox": bbox_of(geom),
        "anchor": representative_lonlat(geom),
        "geometry": mapping(geom),
        "disambiguation": entry.get("disambiguation"),
    }
    return out


def resolve_plan_places(semantic: dict, registry: dict | None = None, extras: dict | None = None) -> dict[str, dict]:
    reg = load_registry() if registry is None else registry
    requested = [place.get("id") for place in semantic.get("places") or []]
    if extras or (requested and any(pid not in reg["places"] for pid in requested)):
        from .catalog import resolve_catalog_places
        return resolve_catalog_places(semantic, extras=extras)
    # Resolve parents first via topological order.
    places = list(semantic["places"])
    remaining = {p["id"]: p for p in places}
    resolved: dict[str, dict] = {}
    # Map requested ids → registry ids
    id_map: dict[str, str] = {}

    progress = True
    while remaining and progress:
        progress = False
        for pid, spec in list(remaining.items()):
            parent = spec.get("parent")
            if parent and parent not in resolved and parent in remaining:
                continue
            # If parent already resolved under a different requested id
            if parent and parent not in resolved and parent in id_map:
                continue
            item = resolve_place(spec, reg, resolved)
            # Store under requested id for plan references
            resolved[pid] = item
            id_map[pid] = item["id"]
            del remaining[pid]
            progress = True
    if remaining:
        raise GeoResolveError(f"Could not resolve places (parent cycle?): {list(remaining)}")
    return resolved


def write_feature_collection(path: Path, feature: dict, properties: dict | None = None) -> None:
    props = dict(feature.get("properties") or {})
    if properties:
        props.update(properties)
    fc = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": props, "geometry": feature["geometry"]}],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
