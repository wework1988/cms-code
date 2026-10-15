import json
import sys
import tempfile
import time
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline_watchdog as w
import pipeline_validation as v

class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state = patch.object(w, 'STATE', self.root/'state'); self.state.start()
        w.STATE.mkdir()
        self.path = w.STATE/'story-1.json'
        self.stage = {'status':'queued','attempts':0}
        self.job = {'story_id':1,'story_path':str(self.root/'story'),'asset_root':str(self.root), 'status':'queued','stages':{'images':self.stage}}
    def tearDown(self):
        self.state.stop(); self.tmp.cleanup()
    def advance(self, now=1000, complete=False, **kwargs):
        with patch.object(w,'validate',return_value={'complete':complete}), patch.object(w,'review_reason',return_value=None):
            w.advance(self.path,self.job,now,**kwargs)
    def test_retry_budget_survives_disk_reload(self):
        for attempt in range(1,4):
            self.stage.update(status='running',attempts=attempt,result=str(self.root/'missing'),last_progress_at=0)
            with patch.object(w,'owned_process',return_value=False): self.advance()
            w.write(self.path,self.job); self.job=w.read(self.path); self.stage=self.job['stages']['images']
            self.assertEqual(self.stage['attempts'],attempt)
            self.assertEqual(self.stage['status'],'failed' if attempt==3 else 'retry_wait')
        self.assertEqual(self.job['status'],'needs_attention')
    def test_success_exit_without_files_does_not_complete(self):
        result=self.root/'result';w.write(result,{'returncode':0})
        self.stage.update(status='running',attempts=1,result=str(result))
        self.advance();self.assertEqual(self.stage['status'],'retry_wait')
    def test_adopts_complete_outputs_without_launch(self):
        self.advance(complete=True)
        self.assertEqual(self.job['status'],'completed');self.assertEqual(self.stage['attempts'],0)
    def test_stop_is_terminal(self):
        self.job['status']='stopped'
        with patch.object(w,'validate',side_effect=AssertionError('must not execute')):
            w.advance(self.path,self.job,1000)
    def test_no_launch_when_resource_busy(self):
        with patch.object(w.subprocess,'Popen',side_effect=AssertionError('duplicate launch')):
            self.advance(resource_busy=True)
        self.assertEqual(self.stage['attempts'],0)

    def test_second_storyboard_can_launch_while_images_run(self):
        path2 = w.STATE/'story-2.json'
        stage2 = {'status':'queued','attempts':0}
        job2 = {'story_id':2,'story_path':str(self.root/'story2'),'asset_root':str(self.root),'status':'queued','stages':{'storyboard':stage2}}
        with patch.object(w,'validate',return_value={'complete':False}), patch.object(w,'review_reason',return_value=None), patch.object(w.subprocess,'Popen') as popen:
            popen.return_value.pid = 77
            w.advance(path2, job2, 1000, resource_busy=False, browser_busy=True)
        self.assertEqual(stage2['status'], 'running')
        self.assertEqual(stage2['attempts'], 1)

    def test_second_images_wait_while_browser_busy(self):
        path2 = w.STATE/'story-2.json'
        stage2 = {'status':'queued','attempts':0}
        job2 = {'story_id':2,'story_path':str(self.root/'story2'),'asset_root':str(self.root),'status':'queued','stages':{'images':stage2}}
        with patch.object(w.subprocess,'Popen',side_effect=AssertionError('duplicate browser')):
            w.advance(path2, job2, 1000, resource_busy=False, browser_busy=True)
        self.assertEqual(stage2['status'], 'queued')
        self.assertEqual(stage2['attempts'], 0)

    def test_videos_can_launch_while_images_run(self):
        images={'status':'running','attempts':1,'token':'img','pid':11,'result':str(self.root/'img.result'),'last_progress_at':999}
        videos={'status':'queued','attempts':0}
        job={'story_id':1,'story_path':str(self.root/'story'),'asset_root':str(self.root),'status':'running','stages':{'images':images,'videos':videos}}
        path=self.path
        with patch.object(w,'owned_process',side_effect=lambda stage: stage is images), patch.object(w,'validate') as validate, patch.object(w,'review_reason',return_value=None), patch.object(w.subprocess,'Popen') as popen:
            validate.side_effect=lambda job,name: {'complete':False,'completed':12 if name=='images' else 0,'invalid':[],'duplicates':[]}
            popen.return_value.pid=88
            w.advance(path, job, 1000, resource_busy=False, chrome_busy=True, firefox_busy=False)
        self.assertEqual(images['status'], 'running')
        self.assertEqual(videos['status'], 'running')
        self.assertEqual(videos['attempts'], 1)

    def test_videos_wait_if_images_are_only_queued(self):
        images={'status':'queued','attempts':1}
        videos={'status':'queued','attempts':0}
        job={'story_id':1,'story_path':str(self.root/'story'),'asset_root':str(self.root),'status':'queued','stages':{'images':images,'videos':videos}}
        with patch.object(w,'validate') as validate, patch.object(w.subprocess,'Popen',side_effect=AssertionError('waiting story should not take firefox')):
            validate.side_effect=lambda job,name: {'complete':False,'completed':40 if name=='images' else 0,'invalid':[],'duplicates':[]}
            w.advance(self.path, job, 1000, chrome_busy=True, firefox_busy=False)
        self.assertEqual(videos['status'], 'queued')
        self.assertEqual(videos['attempts'], 0)

    def test_videos_wait_until_ten_images(self):
        images={'status':'running','attempts':1,'token':'img','pid':11,'result':str(self.root/'img.result'),'last_progress_at':999}
        videos={'status':'queued','attempts':0}
        job={'story_id':1,'story_path':str(self.root/'story'),'asset_root':str(self.root),'status':'running','stages':{'images':images,'videos':videos}}
        with patch.object(w,'owned_process',side_effect=lambda stage: stage is images), patch.object(w,'validate') as validate, patch.object(w.subprocess,'Popen',side_effect=AssertionError('too few images')):
            validate.side_effect=lambda job,name: {'complete':False,'completed':4 if name=='images' else 0,'invalid':[],'duplicates':[]}
            w.advance(self.path, job, 1000, chrome_busy=True, firefox_busy=False)
        self.assertEqual(videos['status'], 'queued')
        self.assertEqual(videos['attempts'], 0)
    def test_stale_owned_runner_is_terminated(self):
        self.stage.update(status='running',attempts=1,result=str(self.root/'missing'),last_progress_at=1)
        self.stage['fingerprint']=w.fingerprint(self.job,self.stage)
        with patch.object(w,'owned_process',return_value=True),patch.object(w,'terminate') as terminate:
            self.advance();terminate.assert_called_once()
        self.assertEqual(self.stage['status'],'retry_wait')
    def test_live_progress_prevents_termination(self):
        self.stage.update(status='running',attempts=1,result=str(self.root/'missing'),last_progress_at=1,fingerprint='old')
        with patch.object(w,'owned_process',return_value=True),patch.object(w,'terminate') as terminate:
            self.advance();terminate.assert_not_called()
        self.assertEqual(self.stage['last_progress_at'],1000)
    def test_orphan_lease_blocks_retry(self):
        self.stage.update(status='running',attempts=1,result=str(self.root/'missing'))
        with patch.object(w,'resource_leased',return_value=True): self.advance()
        self.assertEqual(self.job['status'],'needs_attention')
    def test_real_wrapper_writes_result_and_releases_lease(self):
        artifact=self.root/'done'
        with patch.object(w,'command',return_value=[sys.executable,'-c',f"from pathlib import Path; Path({str(artifact)!r}).write_text('ok')"]):
            self.advance()
        pid=self.stage['pid']
        deadline=time.monotonic()+5
        while time.monotonic()<deadline and not Path(self.stage['result']).exists():
            time.sleep(.02)
        self.assertEqual(w.read(self.stage['result'])['returncode'],0)
        self.assertTrue(artifact.exists())
        import os
        next(proc for proc in w.CHILDREN if proc.pid == pid).wait(timeout=5)
        self.assertFalse(w.resource_leased())
        self.advance(complete=True)
        self.assertEqual(self.job['status'],'completed')
    def test_stopped_flow_manifest_needs_review(self):
        root=Path(self.job['story_path'])/'images'
        w.write(root/'generation-manifest.json',{'control':'stopped','scenes':{}})
        self.assertIn('stopped',w.review_reason(self.job,'images'))
    def test_retry_deadline_prevents_immediate_restart(self):
        self.stage.update(status='retry_wait',attempts=1,next_retry_at=1300)
        with patch.object(w.subprocess,'Popen',side_effect=AssertionError('too early')):self.advance(now=1000)
        self.assertEqual(self.stage['attempts'],1)
    def test_monitor_heartbeats_do_not_count_as_generation_progress(self):
        images=Path(self.job['story_path'])/'images'
        w.write(images/'runner-status.json',{'heartbeat_at':1})
        before=w.fingerprint(self.job,self.stage)
        w.write(images/'runner-status.json',{'heartbeat_at':999})
        self.assertEqual(before,w.fingerprint(self.job,self.stage))
    def test_asset_sync_messages_do_not_hide_stalled_generation(self):
        log = self.root/'runner.log'
        self.stage['log'] = str(log)
        log.write_text('Stage C request sent\n')
        before = w.fingerprint(self.job, self.stage)
        with log.open('a') as stream:
            stream.write('[assets] storyboard (4 file(s)) → story\n[assets] mirrored → mirror\n')
        self.assertEqual(before, w.fingerprint(self.job, self.stage))
        with log.open('a') as stream:
            stream.write('Stage C batch complete\n')
        self.assertNotEqual(before, w.fingerprint(self.job, self.stage))

    def test_active_jobs_prevent_idle_sleep_without_keeping_display_on(self):
        with patch.object(w.sys, 'platform', 'darwin'), patch.object(w.subprocess, 'Popen') as spawn:
            w.keep_awake([(self.path, self.job)])
            self.assertEqual(spawn.call_args.args[0], ['/usr/bin/caffeinate', '-i', '-t', '660'])

    def test_terminal_jobs_do_not_prevent_sleep(self):
        with patch.object(w.sys, 'platform', 'darwin'), patch.object(w.subprocess, 'Popen') as spawn:
            for status in w.TERMINAL:
                self.job['status'] = status
                w.keep_awake([(self.path, self.job)])
            spawn.assert_not_called()

    def test_scene_sets_not_counts(self):
        p=self.root/'image-prompts';p.mkdir();(p/'image-prompts-only.txt').write_text('Scene 1. A\n\nScene 3. B')
        images=self.root/'images';images.mkdir()
        (images/'001.jpg').touch();(images/'002.jpg').touch()
        with patch.object(v,'image_valid',return_value=True): report=v.media_report(self.root,'images')
        self.assertFalse(report['complete']);self.assertEqual(report['missing'],[3])
    def test_duplicate_scene_rejected(self):
        p=self.root/'prompts.txt';p.write_text('Scene 1. A\nScene 1. B')
        with self.assertRaises(ValueError):v.scene_ids(p)
    def test_truncated_video_rejected(self):
        p=self.root/'scene_1.mp4';p.write_bytes(b'\x00\x00\x00\x64mdat123')
        self.assertFalse(v.video_valid(p))

if __name__=='__main__':unittest.main()
