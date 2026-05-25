# tripadvisor-map

Extract the pinned cities from a TripAdvisor TravelMap profile
(`https://www.tripadvisor.co.uk/TravelMap-a_uid.<UID>`).

TripAdvisor's TravelMap page is bot-protected (DataDome), so you can't fetch it
server-side. The workflow is:

1. Open the map in a desktop browser, log in if necessary.
2. **Scroll the city-tile list all the way to the bottom** so every tile loads
   (the list is lazy-loaded, ~10 tiles per scroll). If you skip this step,
   the snapshot will only contain whatever was on-screen.
3. Save the page as `.mht` / `.mhtml` (Chrome: `chrome://flags` → "Save Page
   as MHTML" → File → Save Page As). Drop the file in here as `source.mht`.
4. `python3 extract.py source.mht` → writes `extracted.json`.

If `counts.all` in the JSON is bigger than `len(cities_in_tiles)`, the tile list
didn't fully load before saving. Either re-save after scrolling, or paste
`dump-from-browser.js` into the live page's DevTools console — it auto-scrolls,
collects every city name, and copies the JSON to your clipboard. Save that as
`cities.json` here.

## What's in `extracted.json`

- `counts` — totals reported by the page (`all`, `been`, `want`, `fave`).
- `map_view` — the centre/zoom the map was rendered at when saved.
- `cities_in_tiles` — names from the visible "Cities I've been" list.
- `pins` — every map marker, with pixel offset + type (`been` / `fave`).
  Pixel offsets preserve relative geography but can't be reliably reprojected
  to lat/lng without the map div size at snapshot time.
