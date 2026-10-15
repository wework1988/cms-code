import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
import cinematic
import flow_assets
import render

class CinematicTests(unittest.TestCase):
    def test_isolated_runner_exits_after_success_without_modifying_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'lab'; root.mkdir()
            (root/'flow_prompt.mjs').write_text('export async function fillPrompt() {}')
            source=Path(temp)/'source'; source.mkdir()
            (source/'helper').mkdir()
            (source/'node_modules/playwright').mkdir(parents=True)
            code='''function ensureChromeWithLogin() {}
async function fillPrompt(page, text) {}
async function clickGenerate(page) {}
main().catch((err) => {});
'''
            (source/'run-images.mjs').write_text(code)
            (source/'prompt-recovery.mjs').write_text('')
            with patch.object(flow_assets,'ROOT',root):
                runtime=flow_assets.snapshot_agent(source)
            self.assertEqual((source/'run-images.mjs').read_text(),code)
            self.assertIn('main().then(() => process.exit(process.exitCode || 0))',(runtime/'run-images.mjs').read_text())
            self.assertTrue(runtime.is_relative_to(root))

    def test_camera_has_no_black_edges(self):
        image=Image.new('RGB',(700,400),'#ffffff')
        for motion in ('slow_zoom_in','slow_zoom_out','pan_left','pan_right','parallax'):
            for t in (0,.5,1):
                frame=cinematic.camera(image,motion,t,640,360)
                self.assertEqual(frame.size,(640,360))
                self.assertEqual(frame.getextrema(),((255,255),)*3)

    def test_real_crossfade(self):
        render.TEXT['test']=Image.new('L',(10,10),0)
        scene={'duration':5,'caption':'test','reconstruction_label':'test','motion':'slow_zoom_in'}
        clip={'scenes':[scene,scene],'duration':10,'transition':'crossfade'}
        images=[Image.new('RGB',(640,360),'red'),Image.new('RGB',(640,360),'blue')]
        before=cinematic.storyboard(clip,4.5,images,640,360).getpixel((300,100))
        after=cinematic.storyboard(clip,4.9,images,640,360).getpixel((300,100))
        self.assertGreater(before[0],before[2])
        self.assertGreater(after[2],after[0])

    def test_flow_job_mapping_and_reuse(self):
        plan={'clips':[{'id':'clip_01','type':'storyboard','scenes':[{'image_prompt':'Scene one'},{'image_prompt':'Scene two'}]}]}
        with tempfile.TemporaryDirectory() as temp:
            job,mapping=flow_assets.prepare_job(plan,Path(temp))
            self.assertEqual([e['scene'] for e in mapping],[1,2])
            self.assertEqual(flow_assets.prepare_job(plan,Path(temp))[0],job)
            images=job/'images'; images.mkdir()
            for n in (1,2):
                Image.new('RGB',(20,20)).save(images/f'{n:03d}.png')
            assets=flow_assets.collect_images(job,mapping)
            self.assertTrue((assets/'clip_01-02.png').exists())
            plan['clips'][0]['scenes'][0]['image_prompt']='changed'
            self.assertNotEqual(flow_assets.prepare_job(plan,Path(temp))[0],job)

if __name__=='__main__':
    unittest.main()
