"""Map presentation presets.

Built-in templates live in this module. ``export_builtin_json`` writes the
same document for the CMS. Renderers read the resolved theme on each job
snapshot and do not look up a live template at frame time.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

SCHEMA_VERSION = 1
BUILTIN_JSON = Path(__file__).resolve().parents[1] / "assets" / "maps" / "themes" / "builtin.json"
COLOR = re.compile(r"^(#[0-9A-Fa-f]{6}|#[0-9A-Fa-f]{8}|rgba?\([^)]+\))$")
FONTS = ("Story Condensed", "Story Devanagari Bold", "Story Devanagari", "Story Latin")

# Existing look. Token values match the previous renderer constants.
CINEMATIC_TERRAIN = {
    "id": "cinematic_terrain",
    "ocean": "#0e1a2e",
    "ocean_deep": "#0e1a2e",
    "ocean_openlayers": "#0e1a2e",
    "land": "#3d4a38",
    "land_opacity": 0.04,
    "ink": "#fff8ec",
    "gold": "#e8d5a3",
    "muted": "#9aa7b5",
    "border": "#c9b896",
    "border_selected": "#fff4d6",
    "border_glow": "#ffd27a",
    "vignette": "#03091740",
    "caption_bg": "#08121bcc",
    "callout_box": "rgba(18,28,48,0.92)",
    "callout_border": "#e8d5a3",
    "fill": {"mode": "translucent"},
    "terrain": {
        "saturation": -0.1,
        "contrast": 0.16,
        "regional_saturation": -0.08,
        "regional_contrast": 0.2,
        "brightness_min": 0,
        "brightness_max": 1,
    },
    "boundary": {"renderer": "map"},
    "camera": {},
    "label": {},
}

# Documentary relief. Colors are tuned starting points, not measured from the references.
DOCUMENTARY_RELIEF_BOLD = {
    "id": "documentary_relief_bold",
    "ocean": "#103E4A",
    "ocean_deep": "#082831",
    "ocean_openlayers": "#103E4A",
    "land": "#8d7352",
    "land_opacity": 0.05,
    "ink": "#FFFDF5",
    "gold": "#FFD86B",
    "muted": "#d7c7a4",
    "border": "#e6d7a8",
    "border_selected": "#FFF5C5",
    "border_glow": "#FFD86B",
    "vignette": "#08283144",
    "vignette_inner": "#00000000",
    "caption_bg": "#17160F",
    "callout_box": "rgba(23,22,15,0.0)",
    "callout_border": "#FFF5C5",
    "persist_parent_fill": True,
    "palette": {
        "country_red": "#A32320",
        "country_red_deep": "#651B1B",
        "region_red": "#C34332",
        "yellow": "#D4B300",
        "cyan": "#278FAF",
        "royal_blue": "#074DB5",
        "marker_yellow": "#FFF400",
        "marker_cyan": "#17C9FF",
        "label": "#FFFDF5",
        "date_banner": "#17160F",
    },
    "fill": {
        "mode": "terrain_color",
        "blend": "multiply",
        "hue_blend": "color",
        "opacity_scale": 1,
        "hue_opacity": 0.66,
    },
    "terrain": {
        "saturation": -0.12,
        "contrast": 0.08,
        "regional_saturation": -0.08,
        "regional_contrast": 0.1,
        "brightness_min": 0,
        "brightness_max": 0.9,
        "hue_rotate": 0,
        "use_graded_relief": True,
    },
    "boundary": {
        "renderer": "canvas",
        "country_core": 1.7,
        "country_glow": 0,
        "country_blur": 8,
        "country_glow_opacity": 0.9,
        "region_core": 1.15,
        "region_glow": 0,
        "region_blur": 2.4,
        "region_glow_opacity": 0.45,
    },
    "marker": {
        "core": 3.1,
        "halo": 8.5,
        "glow": 18,
        "arrival_seconds": 0.38,
    },
    "label": {
        "font_latin": "Story Condensed",
        "font_devanagari": "Story Devanagari Bold",
        "color": "#FFFDF5",
        "shadow": "rgba(0,0,0,0.72)",
        "shadow_blur": 2.5,
        "shadow_offset_y": 1.5,
        "stroke_width": 0,
        "uppercase_latin": True,
        "orientation": "screen",
        "reveal_after_camera": True,
        "persist_after_focus": True,
        "city_above_marker": True,
        "safe_margin": 0.06,
        "min_size": 28,
        "max_size": 96,
        "supporting_size": 44,
        "sizes": {
            "country": 72,
            "state": 88,
            "district": 68,
            "city": 92,
            "region": 48,
        },
    },
    "date_banner": {
        "fill": "#17160F",
        "edge": "#0c0b08",
        "text": "#FFFDF5",
        "text_size": 92,
        "height": 146,
        "font": "Story Condensed",
    },
    "camera": {"max_pitch": 0, "bearing": 0},
}


def _label_block(color: str, shadow: str, stroke: str) -> dict:
    label = copy.deepcopy(DOCUMENTARY_RELIEF_BOLD["label"])
    label["color"] = color
    label["shadow"] = shadow
    label["stroke_width"] = 3 if stroke else 0
    return label


def _theme(
    theme_id: str,
    name: str,
    description: str,
    *,
    capabilities: dict,
    tokens: dict,
    palette: dict,
    ocean: str,
    land: str,
    land_opacity: float,
    ink: str,
    gold: str,
    muted: str,
    border: str,
    border_selected: str,
    border_glow: str,
    vignette: str,
    callout_box: str,
    callout_border: str,
    fill: dict,
    terrain: dict,
    boundary: dict,
    marker: dict,
    label: dict,
    date_banner: dict,
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "id": theme_id,
        "name": name,
        "description": description,
        "revision": 1,
        "builtin": True,
        "capabilities": capabilities,
        "tokens": tokens,
        "ocean": ocean,
        "ocean_deep": tokens["background"].get("oceanDeep", ocean),
        "ocean_openlayers": ocean,
        "land": land,
        "land_opacity": land_opacity,
        "ink": ink,
        "gold": gold,
        "muted": muted,
        "border": border,
        "border_selected": border_selected,
        "border_glow": border_glow,
        "vignette": vignette,
        "vignette_inner": "#00000000",
        "caption_bg": tokens["dateBanner"]["background"],
        "callout_box": callout_box,
        "callout_border": callout_border,
        "callout_text": tokens["callout"]["text"],
        "persist_parent_fill": True,
        "palette": palette,
        "fill": fill,
        "terrain": terrain,
        "boundary": boundary,
        "marker": marker,
        "label": label,
        "date_banner": date_banner,
        "camera": {"max_pitch": 0, "bearing": 0},
        "role_opacity": {"country": 0.72, "focus": [0.34, 0.4, 0.42]},
    }


def _pin_marker(fill: str, outline: str, shadow: str) -> dict:
    return {
        "shape": "pin",
        "fill": fill,
        "outline": outline,
        "hole": "transparent",
        "hole_color": "#FFFFFF",
        "shadow": shadow,
        "height": 54,
        "outline_width": 2.25,
        "shadow_strength": 0.4,
        "pulse": False,
        "core": 3.1,
        "halo": 8.5,
        "glow": 0,
        "arrival_seconds": 0.38,
    }


_DOC_CAPS = {
    "presentation": "documentary",
    "basemap_mode": "graded_relief",
    "fill_treatment": "terrain_color",
    "marker_shape": "glow_dot",
    "boundary_treatment": "canvas",
    "banner_treatment": "bar",
    "camera_profile": "documentary",
    "apply_palette": True,
    "vignette": "subtle",
    "border_glow": True,
    "exact_land_ocean": False,
}
_DOC_TOKENS = {
    "background": {"ocean": "#103E4A", "oceanDeep": "#082831", "land": "#8d7352", "contextBorder": "#e6d7a8"},
    "highlights": {
        "country": "#A32320",
        "countryDeep": "#651B1B",
        "primaryRegion": "#D4B300",
        "secondaryRegion": "#278FAF",
        "tertiaryRegion": "#074DB5",
        "activeLocation": "#FFF400",
    },
    "borders": {"selected": "#FFF5C5", "glow": "#FFD86B"},
    "marker": {
        "fill": "#FFF400",
        "outline": "#FFFDF5",
        "hole": "#FFFDF5",
        "shadow": "#FFF400",
        "roles": ["#FFF400", "#17C9FF", "#FFF400"],
    },
    "labels": {"text": "#FFFDF5", "outline": "#0000008C", "shadow": "rgba(0,0,0,0.72)", "secondaryText": "#d7c7a4"},
    "callout": {"background": "rgba(23,22,15,0.0)", "text": "#FFFDF5", "arrow": "#FFD86B", "border": "#FFF5C5"},
    "dateBanner": {"background": "#17160F", "text": "#FFFDF5"},
    "routes": {"primary": "#FFD86B", "secondary": "#278FAF"},
}

CLEAN_ATLAS = _theme(
    "clean_atlas",
    "Clean Atlas",
    "Flat ocean and land, a red teardrop pin, and no heavy vignette.",
    capabilities={
        "presentation": "documentary",
        "basemap_mode": "flat_atlas",
        "fill_treatment": "solid",
        "marker_shape": "pin",
        "boundary_treatment": "canvas",
        "banner_treatment": "bar",
        "camera_profile": "documentary",
        "apply_palette": True,
        "vignette": "none",
        "border_glow": False,
        "exact_land_ocean": True,
    },
    tokens={
        "background": {"ocean": "#DDECF3", "land": "#EEECE5", "contextBorder": "#B8C2CB"},
        "highlights": {
            "country": "#D5DDE7",
            "countryDeep": "#AEBCCB",
            "primaryRegion": "#F4C95D",
            "secondaryRegion": "#61B3C9",
            "tertiaryRegion": "#A993D6",
            "activeLocation": "#E60023",
        },
        "borders": {"selected": "#FFFFFF", "glow": "#FFFFFF"},
        "marker": {"fill": "#E60023", "outline": "#FFFFFF", "hole": "transparent", "shadow": "#172B4D33"},
        "labels": {"text": "#172B4D", "outline": "#FFFFFF", "shadow": "#FFFFFF", "secondaryText": "#526477"},
        "callout": {"background": "#FFFFFFF2", "text": "#172B4D", "arrow": "#E60023", "border": "#D4DCE4"},
        "dateBanner": {"background": "#172B4D", "text": "#FFFFFF"},
        "routes": {"primary": "#E60023", "secondary": "#237E99"},
    },
    palette={
        "country_red": "#D5DDE7",
        "country_red_deep": "#AEBCCB",
        "region_red": "#F4C95D",
        "yellow": "#F4C95D",
        "cyan": "#61B3C9",
        "royal_blue": "#A993D6",
        "marker_yellow": "#E60023",
        "marker_cyan": "#E60023",
        "label": "#172B4D",
        "date_banner": "#172B4D",
    },
    ocean="#DDECF3",
    land="#EEECE5",
    land_opacity=1,
    ink="#172B4D",
    gold="#E60023",
    muted="#526477",
    border="#B8C2CB",
    border_selected="#FFFFFF",
    border_glow="#FFFFFF",
    vignette="#00000000",
    callout_box="#FFFFFFF2",
    callout_border="#D4DCE4",
    fill={"mode": "solid", "blend": "normal", "opacity_scale": 1},
    terrain={"saturation": 0, "contrast": 0, "brightness_min": 0, "brightness_max": 1, "hue_rotate": 0, "use_graded_relief": False},
    boundary={"renderer": "canvas", "country_core": 1.5, "country_glow": 0, "country_blur": 0, "country_glow_opacity": 0, "region_core": 1.2, "region_glow": 0, "region_blur": 0, "region_glow_opacity": 0},
    marker=_pin_marker("#E60023", "#FFFFFF", "#172B4D33"),
    label=_label_block("#172B4D", "#FFFFFF", "#FFFFFF"),
    date_banner={"fill": "#172B4D", "edge": "#0E1C33", "text": "#FFFFFF", "text_size": 92, "height": 146, "font": "Story Condensed"},
)

MIDNIGHT_AMBER = _theme(
    "midnight_amber",
    "Midnight Amber",
    "Dark graded relief, amber pin, and a restrained border glow.",
    capabilities={
        "presentation": "documentary",
        "basemap_mode": "graded_relief",
        "fill_treatment": "terrain_color",
        "marker_shape": "pin",
        "boundary_treatment": "canvas",
        "banner_treatment": "bar",
        "camera_profile": "documentary",
        "apply_palette": True,
        "vignette": "subtle",
        "border_glow": True,
        "exact_land_ocean": False,
    },
    tokens={
        "background": {"ocean": "#071923", "land": "#263A3D", "contextBorder": "#536768"},
        "highlights": {
            "country": "#294B59",
            "countryDeep": "#122B37",
            "primaryRegion": "#D99A2B",
            "secondaryRegion": "#279EAD",
            "tertiaryRegion": "#8B74C8",
            "activeLocation": "#FFD166",
        },
        "borders": {"selected": "#FFF0C2", "glow": "#FFC857"},
        "marker": {"fill": "#FFC857", "outline": "#FFF3D1", "hole": "transparent", "shadow": "#00000066"},
        "labels": {"text": "#FFF8E8", "outline": "#07131D", "shadow": "#07131D", "secondaryText": "#B7C7CC"},
        "callout": {"background": "#102630E8", "text": "#FFF8E8", "arrow": "#FFC857", "border": "#52676D"},
        "dateBanner": {"background": "#102630", "text": "#FFD166"},
        "routes": {"primary": "#FFC857", "secondary": "#49C6D5"},
    },
    palette={
        "country_red": "#294B59",
        "country_red_deep": "#122B37",
        "region_red": "#D99A2B",
        "yellow": "#D99A2B",
        "cyan": "#279EAD",
        "royal_blue": "#8B74C8",
        "marker_yellow": "#FFC857",
        "marker_cyan": "#FFC857",
        "label": "#FFF8E8",
        "date_banner": "#102630",
    },
    ocean="#071923",
    land="#263A3D",
    land_opacity=0.08,
    ink="#FFF8E8",
    gold="#FFC857",
    muted="#B7C7CC",
    border="#536768",
    border_selected="#FFF0C2",
    border_glow="#FFC857",
    vignette="#07131D55",
    callout_box="#102630E8",
    callout_border="#52676D",
    fill={"mode": "terrain_color", "blend": "multiply", "hue_blend": "color", "opacity_scale": 1, "hue_opacity": 0.72},
    terrain={
        "saturation": -0.28,
        "contrast": 0.14,
        "regional_saturation": -0.22,
        "regional_contrast": 0.16,
        "brightness_min": 0,
        "brightness_max": 0.62,
        "hue_rotate": 12,
        "use_graded_relief": True,
    },
    boundary={"renderer": "canvas", "country_core": 1.6, "country_glow": 0, "country_blur": 6, "country_glow_opacity": 0.55, "region_core": 1.15, "region_glow": 0, "region_blur": 2.2, "region_glow_opacity": 0.35},
    marker=_pin_marker("#FFC857", "#FFF3D1", "#00000066"),
    label=_label_block("#FFF8E8", "#07131D", "#07131D"),
    date_banner={"fill": "#102630", "edge": "#07131D", "text": "#FFD166", "text_size": 92, "height": 146, "font": "Story Condensed"},
)

ARCHIVAL_EARTH = _theme(
    "archival_earth",
    "Archival Earth",
    "Warm graded relief and an earth-red pin. Geography stays clear of decorative texture.",
    capabilities={
        "presentation": "documentary",
        "basemap_mode": "graded_relief",
        "fill_treatment": "terrain_color",
        "marker_shape": "pin",
        "boundary_treatment": "canvas",
        "banner_treatment": "bar",
        "camera_profile": "documentary",
        "apply_palette": True,
        "vignette": "subtle",
        "border_glow": False,
        "exact_land_ocean": False,
    },
    tokens={
        "background": {"ocean": "#526F73", "land": "#C2AD83", "contextBorder": "#8B795F"},
        "highlights": {
            "country": "#AD604B",
            "countryDeep": "#6D3E35",
            "primaryRegion": "#D1AA4E",
            "secondaryRegion": "#628F8B",
            "tertiaryRegion": "#9582A5",
            "activeLocation": "#9C302C",
        },
        "borders": {"selected": "#FFF0C7", "glow": "#FFF0C7"},
        "marker": {"fill": "#9C302C", "outline": "#FFF0D2", "hole": "transparent", "shadow": "#34271D55"},
        "labels": {"text": "#FFF5DC", "outline": "#352A20", "shadow": "#352A20", "secondaryText": "#E2D3B5"},
        "callout": {"background": "#342A20EB", "text": "#FFF5DC", "arrow": "#D1AA4E", "border": "#BBA47A"},
        "dateBanner": {"background": "#342A20", "text": "#FFF5DC"},
        "routes": {"primary": "#D1AA4E", "secondary": "#9C302C"},
    },
    palette={
        "country_red": "#AD604B",
        "country_red_deep": "#6D3E35",
        "region_red": "#D1AA4E",
        "yellow": "#D1AA4E",
        "cyan": "#628F8B",
        "royal_blue": "#9582A5",
        "marker_yellow": "#9C302C",
        "marker_cyan": "#9C302C",
        "label": "#FFF5DC",
        "date_banner": "#342A20",
    },
    ocean="#526F73",
    land="#C2AD83",
    land_opacity=0.07,
    ink="#FFF5DC",
    gold="#D1AA4E",
    muted="#E2D3B5",
    border="#8B795F",
    border_selected="#FFF0C7",
    border_glow="#FFF0C7",
    vignette="#34271D33",
    callout_box="#342A20EB",
    callout_border="#BBA47A",
    fill={"mode": "terrain_color", "blend": "multiply", "hue_blend": "color", "opacity_scale": 1, "hue_opacity": 0.62},
    terrain={
        "saturation": 0.18,
        "contrast": 0.06,
        "regional_saturation": 0.14,
        "regional_contrast": 0.08,
        "brightness_min": 0,
        "brightness_max": 0.96,
        "hue_rotate": -16,
        "use_graded_relief": True,
    },
    boundary={"renderer": "canvas", "country_core": 1.55, "country_glow": 0, "country_blur": 1.2, "country_glow_opacity": 0.15, "region_core": 1.1, "region_glow": 0, "region_blur": 0, "region_glow_opacity": 0},
    marker=_pin_marker("#9C302C", "#FFF0D2", "#34271D55"),
    label=_label_block("#FFF5DC", "#352A20", "#352A20"),
    date_banner={"fill": "#342A20", "edge": "#241C16", "text": "#FFF5DC", "text_size": 92, "height": 146, "font": "Story Condensed"},
)


def _attach_contract(theme: dict, name: str, description: str, capabilities: dict, tokens: dict) -> dict:
    theme = copy.deepcopy(theme)
    theme["schema_version"] = SCHEMA_VERSION
    theme["name"] = name
    theme["description"] = description
    theme["revision"] = 1
    theme["builtin"] = True
    theme["capabilities"] = copy.deepcopy(capabilities)
    theme["tokens"] = copy.deepcopy(tokens)
    theme.setdefault("marker", {})
    theme["marker"] = dict(theme["marker"])
    theme["marker"]["shape"] = capabilities["marker_shape"]
    theme.setdefault("role_opacity", {"country": 0.72, "focus": [0.34, 0.4, 0.42]})
    return theme


CINEMATIC_TERRAIN = _attach_contract(
    CINEMATIC_TERRAIN,
    "Cinematic Terrain",
    "Earlier terrain look. Kept for plans that already request it.",
    {
        "presentation": "cinematic",
        "basemap_mode": "graded_relief",
        "fill_treatment": "translucent",
        "marker_shape": "ring",
        "boundary_treatment": "map",
        "banner_treatment": "none",
        "camera_profile": "cinematic",
        "apply_palette": False,
        "vignette": "cinematic",
        "border_glow": True,
        "exact_land_ocean": False,
    },
    {
        "background": {"ocean": "#0e1a2e", "land": "#3d4a38", "contextBorder": "#c9b896"},
        "highlights": {
            "country": "#E52B32",
            "countryDeep": "#8E1B22",
            "primaryRegion": "#E6D545",
            "secondaryRegion": "#3D7EA6",
            "tertiaryRegion": "#C9852A",
            "activeLocation": "#E6D545",
        },
        "borders": {"selected": "#fff4d6", "glow": "#ffd27a"},
        "marker": {"fill": "#E6D545", "outline": "#fff8ec", "hole": "#fff8ec", "shadow": "#00000055"},
        "labels": {"text": "#fff8ec", "outline": "#08121b", "shadow": "#030917", "secondaryText": "#9aa7b5"},
        "callout": {"background": "rgba(18,28,48,0.92)", "text": "#fff8ec", "arrow": "#e8d5a3", "border": "#e8d5a3"},
        "dateBanner": {"background": "#08121bcc", "text": "#fff8ec"},
        "routes": {"primary": "#e8d5a3", "secondary": "#9aa7b5"},
    },
)
DOCUMENTARY_RELIEF_BOLD = _attach_contract(
    DOCUMENTARY_RELIEF_BOLD,
    "Documentary Relief",
    "The current default. Graded relief, glowing location dots, and the approved documentary framing.",
    _DOC_CAPS,
    _DOC_TOKENS,
)

CLEAN_ATLAS["role_opacity"] = {"country": 0.7, "focus": [0.84, 0.8, 0.76]}

THEMES = {
    "cinematic_terrain": CINEMATIC_TERRAIN,
    "documentary_relief_bold": DOCUMENTARY_RELIEF_BOLD,
    "clean_atlas": CLEAN_ATLAS,
    "midnight_amber": MIDNIGHT_AMBER,
    "archival_earth": ARCHIVAL_EARTH,
}
DEFAULT_STYLE = "documentary_relief_bold"


def theme_ids() -> frozenset:
    return frozenset(THEMES)


def theme_hash(theme: dict) -> str:
    payload = {
        "schema_version": theme.get("schema_version"),
        "id": theme.get("id"),
        "revision": theme.get("revision"),
        "capabilities": theme.get("capabilities"),
        "tokens": _normalize_colors(theme.get("tokens")),
        "palette": _normalize_colors(theme.get("palette")),
        "terrain": theme.get("terrain"),
        "fill": theme.get("fill"),
        "marker": _normalize_colors(theme.get("marker")),
        "boundary": theme.get("boundary"),
        "ocean": _norm_color(theme.get("ocean")),
        "land": _norm_color(theme.get("land")),
        "land_opacity": theme.get("land_opacity"),
        "vignette": theme.get("vignette"),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _norm_color(value):
    if not isinstance(value, str):
        return value
    text = value.strip()
    if text.startswith("#"):
        return text.upper()
    return text


def _normalize_colors(value):
    if isinstance(value, dict):
        return {key: _normalize_colors(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_colors(item) for item in value]
    if isinstance(value, str) and (value.startswith("#") or value.startswith("rgb")):
        return _norm_color(value)
    return value


def theme_for(style: str) -> dict:
    if style not in THEMES:
        known = ", ".join(sorted(THEMES))
        raise KeyError(f"Unknown map style '{style}'. Known: {known}")
    theme = copy.deepcopy(THEMES[style])
    theme["theme_hash"] = theme_hash(theme)
    return theme


def camera_profile(theme: dict) -> str:
    profile = (theme.get("capabilities") or {}).get("camera_profile")
    if profile:
        return profile
    return "documentary" if theme.get("id") == "documentary_relief_bold" else "cinematic"


def applies_palette(theme: dict) -> bool:
    caps = theme.get("capabilities") or {}
    if "apply_palette" in caps:
        return bool(caps["apply_palette"])
    return theme.get("id") == "documentary_relief_bold"


def palette_roles(theme: dict) -> dict:
    tokens = theme.get("tokens") or {}
    highlights = tokens.get("highlights") or {}
    marker = tokens.get("marker") or {}
    palette = theme.get("palette") or {}
    opacity = theme.get("role_opacity") or {"country": 0.72, "focus": [0.34, 0.4, 0.42]}
    focus_opacity = list(opacity.get("focus") or [0.34, 0.4, 0.42])
    colors = [
        highlights.get("primaryRegion") or palette.get("yellow"),
        highlights.get("secondaryRegion") or palette.get("cyan"),
        highlights.get("tertiaryRegion") or palette.get("royal_blue"),
    ]
    role_markers = marker.get("roles") or [
        marker.get("fill") or palette.get("marker_yellow"),
        marker.get("fill") or palette.get("marker_cyan"),
        marker.get("fill") or palette.get("marker_yellow"),
    ]
    return {
        "country": {
            "color": highlights.get("country") or palette.get("country_red"),
            "fill_opacity": opacity.get("country", 0.72),
            "marker": None,
        },
        "focus": [
            {"color": colors[index], "fill_opacity": focus_opacity[index % len(focus_opacity)], "marker": role_markers[index]}
            for index in range(3)
        ],
    }


def validate_color(value: str) -> str:
    if not isinstance(value, str) or not COLOR.match(value.strip()):
        raise ValueError(f"Unsupported colour '{value}'.")
    return _norm_color(value.strip()) if value.strip().startswith("#") else value.strip()


_OVERRIDE_CONTROLS = {
    "marker_shape",
    "basemap_mode",
    "font_latin",
    "font_devanagari",
    "marker_height",
    "outline_width",
    "shadow_strength",
    "hole_mode",
    "pulse",
}


def _bounded_number(value, low: float, high: float, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a number.") from error
    if number < low or number > high:
        raise ValueError(f"{label} must be between {low:g} and {high:g}.")
    return number


def apply_token_overrides(style: str, overrides: dict | None, *, theme_id: str | None = None, name: str | None = None, base_theme: dict | None = None) -> dict:
    """Deep-copy a template and replace only supplied semantic tokens."""
    if isinstance(base_theme, dict) and base_theme.get("tokens") and base_theme.get("id"):
        theme = copy.deepcopy(base_theme)
        style = str(theme.get("base_id") or style or DEFAULT_STYLE)
    else:
        theme = theme_for(style if style in THEMES else DEFAULT_STYLE)
    if not overrides:
        if theme_id:
            theme["id"] = theme_id
            theme["base_id"] = style if style in THEMES else theme.get("base_id", style)
            theme["theme_hash"] = theme_hash(theme)
        return theme
    tokens = theme.setdefault("tokens", {})
    for group, values in overrides.items():
        if group in _OVERRIDE_CONTROLS:
            continue
        if not isinstance(values, dict) or group not in tokens:
            raise ValueError(f"Unknown appearance group '{group}'.")
        for key, value in values.items():
            if key not in tokens[group]:
                raise ValueError(f"Unknown appearance token '{group}.{key}'.")
            if isinstance(tokens[group][key], list):
                raise ValueError(f"Token '{group}.{key}' cannot be edited directly.")
            text = str(value).strip()
            if group == "marker" and key == "hole" and text.lower() == "transparent":
                tokens[group][key] = "transparent"
            else:
                tokens[group][key] = validate_color(text)
    shape = overrides.get("marker_shape")
    if shape:
        if shape not in {"glow_dot", "pin", "ring"}:
            raise ValueError("Marker shape must be glow_dot, pin, or ring.")
        theme["capabilities"]["marker_shape"] = shape
        theme["marker"]["shape"] = shape
    basemap = overrides.get("basemap_mode")
    if basemap:
        if basemap not in {"flat_atlas", "graded_relief"}:
            raise ValueError("Basemap must be flat_atlas or graded_relief.")
        theme["capabilities"]["basemap_mode"] = basemap
        theme["capabilities"]["exact_land_ocean"] = basemap == "flat_atlas"
        if basemap == "flat_atlas":
            theme["fill"]["mode"] = "solid"
            theme["land_opacity"] = 1
            theme["terrain"]["use_graded_relief"] = False
            theme["capabilities"]["fill_treatment"] = "solid"
            theme["capabilities"]["vignette"] = "none"
            theme["vignette"] = "none"
        else:
            theme["capabilities"]["exact_land_ocean"] = False
            theme["fill"]["mode"] = "terrain_color"
            theme["terrain"]["use_graded_relief"] = True
            theme["capabilities"]["fill_treatment"] = "terrain_color"
            if float(theme.get("land_opacity") or 0) >= 1:
                theme["land_opacity"] = 0.08
    font = overrides.get("font_latin")
    if font:
        if font not in FONTS:
            raise ValueError("Choose an installed map font.")
        theme["label"]["font_latin"] = font
    font_hi = overrides.get("font_devanagari")
    if font_hi:
        if font_hi not in FONTS:
            raise ValueError("Choose an installed map font.")
        theme["label"]["font_devanagari"] = font_hi
    if "marker_height" in overrides and overrides["marker_height"] not in ("", None):
        theme["marker"]["height"] = _bounded_number(overrides["marker_height"], 28, 72, "Marker size")
    if "outline_width" in overrides and overrides["outline_width"] not in ("", None):
        theme["marker"]["outline_width"] = _bounded_number(overrides["outline_width"], 0, 8, "Outline width")
    if "shadow_strength" in overrides and overrides["shadow_strength"] not in ("", None):
        theme["marker"]["shadow_strength"] = _bounded_number(overrides["shadow_strength"], 0, 1, "Shadow strength")
    hole_mode = overrides.get("hole_mode")
    if hole_mode:
        if hole_mode not in {"transparent", "filled"}:
            raise ValueError("Marker hole must be transparent or filled.")
        if hole_mode == "transparent":
            theme["marker"]["hole"] = "transparent"
            tokens.setdefault("marker", {})["hole"] = "transparent"
        else:
            hole_color = theme["marker"].get("hole_color") or "#FFFFFF"
            theme["marker"]["hole"] = hole_color
            tokens.setdefault("marker", {})["hole"] = hole_color
    if "pulse" in overrides and overrides["pulse"] not in ("", None):
        theme["marker"]["pulse"] = str(overrides["pulse"]).lower() in {"1", "true", "yes", "on"}
    _sync_legacy_from_tokens(theme)
    theme["customized"] = True
    if style in THEMES:
        theme["base_id"] = style
    if theme_id:
        theme["id"] = theme_id
    if name:
        theme["name"] = name
    theme["builtin"] = False
    theme["revision"] = int(theme.get("revision") or 1)
    theme["theme_hash"] = theme_hash(theme)
    return theme


def _sync_legacy_from_tokens(theme: dict) -> None:
    tokens = theme.get("tokens") or {}
    background = tokens.get("background") or {}
    highlights = tokens.get("highlights") or {}
    borders = tokens.get("borders") or {}
    marker = tokens.get("marker") or {}
    labels = tokens.get("labels") or {}
    callout = tokens.get("callout") or {}
    banner = tokens.get("dateBanner") or {}
    if background.get("ocean"):
        theme["ocean"] = background["ocean"]
        theme["ocean_openlayers"] = background["ocean"]
    if background.get("land"):
        theme["land"] = background["land"]
    if background.get("contextBorder"):
        theme["border"] = background["contextBorder"]
    palette = theme.setdefault("palette", {})
    palette["country_red"] = highlights.get("country") or palette.get("country_red")
    palette["country_red_deep"] = highlights.get("countryDeep") or palette.get("country_red_deep")
    palette["yellow"] = highlights.get("primaryRegion") or palette.get("yellow")
    palette["cyan"] = highlights.get("secondaryRegion") or palette.get("cyan")
    palette["royal_blue"] = highlights.get("tertiaryRegion") or palette.get("royal_blue")
    fill = marker.get("fill")
    if fill and not marker.get("roles"):
        palette["marker_yellow"] = fill
        palette["marker_cyan"] = fill
        theme["marker"]["fill"] = fill
    if marker.get("outline"):
        theme["marker"]["outline"] = marker["outline"]
    if marker.get("shadow"):
        theme["marker"]["shadow"] = marker["shadow"]
    if labels.get("text"):
        theme["ink"] = labels["text"]
        theme["label"]["color"] = labels["text"]
        palette["label"] = labels["text"]
    if labels.get("shadow"):
        theme["label"]["shadow"] = labels["shadow"]
    if labels.get("secondaryText"):
        theme["muted"] = labels["secondaryText"]
    if borders.get("selected"):
        theme["border_selected"] = borders["selected"]
    if borders.get("glow"):
        theme["border_glow"] = borders["glow"]
    if callout.get("background"):
        theme["callout_box"] = callout["background"]
    if callout.get("border"):
        theme["callout_border"] = callout["border"]
    if callout.get("text"):
        theme["callout_text"] = callout["text"]
    if callout.get("arrow"):
        theme["gold"] = callout["arrow"]
    if banner.get("background"):
        theme["date_banner"]["fill"] = banner["background"]
        theme["caption_bg"] = banner["background"]
        palette["date_banner"] = banner["background"]
    if banner.get("text"):
        theme["date_banner"]["text"] = banner["text"]


def resolve_theme(style: str | None, job_settings: dict | None = None) -> dict:
    """Use the job snapshot when it has a theme. Otherwise use the built-in style."""
    snapshot = (job_settings or {}).get("map_theme") if isinstance(job_settings, dict) else None
    if isinstance(snapshot, dict) and snapshot.get("tokens") and snapshot.get("id"):
        theme = copy.deepcopy(snapshot)
        theme["theme_hash"] = theme_hash(theme)
        return theme
    return theme_for(style or DEFAULT_STYLE)


def public_theme(theme: dict) -> dict:
    return {
        "schema_version": theme.get("schema_version"),
        "id": theme.get("id"),
        "name": theme.get("name") or theme.get("id"),
        "description": theme.get("description") or "",
        "revision": theme.get("revision"),
        "builtin": bool(theme.get("builtin")),
        "theme_hash": theme.get("theme_hash"),
        "capabilities": theme.get("capabilities"),
        "tokens": theme.get("tokens"),
        "marker_shape": (theme.get("marker") or {}).get("shape"),
    }


def export_builtin_json(path: Path | None = None) -> Path:
    target = path or BUILTIN_JSON
    target.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "schema_version": SCHEMA_VERSION,
        "default_theme_id": DEFAULT_STYLE,
        "fonts": list(FONTS),
        "grade_note": (
            "Flat atlas applies ocean and land colours directly and hides the relief raster. "
            "Graded relief keeps terrain detail. Its ocean colour is the background behind the raster, "
            "and land colour is a light wash. Saturation, contrast, brightness, and hue are grade controls, "
            "not exact land or ocean recolouring. Midnight Amber uses brightness_max 0.62 and hue_rotate 12. "
            "Archival Earth uses hue_rotate -16 and saturation 0.18."
        ),
        "themes": [public_theme(theme_for(theme_id)) | {"resolved": theme_for(theme_id)} for theme_id in (
            "documentary_relief_bold", "clean_atlas", "midnight_amber", "archival_earth", "cinematic_terrain"
        )],
    }
    target.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target
