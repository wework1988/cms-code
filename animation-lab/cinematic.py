"""Full-frame documentary compositions and true scene dissolves."""
from PIL import Image, ImageDraw, ImageOps, ImageFilter
import render as graphics

GOLD='#d9b887'
WHITE='#f4efe6'

def lettering(im,xy,value,size=38,color=WHITE,opacity=1):
    mask=graphics.TEXT[value]
    scale=im.width/1280
    target_height=max(1,round(mask.height*size/graphics.TEXT_SIZES.get(value,28)*scale))
    target_width=max(1,round(mask.width*target_height/mask.height))
    available=round(im.width-xy[0]*scale-60*scale)
    if target_width>available:
        target_height=max(1,round(target_height*available/target_width))
        target_width=available
    mask=mask.resize((target_width,target_height),Image.Resampling.LANCZOS)
    if opacity<1:
        mask=mask.point(lambda p:round(p*max(0,opacity)))
    im.paste(color,(round(xy[0]*scale),round(xy[1]*scale)),mask)

def camera(source,motion,u,width,height):
    u=graphics.ease(max(0,min(1,u)))
    zoom=1.03+.065*u
    if motion=='slow_zoom_out':
        zoom=1.095-.065*u
    if motion in ('pan_left','pan_right'):
        zoom=1.07
    rw,rh=round(width*zoom),round(height*zoom)
    image=ImageOps.fit(source,(rw,rh),method=Image.Resampling.LANCZOS)
    x=(rw-width)/2
    if motion=='pan_left':
        x=(rw-width)*(1-u)
    elif motion=='pan_right':
        x=(rw-width)*u
    y=(rh-height)/2
    return image.crop((round(x),round(y),round(x)+width,round(y)+height))

def shade(im):
    # Transparent lower-third gradient preserves the full picture.
    gradient=Image.new('RGBA',(1,im.height))
    d=ImageDraw.Draw(gradient)
    for y in range(im.height):
        a=round(175*graphics.ease((y/im.height-.54)/.46))
        d.point((0,y),fill=(7,10,13,a))
    return Image.alpha_composite(im.convert('RGBA'),gradient.resize(im.size)).convert('RGB')

def storyboard(clip,t,images,width,height):
    start=0
    for i,scene in enumerate(clip['scenes']):
        end=start+scene['duration']
        if t<end:
            break
        start=end
    elapsed=t-start
    im=camera(images[i],scene['motion'],elapsed/scene['duration'],width,height)
    transition=.65
    remaining=end-t
    if clip['transition']=='crossfade' and i+1<len(images) and remaining<transition:
        next_scene=clip['scenes'][i+1]
        next_image=camera(images[i+1],next_scene['motion'],0,width,height)
        im=Image.blend(im,next_image,graphics.ease(1-remaining/transition))
    im=shade(im)
    opacity=graphics.ease(elapsed/.65)
    if i+1<len(images):
        opacity*=graphics.ease(remaining/transition)
    lettering(im,(64,596),scene['caption'],size=36,opacity=opacity)
    lettering(im,(65,671),scene['reconstruction_label'],size=13,color='#beb7ab',opacity=opacity*.9)
    scale=width/1280
    d=ImageDraw.Draw(im)
    if opacity>0:
        d.line((64*scale,580*scale,106*scale,580*scale),fill=GOLD,width=max(1,round(2*scale)))
    fade=min(graphics.ease(t/.4),graphics.ease((clip['duration']-t)/.4))
    return Image.blend(Image.new('RGB',im.size,'#090b0e'),im,fade)

def timeline(clip,t,background,width,height):
    if background:
        im=ImageOps.fit(background,(width,height),method=Image.Resampling.LANCZOS)
        im=Image.blend(im,Image.new('RGB',im.size,'#080c10'),.77)
    else:
        im=Image.new('RGB',(width,height),'#10191f')
    events=clip['events']
    active=max(i for i,e in enumerate(events) if e['reveal']<=t)
    event=events[active]
    opacity=graphics.ease((t-event['reveal'])/.5)
    lettering(im,(65,57),clip['title'],size=22,color='#bbb5aa')
    size=90 if event['label'].isdigit() else 54
    lettering(im,(95,255),event['label'],size=size,color=GOLD,opacity=opacity)
    lettering(im,(98,385),event['caption'],size=32,opacity=opacity)
    scale=width/1280
    d=ImageDraw.Draw(im)
    xs=[100+i*1080/(len(events)-1) for i in range(len(events))]
    d.line((xs[0]*scale,550*scale,xs[-1]*scale,550*scale),fill='#52606a',width=max(1,round(scale)))
    x=xs[active]
    if active+1<len(events):
        x+=(xs[active+1]-x)*max(0,min(1,(t-event['reveal'])/(events[active+1]['reveal']-event['reveal'])))
    d.line((xs[0]*scale,550*scale,x*scale,550*scale),fill=GOLD,width=max(1,round(2*scale)))
    for i,xx in enumerate(xs):
        r=(6 if i==active else 3)*scale
        d.ellipse((xx*scale-r,550*scale-r,xx*scale+r,550*scale+r),fill=GOLD if i<=active else '#52606a')
    return im
