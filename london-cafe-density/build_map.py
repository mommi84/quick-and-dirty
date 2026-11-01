#!/usr/bin/env python3
"""Build a tongue-in-cheek map of London constituencies by cafés per 100 people.

Reads cafes.csv, computes the all-important Caffeine Density Index (cafés per
100 residents), and spits out a self-contained interactive Leaflet map
(index.html) plus a ranked leaderboard on stdout.

Zero dependencies. Pure standard library. Leaflet is pulled from a CDN by the
browser, so the generated map needs an internet connection to render tiles, but
generating it does not.
"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "cafes.csv")
HTML_PATH = os.path.join(HERE, "index.html")

# Espresso-strength colour ramp: pale oat-milk -> ristretto. Stops are the
# upper bound (cafés per 100 people) for each colour.
RAMP = [
    (0.18, "#f6e7d3"),  # decaf
    (0.22, "#e8c79b"),  # latte
    (0.28, "#d29b5b"),  # flat white
    (0.34, "#a86a32"),  # cortado
    (0.42, "#7a4a1e"),  # double espresso
    (9.99, "#3a2412"),  # ristretto / dangerously caffeinated
]


def colour_for(density):
    for upper, col in RAMP:
        if density <= upper:
            return col
    return RAMP[-1][1]


def load_rows():
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(
            (line for line in f if not line.lstrip().startswith("#"))
        )
        for r in reader:
            pop = int(r["population"])
            cafes = int(r["cafes"])
            density = cafes / pop * 100.0  # cafés per 100 people
            rows.append(
                {
                    "constituency": r["constituency"].strip(),
                    "lat": float(r["lat"]),
                    "lon": float(r["lon"]),
                    "population": pop,
                    "cafes": cafes,
                    "density": density,
                    "quip": r["quip"].strip(),
                }
            )
    rows.sort(key=lambda x: x["density"], reverse=True)
    return rows


def print_leaderboard(rows):
    print("\n  ☕ THE CAFFEINE DENSITY INDEX — London constituencies ranked ☕\n")
    print(f"  {'#':>2}  {'Constituency':37} {'Cafés':>6} {'Pop.':>8}  {'per 100':>8}")
    print("  " + "-" * 67)
    for i, r in enumerate(rows, 1):
        crown = " 👑" if i == 1 else ("  💀" if i == len(rows) else "")
        print(
            f"  {i:>2}  {r['constituency']:37.37} {r['cafes']:>6} "
            f"{r['population']:>8,} {r['density']:>8.2f}{crown}"
        )
    print()


def build_html(rows):
    features = [
        {
            "name": r["constituency"],
            "lat": r["lat"],
            "lon": r["lon"],
            "cafes": r["cafes"],
            "pop": r["population"],
            "density": round(r["density"], 3),
            "colour": colour_for(r["density"]),
            "quip": r["quip"],
            "rank": i + 1,
        }
        for i, r in enumerate(rows)
    ]
    data_json = json.dumps(features)
    total = len(rows)
    legend_rows = "".join(
        f'<i style="background:{col}"></i> &le; {up:.2f}<br>'
        for up, col in RAMP[:-1]
    ) + f'<i style="background:{RAMP[-1][1]}"></i> the danger zone<br>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>☕ London by Cafés per 100 People</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html, body {{ margin: 0; height: 100%; font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }}
  #map {{ height: 100%; width: 100%; background: #cfe3df; }}
  .banner {{
    position: absolute; top: 12px; left: 50%; transform: translateX(-50%);
    z-index: 1000; background: rgba(58,36,18,0.92); color: #f6e7d3;
    padding: 10px 18px; border-radius: 12px; text-align: center;
    box-shadow: 0 2px 10px rgba(0,0,0,0.3); max-width: 90%;
  }}
  .banner h1 {{ margin: 0; font-size: 17px; }}
  .banner p {{ margin: 4px 0 0; font-size: 12px; opacity: 0.85; }}
  .legend {{
    line-height: 20px; color: #3a2412; background: rgba(255,255,255,0.9);
    padding: 8px 10px; border-radius: 8px; font-size: 12px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.25);
  }}
  .legend i {{ width: 16px; height: 16px; float: left; margin-right: 8px; opacity: 0.9; border-radius: 3px; }}
  .legend b {{ display:block; margin-bottom: 4px; }}
  .leaflet-popup-content {{ font-size: 13px; }}
  .leaflet-popup-content .q {{ font-style: italic; color: #6b4a2a; }}
  .leaflet-popup-content .rank {{ font-weight: bold; color: #7a4a1e; }}
</style>
</head>
<body>
<div class="banner">
  <h1>☕ London, ranked by cafés per 100 people</h1>
  <p>A rigorously unscientific Caffeine Density Index. Bigger, browner blobs = more dangerously caffeinated.</p>
</div>
<div id="map"></div>
<script>
  const DATA = {data_json};
  const TOTAL = {total};

  const map = L.map('map', {{ scrollWheelZoom: true }}).setView([51.505, -0.10], 11);
  L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
    attribution: '&copy; OpenStreetMap &copy; CARTO · cafés per 100 people are imaginary, the opinions are real',
    subdomains: 'abcd', maxZoom: 19
  }}).addTo(map);

  // Radius scales with the density so the espresso capitals genuinely loom.
  const dmin = Math.min(...DATA.map(d => d.density));
  const dmax = Math.max(...DATA.map(d => d.density));
  const radius = d => 12 + 26 * (d - dmin) / (dmax - dmin || 1);

  DATA.forEach(d => {{
    const m = L.circleMarker([d.lat, d.lon], {{
      radius: radius(d.density),
      fillColor: d.colour, color: '#2c1c10', weight: 1, opacity: 1, fillOpacity: 0.82
    }}).addTo(map);
    m.bindPopup(
      `<span class="rank">#${{d.rank}} of ${{TOTAL}}</span><br>` +
      `<b>${{d.name}}</b><br>` +
      `<b>${{d.density.toFixed(2)}}</b> cafés per 100 people<br>` +
      `${{d.cafes.toLocaleString()}} cafés · ${{d.pop.toLocaleString()}} residents<br>` +
      `<span class="q">“${{d.quip}}”</span>`
    );
    m.bindTooltip(`${{d.name}} — ${{d.density.toFixed(2)}}/100`, {{ direction: 'top' }});
  }});

  const legend = L.control({{ position: 'bottomright' }});
  legend.onAdd = function () {{
    const div = L.DomUtil.create('div', 'legend');
    div.innerHTML = '<b>Cafés per 100 people</b>{legend_rows}';
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
