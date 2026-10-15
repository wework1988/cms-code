"""Isolated Flow adapter. Reads existing agent code; writes only under animation-lab."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
import urllib.request

ROOT=Path(__file__).resolve().parent
STYLE='semi-realistic hand-drawn 2D graphic novel documentary, fine ink contours, realistic anatomy and perspective, textured materials, restrained earth tones, natural cinematic lighting'

def scene_prompt(scene, index, count, style=STYLE):
    shot=('wide establishing shot','medium narrative detail','close visual reveal')[min(index,2)]
    return f'''Create a single 16:9 cinematic documentary frame.
Visual treatment: {style}. Keep consistent lighting, palette, era and architecture across this sequence.
Narrative brief: {scene['image_prompt']}
Shot {index+1} of {count}: {shot}. Strong foreground/midground/background separation;
realistic worn surfaces, plausible costumes, architecture and props for the stated time and place.
Compose the main subject away from frame edges, with 10 percent crop-safe margins for camera movement.
Keep the lower left quiet for typeset captions added separately. Show one clear story action or visual idea.
No text, labels, watermark, UI, collage, split screen, plastic CGI, flat geometric placeholders,
fantasy architecture or anachronistic details. This is a reconstruction, not an archival photograph.
'''.replace('||','|')

def prepare_job(plan, output, style=STYLE):
    entries=[]
    for clip in plan['clips']:
        if clip['type']=='storyboard':
            for i,scene in enumerate(clip['scenes']):
                entries.append((clip['id'],i+1,scene_prompt(scene,i,len(clip['scenes']),style)))
    digest=hashlib.sha256(json.dumps(entries,ensure_ascii=False).encode()).hexdigest()[:16]
    stories=output.resolve()/'flow-stories'
    job=stories/f'animation-{digest}'
    prompts=job/'image-prompts/image-prompts-only.txt'
    prompts.parent.mkdir(parents=True,exist_ok=True)
    prompts.write_text('\n\n||\n\n'.join(f'Scene {n}. {entry[2]}' for n,entry in enumerate(entries,1)),encoding='utf-8')
    mapping=[{'scene':n,'clip_id':entry[0],'shot':entry[1]} for n,entry in enumerate(entries,1)]
    (job/'scene-map.json').write_text(json.dumps(mapping,indent=2),encoding='utf-8')
    return job,mapping

def snapshot_agent(source):
    """Copy a reviewed adapter snapshot; never execute from or write into source."""
    files=[source/'run-images.mjs',source/'prompt-recovery.mjs',*sorted((source/'helper').glob('*.py'))]
    digest=hashlib.sha256(b''.join(p.read_bytes() for p in files)).hexdigest()[:12]
    runtime=ROOT/'.runtime'/f'flow-{digest}'
    runtime.mkdir(parents=True,exist_ok=True)
    for original in files:
        target=runtime/original.relative_to(source)
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():
            shutil.copy2(original,target)
    # The isolated adapter only attaches to an existing signed-in browser.
    # It never clones profiles, stops Chrome, or launches the existing pipeline.
    runner=runtime/'run-images.mjs'
    body=(source/'run-images.mjs').read_text()
    body=body.replace('function ensureChromeWithLogin() {',
        'function ensureChromeWithLogin() { throw new Error("Open your signed-in Flow browser with CDP enabled before running animation-lab. Existing Chrome is not changed.");')
    # CDP sockets can keep Node alive after all images finish. Exit only this
    # isolated worker; do not close the user's Chrome browser.
    if 'main().catch((err) => {' not in body:
        raise RuntimeError('Flow runner entry point changed; isolated adapter needs review')
    body=body.replace('main().catch((err) => {',
        'main().then(() => process.exit(process.exitCode || 0)).catch((err) => {')
    start=body.index('async function fillPrompt(page, text) {')
    end=body.index('\nasync function clickGenerate(page)',start)
    body=body[:start]+body[end:]
    body="import { fillPrompt } from './flow_prompt.mjs';\n"+body
    # Keep the shebang first if the source has one.
    body=body.replace("import { fillPrompt } from './flow_prompt.mjs';\n#!/usr/bin/env node\n",
                      "#!/usr/bin/env node\nimport { fillPrompt } from './flow_prompt.mjs';\n")
    shutil.copy2(ROOT/'flow_prompt.mjs',runtime/'flow_prompt.mjs')
    runner.write_text(body)
    modules=source/'node_modules'
    if not (modules/'playwright').exists():
        modules=source.parent/'playright-automation/node_modules'
    if not (modules/'playwright').exists():
        raise RuntimeError('Existing Playwright installation not found; install it in animation-lab/.runtime first.')
    link=runtime/'node_modules'
    if not link.exists():
        link.symlink_to(modules.resolve(),target_is_directory=True)
    return runtime

def collect_images(job,mapping):
    assets=job/'animation-assets'
    assets.mkdir(exist_ok=True)
    for entry in mapping:
        source=next((job/'images'/f'{entry["scene"]:03d}{ext}' for ext in ('.png','.jpg','.jpeg','.webp')
                     if (job/'images'/f'{entry["scene"]:03d}{ext}').is_file()),None)
        if source is None:
            raise RuntimeError(f'Flow did not produce scene {entry["scene"]}. Resume the same command after resolving login/quota errors.')
        target=assets/f'{entry["clip_id"]}-{entry["shot"]:02d}{source.suffix}'
        shutil.copy2(source,target)
    return assets

def generate_images(plan,output,source=None,style=STYLE):
    job,mapping=prepare_job(plan,output,style)
    try:
        assets=collect_images(job,mapping)
        print('Reusing completed Flow images; no new generation needed.',flush=True)
        return assets
    except RuntimeError:
        pass
    source=source or ROOT.parent/'flow-image-agent'
    runtime=snapshot_agent(source)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        port=sock.getsockname()[1]
    config={'host':'127.0.0.1','port':port,'story_roots':[str(job.parent)],
        'token_file':str(runtime/'.local/pairing-token'),'state_dir':str(runtime/'.local/state'),
        'model':'Nano Banana 2.1','aspect_ratio':'16:9','outputs_per_prompt':1,
        'download_variant':'2K Upscaled','min_landscape_width':2048,'aspect_tolerance':.08}
    cfg=runtime/'config.json'
    cfg.write_text(json.dumps(config,indent=2))
    env=os.environ.copy()
    env.pop('STORY_ASSET_ROOT',None)
    env.pop('FLOW_PROJECT_URL',None)
    env['PATH']=f'{ROOT}/.venv/bin:/opt/homebrew/bin:/usr/local/bin:'+env.get('PATH','')
    url=f'http://127.0.0.1:{port}'
    log=job/'helper.log'
    with log.open('a') as logs:
        helper=subprocess.Popen([str(ROOT/'.venv/bin/python'),str(runtime/'helper/server.py'),'--config',str(cfg)],stdout=logs,stderr=logs,env=env,cwd=runtime)
        try:
            for _ in range(40):
                if helper.poll() is not None:
                    raise RuntimeError(f'Isolated Flow helper failed; inspect {log}')
                try:
                    with urllib.request.urlopen(url+'/health',timeout=.5) as response:
                        if response.status==200:
                            break
                except OSError:
                    time.sleep(.25)
            else:
                raise RuntimeError(f'Isolated Flow helper did not start; inspect {log}')
            node=shutil.which('node',path=env['PATH'])
            if not node:
                raise RuntimeError('Node.js is required for the Flow adapter')
            subprocess.run([node,str(runtime/'run-images.mjs'),job.name,'--all','--helper',url],env=env,cwd=runtime,check=True)
        finally:
            helper.terminate()
            try:
                helper.wait(timeout=5)
            except subprocess.TimeoutExpired:
                helper.kill()
                helper.wait()
    return collect_images(job,mapping)
