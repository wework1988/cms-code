#!/usr/bin/env python3
"""Story or animation plan → local MP4 clips. Reuses the animation-lab environment."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
# The user's normal python3 may not have the rendering dependencies.
if Path(sys.prefix).resolve() != (ROOT/'.venv').resolve() and (ROOT/'.venv/bin/python').exists():
    os.execv(str(ROOT/'.venv/bin/python'), [str(ROOT/'.venv/bin/python'), str(Path(__file__).resolve()), *sys.argv[1:]])

try:
    from PIL import Image, ImageDraw, ImageOps
    import imageio_ffmpeg
except ImportError:
    sys.exit('Install rendering dependencies first: .venv/bin/pip install -r requirements.txt')

import plan_animations as planner
import render as graphics
import cinematic
import flow_assets

GOLD = '#eabb75'
BG = '#0b1520'

def text(im, xy, value, color=GOLD):
    mask=graphics.TEXT[value]
    available=im.width-round(xy[0])-60
    if mask.width>available:
        mask=mask.resize((available,max(1,round(mask.height*available/mask.width))),Image.Resampling.LANCZOS)
    im.paste(color,(round(xy[0])-6,round(xy[1])-6),mask)

def title_bar(im, clip):
    d = ImageDraw.Draw(im)
    d.rectangle((0,0,1280,140),fill=BG)
    d.text((55,28), 'DOCUMENTARY / '+clip['type'].upper(),font=FONTS['small'],fill=GOLD)
    text(im,(55,65),clip['title'],'#f3eee4')

def timeline_frame(clip, t):
    im = Image.new('RGB',(1280,720),BG)
    d = ImageDraw.Draw(im)
    events = clip['events']
    # Windowed chronology keeps up to eight labels readable on a phone.
    active = max(i for i,e in enumerate(events) if e['reveal'] <= t)
    e = events[active]
    progress = graphics.ease((t-e['reveal'])/.8)
    d.rounded_rectangle((90,185,1190,455),radius=25,fill='#172c3b',outline='#38505e',width=2)
    d.text((125,208),f'{active+1:02d} / {len(events):02d}',font=FONTS['body'],fill=GOLD)
    text(im,(125,265+15*(1-progress)),e['label'])
    text(im,(125,340),e['caption'],'#f3eee4')
    d.line((110,535,1170,535),fill='#38505e',width=3)
    xs = [110+i*1060/(len(events)-1) for i in range(len(events))]
    x = xs[active]
    if active < len(events)-1:
        x += (xs[active+1]-x)*max(0,min(1,(t-e['reveal'])/(events[active+1]['reveal']-e['reveal'])))
    d.line((110,535,x,535),fill=GOLD,width=4)
    for i,xx in enumerate(xs):
        color = GOLD if i <= active else '#466171'
        d.ellipse((xx-9,526,xx+9,544),fill=color)
        d.text((xx-6,555),str(i+1),font=FONTS['body'],fill=color)
    d.text((55,650),'NARRATIVE SEQUENCE · Equal steps, not proportional historical time',font=FONTS['small'],fill='#849cac')
    d.text((55,677),'Editorial preview · Dates and claims require verification',font=FONTS['small'],fill='#849cac')
    title_bar(im,clip)
    return im

def illustrated_card(index):
    """Abstract architectural illustration, not an era-specific reconstruction."""
    im = Image.new('RGB',(1400,800),'#1b2d3a')
    d = ImageDraw.Draw(im)
    d.ellipse((940,80,1120,260),fill='#b68b55')
    d.polygon([(0,420),(240,270),(420,380),(670,240),(1000,400),(1400,240),(1400,800),(0,800)],fill='#283f49')
    base = 510
    for j in range(7):
        x = 150+j*155
        height = 140+(j%3)*35
        d.rectangle((x,base-height,x+85,base),fill='#8c785c')
        d.rectangle((x+12,base-height+10,x+73,base),fill='#3d4140')
        d.rectangle((x-8,base-height-12,x+93,base-height),fill='#bea073')
    d.polygon([(95,302),(695,190),(1295,302)],fill='#bfa274')
    d.rectangle((95,302,1295,325),fill='#675d4c')
    d.rectangle((60,base,1340,base+32),fill='#bfa274')
    d.rectangle((0,base+32,1400,800),fill='#263039')
    for y in range(570,800,50):
        d.line((0,y,1400,y),fill='#41505a',width=2)
    # Alternate cards retain the same visual identity.
    if index % 2:
        d.rounded_rectangle((570,360,810,520),radius=15,fill='#9d815c')
        d.ellipse((640,310,740,410),fill='#d5b47b')
    return im

def storyboard_frame(clip, t, images):
    cumulative = 0
    for i,scene in enumerate(clip['scenes']):
        if t < cumulative+scene['duration']:
            break
        cumulative += scene['duration']
    u = max(0,min(1,(t-cumulative)/scene['duration']))
    source = images[i]
    motion = scene['motion']
    # Pan/zoom are deliberately supported for flat artwork; parallax is a fallback.
    scale = 1.12
    if motion in ('slow_zoom_in','parallax'):
        scale = 1.03+.12*graphics.ease(u)
    elif motion == 'slow_zoom_out':
        scale = 1.15-.12*graphics.ease(u)
    resized = ImageOps.fit(source,(round(1280*scale),round(720*scale)),method=Image.Resampling.LANCZOS)
    spare = resized.width-1280
    x = spare/2
    if motion == 'pan_left':
        x = spare*(1-u)
    elif motion == 'pan_right':
        x = spare*u
    y = (resized.height-720)/2
    im = resized.crop((round(x),round(y),round(x)+1280,round(y)+720))
    # Fade each scene at its boundaries; durations do not gain overlap time.
    fade = min(1,(t-cumulative)/.3,(cumulative+scene['duration']-t)/.3)
    if clip['transition'] != 'cut':
        im = Image.blend(Image.new('RGB',im.size,BG),im,max(0,fade))
    d = ImageDraw.Draw(im)
    d.rectangle((0,575,1280,720),fill=BG)
    text(im,(55,600),scene['caption'],'#f3eee4')
    text(im,(55,658),scene['reconstruction_label'],'#a3b0b7')
    d.text((930,676),f'SCENE {i+1} / {len(images)}',font=FONTS['small'],fill=GOLD)
    title_bar(im,clip)
    return im

def encode(clip, images, path, fps, width, height, background=None):
    temporary = path.with_name(path.stem+'.partial.mp4')
    command = [imageio_ffmpeg.get_ffmpeg_exe(),'-y','-loglevel','error','-f','rawvideo',
        '-pix_fmt','rgb24','-s',f'{width}x{height}','-r',str(fps),'-i','-', '-an',
        '-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(temporary)]
    proc = subprocess.Popen(command,stdin=subprocess.PIPE)
    try:
        for n in range(round(clip['duration']*fps)):
            t = n/fps
            im = cinematic.timeline(clip,t,background,width,height) if clip['type']=='timeline' else cinematic.storyboard(clip,t,images,width,height)
            if (width,height) != im.size:
                im=im.resize((width,height),Image.Resampling.LANCZOS)
            proc.stdin.write(im.tobytes())
    finally:
        proc.stdin.close()
        status = proc.wait()
    if status:
        raise RuntimeError(f'FFmpeg failed for {clip["id"]}')
    temporary.replace(path)
    t=clip['duration']*.7
    preview = cinematic.timeline(clip,t,background,width,height) if clip['type']=='timeline' else cinematic.storyboard(clip,t,images,width,height)
    preview.save(path.with_suffix('.png'))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--story',type=Path)
    p.add_argument('--plan',type=Path,help='Use an existing plan, no DeepSeek call')
    p.add_argument('--env-file',type=Path,default=ROOT.parent/'story-pipeline-worker/.env')
    p.add_argument('--output-dir',type=Path,default=ROOT/'output/videos')
    p.add_argument('--images-dir',type=Path,help='Scene files: clip_01-01.png, clip_01-02.jpg etc.')
    p.add_argument('--image-provider',choices=('flow','preview'),default='flow')
    p.add_argument('--prepare-only',action='store_true',help='Prepare isolated Flow prompts; no image credits or rendering')
    p.add_argument('--style',default=flow_assets.STYLE)
    p.add_argument('--duration',type=float,default=10,help='Length of each clip; scene timings are scaled to fit')
    p.add_argument('--fps',type=int,default=30)
    p.add_argument('--width',type=int,default=1920)
    p.add_argument('--height',type=int,default=1080)
    p.add_argument('--model',default=os.environ.get('DEEPSEEK_MODEL','deepseek-flash'))
    args=p.parse_args()
    if not args.plan and not args.story:
        p.error('Provide --story or --plan')
    if args.story and not args.story.is_file():
        p.error(f'Story file does not exist: {args.story}. Try --story examples/iran-story.txt')
    if not 1 <= args.fps <= 60 or any(v<=0 or v%2 for v in (args.width,args.height)):
        p.error('Use FPS 1–60 and positive even dimensions')
    if not 6<=args.duration<=30:
        p.error('--duration must be 6–30 seconds')
    if not args.output_dir.resolve().is_relative_to(ROOT):
        p.error('--output-dir must stay inside animation-lab')
    args.output_dir.mkdir(parents=True,exist_ok=True)
    story=args.story.read_text(encoding='utf-8') if args.story else None
    if args.plan:
        plan=json.loads(args.plan.read_text(encoding='utf-8'))
    else:
        cache=args.output_dir/'animation-plan.json'
        digest=hashlib.sha256(story.encode('utf-8')).hexdigest()
        plan=json.loads(cache.read_text(encoding='utf-8')) if cache.exists() else None
        if not plan or plan.get('generation',{}).get('story_sha256')!=digest or plan.get('generation',{}).get('model')!=args.model or plan.get('generation',{}).get('requested_style')!=args.style:
            print('Selecting animation scenes with DeepSeek…',flush=True)
            plan=planner.generate(story,planner.load_key(args.env_file),args.model,style=args.style)
            plan['generation']['requested_style']=args.style
            planner.write_plan(cache,plan)
        else:
            print('Reusing cached plan.',flush=True)
    source=story if story is not None else '\n'.join(c['source_excerpt'] for c in plan['clips'])
    planner.validate(plan,source,len(plan['clips']))
    if any(not re.fullmatch(r'clip_[0-9]+',c['id']) for c in plan['clips']):
        raise ValueError('Clip IDs must use clip_01, clip_02 etc.')
    if args.prepare_only:
        job,_=flow_assets.prepare_job(plan,args.output_dir,args.style)
        print(f'Prepared Flow prompts: {job}/image-prompts/image-prompts-only.txt')
        return
    if not args.images_dir and args.image_provider=='flow' and any(c['type']=='storyboard' for c in plan['clips']):
        print('Generating realistic scene images with the isolated Flow adapter…',flush=True)
        args.images_dir=flow_assets.generate_images(plan,args.output_dir,style=args.style)
    for clip in plan['clips']:
        factor=args.duration/clip['duration']
        if clip['type']=='storyboard':
            for scene in clip['scenes']:
                scene['duration']*=factor
        else:
            for event in clip['events']:
                event['reveal']*=factor
        clip['duration']=args.duration
    texts=[c['title'] for c in plan['clips']]
    for clip in plan['clips']:
        if clip['type']=='timeline':
            texts += [v for e in clip['events'] for v in (e['label'],e['caption'])]
        else:
            texts += [v for s in clip['scenes'] for v in (s['caption'],s['reconstruction_label'])]
    print('Preparing Hindi text and rendering MP4 clips…',flush=True)
    graphics.prepare_text({'title':plan['title'],'cities':[{'name':s,'font_size':168} for s in dict.fromkeys(texts)]})
    global FONTS
    FONTS=graphics.fonts()
    manifest=[]
    background=None
    for clip in plan['clips']:
        images=[]
        mode='timeline'
        if clip['type']=='storyboard':
            mode='illustrated_cards'
            for i,scene in enumerate(clip['scenes']):
                candidates=[]
                if args.images_dir:
                    candidates += [args.images_dir/f'{clip["id"]}-{i+1:02d}{ext}' for ext in ('.png','.jpg','.jpeg','.webp')]
                asset=next((v for v in candidates if v.is_file()),None)
                if args.images_dir and not asset:
                    raise ValueError(f'Missing image {clip["id"]}-{i+1:02d} in {args.images_dir}')
                if asset:
                    with Image.open(asset) as img:
                        images.append(ImageOps.exif_transpose(img).convert('RGB'))
                    mode='scene_images'
                else:
                    images.append(illustrated_card(i))
            if mode=='illustrated_cards':
                print(f'{clip["id"]}: using abstract illustrated cards (not AI-generated historical artwork).',flush=True)
            if images:
                from PIL import ImageFilter
                background=images[0].filter(ImageFilter.GaussianBlur(12))
        target=args.output_dir/f'{clip["id"]}-{clip["type"]}.mp4'
        encode(clip,images,target,args.fps,args.width,args.height,background)
        manifest.append({'id':clip['id'],'video':str(target.resolve()),'duration':clip['duration'],
            'asset_mode':mode,'audio':None,'motion_note':'Full-frame pan/zoom, true cross-dissolves. Parallax uses zoom for flat images.',
            'timeline_spacing':'Equal narrative steps; not proportional historical time'})
        print(f'Created {target.resolve()}',flush=True)
    planner.write_plan(args.output_dir/'videos.json',{'clips':manifest})

if __name__=='__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(f'Error: {error}')
