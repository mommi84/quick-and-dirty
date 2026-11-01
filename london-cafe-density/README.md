# ☕ London Café Density Map

A rigorously **unscientific** map of London constituencies ranked by the metric
that truly matters: **cafés per 100 people** — the Caffeine Density Index.

Bigger, browner blobs mean more dangerously caffeinated. Click one to learn an
uncomfortable truth about its residents.

```bash
$ python3 build_map.py
```

This prints a ranked leaderboard and writes a self-contained `index.html`.
Open it in a browser:

```bash
$ open index.html        # macOS
$ xdg-open index.html    # Linux
```

## How it works

* `cafes.csv` — the editable source of truth: constituency, centroid, population,
  café count, and a strongly-held opinion. **Café counts and populations are
  lovingly approximated for comedic effect.** Swap in real numbers from
  [OpenStreetMap Overpass](https://overpass-api.de/) (`amenity=cafe`) and the
  [ONS](https://www.ons.gov.uk/) if you want to ruin the joke with accuracy.
* `build_map.py` — pure standard library, zero dependencies. Computes
  `cafés / population × 100`, ranks everyone, and renders an interactive
  [Leaflet](https://leafletjs.com/) map with an espresso-strength colour ramp
  (pale oat-milk → ristretto).

## Current champions

| Rank | Constituency | per 100 |
|-----:|--------------|--------:|
| 👑 1 | Cities of London and Westminster | 0.52 |
| 2 | Hackney South and Shoreditch | 0.51 |
| 3 | Hackney North and Stoke Newington | 0.44 |
| 💀 last | Barking (honest builder's tea country) | 0.11 |

> Note: generating the map needs no internet, but rendering it does — Leaflet and
> the map tiles are pulled from a CDN in the browser.
