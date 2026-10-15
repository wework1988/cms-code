# World terrain background

- File: `world-relief.jpg` (+ `world-relief.json` extent)
- Source: Natural Earth II with shaded relief and water (public domain)
- Upstream: https://naciscdn.org/naturalearth/50m/raster/NE2_50M_SR_W.zip
- Documentation: https://www.naturalearthdata.com/downloads/50m-raster-data/50m-natural-earth-2/
- Cached master: `../relief-source.zip`
- Processing: equirectangular → Web Mercator resample, oceans graded toward dark navy
- Extent: full mercator-safe world (−180…180°, ±85.0511°)
- Limitation: suitable for a world establishing shot; not detailed satellite imagery
