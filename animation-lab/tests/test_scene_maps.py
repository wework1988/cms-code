"""Scene-breakdown map selection, publication, and job isolation."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from map_story.render_slot import renderer_slot  # noqa: E402
from map_story.scene_publish import StalePublishError, publish_scene_mp4  # noqa: E402
from map_story.scene_run import run_saved_scene_job  # noqa: E402
from map_story.scene_select import SceneSelectionIncomplete, select_suitable_scenes  # noqa: E402
from map_story.scene_source import (  # noqa: E402
    SceneSourceError,
    association_ok,
    generation_key,
    load_scene_breakdown,
    load_scene_file,
    presentation_cache_key,
    selection_cache_key,
)
from map_story.scene_timing import resolve_scene_timing, timing_update_available  # noqa: E402

REAL_SCENE = ROOT.parent / "cms-generate-stories/general/171-sample-test-full-story-genertion/scenes/scene.txt"


def _scene_block(number: int, text: str) -> str:
    return f"--- Scene {number} / ~12 ---\nHindi line:\n{text}\n"


def _document(numbers, text="यह एक परीक्षण दृश्य है।"):
    body = "\n".join(_scene_block(number, f"{text} {number}") for number in numbers)
    return load_scene_breakdown(body)


def _accept_numbers(good: set[int]):
    def complete(payload):
        decisions = []
        for candidate in payload["candidates"]:
            number = candidate["scene_number"]
            suitable = number in good
            decisions.append({
                "scene_id": candidate["scene_id"],
                "suitable": suitable,
                "reason": "A map shows where this happens." if suitable else "The place is only incidental.",
                "passage": candidate["text"] if suitable else "",
                "places": [{"name": "गुजरात", "level": "state", "country": "भारत"}] if suitable else [],
                "purpose": "Show the state." if suitable else "",
            })
        return {"decisions": decisions}
    return complete


def _fake_mp4(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 1200)


class SceneParseTests(unittest.TestCase):
    def test_production_scene_file_keeps_original_numbers(self):
        document = load_scene_file(REAL_SCENE)
        self.assertGreaterEqual(document.scene_count, 10)
        self.assertEqual(document.scenes[0].number, 1)
        self.assertIn("वडनगर", document.scenes[1].text)
        self.assertEqual(document.parser_version, "2026.10-scene-txt-v1")

    def test_two_hundred_noncontiguous_scenes(self):
        numbers = list(range(1, 219))
        numbers[11] = 300
        document = _document(numbers)
        self.assertEqual(document.scene_count, 218)
        self.assertEqual(document.scenes[11].number, 300)
        self.assertEqual(document.scenes[11].scene_id, "scene-300")

    def test_duplicate_and_malformed_files_are_rejected(self):
        with self.assertRaises(SceneSourceError):
            load_scene_breakdown(_scene_block(3, "एक") + _scene_block(3, "दो"))
        with self.assertRaises(SceneSourceError):
            load_scene_breakdown("")
        with self.assertRaises(SceneSourceError):
            load_scene_breakdown("--- Scene 4 / ~12 ---\nHindi line:\n\n")
        with self.assertRaises(SceneSourceError):
            load_scene_breakdown("just a paragraph without headings")


class SceneSelectionTests(unittest.TestCase):
    def test_first_suitable_scenes_not_the_first_scenes(self):
        numbers = list(range(1, 31))
        good = {3, 8, 15, 16, 22}
        result = select_suitable_scenes(_document(numbers), _accept_numbers(good), limit=3, batch_scenes=10, batch_chars=5000)
        self.assertEqual([item.scene_number for item in result.selected], [3, 8, 15])
        self.assertIn("Scanned", result.progress_message)

    def test_fewer_than_the_limit_stays_fewer(self):
        result = select_suitable_scenes(_document([1, 2, 3, 4]), _accept_numbers({4}), limit=10, batch_scenes=2, batch_chars=5000)
        self.assertEqual([item.scene_number for item in result.selected], [4])

    def test_stop_at_limit_across_batches(self):
        numbers = list(range(1, 219))
        good = set(range(20, 221, 20))
        calls = {"n": 0}

        def complete(payload):
            calls["n"] += 1
            return _accept_numbers(good)(payload)

        result = select_suitable_scenes(_document(numbers), complete, limit=10, batch_scenes=20, batch_chars=100000)
        self.assertEqual([item.scene_number for item in result.selected], list(range(20, 201, 20)))
        self.assertLess(calls["n"], 12)
        self.assertNotIn(1, [item.scene_number for item in result.selected])

    def test_unknown_id_is_repaired_and_a_failed_batch_is_not_unsuitable(self):
        document = _document([3, 12, 19])

        def repair_once(payload):
            if not payload.get("repair"):
                return {"decisions": [{"scene_id": "scene-999", "suitable": True, "reason": "no", "passage": "x"}]}
            return _accept_numbers({12})(payload)

        result = select_suitable_scenes(document, repair_once, limit=10, batch_scenes=10, batch_chars=5000)
        self.assertEqual([item.scene_number for item in result.selected], [12])

        def always_bad(_payload):
            return {"decisions": [{"scene_id": "scene-nope", "suitable": True, "reason": "x", "passage": "x"}]}

        with self.assertRaises(SceneSelectionIncomplete):
            select_suitable_scenes(document, always_bad, limit=10, batch_scenes=1, batch_chars=5000)

    def test_resume_does_not_repeat_completed_batches(self):
        document = _document(list(range(1, 41)))
        calls = {"n": 0}

        def complete(payload):
            calls["n"] += 1
            return _accept_numbers({5, 25})(payload)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scene-scan.json"
            first = select_suitable_scenes(document, complete, limit=10, batch_scenes=10, batch_chars=5000, state_path=path)
            self.assertEqual(calls["n"], 4)
            calls["n"] = 0
            second = select_suitable_scenes(document, complete, limit=10, batch_scenes=10, batch_chars=5000, state_path=path)
            self.assertEqual(calls["n"], 0)
            self.assertEqual([item.scene_number for item in second.selected], [item.scene_number for item in first.selected])

    def test_context_scene_is_not_accepted_until_repaired(self):
        document = _document([1, 2, 3])

        def complete(payload):
            context = payload["context"]
            if context and not payload.get("repair"):
                return {"decisions": [{
                    "scene_id": context[0]["scene_id"],
                    "suitable": True,
                    "reason": "context",
                    "passage": context[0]["text"],
                }]}
            return _accept_numbers({2})(payload)

        result = select_suitable_scenes(document, complete, limit=10, batch_scenes=1, batch_chars=5000)
        self.assertEqual([item.scene_number for item in result.selected], [2])

    def test_long_scene_becomes_one_decision(self):
        text = "गुजरात की यात्रा " + ("शब्द " * 80)
        document = load_scene_breakdown(_scene_block(12, text.strip()))
        calls = {"n": 0}

        def complete(payload):
            calls["n"] += 1
            return _accept_numbers({12})(payload)

        result = select_suitable_scenes(document, complete, limit=10, batch_scenes=12, batch_chars=40, chunk_chars=30)
        self.assertEqual(len(result.selected), 1)
        self.assertEqual(result.selected[0].scene_number, 12)
        self.assertGreater(calls["n"], 1)


class PublishAndJobTests(unittest.TestCase):
    def test_scene_12_publishes_without_touching_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "video").mkdir()
            video = root / "video" / "scene_1.mp4"
            video.write_bytes(b"keep-me")
            rendered = root / "job" / "maplibre.mp4"
            _fake_mp4(rendered)
            published = publish_scene_mp4(root, scene_number=12, rendered=rendered, entry={"scene_id": "scene-12"}, job_created=10)
            self.assertEqual(published.name, "scene_12.mp4")
            self.assertTrue((root / "animation" / "manifest.json").is_file())
            self.assertEqual(video.read_bytes(), b"keep-me")
            with self.assertRaises(StalePublishError):
                publish_scene_mp4(root, scene_number=12, rendered=rendered, entry={"scene_id": "scene-12"}, job_created=5)
            self.assertEqual(published.stat().st_size, rendered.stat().st_size)

    def test_concurrent_manifest_updates_keep_both_scenes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rendered = root / "clip.mp4"
            _fake_mp4(rendered)
            errors = []

            def publish(number, created):
                try:
                    publish_scene_mp4(root, scene_number=number, rendered=rendered, entry={"scene_id": f"scene-{number}"}, job_created=created)
                except Exception as error:  # noqa: BLE001
                    errors.append(error)

            threads = [threading.Thread(target=publish, args=(3, 1)), threading.Thread(target=publish, args=(19, 1))]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(errors, [])
            manifest = json.loads((root / "animation" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(sorted(item["scene_number"] for item in manifest["scenes"]), [3, 19])

    def test_job_failure_does_not_remove_normal_video_and_retry_is_narrow(self):
        document_text = _scene_block(12, "गुजरात का वडनगर।") + _scene_block(19, "दिल्ली में शपथ।")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "video").mkdir()
            normal = root / "video" / "scene_1.mp4"
            normal.write_bytes(b"documentary")
            snapshot = {
                "job_id": "abc",
                "input_mode": "scene_breakdown",
                "scene_source": {"text": document_text, "sha256": load_scene_breakdown(document_text).source_hash},
                "max_selected_scenes": 10,
                "story_root": str(root),
                "duration_seconds": 14,
                "created_unix": 20,
                "language": "hi",
            }
            rendered = {"n": 0}

            def render(clip, clip_dir):
                rendered["n"] += 1
                if clip["scene_number"] == 19 and rendered["n"] < 3:
                    raise RuntimeError("renderer failed")
                path = clip_dir / "maplibre.mp4"
                _fake_mp4(path)
                return {"status": "completed", "video": str(path), "places": [], "warnings": []}

            job = Path(tmp) / "job"
            code = run_saved_scene_job(snapshot, job, complete=_accept_numbers({12, 19}), render_scene=render)
            self.assertEqual(code, 0)
            self.assertEqual(normal.read_bytes(), b"documentary")
            progress = json.loads((job / "progress.json").read_text(encoding="utf-8"))
            by_scene = {item["scene_number"]: item["status"] for item in progress["clips"]}
            self.assertEqual(by_scene[12], "completed")
            self.assertEqual(by_scene[19], "failed")
            before = rendered["n"]
            run_saved_scene_job(snapshot, job, complete=_accept_numbers({12, 19}), render_scene=render, retry_clip="clip_02")
            self.assertEqual(rendered["n"], before + 1)
            self.assertTrue((root / "animation" / "scene_12.mp4").is_file())
            self.assertFalse((root / "animation" / "scene_1.mp4").exists())

    def test_timing_is_provisional_until_a_real_duration_file_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unknown = resolve_scene_timing(root, 12, 14)
            self.assertTrue(unknown["provisional"])
            self.assertIsNone(unknown["placement"])
            audio = root / "audio"
            audio.mkdir()
            (audio / "scene-durations.json").write_text(json.dumps({"scenes": [{"number": 12, "duration_seconds": 9.5}]}), encoding="utf-8")
            known = resolve_scene_timing(root, 12, 14)
            self.assertFalse(known["provisional"])
            self.assertEqual(known["map_duration_seconds"], 9.5)
            self.assertIsNone(known["placement"])
            entry = {"status": "completed", "timing": {"timing_source_hash": known["timing_source_hash"]}}
            self.assertFalse(timing_update_available(entry, root))
            (audio / "scene-durations.json").write_text(json.dumps({"scenes": [{"number": 12, "duration_seconds": 11}]}), encoding="utf-8")
            self.assertTrue(timing_update_available(entry, root))

    def test_revision_keys_and_renumber_mismatch(self):
        left = selection_cache_key(source_hash="a", limit=10, batch_scenes=12, batch_chars=12000)
        self.assertEqual(left, selection_cache_key(source_hash="a", limit=10, batch_scenes=12, batch_chars=12000))
        self.assertNotEqual(
            presentation_cache_key(selection_key=left, prompt_hash="p", theme_hash="theme-a"),
            presentation_cache_key(selection_key=left, prompt_hash="p", theme_hash="theme-b"),
        )
        self.assertEqual(
            generation_key(source_hash="a", prompt_hash="p", theme_hash="t", limit=10, renderer="maplibre", duration=14),
            generation_key(source_hash="a", prompt_hash="p", theme_hash="t", limit=10, renderer="maplibre", duration=14),
        )
        document = load_scene_breakdown(_scene_block(19, "दिल्ली"))
        entry = {"scene_number": 12, "scene_id": "scene-12", "scene_text_hash": document.scenes[0].text_hash}
        self.assertFalse(association_ok(entry, document))

    def test_renderer_slot_is_exclusive_across_callers(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / ".map-renderer.lock"
            current = {"n": 0, "max": 0}
            gate = threading.Lock()

            def hold():
                with renderer_slot(lock, timeout=5):
                    with gate:
                        current["n"] += 1
                        current["max"] = max(current["max"], current["n"])
                    threading.Event().wait(0.05)
                    with gate:
                        current["n"] -= 1

            threads = [threading.Thread(target=hold) for _ in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(current["max"], 1)


if __name__ == "__main__":
    unittest.main()
