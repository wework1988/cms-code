#!/usr/bin/env python3
"""Hierarchy allocation is geographic, not tied to one city name."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from map_story.compile import compile_resolved_plan  # noqa: E402
from map_story.geo import resolve_plan_places  # noqa: E402
from map_story.hierarchy import HierarchyPlanError, allocate_focus_stages, merge_verified_ancestors  # noqa: E402
from map_story.planner import golden_gorakhpur_plan  # noqa: E402
from map_story.sequence import accept_focus_plan, build_focus_plan  # noqa: E402


def _card(pid, name, level, parent=None, role="subject", representation="polygon"):
    return {
        "id": pid,
        "name": name,
        "level": level,
        "parent_id": parent,
        "role": role,
        "representation": representation,
    }


def _frames(subjects, orientations, target):
    stages, report = allocate_focus_stages(subjects, orientations, target)
    return [card["id"] for _kind, card in stages], report


class HierarchyAllocationTests(unittest.TestCase):
    def test_city_with_state_and_district_uses_three_levels_not_a_repeated_zoom(self):
        """Same shape as a city inside a district inside a state inside a country."""
        country = _card("country", "Country", "country", role="orientation")
        state = _card("state", "State", "state", "country", role="orientation")
        district = _card("district", "District", "district", "state", role="orientation")
        city = _card("city", "City", "city", "district", representation="point")
        frames, report = _frames([city], [country, state, district], 3)
        self.assertEqual(frames[:3], ["country", "state", "city"])
        self.assertEqual(report["dropped_optional_levels"], ["district"])
        self.assertNotEqual(frames[1], frames[2])

    def test_four_stages_keep_the_district(self):
        country = _card("country", "Country", "country", role="orientation")
        state = _card("state", "State", "state", "country", role="orientation")
        district = _card("district", "District", "district", "state", role="orientation")
        city = _card("city", "City", "city", "district", representation="point")
        frames, report = _frames([city], [country, state, district], 4)
        self.assertEqual(frames, ["country", "state", "district", "city"])
        self.assertEqual(report["dropped_optional_levels"], [])

    def test_two_cities_share_country_and_state(self):
        country = _card("country", "Country", "country", role="orientation")
        state = _card("state", "State", "state", "country", role="orientation")
        first = _card("city-a", "First", "city", "state", representation="point")
        second = _card("city-b", "Second", "city", "state", representation="point")
        frames, _report = _frames([first, second], [country, state], 4)
        self.assertEqual(frames, ["country", "state", "city-a", "city-b"])

    def test_city_state_does_not_invent_a_state(self):
        country = _card("country", "Country", "country", role="orientation")
        city = _card("city", "Capital", "city", "country", representation="point")
        frames, _report = _frames([city], [country], 3)
        self.assertEqual(frames[0], "country")
        self.assertEqual(frames[1], "city")
        self.assertNotIn("state", frames)

    def test_missing_parent_is_not_invented(self):
        city = _card("city", "Island City", "city", parent="missing-country", representation="point")
        frames, _report = _frames([city], [], 3)
        self.assertEqual(frames, ["city", "city", "city"])
        self.assertEqual(len(set(frames)), 1)

    def test_overflow_requests_repair_instead_of_dropping_a_target(self):
        country = _card("country", "Country", "country", role="orientation")
        cities = []
        orientations = [country]
        for index in range(3):
            state = _card(f"state-{index}", f"State {index}", "state", "country", role="orientation")
            city = _card(f"city-{index}", f"City {index}", "city", state["id"], representation="point")
            orientations.append(state)
            cities.append(city)
        with self.assertRaises(HierarchyPlanError):
            allocate_focus_stages(cities, orientations, 3)

    def test_model_plan_is_reallocated_and_labels_are_unique(self):
        plan = {
            "schema_version": "1.0",
            "type": "map_focus_sequence",
            "duration_seconds": 14,
            "language": "en",
            "style": "documentary_relief_bold",
            "places": [
                {"id": "country", "name": "Country", "level": "country", "parent": None, "role": "orientation"},
                {"id": "state", "name": "State", "level": "state", "parent": "country", "role": "orientation"},
                {"id": "district", "name": "District", "level": "district", "parent": "state", "role": "orientation"},
                {"id": "city", "name": "City", "level": "city", "parent": "district", "role": "subject"},
            ],
            "shots": [
                {
                    "id": "a",
                    "start": 0,
                    "end": 4,
                    "frame": "country",
                    "actions": [{"type": "zoom_to_boundary", "place": "country", "padding": 0.1}],
                },
                {
                    "id": "b",
                    "start": 4,
                    "end": 9,
                    "frame": "city",
                    "actions": [
                        {"type": "zoom_to_boundary", "place": "city", "padding": 0.16},
                        {"type": "show_marker", "place": "city", "color": "#FFF400", "size": 8, "pulse": False},
                        {"type": "show_label", "place": "city", "text": "City"},
                    ],
                },
                {
                    "id": "c",
                    "start": 9,
                    "end": 14,
                    "frame": "city",
                    "actions": [
                        {"type": "zoom_to_boundary", "place": "city", "padding": 0.18},
                        {"type": "show_label", "place": "city", "text": "City"},
                    ],
                },
            ],
        }
        accepted = accept_focus_plan(
            plan,
            {
                "language": "en",
                "target_focus_count": 3,
                "narration_unit_count": 1,
                "duration_seconds": 14,
            },
            "documentary_relief_bold",
        )
        frames = [shot["frame"] for shot in accepted["shots"]]
        self.assertEqual(frames, ["country", "state", "city"])
        labels = [
            action["place"]
            for shot in accepted["shots"]
            for action in shot["actions"]
            if action.get("type") == "show_label"
        ]
        self.assertEqual(len(labels), len(set(labels)))
        self.assertIn("state", labels)
        self.assertEqual(labels.count("city"), 1)

    def test_omitted_parent_is_restored_from_verified_summaries(self):
        """A city with parent null still opens country, then state, then city."""
        plan = {
            "schema_version": "1.0",
            "type": "map_focus_sequence",
            "duration_seconds": 14,
            "language": "hi",
            "style": "midnight_amber",
            "places": [
                {"id": "ne-adm0-ind", "name": "India", "level": "country", "parent": None, "role": "orientation"},
                {"id": "gn-1254163", "name": "Thiruvananthapuram", "level": "city", "parent": None, "role": "subject"},
            ],
            "shots": [
                {
                    "id": "focus_1",
                    "start": 0,
                    "end": 14,
                    "frame": "gn-1254163",
                    "actions": [{"type": "zoom_to_boundary", "place": "gn-1254163", "padding": 0.16}],
                },
            ],
        }
        summaries = [
            {"id": "gn-1254163", "name": "Thiruvananthapuram", "level": "city", "parent_id": "district", "representation": "point"},
            {"id": "district", "name": "Thiruvananthapuram", "level": "district", "parent_id": "gb-adm1-IN-KL"},
            {"id": "gb-adm1-IN-KL", "name": "Kerala", "level": "state", "parent_id": "ne-adm0-ind"},
            {"id": "ne-adm0-ind", "name": "India", "level": "country", "parent_id": None},
        ]
        accepted = accept_focus_plan(
            plan,
            {
                "language": "hi",
                "target_focus_count": 3,
                "narration_unit_count": 1,
                "duration_seconds": 14,
            },
            "midnight_amber",
            None,
            summaries,
        )
        frames = [shot["frame"] for shot in accepted["shots"]]
        self.assertEqual(frames, ["ne-adm0-ind", "gb-adm1-IN-KL", "gn-1254163"])
        self.assertEqual(accepted["hierarchy"]["dropped_optional_levels"], ["district"])

    def test_unverified_summary_parent_is_not_invented(self):
        plan = {
            "places": [
                {"id": "city", "name": "Island City", "level": "city", "parent": None, "role": "subject"},
            ],
        }
        summaries = [
            {"id": "city", "name": "Island City", "level": "city", "parent_id": "missing-country", "representation": "point"},
        ]
        merged = merge_verified_ancestors(plan, summaries)
        self.assertIsNone(merged["places"][0].get("parent"))
        self.assertEqual([place["id"] for place in merged["places"]], ["city"])

    def test_compiled_labels_merge_duplicate_place_identity(self):
        plan = golden_gorakhpur_plan(18)
        plan["style"] = "documentary_relief_bold"
        plan["shots"][2]["actions"].append({"type": "show_label", "place": "uttar_pradesh", "text": "उत्तर प्रदेश"})
        places = resolve_plan_places(plan)
        resolved = compile_resolved_plan(plan, places, job_settings={})
        up_labels = [label for label in resolved["labels"] if label["place"] == "uttar_pradesh"]
        self.assertEqual(len(up_labels), 1)

    def test_build_focus_plan_records_hierarchy(self):
        country = _card("country", "Country", "country", role="orientation")
        state = _card("state", "State", "state", "country", role="orientation")
        city = _card("city", "City", "city", "state", representation="point")
        plan = build_focus_plan(
            [city, country, state],
            language="en",
            style="documentary_relief_bold",
            target_focus_count=3,
            narration_unit_count=1,
            counting_method="sentences",
            focus_decision="test",
            duration_seconds=14,
        )
        self.assertEqual(plan["hierarchy"]["stage_ids"][:3], ["country", "state", "city"])
        self.assertEqual(plan["hierarchy"]["parent_before_close"]["city"], "state")


if __name__ == "__main__":
    unittest.main()
