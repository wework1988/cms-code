# India administrative boundaries (animation-lab cache)

## Country — India

- File: `india.geojson`
- Source: Natural Earth 1:50m admin-0 countries (public domain)
- Upstream: https://www.naturalearthdata.com/downloads/50m-cultural-vectors/50m-admin-0-countries-2/
- Extracted from `../countries.geojson` (ADMIN = India)
- Date cached: 2026-10-11

## State — Uttar Pradesh (ADM1)

- File: `uttar-pradesh.geojson`
- Dataset: geoBoundaries IND ADM1 simplified
- Boundary year represented: 2011
- Licence: Creative Commons Attribution 2.5 India (CC BY 2.5 IN)
- Source community: DataMeet India / Election Commission of India (via geoBoundaries)
- API: https://www.geoboundaries.org/api/current/gbOpen/IND/ADM1/
- Download used: https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/IND/ADM1/geoBoundaries-IND-ADM1_simplified.geojson
- Full cached copy: `geoboundaries-IND-ADM1-simp.geojson`
- Feature match: shapeName = "Uttar Pradesh"

## District — Gorakhpur (ADM2)

- File: `gorakhpur-district.geojson`
- Dataset: geoBoundaries IND ADM2 simplified
- Boundary year represented: 2021
- Licence: Open Data Commons Open Database License 1.0 (ODbL)
- Source: Pathways Data Pvt. Ltd. / lgdirectory.gov.in (via geoBoundaries)
- API: https://www.geoboundaries.org/api/current/gbOpen/IND/ADM2/
- Download used: https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/IND/ADM2/geoBoundaries-IND-ADM2_simplified.geojson
- Full cached copy: `geoboundaries-IND-ADM2-simp.geojson`
- Feature match: shapeName = "Gorakhpur", shapeType = ADM2
- Note: This is the **district** polygon, not a city point.

## Terrain — India regional relief

- File: `india-relief.jpg` (+ `india-relief.json` extent)
- Source: Natural Earth II with shaded relief and water (public domain)
- Upstream zip: https://naciscdn.org/naturalearth/50m/raster/NE2_50M_SR_W.zip
- Cached master: `../relief-source.zip`
- Extent (approx): 68°E–98°E, 5°N–37°N, Web Mercator resampled
- Limitation: NE2 50m shaded relief is cartographic terrain colouring, **not**
  high-resolution satellite imagery. District-scale texture remains coarse.

Boundaries are cartographic products and may differ slightly across datasets;
the resolver allows a small parent/child overlap tolerance for that reason.
