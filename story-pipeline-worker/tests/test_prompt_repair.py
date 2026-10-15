import unittest
from unittest.mock import Mock
import json
from repair_image_prompt import repair

class RepairTests(unittest.TestCase):
    def call(self,result):
        response=Mock();response.json.return_value={'choices':[{'message':{'content':json.dumps(result)}}]}
        return repair({'original_prompt':'Scene 5. Peaceful mountain shrine.'},'test-key',post=Mock(return_value=response))
    def test_preserves_scene_and_enforces_aspect(self):
        result=self.call({'action':'rewrite','prompt':'Scene 5. A peaceful mountain shrine in a hand-drawn landscape.','reason':'Clarified'})
        self.assertIn('16:9',result['prompt'])
    def test_changed_scene_rejected(self):
        with self.assertRaises(ValueError):self.call({'action':'rewrite','prompt':'Scene 6. A peaceful mountain shrine in a hand-drawn landscape.'})
    def test_review_is_not_a_prompt(self):
        self.assertEqual(self.call({'action':'review','reason':'Cannot preserve meaning safely'})['action'],'review')
