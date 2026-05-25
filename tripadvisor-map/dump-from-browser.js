// Paste into the DevTools console on
//   https://www.tripadvisor.co.uk/TravelMap-a_uid.343D39EF5D23BC304D551877E8088C9E
//
// Works in both layouts the page can render:
//   1. Desktop tile layout  - cityName divs inside CityTiles
//   2. Mobile / list layout - rows with continent | country | region:city | status
//
// Scrolls everything that scrolls until counts stabilise, then harvests every
// pinned place with as much structure as the visible DOM exposes:
//   geoId, name, city, country, region, continent, pinType, contribCount,
//   photoUrl, photoDate, memberPage
//
// Logs progress and copies the result to your clipboard. Save as
// `tripadvisor-map/cities.json` and push.

(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  const findScrollable = el => {
    while (el && el !== document.body) {
      const s = getComputedStyle(el);
      if (/(auto|scroll)/.test(s.overflowY) && el.scrollHeight > el.clientHeight + 4) return el;
      el = el.parentElement;
    }
    return null;
  };

  // ----- scroll the main page to mount lazy sections -----
  console.log('[dump] scrolling main page to bottom...');
  for (let i = 0; i < 30; i++) {
    window.scrollTo(0, document.body.scrollHeight);
    await sleep(300);
  }
  // also scroll the inner-most scroller of anything that looks pin-related
  const anchorEls = [...document.querySelectorAll(
    '[data-ox-name*="CityTiles"], [data-ox-name*="PinnableList"], .flag-icon.been, .pinFlag, .sprite-beenBox'
  )];
  const innerScrollers = new Set();
  anchorEls.forEach(a => { const s = findScrollable(a); if (s) innerScrollers.add(s); });
  console.log(`[dump] found ${anchorEls.length} pin-related anchors, ${innerScrollers.size} inner scrollers`);

  let prevCount = -1, stable = 0;
  for (let i = 0; i < 500 && stable < 6; i++) {
    innerScrollers.forEach(s => { s.scrollTop = s.scrollHeight; });
    window.scrollTo(0, document.body.scrollHeight);
    await sleep(350);
    const n = document.querySelectorAll(
      '[data-ox-name="modules.membercenter.CityTiles:eachTile"], ' +
      '[data-ox-name="modules.travelmap.PinnableList:eachPin"]'
    ).length;
    if (n === prevCount) stable++; else { stable = 0; prevCount = n; }
    if (i % 5 === 0) console.log(`[dump] pass ${i}: ${n} rows`);
  }

  // ----- helpers -----
  const PHOTO_DATE_RE = /\/(\d{4})(\d{2})(\d{2})-\d{6}/;

  const splitName = raw => {
    let city = raw, country = '';
    const i = raw.lastIndexOf(',');
    if (i > -1) { city = raw.slice(0, i).trim(); country = raw.slice(i + 1).trim(); }
    return { city, country };
  };

  const byGeoId = new Map();
  const addOrMerge = entry => {
    if (!entry.name) return;
    const key = entry.geoId || entry.name;
    const existing = byGeoId.get(key) || {};
    for (const [k, v] of Object.entries(entry)) {
      if (v !== null && v !== undefined && v !== '' && (existing[k] === undefined || existing[k] === '' || existing[k] === null))
        existing[k] = v;
    }
    byGeoId.set(key, existing);
  };

  // ----- strategy 1: desktop tile layout -----
  const tiles = document.querySelectorAll('[data-ox-name="modules.membercenter.CityTiles:eachTile"]');
  for (const tile of tiles) {
    const geoId = tile.dataset.oxId || tile.getAttribute('name') || null;
    const rawName = (tile.querySelector('.cityName, .name')?.textContent || '').trim();
    if (!rawName) continue;
    const { city, country } = splitName(rawName);
    const pinFlag = tile.querySelector('.pinFlag');
    let pinType = 'been';
    if (pinFlag?.classList.contains('sprite-faveBox')) pinType = 'fave';
    const contribEl = tile.querySelector('.contributionCount');
    const photoImg = tile.querySelector('.cityHeroImg, .citySmallImg');
    const photoUrl = photoImg?.src || null;
    const m = photoUrl ? photoUrl.match(PHOTO_DATE_RE) : null;
    const photoDate = m ? `${m[1]}-${m[2]}-${m[3]}` : null;
    const link = tile.querySelector('a[href*="members-citypage"]');
    addOrMerge({
      geoId, name: rawName, city, country, region: '', continent: '',
      pinType, contribCount: contribEl ? parseInt(contribEl.textContent, 10) || 0 : 0,
      photoUrl, photoDate, memberPage: link?.href || null,
    });
  }
  console.log(`[dump] tile-layout entries: ${tiles.length}`);

  // ----- strategy 2: PinnableList rows -----
  const pinRows = document.querySelectorAll('[data-ox-name="modules.travelmap.PinnableList:eachPin"]');
  for (const row of pinRows) {
    const rawId = row.dataset.oxId || '';
    const geoId = (rawId.match(/(\d+)$/) || [])[1] || null;
    const rawName = (row.querySelector('.locationName, .cityName, .name')?.textContent || '').trim();
    if (!rawName) continue;
    const { city, country } = splitName(rawName);
    let pinType = 'been';
    if (row.querySelector('.fave.sprite-faveSet, .flag-icon.fave[class*="Set"]')) pinType = 'fave';
    addOrMerge({ geoId, name: rawName, city, country, region: '', continent: '', pinType });
  }
  console.log(`[dump] pinnable-list entries: ${pinRows.length}`);

  // ----- strategy 3: generic table/list layout (mobile) -----
  // Find rows containing a "Been" / "Want" / "Fave" / "Visited" status cell and
  // walk up to a row container, then read its cells from left to right.
  const STATUS_WORDS = /^\s*(Been|Visited|Want|Fave|Favourite|Favorite)\s*$/i;
  const allEls = document.querySelectorAll('span, div, td, button, a');
  const rowSet = new Set();
  for (const el of allEls) {
    if (!STATUS_WORDS.test(el.textContent)) continue;
    // walk up until we find a parent with at least 3 textual children
    let p = el.parentElement, depth = 0;
    while (p && depth < 6) {
      const cells = [...p.children].map(c => (c.textContent || '').trim()).filter(Boolean);
      if (cells.length >= 3 && cells.length <= 8) { rowSet.add(p); break; }
      p = p.parentElement; depth++;
    }
  }
  console.log(`[dump] generic-table candidate rows: ${rowSet.size}`);

  for (const row of rowSet) {
    const cells = [...row.children].map(c => (c.textContent || '').trim());
    // try to identify which cell is which by content shape
    const statusIdx = cells.findIndex(c => STATUS_WORDS.test(c));
    if (statusIdx < 0) continue;
    const status = cells[statusIdx].trim();
    // before status: continent, country, region:city OR country, region:city
    const before = cells.slice(0, statusIdx).filter(Boolean);
    let continent = '', country = '', region = '', city = '', rawName = '';
    if (before.length === 3) [continent, country, rawName] = before;
    else if (before.length === 2) [country, rawName] = before;
    else if (before.length === 1) [rawName] = before;
    else if (before.length >= 4) {
      continent = before[0]; country = before[1]; rawName = before.slice(2).join(' ');
    }
    if (rawName.includes(':')) {
      const [r, c] = rawName.split(':');
      region = r.trim(); city = c.trim();
    } else {
      city = rawName;
    }
    if (!city) continue;
    const name = country ? `${city}, ${country}` : city;
    const linkEl = row.querySelector('a[href*="g"][href*="-d"], a[href*="geo"], a[href*="members-citypage"]');
    const geoId = (linkEl?.href.match(/g(\d+)/) || [])[1] || null;
    const pinType = /fave|favou?rite/i.test(status) ? 'fave' : 'been';
    addOrMerge({ geoId, name, city, country, region, continent, pinType });
  }

  // ----- finalise -----
  const cities = [...byGeoId.values()]
    .filter(c => c.city)
    .sort((a, b) => (a.continent + a.country + a.city).localeCompare(b.continent + b.country + b.city));

  const stats = {
    total: cities.length,
    been: cities.filter(c => c.pinType === 'been').length,
    fave: cities.filter(c => c.pinType === 'fave').length,
    withCountry: cities.filter(c => c.country).length,
    withContinent: cities.filter(c => c.continent).length,
    withPhotoDate: cities.filter(c => c.photoDate).length,
    countries: [...new Set(cities.map(c => c.country).filter(Boolean))].sort(),
  };

  const result = { stats, cities };
  console.log(`[dump] DONE - ${cities.length} cities (${stats.fave} fave, ${stats.withCountry} with country, ${stats.withContinent} with continent)`);
  console.log(JSON.stringify(result, null, 2));
  try {
    await navigator.clipboard.writeText(JSON.stringify(result, null, 2));
    console.log('[dump] copied to clipboard. Save as tripadvisor-map/cities.json');
  } catch (e) {
    console.warn('[dump] clipboard copy failed; copy the JSON above manually.', e);
  }
})();
