"""Errors shared by cinematic overlays and documentary typography."""
from __future__ import annotations


class GraphicsPlanError(ValueError):
    pass


class UnsupportedCapability(GraphicsPlanError):
    """The plan asked for a placement or tracking mode this build does not perform."""
