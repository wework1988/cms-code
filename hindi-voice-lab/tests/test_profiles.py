import array
import json
import tempfile
import unittest
import wave
from pathlib import Path

from src.voice_profiles import ProfileError, list_profiles, load_profile, save_profile, validate_profile_id


def write_wav(path: Path) -> None:
    samples = array.array("h", [1000] * 16000)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(samples.tobytes())


class ProfileTests(unittest.TestCase):
    def test_profile_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference = root / "clip.wav"
            write_wav(reference)
            saved = save_profile(
                "मेरी आवाज़",
                reference,
                {"start_sec": 1.0, "end_sec": 9.0, "original_file": "take.wav"},
                root=root,
            )
            loaded = load_profile(saved["id"], root=root)
            self.assertEqual(loaded["display_name"], "मेरी आवाज़")
            self.assertEqual(loaded["kind"], "reference_profile")
            self.assertIn("not a fine-tuned", loaded["label"])
            self.assertEqual(loaded["source"]["start_sec"], 1.0)
            self.assertTrue(Path(loaded["reference_path"]).is_file())
            self.assertEqual(list_profiles(root)[0]["id"], saved["id"])
            raw = json.loads((root / saved["id"] / "profile.json").read_text(encoding="utf-8"))
            self.assertEqual(raw["reference_wav"], "reference.wav")

    def test_rejects_path_traversal_ids(self):
        for profile_id in ("../etc", "..", "voice/../../x", "voice id", ""):
            with self.assertRaises(ProfileError):
                validate_profile_id(profile_id)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ProfileError):
                load_profile("../secret", root=Path(tmp))


if __name__ == "__main__":
    unittest.main()
