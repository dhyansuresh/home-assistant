"""Audit local Open Food Facts photos and prepare reviewed product-classification data."""
import argparse
import base64
import csv
import hashlib
import html
import io
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, ImageOps

FIELDS = ["code", "image_path", "product_name", "brands", "quantity", "review_status",
          "split", "capture_group", "source", "image_url", "product_url", "notes"]
SPLITS = ("train", "validation", "test")


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def image_info(path):
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.load()
        pixel_hash = hashlib.sha256(str(image.size).encode() + image.tobytes()).hexdigest()
        width, height = image.size
        image.thumbnail((200, 180))
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=75)
    return {"width": width, "height": height, "pixel_sha256": pixel_hash,
            "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "preview": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()}


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def safe_image_path(root, value):
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("image_path must stay inside the dataset root")
    return path


def gallery(path, cards):
    payload = json.dumps(cards, ensure_ascii=False).replace("<", "\\u003c")
    page = '''<!doctype html><html lang="en"><meta charset="utf-8">
<title>HomePilot · Product photo review</title>
<style>body{font:16px system-ui;background:#f5f6f9;color:#17233b;margin:30px}header{max-width:1000px}
button,input,select{font:inherit;padding:8px;border:1px solid #abb6ca;border-radius:5px}button{cursor:pointer}
#grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(275px,1fr));gap:16px;margin-top:20px}
article{background:white;border:1px solid #dde1e8;padding:16px;border-radius:10px}img{height:180px;max-width:100%;object-fit:contain}
label{display:block;margin-top:8px;font-size:13px}input,select{box-sizing:border-box;width:100%}#search{width:360px;max-width:100%}
.flag{color:#a44216;font-size:13px}.bar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:15px}
</style><header><h1>HomePilot product photo review</h1>
<p>Verify the pictured product, brand, flavor, package size and pack count. A serving size is not a package size.
Approve only usable photos whose identity you have checked. Country tags and source records are claims, not verification.</p>
<p>Each current product has one photo. Add independent webcam capture sessions before training. Keep all frames from
one session in the same split. Do not copy or augment a photo into another split.</p>
<p>Edit below, then <b>Download review.csv</b> and replace the review CSV in your preparation folder.
Changes live in this page until downloaded; closing or refreshing loses unsaved edits. Additional webcam rows can be added in the CSV.</p>
<div class="bar"><input id="search" aria-label="Search products" placeholder="Search barcode, brand, product"><button id="download">Download review.csv</button></div>
<div class="bar"><button id="prev">Previous</button><span id="count"></span><button id="next">Next</button></div></header><main id="grid"></main>
<script>const cards=__CARDS__, fields=__FIELDS__;let page=0;const size=24,grid=document.getElementById('grid');
const search=document.getElementById('search');function render(){const q=search.value.toLowerCase();const found=cards.filter(c=>[c.code,c.product_name,c.brands].join(' ').toLowerCase().includes(q));
page=Math.min(page,Math.max(0,Math.ceil(found.length/size)-1));grid.replaceChildren();document.getElementById('count').textContent=`${found.length} photos · page ${page+1} of ${Math.max(1,Math.ceil(found.length/size))}`;
document.getElementById('prev').disabled=page===0;document.getElementById('next').disabled=(page+1)*size>=found.length;
for(const c of found.slice(page*size,(page+1)*size)){const a=document.createElement('article');const im=document.createElement('img');im.src=c.preview||'';im.alt=c.product_name||c.code;a.append(im);
const h=document.createElement('h3');h.textContent=c.code;a.append(h);const flag=document.createElement('p');flag.className='flag';flag.textContent=c.flags.join(' · ');a.append(flag);
for(const [key,title,options] of [['product_name','Product / flavor'],['brands','Brand'],['quantity','Package size and pack count'],['review_status','Review',['unreviewed','approved','rejected']],['split','Split',['','train','validation','test']],['capture_group','Capture session / original photo group'],['notes','Notes']]){
const label=document.createElement('label');label.textContent=title;const input=document.createElement(options?'select':'input');if(options)for(const v of options){const o=document.createElement('option');o.value=v;o.textContent=v||'Unassigned';input.append(o)}input.value=c[key]||'';input.addEventListener('change',()=>c[key]=input.value);label.append(input);a.append(label)}grid.append(a)}}
search.addEventListener('input',()=>{page=0;render()});document.getElementById('prev').onclick=()=>{page--;render()};document.getElementById('next').onclick=()=>{page++;render()};
document.getElementById('download').onclick=()=>{const esc=v=>'"'+String(v??'').replaceAll('"','""')+'"';const csv=[fields.join(','),...cards.map(c=>fields.map(k=>esc(c[k])).join(','))].join('\\r\\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='review.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};render();</script></html>'''
    path.write_text(page.replace("__CARDS__", payload).replace("__FIELDS__", json.dumps(FIELDS)))


def prepare(root, output, review=None):
    root, output = Path(root).resolve(), Path(output).resolve()
    manifest = root / "manifest.csv"
    originals = read_csv(manifest)
    if not originals or not {"code", "image_key", "product_name", "brands", "quantity"}.issubset(originals[0]):
        raise ValueError("Expected the downloaded Open Food Facts manifest.csv schema")
    output.mkdir(parents=True, exist_ok=True)
    review = Path(review).resolve() if review else output / "review.csv"
    if not review.exists():
        if review != output / "review.csv":
            raise ValueError("The supplied review CSV does not exist")
        with review.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            for row in originals:
                writer.writerow({**{k: row.get(k, "") for k in FIELDS},
                                 "image_path": f"images/{row['code']}_{Path(row['image_key']).name}",
                                 "capture_group": f"off:{row['code']}:{Path(row['image_key']).stem}",
                                 "review_status": "unreviewed", "split": ""})
    rows = read_csv(review)
    if not rows or not set(FIELDS).issubset(rows[0]):
        raise ValueError("Review CSV is empty or is missing required columns")
    cards, approved, errors, bad = [], [], [], []
    hashes = defaultdict(list)
    group_splits = defaultdict(set)
    for number, original in enumerate(rows, 2):
        row = {k: original.get(k, "").strip() for k in FIELDS}
        flags = []
        info = {}
        try:
            if not row["image_path"]:
                raise ValueError("Missing image_path")
            path = safe_image_path(root, row["image_path"])
            info = image_info(path)
            if min(info["width"], info["height"]) < 128:
                flags.append("Narrow image: inspect detail")
        except (OSError, ValueError, Image.DecompressionBombError) as error:
            bad.append({"line": number, "path": row["image_path"], "error": str(error)})
            flags.append("Missing or invalid image")
        for field in ("product_name", "brands", "quantity"):
            if not row[field]:
                flags.append(f"Missing {field}")
        if row["review_status"] not in {"unreviewed", "approved", "rejected"}:
            errors.append(f"Line {number}: invalid review_status")
        if row["review_status"] == "approved":
            row_errors = []
            if not re.fullmatch(r"\d{8}|\d{12,14}", row["code"]):
                row_errors.append("code must be a string of 8 or 12–14 digits")
            for field in ("product_name", "brands", "quantity", "capture_group", "source"):
                if not row[field]:
                    row_errors.append(f"missing {field}")
            if row["split"] not in SPLITS:
                row_errors.append("assign train, validation or test")
            if not info:
                row_errors.append("missing or invalid image")
            if row_errors:
                errors.append(f"Line {number}: " + "; ".join(row_errors))
            else:
                item = {**row, **{k: v for k, v in info.items() if k != "preview"},
                        "path": os.path.relpath(path, output), "line": number}
                approved.append(item)
                hashes[info["pixel_sha256"]].append(item)
                group_splits[row["capture_group"]].add(row["split"])
        cards.append({**row, **info, "flags": flags})
    for group, splits in group_splits.items():
        if len(splits) > 1:
            errors.append(f"Capture group {group} appears in multiple splits")
    for items in hashes.values():
        if len(items) > 1:
            # Reject even same-split duplicates; they inflate weighting and may have conflicting labels.
            errors.append("Repeated image pixels in approved rows: " + ", ".join(str(x["line"]) for x in items))
    products = defaultdict(list)
    for item in approved:
        products[item["code"]].append(item)
    catalog = []
    for label, (code, items) in enumerate(sorted(products.items())):
        identities = {(x["product_name"], x["brands"], x["quantity"]) for x in items}
        if len(identities) != 1:
            errors.append(f"{code}: inconsistent reviewed name/brand/package size")
        available = {x["split"] for x in items}
        if available != set(SPLITS):
            errors.append(f"{code}: missing independent photos in {', '.join(sorted(set(SPLITS)-available))}")
        row = items[0]
        catalog.append({"label": label, "product_id": "off:" + code, "code": code,
                        "display_name": f"{row['brands']} {row['product_name']} — {row['quantity']}",
                        **{k: row[k] for k in ("product_name", "brands", "quantity")}})
        for item in items:
            item["label"] = label
    if len(catalog) < 2:
        errors.append("At least two reviewed products with independent train/validation/test photos are required")
    counts = Counter(x["split"] for x in approved)
    summary = {"source": "Open Food Facts local batch", "source_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
               "review_sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
               "source_rows": len(originals), "source_products": len({x['code'] for x in originals}),
               "source_images_per_code": dict(Counter(Counter(x['code'] for x in originals).values())),
               "source_missing_fields": {k: sum(not x.get(k, '').strip() for x in originals) for k in originals[0]},
               "review_rows": len(rows), "review_status": dict(Counter(x['review_status'] for x in cards)),
               "valid_images": sum('pixel_sha256' in x for x in cards), "invalid_images": bad,
               "narrow_images": sum('width' in x and min(x['width'], x['height']) < 128 for x in cards),
               "duplicate_pixel_groups": sum(n > 1 for n in Counter(x['pixel_sha256'] for x in cards if 'pixel_sha256' in x).values()),
               "reviewed_products": len(catalog), "split_counts": {s: counts[s] for s in SPLITS},
               "ready_for_training": not errors, "blocking_errors": errors,
               "evaluation": "Reviewed exact products; independent capture groups and unique images per split. No claim of webcam accuracy until measured.",
               "notes": ["US sales tag is source-reported; not current availability or visual identity verification.",
                         "One photo per product cannot supply independent classifier training and evaluation.",
                         "Package quantity must be visually verified; the source can contain serving sizes.",
                         "Capture groups must reflect real sessions, not invented IDs per adjacent frame."]}
    write_json(output / "dataset.json", summary)
    write_json(output / "labels.json", catalog if not errors else [])
    for split in SPLITS:
        with (output / f"{split}.jsonl").open("w") as handle:
            if not errors:
                for item in approved:
                    if item['split'] == split:
                        handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    gallery(output / "review.html", cards)
    # Keep an auditable inventory even when training is blocked.
    with (output / "candidates.jsonl").open("w") as handle:
        for card in cards:
            handle.write(json.dumps({k: v for k, v in card.items() if k != 'preview'}, ensure_ascii=False) + "\n")
    report = ["# Open Food Facts preparation report", "",
              f"Source: {len(originals):,} rows / {summary['source_products']:,} product codes.",
              f"Reviewed input: {summary['valid_images']:,} decodable photos; {len(bad)} invalid/missing.",
              f"Narrow photos (short side <128 px): {summary['narrow_images']}. Exact pixel duplicate groups: {summary['duplicate_pixel_groups']}.",
              f"Review states: {summary['review_status']}",
              f"Ready for training: **{summary['ready_for_training']}**.", "",
              "## Missing fields in source", "", *[f"- {k}: {v}" for k, v in summary['source_missing_fields'].items() if v], "",
              "## Remaining requirements", "", *[f"- {x}" for x in errors], "",
              *[f"- {x}" for x in summary['notes']], "",
              "Open review.html, correct metadata and download review.csv. Add reviewed webcam rows with independent capture groups and explicit splits. Rerun preparation.",
              "The minimum three independent views per product only allows a trial; collect more for meaningful evaluation."]
    (output / "REPORT.md").write_text("\n".join(report) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="data/openfoodfacts")
    parser.add_argument("--output", default="datasets/off-prepared")
    parser.add_argument("--review", help="Edited CSV; image_path is relative to --root")
    args = parser.parse_args()
    try:
        result = prepare(args.root, args.output, args.review)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps({k: result[k] for k in ('source_rows', 'valid_images', 'reviewed_products', 'split_counts', 'ready_for_training', 'blocking_errors')}, indent=2))
    # Audit-only preparation succeeds, but the trainer explicitly refuses non-ready datasets.


if __name__ == "__main__":
    main()
