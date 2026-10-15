import unittest

from src.text_processing import MAX_CHUNK_CHARS, SAMPLE_HINDI, chunk_text, script_notice


class TextProcessingTests(unittest.TestCase):
    def test_sample_and_punctuation_are_preserved(self):
        samples = [
            SAMPLE_HINDI,
            "एक। दो॥ तीन? चार! पांच.",
            "संख्या 1.5 ठीक है। आगे बढ़ें।",
            "रुको... फिर चलें।",
            "पंक्ति एक।\nपंक्ति दो।",
            "  नमस्कार।  ",
        ]
        for text in samples:
            parts = chunk_text(text)
            self.assertEqual("".join(parts), text)
            self.assertTrue(parts)
            for part in parts:
                self.assertLessEqual(len(part), MAX_CHUNK_CHARS)
                self.assertNotEqual(part, "")

    def test_oversized_text_is_split_without_loss_or_repetition(self):
        text = "क" * 450
        parts = chunk_text(text, max_chars=180)
        self.assertEqual("".join(parts), text)
        self.assertGreater(len(parts), 1)
        for part in parts:
            self.assertLessEqual(len(part), 180)

    def test_secondary_split_keeps_words(self):
        sentence = "शब्द " * 80
        parts = chunk_text(sentence.strip(), max_chars=50)
        self.assertEqual("".join(parts), sentence.strip())
        for part in parts:
            self.assertLessEqual(len(part), 50)

    def test_roman_text_is_not_rewritten(self):
        roman = "namaste yeh meri awaaz ka test hai. aaj ek kahani sunenge."
        self.assertEqual("".join(chunk_text(roman)), roman)
        notice = script_notice(roman)
        self.assertIsNotNone(notice)
        self.assertIn("Devanagari", notice or "")
        self.assertIsNone(script_notice(SAMPLE_HINDI))

    def test_empty_text(self):
        self.assertEqual(chunk_text(""), [])


if __name__ == "__main__":
    unittest.main()
