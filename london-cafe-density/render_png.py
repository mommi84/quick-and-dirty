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

W,H=2200,1520
PAD=40; TOP=100
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
d.text((PAD,24), "London — cafés per 10,000 residents", font=font(40,True), fill=(44,28,16))
d.text((PAD,72), "Real data · OSM cafés ÷ ONS Census 2021 population · 75 Westminster constituencies (July 2024)",
        font=font(19), fill=(110,90,60))

# legend
lx,ly=W-320,TOP+20
d.rectangle([lx-14,ly-14,lx+260,ly+ (len(RAMP))*28+10], fill=(255,255,255,235), outline=(200,200,200,255))
d.text((lx,ly-10), "Cafés per 10,000", font=font(18,True), fill=(44,28,16))
leg=["≤ 3.0","≤ 4.0","≤ 5.5","≤ 8.0","≤ 11.0","the danger zone"]
for i,((u,c),lab) in enumerate(zip(RAMP,leg)):
    yy=ly+18+i*28
    d.rectangle([lx,yy,lx+22,yy+22], fill=hx(c), outline=(120,120,120))
    d.text((lx+32,yy+3), lab, font=font(16), fill=(50,40,30))

# centroid + polygon area (for ordering: big areas claim their spot first)
def centroid_area(g):
    best=None;ba=-1;tot=0.0
    for r in rings(g):
        a=cx=cy=0;n=len(r)
        for i in range(n):
            x0,y0=r[i];x1,y1=r[(i+1)%n];cr=x0*y1-x1*y0;a+=cr;cx+=(x0+x1)*cr;cy+=(y0+y1)*cr
        if abs(a)<1e-12: continue
        a*=.5; tot+=abs(a)
        if abs(a)>ba: ba=abs(a);best=(cx/(6*a),cy/(6*a))
    return best,tot
geomap={f["properties"]["code"]:f["geometry"] for f in geo["features"]}

# wrap long names so labels stay narrow in the crowded centre
def wrap(name):
    name=name.replace(",", "")
    words=name.split()
    if len(words)<=2: return [name]
    mid=(len(words)+1)//2
    return [" ".join(words[:mid])," ".join(words[mid:])]

fnt=font(15,True)
items=[]
for code,(name,cafes,pop) in rows.items():
    cen,area=centroid_area(geomap[code])
    px,py=proj(*cen)
    lines=wrap(name)
    w=max(d.textbbox((0,0),l,font=fnt)[2] for l in lines)
    h=len(lines)*18
    items.append({"px":px,"py":py,"w":w,"h":h,"lines":lines,"area":area})

# greedy declutter: largest constituencies place first; others nudge to avoid overlap
items.sort(key=lambda it:-it["area"])
def overlap(a,b):
    return not (a[2]<b[0] or b[2]<a[0] or a[3]<b[1] or b[3]<a[1])
placed=[]
# candidate offsets, spiralling outward
offsets=[(0,0)]
for r in range(1,9):
    step=14*r
    offsets+= [(0,-step),(0,step),(-step,0),(step,0),(-step,-step),(step,-step),(-step,step),(step,step)]
for it in items:
    chosen=None
    for dx,dy in offsets:
        cx,cy=it["px"]+dx,it["py"]+dy
        box=(cx-it["w"]/2-2, cy-it["h"]/2-1, cx+it["w"]/2+2, cy+it["h"]/2+1)
        if not any(overlap(box,p) for p in placed):
            chosen=(cx,cy,box);break
    if chosen is None:
        cx,cy=it["px"],it["py"]
        chosen=(cx,cy,(cx-it["w"]/2-2,cy-it["h"]/2-1,cx+it["w"]/2+2,cy+it["h"]/2+1))
    cx,cy,box=chosen
    placed.append(box)
    ly0=cy-it["h"]/2
    for i,line in enumerate(it["lines"]):
        d.text((cx,ly0+i*18+9), line, font=fnt, fill=(15,15,15), anchor="mm",
               stroke_width=3, stroke_fill=(255,255,255,235))

img.save("london_cafe_density.png")
print("saved", img.size, "labels", len(items))
