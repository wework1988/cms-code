from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import generate_map_video as gm  # noqa: E402


class PromptLoadingTests(unittest.TestCase):
    def test_master_prompt_file_takes_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompt = Path(tmp) / "prompt.txt"
            prompt.write_text("Use this prompt.", encoding="utf-8")
            args = type("Args", (), {"master_prompt_file": prompt})
            body, meta = gm._load_master_prompt(args, planner="deepseek")
            self.assertEqual(body, "Use this prompt.")
            self.assertEqual(meta["prompt_source"], "master_prompt_file")
            self.assertEqual(meta["prompt_path"], str(prompt.resolve()))

    def test_loads_cms_prompt_even_for_local_planner(self):
        original = gm._load_cms_map_prompt
        gm._load_cms_map_prompt = lambda: {"id": 42, "body": "CMS revision"}
        try:
            args = type("Args", (), {"master_prompt_file": None})
            body, meta = gm._load_master_prompt(args, planner="local")
            self.assertEqual(body, "CMS revision")
            self.assertEqual(meta["prompt_id"], 42)
            self.assertEqual(meta["prompt_source"], "cms_prompt_revision")
        finally:
            gm._load_cms_map_prompt = original


if __name__ == "__main__":
    unittest.main()
