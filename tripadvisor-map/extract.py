#!/usr/bin/env python3
"""Extract pinned cities + pin positions from a saved TripAdvisor TravelMap MHTML snapshot.

The TravelMap page renders two views of the user's pins:

  1. A scrollable list of city tiles (lazy-loaded ~10 at a time) with city names
     and photos. We harvest these as `cities_in_tiles` -- only the cities the
     user actually scrolled into view before saving will be present.

  2. Google Maps pin markers (`been_pin_icon_border.png` / `fave_pin_icon_border.png`)
     placed as absolutely-positioned divs inside a Google Maps OverlayView layer.
     They only carry pixel offsets (no names, no lat/lng metadata).

If you only get N tiles back but `counts.all` is larger, run
`dump-from-browser.js` in the page's DevTools console to scroll through and dump
the full list, then commit the resulting JSON.

Usage:
  python extract.py source.mht
"""
import json
import re
import sys
from pathlib import Path

PIN_IMG = "been_pin_icon_border.png"
FAVE_IMG = "fave_pin_icon_border.png"

# Pin DOM has the shape: <div style="...; left: -228px; top: 112px; z-index: 125;"><img ... src="...been_pin_icon_border.png" ...></div>
PIN_RE = re.compile(
    r'<div[^>]*style="[^"]*left:\s*(-?\d+)px[^"]*top:\s*(-?\d+)px[^"]*z-index:\s*(-?\d+)[^"]*"[^>]*>\s*'
    r'<img[^>]*src="https://static\.tacdn\.com/img2/travelmap/(been_pin|fave_pin)_icon_border\.png"'
)
CITY_TILE_RE = re.compile(r'<div class="name">([^<]+)</div>')
CENTER_RE = re.compile(r'maps\.google\.com/maps\?ll=(-?\d+\.\d+),(-?\d+\.\d+)&amp;z=(\d+)')
MATRIX_RE = re.compile(r'transform:\s*matrix\(1,\s*0,\s*0,\s*1,\s*(-?\d+),\s*(-?\d+)\)')
COUNTS_RE = re.compile(r'pin_counts pc_(all|been|want|fave)">\((\d+)\)')


def main(path):
    raw = Path(path).read_text(encoding="utf-8", errors="ignore")

    counts = {k: int(v) for k, v in COUNTS_RE.findall(raw)}
    center_match = CENTER_RE.search(raw)
    if not center_match:
        sys.exit("could not find map centre in snapshot")
    center_lat = float(center_match.group(1))
    center_lng = float(center_match.group(2))
    zoom = int(center_match.group(3))

    matrix_match = MATRIX_RE.search(raw)
    layer_dx, layer_dy = (int(matrix_match.group(1)), int(matrix_match.group(2))) if matrix_match else (0, 0)

    cities = sorted(set(CITY_TILE_RE.findall(raw)))

    pins = []
    for left, top, z, kind in PIN_RE.findall(raw):
        pins.append({
            "type": "fave" if kind == "fave_pin" else "been",
            "pixel_left": int(left),
            "pixel_top": int(top),
            "z_index": int(z),
        })

    out = {
        "source": path,
        "counts": counts,
        "map_view": {"center_lat": center_lat, "center_lng": center_lng,
                     "zoom": zoom, "layer_offset_px": [layer_dx, layer_dy]},
        "cities_in_tiles": cities,
        "pins": pins,
    }

    out_path = Path(path).parent / "extracted.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"counts:         {counts}")
    print(f"cities visible: {len(cities)} / {counts.get('all', '?')}")
    print(f"pins:           {len(pins)} ({sum(p['type']=='fave' for p in pins)} fave)")
    print(f"map centre:     ({center_lat}, {center_lng}) zoom {zoom}")
    print(f"wrote           {out_path}")
    if len(cities) < counts.get("all", 0):
        print()
        print(f"!! Only {len(cities)} of {counts['all']} city tiles were loaded in the")
        print( "   snapshot. Use dump-from-browser.js on the live page to grab them all.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "source.mht")
