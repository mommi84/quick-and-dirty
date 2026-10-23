#!/usr/bin/env python3
"""Generate a 3D-printable trophy: stepped base, front plaque with text, cup with handles.

Units are mm. Max width is 70 mm (the base). Prints upright, no supports.
Usage: python award.py --text "WORLD'S OKAYEST" --out award.stl
"""
import argparse

import numpy as np
import shapely.geometry as sg
import shapely.ops
import trimesh
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath

W, D = 70.0, 45.0           # base footprint (W is the max width)
BASE_H = 22.0               # main block height
TIER = (56.0, 34.0, 6.0)    # top tier w, d, h
PLAQUE = (58.0, 15.0, 1.2)  # plaque w, h, thickness (sits on the base front)
TEXT_RELIEF = 0.8


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


def build(text):
    # base: chamfer-ish stepped block + top tier
    base = trimesh.boolean.union([
        box(W, D, 2.0),
        box(W - 2, D - 2, BASE_H - 2, z=2.0),
        box(*TIER, z=BASE_H),
    ])
    top = BASE_H + TIER[2]

    # plaque on the front face (-Y), with raised border and raised text
    pw, ph, pt = PLAQUE
    front = -(D - 2) / 2
    pz = 2.0 + (BASE_H - 2 - ph) / 2
    plaque = box(pw, pt, ph, y=front - pt / 2, z=pz)
    border_outer = box(pw, pt + 0.6, ph, y=front - (pt + 0.6) / 2, z=pz)
    border_inner = box(pw - 2.4, 2.0, ph - 2.4, y=front - pt - 1.0, z=pz + 1.2)
    border = trimesh.boolean.difference([border_outer, border_inner])
    txt, (minx, _, maxx, _) = text_mesh(text, ph - 6.0, TEXT_RELIEF)
    if maxx - minx > pw - 6:  # shrink long text to fit
        f = (pw - 6) / (maxx - minx)
        txt.apply_scale(f)
    # text extrudes +Z in its own frame: rotate so it sticks out of the plaque towards -Y
    txt.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, (1, 0, 0)))
    txt.apply_translation((0, front - pt, pz + ph / 2))

    # cup: foot, stem with knob, flared bowl
    cup = revolve([
        (0, top), (15, top), (15, top + 3), (11, top + 5), (5, top + 9),
        (4.5, top + 18), (8, top + 21), (8, top + 24), (4.5, top + 27),
        (4.5, top + 32), (6, top + 33),
        (21, top + 48), (22, top + 66), (23.5, top + 70), (0, top + 70),
    ])
    hollow = revolve([(0, top + 52), (19, top + 56), (20, top + 72), (0, top + 72)])
    handles = [handle(s, top + 44) for s in (1, -1)]
    cup = trimesh.boolean.difference([trimesh.boolean.union([cup, *handles]), hollow])

    award = trimesh.boolean.union([base, plaque, border, txt, cup])
    award.apply_translation((0, 0, -award.bounds[0][2]))
    return award


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", default="WORLD'S\\nOKAYEST", help="plaque text, \\n for a new line")
    ap.add_argument("--out", default="award.stl")
    a = ap.parse_args()
    m = build(a.text)
    m.export(a.out)
    ext = m.extents
    print(f"{a.out}: {ext[0]:.1f} x {ext[1]:.1f} x {ext[2]:.1f} mm, watertight={m.is_watertight}, "
          f"volume={m.volume / 1000:.1f} cm3")
