"""Deterministic, offline map/timeline sample. Stream frames directly to FFmpeg."""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parent

def ease(v):
    v = max(0, min(1, v))
    return v * v * (3 - 2 * v)

def fonts():
    latin = os.environ.get('ANIMATION_LATIN_FONT', '/System/Library/Fonts/Supplemental/Arial.ttf')
    hindi = os.environ.get('ANIMATION_HINDI_FONT', '/System/Library/Fonts/Supplemental/Devanagari Sangam MN.ttc')
    return {key: ImageFont.truetype(path, size) for key, path, size in
            [('title', hindi, 38), ('city', hindi, 28), ('small', latin, 13), ('body', latin, 18), ('year', latin, 100)]}

TEXT = {}
TEXT_SIZES = {}

def prepare_text(cfg):
    # Render complex scripts once with macOS CoreText, then reuse their masks.
    cache = ROOT/'output/.text-cache'
    cache.mkdir(parents=True, exist_ok=True)
    binary = cache/'text-renderer'
    if not binary.exists() or binary.stat().st_mtime < (ROOT/'text.swift').stat().st_mtime:
        subprocess.run(['swiftc', '-module-cache-path', str(cache/'modules'), str(ROOT/'text.swift'), '-o', str(binary)], check=True)
    with tempfile.TemporaryDirectory() as temp:
        for n, (text, size) in enumerate([(cfg['title'],38)]+[(c['name'],c.get('font_size',28)) for c in cfg['cities']]):
            target = Path(temp)/f'{n}.png'
            subprocess.run([str(binary),text,str(size),str(target)],check=True)
            with Image.open(target) as source:
                TEXT[text] = source.getchannel('A').copy()
                TEXT_SIZES[text] = size

def hindi_text(im, position, text, color):
    mask = TEXT[text]
    im.paste(color, (round(position[0])-6,round(position[1])-6),mask)

def frame(cfg, t, f):
    w, h = cfg['width'], cfg['height']
    im = Image.new('RGB', (1280, 720), '#0b1520')
    d = ImageDraw.Draw(im)
    gold, muted = '#f0bd70', '#8198aa'
    zoom = 1 + .14 * ease(t / 7)
    def point(lon, lat):
        return (640 + (lon - 78.65) * 160 * zoom, 365 - (lat - 27.6) * 95 * zoom)
    # Coordinate grid, deliberately no invented administrative boundaries.
    for lon in range(75, 83):
        x, _ = point(lon, 27.6)
        d.line((x, 165, x, 560), fill='#1a2b39')
        d.text((x + 5, 540), f'{lon}° E', font=f['small'], fill='#3f596d')
    for lat in range(25, 31):
        _, y = point(78.65, lat)
        if 165 < y < 540:
            d.line((80, y, 1200, y), fill='#1a2b39')
            d.text((85, y + 5), f'{lat}° N', font=f['small'], fill='#3f596d')
    # Stylised river-like contour adds texture; explicitly schematic.
    river = [(point(76.4 + i*.07, 29.5 - i*.05 + .13*math.sin(i*.2))) for i in range(75)]
    d.line(river, fill='#24485b', width=3)
    positions = [point(c['lon'], c['lat']) for c in cfg['cities']]
    for route in cfg['connections']:
        p = ease((t-route['start'])/(route['end']-route['start']))
        if p <= 0:
            continue
        a, b = positions[route['from']], positions[route['to']]
        pts = []
        for i in range(81):
            u = p*i/80
            pts.append((a[0]+(b[0]-a[0])*u, a[1]+(b[1]-a[1])*u-50*math.sin(math.pi*u)))
        d.line(pts, fill='#493c2d', width=12)
        d.line(pts, fill=gold, width=3)
        x, y = pts[-1]
        d.ellipse((x-5,y-5,x+5,y+5), fill='#fff0d5')
    for c, (x,y) in zip(cfg['cities'], positions):
        p = ease((t-c['reveal'])/.65)
        if p <= 0:
            continue
        r = 12 + 12*((t-c['reveal']) % 1.5)/1.5
        d.ellipse((x-r,y-r,x+r,y+r), outline='#66563c', width=2)
        d.ellipse((x-7*p,y-7*p,x+7*p,y+7*p), fill=gold)
        ox, oy = c['label_offset']
        hindi_text(im,(x+ox,y+oy+10*(1-p)),c['name'],gold)
        d.text((x+ox,y+oy+34),c['english'],font=f['small'],fill=muted)
    d.rectangle((0,0,1280,150),fill='#0b1520')
    d.text((55,30),'HISTORY / LOCATION / CHRONOLOGY',font=f['small'],fill=gold)
    hindi_text(im,(55,56),cfg['title'],'#ecede5')
    d.text((57,112),cfg['subtitle'],font=f['body'],fill=muted)
    d.text((1000,30),'1857',font=f['year'],fill='#233848')
    d.rectangle((0,575,1280,720),fill='#101e2b')
    d.text((55,596),'NORTH INDIA · SCHEMATIC LOCATION STUDY',font=f['small'],fill=muted)
    d.line((70,646,1210,646),fill='#314553',width=2)
    d.line((70,646,70+1140*min(t/cfg['duration'],1),646),fill=gold,width=3)
    for c in cfg['cities']:
        x = 70+1140*c['reveal']/cfg['duration']
        color = gold if t >= c['reveal'] else '#536776'
        d.ellipse((x-5,641,x+5,651),fill=color)
        d.text((x-25,657),c['english'],font=f['small'],fill=color)
    d.text((55,699),'Illustrative spread of the uprising · Connections are not troop routes · No historical boundaries shown',font=f['small'],fill=muted)
    return im.resize((w,h),Image.Resampling.LANCZOS) if (w,h)!=(1280,720) else im

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config',type=Path,default=ROOT/'sample.json')
    parser.add_argument('--output',type=Path,default=ROOT/'output/1857-sample.mp4')
    args=parser.parse_args()
    cfg=json.loads(args.config.read_text())
    if cfg['duration']<=0 or cfg['fps']<=0 or any(cfg[k]<=0 or cfg[k]%2 for k in ('width','height')):
        raise ValueError('Use positive duration/FPS and positive even dimensions.')
    f=fonts()
    prepare_text(cfg)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    cmd=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s',f"{cfg['width']}x{cfg['height']}",'-r',str(cfg['fps']),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(args.output)]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
    try:
        for i in range(round(cfg['duration']*cfg['fps'])):
            proc.stdin.write(frame(cfg,i/cfg['fps'],f).tobytes())
    finally:
        proc.stdin.close()
        status=proc.wait()
    if status:
        raise RuntimeError(f'FFmpeg exited with status {status}')
    frame(cfg,8,f).save(args.output.with_suffix('.png'))
    print(f'Created {args.output.resolve()}')

if __name__=='__main__':
    main()
