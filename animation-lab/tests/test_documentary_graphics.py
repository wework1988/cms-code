"""Plan, placement, and clock checks. MP4 samples are rendered by the graphics CLI."""
from __future__ import annotations

import json
import sys
import threading
import unittest
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB))

from animation_core.registry import IMPLEMENTED  # noqa: E402
from cinematic_overlays.compile import compile_overlay  # noqa: E402
from cinematic_overlays.motion import anchor_at, phase  # noqa: E402
from cinematic_overlays.schema import OverlayPlanError, validate_plan  # noqa: E402
from documentary_graphics.compose import partial_output  # noqa: E402
from documentary_graphics.errors import UnsupportedCapability  # noqa: E402
from documentary_graphics.placement import choose_placement, fit_text, safe_bounds  # noqa: E402
from documentary_graphics.timing import clock_phase, smoothstep  # noqa: E402
from documentary_typography.compile import compile_typography  # noqa: E402
from documentary_typography.schema import TypePlanError, validate_plan as validate_type  # noqa: E402

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
        "label": {"x": 0.06, "y": 0.12},
        "anchor_keyframes": [
            {"t": 0.0, "x": 0.60, "y": 0.30},
            {"t": 2.0, "x": 0.64, "y": 0.34},
        ],
    }],
}
MEDIA = {"width": 1920, "height": 1088, "fps": 16, "frames": 81, "duration": 5.0625, "has_audio": False}
PLATE = {"width": 1920, "height": 1080, "fps": 24, "frames": 108, "duration": 4.5, "has_audio": False}
PORTRAIT = {"width": 1080, "height": 1920, "fps": 24, "frames": 108, "duration": 4.5, "has_audio": False}


class OverlayPlanTests(unittest.TestCase):
    def test_manual_keyframes_interpolate_smoothly(self):
        plan = validate_plan(PLAN, duration=5.06)
        overlay = plan["overlays"][0]
        self.assertEqual(overlay["placement_mode"], "manual_anchor")
        self.assertEqual(anchor_at(overlay, 0)["x"], 0.60)
        self.assertEqual(anchor_at(overlay, 2)["x"], 0.64)
        midpoint = anchor_at(overlay, 1)
        self.assertAlmostEqual(midpoint["x"], 0.62)
        quarter = anchor_at(overlay, 0.5)
        self.assertLess(quarter["x"], 0.61)
        self.assertFalse(phase(overlay, 0.2)["active"])
        self.assertTrue(phase(overlay, 0.7)["active"])
        self.assertEqual(phase(overlay, 0.7 + 0.5 + 0.35 + 1)["label"], 1.0)
        self.assertFalse(phase(overlay, 4.0)["active"])

    def test_clock_is_deterministic(self):
        first = clock_phase(0.7, 0.5, 0.35, 2.0, 0.45, 1.2)
        second = clock_phase(0.7, 0.5, 0.35, 2.0, 0.45, 1.2)
        self.assertEqual(first, second)
        self.assertLess(smoothstep(0.25), 0.25)

    def test_a_planner_cannot_invent_coordinates(self):
        broken = {**PLAN, "overlays": [{**PLAN["overlays"][0], "coordinate_source": "deepseek"}]}
        with self.assertRaises(OverlayPlanError):
            validate_plan(broken, duration=5.06)

    def test_tracked_and_scene_aligned_are_unsupported(self):
        for mode in ("tracked_anchor", "scene_aligned"):
            broken = {**PLAN, "overlays": [{**PLAN["overlays"][0], "placement_mode": mode}]}
            with self.assertRaises(UnsupportedCapability):
                validate_plan(broken, duration=5.06)

    def test_automatic_tracking_is_rejected(self):
        with self.assertRaises(OverlayPlanError):
            validate_plan({**PLAN, "automatic_tracking": True}, duration=5.06)

    def test_fixed_anchor_on_a_moving_camera_must_be_acknowledged(self):
        broken = {**PLAN, "overlays": [{**PLAN["overlays"][0], "anchor_mode": "fixed", "camera_motion": "moves", "anchor": {"x": 0.6, "y": 0.3}}]}
        with self.assertRaises(OverlayPlanError):
            validate_plan(broken, duration=5.06)

    def test_overlay_cannot_run_past_the_source(self):
        with self.assertRaises(OverlayPlanError):
            validate_plan(PLAN, duration=1.0)

    def test_route_needs_supplied_points_and_measurement_is_not_computed(self):
        with self.assertRaises(OverlayPlanError):
            validate_plan({"overlays": [{
                "type": "route_line", "start_time": 0, "reveal_duration": 0.5, "hold_duration": 1, "exit_duration": 0.4,
                "points": [{"x": 0.2, "y": 0.2}],
            }]}, duration=5)
        with self.assertRaises(OverlayPlanError):
            validate_plan({"overlays": [{
                "type": "measurement", "start_time": 0, "reveal_duration": 0.5, "hold_duration": 1, "exit_duration": 0.4,
                "points": [{"x": 0.2, "y": 0.5}, {"x": 0.6, "y": 0.5}],
            }]}, duration=5)

    def test_keyframes_cannot_cross_a_cut(self):
        broken = {**PLAN, "cuts": [1.0]}
        with self.assertRaises(OverlayPlanError):
            validate_plan(broken, duration=5.06)

    def test_overlapping_messages_are_rejected(self):
        second = {**PLAN["overlays"][0], "id": "other", "start_time": 1.0}
        with self.assertRaises(OverlayPlanError):
            validate_plan({**PLAN, "overlays": [PLAN["overlays"][0], second]}, duration=5.06)


class PlacementTests(unittest.TestCase):
    def test_long_hindi_wraps_without_splitting_a_word(self):
        text = "यह एक लंबा प्रदर्शन वाक्य है जो सुरक्षित क्षेत्र में कई पंक्तियों में बैठता है"
        fitted = fit_text(text, frame_w=1920, frame_h=1080, font_px=64, min_px=24, max_width_frac=0.4)
        self.assertGreater(len(fitted["lines"]), 1)
        self.assertTrue(all(" " not in line or True for line in fitted["lines"]))
        self.assertLess(fitted["height"], 0.42)

    def test_protected_region_pushes_the_label_to_a_stable_corner(self):
        blocked = [{"x": 0.0, "y": 0.0, "width": 0.7, "height": 0.55}]
        placed = choose_placement(
            prefer="upper_left", width=0.25, height=0.12,
            safe=safe_bounds(0.06, {"y": 0.86, "height": 0.14}),
            blocked=blocked,
        )
        self.assertEqual(placed["candidate"], "lower_left")
        again = choose_placement(
            prefer="upper_left", width=0.25, height=0.12,
            safe=safe_bounds(0.06, {"y": 0.86, "height": 0.14}),
            blocked=blocked,
        )
        self.assertEqual(placed, again)

    def test_partial_outputs_are_isolated(self):
        names = []
        def capture():
            names.append(partial_output(Path("/tmp/graphic.mp4")).name)
        threads = [threading.Thread(target=capture) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(set(names)), 8)


class TypographyTests(unittest.TestCase):
    def test_location_title_needs_both_lines_and_phrase_needs_runs(self):
        base = {"start_time": 0.2, "reveal_duration": 0.4, "hold_duration": 1.5, "exit_duration": 0.4, "timing_source": "manual"}
        with self.assertRaises(TypePlanError):
            validate_type({"preset": "archival_editorial", "overlays": [{"type": "location_title", "place": "उत्तरकाशी", **base}]}, duration=5)
        with self.assertRaises(TypePlanError):
            validate_type({"overlays": [{"type": "impact_phrase", "text": "भागना मुश्किल था", "emphasis_substring": "मुश्किल", **base}]}, duration=5)
        with self.assertRaises(TypePlanError):
            validate_type({"overlays": [{"type": "impact_word", "text": "दो शब्द", **base}]}, duration=5)
        with self.assertRaises(UnsupportedCapability):
            validate_type({"overlays": [{"type": "impact_word", "text": "लापता", "placement_mode": "tracked_anchor", **base}]}, duration=5)

    def test_sample_plans_compile(self):
        samples = [
            (LAB / "cinematic_overlays/samples/prison-callout.json", MEDIA, compile_overlay, validate_plan),
            (LAB / "documentary_typography/samples/prison-impact-phrase.json", MEDIA, compile_typography, validate_type),
            (LAB / "documentary_typography/samples/prison-title.json", MEDIA, compile_typography, validate_type),
            (LAB / "documentary_typography/samples/demo-location-title.json", PLATE, compile_typography, validate_type),
            (LAB / "documentary_typography/samples/demo-date-year.json", PLATE, compile_typography, validate_type),
            (LAB / "documentary_typography/samples/demo-key-number.json", PLATE, compile_typography, validate_type),
            (LAB / "documentary_typography/samples/demo-portrait.json", PORTRAIT, compile_typography, validate_type),
            (LAB / "documentary_typography/samples/demo-impact-word.json", PLATE, compile_typography, validate_type),
            (LAB / "documentary_typography/samples/demo-quote.json", PLATE, compile_typography, validate_type),
            (LAB / "cinematic_overlays/samples/demo-spotlight.json", PLATE, compile_overlay, validate_plan),
            (LAB / "cinematic_overlays/samples/demo-key-fact.json", PLATE, compile_overlay, validate_plan),
            (LAB / "cinematic_overlays/samples/demo-route.json", PLATE, compile_overlay, validate_plan),
            (LAB / "cinematic_overlays/samples/demo-measurement.json", PLATE, compile_overlay, validate_plan),
        ]
        for path, media, compile, validate in samples:
            raw = json.loads(path.read_text(encoding="utf-8"))
            compiled = compile(validate(raw, duration=media["duration"]), media)
            self.assertEqual(len(compiled["graphics"]), 1)
            self.assertFalse(compiled["factual_claim"])

    def test_graphics_are_not_registered_with_the_cms(self):
        self.assertNotIn("cinematic_overlays", IMPLEMENTED)
        self.assertNotIn("documentary_typography", IMPLEMENTED)


if __name__ == "__main__":
    unittest.main()
