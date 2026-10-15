# Local geographic catalogue

Story planning still sends the script to DeepSeek. This catalogue stays on disk.
Prompts receive place names, stable ids, levels, parent names, and whether a
place is a boundary or a point. They do not receive GeoJSON coordinates, the
settlement table, or raw boundary files.

Imports are command-line actions. Do not run them inside a CMS request.
A failed import deletes its temporary database and leaves the previous
`geography.sqlite` in place. Saved animation plans embed the geometry they
resolved, so a later refresh does not redraw old jobs. User-confirmed aliases
live in `confirmed-aliases.sqlite` and are not rewritten by an import.

Installed counts, checksums, and limitations are written to `status.json`.
File checksums and retrieval times are written to `provenance.json`.
Unmatched administrative names are written to `crosswalk-diagnostics.json`.

## Commands

```bash
cd animation-lab
.venv/bin/python geography_catalog.py fetch --country IN,PK,AF
.venv/bin/python geography_catalog.py import-boundaries
.venv/bin/python geography_catalog.py import-geonames --country IN
.venv/bin/python geography_catalog.py import-geonames --country PK,AF
.venv/bin/python geography_catalog.py lookup "Lahore" --country PK --level city
.venv/bin/python geography_catalog.py lookup "वडनगर" --country IN
.venv/bin/python geography_catalog.py status
```

`refresh --country IN,PK,AF` rebuilds boundaries and then reimports GeoNames for
those countries. `import-boundaries` keeps settlement rows already in the active
catalogue, so Pakistan and Afghanistan can be added without downloading India again.

ISO-3 codes `IND`, `PAK`, and `AFG` are accepted and stored as `IN`, `PK`, and `AF`.

## Datasets

All three countries use the same pinned geoBoundaries commit, `9469f09`, and the
simplified GeoJSON from `gbOpen`. Natural Earth country outlines are not merged
with those polygons. A province that does not overlap its Natural Earth country
keeps its source country code and is recorded as an unresolved parent.

| Layer | Source | Licence | Version |
| --- | --- | --- | --- |
| Countries | Natural Earth 1:50m admin-0, cached `assets/maps/countries.geojson` | Public domain | ADMIN names India, Pakistan, Afghanistan |
| India ADM1 | geoBoundaries IND ADM1 simplified | CC BY 2.5 IN | commit 9469f09, boundary year 2011 |
| India ADM2 | geoBoundaries IND ADM2 simplified | ODbL 1.0 | commit 9469f09, boundary year 2021 |
| Pakistan ADM1 | geoBoundaries PAK ADM1 simplified | Public domain | commit 9469f09, boundary year 2019, 7 units |
| Pakistan ADM2 | geoBoundaries PAK ADM2 simplified | Public domain | commit 9469f09, boundary year 2019 |
| Afghanistan ADM1 | geoBoundaries AFG ADM1 simplified | Public domain | commit 9469f09, boundary year 2007, 34 units |
| Afghanistan ADM2 | geoBoundaries AFG ADM2 simplified | Public domain | commit 9469f09, boundary year 2014 |
| Populated places | GeoNames `{ISO2}.zip` and `alternatenames/{ISO2}.zip` | CC BY 4.0 | dump files in `downloads/` |

GeoNames files are fetched only from `https://download.geonames.org/export/dump/`:
`IN.zip`, `PK.zip`, `AF.zip`, the matching `alternatenames/{ISO2}.zip`, plus
`admin1CodesASCII.txt`, `admin2Codes.txt`, and `readme.txt`.

Boundary files:

- India: `assets/maps/india/geoboundaries-IND-ADM1-simp.geojson` and `ADM2`
- Pakistan: `assets/maps/pakistan/geoboundaries-PAK-ADM1-simp.geojson` and `ADM2`
- Afghanistan: `assets/maps/afghanistan/geoboundaries-AFG-ADM1-simp.geojson` and `ADM2`

## Inclusion

India keeps every GeoNames populated place (feature class `P`). Pakistan and
Afghanistan include administrative seats (`PPLC`, `PPLA`, `PPLA2`) even when
population is blank, and other populated-place codes only when population is at
least 25,000. Cities stay points. No municipal polygon is invented.

Alternate names are kept for English and Hindi on every country, and also Urdu,
Persian (`fa` / `prs`), and Pashto where GeoNames supplies them. Pakistan and
Afghanistan also keep historic alternate names, marked `geonames_alternate_historic`.
A Hindi gap that the dump does not cover can be added in `curated_aliases.json`
with a note. Transliteration only retrieves candidates.

Canonical ids stay source-derived: `ne-adm0-ind`, `ne-adm0-pak`, `ne-adm0-afg`,
`gb-adm1-{shapeISO}` (Afghanistan Kandahar remains `gb-adm1-AF_KAN`), and
`gn-{geonameid}`.

## Names that are not forced together

GeoNames and geoBoundaries do not share one code list. A parent is attached only
when the country-scoped name matches, including one administrative suffix such as
"Province" or "Capital Territory". Spatial overlap can confirm a point that
already has a name or code match. A point is not moved to the nearest province.

These Afghanistan pairs stay unmatched and are listed in the diagnostics file:

- Ghanzi / Ghazni
- Ghor / Ghowr
- Uruzgan / Oruzgan
- Nimruz / Nimroz
- Khost / Khowst
- Wardak / Maidan Wardak

Afghanistan ADM1 is boundary year 2007 and ADM2 is 2014, so a district found by
overlap is `inferred_spatial`, not a verified membership. Pakistan ADM1 and ADM2
are both 2019, so that overlap can be `verified_pip`.

Azad Kashmir and Gilgit-Baltistan remain Pakistan in the geoBoundaries file
because their `shapeISO` starts with `PK`. They are not reassigned by comparing
them with the Natural Earth outline. Islamabad Capital Territory is stored as a
capital-territory polygon, separate from the Islamabad city point. Delhi stays
the National Capital Territory, separate from the city point.

## Coverage limits

- Delhi’s ADM1 polygon is the National Capital Territory. Populated places named Delhi stay separate points.
- Vadnagar (GeoNames 1253577) is a point in Gujarat. The alternate-name file has no Hindi row for it, so `वडनगर` is a curated alias in `curated_aliases.json`.
- `गुजरात` is curated on the Indian state because GeoNames also uses that spelling for Gujrat city in Pakistan. `पंजाब` is curated on Indian Punjab because the same spelling is on Pakistan's Punjab. Without a country, those names stay ambiguous.
- A spelling is a candidate when it is similar to one catalogue name. Similarity alone does not resolve a place. Two or more exact matches stay unresolved until a verified parent or the identity fallback distinguishes them. Population never chooses.
- Hindi names can be transliterated to Latin only to retrieve candidates. That spelling is not an identity.
- Rivers, lakes, temples, and other landmarks are not settlements. A missing river is not replaced by a similarly named city.
- Historical boundaries are not included.
- South Asia relief (`assets/maps/south-asia-relief.json`) covers India, Pakistan, and Afghanistan. A country outside that raster drops the regional layer and caps zoom. Flat map themes do not depend on that raster.
- After import, rendering uses the local files. It does not geocode over the network.

## Runtime

`animation-lab/.venv` needs Pillow, imageio-ffmpeg, Shapely, and RapidFuzz
(`requirements.txt`). The CMS launcher uses that interpreter.
