# Map story renderer

Isolated headless renderer for compiled `map_focus_sequence` plans.

- Uses Playwright Chromium (not Chrome `:9222`)
- Local static server only; assets from `animation-lab/assets/`
- Engines: MapLibre (pitched cinematic) and OpenLayers (overhead)

Invoked by `../generate_map_video.py` — prefer that CLI.
