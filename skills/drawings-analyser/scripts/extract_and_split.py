#!/usr/bin/env python
"""drawings-to-context :: Step 1 — extract & split.
Turn a multi-page drawing PDF into durable per-sheet artifacts and detect the
vector/raster fork (the single most important input check).

Per sheet writes: pNN.pdf (single sheet), pNN.png (render), pNN.txt (text layer).
Plus manifest.json (per-sheet: textchars, vector_count, has_raster_image,
source_type=vector|raster|mixed, table_count) and all_text.txt (consolidated).

Usage: python extract_and_split.py <input.pdf> -o <out_dir> [--dpi 0 --long-edge 2200]
"""
import sys, os, json, argparse
import pymupdf
try:
    import pdfplumber
except Exception:
    pdfplumber = None

def classify(page, textchars):
    imgs = page.get_images(full=True)
    has_raster = len(imgs) > 0
    # heuristic: real text layer => vector; little/no text + big raster => raster
    if textchars > 200 and not (has_raster and textchars < 50):
        return "vector" if not has_raster else "mixed"
    if has_raster:
        return "raster"
    return "vector" if textchars > 200 else "sparse"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf"); ap.add_argument("-o","--out",required=True)
    ap.add_argument("--long-edge",type=int,default=2200)
    args = ap.parse_args()
    os.makedirs(os.path.join(args.out,"sheets"),exist_ok=True)
    doc = pymupdf.open(args.pdf)
    manifest=[]; dump=[]
    for i,pg in enumerate(doc):
        n=i+1; stem=f"p{n:02d}"
        sp=pymupdf.open(); sp.insert_pdf(doc,from_page=i,to_page=i)
        sp.save(os.path.join(args.out,"sheets",stem+".pdf")); sp.close()
        rect=pg.rect; zoom=args.long_edge/max(rect.width,rect.height)
        pg.get_pixmap(matrix=pymupdf.Matrix(zoom,zoom)).save(os.path.join(args.out,"sheets",stem+".png"))
        txt=pg.get_text()
        open(os.path.join(args.out,"sheets",stem+".txt"),"w",encoding="utf-8").write(txt)
        ntab=0
        if pdfplumber and len(txt)>200:
            try:
                with pdfplumber.open(args.pdf) as pp:
                    ntab=len(pp.pages[i].extract_tables() or [])
            except Exception: ntab=-1
        st=classify(pg,len(txt))
        manifest.append({"page":n,"stem":stem,"textchars":len(txt),
            "vector_count":len(pg.get_drawings()),"has_raster_image":len(pg.get_images())>0,
            "source_type":st,"table_count":ntab,"size_pt":[int(rect.width),int(rect.height)]})
        dump.append(f"\n{'='*80}\nPAGE {n} ({stem}) | type={st} | textchars={len(txt)} | tables={ntab}\n{'='*80}\n{txt}")
    json.dump(manifest,open(os.path.join(args.out,"manifest.json"),"w"),indent=2)
    open(os.path.join(args.out,"all_text.txt"),"w",encoding="utf-8").write("".join(dump))
    # summary
    from collections import Counter
    c=Counter(m["source_type"] for m in manifest)
    print(f"Extracted {len(manifest)} sheets -> {args.out}")
    print("Source-type split:", dict(c))
    raster=[m["page"] for m in manifest if m["source_type"]=="raster"]
    if raster:
        print(f"WARNING: {len(raster)} raster sheet(s) have NO extractable text layer "
              f"(pages {raster[:15]}{'...' if len(raster)>15 else ''}).")
        print("  -> Structured extraction will MISS these. They need OCR/vision, or flag as placeholders.")
if __name__=="__main__": main()
