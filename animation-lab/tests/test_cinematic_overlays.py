"""Overlay plan checks. The sample MP4 is rendered separately."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB))

from cinematic_overlays.motion import anchor_at, phase  # noqa: E402
from cinematic_overlays.schema import OverlayPlanError, validate_plan  # noqa: E402

PLAN = {
    "input": "general/152-priso-story-updated/video/scene_1.mp4",
    "automatic_tracking": False,
    "overlays": [{
        "id": "building_callout",
        "type": "location_callout",
        "text": "द्वीप पर स्थित जेल",
        "start_time": 0.7,
        "reveal_duration": 0.5,
        "label_fade_duration": 0.35,
        "hold_duration": 2.0,
        "exit_duration": 0.45,
        "anchor_mode": "manual_keyframes",
        "limitation": "Hand-placed keyframes, not a tracker.",
        "label": {"x": 0.055, "y": 0.16},
        "anchor_keyframes": [
            {"t": 0.0, "x": 0.60, "y": 0.30},
            {"t": 2.0, "x": 0.64, "y": 0.34},
        ],
    }],
}


class OverlayPlanTests(unittest.TestCase):
    def test_manual_keyframes_interpolate_and_do_not_claim_tracking(self):
        plan = validate_plan(PLAN, duration=5.06)
        overlay = plan["overlays"][0]
        self.assertEqual(anchor_at(overlay, 0)["x"], 0.60)
        self.assertEqual(anchor_at(overlay, 2)["x"], 0.64)
        middle = anchor_at(overlay, 1)
        self.assertGreater(middle["x"], 0.60)
        self.assertLess(middle["x"], 0.64)
        self.assertFalse(phase(overlay, 0.2)["active"])
        self.assertEqual(phase(overlay, 0.7 + 0.5 + 0.35 + 1)["label"], 1.0)

    def test_a_planner_cannot_invent_coordinates(self):
        broken = {
            **PLAN,
            "overlays": [{**PLAN["overlays"][0], "coordinate_source": "deepseek"}],
        }
        with self.assertRaises(OverlayPlanError):
            validate_plan(broken, duration=5.06)

    def test_automatic_tracking_is_rejected(self):
        broken = {**PLAN, "automatic_tracking": True}
        with self.assertRaises(OverlayPlanError):
            validate_plan(broken, duration=5.06)

    def test_fixed_anchor_on_a_moving_camera_must_be_acknowledged(self):
        broken = {
            **PLAN,
            "overlays": [{
                **PLAN["overlays"][0],
                "anchor_mode": "fixed",
                "camera_motion": "moves",
                "anchor": {"x": 0.6, "y": 0.3},
            }],
        }
        with self.assertRaises(OverlayPlanError):
            validate_plan(broken, duration=5.06)

    def test_overlay_cannot_run_past_the_source(self):
        with self.assertRaises(OverlayPlanError):
            validate_plan(PLAN, duration=1.0)

    def test_route_needs_supplied_points(self):
        broken = {
            "overlays": [{
                "type": "route_line",
                "start_time": 0,
                "reveal_duration": 0.5,
                "hold_duration": 1,
                "exit_duration": 0.4,
                "anchor_mode": "fixed",
                "anchor": {"x": 0.2, "y": 0.2},
                "points": [{"x": 0.2, "y": 0.2}],
            }],
        }
        with self.assertRaises(OverlayPlanError):
            validate_plan(broken, duration=5)


if __name__ == "__main__":
    unittest.main()
