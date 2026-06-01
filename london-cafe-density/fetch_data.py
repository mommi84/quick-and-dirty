#!/usr/bin/env python3
"""Fetch REAL data for the London Café Density Map.

This replaces the lovingly-fabricated numbers with actual open data:

* Café locations  — OpenStreetMap via the Overpass API (`amenity=cafe`,
  every node and way inside Greater London).
* Boundaries      — ONS Open Geography Portal: the 75 Westminster
  Parliamentary Constituencies (July 2024) that make up London, as GeoJSON.
* Population       — ONS Census 2021 usual-resident population for those
  same 2024 constituencies, served via the Nomis API (dataset TS001).

Each café is assigned to a constituency by point-in-polygon, counts are
aggregated, and the script writes two files:

* cafes.csv                    — code, constituency, centroid, population, cafés
* london_constituencies.geojson — the boundary polygons (for the choropleth)

Run it whenever you want to refresh the numbers:

    $ python3 fetch_data.py

It needs an internet connection (it is talking to OSM and ONS). Pure standard
library — no pip installs.
"""
import csv
import json
import os
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "cafes.csv")
GEOJSON_PATH = os.path.join(HERE, "london_constituencies.geojson")

UA = "london-cafe-density-map/1.0 (https://github.com/mommi84/quick-and-dirty)"

# ONS Open Geography Portal (ArcGIS REST).
ONS = "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services"
LOOKUP_LAYER = ONS + "/WD24_PCON24_LAD24_UTLA24_UK_LU/FeatureServer/0/query"
BOUNDARY_LAYER = (
    ONS + "/Westminster_Parliamentary_Constituencies_July_2024_Boundaries_UK_BGC"
    "/FeatureServer/0/query"
)
# Nomis: Census 2021 TS001 (usual residents), geography TYPE172 = 2024 PCONs.
NOMIS = (
    "https://www.nomisweb.co.uk/api/v01/dataset/NM_2021_1.data.json"
    "?geography=TYPE172&c2021_restype_3=0&measures=20100"
    "&select=geography_code,obs_value"
)
OVERPASS = "https://overpass-api.de/api/interpreter"


def get_json(url, data=None, timeout=120):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001 - simple retry/backoff
            if attempt == 3:
                raise
            wait = 2 ** (attempt + 1)
            print(f"    …request failed ({e}); retrying in {wait}s")
            time.sleep(wait)


def london_constituency_codes():
    """The 75 PCON codes whose wards fall in a London borough (LAD = E09…)."""
    params = urllib.parse.urlencode(
        {
            "where": "LAD24CD LIKE 'E09%'",
            "outFields": "PCON24CD,PCON24NM",
            "returnDistinctValues": "true",
            "returnGeometry": "false",
            "f": "json",
        }
    )
    data = get_json(f"{LOOKUP_LAYER}?{params}")
    rows = {
        (f["attributes"]["PCON24CD"], f["attributes"]["PCON24NM"])
        for f in data["features"]
    }
    print(f"  • {len(rows)} London constituencies identified")
    return dict(sorted(rows))


def fetch_boundaries(codes):
    """GeoJSON polygons for the given PCON codes (generalised, clipped)."""
    in_clause = ",".join(f"'{c}'" for c in codes)
    params = urllib.parse.urlencode(
        {
            "where": f"PCON24CD IN ({in_clause})",
            "outFields": "PCON24CD,PCON24NM",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
        }
    )
    data = get_json(f"{BOUNDARY_LAYER}?{params}")
    print(f"  • {len(data['features'])} boundary polygons downloaded")
    return data


def fetch_population(codes):
    """Census 2021 usual-resident population, keyed by PCON code."""
    data = get_json(NOMIS)
    pop = {}
    for o in data["obs"]:
        pop[o["geography"]["geogcode"]] = int(o["obs_value"]["value"])
    result = {c: pop[c] for c in codes if c in pop}
    print(f"  • population matched for {len(result)}/{len(codes)} constituencies")
    return result


def fetch_cafes():
    """Every amenity=cafe in Greater London (Q84), as (lat, lon) points."""
    query = (
        "[out:json][timeout:180];area['wikidata'='Q84']->.a;"
        "(node['amenity'='cafe'](area.a);way['amenity'='cafe'](area.a););"
        "out center;"
    )
    data = get_json(
        OVERPASS, data=urllib.parse.urlencode({"data": query}).encode(), timeout=200
    )
    points = []
    for el in data["elements"]:
        if el["type"] == "node":
            points.append((el["lat"], el["lon"]))
        elif "center" in el:
            points.append((el["center"]["lat"], el["center"]["lon"]))
    print(f"  • {len(points)} cafés fetched from OpenStreetMap")
    return points


# ---- geometry helpers (pure python, no shapely) ---------------------------

def _rings(geom):
    """Yield every linear ring (list of [lon,lat]) of a (Multi)Polygon."""
    t = geom["type"]
    if t == "Polygon":
        for ring in geom["coordinates"]:
            yield ring
    elif t == "MultiPolygon":
        for poly in geom["coordinates"]:
            for ring in poly:
                yield ring


def _bbox(geom):
    xs, ys = [], []
    for ring in _rings(geom):
        for x, y in ring:
            xs.append(x)
            ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def _point_in_ring(x, y, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-18) + xi
        ):
            inside = not inside
        j = i
    return inside


def _point_in_polygon(x, y, geom):
    """For (Multi)Polygons: inside outer ring, not inside a hole.

    Each polygon's first ring is the exterior; subsequent rings are holes. We
    treat them per-polygon so that holes only subtract from their own polygon.
    """
    t = geom["type"]
    polys = geom["coordinates"] if t == "MultiPolygon" else [geom["coordinates"]]
    for poly in polys:
        if not poly:
            continue
        if _point_in_ring(x, y, poly[0]) and not any(
            _point_in_ring(x, y, hole) for hole in poly[1:]
        ):
            return True
    return False


def _centroid(geom):
    """Area-weighted centroid of the largest ring (good enough for a marker)."""
    best, best_area = None, -1.0
    for ring in _rings(geom):
        a = cx = cy = 0.0
        n = len(ring)
        for i in range(n):
            x0, y0 = ring[i]
            x1, y1 = ring[(i + 1) % n]
            cross = x0 * y1 - x1 * y0
            a += cross
            cx += (x0 + x1) * cross
            cy += (y0 + y1) * cross
        if abs(a) < 1e-12:
            continue
        a *= 0.5
        if abs(a) > best_area:
            best_area = abs(a)
            best = (cy / (6 * a), cx / (6 * a))  # (lat, lon)
    return best


def count_cafes(geojson, cafes):
    """Point-in-polygon: cafés per constituency, plus centroids."""
    feats = []
    for f in geojson["features"]:
        geom = f["geometry"]
        feats.append(
            {
                "code": f["properties"]["PCON24CD"],
                "name": f["properties"]["PCON24NM"],
                "geom": geom,
                "bbox": _bbox(geom),
                "centroid": _centroid(geom),
                "count": 0,
            }
        )
    for lat, lon in cafes:
        for fe in feats:
            minx, miny, maxx, maxy = fe["bbox"]
            if not (minx <= lon <= maxx and miny <= lat <= maxy):
                continue
            if _point_in_polygon(lon, lat, fe["geom"]):
                fe["count"] += 1
                break
    assigned = sum(fe["count"] for fe in feats)
    print(f"  • {assigned} cafés assigned to a constituency")
    return feats


def main():
    print("\nFetching real data for the London Café Density Map…\n")

    print("ONS Open Geography Portal:")
    codes = london_constituency_codes()
    geojson = fetch_boundaries(list(codes))

    print("Nomis (Census 2021):")
    population = fetch_population(list(codes))

    print("OpenStreetMap (Overpass):")
    cafes = fetch_cafes()

    print("Aggregating:")
    feats = count_cafes(geojson, cafes)

    rows = []
    for fe in feats:
        pop = population.get(fe["code"])
        if not pop or not fe["centroid"]:
            print(f"    !! skipping {fe['name']} (missing population/centroid)")
            continue
        lat, lon = fe["centroid"]
        rows.append(
            {
                "code": fe["code"],
                "constituency": fe["name"],
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "population": pop,
                "cafes": fe["count"],
            }
        )
    rows.sort(key=lambda r: r["cafes"] / r["population"], reverse=True)

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        f.write(
            "# London (75 Westminster constituencies, July 2024) by café density.\n"
            "# REAL DATA — regenerate with `python3 fetch_data.py`.\n"
            "#   cafes      : amenity=cafe in OpenStreetMap (Overpass), "
            "snapshot date varies.\n"
            "#   population : ONS Census 2021 usual residents (Nomis TS001).\n"
            "#   boundaries : ONS July 2024 constituencies -> "
            "london_constituencies.geojson\n"
        )
        w = csv.DictWriter(
            f, fieldnames=["code", "constituency", "lat", "lon", "population", "cafes"]
        )
        w.writeheader()
        w.writerows(rows)

    # Trim the GeoJSON to the properties we use, keep it tidy.
    for feat in geojson["features"]:
        p = feat["properties"]
        feat["properties"] = {"code": p["PCON24CD"], "name": p["PCON24NM"]}
    with open(GEOJSON_PATH, "w", encoding="utf-8") as f:
        json.dump(geojson, f, separators=(",", ":"))

    print(f"\n  ✅ wrote {os.path.relpath(CSV_PATH, HERE)} ({len(rows)} rows)")
    print(f"  ✅ wrote {os.path.relpath(GEOJSON_PATH, HERE)}")
    print("  Now run:  python3 build_map.py\n")


if __name__ == "__main__":
    main()
