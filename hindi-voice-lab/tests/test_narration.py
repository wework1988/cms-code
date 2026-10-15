import array
import unittest
import wave
from pathlib import Path
import tempfile

from src.generation import assemble_timeline, edge_silence_ms, inserted_silence_ms
from src.narration import NARRATION_EXAMPLE, NarrationError, plan_narration
from src.presets import PRESETS, MODEL_PARAMETERS


def write_wav(path: Path, samples: list[int], rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = array.array("h", samples)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(frames.tobytes())


def read_wav(path: Path) -> tuple[int, list[int]]:
    with wave.open(str(path), "rb") as handle:
        rate = handle.getframerate()
        frames = array.array("h")
        frames.frombytes(handle.readframes(handle.getnframes()))
    return rate, list(frames)


class PauseMarkupTests(unittest.TestCase):
    def test_example_keeps_spoken_text_and_explicit_pauses(self):
        plan = plan_narration(NARRATION_EXAMPLE, 450, 800)
        spoken = [piece.model_text for piece in plan.model_segments()]
        self.assertEqual(
            spoken,
            [
                "वडनगर का एक छोटा-सा रेलवे स्टेशन।",
                "यहीं से शुरू हुई एक यात्रा।",
                "एक छोटे शहर से... देश के सबसे बड़े मंच तक।",
                "यह कहानी है उम्मीद की, मेहनत की, और विश्वास की।",
            ],
        )
        self.assertEqual(
            [(mark.ms, mark.source) for kind, mark in plan.events if kind == "pause"],
            [(600, "explicit"), (800, "explicit"), (600, "explicit")],
        )
        self.assertEqual("".join(piece.raw for piece in plan.speech()), plan.spoken_text)
        self.assertNotIn("[pause=", plan.spoken_text)
        for text in spoken:
            self.assertNotIn("[", text)
            self.assertNotIn("]", text)
            self.assertNotIn("pause", text.lower())
        self.assertIn(",", spoken[-1])
        self.assertEqual(plan.original, NARRATION_EXAMPLE)

    def test_pause_units_limits_and_malformed_tags(self):
        one_second = plan_narration("नमस्ते [pause=1s]", 450, 800)
        self.assertEqual([mark.ms for kind, mark in one_second.events if kind == "pause"], [1000])
        self.assertEqual(one_second.model_segments()[0].model_text, "नमस्ते")

        leading = plan_narration("[pause=300ms][pause=700ms]नमस्ते[pause=1s]", 450, 800)
        self.assertEqual([piece.model_text for piece in leading.model_segments()], ["नमस्ते"])
        self.assertEqual([mark.ms for kind, mark in leading.events if kind == "pause"], [300, 700, 1000])

        plan_narration("[pause=10s] ठीक।", 450, 800)
        plan_narration("[pause=10000ms] ठीक।", 450, 800)

        for bad in ("[happy]", "[pause=300]", "[pause=0ms]", "[pause=11s]", "[pause=1.5s]", "अधूरा [pause=300ms"):
            with self.assertRaises(NarrationError):
                plan_narration(f"नमस्ते {bad}", 450, 800)

    def test_sentence_paragraph_and_length_boundaries(self):
        sentences = plan_narration("एक। दो।", 450, 800)
        self.assertEqual([piece.model_text for piece in sentences.model_segments()], ["एक।", "दो।"])
        self.assertEqual(
            [(mark.ms, mark.source) for kind, mark in sentences.events if kind == "pause"],
            [(450, "sentence")],
        )

        paragraph = plan_narration("एक।\n\nदो।", 450, 800)
        self.assertEqual(
            [(mark.ms, mark.source) for kind, mark in paragraph.events if kind == "pause"],
            [(800, "paragraph")],
        )
        self.assertEqual("".join(piece.raw for piece in paragraph.speech()), "एक।\n\nदो।")

        mixed = plan_narration("एक। दो।\n\nतीन।", 450, 800)
        self.assertEqual(
            [(mark.ms, mark.source) for kind, mark in mixed.events if kind == "pause"],
            [(450, "sentence"), (800, "paragraph")],
        )

        explicit = plan_narration("एक। [pause=600ms] दो।", 450, 800)
        self.assertEqual(
            [(mark.ms, mark.source) for kind, mark in explicit.events if kind == "pause"],
            [(600, "explicit")],
        )

        commas = "यह कहानी है उम्मीद की, मेहनत की, और विश्वास की।"
        one_call = plan_narration(commas, 450, 800)
        self.assertEqual(len(one_call.model_segments()), 1)
        self.assertEqual(one_call.model_segments()[0].model_text, commas)

        long_sentence = ("क" * 200) + "। दो।"
        split = plan_narration(long_sentence, 450, 800, max_chars=180)
        self.assertGreater(len(split.model_segments()), 2)
        self.assertEqual(split.model_segments()[0].boundary, "length")
        self.assertEqual(
            [(mark.ms, mark.source) for kind, mark in split.events if kind == "pause"],
            [(450, "sentence")],
        )
        self.assertEqual("".join(piece.raw for piece in split.speech()), long_sentence)
        self.assertEqual("".join(piece.model_text for piece in split.model_segments()).replace(" ", ""), long_sentence.replace(" ", ""))

    def test_inserted_silence_uses_sample_rate_and_keeps_quiet_samples(self):
        self.assertEqual(inserted_silence_ms(600, 0, 0), 600)
        self.assertEqual(inserted_silence_ms(600, 100, 50), 450)
        self.assertEqual(inserted_silence_ms(100, 80, 80), 0)
        rate = 24000
        quiet_tail = [100] * 2400
        loud = [3000] * 50
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "a.wav"
            second = Path(tmp) / "b.wav"
            output = Path(tmp) / "out.wav"
            write_wav(first, loud + quiet_tail, rate)
            write_wav(second, [2000] * 100, rate)
            plan = plan_narration("एक। [pause=600ms] दो।", 450, 800)
            assemble_timeline([first, second], plan.events, output, rate)
            _, samples = read_wav(output)
        self.assertEqual(edge_silence_ms(array.array("h", loud + quiet_tail), rate, "trail"), 100)
        inserted = int(round(rate * (inserted_silence_ms(600, 100, 0) / 1000.0)))
        self.assertEqual(inserted, 12000)
        self.assertEqual(len(samples), len(loud) + len(quiet_tail) + inserted + 100)
        self.assertEqual(samples[:50], loud)
        self.assertEqual(samples[50:2450], quiet_tail)
        self.assertEqual(samples[2450:14450], [0] * inserted)
        self.assertEqual(samples[14450], 2000)

        syllable = [500] * 2400
        self.assertEqual(edge_silence_ms(array.array("h", loud + syllable), rate, "trail"), 0)
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "a.wav"
            second = Path(tmp) / "b.wav"
            output = Path(tmp) / "out.wav"
            write_wav(first, loud + syllable, rate)
            write_wav(second, [2000] * 10, rate)
            plan = plan_narration("एक। [pause=600ms] दो।", 450, 800)
            assemble_timeline([first, second], plan.events, output, rate)
            _, samples = read_wav(output)
        full = int(round(rate * 0.6))
        self.assertEqual(full, 14400)
        self.assertEqual(samples[50:2450], syllable)
        self.assertEqual(samples[2450:2450 + full], [0] * full)


class PresetTests(unittest.TestCase):
    def test_presets_only_use_supported_parameters(self):
        self.assertEqual(
            MODEL_PARAMETERS,
            ("exaggeration", "cfg_weight", "temperature", "repetition_penalty", "min_p", "top_p"),
        )
        self.assertEqual(set(PRESETS), {"neutral", "warm", "serious", "dramatic"})
        for preset in PRESETS.values():
            self.assertEqual(preset["temperature"], 0.8)
            self.assertGreaterEqual(preset["exaggeration"], 0.4)
            self.assertLessEqual(preset["exaggeration"], 0.75)
            self.assertGreaterEqual(preset["cfg_weight"], 0.3)
            self.assertLessEqual(preset["cfg_weight"], 0.55)
        self.assertGreater(PRESETS["warm"]["exaggeration"], PRESETS["neutral"]["exaggeration"])
        self.assertLess(PRESETS["warm"]["cfg_weight"], PRESETS["neutral"]["cfg_weight"])
        self.assertGreater(PRESETS["dramatic"]["exaggeration"], PRESETS["warm"]["exaggeration"])
        self.assertLess(PRESETS["dramatic"]["cfg_weight"], PRESETS["warm"]["cfg_weight"])


if __name__ == "__main__":
    unittest.main()
