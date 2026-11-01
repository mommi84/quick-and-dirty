#!/usr/bin/env python3
"""The lady topper: an existing figure on a foot, swapping in for the cup on the common base.

One part: award_lady.stl scaled down and sunk into a foot, with the cup's socket underneath,
so it drops onto the base's peg. Prints standing up; the raised arms need a few tree supports.
Usage: python lady.py --out .
The output is award_lady_topper.stl, as award_lady.stl is the source model.
"""
import argparse
import os

import manifold3d
import numpy as np
import trimesh

from award import CUP_H, FIT, PEG_H, PEG_R, revolve

SOURCE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "award_lady.stl")
FOOT_H = 8.0                # foot height
COLLAR_R = 12.0             # top of the foot: wider than the clef's neck, to take both thighs
SINK = 4.0                  # the thighs are cut at a slant, so bury the whole cut in the foot
TOLERANCE = 0.02            # mm the surface may move when simplifying, well below a layer


def simplify(m):
    """Drop triangles the printer can't resolve, staying watertight (the source has 700k)."""
    mesh = manifold3d.Mesh(np.asarray(m.vertices, np.float32), np.asarray(m.faces, np.uint32))
    s = manifold3d.Manifold(mesh).simplify(TOLERANCE).to_mesh()
    return trimesh.Trimesh(s.vert_properties[:, :3], s.tri_verts)


def build(source=SOURCE):
    """One piece in print orientation (standing on its foot), which is also how it sits on the base."""
    lady = trimesh.load(source)
    lady.apply_translation((0, 0, -lady.bounds[0][2]))
    # the top lines up with the cup's rim, once the bottom is sunk into the foot
    lady.apply_scale((CUP_H - FOOT_H + SINK) / lady.extents[2])

    # centre the buried thighs on the foot, not the whole figure
    buried = lady.vertices[lady.vertices[:, 2] < SINK][:, :2]
    cx, cy = (buried.min(axis=0) + buried.max(axis=0)) / 2
    lady.apply_translation((-cx, -cy, FOOT_H - SINK))
    r = np.linalg.norm(buried - (cx, cy), axis=1).max()
    if r > COLLAR_R:
        raise SystemExit(f"the thighs reach r = {r:.1f}, past the foot's top at {COLLAR_R}")

    # same footprint and peg socket as the cup, widening into a collar instead of a stem
    foot = revolve([(0, 0), (15, 0), (15, 3), (COLLAR_R, 5), (COLLAR_R, FOOT_H), (0, FOOT_H)])
    socket = trimesh.creation.cylinder(radius=PEG_R + FIT, height=2 * (PEG_H + FIT), sections=64)
    return simplify(trimesh.boolean.difference([trimesh.boolean.union([foot, lady]), socket]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=SOURCE, help="the source figure")
    ap.add_argument("--out", default=".", help="output directory")
    ap.add_argument("--assembled", action="store_true", help="also write the assembled parts (for previews)")
    a = ap.parse_args()
    m = build(a.source)
    path = os.path.join(a.out, "award_lady_topper.stl")
    m.export(path)
    e = m.extents
    print(f"{path}: {e[0]:.1f} x {e[1]:.1f} x {e[2]:.1f} mm, watertight={m.is_watertight}")
    if a.assembled:
        from award import BASE_H, TIER
        m.apply_translation((0, 0, BASE_H + TIER[2]))
        m.export(os.path.join(a.out, "assembled_lady.stl"))
