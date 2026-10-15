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
                elif not district_id and district_tree is not None and state_id:
                    hits = list(district_tree.query(Point(lon, lat), predicate="covers"))
                    owned = [
                        district_ids[int(hit)]
                        for hit in hits
                        if district_state.get(district_ids[int(hit)]) == state_id
                    ]
                    if len(owned) == 1:
                        district_id = owned[0]
                        district_status = containment
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


