#!/usr/bin/env python3
"""A treble-clef topper that swaps in for the cup on the common award base.

Two parts, both printed without supports: the clef (printed flat) and a stand that sits
on the base's peg. The clef's tab glues into a slot in the top of the stand.
Usage: python clef.py --out .
Needs a font with U+1D11E (FreeSerif: apt install fonts-freefont-ttf), or pass --font.
"""
import argparse
import os

import numpy as np
import shapely.geometry as sg
import shapely.ops
import trimesh
from matplotlib.font_manager import FontProperties
from matplotlib.path import Path
from matplotlib.textpath import TextPath

from award import CUP_H, FIT, PEG_H, PEG_R, box, revolve

FONTS = ["/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
         "/usr/share/fonts/opentype/freefont/FreeSerif.otf",
         "/Library/Fonts/FreeSerif.ttf"]
STAND_H = 12.0              # stand height
THICK = 6.0                 # clef thickness (its height as printed)
STROKE = 0.7                # mm added to every edge, so the thin strokes survive
CLEF_H = CUP_H - STAND_H - STROKE  # glyph height, so the top lines up with the cup's rim
TAB = (10.0, 6.0)           # tab under the clef: width, length (thickness is THICK)


def glyph(font, height):
    """The treble clef as a shapely geometry, scaled to `height`, bottom centre at the origin."""
    tp = TextPath((0, 0), "\U0001D11E", size=1.0, prop=FontProperties(fname=font))
    rings, ring = [], []
    for seg, code in tp.iter_bezier():  # sample the curves finely; to_polygons is too coarse
        if code == Path.MOVETO:
            if len(ring) > 2:
                rings.append(ring)
            ring = [tuple(seg.control_points[0])]
        else:
            ring += [tuple(p) for p in seg(np.linspace(0, 1, 12)[1:])]
    if len(ring) > 2:
        rings.append(ring)
    if not rings:
        raise SystemExit(f"{font} has no treble clef glyph")
    # even-odd fill: holes are rings contained in bigger ones
    polys = sorted((sg.Polygon(r).buffer(0) for r in rings), key=lambda p: p.area, reverse=True)
    shapes = []
    for p in polys:
        for i, s in enumerate(shapes):
            if s.contains(p):
                shapes[i] = s.difference(p)
                break
        else:
            shapes.append(p)
    g = shapely.ops.unary_union(shapes)
    minx, miny, maxx, maxy = g.bounds
    f = height / (maxy - miny)
    g = shapely.affinity.scale(g, f, f, origin=(0, 0))
    g = shapely.affinity.translate(g, -(minx + maxx) / 2 * f, -miny * f)
    return g.buffer(STROKE, join_style="round")


def build(font):
    g = glyph(font, CLEF_H)
    tw, tl = TAB
    # tab hangs below the clef's lowest point, overlapping it so they fuse
    tab = sg.box(-tw / 2, -tl, tw / 2, g.bounds[1] + STROKE + 3)
    shape = shapely.ops.unary_union([g, tab])
    clef = trimesh.creation.extrude_polygon(shape, THICK)
    clef.apply_translation((0, 0, -clef.bounds[0][2]))

    # stand: same foot as the cup, a short neck, slot on top, socket underneath for the peg
    stand = revolve([(0, 0), (15, 0), (15, 3), (11, 5), (7, 9), (7, STAND_H), (0, STAND_H)])
    slot = box(tw + 2 * FIT, THICK + 2 * FIT, tl + 1, z=STAND_H - tl)
    socket = trimesh.creation.cylinder(radius=PEG_R + FIT, height=2 * (PEG_H + FIT), sections=64)
    stand = trimesh.boolean.difference([stand, slot, socket])

    # clef as assembled: flat -> upright in the XZ plane, tab down in the slot
    place = trimesh.transformations.rotation_matrix(np.pi / 2, (1, 0, 0))
    place[:3, 3] = (0, THICK / 2, STAND_H)
    return {"clef": clef, "clef_stand": stand}, place


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", default=next((f for f in FONTS if os.path.exists(f)), None))
    ap.add_argument("--out", default=".", help="output directory")
    ap.add_argument("--assembled", action="store_true", help="also write the assembled parts (for previews)")
    a = ap.parse_args()
    if not a.font:
        raise SystemExit("no font with a treble clef found; install FreeSerif or pass --font")
    parts, place = build(a.font)
    for name, m in parts.items():
        path = os.path.join(a.out, f"award_{name}.stl")
        m.export(path)
        e = m.extents
        print(f"{path}: {e[0]:.1f} x {e[1]:.1f} x {e[2]:.1f} mm, watertight={m.is_watertight}")
    if a.assembled:
        from award import BASE_H, TIER
        top = BASE_H + TIER[2]
        parts["clef"].apply_transform(place)
        for m in parts.values():
            m.apply_translation((0, 0, top))
        for name, m in parts.items():
            m.export(os.path.join(a.out, f"assembled_{name}.stl"))
