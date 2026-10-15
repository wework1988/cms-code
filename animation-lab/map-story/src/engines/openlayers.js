import ImageLayer from "ol/layer/Image.js";
import ImageStatic from "ol/source/ImageStatic.js";
import { transformExtent } from "ol/proj.js";
import Map from "ol/Map.js";
import View from "ol/View.js";
import VectorLayer from "ol/layer/Vector.js";
import VectorSource from "ol/source/Vector.js";
import GeoJSON from "ol/format/GeoJSON.js";
import { fromLonLat } from "ol/proj.js";
import { Style, Fill, Stroke } from "ol/style.js";
import "ol/ol.css";
import {
  highlightOpacity,
  preloadImage,
  sampleCamera,
  withTimeout,
} from "../util.js";

function rgba(hex, alpha) {
  const h = hex.replace("#", "");
  const n = h.length === 3
    ? h.split("").map((c) => parseInt(c + c, 16))
    : [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
  return `rgba(${n[0]},${n[1]},${n[2]},${alpha})`;
}

function mercatorExtent(extent) {
  return transformExtent(extent, "EPSG:4326", "EPSG:3857");
}

export async function createOpenLayers(container, plan, featureData, contextData) {
  let timestamp = 0;
  let zoomLevel = plan.camera.keyframes[0].zoom;
  const theme = plan.theme;
  const layersMeta = plan.terrain.layers || [];
  const world = layersMeta.find((l) => l.id === "world") || plan.terrain;
  const regional = layersMeta.find((l) => l.id === "regional");
  const bias = plan.camera.openlayers_zoom_bias ?? 0.35;

  const flat = theme.capabilities?.basemap_mode === "flat_atlas";
  if (!flat) {
    await preloadImage(world.url);
    if (regional) await preloadImage(regional.url);
  }

  const worldLayer = flat ? null : new ImageLayer({
    source: new ImageStatic({
      url: world.url,
      projection: "EPSG:3857",
      imageExtent: mercatorExtent(world.extent),
      interpolate: true,
    }),
    opacity: 1,
  });
  const regionalLayer = !flat && regional
    ? new ImageLayer({
      source: new ImageStatic({
        url: regional.url,
        projection: "EPSG:3857",
        imageExtent: mercatorExtent(regional.extent),
        interpolate: true,
      }),
      opacity: 0,
    })
    : null;

  const contextSource = new VectorSource({
    features: new GeoJSON().readFeatures(contextData, {
      dataProjection: "EPSG:4326",
      featureProjection: "EPSG:3857",
    }),
  });
  const contextLayer = new VectorLayer({
    source: contextSource,
    style: new Style({
      fill: new Fill({ color: rgba(theme.land, flat ? (theme.land_opacity ?? 1) : (theme.land_opacity ?? 0.04)) }),
      stroke: new Stroke({ color: rgba(theme.border, flat ? 0.9 : 0.28), width: flat ? 1.1 : 0.6 }),
    }),
  });

  const placeLayers = {};
  for (const pid of Object.keys(plan.features)) {
    if (plan.features[pid].representation === "point") continue;
    const source = new VectorSource({
      features: new GeoJSON().readFeatures(featureData[pid], {
        dataProjection: "EPSG:4326",
        featureProjection: "EPSG:3857",
      }),
    });
    placeLayers[pid] = new VectorLayer({
      source,
      style: () => {
        const active = [];
        for (const hl of plan.highlights) {
          if (hl.place !== pid) continue;
          const o = highlightOpacity(hl, timestamp, plan.duration);
          if (o > 0) active.push({ ...hl, opacity: o });
        }
        if (!active.length) {
          return new Style({ fill: new Fill({ color: "rgba(0,0,0,0)" }), stroke: new Stroke({ color: "rgba(0,0,0,0)", width: 0 }) });
        }
        active.sort((a, b) => a.opacity - b.opacity);
        const hl = active[active.length - 1];
        const gradeOnCanvas = theme.fill?.mode === "terrain_color";
        const canvasBorders = theme.boundary?.renderer === "canvas";
        const styles = [
          new Style({
            fill: new Fill({ color: rgba(hl.color, gradeOnCanvas ? 0 : hl.opacity) }),
          }),
        ];
        if (!canvasBorders && hl.border !== false && (hl.role === "primary" || hl.border_strength === "country")) {
          styles.push(
            new Style({ stroke: new Stroke({ color: rgba(theme.border_glow, 0.14), width: 11 }) }),
            new Style({ stroke: new Stroke({ color: rgba(theme.border_glow, 0.3), width: 5.5 }) }),
            new Style({ stroke: new Stroke({ color: rgba(theme.border_selected, 0.95), width: 2.1 }) }),
          );
        }
        return styles;
      },
      updateWhileAnimating: true,
    });
  }

  container.style.background = theme.ocean_openlayers || theme.ocean;
  const start = plan.camera.keyframes[0];
  const map = new Map({
    target: container,
    layers: [
      ...(worldLayer ? [worldLayer] : []),
      ...(regionalLayer ? [regionalLayer] : []),
      contextLayer,
      ...Object.values(placeLayers),
    ],
    controls: [],
    interactions: [],
    pixelRatio: 1,
    view: new View({
      center: fromLonLat(start.center),
      zoom: start.zoom + bias,
      rotation: 0,
      constrainResolution: false,
    }),
  });
  map.updateSize();

  await withTimeout(
    new Promise((resolve) => {
      map.once("rendercomplete", resolve);
      map.renderSync();
    }),
    30000,
    "OpenLayers first render",
  );

  return {
    project(lonlat) {
      const px = map.getPixelFromCoordinate(fromLonLat(lonlat));
      return px ? [px[0], px[1]] : null;
    },
    async draw(t) {
      timestamp = t;
      const cam = sampleCamera(plan.camera.keyframes, t);
      zoomLevel = cam.zoom;
      if (regionalLayer) {
        const from = regional.visible_from_zoom ?? 2.6;
        const until = world.visible_until_zoom ?? 3.4;
        const u = Math.max(0, Math.min(1, (zoomLevel - from) / Math.max(0.01, until - from)));
        worldLayer.setOpacity(1);
        regionalLayer.setOpacity(u);
      }
      map.getView().setCenter(fromLonLat(cam.center));
      map.getView().setZoom(cam.zoom + bias);
      for (const layer of Object.values(placeLayers)) layer.changed();
      await withTimeout(
        new Promise((resolve) => {
          map.once("rendercomplete", resolve);
          map.renderSync();
        }),
        8000,
        "OpenLayers frame render",
      );
    },
    destroy() {
      map.setTarget(null);
    },
  };
}
