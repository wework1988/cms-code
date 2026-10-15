"""Versioned fields shared by every animation job. Type plans stay in their own payload."""
from __future__ import annotations

CONTRACT_VERSION = "1.0"

# Stored on the job snapshot and copied onto progress. Old map snapshots omit
# animation_type and remain map jobs.
SNAPSHOT_FIELDS = (
    "job_id",
    "animation_type",
    "script",
    "script_hash",
    "prompt_id",
    "master_prompt",
    "language",
    "duration_seconds",
    "max_clips",
    "planner",
)

CLIP_FIELDS = (
    "animation_type",
    "clip_id",
    "source_passage",
    "offset_start",
    "offset_end",
    "title",
    "reason",
    "language",
    "duration_seconds",
    "semantic_plan",
    "compiled_plan",
    "status",
    "error",
    "video",
    "poster",
    "representative_frames",
    "verification",
    "prompt_id",
    "model",
)
