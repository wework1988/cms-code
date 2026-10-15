import { createMapLibre } from "./src/engines/maplibre.js";
import { createOpenLayers } from "./src/engines/openlayers.js";
import { drawOverlays } from "./src/overlays.js";
import { waitFrame } from "./src/util.js";

const params = new URLSearchParams(location.search);
const engine = (params.get("engine") || "maplibre").toLowerCase();

window.sampleReady = false;
window.sampleError = null;

async function loadCesiumScript() {
  if (window.Cesium) return;
  await new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "/cesium/Cesium.js";
    s.async = true;
    s.onload = resolve;
    s.onerror = () => reject(new Error("Failed to load /cesium/Cesium.js"));
    document.head.appendChild(s);
  });
}

try {
  const story = await fetch("/story.json").then((r) => {
    if (!r.ok) throw new Error(`Failed to load story.json (${r.status})`);
    return r.json();
  });

  const geoPath = story.geojson || "/assets/maps/south-asia.geojson";
  const data = await fetch(geoPath).then((r) => {
    if (!r.ok) throw new Error(`Failed to load GeoJSON ${geoPath} (${r.status})`);
    return r.json();
  });

  const mapEl = document.querySelector("#map");
  const hud = document.querySelector("#hud");
  hud.width = story.width;
  hud.height = story.height;
  const ctx = hud.getContext("2d", { alpha: true });

  document.documentElement.style.width = `${story.width}px`;
  document.documentElement.style.height = `${story.height}px`;
  document.body.style.width = `${story.width}px`;
  document.body.style.height = `${story.height}px`;

  await document.fonts.load('22px "Story Devanagari"');
  await document.fonts.load('34px "Story Devanagari"');
  await document.fonts.load('62px "Story Devanagari"');
  await document.fonts.load('15px "Story Latin"');
  await document.fonts.ready;

  let backend;
  if (engine === "maplibre") {
    backend = await createMapLibre(mapEl, story, data);
  } else if (engine === "openlayers") {
    backend = await createOpenLayers(mapEl, story, data);
  } else if (engine === "cesium") {
    await loadCesiumScript();
    const { createCesium } = await import("./src/engines/cesium.js");
    backend = await createCesium(mapEl, story, data);
  } else {
    throw new Error(`Unknown engine: ${engine}`);
  }

  window.__story = story;
  window.__engine = engine;

  window.renderSample = async (t) => {
    await backend.draw(t);
    drawOverlays(ctx, story, engine, (lonlat) => backend.project(lonlat), t);
    await waitFrame();
  };

  await window.renderSample(0);
  window.sampleReady = true;
  console.log(`[map-comparison] ready engine=${engine}`);
} catch (err) {
  window.sampleError = String(err?.stack || err);
  console.error("[map-comparison] init failed:", err);
  throw err;
}
