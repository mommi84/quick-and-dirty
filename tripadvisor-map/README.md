# tripadvisor-map

Extract the pinned cities from a TripAdvisor TravelMap profile
(`https://www.tripadvisor.co.uk/TravelMap-a_uid.<UID>`).

TripAdvisor's TravelMap page is bot-protected (DataDome), so you can't fetch it
server-side. The workflow is:

1. Open the map in a browser, logged in.
2. **Save the page as MHTML** -> `source.mht` here. (Mobile Chrome: "Save"
   from the share sheet.) Optional but useful: lets the build step recover the
   real pinType for "contributions" tiles (see below).
3. **Switch to the list/table view** at the bottom of the page, scroll the
   whole table into view, and **copy-paste it** into `maptable.tsv`.
   Layout: `Continent <TAB> Country <TAB> [Region: ]City <TAB> Status-or-Count`.
4. Optional: paste `dump-from-browser.js` into the page's DevTools console to
   harvest `geoId` / `photoUrl` / `memberPage` for as many tiles as it can
   reach. Save the output as `raw-dump.json`.
5. `python3 build-cities.py` -> writes `cities.json` and `cities.csv`.

## Why the build needs three sources

The table (`maptable.tsv`) is the most reliable list of pinned cities, but for
cities where you have contributions (reviews/photos), TripAdvisor replaces the
status cell with a contribution count -- so "Been" vs "Fave" gets hidden.

The MHTML snapshot still has the raw DOM with `sprite-faveBox` /
`sprite-beenBox` class flags on those tiles, so the builder reads them
directly to recover the missing statuses. (This is how we got Lisbon = fave
even though the table just showed `1`.)

The runtime dumper adds `geoId`s, photo URLs and your member-page links for
whichever tiles loaded before you copied.

## Output schema (`cities.json`)

```json
{
  "stats": { "total": 212, "been": 204, "fave": 8, ... },
  "cities": [
    {
      "continent": "Europe",
      "country":   "Portugal",
      "region":    "",                  // empty if the table had no "Region: City"
      "city":      "Lisbon",
      "name":      "Lisbon, Portugal",
      "pin_type":  "fave",              // "been" | "fave"
      "contrib_count": 1,
      "geo_id":    "189158",            // TripAdvisor location id, if known
      "photo_url": "https://media-cdn.tripadvisor.com/.../lisbon.jpg",
      "member_page": "https://www.tripadvisor.co.uk/members-citypage/mommi84/g189158"
    }
  ]
}
```

`cities.csv` is the flat version (continent, country, region, city, name,
pin_type, contrib_count, geo_id).

## Note on dates

TripAdvisor's TravelMap doesn't store the date you pinned a city anywhere in
the DOM or API. The dumper records a `photo_date` when the tile's hero image
is a user-uploaded photo (filename pattern `YYYYMMDD-HHMMSS`), but that's just
"when you uploaded a photo for that city" -- a noisy proxy at best, and absent
for cities with stock TripAdvisor photos.
