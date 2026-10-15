"""Timeline schema, dispatch, and layout tests. DeepSeek is not called."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB))

from animation_core.jobs import contained_dir  # noqa: E402
from animation_core.outputs import replace_verified  # noqa: E402
from animation_core.registry import UnsupportedAnimationType, canonical_type  # noqa: E402
from animation_types.timeline.compile import compile_plan, reveal_times  # noqa: E402
from animation_types.timeline.planner import (  # noqa: E402
    PLAN_RULES,
    plan_from_passage,
    select_local,
    select_with_model,
)
from animation_types.timeline.renderer import TimelineRenderer  # noqa: E402
from animation_types.timeline.runner import run_job  # noqa: E402
from animation_types.timeline.schema import TimelineValidationError, validate_semantic_plan  # noqa: E402
from animation_types.timeline.textutil import TextLayoutError, shape  # noqa: E402

SAMPLE = (LAB / "examples" / "timeline-story.txt").read_text(encoding="utf-8")
UNDATED = "पहले संगठन का काम शुरू हुआ।\nफिर पार्टी में जिम्मेदारियाँ आईं।\nबाद में राज्य की राजनीति संभाली।\n"
NONE = "यह शहर नदी के किनारे बसा है और यहाँ बाज़ार शाम को सजता है।\n"
FOUR = (
    "वर्ष 1998 में संगठन की पहली नियमित बैठक शुरू हुई।\n"
    "वर्ष 2001 में प्रदेश स्तर पर जिम्मेदारी सौंपी गई।\n"
    "वर्ष 2014 में राष्ट्रीय नेतृत्व की शपथ ली गई।\n"
    "वर्ष 2024 में तीसरा कार्यकाल फिर से शुरू हुआ।\n"
)


def _plan(passage: str = SAMPLE, duration: float = 18):
    return plan_from_passage(passage, language="hi", duration_seconds=duration)


class TimelineTests(unittest.TestCase):
    def test_registry_and_legacy_map_default(self):
        self.assertEqual(canonical_type(None), "map")
        self.assertEqual(canonical_type("map"), "map")
        self.assertEqual(canonical_type("timeline"), "timeline")
        with self.assertRaises(UnsupportedAnimationType):
            canonical_type("not_a_real_animation_type")

    def test_timeline_import_does_not_load_geography(self):
        code = (
            "import sys\n"
            f"sys.path.insert(0, {str(LAB)!r})\n"
            "import animation_types.timeline.runner\n"
            "assert 'shapely' not in sys.modules\n"
            "assert 'map_story.catalog' not in sys.modules\n"
            "print('ok')\n"
        )
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)

    def test_sample_has_three_years_and_no_invented_fourth(self):
        plan = _plan()
        self.assertEqual([event["year"] for event in plan["events"]], [2001, 2014, 2024])
        self.assertEqual([event["date_label"] for event in plan["events"]], ["2001", "2014", "2024"])
        self.assertEqual(len(plan["events"]), 3)
        self.assertIn("26 मई 2014", plan["events"][1]["evidence_quote"])
        self.assertNotIn("मई", plan["events"][1]["date_label"])
        compiled = compile_plan(plan, SAMPLE, duration_seconds=18)
        self.assertGreater(compiled["overview_start"], compiled["events"][-1]["reveal"])
        self.assertLess(compiled["events"][-1]["reveal"], 18)
        self.assertIn("not proportional", compiled["spacing_note"])

    def test_undated_keeps_narrative_order(self):
        plan = _plan(UNDATED)
        self.assertEqual([event["year"] for event in plan["events"]], [None, None, None])
        self.assertEqual([event["date_label"] for event in plan["events"]], ["पहले", "फिर", "बाद में"])
        compiled = compile_plan(plan, UNDATED, duration_seconds=18)
        self.assertIn("narrative", compiled["spacing_note"])

    def test_no_suitable_chronology(self):
        selection = select_local(NONE, max_clips=3, duration_seconds=18, language="hi")
        self.assertEqual(selection["clips"], [])

    def test_two_events_are_rejected(self):
        short = "वर्ष 2001 में काम शुरू हुआ।\nवर्ष 2014 में शपथ ली।\n"
        with self.assertRaises(TimelineValidationError):
            plan_from_passage(short, language="hi", duration_seconds=18)

    def test_four_longer_captions(self):
        plan = _plan(FOUR)
        self.assertEqual(len(plan["events"]), 4)
        self.assertTrue(all(len(event["caption"]) > 20 for event in plan["events"]))
        compiled = compile_plan(plan, FOUR, duration_seconds=18)
        renderer = TimelineRenderer(compiled)
        self.assertEqual(len(renderer.assets["labels"]), 4)

    def test_invented_year_and_substring_year(self):
        plan = _plan()
        plan["events"][0]["year"] = 1999
        plan["events"][0]["date_label"] = "1999"
        with self.assertRaises(TimelineValidationError):
            validate_semantic_plan(plan, SAMPLE, duration_seconds=18)
        copied = json.loads(json.dumps(plan))
        copied["events"][0]["evidence_quote"] = "संख्या 120014 दर्ज हुई"
        copied["events"][0]["year"] = 2001
        copied["events"][0]["date_label"] = "2001"
        passage = "संख्या 120014 दर्ज हुई\n" + "\n".join(event["evidence_quote"] for event in copied["events"][1:])
        with self.assertRaises(TimelineValidationError) as caught:
            validate_semantic_plan(copied, passage, duration_seconds=18)
        self.assertIn("2001", str(caught.exception))

    def test_years_must_move_forward(self):
        plan = _plan()
        plan["events"][0]["year"] = 2020
        plan["events"][0]["date_label"] = "2020"
        plan["events"][0]["evidence_quote"] = "वर्ष 2020 में नरेंद्र मोदी गुजरात के मुख्यमंत्री बने।"
        with self.assertRaises(TimelineValidationError):
            validate_semantic_plan(plan, plan["events"][0]["evidence_quote"] + SAMPLE, duration_seconds=18)

    def test_exact_date_label_rejected(self):
        plan = _plan()
        plan["events"][1]["date_label"] = "26 मई 2014"
        with self.assertRaises(TimelineValidationError):
            validate_semantic_plan(plan, SAMPLE, duration_seconds=18)

    def test_reveal_times_leave_a_final_hold(self):
        times, overview = reveal_times(3, 18, 4.5)
        self.assertEqual(len(times), 3)
        self.assertLess(times[-1], overview)
        self.assertGreater(18 - overview, 4)
        self.assertLess(times[-1] - times[0], 18)

    def test_hindi_text_wraps_inside_a_box(self):
        image = shape("गुजरात के मुख्यमंत्री बने और फिर राष्ट्रीय भूमिका संभाली", 32, 280, 150)
        self.assertGreater(image.height, 40)
        with self.assertRaises(TextLayoutError):
            shape("यह वाक्य " * 30, 32, 280, 80)

    def test_frame_size_and_distinct_milestones(self):
        compiled = compile_plan(_plan(), SAMPLE, duration_seconds=18)
        renderer = TimelineRenderer(compiled)
        first = renderer.frame(compiled["events"][0]["reveal"] + 0.8)
        overview = renderer.frame(compiled["overview_start"] + 0.4)
        self.assertEqual(first.size, (1920, 1080))
        self.assertNotEqual(first.tobytes(), overview.tobytes())

    def test_deepseek_payload_has_no_catalogue(self):
        seen = {}

        def client(payload):
            seen["payload"] = payload
            passage = SAMPLE.strip()
            body = {
                "clips": [{
                    "title": "मुख्य वर्ष",
                    "reason": "These three years are the chronology.",
                    "source_passage": passage,
                    "beats": ["मुख्यमंत्री", "शपथ", "तीसरा कार्यकाल"],
                    "duration_seconds": 18,
                }],
            }
            return {"choices": [{"message": {"content": json.dumps(body, ensure_ascii=False)}}]}

        select_with_model(
            SAMPLE,
            master_prompt="Editorial only.",
            max_clips=3,
            duration_seconds=18,
            language="hi",
            key="test",
            model="mock",
            client=client,
        )
        encoded = json.dumps(seen["payload"], ensure_ascii=False)
        self.assertNotIn("geojson", encoded.lower())
        self.assertNotIn("shapely", encoded.lower())
        self.assertIn("Editorial only.", encoded)
        self.assertIn("do not include reveal times", PLAN_RULES.lower())

    def test_saved_plan_skips_the_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp)
            passage = SAMPLE.strip()
            semantic = _plan(passage)
            clip_dir = job / "clips" / "clip_01"
            clip_dir.mkdir(parents=True)
            (clip_dir / "semantic-plan.json").write_text(json.dumps(semantic), encoding="utf-8")
            selection = {
                "clips": [{
                    "id": "clip_01",
                    "title": semantic["title"],
                    "reason": "years",
                    "source_passage": passage,
                    "offset_start": 0,
                    "offset_end": len(passage),
                    "beats": [event["caption"] for event in semantic["events"]],
                    "duration_seconds": 18,
                }],
            }
            (job / "selection.json").write_text(json.dumps(selection), encoding="utf-8")
            snapshot = {
                "animation_type": "timeline",
                "script": passage,
                "prompt_id": 7,
                "master_prompt": "Timeline editorial prompt",
                "language": "hi",
                "duration_seconds": 18,
                "max_clips": 3,
                "planner": "deepseek",
                "job_id": "timeline-test",
            }
            (job / "snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")

            def client(_payload):
                raise AssertionError("DeepSeek should not be called when a valid plan is saved")

            status = run_job(job / "snapshot.json", client=client, stop_before_render=True)
            self.assertEqual(status, 0)
            progress = json.loads((job / "progress.json").read_text(encoding="utf-8"))
            self.assertEqual(progress["prompt_id"], 7)
            self.assertEqual(progress["animation_type"], "timeline")
            self.assertTrue((clip_dir / "compiled-plan.json").is_file())
            self.assertEqual(progress["clips"][0]["milestones"][0]["date_label"], "2001")

    def test_concurrent_clip_directories_stay_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = contained_dir(Path(tmp) / "job-a", "clip_01")
            second = contained_dir(Path(tmp) / "job-b", "clip_01")
            self.assertNotEqual(first, second)
            with self.assertRaises(ValueError):
                contained_dir(Path(tmp) / "job-a", "../clip_01")

    def test_failed_verification_keeps_the_previous_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            destination = folder / "timeline.mp4"
            destination.write_bytes(b"previous-good-video")
            partial = folder / "timeline.partial.mp4"
            partial.write_bytes(b"broken")

            def verify(_path):
                raise RuntimeError("decode failed")

            with self.assertRaises(RuntimeError):
                replace_verified(partial, destination, verify)
            self.assertEqual(destination.read_bytes(), b"previous-good-video")
            self.assertFalse(partial.exists())


if __name__ == "__main__":
    unittest.main()
