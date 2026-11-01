# ☕ London Café Density Map

A map of all **75 London Westminster constituencies** ranked by the metric that
truly matters: **cafés per 10,000 residents** — the Caffeine Density Index.

Darker constituencies are more dangerously caffeinated. Click one for the real
numbers. The tone is unscientific; **the data is not** — it now comes from
OpenStreetMap and the ONS.

```bash
$ python3 fetch_data.py   # pull fresh real data (needs internet)
$ python3 build_map.py    # rank + render index.html
```

Then open the map in a browser:

```bash
$ open index.html        # macOS
$ xdg-open index.html    # Linux
```

## Where the data comes from

Everything is real, open data — no fabricated numbers:

| What | Source | Detail |
|------|--------|--------|
| **Cafés** | [OpenStreetMap](https://www.openstreetmap.org/) via the [Overpass API](https://overpass-api.de/) | every `amenity=cafe` (node + way) inside Greater London |
| **Population** | [ONS Census 2021](https://www.nomisweb.co.uk/) | usual-resident population (table TS001), served via the Nomis API |
| **Boundaries** | [ONS Open Geography Portal](https://geoportal.statistics.gov.uk/) | Westminster Parliamentary Constituencies (July 2024), generalised & clipped |

`fetch_data.py` ties them together: it identifies the 75 constituencies whose
wards lie in a London borough (LAD code `E09…`), downloads their boundaries,
pulls every café from OSM, assigns each café to a constituency by
point-in-polygon, and joins the Census population. It writes:

* `cafes.csv` — `code, constituency, lat, lon, population, cafes`
* `london_constituencies.geojson` — the boundary polygons for the choropleth

`build_map.py` reads both, computes `cafés / population × 10,000`, ranks
everyone, and renders an interactive [Leaflet](https://leafletjs.com/)
choropleth with an espresso-strength colour ramp (pale oat-milk → ristretto).

Both scripts are pure standard library — zero `pip install`s.

## Current champions

_(OSM snapshot · Census 2021 population — re-run `fetch_data.py` to refresh)_

| Rank | Constituency | Cafés | Pop. | per 10k |
|-----:|--------------|------:|-----:|--------:|
| 👑 1 | Cities of London and Westminster | 875 | 119,981 | 72.9 |
| 2 | Holborn and St Pancras | 405 | 106,020 | 38.2 |
| 3 | Islington South and Finsbury | 215 | 115,956 | 18.5 |
| 4 | Kensington and Bayswater | 221 | 132,867 | 16.6 |
| 5 | Hackney South and Shoreditch | 182 | 112,556 | 16.2 |
| 💀 last | Mitcham and Morden | 17 | 123,762 | 1.4 |

> London as a whole: **6,747 cafés** across **8.8M residents** ≈ 7.7 per 10,000.

## Caveats (the honest fine print)

* OSM café counts depend on contributor coverage — central, well-mapped areas
  may look denser partly because they're better mapped. The `amenity=cafe` tag
  also excludes many coffee-serving venues tagged as `restaurant`/`fast_food`.
* Population is Census 2021 (residents, not workers/tourists), so commercial
  cores like the City & Westminster score sky-high — lots of cafés, relatively
  few people who actually live there.

> Note: generating the map needs no internet, but rendering it does — Leaflet
> and the basemap tiles are pulled from a CDN in the browser.
