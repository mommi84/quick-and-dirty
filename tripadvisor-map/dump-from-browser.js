// Paste this into the DevTools console while viewing
//   https://www.tripadvisor.co.uk/TravelMap-a_uid.343D39EF5D23BC304D551877E8088C9E
//
// It scrolls the city-tile list to force every tile to lazy-load, then dumps
// the full list as JSON to the console and copies it to your clipboard.
// Save the result as `cities.json` in this folder.

(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  // The city-tile list is the scrollable container holding the .name divs.
  const anyTile = document.querySelector('div.name');
  if (!anyTile) { console.error('No city tiles found - is the page loaded?'); return; }

  // Walk up to the nearest scrollable ancestor.
  let scroller = anyTile.parentElement;
  while (scroller && scroller !== document.body) {
    const style = getComputedStyle(scroller);
    if (/(auto|scroll)/.test(style.overflowY) && scroller.scrollHeight > scroller.clientHeight) break;
    scroller = scroller.parentElement;
  }
  scroller = scroller || document.scrollingElement;

  let prev = -1, stable = 0;
  for (let i = 0; i < 400 && stable < 5; i++) {
    scroller.scrollTop = scroller.scrollHeight;
    window.scrollTo(0, document.body.scrollHeight);
    await sleep(400);
    const n = document.querySelectorAll('div.name').length;
    if (n === prev) stable++; else { stable = 0; prev = n; }
    console.log(`pass ${i}: ${n} tiles loaded`);
  }

  const tiles = [...document.querySelectorAll('div.name')]
    .map(d => d.textContent.trim())
    .filter(Boolean);

  // Best-effort: try to also harvest map pin metadata if available in window state.
  const cities = [...new Set(tiles)].sort();
  const result = { cityCount: cities.length, cities };
  console.log('Dumped cities:', cities.length);
  console.log(JSON.stringify(result, null, 2));
  try {
    await navigator.clipboard.writeText(JSON.stringify(result, null, 2));
    console.log('Copied to clipboard.');
  } catch (e) {
    console.warn('Clipboard copy failed; copy the JSON above manually.', e);
  }
})();
