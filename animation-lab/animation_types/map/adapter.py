"""Map adapter. Does not relocate the working map pipeline.

Dispatch for animation_type "map" (including snapshots that omit the field)
executes story-pipeline-worker/run_map_animations.py. Geography, MapLibre,
and OpenLayers stay there.
"""
from __future__ import annotations

TYPE_ID = "map"
REQUIRES_GEOGRAPHY = True
RENDERERS = ("maplibre", "openlayers")
WORKER = "run_map_animations.py"
