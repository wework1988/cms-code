"""Animation type registry. A type is selectable only after its renderer and sample MP4 exist."""
from __future__ import annotations

class UnsupportedAnimationType(ValueError):
    pass


# Operational modules. A type is listed here only after its sample MP4 verifies.
IMPLEMENTED = {
    "map": {
        "label": "Map",
        "requires_geography": True,
        "worker": "run_map_animations.py",
        "renderers": ("maplibre", "openlayers"),
    },
    "timeline": {
        "label": "Timeline",
        "requires_geography": False,
        "worker": "run_animations.py",
        "renderers": ("timeline",),
    },
    "text_highlighting": {
        "label": "Text highlighting",
        "requires_geography": False,
        "worker": "run_animations.py",
        "renderers": ("text_highlighting",),
    },
    "photo_sequences": {
        "label": "Photo sequence",
        "requires_geography": False,
        "worker": "run_animations.py",
        "renderers": ("photo_sequences",),
    },
    "before_after": {
        "label": "Before / after",
        "requires_geography": False,
        "worker": "run_animations.py",
        "renderers": ("before_after",),
    },
    "document_highlighting": {
        "label": "Document highlighting",
        "requires_geography": False,
        "worker": "run_animations.py",
        "renderers": ("document_highlighting",),
    },
    "relationship_diagrams": {
        "label": "Relationship diagram",
        "requires_geography": False,
        "worker": "run_animations.py",
        "renderers": ("relationship_diagrams",),
    },
    "data_animations": {
        "label": "Data animation",
        "requires_geography": False,
        "worker": "run_animations.py",
        "renderers": ("data_animations",),
    },
    "storyboard_reconstructions": {
        "label": "Storyboard reconstruction",
        "requires_geography": False,
        "worker": "run_animations.py",
        "renderers": ("storyboard_reconstructions",),
    },
}

FUTURE_TYPES = ()


def canonical_type(value: str | None) -> str:
    """Missing type is a legacy map snapshot."""
    kind = (value or "map").strip()
    if kind not in IMPLEMENTED:
        known = ", ".join(IMPLEMENTED)
        later = ", ".join(FUTURE_TYPES) or "none"
        raise UnsupportedAnimationType(
            f"Unsupported animation type {kind!r}. Implemented: {known}. "
            f"Not built yet: {later}."
        )
    return kind


def module_info(value: str | None) -> dict:
    kind = canonical_type(value)
    return {"id": kind, **IMPLEMENTED[kind]}
