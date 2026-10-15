#!/usr/bin/env python3
"""Read-only catalogue search and validated location overrides for the CMS.

The process prints JSON on stdout. It does not read API keys.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .alias_memory import AliasStore
from .catalog import connect
from .identity import catalog_version
from .overrides import (
    OVERRIDE_FILE,
    _same_choice,
    load_overrides,
    save_override_document,
    selection_requests,
    user_point_id,
    validate_catalogue_selection,
    validate_custom_point,
)
from .search import catalogue_filters, place_preview, search_places


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["search", "preview", "apply", "aliases", "alias-disable", "alias-remove", "filters"])
    parser.add_argument("--catalog", type=Path, default=None)
    parser.add_argument("--query", default="")
    parser.add_argument("--level", default=None)
    parser.add_argument("--country", default=None)
    parser.add_argument("--state", default=None)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--id", default="")
    parser.add_argument("--alias-id", type=int, default=0)
    parser.add_argument("--alias-db", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        if args.command == "search":
            payload = search_places(
                args.query,
                level=args.level,
                country=args.country,
                state=args.state,
                limit=args.limit,
                offset=args.offset,
                catalog_path=args.catalog,
            )
        elif args.command == "preview":
            payload = place_preview(args.id, catalog_path=args.catalog)
        elif args.command == "filters":
            payload = catalogue_filters(args.catalog)
        elif args.command == "aliases":
            payload = {"aliases": AliasStore(args.alias_db).list_rows()}
        elif args.command == "alias-disable":
            AliasStore(args.alias_db).set_active(args.alias_id, False)
            payload = {"ok": True, "id": args.alias_id, "active": False}
        elif args.command == "alias-remove":
            AliasStore(args.alias_db).remove(args.alias_id)
            payload = {"ok": True, "id": args.alias_id, "removed": True}
        else:
            payload = apply_document(json.loads(sys.stdin.read() or "{}"), catalog_path=args.catalog, alias_db=args.alias_db)
        payload["ok"] = True
        json.dump(payload, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as error:
        json.dump({"ok": False, "error": str(error)}, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 1


def apply_document(body: dict, *, catalog_path: Path | None, alias_db: Path | None) -> dict:
    job_dir = Path(str(body.get("job_dir") or ""))
    selection_path = job_dir / "selection.json"
    if not selection_path.is_file():
        raise ValueError("This animation has no saved clip selection to attach locations to.")
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    known = selection_requests(selection)
    existing_doc = load_overrides(job_dir / OVERRIDE_FILE)
    by_request = {item.get("request_id"): item for item in existing_doc["overrides"] if item.get("request_id")}
    version = str(body.get("catalogue_version") or catalog_version(catalog_path))
    conn = connect(catalog_path, readonly=True)
    store = AliasStore(alias_db)
    errors = []
    changed_ids = []
    remembered = []
    submitted = []
    try:
        for selection_row in body.get("selections") or []:
            if not isinstance(selection_row, dict):
                continue
            request_id = str(selection_row.get("request_id") or "")
            submitted.append(request_id)
            request = known.get(request_id)
            if not request:
                errors.append({"request_id": request_id, "error": "That location request is not part of this job."})
                continue
            try:
                record = _record(conn, body, request, selection_row, version)
            except ValueError as error:
                errors.append({"request_id": request_id, "error": str(error)})
                continue
            previous = by_request.get(request_id)
            if previous and _same_choice(previous, record):
                record["revision"] = previous.get("revision")
                record["created"] = previous.get("created")
                by_request[request_id] = record
            else:
                changed_ids.append(request_id)
                by_request[request_id] = record
            if selection_row.get("remember") and record["source"] == "manual_catalogue_selection":
                alias_id = _remember(store, conn, record, version, body.get("uid"))
                if alias_id:
                    remembered.append({"alias_id": alias_id, "request_id": request_id, "place_id": record.get("place_id")})
    finally:
        conn.close()
    revision = int(existing_doc["revision"] or 0)
    if changed_ids:
        revision += 1
        for request_id in changed_ids:
            by_request[request_id]["revision"] = revision
    overrides = list(by_request.values())
    document = {
        "revision": revision,
        "job_id": body.get("job_id"),
        "script_hash": body.get("script_hash"),
        "catalogue_version": version,
        "overrides": overrides,
    }
    save_override_document(job_dir / OVERRIDE_FILE, document)
    return {
        "revision": revision,
        "changed": bool(changed_ids),
        "errors": errors,
        "overrides": overrides,
        "remaining": [request_id for request_id in submitted if request_id not in by_request],
        "remembered": remembered,
    }


def _record(conn, body: dict, request: dict, selection_row: dict, version: str) -> dict:
    source = selection_row.get("source")
    created = selection_row.get("created")
    base = {
        "job_id": body.get("job_id"),
        "clip_id": request.get("clip_id"),
        "request_id": request.get("request_id"),
        "original_name": request.get("name"),
        "original_level": request.get("level"),
        "fingerprint": request.get("fingerprint"),
        "script_hash": body.get("script_hash"),
        "catalogue_version": version,
        "uid": body.get("uid"),
        "created": created,
        "updated": None,
        "type_correction": bool(selection_row.get("type_correction")),
    }
    from .overrides import _now

    base["updated"] = _now()
    base["created"] = base["created"] or base["updated"]
    if source == "manual_catalogue_selection":
        place = validate_catalogue_selection(
            conn,
            place_id=str(selection_row.get("place_id") or ""),
            requested_name=str(request.get("name") or ""),
            requested_level=request.get("level") if isinstance(request.get("level"), str) else None,
            type_correction=bool(selection_row.get("type_correction")),
        )
        base.update({
            "source": source,
            "place_id": place["id"],
            "display_name": place["name"],
        })
        return base
    if source == "manual_custom_point":
        geometry = validate_custom_point(
            name=str(selection_row.get("display_name") or ""),
            latitude=selection_row.get("latitude"),
            longitude=selection_row.get("longitude"),
        )
        point_id = user_point_id(str(body.get("job_id") or ""), str(request.get("request_id") or ""))
        base.update({
            "source": source,
            "place_id": point_id,
            "display_name": str(selection_row.get("display_name") or "").strip(),
            "latitude": geometry["coordinates"][1],
            "longitude": geometry["coordinates"][0],
            "stated_admin_id": selection_row.get("stated_admin_id") or None,
            "spatial_membership_verified": False,
        })
        return base
    raise ValueError("Choose a catalogue place or add a custom point.")


def _remember(store: AliasStore, conn, record: dict, version: str, uid) -> int | None:
    row = conn.execute("SELECT * FROM place WHERE id=?", (record["place_id"],)).fetchone()
    if not row:
        return None
    if not row["state_place_id"] and not row["district_place_id"]:
        return None
    return store.remember({
        "name": record.get("original_name"),
        "place_id": record["place_id"],
        "feature_type": row["feature_type"],
        "level": row["level"],
        "country_code": row["country_code"],
        "state_place_id": row["state_place_id"],
        "district_place_id": row["district_place_id"],
        "catalogue_version": version,
        "uid": uid,
    })


if __name__ == "__main__":
    sys.exit(main())
