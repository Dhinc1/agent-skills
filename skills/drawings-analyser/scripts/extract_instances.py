#!/usr/bin/env python
"""drawings-analyser :: instance extraction (the coordinate-grounded IFC layer).
Every TAG on a plan carries an (x,y) in the vector text layer. This turns a schedule
CATALOGUE (one row per type) into an INSTANCE model (one row per physical object, with
coordinates) — object + placement. Enables counts (takeoff), spatial queries, topology.

HARDENED after independent HVAC + civil stress tests:
  - --space-tolerant: matches CAD letter-spaced tags ("SEW M H 1" == "SEWMH1"); the strict
    regex silently returned 0 on real civil drawings.
  - --exclude-pattern: drop region-label tags (e.g. DEMOLITION/EXISTING views) so the same
    unit shown on a demo + reno view of one sheet isn't double-counted.
  - emits per-tag (sheet,x,y) so the model can dedupe across sheets/views and reconcile
    against schedule QTY. NEVER run this on a schedule_sheet/general_notes sheet — a tag in a
    schedule is a DEFINITION, not a placed instance (run only on general_arrangement/plan sheets).

Usage: python extract_instances.py <sheet_json> --pattern "<regex>" --sheet <ID> \
   [--space-tolerant] [--exclude x0,y0,x1,y1 ...] [--exclude-pattern "<regex of nearby labels>"] [-o out.json]
"""
import json, re, argparse

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet_json"); ap.add_argument("--pattern", required=True)
    ap.add_argument("--exclude", action="append", default=[], help="x0,y0,x1,y1 region to drop")
    ap.add_argument("--exclude-pattern", default=None, help="if a tag's text matches this, drop it (e.g. demo-view labels)")
    ap.add_argument("--space-tolerant", action="store_true", help="match letter-spaced CAD tags")
    ap.add_argument("--sheet", default="")
    ap.add_argument("-o", "--out", default="instances_out.json")
    a = ap.parse_args()
    d = json.load(open(a.sheet_json, encoding="utf-8"))
    boxes = [tuple(float(v) for v in e.split(",")) for e in a.exclude]
    pat = re.compile(a.pattern, re.IGNORECASE)
    expat = re.compile(a.exclude_pattern, re.IGNORECASE) if a.exclude_pattern else None
    inst = []; raw = {}; kept = {}
    for b in d.get("text_blocks", []):
        t = (b.get("text") or "").strip()
        if not t:
            continue
        # space-tolerant: also try the despaced form so "SEW M H 1" matches "SEWMH1"
        candidates = [t]
        if a.space_tolerant:
            candidates.append(re.sub(r"\s+", "", t))
        norm = next((c for c in candidates if pat.fullmatch(c)), None)
        if norm is None:
            continue
        if expat and expat.search(t):
            continue
        raw[norm] = raw.get(norm, 0) + 1
        x0, y0, x1, y1 = b["bbox"]; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if any(bx0 <= cx <= bx1 and by0 <= cy <= by1 for bx0, by0, bx1, by1 in boxes):
            continue
        inst.append({"tag": norm, "raw_text": t, "x": round(cx, 1), "y": round(cy, 1), "sheet": a.sheet})
        kept[norm] = kept.get(norm, 0) + 1
    print("RAW tag counts:   ", dict(sorted(raw.items())))
    print("INSTANCE counts:  ", dict(sorted(kept.items())), "(schedule/legend regions excluded)")
    print("total instances:  ", len(inst))
    if not inst:
        print("WARNING: 0 instances. If this is a plan sheet with visible tags, try --space-tolerant "
              "or widen --pattern (CAD often letter-spaces tags). Do NOT run on schedule/notes sheets.")
    json.dump(inst, open(a.out, "w"), indent=2)
    return inst

if __name__ == "__main__":
    main()
