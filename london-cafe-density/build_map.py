#!/usr/bin/env python3
"""Build a map of London constituencies by cafés per 10,000 residents.

Reads the REAL data produced by `fetch_data.py`:

* cafes.csv                     — café counts + Census 2021 population per
                                  2024 Westminster constituency
* london_constituencies.geojson — the matching boundary polygons

Computes the Caffeine Density Index (cafés per 10,000 residents), prints a
ranked leaderboard, and renders a self-contained interactive Leaflet
choropleth (index.html).

Zero dependencies. Pure standard library. Leaflet + the basemap tiles are
pulled from a CDN by the browser, so the generated map needs an internet
connection to render, but generating it does not.

If you haven't fetched the data yet:  python3 fetch_data.py
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "cafes.csv")
GEOJSON_PATH = os.path.join(HERE, "london_constituencies.geojson")
HTML_PATH = os.path.join(HERE, "index.html")

# Per 10,000 residents. Espresso-strength ramp: pale oat-milk -> ristretto.
# Stops are the upper bound for each colour (chosen from the real quantiles).
RAMP = [
    (3.0, "#f6e7d3"),   # decaf
    (4.0, "#e8c79b"),   # latte
    (5.5, "#d29b5b"),   # flat white
    (8.0, "#a86a32"),   # cortado
    (11.0, "#7a4a1e"),  # double espresso
    (9999, "#3a2412"),  # ristretto / dangerously caffeinated
]


def colour_for(density):
    for upper, col in RAMP:
        if density <= upper:
            return col
    return RAMP[-1][1]


def load_rows():
    if not os.path.exists(CSV_PATH):
        sys.exit("cafes.csv not found — run `python3 fetch_data.py` first.")
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(
            (line for line in f if not line.lstrip().startswith("#"))
        )
        for r in reader:
            pop = int(r["population"])
            cafes = int(r["cafes"])
            rows.append(
                {
                    "code": r["code"].strip(),
                    "constituency": r["constituency"].strip(),
                    "lat": float(r["lat"]),
                    "lon": float(r["lon"]),
                    "population": pop,
                    "cafes": cafes,
                    "density": cafes / pop * 10000.0,  # cafés per 10,000 people
                }
            )
    rows.sort(key=lambda x: x["density"], reverse=True)
    return rows


def print_leaderboard(rows):
    print("\n  ☕ THE CAFFEINE DENSITY INDEX — London constituencies ranked ☕")
    print("     (real data: OpenStreetMap cafés ÷ Census 2021 population)\n")
    print(f"  {'#':>2}  {'Constituency':37} {'Cafés':>6} {'Pop.':>8} {'per 10k':>8}")
    print("  " + "-" * 67)
    for i, r in enumerate(rows, 1):
        crown = " 👑" if i == 1 else ("  💀" if i == len(rows) else "")
        print(
            f"  {i:>2}  {r['constituency']:37.37} {r['cafes']:>6} "
            f"{r['population']:>8,} {r['density']:>8.1f}{crown}"
        )
    total_cafes = sum(r["cafes"] for r in rows)
    total_pop = sum(r["population"] for r in rows)
    print("  " + "-" * 67)
    print(
        f"  London total: {total_cafes:,} cafés · {total_pop:,} residents "
        f"· {total_cafes / total_pop * 10000:.1f} per 10,000\n"
    )


def build_html(rows):
    with open(GEOJSON_PATH, encoding="utf-8") as f:
        geojson = json.load(f)

    by_code = {r["code"]: (i + 1, r) for i, r in enumerate(rows)}
    # Decorate the GeoJSON features with the stats + colour the map needs.
    for feat in geojson["features"]:
        code = feat["properties"]["code"]
        rank, r = by_code[code]
        feat["properties"].update(
            {
                "rank": rank,
                "cafes": r["cafes"],
                "pop": r["population"],
                "density": round(r["density"], 2),
                "colour": colour_for(r["density"]),
            }
        )

    geo_json = json.dumps(geojson, separators=(",", ":"))
    total = len(rows)
    legend_rows = "".join(
        f'<i style="background:{col}"></i> &le; {up:.1f}<br>'
        for up, col in RAMP[:-1]
    ) + f'<i style="background:{RAMP[-1][1]}"></i> the danger zone<br>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>☕ London by Cafés per 10,000 People</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html, body {{ margin: 0; height: 100%; font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }}
  #map {{ height: 100%; width: 100%; background: #cfe3df; }}
  .banner {{
    position: absolute; top: 12px; left: 50%; transform: translateX(-50%);
    z-index: 1000; background: rgba(58,36,18,0.92); color: #f6e7d3;
    padding: 10px 18px; border-radius: 12px; text-align: center;
    box-shadow: 0 2px 10px rgba(0,0,0,0.3); max-width: 92%;
  }}
  .banner h1 {{ margin: 0; font-size: 17px; }}
  .banner p {{ margin: 4px 0 0; font-size: 12px; opacity: 0.85; }}
  .legend {{
    line-height: 20px; color: #3a2412; background: rgba(255,255,255,0.9);
    padding: 8px 10px; border-radius: 8px; font-size: 12px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.25);
  }}
  .legend i {{ width: 16px; height: 16px; float: left; margin-right: 8px; opacity: 0.95; border-radius: 3px; }}
  .legend b {{ display:block; margin-bottom: 4px; }}
  .leaflet-popup-content {{ font-size: 13px; }}
  .leaflet-popup-content .rank {{ font-weight: bold; color: #7a4a1e; }}
  .leaflet-tooltip.label {{ background: transparent; border: none; box-shadow: none; color: #2c1c10; font-weight: 600; }}
</style>
</head>
<body>
<div class="banner">
  <h1>☕ London, ranked by cafés per 10,000 residents</h1>
  <p>The Caffeine Density Index — now with real data. Darker = more dangerously caffeinated.</p>
</div>
<div id="map"></div>
<script>
  const GEO = {geo_json};
  const TOTAL = {total};

  const map = L.map('map', {{ scrollWheelZoom: true }}).setView([51.49, -0.08], 10);
  L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
    attribution: '&copy; OpenStreetMap &copy; CARTO · cafés: OSM · population: ONS Census 2021 · boundaries: ONS 2024',
    subdomains: 'abcd', maxZoom: 19
  }}).addTo(map);

  function style(f) {{
    return {{
      fillColor: f.properties.colour, weight: 1, color: '#fff',
      opacity: 1, fillOpacity: 0.82
    }};
  }}

  function onEach(f, layer) {{
    const p = f.properties;
    layer.bindPopup(
      `<span class="rank">#${{p.rank}} of ${{TOTAL}}</span><br>` +
      `<b>${{p.name}}</b><br>` +
      `<b>${{p.density.toFixed(1)}}</b> cafés per 10,000 residents<br>` +
      `${{p.cafes.toLocaleString()}} cafés · ${{p.pop.toLocaleString()}} residents`
    );
    layer.bindTooltip(`${{p.name}} — ${{p.density.toFixed(1)}}/10k`, {{ sticky: true }});
    layer.on({{
      mouseover: e => e.target.setStyle({{ weight: 2.5, color: '#2c1c10', fillOpacity: 0.92 }}),
      mouseout:  e => geo.resetStyle(e.target)
    }});
  }}

  const geo = L.geoJSON(GEO, {{ style: style, onEachFeature: onEach }}).addTo(map);
  map.fitBounds(geo.getBounds(), {{ padding: [10, 10] }});

  const legend = L.control({{ position: 'bottomright' }});
  legend.onAdd = function () {{
    const div = L.DomUtil.create('div', 'legend');
    div.innerHTML = '<b>Cafés per 10,000 residents</b>{legend_rows}';
    return div;
  }};
  legend.addTo(map);
</script>
</body>
</html>
"""
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    rows = load_rows()
    print_leaderboard(rows)
    build_html(rows)
    print(f"  🗺  Map written to {os.path.relpath(HTML_PATH, HERE)} "
          f"({len(rows)} constituencies). Open it in a browser.\n")


if __name__ == "__main__":
    main()
