import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import {
  highlightOpacity,
  preloadImage,
  sampleCamera,
  waitFrame,
  withTimeout,
} from "../util.js";

async function waitMapReady(map, timeoutMs = 45000) {
  await withTimeout(
    new Promise((resolve, reject) => {
      if (map.loaded()) {
        resolve();
        return;
      }
      const onLoad = () => {
        cleanup();
        resolve();
      };
      const onError = (e) => {
        cleanup();
        reject(e.error || e);
      };
      const cleanup = () => {
        map.off("load", onLoad);
        map.off("error", onError);
      };
      map.once("load", onLoad);
      map.once("error", onError);
    }),
    timeoutMs,
    "MapLibre style load",
  );
  await withTimeout(
    new Promise((resolve) => {
      const done = () => {
        if (map.areTilesLoaded()) {
          map.off("idle", done);
          map.off("render", done);
          resolve();
        }
      };
      if (map.areTilesLoaded()) {
        resolve();
        return;
      }
      map.on("idle", done);
      map.on("render", done);
      map.triggerRepaint();
    }),
    timeoutMs,
    "MapLibre sources ready",
  );
}

export async function createMapLibre(container, plan, featureData, contextData) {
  const start = plan.camera.keyframes[0];
  const theme = plan.theme;
  const layers = plan.terrain.layers || [];
  const world = layers.find((l) => l.id === "world") || plan.terrain;
  const regional = layers.find((l) => l.id === "regional");

  const flat = theme.capabilities?.basemap_mode === "flat_atlas";
  if (!flat) {
    await preloadImage(world.url);
    if (regional) await preloadImage(regional.url);
  }

  const sources = {
    context: {
      type: "geojson",
      data: contextData,
      promoteId: "ADMIN",
    },
  };
  if (!flat) {
    sources.relief_world = {
      type: "image",
      url: world.url,
      coordinates: world.coordinates,
    };
  }
  if (!flat && regional) {
    sources.relief_regional = {
      type: "image",
      url: regional.url,
      coordinates: regional.coordinates,
    };
  }

  const placeIds = Object.keys(plan.features).filter((pid) => plan.features[pid].representation !== "point");
  for (const pid of placeIds) {
    sources[`feat_${pid}`] = {
      type: "geojson",
      data: featureData[pid],
    };
  }

  const terrain = theme.terrain || {};
  const styleLayers = [
    {
      id: "sea",
      type: "background",
      paint: { "background-color": theme.ocean },
    },
  ];
  if (!flat) {
    styleLayers.push({
      id: "relief_world",
      type: "raster",
      source: "relief_world",
      paint: {
        "raster-fade-duration": 0,
        "raster-opacity": 1,
        "raster-saturation": terrain.saturation ?? -0.1,
        "raster-contrast": terrain.contrast ?? 0.16,
        "raster-brightness-min": terrain.brightness_min ?? 0,
        "raster-brightness-max": terrain.brightness_max ?? 1,
        "raster-hue-rotate": terrain.hue_rotate ?? 0,
      },
    });
  }
  if (!flat && regional) {
    styleLayers.push({
      id: "relief_regional",
      type: "raster",
      source: "relief_regional",
      paint: {
        "raster-fade-duration": 0,
        "raster-opacity": 0,
        "raster-saturation": terrain.regional_saturation ?? -0.08,
        "raster-contrast": terrain.regional_contrast ?? 0.2,
        "raster-brightness-min": terrain.brightness_min ?? 0,
        "raster-brightness-max": terrain.brightness_max ?? 1,
        "raster-hue-rotate": terrain.hue_rotate ?? 0,
      },
    });
  }
  styleLayers.push({
    id: "context-land",
    type: "fill",
    source: "context",
    paint: {
      "fill-color": theme.land,
      "fill-opacity": flat ? (theme.land_opacity ?? 1) : (theme.land_opacity ?? 0.04),
    },
  });
  styleLayers.push({
    id: "context-borders",
    type: "line",
    source: "context",
    paint: {
      "line-color": theme.border,
      "line-width": flat ? 1.1 : 0.55,
      "line-opacity": flat ? 0.9 : 0.28,
    },
  });

  for (const pid of placeIds) {
    styleLayers.push(
      {
        id: `fill_${pid}`,
        type: "fill",
        source: `feat_${pid}`,
        paint: { "fill-color": theme.palette?.country_red || "#E52B32", "fill-opacity": 0 },
      },
      {
        id: `glow_${pid}`,
        type: "line",
        source: `feat_${pid}`,
        paint: {
          "line-color": theme.border_glow,
          "line-width": 7,
          "line-blur": 5,
          "line-opacity": 0,
        },
      },
      {
        id: `edge_${pid}`,
        type: "line",
        source: `feat_${pid}`,
        paint: {
          "line-color": theme.border_selected,
          "line-width": 1.85,
          "line-opacity": 0,
        },
      },
    );
  }

  const map = new maplibregl.Map({
    container,
    interactive: false,
    attributionControl: false,
    fadeDuration: 0,
    canvasContextAttributes: { preserveDrawingBuffer: true, antialias: true },
    style: { version: 8, sources, layers: styleLayers },
    center: start.center,
    zoom: start.zoom,
    pitch: start.pitch ?? 0,
    bearing: start.bearing ?? 0,
  });

  await waitMapReady(map);

  function paintFor(t, zoom) {
    if (!flat && regional) {
      const from = regional.visible_from_zoom ?? 2.6;
      const until = world.visible_until_zoom ?? 3.4;
      const u = Math.max(0, Math.min(1, (zoom - from) / Math.max(0.01, until - from)));
      // Fully hide world once regional dominates so the regional image is not a floating inset.
      // Keep the world raster as a complete background. The regional image is a
      // rectangle that does not fill the viewport during the zoom, so hiding
      // the world early leaves visible edges.
      map.setPaintProperty("relief_world", "raster-opacity", 1);
      map.setPaintProperty("relief_regional", "raster-opacity", u);
    }

    // Reset then apply active highlights (later entries override earlier for same place+role)
    const byPlace = {};
    for (const hl of plan.highlights) {
      const o = highlightOpacity(hl, t, plan.duration);
      if (o <= 0) continue;
      const prev = byPlace[hl.place];
      if (!prev || (hl.role === "primary") || !prev.primary) {
        byPlace[hl.place] = { ...hl, opacity: o, primary: hl.role === "primary" };
      } else if (hl.role === "context" && !prev.primary) {
        byPlace[hl.place] = { ...hl, opacity: o, primary: false };
      }
    }
    // Prefer highest opacity primary if multiple
    for (const hl of plan.highlights) {
      const o = highlightOpacity(hl, t, plan.duration);
      if (o <= 0) continue;
      const cur = byPlace[hl.place];
      if (!cur || o >= cur.opacity) {
        byPlace[hl.place] = { ...hl, opacity: o, primary: hl.role === "primary" };
      }
    }

    for (const pid of placeIds) {
      const hl = byPlace[pid];
      if (!hl) {
        map.setPaintProperty(`fill_${pid}`, "fill-opacity", 0);
        map.setPaintProperty(`glow_${pid}`, "line-opacity", 0);
        map.setPaintProperty(`edge_${pid}`, "line-opacity", 0);
        continue;
      }
      const gradeOnCanvas = theme.fill?.mode === "terrain_color";
      const canvasBorders = theme.boundary?.renderer === "canvas";
      map.setPaintProperty(`fill_${pid}`, "fill-color", hl.color);
      map.setPaintProperty(`fill_${pid}`, "fill-opacity", gradeOnCanvas ? 0 : hl.opacity);
      const borderOn = hl.border !== false && (hl.role === "primary" || hl.border_strength === "country");
      map.setPaintProperty(`glow_${pid}`, "line-opacity", canvasBorders ? 0 : (borderOn ? 0.5 : 0));
      map.setPaintProperty(`edge_${pid}`, "line-opacity", canvasBorders ? 0 : (borderOn ? 0.95 : 0));
    }
  }

  return {
    project(lonlat) {
      const p = map.project(lonlat);
      return [p.x, p.y];
    },
    async draw(t) {
      const cam = sampleCamera(plan.camera.keyframes, t);
      paintFor(t, cam.zoom);
      await withTimeout(
        new Promise((resolve) => {
          let settled = false;
          const finish = () => {
            if (settled) return;
            settled = true;
            map.off("render", finish);
            resolve();
          };
          map.once("render", finish);
          map.jumpTo({
            center: cam.center,
            zoom: cam.zoom,
            pitch: cam.pitch,
            bearing: cam.bearing,
          });
          map.triggerRepaint();
          requestAnimationFrame(() => requestAnimationFrame(finish));
        }),
        8000,
        "MapLibre frame render",
      );
      await waitFrame();
    },
    destroy() {
      map.remove();
    },
  };
}
