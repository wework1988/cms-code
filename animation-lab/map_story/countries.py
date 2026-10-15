"""Country registry for the local geographic catalogue.

India keeps its existing canonical id ``ne-adm0-ind``. Pakistan and Afghanistan
use the same id pattern. ISO-2 is the internal country code. ISO-3 is accepted
at the boundary and normalised to ISO-2.
"""
from __future__ import annotations

from pathlib import Path

from .geo import normalize_name

LAB = Path(__file__).resolve().parent.parent

# GeoNames feature codes that are administrative seats. They are included even
# when the population field is empty.
SEAT_CODES = frozenset({"PPLC", "PPLA", "PPLA2"})
# Other populated places are included at or above this population.
# Hamlets and unnamed localities stay out of the Pakistan and Afghanistan extracts.
MAJOR_POPULATION_FLOOR = 25000

ADMIN_SUFFIXES = (
    "national capital territory",
    "federal capital territory",
    "capital territory",
    "province",
    "state",
    "territory",
    "wilayat",
    "region",
)

_ISO3_TO_ISO2 = {"IND": "IN", "PAK": "PK", "AFG": "AF"}

# Whole-string country tokens. Place aliases still come from the datasets.
# These only normalise a country constraint to an ISO-2 code.
_TOKEN_ISO = {
    "in": "IN",
    "ind": "IN",
    "india": "IN",
    "bharat": "IN",
    "भारत": "IN",
    "republic of india": "IN",
    "pk": "PK",
    "pak": "PK",
    "pakistan": "PK",
    "पाकिस्तान": "PK",
    "islamic republic of pakistan": "PK",
    "af": "AF",
    "afg": "AF",
    "afghanistan": "AF",
    "अफगानिस्तान": "AF",
    "अफ़गानिस्तान": "AF",
    "अफ़्गानिस्तान": "AF",
    "islamic state of afghanistan": "AF",
    "islamic republic of afghanistan": "AF",
}


def _boundary(iso2: str, level: str, *, filename: str, url: str, licence: str, version: str,
              boundary_year: str, attribution: str, limitations: str, namespace: str,
              place_namespace: str, directory: str) -> dict:
    return {
        "namespace": namespace,
        "place_namespace": place_namespace,
        "source_url": url,
        "licence": licence,
        "version": version,
        "boundary_year": boundary_year,
        "attribution": attribution,
        "limitations": limitations,
        "path": LAB / "assets/maps" / directory / filename,
        "level": level,
        "iso2": iso2,
    }


COUNTRIES: dict[str, dict] = {
    "IN": {
        "iso2": "IN",
        "iso3": "IND",
        "place_id": "ne-adm0-ind",
        "admin_label": "State / Union territory",
        "settlement_policy": "all_populated_places",
        "alternate_languages": frozenset({"", "en", "hi"}),
        "include_historic_aliases": False,
        "min_cities": 100000,
        "min_adm1": 30,
        "min_adm2": 700,
        "require_adm2": True,
        "min_admin1_codes": 30,
        "min_admin2_codes": 500,
        "min_admin1_crosswalk": 30,
        "strict_iso": True,
        "containment_status": "verified_pip",
        "adm1": _boundary(
            "IN", "ADM1",
            filename="geoboundaries-IND-ADM1-simp.geojson",
            directory="india",
            namespace="geoboundaries_adm1",
            place_namespace="geoboundaries_adm1",
            url="https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/IND/ADM1/geoBoundaries-IND-ADM1_simplified.geojson",
            licence="Creative Commons Attribution 2.5 India (CC BY 2.5 IN)",
            version="geoBoundaries gbOpen IND ADM1 simplified @ 9469f09",
            boundary_year="2011",
            attribution="geoBoundaries / DataMeet India / Election Commission of India",
            limitations="Simplified ADM1. Delhi is the National Capital Territory, not a city polygon.",
        ),
        "adm2": _boundary(
            "IN", "ADM2",
            filename="geoboundaries-IND-ADM2-simp.geojson",
            directory="india",
            namespace="geoboundaries_adm2",
            place_namespace="geoboundaries_adm2",
            url="https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/IND/ADM2/geoBoundaries-IND-ADM2_simplified.geojson",
            licence="Open Data Commons Open Database License 1.0 (ODbL)",
            version="geoBoundaries gbOpen IND ADM2 simplified @ 9469f09",
            boundary_year="2021",
            attribution="geoBoundaries / Pathways Data Pvt. Ltd. / lgdirectory.gov.in",
            limitations="Simplified districts. Historical district boundaries are not included.",
        ),
    },
    "PK": {
        "iso2": "PK",
        "iso3": "PAK",
        "place_id": "ne-adm0-pak",
        "admin_label": "Province / Territory",
        "settlement_policy": "major_settlements",
        "alternate_languages": frozenset({"", "en", "hi", "ur", "fa", "prs", "ps"}),
        "include_historic_aliases": True,
        "min_cities": 15,
        "min_adm1": 6,
        "min_adm2": 100,
        "require_adm2": True,
        "min_admin1_codes": 6,
        "min_admin2_codes": 0,
        "min_admin1_crosswalk": 4,
        "strict_iso": False,
        "containment_status": "verified_pip",
        "adm1": _boundary(
            "PK", "ADM1",
            filename="geoboundaries-PAK-ADM1-simp.geojson",
            directory="pakistan",
            namespace="geoboundaries_adm1_PK",
            place_namespace="geoboundaries_adm1",
            url="https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/PAK/ADM1/geoBoundaries-PAK-ADM1_simplified.geojson",
            licence="Public domain",
            version="geoBoundaries gbOpen PAK ADM1 simplified @ 9469f09",
            boundary_year="2019",
            attribution="geoBoundaries / Wikimedia",
            limitations=(
                "Simplified provinces and territories, boundary year 2019. "
                "Units such as Azad Kashmir and Gilgit-Baltistan stay in this source's classification. "
                "They are not reassigned by overlapping them with the Natural Earth country outline."
            ),
        ),
        "adm2": _boundary(
            "PK", "ADM2",
            filename="geoboundaries-PAK-ADM2-simp.geojson",
            directory="pakistan",
            namespace="geoboundaries_adm2_PK",
            place_namespace="geoboundaries_adm2",
            url="https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/PAK/ADM2/geoBoundaries-PAK-ADM2_simplified.geojson",
            licence="Public domain",
            version="geoBoundaries gbOpen PAK ADM2 simplified @ 9469f09",
            boundary_year="2019",
            attribution="geoBoundaries / Wikimedia",
            limitations="Simplified districts, boundary year 2019. Same release year as PAK ADM1.",
        ),
    },
    "AF": {
        "iso2": "AF",
        "iso3": "AFG",
        "place_id": "ne-adm0-afg",
        "admin_label": "Administrative region",
        "settlement_policy": "major_settlements",
        "alternate_languages": frozenset({"", "en", "hi", "ur", "fa", "prs", "ps"}),
        "include_historic_aliases": True,
        "min_cities": 10,
        "min_adm1": 30,
        "min_adm2": 300,
        "require_adm2": True,
        "min_admin1_codes": 30,
        "min_admin2_codes": 0,
        "min_admin1_crosswalk": 20,
        "strict_iso": False,
        "containment_status": "inferred_spatial",
        "adm1": _boundary(
            "AF", "ADM1",
            filename="geoboundaries-AFG-ADM1-simp.geojson",
            directory="afghanistan",
            namespace="geoboundaries_adm1_AF",
            place_namespace="geoboundaries_adm1",
            url="https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/AFG/ADM1/geoBoundaries-AFG-ADM1_simplified.geojson",
            licence="Public domain",
            version="geoBoundaries gbOpen AFG ADM1 simplified @ 9469f09",
            boundary_year="2007",
            attribution="geoBoundaries / Wikimedia",
            limitations="Simplified provinces (wilayat), boundary year 2007. Not the same year as AFG ADM2.",
        ),
        "adm2": _boundary(
            "AF", "ADM2",
            filename="geoboundaries-AFG-ADM2-simp.geojson",
            directory="afghanistan",
            namespace="geoboundaries_adm2_AF",
            place_namespace="geoboundaries_adm2",
            url="https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/AFG/ADM2/geoBoundaries-AFG-ADM2_simplified.geojson",
            licence="Public domain",
            version="geoBoundaries gbOpen AFG ADM2 simplified @ 9469f09",
            boundary_year="2014",
            attribution="geoBoundaries / Afghanistan Information Management Services / Esri Disaster Response Program",
            limitations=(
                "Simplified districts (wuleswali), boundary year 2014. "
                "ADM1 is 2007, so a district-to-province link from overlap is inferred_spatial, not a verified code crosswalk."
            ),
        ),
    },
}

NATURAL_EARTH = {
    "namespace": "naturalearth",
    "source_url": "https://www.naturalearthdata.com/downloads/50m-cultural-vectors/50m-admin-0-countries-2/",
    "licence": "Public domain",
    "version": "Natural Earth 1:50m admin-0",
    "boundary_year": "current 50m cultural",
    "attribution": "Natural Earth",
    "limitations": "Country outline only. Not a survey boundary. Not merged with geoBoundaries polygons.",
    "path": LAB / "assets/maps/countries.geojson",
}

SHARED_GEONAMES = {
    "admin1CodesASCII.txt": "https://download.geonames.org/export/dump/admin1CodesASCII.txt",
    "admin2Codes.txt": "https://download.geonames.org/export/dump/admin2Codes.txt",
    "readme.txt": "https://download.geonames.org/export/dump/readme.txt",
}

# Backward-compatible India download list.
GEONAMES_URLS = {
    "IN.zip": "https://download.geonames.org/export/dump/IN.zip",
    "alternatenames-IN.zip": "https://download.geonames.org/export/dump/alternatenames/IN.zip",
    **SHARED_GEONAMES,
}


def supported_iso2() -> list[str]:
    return list(COUNTRIES)


def parse_country_list(value: str) -> list[str]:
    """Accept ISO-2 or ISO-3, comma-separated. Returns ISO-2 codes."""
    from .geo import GeoResolveError

    codes = []
    for part in str(value or "").split(","):
        token = part.strip().upper()
        if not token:
            continue
        token = _ISO3_TO_ISO2.get(token, token)
        if token not in COUNTRIES:
            raise GeoResolveError(
                f"Unsupported country '{part.strip()}'. Supported ISO-2 codes: IN, PK, AF "
                "(ISO-3 IND, PAK, AFG are accepted and stored as ISO-2)."
            )
        if token not in codes:
            codes.append(token)
    if not codes:
        raise GeoResolveError("Name at least one country: IN, PK, or AF.")
    return codes


def geonames_urls(iso2: str) -> dict[str, str]:
    return {
        f"{iso2}.zip": f"https://download.geonames.org/export/dump/{iso2}.zip",
        f"alternatenames-{iso2}.zip": f"https://download.geonames.org/export/dump/alternatenames/{iso2}.zip",
        **SHARED_GEONAMES,
    }


def all_download_urls() -> dict[str, str]:
    urls = {}
    for iso2 in COUNTRIES:
        urls.update(geonames_urls(iso2))
        for level in ("adm1", "adm2"):
            spec = COUNTRIES[iso2][level]
            urls[spec["path"].name] = spec["source_url"]
    urls[NATURAL_EARTH["path"].name] = NATURAL_EARTH["source_url"]
    return urls


def iso_for_token(value: str | None) -> str | None:
    token = normalize_name(value or "")
    if not token:
        return None
    if token in _TOKEN_ISO:
        return _TOKEN_ISO[token]
    upper = token.upper()
    if upper in COUNTRIES:
        return upper
    return _ISO3_TO_ISO2.get(upper)


def admin_label_for(country_code: str | None) -> str:
    spec = COUNTRIES.get(country_code or "")
    if spec:
        return spec["admin_label"]
    return "Administrative region"


def level_label(level: str | None, country_code: str | None = None) -> str:
    if level == "state":
        return admin_label_for(country_code)
    return {
        "country": "Country",
        "district": "District",
        "city": "City",
    }.get(level or "", level or "")


def admin_name_forms(name: str) -> list[str]:
    """Exact normalised name, then the same name with one administrative suffix removed."""
    raw = normalize_name(name)
    forms = []
    if len(raw) >= 2:
        forms.append(raw)
    stripped = raw
    for suffix in ADMIN_SUFFIXES:
        marker = " " + suffix
        if stripped.endswith(marker):
            stripped = stripped[: -len(marker)].strip()
            break
    if len(stripped) >= 2 and stripped not in forms:
        forms.append(stripped)
    return forms


def include_settlement(spec: dict, feature_code: str, population: int | None) -> bool:
    """India keeps every populated place. Pakistan and Afghanistan keep seats and larger towns."""
    if spec["settlement_policy"] == "all_populated_places":
        return True
    if feature_code in SEAT_CODES:
        return True
    return int(population or 0) >= MAJOR_POPULATION_FLOOR


def dataset_namespace_for_geonames(iso2: str) -> str:
    if iso2 == "IN":
        return "geonames"
    return f"geonames_{iso2}"
