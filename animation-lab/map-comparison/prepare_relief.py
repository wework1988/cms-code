"""Reproject the downloaded Natural Earth equirectangular raster to a local Mercator image."""
from pathlib import Path
import zipfile, math, io
from PIL import Image
root=Path(__file__).resolve().parent.parent
with zipfile.ZipFile(root/'assets/maps/relief-source.zip') as z:
    source=Image.open(io.BytesIO(z.read('NE2_50M_SR_W/NE2_50M_SR_W.tif'))).convert('RGB')
w,h=source.size
left,top,right,bottom=45,50,115,0
crop=source.crop((round((left+180)/360*w),round((90-top)/180*h),round((right+180)/360*w),round((90-bottom)/180*h)))
outw=2400
maxy=math.log(math.tan(math.pi/4+math.radians(top)/2))
outh=round(outw*maxy/math.radians(right-left))
crop=crop.resize((outw,crop.height),Image.Resampling.LANCZOS)
out=Image.new('RGB',(outw,outh))
for row in range(outh):
    my=maxy*(1-(row+.5)/outh)
    lat=math.degrees(2*math.atan(math.exp(my))-math.pi/2)
    sy=min(crop.height-1,max(0,round((top-lat)/(top-bottom)*crop.height)))
    out.paste(crop.crop((0,sy,outw,sy+1)),(0,row))
# Documentary grade: pull Natural Earth water toward dark navy while keeping land.
from PIL import ImageChops, ImageEnhance, ImageFilter
r,g,b=out.split()
mask=ImageChops.multiply(
    ImageChops.subtract(b,r.point(lambda x:x+8)).point(lambda p:255 if p>0 else 0),
    ImageChops.subtract(b,g.point(lambda x:x+2)).point(lambda p:255 if p>0 else 0),
)
mask=ImageChops.multiply(mask,b.point(lambda p:255 if 70<=p<=210 else 0)).filter(ImageFilter.GaussianBlur(1.2))
navy=Image.new('RGB',out.size,(14,26,46))
out=Image.composite(Image.blend(out,navy,.72),out,mask)
out=ImageEnhance.Contrast(out).enhance(1.08)
out=ImageEnhance.Color(out).enhance(1.05)
out.save(root/'assets/maps/south-asia-relief.jpg',quality=93,optimize=True)
print(out.size)
