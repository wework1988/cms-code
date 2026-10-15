"""Map appearance templates stay independent of camera planning."""
from __future__ import annotations

import copy
import unittest

from map_story.compile import compile_resolved_plan
from map_story.geo import resolve_plan_places
from map_story.restyle import camera_signature, restyle_plan
from map_story.schema import SUPPORTED_STYLES, validate_semantic_plan
from map_story.sequence import apply_palette
from map_story.themes import THEMES, apply_token_overrides, theme_for, theme_hash
from tests.test_map_story import golden_gorakhpur_plan


class ThemeContractTests(unittest.TestCase):
    def test_default_tokens_match_the_shipped_documentary_look(self):
        theme = theme_for("documentary_relief_bold")
        self.assertEqual(theme["ocean"], "#103E4A")
        self.assertEqual(theme["fill"]["mode"], "terrain_color")
        self.assertEqual(theme["palette"]["yellow"], "#D4B300")
        self.assertEqual(theme["palette"]["country_red"], "#A32320")
        self.assertEqual(theme["marker"]["shape"], "glow_dot")
        self.assertEqual(theme["capabilities"]["camera_profile"], "documentary")
        self.assertEqual(theme["theme_hash"], theme_hash(theme))

    def test_custom_override_does_not_mutate_the_builtin(self):
        before = copy.deepcopy(THEMES["clean_atlas"]["tokens"]["highlights"]["primaryRegion"])
        custom = apply_token_overrides("clean_atlas", {"highlights": {"primaryRegion": "#112233"}}, theme_id="custom_demo")
        self.assertEqual(THEMES["clean_atlas"]["tokens"]["highlights"]["primaryRegion"], before)
        self.assertEqual(custom["tokens"]["highlights"]["primaryRegion"], "#112233")
        self.assertNotEqual(custom["theme_hash"], theme_for("clean_atlas")["theme_hash"])
        again = theme_for("clean_atlas")
        again["ocean"] = "#000000"
        self.assertEqual(theme_for("clean_atlas")["ocean"], "#DDECF3")

    def test_new_themes_keep_documentary_camera_and_replace_baked_colours(self):
        plan = golden_gorakhpur_plan(18)
        plan["style"] = "documentary_relief_bold"
        places = resolve_plan_places(plan)
        baseline = compile_resolved_plan(plan, places)
        for style in ("clean_atlas", "midnight_amber", "archival_earth"):
            self.assertIn(style, SUPPORTED_STYLES)
            themed = copy.deepcopy(plan)
            themed["style"] = style
            themed["shots"][1]["actions"].append({
                "type": "highlight",
                "place": themed["places"][0]["id"],
                "color": "#FF00AA",
                "fill_opacity": 0.2,
            })
            apply_palette(themed, style)
            colours = [
                action["color"]
                for shot in themed["shots"]
                for action in shot["actions"]
                if action.get("type") == "highlight"
            ]
            self.assertNotIn("#FF00AA", colours)
            validate_semantic_plan(themed, duration_seconds=18)
            compiled = compile_resolved_plan(themed, places, job_settings={"map_theme": theme_for(style)})
            self.assertEqual(camera_signature(compiled), camera_signature(baseline))
            self.assertEqual(compiled["duration"], baseline["duration"])
            self.assertEqual(len(compiled["camera"]["keyframes"]), len(baseline["camera"]["keyframes"]))
            self.assertEqual(compiled["theme"]["capabilities"]["camera_profile"], "documentary")
            self.assertNotEqual(compiled["theme"]["palette"]["yellow"], baseline["theme"]["palette"]["yellow"])

    def test_user_colour_is_kept(self):
        plan = golden_gorakhpur_plan(18)
        plan["style"] = "clean_atlas"
        action = plan["shots"][1]["actions"][0]
        action["color"] = "#ABCDEF"
        action["color_source"] = "user"
        apply_palette(plan, "clean_atlas")
        self.assertEqual(action["color"], "#ABCDEF")

    def test_legacy_job_without_a_theme_snapshot_still_compiles(self):
        plan = golden_gorakhpur_plan(18)
        plan["style"] = "documentary_relief_bold"
        places = resolve_plan_places(plan)
        compiled = compile_resolved_plan(plan, places, job_settings={})
        self.assertEqual(compiled["theme"]["id"], "documentary_relief_bold")
        self.assertEqual(compiled["camera"]["keyframes"][0]["pitch"], 0)

    def test_restyle_does_not_need_a_model_client(self):
        plan = golden_gorakhpur_plan(18)
        plan["style"] = "documentary_relief_bold"
        places = resolve_plan_places(plan)
        resolved = compile_resolved_plan(plan, places)
        themed = restyle_plan(plan, resolved, theme_for("midnight_amber"))
        self.assertFalse(themed["restyle"]["deepseek"])
        self.assertEqual(camera_signature(themed), camera_signature(resolved))
        self.assertEqual(themed["theme"]["id"], "midnight_amber")

    def test_invalid_colour_is_rejected(self):
        with self.assertRaises(ValueError):
            apply_token_overrides("clean_atlas", {"highlights": {"primaryRegion": "red"}})


if __name__ == "__main__":
    unittest.main()
