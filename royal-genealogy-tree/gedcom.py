#!/usr/bin/env python3
"""Minimal GEDCOM 5.5 reader -- the bridge to a real FamilySearch tree.

FamilySearch's Family Tree API needs OAuth, so build_tree.py cannot fetch a
private person like 98R9-WVR on its own. But any logged-in FamilySearch user can
export their tree to a GEDCOM file, and this reader turns that file into the same
person records the Wikidata crawler produces, so the identical enrichment +
renderer pipeline draws it.

We keep only what the tree needs: names, birth/death years and places, sex, and
parent links (resolved through FAM records). Royal-house colouring still works if
your GEDCOM carries a noble title -- we treat a TITL line as the "house" bucket.

This is deliberately small and forgiving, not a spec-complete parser.
"""
import re


def _parse_records(path):
    """Yield top-level GEDCOM records as (tag, xref, [lines])."""
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        lines = [ln.rstrip("\n").rstrip("\r") for ln in fh if ln.strip()]
    records, cur = [], None
    for ln in lines:
        m = re.match(r"^(\d+)\s+(@[^@]+@\s+)?(\S+)(?:\s(.*))?$", ln)
        if not m:
            continue
        level = int(m.group(1))
        xref = (m.group(2) or "").strip().strip("@") or None
        tag = m.group(3)
        value = m.group(4) or ""
        if level == 0:
            if cur:
                records.append(cur)
            # For level-0, the "tag" slot holds the xref and value holds the type.
            cur = {"xref": xref or tag, "type": value or tag, "lines": []}
        elif cur is not None:
            cur["lines"].append((level, tag, value))
    if cur:
        records.append(cur)
    return records


def _year(value):
    m = re.search(r"(\d{3,4})", value or "")
    return int(m.group(1)) if m else None


def _sub(lines, start_idx):
    """Return the block of lines belonging to the structure opened at start_idx."""
    base = lines[start_idx][0]
    block = []
    for level, tag, value in lines[start_idx + 1:]:
        if level <= base:
            break
        block.append((level, tag, value))
    return block


def to_people(path, root_id=None):
    """Parse `path` into {id: person} plus the chosen root id.

    Person shape matches the Wikidata crawler's records so downstream code
    (enrichment, house colouring, hierarchy, HTML) is identical.
    """
    records = _parse_records(path)
    indis, fams = {}, {}
    for rec in records:
        if rec["type"] == "INDI":
            indis[rec["xref"]] = rec
        elif rec["type"] == "FAM":
            fams[rec["xref"]] = rec

    # Map each child -> (father_xref, mother_xref) via FAM records.
    parents = {}
    for fam in fams.values():
        husb = wife = None
        children = []
        for _, tag, value in fam["lines"]:
            ref = value.strip().strip("@") if value else None
            if tag == "HUSB":
                husb = ref
            elif tag == "WIFE":
                wife = ref
            elif tag == "CHIL":
                children.append(ref)
        for child in children:
            parents[child] = (husb, wife)

    people = {}
    for xref, rec in indis.items():
        name = title = birth_year = death_year = birth_place = None
        lines = rec["lines"]
        for idx, (level, tag, value) in enumerate(lines):
            if tag == "NAME" and name is None:
                name = value.replace("/", "").strip()
            elif tag == "TITL" and title is None:
                title = value.strip()
            elif tag in ("BIRT", "DEAT"):
                block = _sub(lines, idx)
                year = place = None
                for _, btag, bval in block:
                    if btag == "DATE":
                        year = _year(bval)
                    elif btag == "PLAC":
                        place = bval.strip()
                if tag == "BIRT":
                    birth_year, birth_place = year, place or birth_place
                else:
                    death_year = year
        father, mother = parents.get(xref, (None, None))
        people[xref] = {
            "qid": xref,               # reuse the id slot; FamilySearch PIDs live here
            "name": name or xref,
            "description": title,
            "father": father,
            "mother": mother,
            "birth_year": birth_year,
            "death_year": death_year,
            "birth_place": birth_place,
            "image": None,
            "houses": [title] if title else [],
            "wikipedia": None,         # enrichment will try to match by name later
            "wikipedia_url": None,
            "generation": None,
        }

    # Choose a root: explicit id, else the individual with no recorded parents
    # that has the most descendants reachable -- simplest is the first INDI.
    if root_id and root_id in people:
        root = root_id
    elif root_id:
        # FamilySearch ids in GEDCOM are sometimes wrapped or suffixed; fuzzy match.
        root = next((x for x in people if root_id in x), None) or next(iter(people))
    else:
        root = next(iter(people))

    _tag_generations(people, root)
    return people, root


def _tag_generations(people, root):
    frontier, gen = [root], 0
    seen = set()
    while frontier:
        nxt = []
        for x in frontier:
            if x in seen or x not in people:
                continue
            seen.add(x)
            people[x]["generation"] = gen
            nxt += [people[x]["father"], people[x]["mother"]]
        frontier = [x for x in nxt if x]
        gen += 1


if __name__ == "__main__":
    import sys
    ppl, r = to_people(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(f"parsed {len(ppl)} individuals; root = {r} ({ppl[r]['name']})")
