#!/usr/bin/env python3
"""Build the canonical pinned-cities JSON from a TripAdvisor TravelMap export.

Sources, in priority order:
  - `maptable.tsv` -- a tab-separated table copy-pasted from the page. Layout is
        Continent <TAB> Country <TAB> [Region: ]City <TAB> Status-or-#-Contribs
    This is the source of truth for which 212 cities are pinned and their
    continent/country/region.
  - `raw-dump.json` -- output of dump-from-browser.js. Used to enrich each row
    with `geoId`, `contribCount`, `photoUrl`, `photoDate`, `memberPage`.
  - `source.mht` (optional) -- the saved MHTML snapshot. The table hides
    `pinType` behind a contribution count for any city you've contributed to,
    so we read those tiles' `sprite-faveBox` / `sprite-beenBox` flags from the
    saved DOM to recover the real status.

Output: `cities.json` (full structured records) and `cities.csv` (flat).

Usage:
  python build-cities.py
"""
import csv
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TABLE = HERE / "maptable.tsv"
DUMP = HERE / "raw-dump.json"
SNAPSHOT = HERE / "source.mht"
OUT_JSON = HERE / "cities.json"
OUT_CSV = HERE / "cities.csv"


def parse_table():
    rows = []
    with TABLE.open(encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        next(reader, None)  # header
        for parts in reader:
            if len(parts) < 4:
                continue
            continent, country, region_city, status_or_count = [p.strip() for p in parts[:4]]
            if ":" in region_city:
                region, city = (s.strip() for s in region_city.split(":", 1))
            else:
                region, city = "", region_city
            # status cell is either "Been"/"Fave"/"Want"/"Visited" or an integer
            # (the contribution count, which means the status is hidden in the table)
            pin_type, contrib = None, 0
            if re.fullmatch(r"\d+", status_or_count):
                contrib = int(status_or_count)
            elif status_or_count.lower() in ("fave", "favourite", "favorite"):
                pin_type = "fave"
            elif status_or_count.lower() in ("been", "visited"):
                pin_type = "been"
            elif status_or_count.lower() == "want":
                pin_type = "want"
            rows.append({
                "continent": continent,
                "country": country,
                "region": region,
                "city": city,
                "name": f"{city}, {country}",
                "pin_type": pin_type,
                "contrib_count": contrib,
            })
    return rows


def index_dump():
    """Return a lookup keyed by city -> merged record across every duplicate
    the dumper produced (tile strategy, table strategy, etc.). Merging picks
    the first non-empty value for each field, so a structured entry gives us
    `country`/`continent` and a tile entry contributes `geoId`/`photoUrl`.
    """
    data = json.loads(DUMP.read_text(encoding="utf-8"))
    by_city = {}
    for e in data.get("cities", []):
        city = e.get("city")
        if not city:
            continue
        merged = by_city.setdefault(city, {})
        for k, v in e.items():
            if v in (None, "", 0):
                continue
            merged.setdefault(k, v)
    return by_city


def snapshot_pin_types():
    """Read `source.mht` and recover pinType for each contribution tile from
    its `sprite-faveBox` / `sprite-beenBox` class. Keyed by city name."""
    if not SNAPSHOT.exists():
        return {}
    raw = SNAPSHOT.read_bytes().decode("utf-8", "ignore")
    # Tiles look like:
    #   <li ... data-ox-id="189158" ...>
    #     <a ...><div class="cityHero"><img...><span class="pinFlag sprite-faveBox">...
    #     <div class="cityName">Lisbon, Portugal</div>...
    out = {}
    tile_re = re.compile(
        r'data-ox-id="(?P<geo>\d+)"[^>]*data-ox-name="modules\.membercenter\.CityTiles:eachTile"'
        r'(?P<body>.{0,1500}?)</li>',
        re.DOTALL,
    )
    name_re = re.compile(r'class="cityName">([^<]+)</div>|class="name">([^<]+)</div>')
    for m in tile_re.finditer(raw):
        body = m.group("body")
        is_fave = "sprite-faveBox" in body
        is_been = "sprite-beenBox" in body and not is_fave
        nm = name_re.search(body)
        if not nm:
            continue
        full = (nm.group(1) or nm.group(2) or "").strip()
        if not full:
            continue
        out[full] = {"geo_id": m.group("geo"),
                     "pin_type": "fave" if is_fave else ("been" if is_been else None)}
    return out


def main():
    rows = parse_table()
    by_city = index_dump()
    snap = snapshot_pin_types()

    enriched = []
    fave_recovered = 0
    for r in rows:
        match = by_city.get(r["city"])
        if match and match.get("country") and match["country"] != r["country"]:
            match = None

        # Pin-type priority:
        #   1. Status word from the table (already set in r["pin_type"]).
        #   2. Sprite class from the MHTML snapshot (only for contribution
        #      tiles, but rock-solid because we read the actual DOM class).
        #   3. pinType from the runtime dumper (least reliable - the live
        #      DOM sometimes hides the sprite class).
        snap_match = snap.get(r["name"]) or snap.get(r["city"])
        if r["pin_type"] is None and snap_match and snap_match.get("pin_type"):
            r["pin_type"] = snap_match["pin_type"]
            if snap_match["pin_type"] == "fave":
                fave_recovered += 1
        if r["pin_type"] is None and match and match.get("pinType"):
            r["pin_type"] = match["pinType"]

        # Other fields - merge in whatever we have.
        if match:
            if not r["contrib_count"] and match.get("contribCount"):
                r["contrib_count"] = match["contribCount"]
            if match.get("geoId"):
                r["geo_id"] = match["geoId"]
            if match.get("photoUrl"):
                r["photo_url"] = match["photoUrl"]
            if match.get("photoDate"):
                r["photo_date"] = match["photoDate"]
            if match.get("memberPage"):
                r["member_page"] = match["memberPage"]
        if snap_match and snap_match.get("geo_id") and not r.get("geo_id"):
            r["geo_id"] = snap_match["geo_id"]

        if r["pin_type"] is None:
            r["pin_type"] = "been"
            r["pin_type_inferred"] = True
        enriched.append(r)

    enriched.sort(key=lambda r: (r["continent"], r["country"], r["region"], r["city"]))

    stats = {
        "total": len(enriched),
        "been": sum(1 for r in enriched if r["pin_type"] == "been"),
        "fave": sum(1 for r in enriched if r["pin_type"] == "fave"),
        "fave_recovered_from_snapshot": fave_recovered,
        "with_region": sum(1 for r in enriched if r["region"]),
        "with_geo_id": sum(1 for r in enriched if r.get("geo_id")),
        "countries": sorted({r["country"] for r in enriched}),
        "continents": sorted({r["continent"] for r in enriched}),
    }

    OUT_JSON.write_text(json.dumps({"stats": stats, "cities": enriched}, indent=2, ensure_ascii=False))
    fields = ["continent", "country", "region", "city", "name", "pin_type", "contrib_count", "geo_id"]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(enriched)

    print(f"wrote {OUT_JSON} ({stats['total']} cities, {stats['fave']} fave)")
    print(f"wrote {OUT_CSV}")
    print(f"stats: {json.dumps(stats, indent=2)}")


if __name__ == "__main__":
    main()
