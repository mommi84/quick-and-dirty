#!/usr/bin/env python3
"""Build an interactive ancestry tree for a person and light it up with royal branches.

The FamilySearch tree that inspired this project
(https://www.familysearch.org/en/tree/pedigree/landscape/98R9-WVR) lives behind
an OAuth login, so it cannot be scraped anonymously. This tool therefore climbs
the *open* genealogy graph instead:

  * Wikidata  -- the world's largest openly queryable pedigree. We follow
                 P22 (father) and P25 (mother) up the tree, generation by
                 generation, pulling dates, birthplaces, portraits, and -- the
                 star of the show -- P53 (the noble family / royal house).
  * Wikipedia -- a one-paragraph biography for every ancestor we can match.

You can point it at any Wikidata person, or at a GEDCOM you exported from
FamilySearch yourself (File > Export, once you are logged in) -- see gedcom.py.

Zero third-party dependencies: pure standard library. D3.js is pulled from a CDN
by the browser to draw the tree, so viewing index.html needs internet, but the
data is baked into the file and the crawl is fully cached under data/.

Usage:
  python3 build_tree.py                       # default demo: King Charles III
  python3 build_tree.py --wikidata Q9439 -g 8 # Queen Victoria, 8 generations
  python3 build_tree.py --gedcom mytree.ged --root 98R9-WVR
  python3 build_tree.py --offline             # rebuild HTML from cache only
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
CACHE_PATH = os.path.join(DATA_DIR, "wikipedia_cache.json")
TREE_PATH = os.path.join(DATA_DIR, "tree.json")
HTML_PATH = os.path.join(HERE, "index.html")

WD_SPARQL = "https://query.wikidata.org/sparql"
WP_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/"
UA = ("quick-and-dirty-genealogy/1.0 "
      "(https://github.com/mommi84/quick-and-dirty; contact via repo)")

# A gentle, distinct palette for royal houses (assigned in order of appearance).
HOUSE_COLOURS = [
    "#b8860b", "#8b0000", "#1f5c8b", "#2e7d32", "#6a1b9a", "#c2185b",
    "#00838f", "#e65100", "#4e342e", "#37474f", "#ad1457", "#558b2f",
    "#5d4037", "#283593", "#00695c", "#9e2a2b", "#7b5e00", "#455a64",
]
NO_HOUSE_COLOUR = "#9aa0a6"  # commoners / unknown house


# --------------------------------------------------------------------------- #
# HTTP helpers                                                                 #
# --------------------------------------------------------------------------- #
def http_get(url, accept="application/json", tries=4):
    """GET with a real User-Agent and polite exponential backoff."""
    last = None
    for attempt in range(tries):
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": accept,
        })
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read().decode("utf-8")
        except Exception as exc:  # noqa: BLE001 - network is best-effort
            last = exc
            wait = 2 ** attempt
            sys.stderr.write(f"  ! request failed ({exc}); retrying in {wait}s\n")
            time.sleep(wait)
    raise RuntimeError(f"giving up on {url}: {last}")


def sparql(query):
    url = WD_SPARQL + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
    data = json.loads(http_get(url, accept="application/sparql-results+json"))
    return data["results"]["bindings"]


def qid_of(uri):
    return uri.rsplit("/", 1)[-1] if uri else None


def cell(binding, key):
    return binding[key]["value"] if key in binding else None


def year_of(iso):
    if not iso:
        return None
    m = re.match(r"(-?\d{1,4})", iso.lstrip("+"))
    if not m:
        return None
    y = int(m.group(1))
    # SPARQL sometimes hands back leading-zero padded years; keep the sign.
    return y


# --------------------------------------------------------------------------- #
# Wikidata ancestry crawl                                                      #
# --------------------------------------------------------------------------- #
PERSON_QUERY = """
SELECT ?p ?pLabel ?pDescription ?father ?mother ?dob ?dod
       ?birthPlaceLabel ?img ?house ?houseLabel ?article WHERE {
  VALUES ?p { %s }
  OPTIONAL { ?p wdt:P22 ?father }
  OPTIONAL { ?p wdt:P25 ?mother }
  OPTIONAL { ?p wdt:P569 ?dob }
  OPTIONAL { ?p wdt:P570 ?dod }
  OPTIONAL { ?p wdt:P19 ?birthPlace }
  OPTIONAL { ?p wdt:P18 ?img }
  OPTIONAL { ?p wdt:P53 ?house }
  OPTIONAL { ?article schema:about ?p ; schema:isPartOf <https://en.wikipedia.org/> }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr,de,es,it,ru,nl" }
}
"""


def fetch_people(qids):
    """One SPARQL round-trip for a batch of QIDs. Merges multi-house rows."""
    values = " ".join(f"wd:{q}" for q in qids)
    rows = sparql(PERSON_QUERY % values)
    people = {}
    for b in rows:
        qid = qid_of(cell(b, "p"))
        p = people.get(qid)
        if p is None:
            article = cell(b, "article")
            p = {
                "qid": qid,
                "name": cell(b, "pLabel") or qid,
                "description": cell(b, "pDescription"),
                "father": qid_of(cell(b, "father")),
                "mother": qid_of(cell(b, "mother")),
                "birth_year": year_of(cell(b, "dob")),
                "death_year": year_of(cell(b, "dod")),
                "birth_place": cell(b, "birthPlaceLabel"),
                "image": cell(b, "img"),
                "houses": [],
                "wikipedia": urllib.parse.unquote(article.rsplit("/", 1)[-1]) if article else None,
                "wikipedia_url": article,
            }
            people[qid] = p
        house = cell(b, "houseLabel")
        if house and house not in p["houses"]:
            p["houses"].append(house)
    return people


def crawl(root_qid, max_generations):
    """Breadth-first climb through ancestors, one SPARQL query per generation."""
    people = {}
    frontier = [root_qid]
    for gen in range(max_generations + 1):
        frontier = [q for q in frontier if q and q not in people]
        if not frontier:
            break
        sys.stderr.write(f"generation {gen}: fetching {len(frontier)} individual(s)...\n")
        batch = fetch_people(frontier)
        nxt = []
        for qid, p in batch.items():
            p["generation"] = gen
            people[qid] = p
            nxt += [p["father"], p["mother"]]
        frontier = nxt
        time.sleep(0.3)  # be kind to the public endpoint
    sys.stderr.write(f"crawled {len(people)} ancestors across {gen} generation(s).\n")
    return people


# --------------------------------------------------------------------------- #
# Wikipedia enrichment                                                         #
# --------------------------------------------------------------------------- #
def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return default


def enrich(people):
    """Attach a one-paragraph Wikipedia biography + thumbnail to each person."""
    cache = load_json(CACHE_PATH, {})
    todo = [p for p in people.values()
            if p.get("wikipedia") and p["wikipedia"] not in cache]
    for i, p in enumerate(todo, 1):
        title = p["wikipedia"]
        sys.stderr.write(f"  wikipedia {i}/{len(todo)}: {title}\n")
        try:
            raw = http_get(WP_SUMMARY + urllib.parse.quote(title, safe=""))
            data = json.loads(raw)
            cache[title] = {
                "extract": data.get("extract"),
                "thumbnail": (data.get("thumbnail") or {}).get("source"),
            }
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write(f"    (skipped: {exc})\n")
            cache[title] = {"extract": None, "thumbnail": None}
        time.sleep(0.1)
    with open(CACHE_PATH, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, ensure_ascii=False, indent=1)

    for p in people.values():
        entry = cache.get(p.get("wikipedia") or "", {})
        p["extract"] = entry.get("extract")
        if entry.get("thumbnail") and not p.get("image"):
            p["image"] = entry["thumbnail"]
    return people


# --------------------------------------------------------------------------- #
# Shaping the tree                                                             #
# --------------------------------------------------------------------------- #
def assign_house_colours(people):
    """Order houses by how many ancestors carry them; hand out stable colours."""
    counts = {}
    for p in people.values():
        for h in p["houses"]:
            counts[h] = counts.get(h, 0) + 1
    ordered = sorted(counts, key=lambda h: (-counts[h], h))
    colours = {h: HOUSE_COLOURS[i % len(HOUSE_COLOURS)] for i, h in enumerate(ordered)}
    return colours, counts


def primary_house(p):
    return p["houses"][0] if p["houses"] else None


def build_hierarchy(people, root_qid, colours):
    """Nested ancestor tree. Royal ancestry loops back on itself constantly
    (pedigree collapse), so a repeated ancestor is shown once fully and then as
    a lightweight 'see above' leaf to keep the drawing finite and honest."""
    emitted = set()

    def node(qid, path):
        p = people.get(qid)
        if p is None:
            return None
        house = primary_house(p)
        n = {
            "qid": qid,
            "name": p["name"],
            "birth_year": p.get("birth_year"),
            "death_year": p.get("death_year"),
            "birth_place": p.get("birth_place"),
            "description": p.get("description"),
            "extract": p.get("extract"),
            "image": p.get("image"),
            "house": house,
            "houses": p["houses"],
            "colour": colours.get(house, NO_HOUSE_COLOUR),
            "wikipedia_url": p.get("wikipedia_url"),
            "generation": p.get("generation"),
        }
        if qid in emitted or qid in path:
            n["repeat"] = True
            return n
        emitted.add(qid)
        kids = []
        for parent in (p.get("father"), p.get("mother")):
            child = node(parent, path | {qid})
            if child:
                kids.append(child)
        if kids:
            n["children"] = kids
        return n

    return node(root_qid, frozenset())


# --------------------------------------------------------------------------- #
# HTML rendering                                                               #
# --------------------------------------------------------------------------- #
def render_html(tree, people, colours, counts, root_qid):
    houses_legend = [
        {"name": h, "colour": colours[h], "count": counts[h]}
        for h in sorted(counts, key=lambda h: (-counts[h], h))
    ]
    root = people[root_qid]
    generations = max((p.get("generation", 0) for p in people.values()), default=0)
    stats = {
        "root": root["name"],
        "individuals": len(people),
        "generations": generations,
        "houses": len(counts),
        "with_bio": sum(1 for p in people.values() if p.get("extract")),
    }
    payload = json.dumps({
        "tree": tree,
        "houses": houses_legend,
        "stats": stats,
    }, ensure_ascii=False)

    html_doc = HTML_TEMPLATE.replace("__DATA__", payload)
    html_doc = html_doc.replace("__D3__", _d3_tag())
    with open(HTML_PATH, "w", encoding="utf-8") as fh:
        fh.write(html_doc)
    with open(TREE_PATH, "w", encoding="utf-8") as fh:
        json.dump({"tree": tree, "houses": houses_legend, "stats": stats},
                  fh, ensure_ascii=False, indent=1)
    return stats


D3_PATH = os.path.join(DATA_DIR, "d3.min.js")


def _d3_tag():
    """Inline the vendored D3 so index.html is fully self-contained. Falls back
    to the CDN if data/d3.min.js is missing (mirrors the cafe project)."""
    if os.path.exists(D3_PATH):
        with open(D3_PATH, encoding="utf-8") as fh:
            return "<script>" + fh.read() + "</script>"
    return '<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>'


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Royal Ancestry Tree</title>
__D3__
<style>
  :root { --bg:#12100e; --panel:#1c1917; --ink:#f4efe6; --muted:#b8ae9e; --line:#4a4038; }
  * { box-sizing: border-box; }
  html, body { margin:0; height:100%; background:var(--bg); color:var(--ink);
    font-family: ui-serif, Georgia, "Times New Roman", serif; }
  header { padding:14px 20px; border-bottom:1px solid var(--line);
    display:flex; flex-wrap:wrap; align-items:baseline; gap:6px 18px; }
  header h1 { font-size:20px; margin:0; letter-spacing:.02em; }
  header h1 .crown { font-style:normal; }
  header .sub { color:var(--muted); font-size:13px; }
  .stats { margin-left:auto; display:flex; gap:16px; font-size:13px; color:var(--muted); }
  .stats b { color:var(--ink); font-size:15px; }
  #wrap { display:flex; height:calc(100vh - 56px); }
  #chart { flex:1; overflow:hidden; }
  #side { width:340px; border-left:1px solid var(--line); background:var(--panel);
    padding:18px; overflow-y:auto; }
  #side h2 { margin:0 0 2px; font-size:19px; }
  #side .dates { color:var(--muted); font-size:13px; margin-bottom:10px; }
  #side img { width:100%; border-radius:6px; margin:6px 0 12px;
    border:1px solid var(--line); }
  #side p { font-size:14px; line-height:1.5; color:#e8e0d3; }
  #side .house-tag { display:inline-block; padding:2px 9px; border-radius:20px;
    font-size:12px; color:#fff; margin:2px 4px 6px 0; }
  #side a { color:#e3b23c; }
  #side .hint { color:var(--muted); font-style:italic; }
  .legend { position:absolute; bottom:14px; left:14px; background:rgba(28,25,23,.92);
    border:1px solid var(--line); border-radius:8px; padding:10px 12px; max-width:260px;
    font-size:12px; max-height:42vh; overflow-y:auto; }
  .legend h3 { margin:0 0 6px; font-size:12px; color:var(--muted);
    text-transform:uppercase; letter-spacing:.08em; }
  .legend .row { display:flex; align-items:center; gap:7px; margin:3px 0; cursor:pointer; }
  .legend .row:hover { color:#fff; }
  .legend .sw { width:11px; height:11px; border-radius:3px; flex:none; }
  .legend .c { margin-left:auto; color:var(--muted); }
  .node circle { stroke:#12100e; stroke-width:1.5px; cursor:pointer; }
  .node.repeat circle { stroke-dasharray:2,2; opacity:.6; }
  .node text { font-size:11px; fill:var(--ink); paint-order:stroke;
    stroke:#12100e; stroke-width:3px; stroke-linejoin:round; cursor:pointer; }
  .link { fill:none; stroke:var(--line); stroke-width:1.4px; }
  .dim { opacity:.12; }
  .controls { position:absolute; top:70px; left:14px; font-size:12px; color:var(--muted); }
  .controls button { background:var(--panel); color:var(--ink); border:1px solid var(--line);
    border-radius:6px; padding:5px 9px; cursor:pointer; font-family:inherit; }
  .controls button:hover { border-color:#e3b23c; }
</style>
</head>
<body>
<header>
  <h1><span class="crown">&#128081;</span> Royal Ancestry Tree</h1>
  <span class="sub" id="rootline"></span>
  <div class="stats" id="stats"></div>
</header>
<div id="wrap">
  <div id="chart">
    <div class="controls">
      <button id="fit">Fit to screen</button>
      <button id="reset">Collapse all</button>
    </div>
    <div class="legend" id="legend"></div>
  </div>
  <aside id="side">
    <p class="hint">Click any ancestor to read who they were. Dashed circles are
    ancestors who already appear elsewhere in the tree (royal lines intermarry,
    so the same person is reached by several paths).</p>
  </aside>
</div>
<script>
const DATA = __DATA__;

document.getElementById('rootline').textContent =
  'Ancestors of ' + DATA.stats.root;
const s = DATA.stats;
document.getElementById('stats').innerHTML =
  `<span><b>${s.individuals}</b> ancestors</span>` +
  `<span><b>${s.generations}</b> generations</span>` +
  `<span><b>${s.houses}</b> royal houses</span>` +
  `<span><b>${s.with_bio}</b> with bios</span>`;

// ---- legend ----
const legend = document.getElementById('legend');
legend.innerHTML = '<h3>Royal houses</h3>';
let houseFilter = null;
DATA.houses.forEach(h => {
  const row = document.createElement('div');
  row.className = 'row';
  row.innerHTML = `<span class="sw" style="background:${h.colour}"></span>` +
                  `<span>${h.name}</span><span class="c">${h.count}</span>`;
  row.onclick = () => { houseFilter = (houseFilter === h.name) ? null : h.name; applyFilter(); };
  legend.appendChild(row);
});

// ---- tree layout ----
const root = d3.hierarchy(DATA.tree);
root.x0 = 0; root.y0 = 0;
let i = 0;
// collapse deep branches initially for readability
root.descendants().forEach(d => {
  if (d.depth >= 3 && d.children) { d._children = d.children; d.children = null; }
});

const svg = d3.select('#chart').append('svg')
  .attr('width', '100%').attr('height', '100%');
const g = svg.append('g');
const gLink = g.append('g');
const gNode = g.append('g');

const zoom = d3.zoom().scaleExtent([0.15, 2.5]).on('zoom', e => g.attr('transform', e.transform));
svg.call(zoom);

const dx = 16, dy = 200;
const tree = d3.tree().nodeSize([dx, dy]);
const diagonal = d3.linkHorizontal().x(d => d.y).y(d => d.x);

function update(source) {
  tree(root);
  const nodes = root.descendants();
  const links = root.links();

  const t = svg.transition().duration(300);

  const node = gNode.selectAll('g.node').data(nodes, d => d.id || (d.id = ++i));
  const nodeEnter = node.enter().append('g')
    .attr('class', d => 'node' + (d.data.repeat ? ' repeat' : ''))
    .attr('transform', d => `translate(${source.y0},${source.x0})`)
    .on('click', (e, d) => { toggle(d); select(d); });

  nodeEnter.append('circle')
    .attr('r', d => d.depth === 0 ? 6 : 4.5)
    .attr('fill', d => d.data.colour);

  nodeEnter.append('text')
    .attr('dy', '0.32em')
    .attr('x', d => (d._children || d.children) ? -8 : 8)
    .attr('text-anchor', d => (d._children || d.children) ? 'end' : 'start')
    .text(d => label(d.data));

  node.merge(nodeEnter).transition(t)
    .attr('transform', d => `translate(${d.y},${d.x})`)
    .attr('opacity', 1);
  node.exit().transition(t).remove()
    .attr('transform', d => `translate(${source.y},${source.x})`);

  const link = gLink.selectAll('path.link').data(links, d => d.target.id);
  const linkEnter = link.enter().append('path').attr('class', 'link')
    .attr('d', d => { const o = {x: source.x0, y: source.y0}; return diagonal({source:o, target:o}); });
  link.merge(linkEnter).transition(t).attr('d', diagonal);
  link.exit().transition(t).remove()
    .attr('d', d => { const o = {x: source.x, y: source.y}; return diagonal({source:o, target:o}); });

  root.eachBefore(d => { d.x0 = d.x; d.y0 = d.y; });
  applyFilter();
}

function label(d) {
  const b = d.birth_year, dd = d.death_year;
  const span = (b || dd) ? ` (${b || '?'}–${dd || ''})` : '';
  return d.name + span;
}

function toggle(d) {
  if (d.children) { d._children = d.children; d.children = null; }
  else if (d._children) { d.children = d._children; d._children = null; }
  update(d);
}

function select(d) {
  const p = d.data;
  const side = document.getElementById('side');
  const dates = [p.birth_year ? 'b. ' + p.birth_year : null,
                 p.death_year ? 'd. ' + p.death_year : null].filter(Boolean).join('  ·  ');
  let html = `<h2>${p.name}</h2>`;
  if (dates || p.birth_place)
    html += `<div class="dates">${dates}${p.birth_place ? '  ·  ' + p.birth_place : ''}</div>`;
  (p.houses || []).forEach(h => {
    const col = (DATA.houses.find(x => x.name === h) || {}).colour || '#9aa0a6';
    html += `<span class="house-tag" style="background:${col}">${h}</span>`;
  });
  if (p.image) html += `<img src="${p.image}" alt="${p.name}" loading="lazy">`;
  if (p.extract) html += `<p>${p.extract}</p>`;
  else if (p.description) html += `<p>${p.description}</p>`;
  else html += `<p class="hint">No biography matched for this ancestor.</p>`;
  if (p.wikipedia_url) html += `<p><a href="${p.wikipedia_url}" target="_blank" rel="noopener">Read on Wikipedia →</a></p>`;
  if (p.repeat) html += `<p class="hint">This ancestor also appears on another branch — the royal lines converge here.</p>`;
  side.innerHTML = html;
}

function applyFilter() {
  gNode.selectAll('g.node').classed('dim', d =>
    houseFilter && !(d.data.houses || []).includes(houseFilter));
  document.querySelectorAll('#legend .row').forEach(r => {
    r.style.fontWeight = (houseFilter && r.textContent.includes(houseFilter)) ? '700' : '400';
  });
}

function fit() {
  const b = gNode.node().getBBox();
  const cw = document.getElementById('chart').clientWidth;
  const ch = document.getElementById('chart').clientHeight;
  const scale = Math.min(2, 0.9 / Math.max(b.width / cw, b.height / ch));
  const tx = cw / 2 - scale * (b.x + b.width / 2);
  const ty = ch / 2 - scale * (b.y + b.height / 2);
  svg.transition().duration(500).call(zoom.transform,
    d3.zoomIdentity.translate(tx, ty).scale(scale));
}

document.getElementById('fit').onclick = fit;
document.getElementById('reset').onclick = () => {
  root.descendants().forEach(d => {
    if (d.depth >= 1 && d.children) { d._children = d.children; d.children = null; }
  });
  update(root); setTimeout(fit, 350);
};

update(root);
setTimeout(fit, 400);

// Expose a tiny hook so the tree can be driven programmatically (used by the
// screenshot tooling; harmless in normal use).
window.tree = {
  expandAll() {
    (function ex(d){ if (d._children){ d.children=d._children; d._children=null; }
      (d.children||[]).forEach(ex); })(root);
    update(root); fit();
  },
  fit, root,
};
</script>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
# GEDCOM path (for the actual FamilySearch export)                            #
# --------------------------------------------------------------------------- #
def from_gedcom(path, root_id):
    import gedcom  # local module
    people, root = gedcom.to_people(path, root_id)
    return people, root


# --------------------------------------------------------------------------- #
# main                                                                         #
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wikidata", default="Q43274",
                    help="Wikidata QID of the root person (default Q43274 = King Charles III)")
    ap.add_argument("-g", "--generations", type=int, default=7,
                    help="how many generations of ancestors to climb (default 7)")
    ap.add_argument("--gedcom", help="path to a GEDCOM exported from FamilySearch")
    ap.add_argument("--root", help="root individual id within the GEDCOM (e.g. 98R9-WVR)")
    ap.add_argument("--offline", action="store_true",
                    help="rebuild index.html from the cached tree.json without any network")
    args = ap.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)

    if args.offline:
        cached = load_json(TREE_PATH, None)
        if not cached:
            sys.exit("no cached tree.json to rebuild from; run a live crawl first.")
        html_doc = HTML_TEMPLATE.replace("__DATA__", json.dumps(cached, ensure_ascii=False))
        html_doc = html_doc.replace("__D3__", _d3_tag())
        with open(HTML_PATH, "w", encoding="utf-8") as fh:
            fh.write(html_doc)
        print(f"Rebuilt {HTML_PATH} from cache.")
        return

    if args.gedcom:
        people, root_qid = from_gedcom(args.gedcom, args.root)
        # GEDCOM people are already fully-formed; still try Wikipedia enrichment.
        people = enrich(people)
    else:
        root_qid = args.wikidata
        people = crawl(root_qid, args.generations)
        people = enrich(people)

    colours, counts = assign_house_colours(people)
    tree = build_hierarchy(people, root_qid, colours)
    stats = render_html(tree, people, colours, counts, root_qid)

    print("\nDone. Wrote", HTML_PATH)
    print(f"  root:         {stats['root']}")
    print(f"  ancestors:    {stats['individuals']}")
    print(f"  generations:  {stats['generations']}")
    print(f"  royal houses: {stats['houses']}")
    print(f"  with bios:    {stats['with_bio']}")
    print("\nTop royal branches:")
    for h in sorted(counts, key=lambda h: (-counts[h], h))[:10]:
        print(f"  {counts[h]:3d}  {h}")


if __name__ == "__main__":
    main()
