import array
import hashlib
import json
import tempfile
import unittest
import wave
from pathlib import Path

from src.generation import JOB_ID_RE, _assemble, build_fingerprint, reusable_chunks


def write_wav(path: Path, frames: int, rate: int = 8000, value: int = 1000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = array.array("h", [value] * frames)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(samples.tobytes())


def settings() -> dict:
    return {
        "device": "cpu",
        "offline": False,
        "exaggeration": 0.5,
        "cfg_weight": 0.5,
        "temperature": 0.8,
        "repetition_penalty": 2.0,
        "min_p": 0.05,
        "top_p": 1.0,
        "pause_ms": 100,
        "preset": "neutral",
        "sentence_pause_ms": 450,
        "paragraph_pause_ms": 800,
        "seed": 7,
    }


def plan_for(chunks: list[str]) -> list[dict]:
    events = []
    for index, chunk in enumerate(chunks):
        boundary = "sentence" if index < len(chunks) - 1 else "end"
        events.append({"type": "speech", "text": chunk, "raw": chunk, "boundary": boundary})
        if index < len(chunks) - 1:
            events.append({"type": "pause", "ms": 450, "source": "sentence"})
    return events


class ResumeTests(unittest.TestCase):
    def test_matching_chunk_is_reused_and_changes_invalidate_it(self):
        chunks = ["नमस्कार।", "यह परीक्षा है।"]
        fingerprint = build_fingerprint(
            "नमस्कार।यह परीक्षा है।", plan_for(chunks), "voice-abc12345", "a" * 64, settings()
        )
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp) / "job-0123456789ab"
            write_wav(job / "chunks" / "0000.wav", 800)
            metadata = {
                "fingerprint": fingerprint,
                "sample_rate": 8000,
                "chunks": [
                    {
                        "index": 0,
                        "text": chunks[0],
                        "relative_path": "chunks/0000.wav",
                        "status": "complete",
                    }
                ],
            }
            (job / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
            reused = reusable_chunks(job, fingerprint, chunks, 8000)
            self.assertEqual(reused[0], (job / "chunks" / "0000.wav").resolve())
            self.assertIsNone(reused[1])

            changed = dict(settings())
            changed["temperature"] = 0.2
            other = build_fingerprint(
                "नमस्कार।यह परीक्षा है।", plan_for(chunks), "voice-abc12345", "a" * 64, changed
            )
            self.assertNotEqual(other, fingerprint)
            self.assertEqual(reusable_chunks(job, other, chunks, 8000), [None, None])

            metadata["chunks"][0]["text"] = "अलग पाठ"
            (job / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
            self.assertIsNone(reusable_chunks(job, fingerprint, chunks, 8000)[0])

    def test_escaping_chunk_path_is_ignored(self):
        chunks = ["नमस्कार।"]
        fingerprint = build_fingerprint("नमस्कार।", plan_for(chunks), "voice-abc12345", "b" * 64, settings())
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp) / "job-0123456789ab"
            job.mkdir()
            outside = Path(tmp) / "outside.wav"
            write_wav(outside, 100)
            metadata = {
                "fingerprint": fingerprint,
                "sample_rate": 8000,
                "chunks": [
                    {
                        "index": 0,
                        "text": chunks[0],
                        "relative_path": "../outside.wav",
                        "status": "complete",
                    }
                ],
            }
            (job / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
            self.assertEqual(reusable_chunks(job, fingerprint, chunks, 8000), [None])

    def test_pause_is_inserted_without_crossfade(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "a.wav"
            second = Path(tmp) / "b.wav"
            output = Path(tmp) / "out.wav"
            write_wav(first, 400, value=1000)
            write_wav(second, 400, value=2000)
            _assemble([first, second], output, 8000, 100)
            with wave.open(str(output), "rb") as handle:
                self.assertEqual(handle.getframerate(), 8000)
                samples = array.array("h")
                samples.frombytes(handle.readframes(handle.getnframes()))
            self.assertEqual(len(samples), 400 + 800 + 400)
            self.assertEqual(samples[399], 1000)
            self.assertEqual(samples[400], 0)
            self.assertEqual(samples[1199], 0)
            self.assertEqual(samples[1200], 2000)

    def test_pause_preset_and_old_flat_jobs_do_not_resume(self):
        chunks = ["एक।", "दो।"]
        text = "एक।दो।"
        profile = "voice-abc12345"
        reference = "c" * 64
        current = settings()
        plan = plan_for(chunks)
        original = build_fingerprint(text, plan, profile, reference, current)

        longer_pause = dict(current)
        longer_pause["sentence_pause_ms"] = 900
        self.assertNotEqual(build_fingerprint(text, plan, profile, reference, longer_pause), original)

        dramatic = dict(current)
        dramatic["preset"] = "dramatic"
        dramatic["exaggeration"] = 0.75
        dramatic["cfg_weight"] = 0.3
        self.assertNotEqual(build_fingerprint(text, plan, profile, reference, dramatic), original)

        with_explicit = list(plan)
        with_explicit.insert(1, {"type": "pause", "ms": 600, "source": "explicit"})
        self.assertNotEqual(build_fingerprint(text, with_explicit, profile, reference, current), original)

        self.assertNotEqual(
            build_fingerprint(text, plan, profile, "d" * 64, current),
            original,
        )

        old_payload = {
            "text": text,
            "chunks": chunks,
            "profile_id": profile,
            "reference_sha256": reference,
            "language_id": "hi",
            "package_version": "0.1.7",
            "checkpoint": "t3_mtl23ls_v2.safetensors",
            "settings": {
                "device": "cpu",
                "offline": False,
                "exaggeration": 0.5,
                "cfg_weight": 0.5,
                "temperature": 0.8,
                "repetition_penalty": 2.0,
                "min_p": 0.05,
                "top_p": 1.0,
                "pause_ms": 250,
                "seed": None,
            },
        }
        old_hash = hashlib.sha256(
            json.dumps(old_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        self.assertNotEqual(old_hash, original)
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp) / "job-0123456789ab"
            job.mkdir()
            (job / "metadata.json").write_text(
                json.dumps({"fingerprint": old_hash, "sample_rate": 8000, "chunks": []}),
                encoding="utf-8",
            )
            self.assertEqual(reusable_chunks(job, original, chunks, 8000), [None, None])

    def test_job_ids_cannot_escape(self):
        self.assertIsNone(JOB_ID_RE.fullmatch("../job"))
        self.assertIsNone(JOB_ID_RE.fullmatch("job-NOTHEX"))
        self.assertIsNotNone(JOB_ID_RE.fullmatch("job-0123456789ab"))


if __name__ == "__main__":
    unittest.main()
