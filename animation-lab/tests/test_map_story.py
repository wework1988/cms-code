#!/usr/bin/env python3
"""Unit tests for map storytelling planner / resolver / compiler."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from map_story.compile import THEME, compile_resolved_plan, minimum_edge_margin, zoom_for_bounds
from map_story.themes import theme_for
from map_story.geo import GeoResolveError, load_registry, resolve_plan_places
from map_story.planner import golden_gorakhpur_plan
from map_story.schema import PlanValidationError, validate_semantic_plan


class SchemaTests(unittest.TestCase):
    def test_golden_valid(self):
        plan = golden_gorakhpur_plan(18)
        validate_semantic_plan(plan, duration_seconds=18)

    def test_invalid_timeline_gap(self):
        plan = golden_gorakhpur_plan(18)
        plan["shots"][1]["start"] = 3.5
        with self.assertRaises(PlanValidationError):
            validate_semantic_plan(plan, duration_seconds=18)

    def test_unsupported_action(self):
        plan = golden_gorakhpur_plan(18)
        plan["shots"][0]["actions"].append({"type": "fly_fighter_jet", "place": "india"})
        with self.assertRaises(PlanValidationError):
            validate_semantic_plan(plan)

    def test_rejects_invented_coordinates(self):
        plan = golden_gorakhpur_plan(18)
        plan["places"][0]["coordinates"] = [77.0, 28.0]
        with self.assertRaises(PlanValidationError):
            validate_semantic_plan(plan)


class ResolveTests(unittest.TestCase):
    def setUp(self):
        self.registry = load_registry()
        self.plan = golden_gorakhpur_plan(18)

    def test_resolve_gorakhpur_district(self):
        places = resolve_plan_places(self.plan, self.registry)
        self.assertIn("gorakhpur", places)
        self.assertEqual(places["gorakhpur"]["level"], "district")
        self.assertTrue(places["gorakhpur"]["geojson"].endswith("gorakhpur-district.geojson"))
        # Interior anchor inside bbox
        lon, lat = places["gorakhpur"]["anchor"]
        west, south, east, north = places["gorakhpur"]["bbox"]
        self.assertTrue(west <= lon <= east)
        self.assertTrue(south <= lat <= north)

    def test_ambiguous_city_vs_district_without_level(self):
        # Register a fake city alias collision by asking for city level
        bad = {
            "schema_version": "1.0",
            "type": "map_focus_sequence",
            "duration_seconds": 4,
            "language": "en",
            "style": "x",
            "places": [
                {"id": "india", "name": "India", "level": "country"},
                {"id": "g", "name": "Gorakhpur", "level": "city", "parent": "india"},
            ],
            "shots": [
                {
                    "id": "a",
                    "start": 0,
                    "end": 4,
                    "frame": "india",
                    "actions": [{"type": "hold"}],
                }
            ],
        }
        # city level should not match district registry entry
        with self.assertRaises(GeoResolveError):
            resolve_plan_places(bad, self.registry)

    def test_missing_boundary(self):
        reg = json.loads(json.dumps(self.registry))
        reg["places"]["uttar_pradesh"]["geojson"] = "assets/maps/india/does-not-exist.geojson"
        with self.assertRaises(GeoResolveError):
            resolve_plan_places(self.plan, reg)


class OpeningPolicyTests(unittest.TestCase):
    def test_frame_zero_is_country_centered_not_world(self):
        plan = golden_gorakhpur_plan(18)
        places = resolve_plan_places(plan)
        resolved = compile_resolved_plan(plan, places)
        k0 = resolved["camera"]["keyframes"][0]
        self.assertEqual(k0["pitch"], 0.0)
        self.assertEqual(k0["bearing"], 0.0)
        self.assertGreater(k0["zoom"], 2.5)
        self.assertGreater(k0["center"][0], 60.0)
        self.assertGreater(k0["center"][1], 10.0)

    def test_normalize_world_opening_from_model(self):
        from map_story.sequence import accept_focus_plan

        plan = golden_gorakhpur_plan(18)
        plan["shots"][0]["frame"] = "world"
        plan["shots"][0]["actions"] = [{"type": "establish_view", "place": "india"}]
        accepted = accept_focus_plan(
            plan,
            {"language": "hi", "target_focus_count": 5, "narration_unit_count": 2, "duration_seconds": 18},
            "documentary_relief_bold",
        )
        self.assertEqual(accepted["shots"][0]["frame"], "india")
        self.assertEqual(accepted["opening_policy"]["mode"], "country_centered")

    def test_model_world_scope_is_normalized_to_country(self):
        from map_story.opening import normalize_semantic_opening, trusted_world_opening_requested

        shot = {
            "id": "world",
            "frame": "world",
            "actions": [{"type": "establish_view", "scope": "world"}],
        }
        self.assertFalse(trusted_world_opening_requested({}))
        plan = golden_gorakhpur_plan(18)
        plan["shots"][0] = {**plan["shots"][0], **shot}
        normalized = normalize_semantic_opening(plan, language="hi")
        self.assertEqual(normalized["opening_policy"]["mode"], "country_centered")
        self.assertEqual(normalized["shots"][0]["frame"], "india")

    def test_trusted_world_override_is_preserved(self):
        from map_story.opening import normalize_semantic_opening

        plan = golden_gorakhpur_plan(18)
        plan["shots"][0]["frame"] = "world"
        plan["shots"][0]["actions"] = [{"type": "establish_view", "scope": "world"}]
        normalized = normalize_semantic_opening(
            plan,
            language="hi",
            job_settings={"opening_override": "world_overview"},
        )
        self.assertEqual(normalized["opening_policy"]["mode"], "world_overview")
        self.assertEqual(normalized["shots"][0]["frame"], "world")

    def test_portrait_opening_fits_country(self):
        plan = golden_gorakhpur_plan(18)
        places = resolve_plan_places(plan)
        resolved = compile_resolved_plan(plan, places, width=1080, height=1920)
        opening = resolved["composition"]["opening"]
        self.assertEqual(opening["primary_country_id"], "india")
        k0 = resolved["camera"]["keyframes"][0]
        india_bbox = places["india"]["bbox"]
        margin = minimum_edge_margin(
            india_bbox, k0["center"], k0["zoom"], 1080, 1920, tile_size=512
        )
        self.assertGreaterEqual(margin, 0.06)


class CameraTests(unittest.TestCase):
    def test_india_fit_keeps_islands_inside_maplibre_frame(self):
        india = [68.165039, 6.748682, 97.343555, 35.495898]
        center, zoom = zoom_for_bounds(india, 1920, 1080, padding=0.10, tile_size=512)
        margin = minimum_edge_margin(india, center, zoom, 1920, 1080, tile_size=512)
        self.assertGreaterEqual(margin, 0.08)
        self.assertLessEqual(margin, 0.13)

    def test_zoom_increases_for_smaller_bbox(self):
        india = [68.0, 6.7, 97.3, 35.5]
        gora = [83.07, 26.22, 83.67, 27.14]
        _, z_india = zoom_for_bounds(india, 1920, 1080, padding=0.14)
        _, z_gora = zoom_for_bounds(gora, 1920, 1080, padding=0.2)
        self.assertGreater(z_gora, z_india)

    def test_dateline_bbox_uses_short_arc(self):
        # A shape around the date line should not be treated as almost-global width.
        bbox = [170.0, -12.0, -170.0, 9.0]
        center, zoom = zoom_for_bounds(bbox, 1920, 1080, padding=0.12)
        self.assertGreater(center[0], 160.0)  # wrapped midpoint near the date line
        self.assertGreater(zoom, 2.0)

    def test_compile_keyframes_cover_duration(self):
        plan = golden_gorakhpur_plan(18)
        places = resolve_plan_places(plan)
        resolved = compile_resolved_plan(plan, places)
        self.assertEqual(resolved["duration"], 18)
        kfs = resolved["camera"]["keyframes"]
        self.assertEqual(kfs[0]["t"], 0)
        self.assertGreaterEqual(kfs[-1]["t"], 18 - 1e-6)
        self.assertIsNotNone(resolved["callout"])
        self.assertEqual(resolved["callout"]["text"], "गोरखपुर")


class RegressionTests(unittest.TestCase):
    def test_conflicting_id_and_name(self):
        plan = golden_gorakhpur_plan(18)
        plan["places"][0]["name"] = "Bangladesh"
        with self.assertRaises(GeoResolveError):
            resolve_plan_places(plan)

    def test_unsupported_style_rejected(self):
        plan = golden_gorakhpur_plan(18)
        plan["style"] = "satellite_live"
        with self.assertRaises(PlanValidationError):
            validate_semantic_plan(plan)

    def test_invalid_padding_rejected(self):
        plan = golden_gorakhpur_plan(18)
        plan["shots"][1]["actions"][0]["padding"] = 5
        with self.assertRaises(PlanValidationError):
            validate_semantic_plan(plan)

    def test_saved_plan_keeps_its_duration(self):
        plan = golden_gorakhpur_plan(12)
        validate_semantic_plan(plan, duration_seconds=None)
        self.assertEqual(plan["duration_seconds"], 12)

    def test_hidden_parent_is_not_left_visible(self):
        plan = golden_gorakhpur_plan(18)
        plan["shots"][1]["actions"][1]["parent_context"] = "hidden"
        places = resolve_plan_places(plan)
        resolved = compile_resolved_plan(plan, places)
        india_after = [
            h for h in resolved["highlights"]
            if h["place"] == "india" and h["from"] >= 3 and h["role"] == "context"
        ]
        self.assertEqual(india_after, [])

    def test_selection_offsets_and_beat_count(self):
        from map_story.selection import heuristic_select, plan_from_selection
        script = (
            "Intro without a map.\n\n"
            "Show Gorakhpur district in Uttar Pradesh, India. "
            "Start from the world, then the state, then the district.\n\n"
            "Later text."
        )
        selected = heuristic_select(script, max_clips=3, duration_seconds=18)
        self.assertEqual(len(selected["clips"]), 1)
        clip = selected["clips"][0]
        self.assertEqual(script[clip["offset_start"]:clip["offset_end"]], clip["source_passage"])
        self.assertEqual(clip["narration_unit_count"], 2)
        self.assertEqual(clip["target_focus_count"], 3)
        self.assertEqual(len(clip["beats"]), 3)
        plan = plan_from_selection(clip)
        self.assertEqual(plan["duration_seconds"], 14)
        self.assertEqual(plan["style"], "documentary_relief_bold")
        from map_story.schema import meaningful_beat_count
        self.assertEqual(meaningful_beat_count(plan), 3)

    def test_first_three_passages_in_script_order(self):
        from map_story.selection import heuristic_select
        script = (
            "India and Uttar Pradesh open the story.\n\n"
            "India and Gorakhpur district come next, still inside Uttar Pradesh.\n\n"
            "Back to India and Uttar Pradesh for a third map.\n\n"
            "A fourth India and Uttar Pradesh passage should not be used.\n"
        )
        selected = heuristic_select(script, max_clips=8)
        passages = [c["source_passage"] for c in selected["clips"]]
        self.assertEqual(len(passages), 3)
        self.assertTrue(passages[0].startswith("India and Uttar Pradesh open"))
        self.assertIn("Gorakhpur", passages[1])
        self.assertTrue(passages[2].startswith("Back to India"))
        self.assertTrue(all("fourth" not in p for p in passages))
        self.assertEqual([c["offset_start"] for c in selected["clips"]], sorted(c["offset_start"] for c in selected["clips"]))

    def test_scene_filename_from_overlapping_passage(self):
        from pathlib import Path
        from map_story.scenes import parse_scene_text, scene_numbers_for_passage, scene_video_name
        scene_file = Path(__file__).resolve().parents[2] / "cms-generate-stories/general/171-sample-test-full-story-genertion/scenes/scene.txt"
        scenes = parse_scene_text(scene_file.read_text(encoding="utf-8"))
        passage = (
            "लगभग एक मिनट की हिंदी कहानी: “वडनगर से दिल्ली तक”\n\n"
            "गुजरात का एक छोटा-सा शहर—वडनगर।\n\n"
            "यहीं, 17 सितंबर 1950 को नरेंद्र मोदी का जन्म हुआ।"
        )
        numbers = scene_numbers_for_passage(passage, scenes)
        self.assertEqual(numbers, [1, 2])
        self.assertEqual(scene_video_name(numbers), "scene_1_2")
        self.assertEqual(scene_video_name([1, 2, 3]), "scene_1_2_3")

    def test_rejects_unsafe_clip_id(self):
        from map_story.selection import SelectionError, validate_selection_document
        script = "India and Uttar Pradesh."
        doc = {
            "schema_version": "1.0",
            "clips": [{
                "id": "../escape",
                "animation_type": "map",
                "title": "Bad",
                "source_passage": script,
                "offset_start": 0,
                "offset_end": len(script),
                "reason": "test",
                "duration_seconds": 18,
                "places": [{"id": "india", "name": "India", "level": "country"}],
                "beats": [
                    {"purpose": "a", "action": "highlight"},
                    {"purpose": "b", "action": "zoom_to_boundary"},
                    {"purpose": "c", "action": "show_callout"},
                ],
                "narration_start": None,
                "narration_end": None,
            }],
        }
        with self.assertRaises(SelectionError):
            validate_selection_document(doc, script, max_clips=3)

    def test_retry_status_keeps_other_failed_clips(self):
        sys.path.insert(0, str(ROOT.parent / "story-pipeline-worker"))
        from run_map_animations import overall_status
        status, _message = overall_status([
            {"status": "completed"},
            {"status": "failed"},
        ])
        self.assertEqual(status, "completed_with_errors")

    def test_no_suitable_passage(self):
        from map_story.selection import heuristic_select
        selected = heuristic_select("The bakery opened on Tuesday.", max_clips=3)
        self.assertEqual(selected["clips"], [])
        self.assertTrue(selected["explanation"])

    def test_resolved_plan_contains_composition_diagnostics(self):
        plan = golden_gorakhpur_plan(18)
        places = resolve_plan_places(plan)
        resolved = compile_resolved_plan(plan, places)
        self.assertIn("composition", resolved)
        composition = resolved["composition"]
        self.assertEqual(composition["version"], "1.2")
        self.assertIn("opening", composition)
        self.assertEqual(composition["opening"]["policy"], "country_centered")
        self.assertEqual(composition["opening"]["primary_country_id"], "india")
        self.assertTrue(composition["stages"])
        first = composition["stages"][0]
        self.assertIn("camera", first)
        self.assertIn("labels", first)


class StylePresetTests(unittest.TestCase):
    def test_cinematic_tokens_stay_available(self):
        self.assertEqual(THEME["ocean"], "#0e1a2e")
        self.assertEqual(THEME["fill"]["mode"], "translucent")
        bold = theme_for("documentary_relief_bold")
        self.assertEqual(bold["ocean"], "#103E4A")
        self.assertEqual(bold["fill"]["mode"], "terrain_color")
        self.assertNotEqual(bold["ocean"], THEME["ocean"])

    def test_documentary_style_is_accepted(self):
        plan = golden_gorakhpur_plan(18)
        plan["style"] = "documentary_relief_bold"
        validate_semantic_plan(plan, duration_seconds=18)
        places = resolve_plan_places(plan)
        resolved = compile_resolved_plan(plan, places)
        self.assertEqual(resolved["style"], "documentary_relief_bold")
        self.assertEqual(resolved["theme"]["id"], "documentary_relief_bold")
        self.assertEqual(max(kf["pitch"] for kf in resolved["camera"]["keyframes"]), 0)
        classic = compile_resolved_plan(golden_gorakhpur_plan(18), places)
        self.assertGreater(max(kf["pitch"] for kf in classic["camera"]["keyframes"]), 0)
        self.assertEqual(classic["theme"]["ocean"], "#0e1a2e")


class SavedPlanTests(unittest.TestCase):
    def test_roundtrip_without_api(self):
        plan = golden_gorakhpur_plan(18)
        places = resolve_plan_places(plan)
        resolved = compile_resolved_plan(plan, places)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "resolved-plan.json"
            p.write_text(json.dumps(resolved), encoding="utf-8")
            loaded = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(loaded["type"], "map_focus_sequence")
            self.assertEqual(len(loaded["features"]), 3)


if __name__ == "__main__":
    unittest.main()
