#!/usr/bin/env python3
"""Generate a 3D-printable trophy: stepped base, front plaque with text, cup with handles.

Units are mm. Max width is 70 mm (the base). Three parts, all printed without supports:
base (black), cup, and the plaque (black plate, white text and border) which glues into
a pocket on the front of the base.
Usage: python award.py --text "WORLD'S\\nOKAYEST" --out .
"""
import argparse
import os

import numpy as np
import shapely.geometry as sg
import shapely.ops
import trimesh
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath

W, D = 70.0, 45.0           # base footprint (W is the max width)
BASE_H = 22.0               # main block height
TIER = (56.0, 34.0, 6.0)    # top tier w, d, h
PLAQUE = (58.0, 15.0, 1.6)  # plaque w, h, plate thickness (glued into a pocket on the base)
TEXT_RELIEF = 0.6           # white text/border height above the black plate
PEG_R, PEG_H = 4.0, 4.0     # peg on the base that locates the cup
POCKET = 1.0                # depth of the plaque pocket in the base
FIT = 0.2                   # clearance per side for parts that slot together
CUP_H = 70.0                # cup height above the base (the clef matches it)


def box(w, d, h, x=0, y=0, z=0):
    m = trimesh.creation.box((w, d, h))
    m.apply_translation((x, y, z + h / 2))
    return m


def revolve(profile, sections=128):
    """profile: list of (r, z), from the axis at the bottom round to the axis at the top."""
    return trimesh.creation.revolve(np.array(profile, float), sections=sections)


def text_mesh(text, height, depth):
    """Extruded text, centred on the origin in XY, extruded along +Z."""
    fp = FontProperties(family="DejaVu Sans", weight="bold")
    lines = text.split("\\n")
    polys = []
    for i, line in enumerate(lines):
        tp = TextPath((0, -i * 1.25), line, size=1.0, prop=fp)
        rings = [sg.Polygon(p) for p in tp.to_polygons() if len(p) > 2]
        # even-odd fill: holes (inside of O, A, ...) are rings contained in others
        rings.sort(key=lambda p: p.area, reverse=True)
        shapes = []
        for r in rings:
            for j, s in enumerate(shapes):
                if s.contains(r):
                    shapes[j] = s.difference(r)
                    break
            else:
                shapes.append(r.buffer(0))
        line_geom = shapely.ops.unary_union(shapes)
        minx, _, maxx, _ = line_geom.bounds
        polys.append(shapely.affinity.translate(line_geom, -(minx + maxx) / 2, 0))
    geom = shapely.ops.unary_union(polys)
    minx, miny, maxx, maxy = geom.bounds
    scale = height / (maxy - miny)
    geom = shapely.affinity.scale(geom, scale, scale, origin=(0, 0))
    geom = shapely.affinity.translate(geom, 0, -(miny + maxy) / 2 * scale)
    parts = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    return trimesh.util.concatenate(
        [trimesh.creation.extrude_polygon(p, depth) for p in parts]), geom.bounds


def handle(side, z0):
    """A flat handle in the XZ plane, shaped so it prints without support."""
    t = 4.0
    # all downward-facing edges are at 45 degrees; the inner edge is buried in the bowl
    outer = sg.Polygon([(0, -2), (4, -2), (19, 13), (19, 19), (14, 24), (0, 24)])
    inner = sg.Polygon([(11, 6), (15, 10), (15, 14), (11, 18)])
    shape = outer.difference(inner)
    m = trimesh.creation.extrude_polygon(shape, t)
    m.apply_translation((0, 0, -t / 2))
    # map 2D (x, y) -> world (x, z), extrusion -> y
    m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, (1, 0, 0)))
    m.apply_translation((10.0, 0, z0))
    if side < 0:
        m.apply_transform(trimesh.transformations.reflection_matrix((0, 0, 0), (1, 0, 0)))
    return m


def plaque_parts(text):
    """The label, lying flat with the text facing up: a black plate and white border + text."""
    pw, ph, pt = PLAQUE
    plate = box(pw, ph, pt)
    border = trimesh.boolean.difference([
        box(pw, ph, TEXT_RELIEF, z=pt),
        box(pw - 2.4, ph - 2.4, TEXT_RELIEF + 1, z=pt - 0.5),
    ])
    if not text:
        return plate, border
    txt, (minx, _, maxx, _) = text_mesh(text, ph - 6.0, TEXT_RELIEF)
    if maxx - minx > pw - 6:  # shrink long text to fit
        txt.apply_scale((pw - 6) / (maxx - minx))
        txt.apply_translation((0, 0, -txt.bounds[0][2]))
    txt.apply_translation((0, 0, pt))
    return plate, trimesh.boolean.union([border, txt])


def build(text):
    """Returns the printable parts, each in its print orientation, plus the plaque's placement."""
    top = BASE_H + TIER[2]
    pw, ph, pt = PLAQUE
    front = -(D - 2) / 2
    pz = 2.0 + (BASE_H - 2 - ph) / 2

    # base: stepped block, a pocket at the front for the plaque, a peg on top for the cup
    base = trimesh.boolean.union([
        box(W, D, 2.0),
        box(W - 2, D - 2, BASE_H - 2, z=2.0),
        box(*TIER, z=BASE_H),
        trimesh.creation.cylinder(radius=PEG_R, height=PEG_H, sections=64).apply_translation(
            (0, 0, top + PEG_H / 2)),
    ])
    pocket = box(pw + 2 * FIT, 2 * POCKET, ph + 2 * FIT, y=front, z=pz - FIT)
    base = trimesh.boolean.difference([base, pocket])

    # cup: foot, stem with knob, flared bowl; a socket underneath takes the peg
    cup = revolve([
        (0, 0), (15, 0), (15, 3), (11, 5), (5, 9),
        (4.5, 18), (8, 21), (8, 24), (4.5, 27),
        (4.5, 32), (6, 33),
        (21, 48), (22, 66), (23.5, CUP_H), (0, CUP_H),
    ])
    hollow = revolve([(0, 52), (19, 56), (20, 72), (0, 72)])
    socket = trimesh.creation.cylinder(radius=PEG_R + FIT, height=2 * (PEG_H + FIT), sections=64)
    handles = [handle(s, 44) for s in (1, -1)]
    cup = trimesh.boolean.difference([trimesh.boolean.union([cup, *handles]), hollow, socket])

    plate, label = plaque_parts(text)
    # flat plaque -> upright on the front of the base, text facing -Y, back in the pocket
    place = trimesh.transformations.rotation_matrix(np.pi / 2, (1, 0, 0))
    place[:3, 3] = (0, front + POCKET, pz + ph / 2)
    return {"base": base, "cup": cup, "plaque_black": plate, "plaque_white": label}, \
        {"cup": trimesh.transformations.translation_matrix((0, 0, top)),
         "plaque_black": place, "plaque_white": place}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", default="WORLD'S\\nOKAYEST", help="plaque text, \\n for a new line")
    ap.add_argument("--out", default=".", help="output directory")
    ap.add_argument("--assembled", action="store_true", help="also write the assembled award (for previews)")
    a = ap.parse_args()
    parts, placements = build(a.text)
    # single-extruder version of the label: print it, swap to white at the layer above the plate
    parts["plaque"] = trimesh.boolean.union([parts["plaque_black"], parts["plaque_white"]])
    # just the white frame (no text), to pair with plaque_black and add text in the slicer
    parts["plaque_frame"] = plaque_parts("")[1]
    for name, m in parts.items():
        path = os.path.join(a.out, f"award_{name}.stl")
        m.export(path)
        e = m.extents
        print(f"{path}: {e[0]:.1f} x {e[1]:.1f} x {e[2]:.1f} mm, watertight={m.is_watertight}")
    if a.assembled:
        for name, tf in placements.items():
            parts[name].apply_transform(tf)
        for name in ("base", "cup", "plaque_black", "plaque_white"):
            parts[name].export(os.path.join(a.out, f"assembled_{name}.stl"))
    print(f"plaque colour change: white from z = {PLAQUE[2]:.1f} mm")
