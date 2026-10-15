Country geometry: Natural Earth 1:50m admin-0 countries (public domain).
Downloaded 2026-10-11 from the Natural Earth vector repository:
https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson
Dataset information: https://www.naturalearthdata.com/downloads/50m-cultural-vectors/50m-admin-0-countries-2/

Natural Earth depicts de facto boundaries; these are generalized cartographic outlines,
not a declaration about disputed territory.

Files in this folder:
- `countries.geojson` — full Natural Earth 1:50m admin-0 extract
- `south-asia.geojson` — regional subset (features intersecting roughly 40–120° E, 10° S–55° N)
  used by `map-comparison/` for faster local renders. Feature `id` is set to ADMIN for MapLibre.

The parchment Python renderer (`map_video.py`) uses a fixed regional equirectangular
projection at reference latitude 23° N. Country label anchors and callout positions are
editorial layout settings, not capital/city locations.

City-level streets are not present in these polygons. For street detail, add an optional
local tileset or OpenMapTiles extract under `animation-lab/assets/` rather than inventing
geometry from country outlines.

Fonts used by map-comparison (cached under `map-comparison/assets/fonts/`):
- Devanagari Sangam MN (system copy for Hindi UI)
- Arial (system copy for Latin labels)


Terrain styling: Natural Earth II with shaded relief and water (public domain).
Source: https://naciscdn.org/naturalearth/50m/raster/NE2_50M_SR_W.zip
Documentation: https://www.naturalearthdata.com/downloads/50m-raster-data/50m-natural-earth-2/
The regional JPEG is resampled into Web Mercator by map-comparison/prepare_relief.py,
then lightly colour-graded (ocean blues darkened toward navy) for documentary contrast.
This is shaded relief, not live satellite imagery or 3D elevation.
Geographic bounds of the regional asset: west 45°, south 0°, east 115°, north 50°.

Additional storytelling assets (see subfolders):
- `world/world-relief.jpg` — full mercator-safe NE2 world background
- `india/` — India country extract, Uttar Pradesh (geoBoundaries ADM1),
  Gorakhpur district (geoBoundaries ADM2), and India regional relief
  Licences and URLs: `india/SOURCE.md`, `world/SOURCE.md`

