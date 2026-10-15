import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import {
  bangladeshEmphasis,
  preloadImage,
  sampleCamera,
  waitFrame,
  withTimeout,
} from "../util.js";

function reliefCoordinates(story) {
  const c = story.terrain?.coordinates;
  if (Array.isArray(c) && c.length === 4) return c;
  const [west, south, east, north] = story.terrain.extent;
  // MapLibre image source: TL, TR, BR, BL in longitude/latitude.
  // JPEG content is Web Mercator; UV maps onto this geographic rectangle in mercator space.
  return [
    [west, north],
    [east, north],
    [east, south],
    [west, south],
  ];
}

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
    "MapLibre raster/geojson ready",
  );
}

export async function createMapLibre(container, story, data) {
  const start = story.camera.keyframes[0];
  const hl = story.highlights;
  const theme = story.theme;

  // Decode relief before Map construction so load/idle cannot race an unfinished fetch.
  await preloadImage(story.terrain.url);

  const map = new maplibregl.Map({
    container,
    interactive: false,
    attributionControl: false,
    fadeDuration: 0,
    canvasContextAttributes: { preserveDrawingBuffer: true, antialias: true },
    style: {
      version: 8,
      sources: {
        relief: {
          type: "image",
          url: story.terrain.url,
          coordinates: reliefCoordinates(story),
        },
        countries: {
          type: "geojson",
          data,
          promoteId: "ADMIN",
          attribution: "Natural Earth",
        },
      },
      layers: [
        {
          id: "sea",
          type: "background",
          paint: { "background-color": theme.ocean },
        },
        {
          id: "relief",
          type: "raster",
          source: "relief",
          paint: {
            "raster-fade-duration": 0,
            "raster-opacity": 1,
            "raster-saturation": -0.12,
            "raster-contrast": 0.18,
            "raster-brightness-min": 0.02,
            "raster-brightness-max": 0.92,
          },
        },
        {
          id: "land",
          type: "fill",
          source: "countries",
          paint: {
            "fill-color": theme.land,
            "fill-opacity": hl.land_opacity ?? 0.06,
          },
        },
        {
          id: "india-fill",
          type: "fill",
          source: "countries",
          filter: ["==", ["get", "ADMIN"], story.countries.india],
          paint: {
            "fill-color": theme.india,
            "fill-opacity": hl.india_opacity ?? 0.58,
          },
        },
        {
          id: "bangladesh-fill",
          type: "fill",
          source: "countries",
          filter: ["==", ["get", "ADMIN"], story.countries.bangladesh],
          paint: {
            "fill-color": theme.bangladesh,
            "fill-opacity": 0,
          },
        },
        {
          id: "borders",
          type: "line",
          source: "countries",
          paint: {
            "line-color": theme.border,
            "line-width": 0.65,
            "line-opacity": 0.35,
          },
        },
        {
          id: "highlight-glow",
          type: "line",
          source: "countries",
          filter: ["==", ["get", "ADMIN"], story.countries.india],
          paint: {
            "line-color": theme.border_glow,
            "line-width": 8,
            "line-blur": 5.5,
            "line-opacity": 0.55,
          },
        },
        {
          id: "highlight-edge",
          type: "line",
          source: "countries",
          filter: ["==", ["get", "ADMIN"], story.countries.india],
          paint: {
            "line-color": theme.border_selected,
            "line-width": 1.9,
            "line-opacity": 0.95,
          },
        },
        {
          id: "bangladesh-glow",
          type: "line",
          source: "countries",
          filter: ["==", ["get", "ADMIN"], story.countries.bangladesh],
          paint: {
            "line-color": theme.border_glow,
            "line-width": 8,
            "line-blur": 5.5,
            "line-opacity": 0,
          },
        },
        {
          id: "bangladesh-edge",
          type: "line",
          source: "countries",
          filter: ["==", ["get", "ADMIN"], story.countries.bangladesh],
          paint: {
            "line-color": theme.border_selected,
            "line-width": 1.9,
            "line-opacity": 0,
          },
        },
      ],
    },
    center: start.center,
    zoom: start.zoom,
    pitch: start.pitch ?? 0,
    bearing: start.bearing ?? 0,
  });

  await waitMapReady(map);

  function paintFor(t) {
    const bd = bangladeshEmphasis(story, t);
    const indiaOn = t < (hl.india_until ?? 10);
    map.setPaintProperty(
      "india-fill",
      "fill-opacity",
      indiaOn ? hl.india_opacity ?? 0.58 : 0,
    );
    map.setPaintProperty(
      "bangladesh-fill",
      "fill-opacity",
      (hl.bangladesh_opacity ?? 0.72) * bd,
    );
    map.setPaintProperty("bangladesh-glow", "line-opacity", 0.55 * bd);
    map.setPaintProperty("bangladesh-edge", "line-opacity", 0.95 * bd);
    map.setPaintProperty("highlight-glow", "line-opacity", indiaOn ? 0.55 : 0);
    map.setPaintProperty("highlight-edge", "line-opacity", indiaOn ? 0.95 : 0);
  }

  return {
    project(lonlat) {
      const p = map.project(lonlat);
      return [p.x, p.y];
    },
    async draw(t) {
      const cam = sampleCamera(story.camera.keyframes, t);
      paintFor(t);
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
          // If a render event was coalesced, settle on the next frames.
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
