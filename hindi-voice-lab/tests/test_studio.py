import json
import tempfile
import unittest
import wave
from array import array
from pathlib import Path

from src.config import ROOT
from src.generation import build_fingerprint, mark_abandoned_jobs
from src.history import HistoryError, audio_path, get_record, query_history
from src.preferences import (
    ensure_voice_settings,
    load_preferences,
    reset_voice_settings,
    save_draft,
    save_voice_settings,
    select_voice,
)
from src.voice_profiles import load_profile, save_profile, update_profile


def write_wav(path: Path, frames: int = 800, rate: int = 8000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(array("h", [1000] * frames).tobytes())


def job(folder: Path, name: str, **extra) -> None:
    payload = {
        "id": name,
        "status": "complete",
        "text": extra.pop("text", "नमस्ते।"),
        "created_at": extra.pop("created_at", "2026-10-01T00:00:00+00:00"),
        "profile_id": extra.pop("profile_id", "voice-abc12345"),
        "voice_name": extra.pop("voice_name", "Saved voice"),
    }
    payload.update(extra)
    target = folder / name
    target.mkdir(parents=True, exist_ok=True)
    (target / "metadata.json").write_text(json.dumps(payload), encoding="utf-8")


class ProfileCompatibilityTests(unittest.TestCase):
    def test_old_profile_keeps_its_id_and_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference = root / "clip.wav"
            write_wav(reference)
            saved = save_profile("Old voice", reference, {"start_sec": 0, "end_sec": 1}, root=root)
            path = root / saved["id"] / "profile.json"
            document = json.loads(path.read_text(encoding="utf-8"))
            document.pop("description", None)
            path.write_text(json.dumps(document), encoding="utf-8")
            before = (root / saved["id"] / "reference.wav").read_bytes()
            updated = update_profile(saved["id"], display_name="New name", description="A calm read", root=root)
            self.assertEqual(updated["id"], saved["id"])
            self.assertEqual(updated["display_name"], "New name")
            self.assertEqual(updated["description"], "A calm read")
            self.assertEqual((root / saved["id"] / "reference.wav").read_bytes(), before)
            self.assertEqual(load_profile(saved["id"], root)["source"]["start_sec"], 0)


class PreferenceTests(unittest.TestCase):
    def test_selection_draft_and_settings_are_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = ensure_voice_settings("voice-aaaaaaaa", root)
            second = ensure_voice_settings("voice-bbbbbbbb", root)
            self.assertNotEqual(first["seed"], None)
            changed = dict(first)
            changed["exaggeration"] = 0.9
            changed["preset"] = "custom"
            save_voice_settings("voice-aaaaaaaa", changed, root)
            reloaded = load_preferences(root)
            self.assertEqual(reloaded["voices"]["voice-aaaaaaaa"]["exaggeration"], 0.9)
            self.assertEqual(reloaded["voices"]["voice-bbbbbbbb"]["exaggeration"], second["exaggeration"])
            select_voice("voice-bbbbbbbb", root, make_default=True)
            save_draft("ड्राफ्ट", "Title", root, screen="speak")
            again = load_preferences(root)
            self.assertEqual(again["selected_voice_id"], "voice-bbbbbbbb")
            self.assertEqual(again["default_voice_id"], "voice-bbbbbbbb")
            self.assertEqual(again["draft_text"], "ड्राफ्ट")
            self.assertEqual(again["draft_title"], "Title")
            self.assertEqual(again["last_screen"], "speak")
            seed = again["voices"]["voice-aaaaaaaa"]["seed"]
            reset = reset_voice_settings("voice-aaaaaaaa", root)
            self.assertEqual(reset["seed"], seed)
            self.assertEqual(reset["exaggeration"], 0.5)
            self.assertEqual(load_preferences(root)["voices"]["voice-bbbbbbbb"]["exaggeration"], second["exaggeration"])


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / "tmp")
        self.jobs = Path(self.tmp.name) / "jobs"
        self.profiles = Path(self.tmp.name) / "profiles"
        self.jobs.mkdir()
        self.profiles.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_legacy_search_pagination_and_restart(self):
        write_wav(self.jobs / "job-aaaaaaaaaaaa" / "output.wav", frames=16000, rate=8000)
        job(
            self.jobs,
            "job-aaaaaaaaaaaa",
            text="वडनगर का एक छोटा-सा रेलवे स्टेशन।",
            voice_name="Historical name",
            output_wav=str(self.jobs / "job-aaaaaaaaaaaa" / "output.wav"),
            created_at="2026-10-14T09:00:00+00:00",
        )
        for index in range(24):
            job(
                self.jobs,
                f"job-{index:012d}",
                text=f"रिकॉर्ड {index}",
                voice_name="Other",
                created_at=f"2026-10-02T00:{index:02d}:00+00:00",
            )
        (self.jobs / "job-bbbbbbbbbbbb").mkdir()
        (self.jobs / "job-bbbbbbbbbbbb" / "metadata.json").write_text("{", encoding="utf-8")
        job(self.jobs, "job-cccccccccccc", text="गायब", output_wav=str(self.jobs / "missing.wav"), voice_name="Other")

        first = query_history(text="वडनगर", jobs_root=self.jobs, page_size=10)
        self.assertEqual(first["total"], 1)
        self.assertEqual(first["items"][0]["voice_name"], "Historical name")
        self.assertEqual(first["items"][0]["duration_sec"], 2.0)
        self.assertEqual(first["items"][0]["duration_source"], "header")
        self.assertTrue(first["items"][0]["audio_available"])

        page = query_history(jobs_root=self.jobs, page=3, page_size=10)
        self.assertGreaterEqual(page["total"], 25)
        self.assertGreater(len(page["items"]), 0)
        self.assertLessEqual(len(page["items"]), 10)

        names = {item["id"]: item["excerpt"] for item in query_history(jobs_root=self.jobs, page_size=100)["items"]}
        self.assertIn("Unreadable record", names.values())
        missing = get_record("job-cccccccccccc", jobs_root=self.jobs)
        self.assertFalse(missing["audio_available"])
        with self.assertRaises(HistoryError):
            audio_path("job-cccccccccccc", "wav", jobs_root=self.jobs)

        outside = Path(self.tmp.name) / "secret.wav"
        write_wav(outside)
        job(self.jobs, "job-dddddddddddd", output_wav=str(outside), text="बाहर")
        with self.assertRaises(HistoryError):
            audio_path("job-dddddddddddd", "wav", jobs_root=self.jobs)

        played = audio_path("job-aaaaaaaaaaaa", "wav", jobs_root=self.jobs)
        self.assertTrue(played.is_file())
        self.assertEqual(played.suffix, ".wav")
        again = query_history(text="वडनगर", jobs_root=self.jobs)
        self.assertEqual(again["items"][0]["id"], "job-aaaaaaaaaaaa")

    def test_voice_snapshot_survives_rename_and_abandoned_jobs(self):
        reference = self.profiles / "clip.wav"
        write_wav(reference)
        saved = save_profile("Original", reference, {"start_sec": 0}, root=self.profiles)
        write_wav(self.jobs / "job-eeeeeeeeeeee" / "output.wav")
        job(
            self.jobs,
            "job-eeeeeeeeeeee",
            profile_id=saved["id"],
            voice_name="Original",
            output_wav=str(self.jobs / "job-eeeeeeeeeeee" / "output.wav"),
            schema_version=2,
        )
        update_profile(saved["id"], display_name="Renamed", root=self.profiles)
        record = get_record("job-eeeeeeeeeeee", jobs_root=self.jobs, profiles_root=self.profiles)
        self.assertEqual(record["voice_name"], "Original")
        self.assertEqual(record["voice_name_source"], "snapshot")

        legacy = self.jobs / "job-ffffffffffff"
        legacy.mkdir()
        (legacy / "metadata.json").write_text(
            json.dumps({"id": "job-ffffffffffff", "status": "complete", "text": "पुराना", "profile_id": saved["id"]}),
            encoding="utf-8",
        )
        derived = get_record("job-ffffffffffff", jobs_root=self.jobs, profiles_root=self.profiles)
        self.assertEqual(derived["voice_name"], "Renamed")
        self.assertEqual(derived["voice_name_source"], "profile")
        self.assertTrue(derived["legacy"])

        (self.jobs / "job-111111111111").mkdir()
        (self.jobs / "job-111111111111" / "metadata.json").write_text(
            json.dumps({"id": "job-111111111111", "status": "generating", "text": "रुका"}),
            encoding="utf-8",
        )
        self.assertEqual(mark_abandoned_jobs(self.jobs), ["job-111111111111"])
        self.assertEqual(get_record("job-111111111111", jobs_root=self.jobs)["status"], "interrupted")
        self.assertEqual(get_record("job-eeeeeeeeeeee", jobs_root=self.jobs)["status"], "completed")

    def test_fingerprint_changes_when_pause_plan_changes(self):
        settings = {
            "preset": "neutral",
            "exaggeration": 0.5,
            "cfg_weight": 0.5,
            "temperature": 0.8,
            "repetition_penalty": 2.0,
            "min_p": 0.05,
            "top_p": 1.0,
            "sentence_pause_ms": 450,
            "paragraph_pause_ms": 800,
            "seed": 3,
            "device": "cpu",
            "offline": False,
        }
        plan = [{"type": "speech", "text": "एक।", "raw": "एक।", "boundary": "end"}]
        original = build_fingerprint("एक।", plan, "voice-abc12345", "a" * 64, settings)
        paused = list(plan)
        paused.append({"type": "pause", "ms": 600, "source": "explicit"})
        self.assertNotEqual(build_fingerprint("एक। [pause=600ms]", paused, "voice-abc12345", "a" * 64, settings), original)
        other = dict(settings)
        other["seed"] = 9
        self.assertNotEqual(build_fingerprint("एक।", plan, "voice-abc12345", "a" * 64, other), original)


if __name__ == "__main__":
    unittest.main()
