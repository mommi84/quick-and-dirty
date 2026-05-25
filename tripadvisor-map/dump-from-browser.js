// Paste into the DevTools console on
//   https://www.tripadvisor.co.uk/TravelMap-a_uid.343D39EF5D23BC304D551877E8088C9E
//
// Scrolls the page (and any inner scrollers) to trigger lazy-loaded city tiles,
// then harvests every city name it can find from any of the known TripAdvisor
// markup variants. Logs progress, copies the result to your clipboard.

(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  // Every selector the TravelMap page is known to use for a pinned-city name.
  const SELECTORS = [
    '[data-ox-name="modules.membercenter.CityTiles:eachTile"] .name',
    '[data-ox-name="modules.membercenter.CityTiles:eachTile"] .cityName',
    '[data-ox-name="modules.travelmap.PinnableList:eachPin"] .locationName',
    '.cityHero .name',
    '.cityHero .cityName',
    '.cityName',
    '.locationName',
    'div.name',
  ];

  const harvest = () => {
    const found = new Map();           // text -> selector that found it
    for (const sel of SELECTORS) {
      for (const el of document.querySelectorAll(sel)) {
        const t = (el.textContent || '').trim();
        if (t && t.length < 120 && !found.has(t)) found.set(t, sel);
      }
    }
    return found;
  };

  const findScrollableAncestor = el => {
    while (el && el !== document.body) {
      const s = getComputedStyle(el);
      if (/(auto|scroll)/.test(s.overflowY) && el.scrollHeight > el.clientHeight + 4) return el;
      el = el.parentElement;
    }
    return null;
  };

  // Step 1: scroll the main page to the bottom so the city-tile section mounts.
  console.log('[dump] scrolling main page to force-mount sections...');
  for (let i = 0; i < 30; i++) {
    window.scrollTo(0, document.body.scrollHeight);
    await sleep(300);
    if (harvest().size > 0) break;
  }

  let snapshot = harvest();
  console.log(`[dump] after main scroll: ${snapshot.size} names`);

  if (snapshot.size === 0) {
    // Helpful diagnostics
    const hints = {
      ox_modules: [...document.querySelectorAll('[data-ox-name]')]
        .map(e => e.dataset.oxName).filter((v,i,a)=>a.indexOf(v)===i),
      iframes:   document.querySelectorAll('iframe').length,
      bodyChars: document.body && document.body.innerText.length,
    };
    console.warn('[dump] no city names found in DOM. Hints:', hints);
    console.warn('       - Make sure you are signed into TripAdvisor (your map URL).');
    console.warn('       - Try scrolling the page manually until you see the city tiles, then re-run.');
    return;
  }

  // Step 2: find the inner scrollable container holding the tiles and scroll it.
  const sampleEl = document.querySelector(snapshot.values().next().value)
                || document.querySelector('.name');
  const inner = findScrollableAncestor(sampleEl.parentElement);
  if (inner) console.log('[dump] inner scroller:', inner);

  let prev = -1, stable = 0;
  for (let i = 0; i < 500 && stable < 6; i++) {
    if (inner) inner.scrollTop = inner.scrollHeight;
    window.scrollTo(0, document.body.scrollHeight);
    await sleep(350);
    snapshot = harvest();
    if (snapshot.size === prev) stable++; else { stable = 0; prev = snapshot.size; }
    if (i % 5 === 0) console.log(`[dump] pass ${i}: ${snapshot.size} names`);
  }

  const cities = [...snapshot.keys()].sort();
  const bySelector = {};
  for (const [name, sel] of snapshot) (bySelector[sel] = bySelector[sel] || []).push(name);

  const result = { cityCount: cities.length, cities, bySelector };
  console.log(`[dump] DONE - ${cities.length} unique names`);
  console.log(JSON.stringify(result, null, 2));
  try {
    await navigator.clipboard.writeText(JSON.stringify(result, null, 2));
    console.log('[dump] copied to clipboard.');
  } catch (e) {
    console.warn('[dump] clipboard copy failed; copy the JSON above manually.', e);
  }
})();
