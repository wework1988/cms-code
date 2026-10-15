import { sampleCamera, waitFrame } from "../util.js";

function getCesium() {
  const C = window.Cesium;
  if (!C) throw new Error("Cesium global missing. Ensure /cesium/Cesium.js is loaded.");
  return C;
}

/**
 * Local ellipsoid imagery without Cesium ion.
 * GridImageryProvider is used because SingleTileImageryProvider produced zero
 * tiles in headless Chromium on this host; the grid also reads as a globe cue.
 */
function oceanBaseLayer(C, theme) {
  return new C.ImageryLayer(
    new C.GridImageryProvider({
      cells: 6,
      color: C.Color.fromCssColorString("#d7c39a").withAlpha(0.18),
      glowColor: C.Color.fromCssColorString("#f0e2c0").withAlpha(0.05),
      glowWidth: 1,
      backgroundColor: C.Color.fromCssColorString(theme.cesium_globe),
    }),
  );
}

export async function createCesium(container, story, data) {
  const C = getCesium();
  C.Ion.defaultAccessToken = "";

  container.style.width = `${story.width}px`;
  container.style.height = `${story.height}px`;

  const viewer = new C.Viewer(container, {
    baseLayer: oceanBaseLayer(C, story.theme),
    terrainProvider: new C.EllipsoidTerrainProvider(),
    animation: false,
    timeline: false,
    baseLayerPicker: false,
    geocoder: false,
    homeButton: false,
    sceneModePicker: false,
    navigationHelpButton: false,
    fullscreenButton: false,
    selectionIndicator: false,
    infoBox: false,
    skyBox: false,
    skyAtmosphere: false,
    creditContainer: document.createElement("div"),
    contextOptions: {
      webgl: {
        preserveDrawingBuffer: true,
        antialias: true,
      },
    },
    requestRenderMode: true,
    maximumRenderTimeChange: Number.POSITIVE_INFINITY,
  });

  viewer.scene.logarithmicDepthBuffer = false;
  viewer.scene.highDynamicRange = false;
  viewer.scene.globe.baseColor = C.Color.fromCssColorString(story.theme.cesium_globe);
  viewer.scene.backgroundColor = C.Color.fromCssColorString(story.theme.cesium_sky);
  viewer.scene.globe.enableLighting = false;
  viewer.scene.fog.enabled = false;
  viewer.scene.globe.showGroundAtmosphere = true;
  try {
    viewer.scene.skyAtmosphere = new C.SkyAtmosphere();
    viewer.scene.skyAtmosphere.show = true;
  } catch {
    /* optional */
  }
  viewer.resolutionScale = 1;
  viewer.useDefaultRenderLoop = false;
  viewer.resize();

  const countries = await C.GeoJsonDataSource.load(data, {
    fill: C.Color.fromCssColorString(story.theme.land).withAlpha(0.92),
    stroke: C.Color.fromCssColorString(story.theme.border),
    strokeWidth: 2,
    clampToGround: false,
  });
  await viewer.dataSources.add(countries);

  for (const entity of countries.entities.values) {
    if (!entity.polygon) continue;
    entity.polygon.outline = true;
    entity.polygon.outlineColor = C.Color.fromCssColorString(story.theme.border);
    // Slight thickness so fills sit above the grid imagery.
    entity.polygon.height = 0;
    entity.polygon.extrudedHeight = 12000;
  }

  function colorFor(name, t) {
    let css = story.theme.land;
    if (name === story.countries.india && t < story.highlights.india_until) {
      css = story.theme.india;
    } else if (name === story.countries.bangladesh && t >= story.highlights.bangladesh_from) {
      css = story.theme.bangladesh;
    }
    return new C.ColorMaterialProperty(C.Color.fromCssColorString(css));
  }

  function project(lonlat) {
    const cartesian = C.Cartesian3.fromDegrees(lonlat[0], lonlat[1], 0);
    let win = null;
    if (C.SceneTransforms?.worldToWindowCoordinates) {
      win = C.SceneTransforms.worldToWindowCoordinates(viewer.scene, cartesian);
    } else if (C.SceneTransforms?.wgs84ToWindowCoordinates) {
      win = C.SceneTransforms.wgs84ToWindowCoordinates(viewer.scene, cartesian);
    }
    if (!win || Number.isNaN(win.x) || Number.isNaN(win.y)) return null;
    return [win.x, win.y];
  }

  async function settle(frames = 30) {
    for (let i = 0; i < frames; i += 1) {
      viewer.resize();
      viewer.render();
      await waitFrame();
    }
  }

  // Apply initial highlight colours before the first captured frame.
  {
    const time = C.JulianDate.now();
    for (const entity of countries.entities.values) {
      const name = entity.properties?.ADMIN?.getValue?.(time) ?? entity.name;
      if (entity.polygon) entity.polygon.material = colorFor(name, 0);
    }
  }

  const start = sampleCamera(story.camera.keyframes, 0);
  viewer.camera.setView({
    destination: C.Cartesian3.fromDegrees(start.center[0], start.center[1], start.altitude_m),
    orientation: {
      heading: C.Math.toRadians(start.heading_deg),
      pitch: C.Math.toRadians(start.pitch_deg),
      roll: 0,
    },
  });
  await settle(60);

  return {
    project,
    async draw(t) {
      const cam = sampleCamera(story.camera.keyframes, t);
      const time = C.JulianDate.now();
      for (const entity of countries.entities.values) {
        const name = entity.properties?.ADMIN?.getValue?.(time) ?? entity.name;
        if (entity.polygon) entity.polygon.material = colorFor(name, t);
      }
      viewer.camera.setView({
        destination: C.Cartesian3.fromDegrees(cam.center[0], cam.center[1], cam.altitude_m),
        orientation: {
          heading: C.Math.toRadians(cam.heading_deg),
          pitch: C.Math.toRadians(cam.pitch_deg),
          roll: 0,
        },
      });
      viewer.resize();
      viewer.render();
      await waitFrame();
      viewer.render();
    },
    destroy() {
      viewer.destroy();
    },
  };
}
