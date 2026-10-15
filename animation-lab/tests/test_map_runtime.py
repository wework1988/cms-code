"""Node discovery for the map renderer when the CMS PATH is short."""
from __future__ import annotations

import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from map_story.runtime import resolve_node_executable  # noqa: E402


class NodeDiscoveryTests(unittest.TestCase):
    def test_limited_path_still_finds_a_known_node(self):
        node = Path("/opt/homebrew/bin/node")
        if not node.is_file():
            self.skipTest("Homebrew node is not installed on this machine")
        found = resolve_node_executable({"PATH": "/usr/bin:/bin", "NODE": ""})
        self.assertEqual(found, str(node.resolve()))
        self.assertTrue(found.startswith("/"))

    def test_explicit_absolute_node_is_used(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "node"
            binary.write_text("#!/bin/sh\n", encoding="utf-8")
            binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
            found = resolve_node_executable({"PATH": "/usr/bin:/bin", "NODE": str(binary)})
        self.assertEqual(found, str(binary.resolve()))

    def test_missing_node_is_a_preflight_error(self):
        import map_story.runtime as runtime
        original_known = runtime._KNOWN_NODE
        original_which = runtime.shutil.which
        runtime._KNOWN_NODE = ()
        runtime.shutil.which = lambda *_args, **_kwargs: None
        try:
            with self.assertRaises(RuntimeError) as caught:
                runtime.resolve_node_executable({"PATH": "/usr/bin:/bin", "NODE": "node"})
            self.assertIn("Node.js", str(caught.exception))
        finally:
            runtime._KNOWN_NODE = original_known
            runtime.shutil.which = original_which


if __name__ == "__main__":
    unittest.main()
