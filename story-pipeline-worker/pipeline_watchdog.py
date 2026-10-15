#!/usr/bin/env python3
"""Durable stage queue. launchd calls tick every 300 seconds; retries never reset."""
from __future__ import annotations
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from pipeline_validation import media_report, storyboard_report

ROOT = Path(__file__).resolve().parent
STATE = Path(os.environ.get('PIPELINE_STATE_DIR', str(ROOT/'.pipeline-jobs')))
MAX_ATTEMPTS = 3  # initial attempt + TWO retries, persisted across restarts
STALE_SECONDS = 300
TERMINAL = {'completed', 'failed', 'needs_attention', 'stopped'}
BROWSER_STAGES = {'images', 'videos'}
CHROME_STAGES = {'images'}   # Google Flow
FIREFOX_STAGES = {'videos'}  # Digen
MIN_IMAGES_FOR_VIDEOS = 10
CHILDREN = []


def max_jobs() -> int:
    """How many stories may run at once. Flow/video still share one browser lock."""
    try:
        n = int(str(os.environ.get('PIPELINE_MAX_JOBS', '2')).strip())
    except ValueError:
        n = 2
    return max(1, n)


def read(path, default=None):
    try: return json.loads(Path(path).read_text())
    except FileNotFoundError: return default


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    with tmp.open('w') as f:
        json.dump(value, f, indent=2); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


@contextlib.contextmanager
def locked():
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE/'watchdog.lock').open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


def owned_process(stage):
    pid, token = stage.get('pid'), stage.get('token')
    if not pid and stage.get('result'):
        pid = read(stage['result']+'.pid', {}).get('pid')
        if pid: stage['pid'] = pid
    if not pid or not token: return False
    try:
        command = subprocess.check_output(['ps','-p',str(pid),'-o','command='], text=True, timeout=3)
        return 'pipeline_watchdog.py execute' in command and token in command and os.getpgid(pid) == pid
    except (OSError, subprocess.SubprocessError): return False


def _lock_held(path: Path) -> bool:
    STATE.mkdir(parents=True, exist_ok=True)
    with path.open('a') as lease:
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        return False


def token_lease_held(token) -> bool:
    if not token:
        return False
    return _lock_held(STATE / f'execute-{token}.lock')


def browser_lock_held() -> bool:
    """True while a legacy exclusive execute still holds the shared browser lock."""
    return _lock_held(STATE / 'browser.lock') or _lock_held(STATE / 'execution.lock')


def chrome_lock_held() -> bool:
    """True while Flow/Chrome is in use (includes legacy browser.lock)."""
    return _lock_held(STATE / 'chrome.lock') or browser_lock_held()


def firefox_lock_held() -> bool:
    """True while Digen/Firefox is in use."""
    return _lock_held(STATE / 'firefox.lock')


def resource_leased():
    return chrome_lock_held() or firefox_lock_held()


def job_has_owned_process(job) -> bool:
    return any(owned_process(stage) for stage in job.get('stages', {}).values())


def browser_stage_owned(jobs) -> bool:
    return chrome_stage_owned(jobs) or firefox_stage_owned(jobs)


def chrome_stage_owned(jobs) -> bool:
    return any(
        owned_process(stage)
        for _path, job in jobs
        for name, stage in job.get('stages', {}).items()
        if name in CHROME_STAGES
    )


def firefox_stage_owned(jobs) -> bool:
    return any(
        owned_process(stage)
        for _path, job in jobs
        for name, stage in job.get('stages', {}).items()
        if name in FIREFOX_STAGES
    )


def terminate(stage):
    if not owned_process(stage): return
    pid = stage['pid']
    os.killpg(pid, signal.SIGTERM)
    for _ in range(20):
        if not owned_process(stage): break
        time.sleep(.1)
    # Only this verified, dedicated process group is eligible for termination.
    try: os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError: pass


def fingerprint(job, stage):
    h = hashlib.sha256()
    root = Path(job['story_path'])
    for folder in ['script','scenes','prompts','image-prompts','images','videos','audio']:
        for p in sorted((root/folder).rglob('*')):
            if not p.is_file() or p.suffix in {'.tmp','.lock'} or p.name == 'runner-status.json': continue
            h.update(str(p.relative_to(root)).encode())
            if p.suffix in {'.txt','.md','.json'}:
                h.update(p.read_bytes())
            else:
                info=p.stat(); h.update(f'{info.st_size}:{info.st_mtime_ns}'.encode())
    log = Path(stage.get('log','/nonexistent'))
    if log.is_file():
        # Repeated heartbeat/wait lines do not count as forward progress.
        with log.open('rb') as f:
            f.seek(max(0,log.stat().st_size-65536)); lines=f.read().splitlines()
        meaningful = [line for line in lines if not line.startswith(b'[assets]') and not any(x in line.lower() for x in [b'heartbeat',b'polling',b'still waiting',b'waiting for'])]
        h.update(b'\n'.join(dict.fromkeys(meaningful)))
    return h.hexdigest()


def validate(job, name):
    root=Path(job['story_path'])
    if name == 'storyboard': return storyboard_report(root)
    if name in {'images','videos'}: return media_report(root,name)
    if name == 'script':
        p=root/'script/FULL_STORY.txt'
        return {'complete':p.is_file() and bool(p.read_text().strip())}
    if name.startswith('audio_'):
        folder=root/'audio' / ('english' if name == 'audio_english' else '')
        paths=list(folder.glob('*.mp3'))
        valid=bool(paths)
        for p in paths:
            try:
                r=subprocess.run(['/usr/bin/afinfo',str(p)],capture_output=True,text=True,timeout=15)
                valid = valid and r.returncode == 0 and p.stat().st_size > 0
            except (OSError,subprocess.SubprocessError): valid=False
        return {'complete':valid, 'files':len(paths)}
    return {'complete':False}


def review_reason(job, name):
    root=Path(job['story_path'])
    if name != 'images': return None
    manifest=read(root/'images/generation-manifest.json',{})
    if manifest.get('control') in {'paused','stopped'}: return 'Flow job was paused or stopped; resume it explicitly first.'
    for scene in manifest.get('scenes',{}).values():
        status=scene.get('status')
        category=scene.get('error_category','')
        if status in {'submitting','generating','upscaling','downloading','saving','needs_review'}:
            return f"Scene {scene.get('scene')}: {status}; reconcile the Flow result before another submission."
        if category == 'policy_rejection': return f"Scene {scene.get('scene')}: policy rejection requires review."
    return None


def command(job, name):
    python=sys.executable; sid=str(job['story_id']); root=Path(job['story_path'])
    if name == 'script': return [python,'-u',str(ROOT/'run_generate_story.py'),sid]
    if name == 'storyboard':
        cmd=[python,'-u',str(ROOT/'run_storyboard.py'),sid]
        if list((root/'prompts').glob('output_config_*.md')) and list((root/'scenes').glob('output_story_breakdown_*.md')):
            cmd.append('--resume')
            if (root/'prompts/prompt.txt').is_file(): cmd.append('--fill-prompt-gaps')
        return cmd
    if name.startswith('audio_'): return [python,'-u',str(ROOT/'run_elevenlabs.py'),sid,'--audio',name.removeprefix('audio_')]
    runner='run_flow_images.py' if name == 'images' else 'run_digen_videos.py'
    return [python,'-u',str(ROOT/runner),str(root)]


def publish(job):
    """Use existing Drupal status vocabulary; preserve last_job metadata."""
    try:
        from drupal_client import DrupalStoryClient
        client=DrupalStoryClient(timeout=10)
        story=client.get_story(job['story_id'])
        try: meta=json.loads(story.get('story_meta') or '{}')
        except (ValueError,TypeError): meta={}
        if not isinstance(meta,dict): meta={}
        meta['pipeline']={k:job[k] for k in ['job_id','status','stages','updated_at']}
        status=('storyboard_done' if job['status']=='completed' else 'stopped' if job['status']=='stopped'
                else 'failed' if job['status'] in {'failed','needs_attention'} else 'storyboard_running')
        client.update_story(job['story_id'],{'status':status,'story_meta':json.dumps(meta)})
    except Exception as exc:
        print(f'[watchdog] Drupal status sync pending: {type(exc).__name__}',flush=True)
        return False
    return True


def save_job(path,job):
    job['updated_at']=time.time();write(path,job)
    mirror=Path(job['story_path'])/'meta/pipeline-status.json'
    write(mirror,job)


def fail(stage,reason,now):
    stage['error']=reason;stage['pid']=None
    stage['status']='failed' if stage['attempts'] >= MAX_ATTEMPTS else 'retry_wait'
    stage['next_retry_at']=now+300


def advance(path,job,now,resource_busy=False,browser_busy=False,chrome_busy=None,firefox_busy=None):
    if chrome_busy is None: chrome_busy = browser_busy
    if firefox_busy is None: firefox_busy = False
    if job['status'] in TERMINAL: return
    for name,stage in job['stages'].items():
        if stage['status']=='skipped': continue
        report=validate(job,name);stage['validation']=report
        if stage['status']=='completed':
            if report['complete']: continue
            stage['status']='needs_attention';stage['error']='Previously completed output is now missing or invalid.'
        if stage['status'] in {'failed','needs_attention'}:
            job['status']='needs_attention';return
        if stage['status']=='running':
            result=read(stage['result'])
            alive=owned_process(stage)
            current=fingerprint(job,stage)
            if current != stage.get('fingerprint'):
                stage['fingerprint']=current;stage['last_progress_at']=now
            if result is None and alive:
                if now-stage['last_progress_at'] < STALE_SECONDS: continue
                terminate(stage);fail(stage,'No progress for five minutes; owned process stopped.',now)
                reason=review_reason(job,name)
                if reason: stage.update(status='needs_attention',error=reason)
                return
            if alive: continue # Flow/Digen can overlap on Chrome vs Firefox
            if report['complete'] and result and result.get('returncode')==0:
                stage.update(status='completed',pid=None,completed_at=now);continue
            if name == 'videos' and result and result.get('returncode')==0:
                images_report=validate(job,'images')
                if not images_report.get('complete'):
                    # Partial Digen catch-up while Flow is still generating.
                    stage.update(status='queued',pid=None)
                    stage['attempts']=max(0, int(stage.get('attempts') or 1)-1)
                    continue
            reason=review_reason(job,name)
            if reason:
                stage.update(status='needs_attention',pid=None,error=reason);job['status']='needs_attention';return
            orphan_lease = token_lease_held(stage.get('token'))
            busy = chrome_busy if name in CHROME_STAGES else firefox_busy if name in FIREFOX_STAGES else browser_busy
            if not orphan_lease and name in BROWSER_STAGES and resource_leased() and not busy:
                orphan_lease = True
            if orphan_lease:
                stage.update(status='needs_attention',error='Runner disappeared but a worker still holds the execution lease. Review before resuming.');job['status']='needs_attention';return
            fail(stage,'Process exited or disappeared before validated completion.',now)
            if stage['status']=='failed':job['status']='needs_attention'
            return
        # Existing complete scene sets may be adopted; audio needs a successful stage record.
        if report['complete'] and not name.startswith('audio_'):
            stage.update(status='completed',completed_at=now);continue
        if report.get('invalid') or report.get('duplicates'):
            stage.update(status='needs_attention',error='Invalid/duplicate output files need review.');job['status']='needs_attention';return
        reason=review_reason(job,name)
        if reason:stage.update(status='needs_attention',error=reason);job['status']='needs_attention';return
        if name in CHROME_STAGES and (chrome_busy or chrome_lock_held()):
            continue
        if name in FIREFOX_STAGES and (firefox_busy or firefox_lock_held()):
            continue
        if name == 'videos':
            images_report=validate(job,'images') or {}
            images_stage=job.get('stages',{}).get('images') or {}
            if int(images_report.get('completed') or 0) < MIN_IMAGES_FOR_VIDEOS:
                continue
            # Don't steal Firefox for a story that is only waiting on Chrome.
            if not images_report.get('complete') and images_stage.get('status') not in {'running','completed'}:
                continue
        if resource_busy or now < stage.get('next_retry_at',0):
            if name in BROWSER_STAGES:
                continue
            return
        if stage['attempts'] >= MAX_ATTEMPTS:
            stage.update(status='failed',error='Two retries exhausted.');job['status']='needs_attention';return
        if name == 'images':
            manifest_path=Path(job['story_path'])/'images/generation-manifest.json'
            manifest=read(manifest_path)
            if manifest:
                for scene in manifest.get('scenes',{}).values():
                    if scene.get('status') in {'failed','configuring'} and scene.get('error_category') != 'policy_rejection':
                        scene.update(status='queued',error_message=None)
                manifest.update(active_scene=None,lock_owner=None,control='running')
                write(manifest_path,manifest)
        token=uuid.uuid4().hex
        base=STATE/f"{job['story_id']}-{name}-{token}"
        stage.update(status='running',attempts=stage['attempts']+1,token=token,
                     log=str(base)+'.log',result=str(base)+'.result.json',last_progress_at=now)
        job['status']='running';stage['fingerprint']=fingerprint(job,stage)
        spec={'command':command(job,name),'result':stage['result'],'asset_root':job['asset_root'],'stage':name,'story_id':job['story_id']}
        write(str(base)+'.spec.json',spec)
        # Persist attempt BEFORE launching; a crash cannot reset the retry budget.
        save_job(path,job)
        with open(stage['log'],'ab',buffering=0) as log:
            proc=subprocess.Popen([sys.executable,'-u',str(Path(__file__).resolve()),'execute',token,str(base)+'.spec.json'],cwd=str(ROOT),stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env={**os.environ,'PIPELINE_STATE_DIR':str(STATE)})
        CHILDREN.append(proc)
        stage['pid']=proc.pid;save_job(path,job);return
    if any(s.get('status') in {'running','queued','retry_wait'} for s in job['stages'].values()):
        return
    job['status']='completed'


def job_paths():
    """Only story-<id>.json job files (exclude heartbeat / health sidecars)."""
    return sorted(p for p in STATE.glob('story-*.json') if re.fullmatch(r'story-\d+\.json', p.name))


def keep_awake(jobs):
    """Bridge watchdog polls and retry delays without keeping the display on."""
    if sys.platform != 'darwin' or not any(job['status'] not in TERMINAL for _, job in jobs):
        return
    CHILDREN.append(subprocess.Popen(
        ['/usr/bin/caffeinate', '-i', '-t', '660'],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    ))


def tick():
    CHILDREN[:] = [proc for proc in CHILDREN if proc.poll() is None]
    with locked():
        write(STATE/'watchdog-health.json',{'checked_at':time.time(),'interval_seconds':300})
        paths=job_paths()
        jobs=[(p,j) for p in paths if isinstance((j:=read(p)), dict) and isinstance(j.get('stages'), dict)]
        keep_awake(jobs)
        running=sum(1 for _p,j in jobs if job_has_owned_process(j))
        chrome=chrome_stage_owned(jobs) or chrome_lock_held()
        firefox=firefox_stage_owned(jobs) or firefox_lock_held()
        for path,job in jobs:
            own=job_has_owned_process(job)
            try: advance(path,job,time.time(),resource_busy=(running>=max_jobs() and not own),browser_busy=chrome,chrome_busy=chrome,firefox_busy=firefox)
            except Exception as exc:
                job['status']='needs_attention';job['error']=f'{type(exc).__name__}: {exc}'
            signature=hashlib.sha256(json.dumps({'status':job['status'],'stages':job['stages']},sort_keys=True).encode()).hexdigest()
            save_job(path,job)
            if signature != job.get('synced_signature'):
                job['drupal_synced']=publish(job)
                if job['drupal_synced']: job['synced_signature']=signature
                write(path,job)
            running=sum(1 for _p,j in jobs if job_has_owned_process(j))
            chrome=chrome_stage_owned(jobs) or chrome_lock_held()
            firefox=firefox_stage_owned(jobs) or firefox_lock_held()


def enqueue(args):
    from drupal_client import DrupalStoryClient
    from secrets import apply_asset_root_from_bundle
    from asset_store import story_folder
    from workspace import slugify, strip_html
    from audio_languages import parse_audio_languages
    client=DrupalStoryClient();story=client.get_story(args.story_id)
    bundle=client.get_bundle(args.story_id,pipeline='storyboard');apply_asset_root_from_bundle(bundle)
    title=story.get('title') or '';folder=story_folder(slugify(title),args.story_id,title,story.get('story_type') or 'general',ensure=True)
    if folder is None: raise ValueError('STORY_ASSET_ROOT must be configured.')
    names=[]
    if args.mode=='full':
        names.append('script')
        existing_script=strip_html(story.get('full_story') or '')
        script_path=folder/'script/FULL_STORY.txt'
        if existing_script and not script_path.is_file():
            script_path.parent.mkdir(parents=True,exist_ok=True)
            script_path.write_text(existing_script,encoding='utf-8')
    if args.mode != 'elevenlabs': names.append('storyboard')
    if args.audio or args.mode in {'full','elevenlabs'}:
        names += ['audio_'+lang for lang in parse_audio_languages(bundle)]
    if args.mode != 'elevenlabs': names += ['images','videos']
    path=STATE/f'story-{args.story_id}.json'
    with locked():
        existing=read(path)
        if existing:
            stages=existing.setdefault('stages', {})
            changed=False
            queued_names=[]
            for name in names:
                stage=stages.get(name)
                # Add stages the prior job never had (e.g. audio after storyboard-only).
                # Re-queue audio when CMS asks for elevenlabs again.
                should_queue = stage is None or (
                    args.mode == 'elevenlabs' and name.startswith('audio_')
                )
                if not should_queue:
                    continue
                stages[name]={'status':'queued','attempts':0}
                queued_names.append(name)
                changed=True
            if changed:
                existing['status']='queued'
                existing.pop('error', None)
                existing['updated_at']=time.time()
                save_job(path,existing)
                print(
                    f"Updated existing job {existing.get('job_id')}: queued {', '.join(queued_names)}. "
                    f"Use watchdog status {args.story_id}.",
                    flush=True,
                )
                job=existing
            else:
                print(
                    f"Existing job: {existing['status']}. Attempts retained. "
                    f"Use watchdog status {args.story_id}."
                )
                return
        else:
            stages={name:{'status':'queued','attempts':0} for name in names}
            for name,flag in [('images','FLOW_IMAGES'),('videos','DIGEN_VIDEOS')]:
                if name in stages and os.environ.get(flag,'1').lower() in {'0','false','no','off'}:
                    stages[name]['status']='skipped'
            job={'job_id':str(uuid.uuid4()),'story_id':args.story_id,'story_path':str(folder),
                 'asset_root':str(folder.parent.parent),'status':'queued','stages':stages,
                 'created_at':time.time()}
            save_job(path,job)
            print(
                f"Queued durable job {job['job_id']}; "
                f"initial attempt + at most two retries per stage.",
                flush=True,
            )
    tick()


def stop(story_id):
    with locked():
        path=STATE/f'story-{story_id}.json';job=read(path)
        if not job:return
        job['status']='stopped';save_job(path,job) # persist intention before signalling
        for stage in job['stages'].values():
            terminate(stage)
            if stage['status']=='running':stage['status']='stopped'
        save_job(path,job);publish(job)


def resume(story_id):
    with locked():
        path=STATE/f'story-{story_id}.json';job=read(path)
        if not job: raise ValueError('No managed job exists.')
        if job_has_owned_process(job): raise ValueError('This story already has a worker running.')
        if job['status']=='completed': raise ValueError('Job is already complete.')
        for name,stage in job['stages'].items():
            if stage['status'] in {'stopped','needs_attention','failed'}:
                if stage['attempts'] >= MAX_ATTEMPTS:
                    raise ValueError(f'{name}: two retries exhausted; resume cannot reset the budget.')
                reason=review_reason(job,name)
                if reason: raise ValueError(reason)
                stage.update(status='queued',pid=None,next_retry_at=0)
        job['status']='queued';save_job(path,job)
    tick()


def execute(token,spec_path):
    spec=read(spec_path)
    env=os.environ.copy();env.update(STORY_ASSET_ROOT=spec['asset_root'],PIPELINE_MANAGED='1',DEEPSEEK_API_MAX_RETRIES='1',STAGE_C_BATCH_RETRIES='6',SCENE_RETRIES='1')
    if spec['stage']=='storyboard':env.update(FLOW_IMAGES='0',DIGEN_VIDEOS='0')
    write(spec['result']+'.pid',{'pid':os.getpid(),'token':token})
    code=1
    STATE.mkdir(parents=True, exist_ok=True)
    lock_paths=[STATE / f'execute-{token}.lock']
    if spec.get('stage') in CHROME_STAGES:
        lock_paths.extend([STATE / 'chrome.lock', STATE / 'browser.lock'])
    elif spec.get('stage') in FIREFOX_STAGES:
        lock_paths.append(STATE / 'firefox.lock')
    lock_files=[]
    try:
        for path in lock_paths:
            handle=path.open('a')
            fcntl.flock(handle, fcntl.LOCK_EX)
            lock_files.append(handle)
        heartbeat=STATE/f"story-{spec.get('story_id','unknown')}.heartbeat.json"
        def report(state):
            write(heartbeat,{'state':state,'heartbeat_at':time.time(),'stage':spec['stage'],'token':token})
        try:
            inherited=tuple(handle.fileno() for handle in lock_files)
            with subprocess.Popen(spec['command'],cwd=str(ROOT),env=env,pass_fds=inherited) as proc:
                while True:
                    report('running')
                    try: code=proc.wait(timeout=20);break
                    except subprocess.TimeoutExpired: pass
        finally:
            report('completed' if code==0 else 'failed')
            write(spec['result'],{'returncode':code,'finished_at':time.time(),'token':token})
    finally:
        for handle in lock_files:
            handle.close()


def main():
    if len(sys.argv)>1 and sys.argv[1]=='execute':
        execute(sys.argv[2],sys.argv[3]);return
    from secrets import load_all_env
    load_all_env()
    parser=argparse.ArgumentParser(description=__doc__);subs=parser.add_subparsers(dest='action',required=True)
    p=subs.add_parser('enqueue');p.add_argument('mode',choices=['storyboard','full','elevenlabs']);p.add_argument('story_id',type=int);p.add_argument('--audio',action='store_true');p.add_argument('--wait',action='store_true')
    subs.add_parser('tick')
    for action in ['status','stop','resume']:
        p=subs.add_parser(action);p.add_argument('story_id',type=int)
    args=parser.parse_args()
    if args.action=='enqueue':
        enqueue(args)
        if args.wait:
            path=STATE/f'story-{args.story_id}.json'
            next_poll=time.monotonic()+300
            while True:
                if time.monotonic() >= next_poll:
                    tick();next_poll=time.monotonic()+300
                job=read(path,{})
                if job.get('status') in TERMINAL:
                    print(f"Pipeline {job['status']}; stage details: {path}",flush=True)
                    sys.exit(0 if job['status']=='completed' else 1)
                time.sleep(5)
    elif args.action=='tick':tick()
    elif args.action=='stop':stop(args.story_id)
    elif args.action=='resume':resume(args.story_id)
    else:print(json.dumps(read(STATE/f'story-{args.story_id}.json',{'error':'No managed job'}),indent=2))


if __name__=='__main__':main()
