import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

WORKER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKER))
import asset_store

spec = importlib.util.spec_from_file_location('worker_voice_secrets', WORKER / 'secrets.py')
worker_secrets = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = worker_secrets
spec.loader.exec_module(worker_secrets)


class VoiceFolderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.env = patch.dict(os.environ, {'STORY_ASSET_ROOT': str(self.root), 'STORY_ASSET_VOICE_TYPE': ''})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_new_folder_uses_voice_from_bundle_with_existing_root(self):
        worker_secrets.apply_asset_root_from_bundle({'settings': {'voice_type': 'bindass-gupshup'}})
        folder = asset_store.story_folder('new-story', 203, 'New Story', 'general')
        self.assertEqual(folder.name, '203-new-story--voice-bindass-gupshup')
        self.assertEqual((folder / 'meta/drupal-node-id.txt').read_text().strip(), '203')

    def test_existing_folder_keeps_name_after_voice_and_title_change(self):
        old = asset_store.story_folder('mahisasur', 191, 'Mahisasur', 'god_story')
        (old / 'images/047.jpg').write_bytes(b'existing-output')
        worker_secrets.apply_asset_root_from_bundle({'settings': {'voice_type': 'god'}})
        found = asset_store.story_folder('updated-title', 191, 'Updated Title', 'general')
        self.assertEqual(found, old)
        self.assertEqual((found / 'images/047.jpg').read_bytes(), b'existing-output')
        self.assertFalse((self.root / 'general/191-updated-title--voice-god').exists())

    def test_old_folder_without_metadata_is_reused(self):
        old = self.root / 'god_story/191-mahisasur'
        old.mkdir(parents=True)
        os.environ['STORY_ASSET_VOICE_TYPE'] = 'god'
        self.assertEqual(asset_store.story_folder('mahisasur', 191, 'Mahisasur', 'god_story'), old)

    def test_suffixed_folder_keeps_path_after_voice_change(self):
        os.environ['STORY_ASSET_VOICE_TYPE'] = 'crime'
        old = asset_store.story_folder('title', 203, 'Title')
        os.environ['STORY_ASSET_VOICE_TYPE'] = 'explainer'
        self.assertEqual(asset_store.story_folder('title', 203, 'Title'), old)

    def test_missing_voice_clears_previous_context(self):
        worker_secrets.apply_asset_root_from_bundle({'settings': {'voice_type': 'god'}})
        worker_secrets.apply_asset_root_from_bundle({'settings': {}})
        self.assertEqual(asset_store.folder_name(203, 'Title'), '203-title')

    def test_voice_is_safe_for_paths(self):
        self.assertEqual(asset_store.folder_name(203, 'Title', '../../Bindass Gupshup'), '203-title--voice-bindass-gupshup')


if __name__ == '__main__':
    unittest.main()
