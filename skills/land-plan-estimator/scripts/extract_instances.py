#!/usr/bin/env python3
"""extract_instances.py — the coordinate-grounded instance layer.

Every tag on a plan sheet (a storm structure number, a curb inlet mark, a
buffer-plant tag) carries an (x,y) in the vector text layer, already captured
by split_extract.py's per-sheet JSON. This turns a schedule CATALOGUE (one
row per TYPE — "1A" structures are catch basins) into an INSTANCE model (one
row per physical object placed on the plan, with coordinates).

Run this ONLY on plan-classified sheets (general_arrangement / site plan /
utility plan), NEVER on a schedule sheet or general-notes sheet — a tag
appearing in a schedule table is a DEFINITION, not a placed instance, and
running there returns phantom counts (every schedule row = a fake instance).

Ported from ContractorOS's drawings-analyser, unchanged (no unit-system
dependency — this is pure text-and-coordinate matching):
  - --space-tolerant: matches CAD letter-spaced tags ("1 A - 1 1" == "1A-11");
    a strict regex silently returns 0 on some civil exports.
  - --exclude-pattern: drop region-label tags (e.g. a phasing/demolition
    callout) so the same structure shown on two views of one sheet isn't
    double-counted.
  - Emits per-tag (sheet,x,y) so the model can dedupe across sheets/views and
    reconcile the instance count against the schedule's stated Qty column
    (this is the mechanism that catches a schedule-vs-plan mismatch before
    it ships — see SKILL.md Step 5a).

Usage:
    python extract_instances.py <sheet.json> --pattern "<regex>" --sheet <ID> \\
        [--space-tolerant] [--exclude x0,y0,x1,y1 ...] [--exclude-pattern "<regex>"] [-o out.json]

Example (storm structures 1A-1 .. 1A-99, excluding the schedule box):
    python extract_instances.py sheet_015.json --pattern "1A-\\d+" --sheet sheet_015 \\
        --exclude "1500,980,1850,1180" -o takeoff/instances_1A.json
"""
import json
import re
import argparse


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet_json")
    ap.add_argument("--pattern", required=True)
    ap.add_argument("--exclude", action="append", default=[], help="x0,y0,x1,y1 region to drop (schedule/legend box)")
    ap.add_argument("--exclude-pattern", default=None, help="if a tag's raw text matches this, drop it (e.g. a demo/phasing view label)")
    ap.add_argument("--space-tolerant", action="store_true", help="match letter-spaced CAD tags")
    ap.add_argument("--sheet", default="")
    ap.add_argument("-o", "--out", default="instances_out.json")
    a = ap.parse_args()

    d = json.load(open(a.sheet_json, encoding="utf-8"))
    boxes = [tuple(float(v) for v in e.split(",")) for e in a.exclude]
    pat = re.compile(a.pattern, re.IGNORECASE)
    expat = re.compile(a.exclude_pattern, re.IGNORECASE) if a.exclude_pattern else None

    inst, raw, kept = [], {}, {}
    for b in d.get("text_blocks", []):
        t = (b.get("text") or "").strip()
        if not t:
            continue
        candidates = [t]
        if a.space_tolerant:
            candidates.append(re.sub(r"\s+", "", t))
        norm = next((c for c in candidates if pat.fullmatch(c)), None)
        if norm is None:
            continue
        if expat and expat.search(t):
            continue
        raw[norm] = raw.get(norm, 0) + 1
        x0, y0, x1, y1 = b["bbox"]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if any(bx0 <= cx <= bx1 and by0 <= cy <= by1 for bx0, by0, bx1, by1 in boxes):
            continue
        inst.append({"tag": norm, "raw_text": t, "x": round(cx, 1), "y": round(cy, 1), "sheet": a.sheet})
        kept[norm] = kept.get(norm, 0) + 1

    print("RAW tag counts:   ", dict(sorted(raw.items())))
    print("INSTANCE counts:  ", dict(sorted(kept.items())), "(schedule/legend regions excluded)")
    print("total instances:  ", len(inst))
    if not inst:
        print("WARNING: 0 instances. If this is a plan sheet with visible tags, try --space-tolerant "
              "or widen --pattern (CAD often letter-spaces tags). Do NOT run this on a schedule/notes sheet.")
    json.dump(inst, open(a.out, "w"), indent=2)
    return inst


if __name__ == "__main__":
    main()
