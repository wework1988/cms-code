import copy
import json
from pathlib import Path
import unittest
import map_video

class MapTests(unittest.TestCase):
    def setUp(self):
        self.config=json.loads((Path(__file__).parent/'examples/india-bangladesh-map.json').read_text())

    def test_projection_centres_correctly(self):
        self.assertEqual(map_video.project([90,24],[90,24],15,1920,1080),(960,540))
        self.assertLess(map_video.project([90,25],[90,24],15,1920,1080)[1],540)

    def test_camera_finishes_on_bangladesh(self):
        start=map_video.camera(self.config,0)
        end=map_video.camera(self.config,9)
        self.assertEqual(start[:2],([80,23],58))
        self.assertEqual(end[0],[90.3,23.7])
        self.assertAlmostEqual(end[1],15)

    def test_bad_timing_rejected(self):
        self.config['callout']['start']=2
        with self.assertRaisesRegex(ValueError,'after zoom'):
            map_video.validate(self.config)

    def test_both_country_geometries_present(self):
        names={name for name,_ in map_video.load_features()}
        self.assertTrue({'India','Bangladesh'}<=names)

if __name__=='__main__':
    unittest.main()
