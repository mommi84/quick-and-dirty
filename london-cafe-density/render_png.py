import csv, json
from PIL import Image, ImageDraw, ImageFont

HERE="."
RAMP=[(3.0,"#f6e7d3"),(4.0,"#e8c79b"),(5.5,"#d29b5b"),(8.0,"#a86a32"),(11.0,"#7a4a1e"),(9999,"#3a2412")]
def colour(d):
    for u,c in RAMP:
        if d<=u: return c
    return RAMP[-1][1]
def hx(c): return tuple(int(c[i:i+2],16) for i in (1,3,5))

# load data
rows={}
with open("cafes.csv") as f:
    for r in csv.DictReader(l for l in f if not l.startswith("#")):
        rows[r["code"]]=(r["constituency"],int(r["cafes"]),int(r["population"]))
geo=json.load(open("london_constituencies.geojson"))

# bounds
minx=miny=1e9; maxx=maxy=-1e9
def rings(g):
    if g["type"]=="Polygon":
        for r in g["coordinates"]: yield r
    else:
        for p in g["coordinates"]:
            for r in p: yield r
for f in geo["features"]:
    for r in rings(f["geometry"]):
        for x,y in r:
            minx=min(minx,x);maxx=max(maxx,x);miny=min(miny,y);maxy=max(maxy,y)

W,H=1600,1100
PAD=40; TOP=90
gw,gh=W-2*PAD, H-TOP-PAD
sx=gw/(maxx-minx); sy=gh/(maxy-miny); s=min(sx,sy)
ox=PAD+(gw-s*(maxx-minx))/2
oy=TOP+(gh-s*(maxy-miny))/2
def proj(x,y):
    return (ox+(x-minx)*s, oy+(maxy-y)*s)  # flip y

img=Image.new("RGB",(W,H),(245,243,239))
d=ImageDraw.Draw(img,"RGBA")

def font(sz,bold=False):
    paths=["/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf"%("-Bold" if bold else ""),
           "/usr/share/fonts/truetype/liberation/LiberationSans-%s.ttf"%("Bold" if bold else "Regular")]
    for p in paths:
        try: return ImageFont.truetype(p,sz)
        except: pass
    return ImageFont.load_default()

# draw polygons
for f in geo["features"]:
    code=f["properties"]["code"]
    name,cafes,pop=rows[code]
    dens=cafes/pop*10000
    col=hx(colour(dens))
    g=f["geometry"]
    polys=g["coordinates"] if g["type"]=="MultiPolygon" else [g["coordinates"]]
    for poly in polys:
        ext=[proj(x,y) for x,y in poly[0]]
        d.polygon(ext, fill=col+(230,), outline=(255,255,255,255))

# title
d.text((PAD,22), "London — cafés per 10,000 residents", font=font(34,True), fill=(44,28,16))
d.text((PAD,62), "Real data · OSM cafés ÷ ONS Census 2021 population · 75 Westminster constituencies (July 2024)",
        font=font(17), fill=(110,90,60))

# legend
lx,ly=W-300,TOP+20
d.rectangle([lx-14,ly-14,lx+250,ly+ (len(RAMP))*26+10], fill=(255,255,255,235), outline=(200,200,200,255))
d.text((lx,ly-10), "Cafés per 10,000", font=font(16,True), fill=(44,28,16))
labels=["≤ 3.0","≤ 4.0","≤ 5.5","≤ 8.0","≤ 11.0","the danger zone"]
for i,((u,c),lab) in enumerate(zip(RAMP,labels)):
    yy=ly+18+i*26
    d.rectangle([lx,yy,lx+20,yy+20], fill=hx(c), outline=(120,120,120))
    d.text((lx+30,yy+2), lab, font=font(15), fill=(50,40,30))

# annotate top 3 + bottom
ann=sorted(rows.items(), key=lambda kv: kv[1][1]/kv[1][2], reverse=True)
def centroid(g):
    best=None;ba=-1
    for r in rings(g):
        a=cx=cy=0;n=len(r)
        for i in range(n):
            x0,y0=r[i];x1,y1=r[(i+1)%n];cr=x0*y1-x1*y0;a+=cr;cx+=(x0+x1)*cr;cy+=(y0+y1)*cr
        if abs(a)<1e-12: continue
        a*=.5
        if abs(a)>ba: ba=abs(a);best=(cx/(6*a),cy/(6*a))
    return best
geomap={f["properties"]["code"]:f["geometry"] for f in geo["features"]}
for code,(name,cafes,pop) in [ann[0],ann[-1]]:
    cen=centroid(geomap[code]); px,py=proj(*cen)
    dens=cafes/pop*10000
    txt=f"{name}\n{dens:.1f}/10k"
    d.text((px,py), txt, font=font(13,True), fill=(20,20,20), anchor="mm", align="center",
           stroke_width=3, stroke_fill=(255,255,255,230))

img.save("london_cafe_density.png")
print("saved", img.size)
