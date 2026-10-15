#!/usr/bin/env python3
"""Offline parchment-style geographic camera animation, configured with JSON."""
import argparse
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
if Path(sys.prefix).resolve()!=(ROOT/'.venv').resolve() and (ROOT/'.venv/bin/python').exists():
    os.execv(str(ROOT/'.venv/bin/python'),[str(ROOT/'.venv/bin/python'),str(Path(__file__).resolve()),*sys.argv[1:]])

from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageFilter
import imageio_ffmpeg
import render as graphics
import cinematic

DATA=ROOT/'assets/maps/countries.geojson'
COS=math.cos(math.radians(23))

def project(point,center,span,width,height):
    return (width/2+(point[0]-center[0])*width/span,
            height/2-(point[1]-center[1])*width/span/COS)

def camera(config,t):
    z=config['zoom']
    u=graphics.ease((t-z['start'])/(z['end']-z['start']))
    a,b=config['start_view'],config['end_view']
    center=[a['center'][i]+(b['center'][i]-a['center'][i])*u for i in (0,1)]
    span=a['longitude_span']*(b['longitude_span']/a['longitude_span'])**u
    return center,span,u

def validate(c):
    if c.get('type')!='map_zoom':
        raise ValueError('Config type must be map_zoom')
    if not 1<=c['fps']<=60 or c['duration']<=0 or any(type(c[k]) is not int or c[k]<=0 or c[k]%2 for k in ('width','height')):
        raise ValueError('Use positive even dimensions, positive duration and FPS 1–60')
    if not 0<=c['zoom']['start']<c['zoom']['end']<c['duration']:
        raise ValueError('Zoom times must increase within video duration')
    if not c['zoom']['end']<=c['callout']['start']<c['duration']-1:
        raise ValueError('Callout must start after zoom, at least one second before the end')
    for view in ('start_view','end_view'):
        if len(c[view]['center'])!=2 or not 0<c[view]['longitude_span']<=180:
            raise ValueError('Views require [longitude,latitude] and span 0–180')

def load_features():
    result=[]
    for feature in json.loads(DATA.read_text())['features']:
        geom=feature['geometry']
        polygons=[geom['coordinates']] if geom['type']=='Polygon' else geom['coordinates']
        # Keep nearby countries only for this regional renderer.
        relevant=[]
        for polygon in polygons:
            outer=polygon[0]
            if any(45<p[0]<120 and -10<p[1]<55 for p in outer):
                relevant.append(polygon)
        if relevant:
            result.append((feature['properties']['ADMIN'],relevant))
    return result

def texture(size):
    rng=random.Random(1857)
    noise=Image.new('L',(320,180))
    noise.putdata([max(150,min(255,round(rng.gauss(225,13)))) for _ in range(320*180)])
    return noise.resize(size,Image.Resampling.BICUBIC).convert('RGB')

def compass(d,width,height):
    s=width/1920
    x,y=width-105*s,height-100*s
    r=48*s
    d.ellipse((x-r,y-r,x+r,y+r),outline='#675642',width=max(1,round(s)))
    for angle in range(0,360,45):
        a=math.radians(angle)
        tip=(x+math.sin(a)*r,y-math.cos(a)*r)
        left=(x+math.sin(a-.9)*r*.18,y-math.cos(a-.9)*r*.18)
        right=(x+math.sin(a+.9)*r*.18,y-math.cos(a+.9)*r*.18)
        d.polygon([tip,left,(x,y)],fill='#68513a')
        d.polygon([tip,right,(x,y)],fill='#cab887')
    d.text((x,y-r-15*s),'N',font=SMALL,fill='#594733',anchor='mm')

def frame(c,t,features,paper):
    w,h=c['width'],c['height']
    scale=w/1920
    center,span,u=camera(c,t)
    im=Image.new('RGB',(w,h),'#adb49b')
    d=ImageDraw.Draw(im)
    def pt(p):
        return project(p,center,span,w,h)
    # Fine engraved geographic graticule.
    for lon in range(40,125,5):
        x,_=pt((lon,0))
        d.line((x,0,x,h),fill='#929981',width=max(1,round(scale)))
    for lat in range(-10,60,5):
        _,y=pt((0,lat))
        d.line((0,y,w,y),fill='#929981',width=max(1,round(scale)))
    for name,polygons in features:
        fill='#d8be85'
        if name==c['first_country']:
            fill='#e4bd72' if u<.6 else '#d8be85'
        if name==c['target_country']:
            fill='#c98c57' if u>.8 else '#dfc68b'
        for polygon in polygons:
            outer=[pt(p) for p in polygon[0]]
            # Skip wholly offscreen polygons; Pillow clips intersecting ones.
            xs,ys=zip(*outer)
            if max(xs)<-10 or min(xs)>w+10 or max(ys)<-10 or min(ys)>h+10:
                continue
            d.polygon(outer,fill=fill)
            d.line(outer,fill='#594833',width=max(1,round(2*scale)),joint='curve')
            for hole in polygon[1:]:
                d.polygon([pt(p) for p in hole],fill='#adb49b')
    # Paper texture stays screen-stable so zooming does not magnify grain.
    im=Image.blend(im,ImageChops.multiply(im,paper),.38)
    d=ImageDraw.Draw(im)
    for label in c['labels']:
        x,y=pt(label['anchor'])
        if 80*scale<x<w-100*scale and 70*scale<y<h-60*scale:
            if label['name']=='BANGLADESH' and u>.6:
                continue
            d.text((x,y),label['name'],font=MAP_FONT,fill='#584531',anchor='mm',stroke_width=0)
    compass(d,w,h)
    d.rectangle((16*scale,16*scale,w-16*scale,h-16*scale),outline='#766344',width=max(1,round(2*scale)))
    d.rectangle((23*scale,23*scale,w-23*scale,h-23*scale),outline='#766344',width=max(1,round(scale)))
    if t<c['zoom']['start']:
        cinematic.lettering(im,(64,62),c['first_caption'],size=38,color='#463021',opacity=graphics.ease(t/.5))
    reveal=graphics.ease((t-c['callout']['start'])/.9)
    if reveal>0:
        anchor=pt(c['callout']['anchor'])
        # An animated curved leader connects a typeset callout to Bangladesh.
        start=(w*.17,h*.31)
        control=(w*.36,h*.16)
        pts=[]
        for i in range(81):
            v=reveal*i/80
            pts.append(((1-v)**2*start[0]+2*(1-v)*v*control[0]+v*v*anchor[0],
                        (1-v)**2*start[1]+2*(1-v)*v*control[1]+v*v*anchor[1]))
        d.line(pts,fill='#8b3428',width=max(2,round(4*scale)),joint='curve')
        if reveal>.97:
            angle=math.atan2(anchor[1]-pts[-2][1],anchor[0]-pts[-2][0])
            length=21*scale
            d.polygon([anchor,(anchor[0]-length*math.cos(angle-.4),anchor[1]-length*math.sin(angle-.4)),
                       (anchor[0]-length*math.cos(angle+.4),anchor[1]-length*math.sin(angle+.4))],fill='#8b3428')
        cinematic.lettering(im,(74,112),c['target_label'],size=40,color='#672e23',opacity=reveal)
        cinematic.lettering(im,(74,171),c['target_caption'],size=19,color='#4e3d29',opacity=reveal)
        r=7*scale
        d.ellipse((anchor[0]-r,anchor[1]-r,anchor[0]+r,anchor[1]+r),outline='#8b3428',width=max(2,round(2*scale)))
    return im

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=ROOT/'examples/india-bangladesh-map.json')
    p.add_argument('--output',type=Path,default=ROOT/'output/maps/india-bangladesh.mp4')
    a=p.parse_args()
    if not a.output.resolve().is_relative_to(ROOT):
        p.error('Keep output inside animation-lab')
    c=json.loads(a.config.read_text(encoding='utf-8'))
    validate(c)
    features=load_features()
    names={name for name,_ in features}
    if c['first_country'] not in names or c['target_country'] not in names:
        raise ValueError('Country name must match the bundled regional geographic data')
    graphics.prepare_text({'title':c['first_caption'],'cities':[{'name':s,'font_size':168} for s in (c['first_caption'],c['target_label'],c['target_caption'])]})
    global MAP_FONT,SMALL
    MAP_FONT=ImageFont.truetype('/System/Library/Fonts/Supplemental/Georgia.ttf',round(22*c['width']/1920))
    SMALL=ImageFont.truetype('/System/Library/Fonts/Supplemental/Georgia.ttf',round(16*c['width']/1920))
    paper=texture((c['width'],c['height']))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    tmp=a.output.with_name(a.output.stem+'.partial.mp4')
    cmd=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s',f"{c['width']}x{c['height']}",'-r',str(c['fps']),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(tmp)]
    print('Rendering parchment map → Bangladesh zoom → arrow and caption…',flush=True)
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
    try:
        for n in range(round(c['duration']*c['fps'])):
            proc.stdin.write(frame(c,n/c['fps'],features,paper).tobytes())
    finally:
        proc.stdin.close()
        status=proc.wait()
    if status:
        raise RuntimeError('FFmpeg failed')
    tmp.replace(a.output)
    frame(c,c['duration']-.1,features,paper).save(a.output.with_suffix('.png'))
    frame(c,1.5,features,paper).save(a.output.with_name(a.output.stem+'-start.png'))
    print(f'Created {a.output.resolve()}')

if __name__=='__main__':
    try:
        main()
    except (ValueError,OSError,RuntimeError) as error:
        sys.exit(f'Error: {error}')
