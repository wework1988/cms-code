# Map engine comparison (MapLibre / OpenLayers / Cesium)

Shared 10-second documentary map sample rendered three ways from one JSON story.

## Commands

```bash
cd /Users/alokkumarverma/project/cms-code/animation-lab/map-comparison
npm install
npx playwright install chromium
# MapLibre + OpenLayers documentary samples (recommended):
npm run render -- --engine documentary
# Or all three (includes Cesium):
npm run render -- --engine all
```

Single engine:

```bash
npm run render -- --engine maplibre
npm run render -- --engine openlayers
npm run render -- --engine cesium
```

Browser preview (isolated local server, not Chrome :9222):

```bash
npm run preview
# open http://127.0.0.1:4173/?engine=maplibre
```

## Outputs

- `../output/map-comparison/maplibre.mp4`
- `../output/map-comparison/openlayers.mp4`
- `../output/map-comparison/cesium.mp4`
- PNG previews, contact sheet, `manifest.json`

## Edit the story

`story.json` — camera keyframes, captions, aircraft route, impacts, theme colours.
Coordinates are `[longitude, latitude]`.


MapLibre and OpenLayers now use local Natural Earth II relief, translucent crimson India, yellow-green Bangladesh, layered ivory outlines and larger Hindi country labels. Edit `story.json` theme and camera settings to restyle. The relief stays visible through the highlights. Cesium retains its previous vector globe treatment.

Recreate the regional relief asset from `../assets/maps/relief-source.zip` with `../.venv/bin/python prepare_relief.py`. Rendering needs no remote tiles or API key.
