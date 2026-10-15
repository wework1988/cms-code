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
  bangladeshEmphasis,
  preloadImage,
  sampleCamera,
  withTimeout,
} from "../util.js";

function mercatorExtent(story) {
  const [west, south, east, north] = story.terrain.extent;
  // ImageStatic expects EPSG:3857 metres for a Mercator-baked JPEG.
  return transformExtent([west, south, east, north], "EPSG:4326", "EPSG:3857");
}

function rgba(hex, alpha) {
  const h = hex.replace("#", "");
  const n = h.length === 3
    ? h.split("").map((c) => parseInt(c + c, 16))
    : [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
  return `rgba(${n[0]},${n[1]},${n[2]},${alpha})`;
}

export async function createOpenLayers(container, story, data) {
  let timestamp = 0;
  const theme = story.theme;
  const hl = story.highlights;

  await preloadImage(story.terrain.url);

  const styleFn = (feature) => {
    const name = feature.get("ADMIN");
    const bd = bangladeshEmphasis(story, timestamp);
    const indiaOn = timestamp < (hl.india_until ?? 10);

    let fill = rgba(theme.land, hl.land_opacity ?? 0.06);
    if (name === story.countries.india && indiaOn) {
      fill = rgba(theme.india, hl.india_opacity ?? 0.58);
    } else if (name === story.countries.bangladesh && bd > 0) {
      fill = rgba(theme.bangladesh, (hl.bangladesh_opacity ?? 0.72) * bd);
    }

    const styles = [
      new Style({
        fill: new Fill({ color: fill }),
        stroke: new Stroke({ color: rgba(theme.border, 0.35), width: 0.7 }),
      }),
    ];

    const selectedIndia = name === story.countries.india && indiaOn;
    const selectedBd = name === story.countries.bangladesh && bd > 0.05;
    if (selectedIndia || selectedBd) {
      const glowA = selectedBd ? 0.12 * bd : 0.12;
      const midA = selectedBd ? 0.28 * bd : 0.28;
      const edgeA = selectedBd ? 0.95 * bd : 0.95;
      styles.push(
        new Style({
          stroke: new Stroke({ color: rgba(theme.border_glow, glowA), width: 12 }),
        }),
        new Style({
          stroke: new Stroke({ color: rgba(theme.border_glow, midA), width: 6 }),
        }),
        new Style({
          stroke: new Stroke({ color: rgba(theme.border_selected, edgeA), width: 2.1 }),
        }),
      );
    }
    return styles;
  };

  const source = new VectorSource({
    features: new GeoJSON().readFeatures(data, {
      dataProjection: "EPSG:4326",
      featureProjection: "EPSG:3857",
    }),
  });

  const relief = new ImageLayer({
    source: new ImageStatic({
      url: story.terrain.url,
      projection: "EPSG:3857",
      imageExtent: mercatorExtent(story),
      interpolate: true,
    }),
  });

  const layer = new VectorLayer({
    source,
    style: styleFn,
    updateWhileAnimating: true,
    updateWhileInteracting: true,
  });

  container.style.background = theme.ocean_openlayers || theme.ocean;

  const start = story.camera.keyframes[0];
  const map = new Map({
    target: container,
    layers: [relief, layer],
    controls: [],
    interactions: [],
    pixelRatio: 1,
    view: new View({
      center: fromLonLat(start.center),
      zoom: start.zoom,
      rotation: 0,
      constrainResolution: false,
    }),
  });

  map.updateSize();

  await withTimeout(
    new Promise((resolve, reject) => {
      const src = relief.getSource();
      const onChange = () => {
        const state = src.getState();
        if (state === "ready") {
          src.un("change", onChange);
          resolve();
        } else if (state === "error") {
          src.un("change", onChange);
          reject(new Error("OpenLayers relief ImageStatic failed to load"));
        }
      };
      if (src.getState() === "ready") resolve();
      else {
        src.on("change", onChange);
        // Force evaluation after Image() preload.
        map.renderSync();
        setTimeout(onChange, 0);
      }
    }),
    30000,
    "OpenLayers relief ready",
  );

  map.renderSync();

  return {
    project(lonlat) {
      const px = map.getPixelFromCoordinate(fromLonLat(lonlat));
      if (!px) return null;
      return [px[0], px[1]];
    },
    async draw(t) {
      timestamp = t;
      const cam = sampleCamera(story.camera.keyframes, t);
      const view = map.getView();
      view.setCenter(fromLonLat(cam.center));
      // Slight zoom bias keeps the Mercator relief filling the 16:9 frame
      // (shared keyframes are tuned for MapLibre's raster coverage).
      const zoomBias = story.camera.openlayers_zoom_bias ?? 0.35;
      view.setZoom(cam.zoom + zoomBias);
      if (story.camera.openlayers_rotation) {
        // Bearing degrees → OpenLayers rotation (clockwise positive from north).
        view.setRotation((-cam.bearing * Math.PI) / 180);
      } else {
        view.setRotation(0);
      }
      layer.changed();
      map.renderSync();
    },
    destroy() {
      map.setTarget(null);
    },
  };
}
