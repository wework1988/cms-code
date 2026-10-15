#!/usr/bin/env python3
"""CMS worker integration tests for country-centered map openings."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT.parent / "story-pipeline-worker"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WORKER))

from map_story.compile import compile_resolved_plan  # noqa: E402
from map_story.geo import resolve_plan_places  # noqa: E402
from map_story.opening import (  # noqa: E402
    PRESENTATION_VERSION,
    normalize_semantic_opening,
    resolved_plan_needs_recompile,
)
from map_story.planner import golden_gorakhpur_plan  # noqa: E402


class EstablishViewOpeningTests(unittest.TestCase):
    def test_establish_view_compiles_to_country_camera(self):
        plan = golden_gorakhpur_plan(18)
        plan["style"] = "documentary_relief_bold"
        plan["shots"][0]["frame"] = "india"
        plan["shots"][0]["actions"] = [{"type": "establish_view", "place": "india"}]
        plan = normalize_semantic_opening(plan, language="hi", job_settings={})
        places = resolve_plan_places(plan)
        resolved = compile_resolved_plan(plan, places, job_settings={})
        k0 = resolved["camera"]["keyframes"][0]
        self.assertGreater(k0["zoom"], 3.0)
        self.assertEqual(resolved["presentation_version"], PRESENTATION_VERSION)
        self.assertEqual(resolved["composition"]["opening"]["policy"], "country_centered")

    def test_trusted_world_compile_allows_low_zoom(self):
        plan = golden_gorakhpur_plan(18)
        plan["style"] = "documentary_relief_bold"
        plan["shots"][0]["frame"] = "world"
        plan["shots"][0]["actions"] = [{"type": "establish_view", "scope": "world"}]
        plan = normalize_semantic_opening(
            plan,
            language="hi",
            job_settings={"opening_override": "world_overview"},
        )
        places = resolve_plan_places(plan)
        resolved = compile_resolved_plan(plan, places, job_settings={"opening_override": "world_overview"})
        k0 = resolved["camera"]["keyframes"][0]
        self.assertLess(k0["zoom"], 2.5)


class StaleResolvedPlanTests(unittest.TestCase):
    def test_world_scale_resolved_plan_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "resolved-plan.json"
            path.write_text(
                json.dumps(
                    {
                        "presentation_version": "old",
                        "camera": {"keyframes": [{"center": [40.0, 18.0], "zoom": 1.35, "t": 0}]},
                        "composition": {"opening": {"policy": "country_centered"}},
                    }
                ),
                encoding="utf-8",
            )
            self.assertTrue(resolved_plan_needs_recompile(path))

    def test_current_country_plan_is_not_stale(self):
        plan = golden_gorakhpur_plan(18)
        plan["style"] = "documentary_relief_bold"
        places = resolve_plan_places(plan)
        resolved = compile_resolved_plan(plan, places, job_settings={})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "resolved-plan.json"
            path.write_text(json.dumps(resolved), encoding="utf-8")
            self.assertFalse(resolved_plan_needs_recompile(path))


class WorkerReapplyTests(unittest.TestCase):
    def test_reapply_does_not_reuse_world_camera_from_old_semantic(self):
        import run_map_animations as worker  # noqa: E402

        plan = golden_gorakhpur_plan(18)
        plan["style"] = "documentary_relief_bold"
        plan["shots"][0]["frame"] = "world"
        plan["shots"][0]["actions"] = [{"type": "establish_view", "scope": "world"}]
        snapshot = {"language": "hi", "presentation_version": PRESENTATION_VERSION}
        selection = {
            "language": "hi",
            "target_focus_count": 5,
            "narration_unit_count": 2,
            "duration_seconds": 18,
        }
        reapplied = worker.reapply_semantic_presentation(plan, snapshot, selection, "documentary_relief_bold")
        self.assertEqual(reapplied["shots"][0]["frame"], "india")
        places = resolve_plan_places(reapplied)
        resolved = compile_resolved_plan(reapplied, places, job_settings=snapshot)
        self.assertGreater(resolved["camera"]["keyframes"][0]["zoom"], 3.0)


if __name__ == "__main__":
    unittest.main()
