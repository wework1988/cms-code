"""Documentary plan checks. Rendering is covered by the sample MP4s, not by these tests."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB))

from animation_core.jobs import atomic_write_json, contained_dir, overall_status  # noqa: E402
from animation_core.outputs import decoded_frame_count, replace_verified  # noqa: E402
from animation_core.registry import canonical_type  # noqa: E402
from animation_types.before_after.schema import validate_semantic_plan as validate_compare  # noqa: E402
from animation_types.data_animations.planner import sample_plan as data_sample  # noqa: E402
from animation_types.data_animations.schema import validate_semantic_plan as validate_data  # noqa: E402
from animation_types.documentary.common import NeedsAssets, NeedsReview, PlanError  # noqa: E402
from animation_types.documentary.runner import run_job  # noqa: E402
from animation_types.document_highlighting.schema import validate_semantic_plan as validate_document  # noqa: E402
from animation_types.photo_sequences.planner import PASSAGE as PHOTO_PASSAGE  # noqa: E402
from animation_types.photo_sequences.planner import plan_clip as plan_photo  # noqa: E402
from animation_types.relationship_diagrams.planner import sample_plan as relationship_sample  # noqa: E402
from animation_types.relationship_diagrams.schema import validate_semantic_plan as validate_relationship  # noqa: E402
from animation_types.storyboard_reconstructions.planner import plan_clip as plan_storyboard  # noqa: E402
from animation_types.text_highlighting.compile import compile_plan as compile_text  # noqa: E402
from animation_types.text_highlighting.planner import PASSAGE, sample_plan  # noqa: E402
from animation_types.text_highlighting.schema import validate_semantic_plan as validate_text  # noqa: E402


class DocumentaryPlanTests(unittest.TestCase):
    def test_registry_lists_verified_types(self):
        for name in (
            "map",
            "timeline",
            "text_highlighting",
            "photo_sequences",
            "before_after",
            "document_highlighting",
            "relationship_diagrams",
            "data_animations",
            "storyboard_reconstructions",
        ):
            self.assertEqual(canonical_type(name), name)

    def test_text_emphasis_stays_a_phrase(self):
        plan, passage = sample_plan()
        compiled = compile_text(plan, passage, duration_seconds=12)
        again = compile_text(plan, passage, duration_seconds=12)
        self.assertEqual(compiled["cache_key"], again["cache_key"])
        emphasis = compiled["lines"][0]["emphasis"]
        self.assertEqual(emphasis, "एक दिन में नहीं")
        self.assertIn(emphasis, compiled["lines"][0]["text"])
        self.assertGreater(len(emphasis), 1)
        self.assertNotIsInstance(compiled["lines"][0]["text"], list)

    def test_named_quotation_requires_the_name_in_the_passage(self):
        plan, passage = sample_plan()
        plan["template_id"] = "quote_annotation"
        plan["speaker"] = "कोई unnamed व्यक्ति नहीं"
        with self.assertRaises(PlanError):
            validate_text(plan, passage)

    def test_missing_photo_is_needs_assets(self):
        with self.assertRaises(NeedsAssets):
            plan_photo(
                {"planner": "local", "duration_seconds": 12, "language": "hi", "inputs": {}},
                {"source_passage": PHOTO_PASSAGE, "title": "तस्वीरें"},
            )

    def test_unsupported_relationship_is_review(self):
        plan, passage = relationship_sample()
        plan["edges"][0]["evidence_quote"] = "बाढ़ कोष ने तट की मरम्मत कराई।"
        with self.assertRaises(NeedsReview):
            validate_relationship(plan, passage)

    def test_split_of_different_viewpoints_is_rejected(self):
        from animation_types.before_after.planner import sample_plan as compare_sample
        plan, passage = compare_sample()
        plan["template_id"] = "split_divider"
        with self.assertRaises(PlanError):
            validate_compare(plan, passage)

    def test_invented_date_is_rejected(self):
        from animation_types.before_after.planner import sample_plan as compare_sample
        plan, passage = compare_sample()
        plan["before"]["date"] = "1999"
        with self.assertRaises(PlanError):
            validate_compare(plan, passage)

    def test_scan_is_not_pdf_text(self):
        plan, _passage = __import__(
            "animation_types.document_highlighting.planner", fromlist=["sample_plan"]
        ).sample_plan()
        plan["asset"]["kind"] = "scan"
        plan["asset"]["text_source"] = "pdf_text"
        plan["asset"]["path"] = str(LAB / "examples" / "documentary" / "assets" / "document-scan.png")
        with self.assertRaises(NeedsReview):
            validate_document(plan, "यह पृष्ठ एक सिंथेटिक प्रदर्शन है।\nThe river changed course after the flood.\nहाशिये की टिप्पणी उसी वाक्य को दिखाती है।")

    def test_invalid_number_and_percentage(self):
        plan, passage = data_sample()
        plan["series"][0]["value"] = float("nan")
        with self.assertRaises(PlanError):
            validate_data(plan, passage)
        plan, passage = data_sample()
        plan["unit"] = "%"
        with self.assertRaises(PlanError):
            validate_data(plan, passage)

    def test_value_must_be_its_own_number(self):
        plan, passage = data_sample()
        plan["series"][0]["value"] = 20
        plan["series"][0]["evidence_quote"] = "पहले स्तर 2 मीटर था।"
        with self.assertRaises(PlanError):
            validate_data(plan, passage)

    def test_flow_is_not_launched(self):
        with self.assertRaises(NeedsAssets):
            plan_storyboard(
                {"planner": "local", "duration_seconds": 12, "inputs": {"provider": "flow", "images": []}},
                {"source_passage": PASSAGE, "title": "दृश्य"},
            )

    def test_missing_assets_do_not_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp)
            snapshot = {
                "animation_type": "photo_sequences",
                "planner": "local",
                "script": PHOTO_PASSAGE,
                "duration_seconds": 12,
                "language": "hi",
                "max_clips": 1,
                "inputs": {},
            }
            path = job / "snapshot.json"
            path.write_text(json.dumps(snapshot), encoding="utf-8")
            code = run_job(path)
            progress = json.loads((job / "progress.json").read_text(encoding="utf-8"))
            self.assertEqual(code, 0)
            self.assertEqual(progress["status"], "needs_assets")
            self.assertFalse((job / "clips" / "clip_01" / "sample.mp4").exists())

    def test_frame_count_uses_the_last_progress_line(self):
        log = "frame=  12\nframe= 360\n"
        self.assertEqual(decoded_frame_count(log), 360)

    def test_failed_verify_keeps_the_previous_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            good = folder / "sample.mp4"
            good.write_bytes(b"verified-video")
            partial = folder / "partial.mp4"
            partial.write_bytes(b"bad")

            def reject(_path):
                raise RuntimeError("decode failed")

            with self.assertRaises(RuntimeError):
                replace_verified(partial, good, reject)
            self.assertEqual(good.read_bytes(), b"verified-video")
            self.assertFalse(partial.exists())

    def test_concurrent_progress_writes_do_not_share_a_temp_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            errors = []

            def write(index: int) -> None:
                try:
                    atomic_write_json(folder / f"job-{index}.json", {"index": index})
                except Exception as error:  # noqa: BLE001
                    errors.append(error)

            threads = [threading.Thread(target=write, args=(index,)) for index in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(errors, [])
            self.assertEqual(json.loads((folder / "job-3.json").read_text())["index"], 3)
            left = contained_dir(folder / "a", "clip_01")
            right = contained_dir(folder / "b", "clip_01")
            self.assertNotEqual(left, right)

    def test_uniform_review_status_is_not_collapsed(self):
        status, _message = overall_status([
            {"status": "needs_review"},
            {"status": "needs_review"},
        ])
        self.assertEqual(status, "needs_review")


if __name__ == "__main__":
    unittest.main()
