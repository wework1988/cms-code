import tempfile
import unittest
from pathlib import Path

from src.config import ROOT, confine
from src.generation import JOB_ID_RE


class PathConfinementTests(unittest.TestCase):
    def test_rejects_paths_outside_the_lab(self):
        with self.assertRaises(ValueError):
            confine(ROOT / ".." / "outside.txt")
        with self.assertRaises(ValueError):
            confine(Path("/tmp/not-in-the-lab"))

    def test_allows_a_path_inside_a_chosen_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "job-0123456789ab" / "output.wav"
            target.parent.mkdir()
            resolved = confine(target, root)
            self.assertTrue(resolved.is_relative_to(root.resolve()))
            self.assertTrue(JOB_ID_RE.fullmatch(target.parent.name))

    def test_job_parent_segments_are_rejected_by_the_id_rule(self):
        self.assertIsNone(JOB_ID_RE.fullmatch(".."))
        self.assertIsNone(JOB_ID_RE.fullmatch("job-../../abcd"))


if __name__ == "__main__":
    unittest.main()
