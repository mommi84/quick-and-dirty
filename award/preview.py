#!/usr/bin/env python3
"""Render a preview PNG of the assembled award (base + plaque + a topper).

Usage: python preview.py cup preview.png
       python preview.py clef clef_preview.png
"""
import os
import sys

import matplotlib
import numpy as np
import trimesh

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

import award  # noqa: E402

BLACK, GOLD, WHITE = (0.12, 0.12, 0.13), (0.85, 0.65, 0.15), (0.97, 0.97, 0.97)


def scene(topper):
    parts, placements = award.build("WORLD'S\\nOKAYEST")
    top = award.BASE_H + award.TIER[2]
    if topper == "cup":
        t = parts["cup"]
    elif topper == "clef":
        import clef
        t = clef.build(next(f for f in clef.FONTS if os.path.exists(f)))
    else:
        raise SystemExit(f"unknown topper {topper!r}")
    t.apply_translation((0, 0, top))
    for name in ("plaque_black", "plaque_white"):
        parts[name].apply_transform(placements[name])
    return [(parts["base"], BLACK), (parts["plaque_black"], BLACK), (parts["plaque_white"], WHITE), (t, GOLD)]


def render(meshes, out):
    light = np.array([0.3, -0.6, 0.75])
    light /= np.linalg.norm(light)
    fig = plt.figure(figsize=(10, 6))
    for i, (el, az) in enumerate([(15, -60), (5, -90)]):
        ax = fig.add_subplot(1, 2, i + 1, projection="3d")
        tris, cols = [], []
        for m, c in meshes:
            shade = np.clip(m.face_normals @ light, 0, 1)[:, None] * 0.6 + 0.4
            tris.append(m.vertices[m.faces])
            cols.append(np.clip(np.array(c) * shade + (0.08 if c[0] < 0.5 else 0), 0, 1))
        ax.add_collection3d(Poly3DCollection(np.vstack(tris), facecolors=np.vstack(cols), linewidths=0))
        ax.set_xlim(-50, 50), ax.set_ylim(-50, 50), ax.set_zlim(0, 100)
        ax.set_box_aspect((1, 1, 1)), ax.view_init(el, az), ax.axis("off")
    plt.tight_layout()
    plt.savefig(out, dpi=110)


if __name__ == "__main__":
    render(scene(sys.argv[1]), sys.argv[2])
