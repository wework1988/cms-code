"""Compile semantic plan + resolved geography into a renderer-ready resolved plan."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from map_story.opening import (
    COMPOSITION_VERSION,
    DEFAULT_COUNTRY_PADDING,
    PRESENTATION_VERSION,
    joint_country_opening_ids,
    job_settings_from_snapshot,
    opening_policy_record,
    resolve_primary_country_id,
    trusted_world_opening_requested,
    validate_country_centered_opening,
)
from map_story.schema import SUPPORTED_STYLES
from map_story.themes import camera_profile, resolve_theme, theme_for

LAB = Path(__file__).resolve().parent.parent

# Backward-compatible alias. New compiles use theme_for(style).
THEME = theme_for("cinematic_terrain")


def _lon_span(west: float, east: float) -> float:
    span = float(east) - float(west)
    if span < 0:
        span += 360.0
    if span > 180.0:
        span = 360.0 - span
    return max(0.01, span)


def _lon_midpoint(west: float, east: float) -> float:
    west = float(west)
    east = float(east)
    span_raw = east - west
    if span_raw < 0:
        east += 360.0
    span = east - west
    if span > 180.0:
        # Prefer the short arc near the date line.
        west += 360.0
        span = east - west
    mid = west + span * 0.5
    while mid > 180.0:
        mid -= 360.0
    while mid < -180.0:
        mid += 360.0
    return mid


def _lon_near_center(lon: float, center_lon: float) -> float:
    best = float(lon)
    dist = abs(best - center_lon)
    for shift in (-360.0, 360.0):
        shifted = best + shift
        d = abs(shifted - center_lon)
        if d < dist:
            best = shifted
            dist = d
    return best


def _mercator_y(lat: float) -> float:
    lat = max(min(lat, 85.05112878), -85.05112878)
    rad = math.radians(lat)
    return math.log(math.tan(math.pi / 4 + rad / 2))


def _lat_from_mercator(y: float) -> float:
    return math.degrees(2 * math.atan(math.exp(y)) - math.pi / 2)


def project_lonlat(
    lon: float,
    lat: float,
    center: list[float],
    zoom: float,
    width: int,
    height: int,
    *,
    tile_size: int = 512,
) -> tuple[float, float]:
    """Screen pixel for a lon/lat. tile_size 512 matches MapLibre; 256 matches OpenLayers."""
    world = tile_size * (2 ** zoom)

    def mercator_unit_y(latitude: float) -> float:
        clamped = max(min(latitude, 85.05112878), -85.05112878)
        sine = math.sin(math.radians(clamped))
        return 0.5 - math.log((1 + sine) / (1 - sine)) / (4 * math.pi)

    def world_xy(longitude: float, latitude: float) -> tuple[float, float]:
        return (longitude + 180.0) / 360.0 * world, mercator_unit_y(latitude) * world

    cx, cy = world_xy(center[0], center[1])
    x, y = world_xy(_lon_near_center(lon, center[0]), lat)
    return (x - cx) + width / 2.0, (y - cy) + height / 2.0


def minimum_edge_margin(
    bbox: list[float],
    center: list[float],
    zoom: float,
    width: int,
    height: int,
    *,
    tile_size: int = 512,
) -> float:
    """Smallest fraction of the frame between the bbox and an edge. Negative means cropped."""
    west, south, east, north = bbox
    xs = []
    ys = []
    for lon, lat in ((west, south), (west, north), (east, south), (east, north)):
        x, y = project_lonlat(lon, lat, center, zoom, width, height, tile_size=tile_size)
        xs.append(x)
        ys.append(y)
    return min(min(xs) / width, (width - max(xs)) / width, min(ys) / height, (height - max(ys)) / height)


def zoom_for_bounds(
    bbox: list[float],
    width: int,
    height: int,
    *,
    padding: float = 0.10,
    max_zoom: float = 11.0,
    min_zoom: float = 0.8,
    pitch_deg: float = 0.0,
    tile_size: int = 512,
) -> tuple[list[float], float]:
    """Fit a lon/lat bbox in the viewport.

    padding is the safe margin on each edge, as a fraction of the frame.
    The center is the mercator midpoint so north and south stay inside together.
    tile_size 512 is MapLibre's world size at zoom 0. OpenLayers uses 256.
    """
    west, south, east, north = bbox
    inset = max(0.0, min(0.4, float(padding)))
    pitch_factor = 1.0 + max(0.0, pitch_deg) / 90.0 * 0.35
    usable_w = width * (1 - 2 * inset)
    usable_h = height * (1 - 2 * inset) / pitch_factor
    my0 = _mercator_y(south)
    my1 = _mercator_y(north)
    center = [_lon_midpoint(west, east), _lat_from_mercator((my0 + my1) / 2.0)]
    circumference = 2 * math.pi * 6378137.0
    metres_per_pixel_z0 = circumference / tile_size
    lon_metres = _lon_span(west, east) / 360.0 * circumference * math.cos(math.radians(center[1]))
    lat_metres = abs(my1 - my0) * 6378137.0

    def zoom_for_metres(metres: float, pixels: float) -> float:
        return math.log2((metres_per_pixel_z0 * pixels) / max(metres, 1.0))

    zoom = min(zoom_for_metres(lon_metres, usable_w), zoom_for_metres(lat_metres, usable_h), max_zoom)
    zoom = max(min_zoom, zoom)
    return center, zoom


def world_frame(width: int, height: int) -> dict:
    """Explicit world-overview override only; default openings are country-centered."""
    return {
        "center": [20.0, 20.0],
        "zoom": 1.35 if width >= 1600 else 1.15,
        "pitch": 0,
        "bearing": 0,
    }


def load_terrain_meta(rel_json: str) -> dict:
    data = json.loads((LAB / rel_json).read_text(encoding="utf-8"))
    return data


def callout_screen_position(
    position: str,
    anchor_lonlat: list[float],
    camera_center: list[float],
) -> list[float]:
    """Normalised screen [x,y] for the text box."""
    if position == "left":
        return [0.18, 0.28]
    if position == "right":
        return [0.78, 0.30]
    if position == "top":
        return [0.55, 0.18]
    if position == "bottom":
        return [0.62, 0.78]
    # auto: prefer right if feature is left of frame centre, else left
    if anchor_lonlat[0] <= camera_center[0]:
        return [0.76, 0.30]
    return [0.20, 0.32]


def _estimate_text_bounds(text: str, size: float) -> tuple[float, float]:
    stripped = str(text or "").strip()
    if not stripped:
        return (0.0, 0.0)
    devanagari = any("\u0900" <= ch <= "\u097f" for ch in stripped)
    width_factor = 0.9 if devanagari else 0.62
    width = max(size * 1.4, len(stripped) * size * width_factor)
    # Single-line estimate; renderer may wrap further.
    height = size * 1.26
    return width, height


def _sample_camera(keyframes: list[dict], t: float) -> dict:
    if t <= keyframes[0]["t"]:
        return keyframes[0]
    if t >= keyframes[-1]["t"]:
        return keyframes[-1]
    index = 0
    while index < len(keyframes) - 1 and keyframes[index + 1]["t"] < t:
        index += 1
    a = keyframes[index]
    b = keyframes[index + 1]
    span = max(1e-6, b["t"] - a["t"])
    u = max(0.0, min(1.0, (t - a["t"]) / span))
    return {
        "t": t,
        "center": [a["center"][0] + (b["center"][0] - a["center"][0]) * u, a["center"][1] + (b["center"][1] - a["center"][1]) * u],
        "zoom": a["zoom"] + (b["zoom"] - a["zoom"]) * u,
        "pitch": (a.get("pitch", 0.0) + (b.get("pitch", 0.0) - a.get("pitch", 0.0)) * u),
        "bearing": (a.get("bearing", 0.0) + (b.get("bearing", 0.0) - a.get("bearing", 0.0)) * u),
    }


def compile_resolved_plan(
    semantic: dict,
    resolved_places: dict[str, dict],
    *,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
    engine_hint: str = "maplibre",
    job_settings: dict | None = None,
) -> dict:
    if not (320 <= int(width) <= 3840 and 240 <= int(height) <= 2160):
        raise ValueError(f"Unsupported output size {width}x{height}")
    if not (1 <= int(fps) <= 60):
        raise ValueError(f"Unsupported fps {fps}")
    style = semantic.get("style") or "cinematic_terrain"
    custom_style = isinstance(style, str) and style.startswith("custom_")
    if style not in SUPPORTED_STYLES and not custom_style:
        raise ValueError(f"Unsupported style '{style}'")
    theme = resolve_theme(style, job_settings)
    duration = float(semantic["duration_seconds"])
    highlights: list[dict] = []
    labels: list[dict] = []
    callout = None
    keyframes: list[dict] = []

    # Active primary highlight state for persistence across shots.
    active_primary: dict[str, dict] = {}
    active_context: dict[str, dict] = {}
    markers: list[dict] = []
    settings = job_settings if job_settings is not None else job_settings_from_snapshot(semantic)
    primary_country_id, _primary_reason = resolve_primary_country_id(semantic)
    allow_world_opening = trusted_world_opening_requested(settings)
    joint_countries = (
        joint_country_opening_ids(semantic, resolved_places, primary_id=primary_country_id)
        if allow_world_opening
        else None
    )
    world_terrain = load_terrain_meta("assets/maps/world/world-relief.json")
    regional_path = "assets/maps/south-asia-relief.json"
    if not (LAB / regional_path).is_file():
        regional_path = "assets/maps/india/india-relief.json"
    regional_terrain = load_terrain_meta(regional_path)
    relief_limited = False
    country_place = resolved_places.get(primary_country_id or "")
    country_box = country_place.get("bbox") if country_place else None
    regional_extent = regional_terrain.get("extent") or []
    if country_box and len(regional_extent) == 4:
        west, south, east, north = country_box
        relief_limited = not (
            west >= regional_extent[0] and south >= regional_extent[1]
            and east <= regional_extent[2] and north <= regional_extent[3]
        )

    def frame_bbox(place: dict) -> list[float]:
        if place.get("representation") == "point":
            lon, lat = place["anchor"]
            parent = resolved_places.get(place.get("parent") or "")
            if parent and parent.get("bbox"):
                pbox = parent["bbox"]
                plon = _lon_span(pbox[0], pbox[2])
                plat = max(0.08, pbox[3] - pbox[1])
                span_lon = max(0.55, min(3.9, plon * 0.42))
                span_lat = max(0.40, min(2.8, plat * 0.42))
            else:
                span_lon = 1.45 if camera_profile(theme) == "documentary" else 0.9
                span_lat = span_lon * 0.72
            return [lon - span_lon, lat - span_lat, lon + span_lon, lat + span_lat]
        return place["bbox"]

    def push_camera(t: float, frame: str, padding: float, pitch: float) -> dict:
        if frame == "world":
            if allow_world_opening:
                cam = world_frame(width, height)
                cam.update({"t": t, "pitch": pitch, "bearing": 0})
                return cam
            if primary_country_id and primary_country_id in resolved_places:
                frame = primary_country_id
                padding = padding or DEFAULT_COUNTRY_PADDING
            else:
                cam = world_frame(width, height)
                cam.update({"t": t, "pitch": pitch, "bearing": 0})
                return cam
        place = resolved_places[frame]
        # Reserve space for callout on final district framing.
        pad = padding
        if place.get("representation") == "point":
            max_zoom = 7.15 if camera_profile(theme) == "documentary" else 8.6
        else:
            max_zoom = 11.2 if place["level"] == "district" else 9.5
        if relief_limited:
            max_zoom = min(max_zoom, 5.2)
        center, zoom = zoom_for_bounds(
            frame_bbox(place), width, height, padding=pad, max_zoom=max_zoom,
            pitch_deg=pitch,
            tile_size=512 if engine_hint == "maplibre" else 256,
        )
        # Nudge center slightly away from callout side on district hold.
        return {
            "t": t,
            "center": center,
            "zoom": zoom,
            "pitch": pitch,
            "bearing": 0,
        }

    # Opening keyframe uses the first shot's own fit, so frame 0 is not a tighter default.
    first = semantic["shots"][0]
    first_pad = 0.10
    for action in first.get("actions") or []:
        if action.get("type") == "zoom_to_boundary":
            first_pad = float(action.get("padding", first_pad))
            break
    keyframes.append(push_camera(0.0, first["frame"], first_pad, 0.0))

    for shot in semantic["shots"]:
        start = float(shot["start"])
        end = float(shot["end"])
        frame = shot["frame"]
        padding = 0.12
        pitch = 0.0
        moving = False

        for action in shot["actions"]:
            atype = action["type"]
            if atype == "zoom_to_boundary":
                moving = True
                padding = float(action.get("padding", 0.14 if action["place"] == "india" else 0.12))
                max_pitch = (theme.get("camera") or {}).get("max_pitch")
                if (
                    engine_hint == "maplibre"
                    and action["place"] in ("uttar_pradesh", "gorakhpur")
                    and max_pitch != 0
                ):
                    pitch = 18.0 if action["place"] == "uttar_pradesh" else 22.0
                fitted = push_camera(start, action["place"], padding, pitch)
                # Hold keeps the fitted view for the whole shot, including frame 0.
                if action.get("motion") == "hold":
                    if keyframes and abs(keyframes[0]["t"] - start) < 1e-6:
                        keyframes[0] = dict(fitted)
                        keyframes[0]["t"] = start
                    end_cam = dict(fitted)
                    end_cam["t"] = end
                    keyframes.append(end_cam)
                else:
                    arrive = start + max(0.35, (end - start) * 0.72)
                    keyframes.append(push_camera(arrive, action["place"], padding, pitch))
                    end_cam = push_camera(end, action["place"], padding, pitch)
                    keyframes.append(end_cam)
            elif atype == "establish_view":
                moving = True
                if allow_world_opening and action.get("scope") == "countries" and joint_countries:
                    boxes = [
                        resolved_places[cid]["bbox"]
                        for cid in joint_countries
                        if cid in resolved_places and resolved_places[cid].get("bbox")
                    ]
                    if boxes:
                        union = [
                            min(box[0] for box in boxes),
                            min(box[1] for box in boxes),
                            max(box[2] for box in boxes),
                            max(box[3] for box in boxes),
                        ]
                        center, zoom = zoom_for_bounds(
                            union, width, height, padding=DEFAULT_COUNTRY_PADDING, pitch_deg=0,
                            tile_size=512 if engine_hint == "maplibre" else 256,
                        )
                        fitted = {"t": start, "center": center, "zoom": zoom, "pitch": 0.0, "bearing": 0}
                        if keyframes and abs(keyframes[0]["t"] - start) < 1e-6:
                            keyframes[0] = dict(fitted)
                        else:
                            keyframes.append(dict(fitted))
                        end_cam = dict(fitted)
                        end_cam["t"] = end
                        keyframes.append(end_cam)
                        continue
                if allow_world_opening:
                    scope = str(action.get("scope") or "").lower()
                    if scope in ("world", "global", "planet"):
                        keyframes.append(push_camera(start, "world", DEFAULT_COUNTRY_PADDING, 0))
                        keyframes.append(push_camera(end, "world", DEFAULT_COUNTRY_PADDING, 0))
                        continue
                target = action.get("place") or primary_country_id
                if not allow_world_opening and primary_country_id:
                    target = primary_country_id
                if target and target in resolved_places:
                    pad = float(action.get("padding", DEFAULT_COUNTRY_PADDING))
                    fitted = push_camera(start, str(target), pad, 0.0)
                    if keyframes and abs(keyframes[0]["t"] - start) < 1e-6:
                        keyframes[0] = dict(fitted)
                        keyframes[0]["t"] = start
                    else:
                        keyframes.append(dict(fitted))
                    end_cam = dict(fitted)
                    end_cam["t"] = end
                    keyframes.append(end_cam)
                    continue
                keyframes.append(push_camera(start, "world", DEFAULT_COUNTRY_PADDING, 0))
                keyframes.append(push_camera(end, "world", DEFAULT_COUNTRY_PADDING, 0))
            elif atype == "hold":
                # Keep last camera; add explicit end keyframe
                last = dict(keyframes[-1])
                last["t"] = end
                keyframes.append(last)
            elif atype == "show_marker":
                place = action["place"]
                if resolved_places[place].get("representation") != "point":
                    raise ValueError(f"{place} has a boundary; use highlight rather than show_marker")
                markers.append({
                    "place": place,
                    "anchor": resolved_places[place]["anchor"],
                    "color": action.get("color", "#E6D545"),
                    "size": float(action.get("size", 11)),
                    "pulse": bool(action.get("pulse", False)),
                    "from": start + float(action.get("from_offset", 0)),
                    "to": duration,
                })
            elif atype == "highlight":
                place = action["place"]
                if resolved_places[place].get("representation") == "point":
                    markers.append({
                        "place": place,
                        "anchor": resolved_places[place]["anchor"],
                        "color": action.get("color", "#E6D545"),
                        "size": 11,
                        "pulse": False,
                        "from": start,
                        "to": duration,
                    })
                    continue
                color = action["color"]
                opacity = float(action.get("fill_opacity", 0.48))
                reveal_at = start + float(action.get("from_offset", 0))
                parent_context = action.get("parent_context")
                parent = None
                for p in semantic["places"]:
                    if p["id"] == place:
                        parent = p.get("parent")
                        break
                # Demote parent when requested, or automatically when a child takes focus.
                if parent and (parent_context in ("subdued", "hidden") or parent in active_primary):
                    prev = active_primary.pop(parent, {"color": color, "fill_opacity": 0.45})
                    for hl in reversed(highlights):
                        if hl["place"] == parent and hl["role"] == "primary" and hl["to"] == duration:
                            hl["to"] = start
                            hl["fade_out"] = 0
                            break
                    if parent_context == "hidden":
                        active_context.pop(parent, None)
                    else:
                        parent_level = resolved_places.get(parent, {}).get("level")
                        keep_country = bool(theme.get("persist_parent_fill")) and parent_level == "country"
                        if keep_country:
                            context_opacity = float(prev.get("fill_opacity", opacity))
                            context_border = True
                            context_strength = "country"
                        else:
                            context_opacity = 0.16 if parent_context == "subdued" else 0.22
                            context_border = False
                            context_strength = "region"
                        highlights.append({
                            "place": parent,
                            "color": prev.get("color", "#E52B32"),
                            "fill_opacity": context_opacity,
                            "from": reveal_at,
                            "to": duration,
                            "role": "context",
                            "border": context_border,
                            "border_strength": context_strength,
                        })
                        active_context[parent] = True
                place_level = resolved_places[place]["level"]
                highlights.append({
                    "place": place,
                    "color": color,
                    "fill_opacity": opacity,
                    "from": reveal_at,
                    "to": duration,
                    "role": "primary",
                    "border": True,
                    "border_strength": "country" if place_level == "country" else "region",
                })
                active_primary[place] = {"color": color, "fill_opacity": opacity, "from": start}
            elif atype == "show_label":
                place = action["place"]
                level = resolved_places[place]["level"]
                label_cfg = theme.get("label") or {}
                sizes = label_cfg.get("sizes") or {}
                frame_level = resolved_places.get(frame, {}).get("level") if frame != "world" else None
                if action.get("size") is not None:
                    size = float(action["size"])
                elif sizes and level == "city" and frame_level != "city":
                    size = label_cfg.get("supporting_size", 40)
                elif sizes:
                    size = sizes.get(level, 48)
                else:
                    size = 56 if level == "country" else 48
                visible_from = start
                if action.get("from_offset") is not None:
                    visible_from = start + float(action["from_offset"])
                elif label_cfg.get("reveal_after_camera"):
                    span = max(0.01, end - start)
                    has_move = any(
                        a.get("type") in ("zoom_to_boundary", "establish_view")
                        and a.get("motion") != "hold"
                        for a in shot["actions"]
                    )
                    visible_from = start + (max(0.5, span * 0.72) if has_move else 0.4)
                if action.get("offset_y") is not None:
                    offset_y = float(action["offset_y"])
                else:
                    offset_y = -78 if level == "city" and label_cfg.get("city_above_marker") else 0
                focus_until = end
                visible_until = end
                rest_opacity = None
                if label_cfg.get("persist_after_focus"):
                    visible_until = duration
                    rest_opacity = float(action.get("rest_opacity", 0.0 if level == "country" else (0.55 if level == "city" else 0.38)))
                    if action.get("hold_focus"):
                        rest_opacity = 1
                label_row = {
                    "place": place,
                    "text": action["text"],
                    "anchor": resolved_places[place]["anchor"],
                    "visible_from": visible_from,
                    "visible_until": visible_until,
                    "focus_until": focus_until,
                    "rest_opacity": rest_opacity,
                    "size": size,
                    "offset_y": offset_y,
                    "level": level,
                }
                existing = next((item for item in labels if item["place"] == place), None)
                if existing:
                    existing["visible_from"] = min(existing["visible_from"], visible_from)
                    existing["visible_until"] = max(existing["visible_until"], visible_until)
                    existing["focus_until"] = max(existing["focus_until"], focus_until)
                    if action.get("hold_focus"):
                        existing["rest_opacity"] = 1
                else:
                    labels.append(label_row)
            elif atype == "show_callout":
                place = action["place"]
                callout_pitch = 16.0 if engine_hint == "maplibre" else 0
                if (theme.get("camera") or {}).get("max_pitch") == 0:
                    callout_pitch = 0
                cam = push_camera(start, frame, 0.22, callout_pitch)
                # Extra padding / nudge for callout space
                screen = callout_screen_position(
                    action.get("position", "auto"),
                    resolved_places[place]["anchor"],
                    cam["center"],
                )
                # Shift camera opposite the callout box slightly.
                bounds = frame_bbox(resolved_places[place])
                shift = 0.12 * (bounds[2] - bounds[0])
                if screen[0] > 0.5:
                    cam["center"] = [cam["center"][0] - shift, cam["center"][1]]
                else:
                    cam["center"] = [cam["center"][0] + shift, cam["center"][1]]
                cam["t"] = start
                keyframes.append(cam)
                end_cam = dict(cam)
                end_cam["t"] = end
                keyframes.append(end_cam)
                callout = {
                    "reveal": start,
                    "text": action["text"],
                    "place": place,
                    "anchor": resolved_places[place]["anchor"],
                    "screen": screen,
                    "presentation": action.get("presentation", "text_box_with_arrow"),
                }

        if not moving and shot["actions"] and all(a["type"] not in ("zoom_to_boundary", "establish_view", "hold", "show_callout") for a in shot["actions"]):
            # Static frame for the shot duration
            keyframes.append(push_camera(end, frame, 0.12, pitch))

    # Sort / dedupe keyframes by time
    keyframes.sort(key=lambda k: k["t"])
    cleaned = []
    for kf in keyframes:
        if cleaned and abs(cleaned[-1]["t"] - kf["t"]) < 1e-6:
            cleaned[-1] = kf
        else:
            cleaned.append(kf)
    # Ensure final keyframe at duration
    if cleaned[-1]["t"] < duration - 1e-6:
        last = dict(cleaned[-1])
        last["t"] = duration
        cleaned.append(last)

    def overlaps(a: dict, b: dict) -> bool:
        return not (
            a["x"] + a["w"] <= b["x"]
            or b["x"] + b["w"] <= a["x"]
            or a["y"] + a["h"] <= b["y"]
            or b["y"] + b["h"] <= a["y"]
        )

    label_theme = theme.get("label") or {}
    min_size = float(label_theme.get("min_size", 28))
    safe = float(label_theme.get("safe_margin", 0.06))
    safe_box = {
        "left": width * safe,
        "top": height * safe,
        "right": width * (1.0 - safe),
        "bottom": height * (1.0 - safe),
    }
    stages: list[dict[str, Any]] = []
    layout_warnings: list[str] = []
    tile = 512 if engine_hint == "maplibre" else 256
    for shot in semantic["shots"]:
        s0 = float(shot["start"])
        s1 = float(shot["end"])
        mid = s0 + (s1 - s0) * 0.5
        cam = _sample_camera(cleaned, mid)
        stage_targets = []
        for action in shot.get("actions") or []:
            if isinstance(action, dict) and action.get("place"):
                stage_targets.append(str(action["place"]))
        primary_target = stage_targets[-1] if stage_targets else (shot["frame"] if shot["frame"] != "world" else None)
        stage_labels = []
        accepted_boxes: list[dict[str, float]] = []
        for label in labels:
            if label["visible_until"] < s0 or label["visible_from"] > s1:
                continue
            place = resolved_places.get(label["place"])
            if not place:
                continue
            ax, ay = project_lonlat(place["anchor"][0], place["anchor"][1], cam["center"], cam["zoom"], width, height, tile_size=tile)
            level = label.get("level") or place.get("level")
            role = (
                "city_label" if level == "city" else
                "primary_area_label" if label["place"] == primary_target else
                "secondary_context_label"
            )
            preferred = float(label.get("size") or (label_theme.get("sizes", {}).get(level, 44)))
            clamped = max(min_size, min(preferred, float(label_theme.get("max_size", 96))))
            tw, th = _estimate_text_bounds(label["text"], clamped)
            # Internal label check for area features only.
            internal_ok = False
            if place.get("representation") != "point":
                west, south, east, north = place["bbox"]
                corners = [
                    project_lonlat(west, south, cam["center"], cam["zoom"], width, height, tile_size=tile),
                    project_lonlat(west, north, cam["center"], cam["zoom"], width, height, tile_size=tile),
                    project_lonlat(east, south, cam["center"], cam["zoom"], width, height, tile_size=tile),
                    project_lonlat(east, north, cam["center"], cam["zoom"], width, height, tile_size=tile),
                ]
                min_x = min(item[0] for item in corners)
                max_x = max(item[0] for item in corners)
                min_y = min(item[1] for item in corners)
                max_y = max(item[1] for item in corners)
                pad = max(10.0, clamped * 0.35)
                internal_ok = (
                    ax - tw / 2.0 >= min_x + pad
                    and ax + tw / 2.0 <= max_x - pad
                    and ay - th / 2.0 >= min_y + pad
                    and ay + th / 2.0 <= max_y - pad
                )
            placement = "internal_center" if internal_ok else ("external_right" if ax <= width * 0.5 else "external_left")
            if placement == "internal_center":
                cx, cy = ax, ay + float(label.get("offset_y") or 0.0)
            elif placement == "external_right":
                cx, cy = ax + tw * 0.6 + 24.0, ay
            else:
                cx, cy = ax - tw * 0.6 - 24.0, ay
            box = {"x": cx - tw / 2.0, "y": cy - th / 2.0, "w": tw, "h": th}
            if (
                box["x"] < safe_box["left"]
                or box["y"] < safe_box["top"]
                or box["x"] + box["w"] > safe_box["right"]
                or box["y"] + box["h"] > safe_box["bottom"]
            ):
                scale = 0.88
                while clamped > min_size:
                    clamped = max(min_size, clamped * scale)
                    tw, th = _estimate_text_bounds(label["text"], clamped)
                    if placement == "internal_center":
                        cx, cy = ax, ay + float(label.get("offset_y") or 0.0)
                    elif placement == "external_right":
                        cx, cy = ax + tw * 0.6 + 24.0, ay
                    else:
                        cx, cy = ax - tw * 0.6 - 24.0, ay
                    box = {"x": cx - tw / 2.0, "y": cy - th / 2.0, "w": tw, "h": th}
                    if (
                        box["x"] >= safe_box["left"]
                        and box["y"] >= safe_box["top"]
                        and box["x"] + box["w"] <= safe_box["right"]
                        and box["y"] + box["h"] <= safe_box["bottom"]
                    ):
                        break
            collision = next((existing for existing in accepted_boxes if overlaps(existing, box)), None)
            if collision is not None:
                layout_warnings.append(
                    f"{shot['id']}: label '{label['text']}' overlaps another label; using external fallback."
                )
                placement = "external_bottom" if placement == "internal_center" else placement
                cy = ay + th + 18.0
                box = {"x": cx - tw / 2.0, "y": cy - th / 2.0, "w": tw, "h": th}
            accepted_boxes.append(box)
            stage_labels.append({
                "place": label["place"],
                "text": label["text"],
                "role": role,
                "placement": placement,
                "anchor": [round(ax, 2), round(ay, 2)],
                "box": {k: round(v, 2) for k, v in box.items()},
                "font_size": round(clamped, 2),
                "text_bounds": {"width": round(tw, 2), "height": round(th, 2)},
                "reveal_interval": [round(max(label["visible_from"], s0), 3), round(min(label["visible_until"], s1), 3)],
            })
        stages.append({
            "id": shot["id"],
            "interval": [s0, s1],
            "purpose": "focus_stage",
            "primary_targets": [primary_target] if primary_target else [],
            "context_targets": [pid for pid in stage_targets[:-1] if pid != primary_target],
            "camera": {
                "center": [round(cam["center"][0], 6), round(cam["center"][1], 6)],
                "zoom": round(float(cam["zoom"]), 5),
                "pitch": round(float(cam.get("pitch", 0.0)), 3),
                "bearing": round(float(cam.get("bearing", 0.0)), 3),
            },
            "labels": stage_labels,
        })

    def terrain_url(meta: dict) -> str:
        url = meta["url"]
        if theme.get("terrain", {}).get("use_graded_relief") and url.endswith(".jpg"):
            graded = url[:-4] + "-doc.jpg"
            local = LAB / graded.lstrip("/")
            if local.is_file():
                return graded
        return url

    features_out = {}
    for pid, place in resolved_places.items():
        feature_out = {
            "id": place["id"],
            "name": place["name"],
            "level": place["level"],
            "parent": place.get("parent"),
            "source_id": place["source_id"],
            "representation": place.get("representation", "boundary"),
            "bbox": place["bbox"],
            "anchor": place["anchor"],
        }
        if place.get("feature"):
            feature_out["feature"] = place["feature"]
        if place.get("geojson"):
            feature_out["geojson"] = place["geojson"]
        features_out[pid] = feature_out

    # Trim highlight windows when a place is superseded as primary by a child focus
    # (keep India subdued while UP/district stay primary — already handled).

    attribution = (
        "Natural Earth II relief (PD) · Natural Earth countries (PD) · "
        "geoBoundaries IND ADM1 (CC BY 2.5 IN) · IND ADM2 (ODbL) · "
        "PAK ADM1/ADM2 (Public domain) · AFG ADM1/ADM2 (Public domain) · "
        "GeoNames (CC BY 4.0)"
    )

    resolved_out = {
        "schema_version": "1.0",
        "type": "map_focus_sequence",
        "duration": duration,
        "duration_seconds": duration,
        "fps": fps,
        "width": width,
        "height": height,
        "language": semantic.get("language", "hi"),
        "style": style,
        "presentation_version": PRESENTATION_VERSION,
        "attribution": attribution,
        "disclaimer": None,
        "theme": theme,
        "terrain": {
            "layers": [
                {
                    "id": "world",
                    "url": terrain_url(world_terrain),
                    "extent": world_terrain["extent"],
                    "coordinates": world_terrain["coordinates"],
                    "visible_until_zoom": 3.4,
                },
                *([] if relief_limited else [{
                    "id": "regional",
                    "url": terrain_url(regional_terrain),
                    "extent": regional_terrain["extent"],
                    "coordinates": regional_terrain["coordinates"],
                    "visible_from_zoom": 2.6,
                }]),
            ],
            # Convenience for engines that use a single active layer initially:
            "url": world_terrain["url"],
            "extent": world_terrain["extent"],
            "coordinates": world_terrain["coordinates"],
        },
        "context_geojson": "/assets/maps/countries.geojson",
        "features": features_out,
        "camera": {
            "openlayers_rotation": False,
            "openlayers_zoom_bias": 0.35,
            "keyframes": cleaned,
            "notes": "Compiled from feature bounds; not LLM zoom guesses.",
        },
        "highlights": highlights,
        "markers": markers,
        "labels": labels,
        "callout": callout,
        "composition": {
            "version": COMPOSITION_VERSION,
            "viewport": {"width": width, "height": height},
            "safe_area": safe_box,
            "opening": opening_policy_record(
                semantic,
                resolved_places,
                width=width,
                height=height,
                engine_hint=engine_hint,
                first_camera=cleaned[0] if cleaned else None,
                job_settings=settings,
            ),
            "stages": stages,
            "warnings": layout_warnings,
            "debug_overlay_available": True,
        },
        "captions": [],
        "persistence": {
            "highlights": "Primary highlights persist until superseded; parent_context=subdued demotes parent fill.",
            "labels": "Labels visible for their shot window with short fades.",
            "camera": "zoom_to_boundary interpolates across the shot; hold freezes framing.",
            "callout": "Appears at reveal and holds through duration.",
        },
        "qa_frames": list(semantic.get("qa_frames") or []),
        "date_banner": semantic.get("date_banner"),
        "limitations": [
            "Terrain is Natural Earth II 50m shaded relief, not live satellite imagery.",
            "The South Asia relief raster covers 45–115E, 0–50N, including India, Pakistan, and Afghanistan. City close-ups enlarge that raster; they do not add local detail.",
            "A country outside that raster drops the regional layer and caps zoom instead of switching to unrelated imagery.",
            "District-scale texture remains coarse.",
            "Boundaries and points come from the local catalogue. DeepSeek does not receive polygons.",
            "Point places use a marker and a regional camera extent. No city polygon is invented.",
        ],
    }
    if relief_limited:
        resolved_out["limitations"].append(
            "The primary country is outside the South Asia relief raster, so the regional layer was omitted and zoom was capped."
        )
    validate_country_centered_opening(resolved_out, job_settings=settings)
    return resolved_out


def atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
