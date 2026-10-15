#!/usr/bin/env python3
"""Build and query the local geographic catalogue. Do not run this from a CMS request."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB))

from map_story.catalog import (  # noqa: E402
    ACTIVE_PATH,
    DOWNLOADS,
    catalog_status,
    fetch_sources,
    import_boundaries,
    import_geonames,
    lookup,
)
from map_story.countries import all_download_urls, parse_country_list  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="Download missing pinned source files for IN, PK, and AF")
    fetch.add_argument("--country", default="IN,PK,AF", help="ISO-2 or ISO-3 codes, comma-separated")

    boundaries = sub.add_parser("import-boundaries", help="Import cached country and first-level boundaries for IN, PK, and AF")
    boundaries.add_argument("--refresh", action="store_true", help="Rebuild boundary rows and keep an existing settlement import")

    geonames = sub.add_parser("import-geonames", help="Import GeoNames populated places for one or more countries")
    geonames.add_argument("--country", default="IN", help="ISO-2 or ISO-3 codes, comma-separated. Example: PK,AF")

    find = sub.add_parser("lookup", help="Resolve one place name locally")
    find.add_argument("name")
    find.add_argument("--country", default=None)
    find.add_argument("--state", default=None)
    find.add_argument("--district", default=None)
    find.add_argument("--level", default=None)

    sub.add_parser("status", help="Show installed dataset versions and counts")
    refresh = sub.add_parser("refresh", help="Rebuild boundaries, then GeoNames, without touching saved animation plans")
    refresh.add_argument("--country", default="IN,PK,AF", help="GeoNames countries to reimport after the boundary rebuild")
    args = parser.parse_args()

    if args.command == "fetch":
        records = fetch_sources(args.country)
        print(json.dumps({"fetched": len(records), "countries": parse_country_list(args.country)}, ensure_ascii=False, indent=2))
    elif args.command == "import-boundaries":
        import_boundaries(refresh=args.refresh)
    elif args.command == "import-geonames":
        import_geonames(args.country)
    elif args.command == "refresh":
        import_boundaries(refresh=True)
        import_geonames(args.country)
    elif args.command == "lookup":
        print(json.dumps(lookup(
            args.name,
            country=args.country,
            state=args.state,
            district=args.district,
            level=args.level,
        ), ensure_ascii=False, indent=2))
        return
    elif args.command == "status":
        print(json.dumps(catalog_status(), ensure_ascii=False, indent=2))
        return
    print(json.dumps(catalog_status(), ensure_ascii=False, indent=2))
    print(f"Active catalogue: {ACTIVE_PATH}")
    print(f"GeoNames downloads: {DOWNLOADS}")
    print("Download URLs:")
    for name, url in all_download_urls().items():
        print(f"  {name}: {url}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 — CLI should preserve the previous catalogue
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
