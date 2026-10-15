import array
import tempfile
import unittest
import wave
from pathlib import Path

from src.audio_processing import AudioError, extract_segment, validate_segment_bounds


def write_wav(path: Path, seconds: float, rate: int = 16000, channels: int = 1, value: int = 1000) -> None:
    frames = int(seconds * rate)
    samples = array.array("h", [value] * (frames * channels))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(samples.tobytes())


class SegmentBoundsTests(unittest.TestCase):
    def test_rejects_invalid_bounds(self):
        cases = [
            (-1, 2, 10),
            (2, 2, 10),
            (3, 1, 10),
            (11, 12, 10),
            (0, 12, 10),
            (0, 0.1, 10),
            (0, 31, 60),
        ]
        for start, end, duration in cases:
            with self.assertRaises(AudioError):
                validate_segment_bounds(start, end, duration)

    def test_accepts_a_short_window(self):
        self.assertAlmostEqual(validate_segment_bounds(1.0, 8.0, 30.0), 8.0)

    def test_extract_does_not_change_the_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "original.wav"
            dest = Path(tmp) / "clip.wav"
            write_wav(source, 2.0, value=4000)
            before = source.read_bytes()
            info = extract_segment(source, dest, 0.2, 1.0)
            self.assertEqual(source.read_bytes(), before)
            self.assertTrue(dest.is_file())
            self.assertGreater(info.duration_sec, 0.7)
            self.assertLess(info.duration_sec, 0.9)
            self.assertEqual(info.channels, 1)

    def test_empty_slice_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "original.wav"
            dest = Path(tmp) / "clip.wav"
            write_wav(source, 1.0)
            with self.assertRaises(AudioError):
                extract_segment(source, dest, 0.5, 0.5)

    def test_silence_and_clipping_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            silent = Path(tmp) / "silent.wav"
            clipped = Path(tmp) / "clipped.wav"
            write_wav(silent, 4.0, value=0)
            write_wav(clipped, 4.0, value=32767)
            silent_info = extract_segment(silent, Path(tmp) / "silent-clip.wav", 0, 4)
            clipped_info = extract_segment(clipped, Path(tmp) / "clipped-clip.wav", 0, 4)
            self.assertTrue(any("silence" in item.lower() for item in silent_info.warnings))
            self.assertTrue(any("clipped" in item.lower() for item in clipped_info.warnings))


if __name__ == "__main__":
    unittest.main()
