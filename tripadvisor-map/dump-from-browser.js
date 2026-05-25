// Paste into the DevTools console on
//   https://www.tripadvisor.co.uk/TravelMap-a_uid.343D39EF5D23BC304D551877E8088C9E
//
// Scrolls the page (and any inner scrollers) to trigger lazy-loaded city tiles,
// then harvests every pinned city with all available metadata:
//   - geoId        (TripAdvisor location id)
//   - name         (raw "City, Country" string from the tile)
//   - city         (split from name)
//   - country      (split from name)
//   - pinType      ("fave" or "been")
//   - contribCount (TripAdvisor reviews/photos you contributed for this city)
//   - photoUrl     (hero image URL)
//   - photoDate    (if the photo is a user upload, YYYY-MM-DD parsed from the
//                   filename — TripAdvisor doesn't store the actual pin date,
//                   so this is the best "when did you go" proxy available)
//   - memberPage   (link to your member-citypage for this geo)
//
// Logs progress and copies the full JSON to your clipboard. Save as
// `tripadvisor-map/cities.json` and push.

(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  const TILE_SEL = '[data-ox-name="modules.membercenter.CityTiles:eachTile"]';
  const FALLBACK_NAME_SELS = ['.cityName', '.name', '.locationName'];

  const findScrollable = el => {
    while (el && el !== document.body) {
      const s = getComputedStyle(el);
      if (/(auto|scroll)/.test(s.overflowY) && el.scrollHeight > el.clientHeight + 4) return el;
      el = el.parentElement;
    }
    return null;
  };

  // ---------- scroll the main page first ----------
  console.log('[dump] scrolling main page...');
  for (let i = 0; i < 30; i++) {
    window.scrollTo(0, document.body.scrollHeight);
    await sleep(300);
    if (document.querySelector(TILE_SEL)) break;
  }

  let anyTile = document.querySelector(TILE_SEL);
  if (!anyTile) {
    // Diagnostics if the tile section never mounted
    console.warn('[dump] No city tiles found. DOM hints:', {
      ox_modules: [...new Set([...document.querySelectorAll('[data-ox-name]')]
                    .map(e => e.dataset.oxName))],
      iframes: document.querySelectorAll('iframe').length,
      bodyChars: document.body.innerText.length,
    });
    console.warn('       Scroll manually to the city list section and re-run.');
    return;
  }

  // ---------- scroll inner list until tile count stabilises ----------
  const inner = findScrollable(anyTile.parentElement);
  if (inner) console.log('[dump] inner scroller:', inner);

  let prevCount = -1, stable = 0;
  for (let i = 0; i < 500 && stable < 6; i++) {
    if (inner) inner.scrollTop = inner.scrollHeight;
    window.scrollTo(0, document.body.scrollHeight);
    await sleep(350);
    const n = document.querySelectorAll(TILE_SEL).length;
    if (n === prevCount) stable++; else { stable = 0; prevCount = n; }
    if (i % 5 === 0) console.log(`[dump] pass ${i}: ${n} tiles`);
  }

  // ---------- harvest ----------
  const PHOTO_DATE_RE = /\/(\d{4})(\d{2})(\d{2})-\d{6}/;

  const tiles = [...document.querySelectorAll(TILE_SEL)];
  const cities = [];
  const seen = new Set();
  for (const tile of tiles) {
    const geoId = tile.dataset.oxId || tile.getAttribute('name') || null;

    let rawName = '';
    for (const sel of FALLBACK_NAME_SELS) {
      const n = tile.querySelector(sel);
      if (n && n.textContent.trim()) { rawName = n.textContent.trim(); break; }
    }
    if (!rawName) continue;

    let city = rawName, country = '';
    const lastComma = rawName.lastIndexOf(',');
    if (lastComma > -1) {
      city = rawName.slice(0, lastComma).trim();
      country = rawName.slice(lastComma + 1).trim();
    }

    const pinFlag = tile.querySelector('.pinFlag');
    let pinType = 'been';
    if (pinFlag) {
      if (pinFlag.classList.contains('sprite-faveBox')) pinType = 'fave';
      else if (pinFlag.classList.contains('sprite-beenBox')) pinType = 'been';
    }

    const contribEl = tile.querySelector('.contributionCount');
    const contribCount = contribEl ? parseInt(contribEl.textContent, 10) || 0 : 0;

    const photoImg = tile.querySelector('.cityHeroImg, .citySmallImg');
    const photoUrl = photoImg ? photoImg.src : null;
    let photoDate = null;
    if (photoUrl) {
      const m = photoUrl.match(PHOTO_DATE_RE);
      if (m) photoDate = `${m[1]}-${m[2]}-${m[3]}`;
    }

    const link = tile.querySelector('a[href*="members-citypage"]');
    const memberPage = link ? link.href : null;

    const key = `${geoId}|${rawName}`;
    if (seen.has(key)) continue;
    seen.add(key);

    cities.push({ geoId, name: rawName, city, country, pinType,
                  contribCount, photoUrl, photoDate, memberPage });
  }

  cities.sort((a, b) => a.name.localeCompare(b.name));

  const stats = {
    total: cities.length,
    been: cities.filter(c => c.pinType === 'been').length,
    fave: cities.filter(c => c.pinType === 'fave').length,
    withPhotoDate: cities.filter(c => c.photoDate).length,
    countries: [...new Set(cities.map(c => c.country).filter(Boolean))].sort(),
  };

  const result = { stats, cities };
  console.log(`[dump] DONE - ${cities.length} cities (${stats.fave} fave, ${stats.withPhotoDate} with photo-date)`);
  console.log(JSON.stringify(result, null, 2));
  try {
    await navigator.clipboard.writeText(JSON.stringify(result, null, 2));
    console.log('[dump] copied to clipboard. Save as tripadvisor-map/cities.json');
  } catch (e) {
    console.warn('[dump] clipboard copy failed; copy the JSON above manually.', e);
  }
})();
