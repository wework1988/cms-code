"""Story passage selection and focus counts for the documentary map style."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from map_story.catalog import create_fixture, planner_summaries, resolve_requests
from map_story.narration import count_narration_units, split_sentences
from map_story.schema import meaningful_beat_count, style_from_snapshot
from map_story.selection import SelectionError, plan_from_selection, select_story
from map_story.sequence import build_focus_plan


class NarrationTests(unittest.TestCase):
    def test_line_breaks_do_not_change_the_unit_count(self):
        compact = "National Capital Territory of Delhi sits in the north. The territory is the capital."
        wrapped = "National Capital Territory\nof Delhi sits in the north.\n\nThe territory is the capital."
        self.assertEqual(count_narration_units(compact)["count"], 2)
        self.assertEqual(count_narration_units(wrapped)["count"], count_narration_units(compact)["count"])
        self.assertEqual(count_narration_units(compact)["method"], "sentences")

    def test_abbreviations_and_danda(self):
        self.assertEqual(len(split_sentences("Dr. Sharma reached the city. He stayed.")), 2)
        self.assertEqual(len(split_sentences("दिल्ली भारत में है। यह राजधानी है।")), 2)
        self.assertEqual(count_narration_units("एक ही वाक्य बिना विराम के")["count"], 1)


class StoryPlanningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "geography.sqlite"
        create_fixture(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_two_sentence_delhi_has_three_stages(self):
        script = (
            "National Capital Territory of Delhi sits in the north. "
            "National Capital Territory of Delhi is the capital region."
        )
        selected = select_story(script, catalog_path=self.path, language="hi")
        self.assertEqual(len(selected["clips"]), 1)
        clip = selected["clips"][0]
        self.assertEqual(clip["narration_unit_count"], 2)
        self.assertEqual(clip["target_focus_count"], 3)
        self.assertEqual(clip["counting_method"], "sentences")
        plan = self._plan(clip)
        self.assertEqual(meaningful_beat_count(plan), 3)
        self.assertEqual(plan["style"], "documentary_relief_bold")
        ids = {place["id"] for place in plan["places"]}
        self.assertIn("gb-adm1-IN-DL", ids)
        self.assertIn("ne-adm0-ind", ids)
        self.assertNotIn("gn-delhi-city", ids)
        self.assertEqual(plan["shots"][0]["actions"][0]["motion"], "hold")
        self.assertEqual(plan["shots"][0]["actions"][0]["padding"], 0.10)
        colors = [action["color"] for shot in plan["shots"] for action in shot["actions"] if action.get("type") == "highlight"]
        self.assertEqual(colors[0], "#A32320")
        self.assertIn("#D4B300", colors)

    def test_nested_area_has_four_stages(self):
        script = (
            "National Capital Territory of Delhi is the capital region. "
            "नई दिल्ली उस क्षेत्र के अंदर है। "
            "नई दिल्ली का नाम मानचित्र पर दिखना चाहिए।"
        )
        clip = select_story(script, catalog_path=self.path, language="hi")["clips"][0]
        self.assertEqual(clip["narration_unit_count"], 3)
        self.assertEqual(clip["target_focus_count"], 4)
        plan = self._plan(clip)
        self.assertEqual(meaningful_beat_count(plan), 4)
        ids = [place["id"] for place in plan["places"]]
        self.assertIn("gb-adm2-new-delhi", ids)
        self.assertNotIn("gn-delhi-city", ids)
        levels = {place["id"]: place["level"] for place in plan["places"]}
        self.assertEqual(levels["gb-adm2-new-delhi"], "district")
        self.assertEqual(levels["gb-adm1-IN-DL"], "state")

    def test_multi_state_passage_uses_each_state(self):
        script = (
            "Gujarat opens the route. "
            "Uttar Pradesh continues it. "
            "National Capital Territory of Delhi is the last stop."
        )
        clip = select_story(script, catalog_path=self.path, language="en")["clips"][0]
        self.assertEqual(clip["target_focus_count"], 4)
        plan = self._plan(clip)
        ids = {place["id"] for place in plan["places"]}
        self.assertTrue({"gb-adm1-IN-GJ", "gb-adm1-IN-UP", "gb-adm1-IN-DL", "ne-adm0-ind"} <= ids)
        self.assertEqual(meaningful_beat_count(plan), 4)
        highlighted = [
            action["place"] for shot in plan["shots"] for action in shot["actions"] if action.get("type") == "highlight"
        ]
        self.assertEqual(highlighted[0], "ne-adm0-ind")
        for place_id in ("gb-adm1-IN-GJ", "gb-adm1-IN-UP", "gb-adm1-IN-DL"):
            self.assertIn(place_id, highlighted)

    def test_ambiguous_place_is_not_substituted(self):
        script = "Rampur grew quickly. Rampur is known for its market."
        clip = select_story(script, catalog_path=self.path)["clips"][0]
        self.assertEqual(clip["review_status"], "needs_location_clarification")
        with self.assertRaises(SelectionError):
            plan_from_selection(clip, summaries=[])

    def test_story_without_geography_returns_no_clips(self):
        selected = select_story("The bakery opened on Tuesday. The bread sold out.", catalog_path=self.path)
        self.assertEqual(selected["clips"], [])
        self.assertTrue(selected["explanation"])

    def test_multiple_countries_do_not_force_india(self):
        cards = [
            {"id": "country-a", "name": "Alpha", "level": "country", "country_code": "AA", "role": "subject", "representation": "polygon"},
            {"id": "country-b", "name": "Beta", "level": "country", "country_code": "BB", "role": "subject", "representation": "polygon"},
        ]
        plan = build_focus_plan(
            cards,
            language="en",
            style="documentary_relief_bold",
            target_focus_count=3,
            narration_unit_count=2,
            counting_method="sentences",
            focus_decision="two_units_three_focuses",
        )
        self.assertEqual(plan["shots"][0]["frame"], "country-a")
        self.assertEqual(plan["shots"][0]["actions"][0]["type"], "zoom_to_boundary")
        self.assertEqual(plan["shots"][0]["actions"][0]["motion"], "hold")
        self.assertNotIn("ne-adm0-ind", {place["id"] for place in plan["places"]})
        self.assertEqual(meaningful_beat_count(plan), 3)

    def test_city_cue_keeps_jaipur_a_city(self):
        from map_story.catalog import ACTIVE_PATH
        if not ACTIVE_PATH.is_file():
            self.skipTest("production catalogue is not installed")
        script = "राजस्थान के जयपुर में हवा महल शहर की ऐतिहासिक पहचान का हिस्सा है।"
        selected = select_story(script, catalog_path=ACTIVE_PATH, language="hi")
        self.assertEqual(len(selected["clips"]), 1)
        clip = selected["clips"][0]
        self.assertNotIn("review_status", clip)
        city = next(item for item in clip["place_requests"] if item["name"] == "जयपुर")
        self.assertEqual(city["level"], "city")
        from map_story.catalog import resolve_requests
        results = resolve_requests(clip["place_requests"], catalog_path=ACTIVE_PATH)
        self.assertTrue(all(item["status"] == "resolved" for item in results), results)
        jaipur = next(item["place"] for item in results if item["requested"]["name"] == "जयपुर")
        self.assertEqual(jaipur["level"], "city")
        self.assertEqual(jaipur["representation"], "point")

    def test_selection_keeps_a_passage_when_suggested_beats_differ(self):
        from map_story.selection import finalize_selection, validate_selection_document
        script = "राजस्थान के जयपुर में हवा महल शहर की ऐतिहासिक पहचान का हिस्सा है।"
        suggestions = [
            {"purpose": "Show India"},
            {"purpose": "Show Rajasthan"},
            {"purpose": "Focus Jaipur"},
            {"purpose": "Hold the label"},
        ]
        clip = {
            "id": "clip_01",
            "animation_type": "map",
            "title": "जयपुर",
            "source_passage": script,
            "offset_start": 0,
            "offset_end": len(script),
            "reason": "A city.",
            "place_requests": [{"name": "जयपुर", "level": "city"}],
            "duration_seconds": 18,
            "beats": suggestions,
        }
        done = finalize_selection({"clips": [clip]}, script)
        selected = done["clips"][0]
        self.assertEqual(selected["narration_unit_count"], 1)
        self.assertEqual(selected["target_focus_count"], 3)
        self.assertEqual(selected["advisory_beat_count"], 4)
        self.assertEqual([beat["purpose"] for beat in selected["beats"]], [item["purpose"] for item in suggestions])
        validated = validate_selection_document(done, script, max_clips=3)
        self.assertEqual(len(validated["clips"][0]["beats"]), 4)
        self.assertEqual(validated["clips"][0]["target_focus_count"], 3)
        missing = dict(clip)
        missing["source_passage"] = "यह वाक्य स्क्रिप्ट में नहीं है।"
        missing["offset_start"] = 0
        missing["offset_end"] = len(missing["source_passage"])
        counted = finalize_selection({"clips": [missing]}, script)
        with self.assertRaises(SelectionError):
            validate_selection_document(counted, script, max_clips=3)

    def test_documentary_focus_planning_asks_the_model(self):
        import sys
        worker_dir = Path(__file__).resolve().parents[2] / "story-pipeline-worker"
        sys.path.insert(0, str(worker_dir))
        import run_map_animations as worker
        from map_story import sequence

        called = {"model": 0, "local": 0}
        original_local = worker.plan_from_selection
        original_model = worker.generate_semantic_plan
        original_key = worker.load_key
        original_accept = sequence.accept_focus_plan

        def local_plan(*_args, **_kwargs):
            called["local"] += 1
            raise AssertionError("local sequence replaced the model plan")

        def model_plan(*args, **kwargs):
            called["model"] += 1
            self.assertIn("USE THIS SAVED PROMPT", args[0])
            self.assertEqual(kwargs["expected_focus_count"], 3)
            return {"generation": {"provider": "deepseek"}, "target_focus_count": 3}

        def accept(plan, _selection, style, _theme=None, _summaries=None):
            plan["style"] = style
            return plan

        worker.plan_from_selection = local_plan
        worker.generate_semantic_plan = model_plan
        worker.load_key = lambda _path: "test-key"
        sequence.accept_focus_plan = accept
        try:
            plan = worker.plan_clip(
                {
                    "planner": "deepseek",
                    "style": "documentary_relief_bold",
                    "master_prompt": "USE THIS SAVED PROMPT",
                    "language": "hi",
                    "env_file": "/tmp/missing.env",
                },
                {"target_focus_count": 3, "duration_seconds": 14, "source_passage": "जयपुर"},
                [{"id": "gn-1269515", "name": "Jaipur"}],
            )
            self.assertEqual(called["model"], 1)
            self.assertEqual(called["local"], 0)
            self.assertEqual(plan["focus_planning_provider"], "deepseek")
            self.assertEqual(plan["style"], "documentary_relief_bold")
            with self.assertRaises(SelectionError):
                worker.select_clips({
                    "planner": "deepseek",
                    "script": "जयपुर",
                    "master_prompt": "  ",
                    "max_clips": 1,
                })
        finally:
            worker.plan_from_selection = original_local
            worker.generate_semantic_plan = original_model
            worker.load_key = original_key
            sequence.accept_focus_plan = original_accept

    def test_legacy_snapshot_keeps_its_style(self):
        self.assertEqual(style_from_snapshot({"job_id": "old"}), "cinematic_terrain")
        self.assertEqual(style_from_snapshot({"style": "documentary_relief_bold"}), "documentary_relief_bold")

    def _plan(self, clip):
        results = resolve_requests(clip["place_requests"], catalog_path=self.path)
        self.assertTrue(all(item["status"] == "resolved" for item in results))
        return plan_from_selection(
            clip,
            language="hi",
            style="documentary_relief_bold",
            summaries=planner_summaries(results, catalog_path=self.path),
        )


if __name__ == "__main__":
    unittest.main()
