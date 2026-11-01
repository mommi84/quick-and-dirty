#!/usr/bin/env python3
"""Turn a burst of hand-held eclipse photos into a centred, square, looping GIF.

The sun is located by fitting a circle to its limb: the blown-out disc is
thresholded, its outline extracted, and a least-squares circle fitted with
iterative trimming so the moon's bite (a chord, not an arc) drops out of the
fit. That gives a far steadier centre than a brightness centroid, which drifts
towards whichever side of the disc is still lit.

Frames are EXIF-rotated upright and rescaled to a common pixel scale before
cropping, so a shot saved at a lower resolution still matches the rest.

Usage:
    python3 make_loop.py SRC_DIR [-o OUT_DIR]
"""

import argparse
import glob
import os
import re

import numpy as np
from PIL import Image, ImageOps

# Pixel value at which the solar disc is considered blown out. The photos are
# heavily clipped, so the saturated region is bounded by the limb.
DISC_THRESHOLD = 250

# All frames are resampled so their long edge matches this, putting every shot
# on one pixel scale (the burst was taken at a single 23mm-equivalent focal
# length, so equal long edge means equal angular scale).
BASELINE_LONG_EDGE = 4000

# Square crop taken around the sun, in baseline pixels. The disc is ~300px
# across, so this leaves it a bit under a third of the frame.
CROP = 950

# Final GIF edge, and per-frame delay in ms.
SIZE = 600
DELAY = 150

# The photos carry plenty of sensor grain, which dithers the smooth halo
# gradients on its own. Adding Floyd-Steinberg on top measurably raised the
# error against the source frames *and* grew the file by ~17%, so leave it off.
DITHER = Image.NONE


def load_upright(path):
    """Open an image, apply its EXIF rotation, and normalise the pixel scale."""
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    scale = BASELINE_LONG_EDGE / max(im.size)
    if abs(scale - 1.0) > 1e-3:
        im = im.resize((round(im.width * scale), round(im.height * scale)),
                       Image.LANCZOS)
    return im, scale


def disc_outline(im):
    """Coordinates of the saturated disc's outline."""
    g = np.asarray(im.convert("L"))
    mask = g >= DISC_THRESHOLD
    if mask.sum() < 200:                      # thin crescent / dim frame
        mask = g >= max(int(g.max()) - 3, 1)
    inner = (mask
             & np.roll(mask, 1, 0) & np.roll(mask, -1, 0)
             & np.roll(mask, 1, 1) & np.roll(mask, -1, 1))
    ys, xs = np.nonzero(mask & ~inner)
    return xs.astype(np.float64), ys.astype(np.float64)


def fit_circle(x, y):
    """Algebraic least-squares circle fit."""
    sol, *_ = np.linalg.lstsq(np.c_[x, y, np.ones(len(x))],
                              x ** 2 + y ** 2, rcond=None)
    cx, cy = sol[0] / 2, sol[1] / 2
    return cx, cy, np.sqrt(sol[2] + cx ** 2 + cy ** 2)


def fit_limb(x, y, iters=6):
    """Fit the solar limb, trimming points that sit off the arc.

    The occluded edge is a chord and the lens flare spikes are outliers; both
    have large residuals against the true limb, so a few reweighted passes
    settle on the arc alone.
    """
    keep = np.ones(len(x), bool)
    cx, cy, r = fit_circle(x, y)
    for _ in range(iters):
        cx, cy, r = fit_circle(x[keep], y[keep])
        res = np.abs(np.hypot(x - cx, y - cy) - r)
        cut = max(3.0 * np.median(res[keep]), 0.02 * r)
        nxt = res < cut
        if nxt.sum() < 30:
            break
        keep = nxt
    return cx, cy, r, int(keep.sum()), len(x)


def sky_colour(im):
    """Median colour of the frame's border, used to pad short crops."""
    a = np.asarray(im)
    edge = np.concatenate([a[:8].reshape(-1, 3), a[-8:].reshape(-1, 3),
                           a[:, :8].reshape(-1, 3), a[:, -8:].reshape(-1, 3)])
    return tuple(int(v) for v in np.median(edge, axis=0))


def centred_crop(im, cx, cy, side):
    """Square crop with (cx, cy) exactly at its centre, padding if needed."""
    pad = side
    canvas = Image.new("RGB", (im.width + 2 * pad, im.height + 2 * pad),
                       sky_colour(im))
    canvas.paste(im, (pad, pad))
    left = int(round(cx + pad - side / 2))
    top = int(round(cy + pad - side / 2))
    return canvas.crop((left, top, left + side, top + side))


def to_gif(frames, path, delay=DELAY, boomerang=False):
    """Write a looping GIF sharing one palette across all frames.

    A per-frame palette makes a near-monochrome sequence like this shimmer, so
    the palette is derived once from every frame stacked together.
    """
    seq = frames + frames[-2:0:-1] if boomerang else frames
    strip = Image.new("RGB", (frames[0].width, frames[0].height * len(frames)))
    for i, f in enumerate(frames):
        strip.paste(f, (0, i * frames[0].height))
    palette = strip.quantize(colors=256, method=Image.MEDIANCUT)
    quantised = [f.quantize(palette=palette, dither=DITHER) for f in seq]
    quantised[0].save(path, save_all=True, append_images=quantised[1:],
                      duration=delay, loop=0, optimize=True, disposal=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help="directory of source photos")
    ap.add_argument("-o", "--out", default=".", help="output directory")
    ap.add_argument("--size", type=int, default=SIZE, help="GIF edge in px")
    ap.add_argument("--crop", type=int, default=CROP,
                    help="crop side in baseline px (smaller = tighter)")
    ap.add_argument("--delay", type=int, default=DELAY, help="frame delay in ms")
    args = ap.parse_args()

    paths = sorted(glob.glob(os.path.join(args.src, "*.jpg")),
                   key=lambda p: [int(t) for t in re.findall(r"\d+", os.path.basename(p))][-1:])
    if not paths:
        raise SystemExit(f"no .jpg files in {args.src}")

    os.makedirs(args.out, exist_ok=True)
    frames = []
    for path in paths:
        im, scale = load_upright(path)
        cx, cy, r, kept, total = fit_limb(*disc_outline(im))
        tile = centred_crop(im, cx, cy, args.crop)
        frames.append(tile.resize((args.size, args.size), Image.LANCZOS))
        print(f"{os.path.basename(path):32s} scale={scale:.3f} "
              f"centre=({cx:7.1f},{cy:7.1f}) r={r:5.1f} limb={kept}/{total}")

    loop = os.path.join(args.out, "eclipse-loop.gif")
    boom = os.path.join(args.out, "eclipse-loop-boomerang.gif")
    to_gif(frames, loop, args.delay)
    to_gif(frames, boom, args.delay, boomerang=True)
    for p in (loop, boom):
        print(f"wrote {p} ({os.path.getsize(p) / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
