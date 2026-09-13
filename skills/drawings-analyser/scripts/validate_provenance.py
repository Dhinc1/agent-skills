#!/usr/bin/env python
"""drawings-analyser :: provenance validator (the key accuracy fix).
For every DB row with a quotable ATOMIC value + a claimed source sheet, confirm the
value's distinctive tokens actually appear in that sheet's text layer. If the cited
sheet lacks them (e.g. a raster/outlined sheet, or a wrong attribution), relocate the
row to the sheet that contains them — or FLAG it. Eliminated the structural hallucination.

HARDENED after a civil stress test where it nearly relocated a CORRECT row onto the
wrong-discipline sheet:
  - DESPACING: text and tokens are despaced so letter-spaced CAD text validates.
  - PROSE GUARD: skips long/paraphrased value fields (notes) — only validates atomic
    values (sizes, marks, model numbers, levels). Tokenising a sentence caused false fails.
  - SAME-DISCIPLINE GATE: with --discipline-map, never relocate across disciplines.
  - HIGHER BAR: relocate only if target coverage >=0.7 AND (cited empty OR target >=3x cited),
    or the value's high-entropy token appears on exactly one sheet.

Config: structured.json, a dir of per-sheet text files (stem matches the source value, e.g.
S101 -> <textdir>/S101.txt), and {table:[id_field, value_field, source_field]}.
Optional --discipline-map {sheet_stem: discipline}.
Usage: python validate_provenance.py <structured.json> --textdir <dir> --fields <fields.json> \
   [--discipline-map <map.json>] [--apply] -o <out.json>
"""
import json, re, os, glob, argparse

STOP = {'MINIMUM', 'CONCRETE', 'REINFORCEMENT', 'PROVIDE', 'CONTRACTOR', 'TYPICAL', 'REFER',
        'DRAWING', 'DETAIL', 'SCHEDULE', 'GENERAL', 'NOTES'}

def despace(s):
    return re.sub(r'\s+', '', s)

def tokens(val):
    """Distinctive atomic tokens. Returns set; high-entropy singletons are allowed."""
    up = str(val).upper()
    toks = set(re.findall(r'[A-Z0-9][A-Z0-9/\-\.\"]{1,}', up))
    keep = set()
    for t in toks:
        if t in STOP:
            continue
        hi = (len(t) >= 6) or (any(c.isdigit() for c in t) and any(c.isalpha() for c in t))
        if any(c.isdigit() for c in t) or len(t) >= 5 or hi:
            keep.add(t)
    return keep

def is_prose(val):
    """Paraphrased note text — don't tokenise/validate it (false fails)."""
    s = str(val).strip()
    return len(s.split()) > 6 or s.endswith('.')

def cov(toks, txt, txt_ds):
    if not toks:
        return None
    return sum(1 for t in toks if t in txt or despace(t) in txt_ds) / len(toks)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json"); ap.add_argument("--textdir", required=True)
    ap.add_argument("--fields", required=True, help="JSON: {table:[id,value,source]}")
    ap.add_argument("--discipline-map", default=None, help="JSON {sheet_stem: discipline} — gates relocation")
    ap.add_argument("-o", "--out", required=True); ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    sheet_text, sheet_ds = {}, {}
    for f in glob.glob(os.path.join(a.textdir, "*.txt")):
        stem = os.path.splitext(os.path.basename(f))[0].upper()
        txt = open(f, encoding="utf-8").read().upper()
        sheet_text[stem] = txt; sheet_ds[stem] = despace(txt)
    disc = {k.upper(): v for k, v in json.load(open(a.discipline_map, encoding="utf-8")).items()} if a.discipline_map else None
    fields = json.load(open(a.fields, encoding="utf-8"))
    db = json.load(open(a.json, encoding="utf-8"))
    report = []; fixes = 0
    for table, (idf, valf, srcf) in fields.items():
        for row in db.get(table, []):
            src = str(row.get(srcf, "")).upper()
            key = src if src in sheet_text else next((k for k in sheet_text if src and src in k), None)
            if key is None:
                continue
            if is_prose(row.get(valf, "")):
                continue  # don't validate paraphrased notes
            toks = tokens(row.get(valf, "")) | tokens(row.get(idf, ""))
            if not toks:
                continue
            c = cov(toks, sheet_text.get(key, ""), sheet_ds.get(key, ""))
            empty = not sheet_text.get(key)
            if not (empty or (c is not None and c < 0.34)):
                continue
            ranked = sorted(((s, cov(toks, t, sheet_ds[s])) for s, t in sheet_text.items() if t),
                            key=lambda kv: -(kv[1] or 0))[:3]
            top = ranked[0] if ranked else (None, 0)
            # same-discipline gate
            same_disc = (disc is None) or (top[0] and disc.get(top[0]) == disc.get(key))
            # exactly-one-sheet rule for a high-entropy value
            on_sheets = [s for s, t in sheet_text.items() if all((tk in t or despace(tk) in sheet_ds[s]) for tk in toks)]
            flag = {"table": table, "id": row.get(idf), "cited": src,
                    "cov": round(c, 2) if c is not None else None, "cited_empty": empty,
                    "best": [(s, round(v, 2)) for s, v in ranked]}
            relocate = (top[0] and top[0] != key and same_disc and
                        (((top[1] or 0) >= 0.7 and (empty or c is None or top[1] >= 3 * c)) or len(on_sheets) == 1))
            if relocate:
                tgt = on_sheets[0] if len(on_sheets) == 1 and (disc is None or disc.get(on_sheets[0]) == disc.get(key)) else top[0]
                flag["action"] = f"RELOCATE {src} -> {tgt}"
                if a.apply:
                    row[srcf] = tgt
                fixes += 1
            else:
                flag["action"] = "FLAG (manual review)" + ("" if same_disc else " [cross-discipline — not relocated]")
            report.append(flag)
    json.dump(report, open(a.out, "w"), indent=2)
    if a.apply:
        json.dump(db, open(a.json.replace('.json', '_validated.json'), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"Provenance: {len(report)} flags, {fixes} relocations{' (applied)' if a.apply else ' (dry-run; use --apply)'}.")
    for f in report:
        print(f"  [{f['action']}] {f['table']}.{f['id']} cited={f['cited']}(cov={f['cov']},empty={f['cited_empty']}) best={f['best']}")

if __name__ == "__main__":
    main()
