import { createMapLibre } from "./src/engines/maplibre.js";
import { createOpenLayers } from "./src/engines/openlayers.js";
import { drawOverlays } from "./src/overlays.js";
import { drawMapGrade } from "./src/presentation.js";
import { documentaryPresentation, waitFrame } from "./src/util.js";

const params = new URLSearchParams(location.search);
const engine = (params.get("engine") || "maplibre").toLowerCase();
window.__mapDebugOverlay = params.get("debugOverlay") === "1";

window.sampleReady = false;
window.sampleError = null;

try {
  const plan = await fetch("/plan.json").then((r) => {
    if (!r.ok) throw new Error(`Failed to load plan.json (${r.status})`);
    return r.json();
  });

  const contextPath = plan.context_geojson || "/assets/maps/countries.geojson";
  const contextData = await fetch(contextPath).then((r) => {
    if (!r.ok) throw new Error(`Failed to load context GeoJSON (${r.status})`);
    return r.json();
  });

  const featureData = {};
  for (const [pid, feat] of Object.entries(plan.features || {})) {
    if (feat.feature) {
      featureData[pid] = feat.feature;
      continue;
    }
    const url = feat.geojson;
    if (!url) throw new Error(`Feature ${pid} has no geometry`);
    featureData[pid] = await fetch(url).then((r) => {
      if (!r.ok) throw new Error(`Failed to load ${url} (${r.status})`);
      return r.json();
    });
  }

  const mapEl = document.querySelector("#map");
  const hud = document.querySelector("#hud");
  const tint = document.querySelector("#tint");
  const hue = document.querySelector("#hue");
  const vignette = document.querySelector("#vignette");
  const glow = document.querySelector("#glow");
  for (const canvas of [hud, tint, hue, vignette, glow]) {
    canvas.width = plan.width;
    canvas.height = plan.height;
  }
  const ctx = hud.getContext("2d", { alpha: true });

  document.documentElement.style.width = `${plan.width}px`;
  document.documentElement.style.height = `${plan.height}px`;
  document.body.style.width = `${plan.width}px`;
  document.body.style.height = `${plan.height}px`;
  document.body.style.background = plan.theme?.ocean || "#0e1a2e";

  await document.fonts.load('40px "Story Devanagari"');
  await document.fonts.load('56px "Story Devanagari"');
  if (documentaryPresentation(plan.theme)) {
    await document.fonts.load('92px "Story Condensed"');
    await document.fonts.load('92px "Story Devanagari Bold"');
  }
  await document.fonts.ready;
  if (documentaryPresentation(plan.theme)) {
    if (!document.fonts.check('92px "Story Condensed"')) {
      throw new Error("Story Condensed failed to load before capture");
    }
    if (!document.fonts.check('92px "Story Devanagari Bold"')) {
      throw new Error("Story Devanagari Bold failed to load before capture");
    }
  }

  let backend;
  if (engine === "maplibre") {
    backend = await createMapLibre(mapEl, plan, featureData, contextData);
  } else if (engine === "openlayers") {
    backend = await createOpenLayers(mapEl, plan, featureData, contextData);
  } else {
    throw new Error(`Unsupported engine for map-story: ${engine}`);
  }

  window.__plan = plan;
  window.__engine = engine;

  window.renderSample = async (t) => {
    await backend.draw(t);
    const project = (lonlat) => backend.project(lonlat);
    drawMapGrade({ tint, hue, vignette, glow }, plan, featureData, project, t);
    drawOverlays(ctx, plan, engine, project, t);
    await waitFrame();
  };

  await window.renderSample(0);
  window.sampleReady = true;
  console.log(`[map-story] ready engine=${engine}`);
} catch (err) {
  window.sampleError = String(err?.stack || err);
  console.error("[map-story] init failed:", err);
  throw err;
}
