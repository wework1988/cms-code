"""Local catalogue lookup, marker framing, and prompt boundaries."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "story-pipeline-worker"))

from map_story.catalog import (  # noqa: E402
    activate_database,
    create_fixture,
    lookup,
    planner_summaries,
    resolve_catalog_places,
    resolve_requests,
)
from map_story.compile import compile_resolved_plan  # noqa: E402
from map_story.geo import GeoResolveError, normalize_name  # noqa: E402
from map_story.schema import PlanValidationError, validate_semantic_plan  # noqa: E402
from map_story.selection import clip_planning_payload, selection_prompt  # noqa: E402
from run_map_animations import align_selection_offsets, contained_dir  # noqa: E402


def point_plan():
    return {
        "schema_version": "1.0",
        "type": "map_focus_sequence",
        "duration_seconds": 12,
        "language": "hi",
        "style": "cinematic_terrain",
        "ambiguity": [],
        "places": [
            {"id": "india", "name": "India", "level": "country"},
            {"id": "gujarat", "name": "Gujarat", "level": "state", "parent": "india"},
            {"id": "vadnagar", "name": "Vadnagar", "level": "city", "parent": "gujarat"},
        ],
        "shots": [
            {"id": "a", "start": 0, "end": 3, "frame": "world", "actions": [
                {"type": "establish_view", "place": "india"},
                {"type": "highlight", "place": "india", "color": "#E52B32", "fill_opacity": 0.4},
            ]},
            {"id": "b", "start": 3, "end": 6, "frame": "gujarat", "actions": [
                {"type": "zoom_to_boundary", "place": "gujarat", "padding": 0.14},
                {"type": "highlight", "place": "gujarat", "color": "#E52B32", "fill_opacity": 0.45, "parent_context": "subdued"},
            ]},
            {"id": "c", "start": 6, "end": 9, "frame": "vadnagar", "actions": [
                {"type": "zoom_to_boundary", "place": "vadnagar", "padding": 0.16},
            ]},
            {"id": "d", "start": 9, "end": 12, "frame": "vadnagar", "actions": [
                {"type": "show_marker", "place": "vadnagar", "color": "#E6D545", "size": 12, "pulse": True},
                {"type": "show_callout", "place": "vadnagar", "text": "वडनगर", "presentation": "text_box_with_arrow"},
                {"type": "hold"},
            ]},
        ],
    }


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "fixture.sqlite"
        create_fixture(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_devanagari_vowels_survive_normalisation(self):
        self.assertEqual(normalize_name("भारत"), "भारत")
        self.assertEqual(normalize_name("गुजरात"), "गुजरात")
        self.assertEqual(normalize_name("Gujarāt"), "gujarat")
        self.assertEqual(normalize_name("Gorakhpur District"), "gorakhpur")

    def test_exact_english_and_hindi(self):
        gujarat = lookup("Gujarat", level="state", catalog_path=self.path)
        self.assertEqual(gujarat["status"], "resolved")
        self.assertEqual(gujarat["place"]["id"], "gb-adm1-IN-GJ")
        self.assertEqual(gujarat["place"]["representation"], "boundary")
        hindi = lookup("गुजरात", country="IN", catalog_path=self.path)
        self.assertEqual(hindi["place"]["name"], "Gujarat")
        self.assertEqual(lookup("भारत", catalog_path=self.path)["place"]["level"], "country")
        self.assertEqual(lookup("उत्तर प्रदेश", level="state", catalog_path=self.path)["place"]["name"], "Uttar Pradesh")
        vad = lookup("वडनगर", country="IN", catalog_path=self.path)
        self.assertEqual(vad["status"], "resolved")
        via_hindi_state = lookup("वडनगर", state="गुजरात", level="city", catalog_path=self.path)
        self.assertEqual(via_hindi_state["status"], "resolved")
        self.assertEqual(via_hindi_state["place"]["id"], "gn-vadnagar")
        self.assertEqual(vad["place"]["representation"], "point")
        self.assertEqual(vad["place"]["state_name"], "Gujarat")

    def test_spelling_variation_stays_a_suggestion(self):
        result = lookup("Vadnager", state="Gujarat", catalog_path=self.path)
        self.assertEqual(result["status"], "not_found")
        self.assertTrue(any(item["name"] == "Vadnagar" for item in result["candidates"]))
        self.assertTrue(all(item.get("suggestion_only") for item in result["candidates"]))

    def test_close_spellings_do_not_auto_resolve(self):
        result = lookup("Rampure", catalog_path=self.path)
        self.assertEqual(result["status"], "not_found")
        self.assertGreaterEqual(len(result["candidates"]), 2)

    def test_country_parent_is_not_treated_as_a_state(self):
        from map_story.catalog import resolve_requests
        delhi = resolve_requests([{
            "name": "दिल्ली",
            "level": "city",
            "parent_name": "भारत",
            "country": "भारत",
        }], catalog_path=self.path)[0]
        self.assertEqual(delhi["status"], "resolved")
        self.assertEqual(delhi["place"]["id"], "gn-delhi-city")
        self.assertIsNone(delhi["context"]["state"])
        gujarat = resolve_requests([{
            "name": "Gujarat",
            "level": "state",
            "parent_name": "India",
        }], catalog_path=self.path)[0]
        self.assertEqual(gujarat["status"], "resolved")
        self.assertEqual(gujarat["place"]["id"], "gb-adm1-IN-GJ")
        self.assertIsNone(gujarat["context"]["state"])

    def test_district_parent_is_not_treated_as_a_state(self):
        from map_story.catalog import resolve_requests
        city = resolve_requests([{
            "name": "गोरखपुर",
            "level": "city",
            "parent_name": "Gorakhpur",
        }], catalog_path=self.path)[0]
        self.assertEqual(city["status"], "resolved")
        self.assertEqual(city["place"]["id"], "gn-gorakhpur-city")
        self.assertFalse(city["context"]["verified"]["district"])
        self.assertFalse(city["context"]["membership_verified"])
        self.assertEqual(city["context"]["relationship_source"], "inferred")
        self.assertEqual(city["context"]["parent_entity"]["id"], "gb-adm2-gorakhpur")
        self.assertFalse(city["context"]["verified"]["state"])

    def test_weak_spelling_stays_a_suggestion(self):
        result = lookup("Atlantis", catalog_path=self.path)
        self.assertEqual(result["status"], "not_found")
        self.assertTrue(all(item.get("suggestion_only") for item in result["candidates"]))

    def test_ambiguous_repeated_names_and_city_versus_district(self):
        rampur = lookup("Rampur", catalog_path=self.path)
        self.assertEqual(rampur["status"], "ambiguous")
        self.assertGreaterEqual(len(rampur["candidates"]), 2)
        narrowed = lookup("Rampur", state="Gujarat", catalog_path=self.path)
        self.assertEqual(narrowed["place"]["id"], "gn-rampur-gj")
        both = lookup("Gorakhpur", catalog_path=self.path)
        self.assertEqual(both["status"], "ambiguous")
        district = lookup("Gorakhpur", level="district", state="Uttar Pradesh", catalog_path=self.path)
        self.assertEqual(district["place"]["level"], "district")
        self.assertEqual(district["place"]["representation"], "boundary")
        city = lookup("गोरखपुर", level="city", state="Uttar Pradesh", catalog_path=self.path)
        self.assertEqual(city["place"]["representation"], "point")
        self.assertNotEqual(city["place"]["id"], district["place"]["id"])

    def test_delhi_territory_is_explicit(self):
        mixed = lookup("दिल्ली", catalog_path=self.path)
        self.assertEqual(mixed["status"], "ambiguous")
        territory = lookup("Delhi", level="state", catalog_path=self.path)
        self.assertEqual(territory["place"]["feature_type"], "national_capital_territory")
        self.assertIn("National Capital Territory", territory["reason"])
        self.assertEqual(territory["place"]["representation"], "boundary")

    def test_conflicting_id_and_parent_containment(self):
        with self.assertRaises(GeoResolveError):
            resolve_catalog_places({
                "places": [{"id": "gn-vadnagar", "name": "Bangladesh", "level": "city"}],
            }, self.path)
        resolved = resolve_catalog_places({
            "places": [
                {"id": "ne-adm0-ind", "name": "India", "level": "country"},
                {"id": "gb-adm1-IN-GJ", "name": "Gujarat", "level": "state", "parent": "ne-adm0-ind"},
                {"id": "gn-vadnagar", "name": "Vadnagar", "level": "city", "parent": "gb-adm1-IN-GJ"},
            ],
        }, self.path)
        self.assertEqual(resolved["gn-vadnagar"]["geometry"]["type"], "Point")
        outside = dict(resolved["gn-vadnagar"])
        # A point placed over Uttar Pradesh must not validate inside Gujarat.
        moved = {
            "places": [
                {"id": "gb-adm1-IN-GJ", "name": "Gujarat", "level": "state"},
                {"id": "gn-gorakhpur-city", "name": "Gorakhpur", "level": "city", "parent": "gb-adm1-IN-GJ"},
            ],
        }
        with self.assertRaises(GeoResolveError):
            resolve_catalog_places(moved, self.path)

    def test_missing_place(self):
        result = lookup("Atlantis", catalog_path=self.path)
        self.assertEqual(result["status"], "not_found")
        self.assertTrue(result["reason"])

    def test_planner_summaries_omit_geometry(self):
        results = resolve_requests(
            [{"name": "वडनगर", "level": "city", "parent_name": "Gujarat", "country": "IN"}],
            catalog_path=self.path,
        )
        cards = planner_summaries(results, catalog_path=self.path)
        blob = json.dumps(cards)
        self.assertNotIn("coordinates", blob)
        self.assertNotIn("72.64", blob)
        self.assertNotIn("geometry", blob)
        self.assertTrue(any(card["id"] == "gb-adm1-IN-GJ" and card["role"] == "orientation" for card in cards))
        payload = clip_planning_payload("prompt", {"source_passage": "वडनगर", "reason": "map", "beats": []}, cards, "hi", 18)
        encoded = json.dumps(payload)
        self.assertNotIn("Polygon", encoded)
        self.assertNotIn("[[", encoded)
        prompt = selection_prompt("Read the script.", [{"id": "only-three"}], 3, "hi", 18)
        self.assertNotIn("only-three", prompt)
        self.assertNotIn("gorakhpur-district", prompt)

    def test_atomic_failure_keeps_previous_catalogue(self):
        active = Path(self.tmp.name) / "geography.sqlite"
        active.write_text("previous-good", encoding="utf-8")
        building = Path(self.tmp.name) / "geography.sqlite.building"
        building.write_bytes(b"this is not a sqlite database")
        with self.assertRaises(Exception):
            activate_database(building, active)
        self.assertEqual(active.read_text(encoding="utf-8"), "previous-good")

    def test_point_marker_framing_and_rejected_coordinates(self):
        plan = point_plan()
        validate_semantic_plan(plan, enforce_beats=True)
        bad = json.loads(json.dumps(plan))
        bad["shots"][3]["actions"][0]["coordinates"] = [72.6, 23.8]
        with self.assertRaises(PlanValidationError):
            validate_semantic_plan(bad)
        india = [(68, 8), (78, 8), (78, 32), (68, 32), (68, 8)]
        gujarat = [(68.5, 20), (74.5, 20), (74.5, 24.5), (68.5, 24.5), (68.5, 20)]

        def polygon(coords):
            return {"type": "Polygon", "coordinates": [coords]}

        places = {
            "india": {
                "id": "india", "name": "India", "level": "country", "source_id": "fixture:india",
                "representation": "boundary", "bbox": [68, 8, 78, 32], "anchor": [73, 22],
                "geometry": polygon(india), "geojson": "/assets/maps/india/india.geojson",
            },
            "gujarat": {
                "id": "gujarat", "name": "Gujarat", "level": "state", "parent": "india", "source_id": "fixture:gj",
                "representation": "boundary", "bbox": [68.5, 20, 74.5, 24.5], "anchor": [72, 22],
                "geometry": polygon(gujarat),
                "feature": {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": polygon(gujarat)}]},
            },
            "vadnagar": {
                "id": "vadnagar", "name": "Vadnagar", "level": "city", "parent": "gujarat", "source_id": "fixture:vad",
                "representation": "point", "bbox": [72.64, 23.79, 72.64, 23.79], "anchor": [72.64, 23.79],
                "geometry": {"type": "Point", "coordinates": [72.64, 23.79]},
                "feature": {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [72.64, 23.79]}}]},
            },
        }
        resolved = compile_resolved_plan(plan, places)
        self.assertEqual(resolved["markers"][0]["anchor"], [72.64, 23.79])
        self.assertEqual(resolved["features"]["vadnagar"]["feature"]["features"][0]["geometry"]["type"], "Point")
        point_frames = [frame for frame in resolved["camera"]["keyframes"] if abs(frame["center"][0] - 72.64) < 1]
        self.assertTrue(point_frames)
        self.assertLessEqual(max(frame["zoom"] for frame in point_frames), 8.6)
        self.assertGreater(point_frames[-1]["zoom"], 4)

    def test_exact_quotation_offsets_are_computed_locally(self):
        script = "गुजरात का एक छोटा-सा शहर—वडनगर।"
        doc = {"clips": [{"source_passage": script, "offset_start": 5, "offset_end": 9}]}
        align_selection_offsets(doc, script)
        self.assertEqual(doc["clips"][0]["offset_start"], 0)
        self.assertEqual(doc["clips"][0]["offset_end"], len(script))
        paraphrased = {"clips": [{"source_passage": "not in the script", "offset_start": 1, "offset_end": 2}]}
        align_selection_offsets(paraphrased, script)
        self.assertEqual(paraphrased["clips"][0]["offset_start"], 1)

    def test_devanagari_spacing_matches_a_verified_alias(self):
        self.assertEqual(normalize_name("तमिल नाडु"), "तमिलनाडु")
        self.assertEqual(normalize_name("Tamil Nadu"), "tamil nadu")
        from map_story.catalog import _add_alias, connect
        conn = connect(self.path, readonly=False)
        try:
            _add_alias(conn, "gb-adm1-IN-UP", "तमिल नाडु", "hi", "test:spacing")
            conn.commit()
        finally:
            conn.close()
        matched = lookup("तमिलनाडु", level="state", catalog_path=self.path)
        self.assertEqual(matched["status"], "resolved")
        self.assertEqual(matched["place"]["id"], "gb-adm1-IN-UP")

    def test_parent_filter_uses_the_canonical_state_id(self):
        narrowed = lookup("Rampur", state="गुजरात", catalog_path=self.path)
        self.assertEqual(narrowed["status"], "resolved")
        self.assertEqual(narrowed["place"]["id"], "gn-rampur-gj")
        self.assertEqual(narrowed["place"]["state_place_id"], "gb-adm1-IN-GJ")

    def test_optional_river_does_not_block_a_resolved_city(self):
        from map_story.catalog import apply_feature_policy
        city = {
            "status": "resolved",
            "requested": {"name": "कोलकाता", "level": "city"},
            "place": {"id": "gn-1275004", "name": "Kolkata", "level": "city", "state_place_id": "gb-adm1-IN-WB"},
        }
        river = {
            "status": "not_found",
            "reason": "No exact canonical name or alias matched.",
            "requested": {"name": "हुगली नदी", "level": "city"},
        }
        ready = apply_feature_policy([city, river])
        self.assertEqual(ready["status"], "ready")
        self.assertEqual(ready["resolved"], [city])
        self.assertEqual(ready["omitted_features"][0]["name"], "हुगली नदी")
        self.assertTrue(ready["warnings"])
        from map_story.catalog import passage_omissions
        warnings, omitted = passage_omissions(
            "यहाँ हावड़ा ब्रिज और हुगली नदी शहर की पहचान बनाते हैं।",
            ["हुगली नदी"],
        )
        self.assertEqual(omitted[0]["name"], "हावड़ा ब्रिज")
        self.assertEqual(
            passage_omissions("फिर तमिलनाडु के चेन्नई पर नज़र जाती है, जो बंगाल की खाड़ी के किनारे बसा है।", [])[1][0]["name"],
            "बंगाल की खाड़ी",
        )
        self.assertTrue(warnings)
        warnings, omitted = passage_omissions(
            "पंजाब के अमृतसर में स्वर्ण मंदिर शहर की आध्यात्मिक पहचान का प्रतीक है।",
            [],
        )
        self.assertEqual(omitted[0]["name"], "स्वर्ण मंदिर")
        self.assertTrue(warnings)
        self.assertFalse(passage_omissions("पंजाब के अमृतसर में स्वर्ण मंदिर है।", ["स्वर्ण मंदिर"])[1])
        bay_only = apply_feature_policy([{
            "status": "not_found",
            "reason": "No exact canonical name or alias matched.",
            "requested": {"name": "बंगाल की खाड़ी"},
        }])
        self.assertEqual(bay_only["status"], "review")
        missing_city = apply_feature_policy([{
            "status": "not_found",
            "reason": "No exact canonical name or alias matched.",
            "requested": {"name": "चेन्नई", "level": "city"},
        }])
        self.assertEqual(missing_city["status"], "blocked")
        peak = apply_feature_policy([
            city,
            {
                "status": "not_found",
                "reason": "No exact canonical name or alias matched.",
                "requested": {"name": "कंचनजंगा", "level": None},
            },
        ])
        self.assertEqual(peak["status"], "ready")
        self.assertEqual(peak["omitted_features"][0]["name"], "कंचनजंगा")

    def test_production_tamil_nadu_and_chennai_stay_distinct(self):
        from map_story.catalog import ACTIVE_PATH
        if not ACTIVE_PATH.is_file():
            self.skipTest("production catalogue is not installed")
        state = lookup("तमिलनाडु", level="state", catalog_path=ACTIVE_PATH)
        self.assertEqual(state["status"], "resolved", state)
        self.assertEqual(state["place"]["id"], "gb-adm1-IN-TN")
        city = lookup("चेन्नई", state="तमिलनाडु", level="city", catalog_path=ACTIVE_PATH)
        district = lookup("चेन्नई", state="तमिलनाडु", level="district", catalog_path=ACTIVE_PATH)
        self.assertEqual(city["status"], "resolved", city)
        self.assertEqual(city["place"]["id"], "gn-1264527")
        self.assertEqual(city["place"]["representation"], "point")
        self.assertEqual(district["status"], "resolved", district)
        self.assertNotEqual(district["place"]["id"], city["place"]["id"])
        self.assertEqual(district["place"]["level"], "district")
        both = lookup("चेन्नई", state="तमिलनाडु", catalog_path=ACTIVE_PATH)
        self.assertEqual(both["status"], "ambiguous")

    def test_concurrent_job_directories_stay_separate(self):
        one = Path(self.tmp.name) / "job-a"
        two = Path(self.tmp.name) / "job-b"
        self.assertNotEqual(contained_dir(one, "clip_01"), contained_dir(two, "clip_01"))
        with self.assertRaises(ValueError):
            contained_dir(one, "../clip_01")


if __name__ == "__main__":
    unittest.main()
