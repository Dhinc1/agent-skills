#!/usr/bin/env python3
"""build_db.py — load a structured.json (schedules, instances, relationships,
notes) into a queryable SQLite database. Generic: one table per top-level
key (an array of row objects); lists/dicts inside a row are stored as JSON
text. No unit-system or domain dependency.

Ported unchanged from ContractorOS's drawings-analyser.

Usage:
    python build_db.py <structured.json> -o <project.sqlite>
"""
import json
import sqlite3
import os
import argparse


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()

    db = json.load(open(a.json, encoding="utf-8"))
    if os.path.exists(a.out):
        os.remove(a.out)
    con = sqlite3.connect(a.out)
    for tbl, rows in db.items():
        if not isinstance(rows, list) or not rows:
            continue
        cols = sorted({k for r in rows for k in r.keys()})
        con.execute(f'CREATE TABLE "{tbl}" (' + ",".join(f'"{c}" TEXT' for c in cols) + ")")
        for r in rows:
            con.execute(
                f'INSERT INTO "{tbl}" (' + ",".join(f'"{c}"' for c in cols) + ") VALUES (" + ",".join("?" * len(cols)) + ")",
                [json.dumps(r[c]) if isinstance(r.get(c), (list, dict)) else r.get(c) for c in cols])
    con.commit()
    print("Built", a.out, "tables:", [t[0] for t in con.execute("SELECT name FROM sqlite_master WHERE type='table'")])


if __name__ == "__main__":
    main()
