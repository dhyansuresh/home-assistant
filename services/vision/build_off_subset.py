"""Select a random US Open Food Facts subset with up to two photo views for retrieval fine-tuning.

Writes a download manifest compatible with complete_aws_download.py (`download --manifest`).
Products used for held-out evaluation (the trained 1,620) are excluded by barcode and by
normalized brand+name, so a duplicate listing under another barcode cannot leak into training.
"""
import argparse
import csv
import gzip
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from download_off_heldout import ROLE_ORDER, folder
from prepare_openfoodfacts import read_csv, write_json

BASE = "https://openfoodfacts-images.s3.eu-west-3.amazonaws.com/"
FIELDS = ["file_name", "code", "product_name", "brands", "quantity", "language", "image_key", "image_url",
          "product_url", "image_uploader", "source", "review_status", "view", "role", "split"]


def identity(brands, name):
    """Normalized brand+name; identical keys are treated as the same product."""
    clean = lambda s: re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()
    return f"{clean(brands.split(',')[0] if brands else '')}|{clean(name)}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--complete-manifest", required=True, help="outputs/openfoodfacts_us_complete/manifest.csv")
    parser.add_argument("--products-parquet", required=True)
    parser.add_argument("--data-keys", required=True)
    parser.add_argument("--exclude-manifest", default="data/openfoodfacts/manifest.csv")
    parser.add_argument("--output", default="data/off_retrieval_subset")
    parser.add_argument("--products", type=int, default=100000)
    parser.add_argument("--validation-products", type=int, default=1500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip-view-role", action="append", dest="skip_roles",
                        help="Second-view roles to skip (default: nutrition; panels look alike across products)")
    args = parser.parse_args()
    import pyarrow.parquet as pq
    skip_roles = set(args.skip_roles or ["nutrition"])

    output = Path(args.output)
    if (output / "manifest.csv").exists():
        parser.error("Subset manifest already exists; choose a new --output")
    excluded = read_csv(Path(args.exclude_manifest))
    excluded_codes = {r["code"] for r in excluded}
    excluded_ids = {identity(r["brands"], r["product_name"]) for r in excluded} - {"|"}
    counts = Counter()
    by_identity = defaultdict(list)
    with open(args.complete_manifest, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            counts["catalog_products"] += 1
            key = identity(row["brands"], row["product_name"])
            if row["code"] in excluded_codes:
                counts["excluded_eval_barcode"] += 1
            elif key in excluded_ids:
                counts["excluded_eval_same_brand_name"] += 1
            elif not row["product_name"].strip():
                counts["excluded_missing_name"] += 1
            else:
                by_identity[key].append(row)
    rng = random.Random(args.seed)
    # One barcode per brand+name, so contrastive batches do not contain unlabeled duplicates.
    candidates = [rng.choice(rows) for _, rows in sorted(by_identity.items())]
    counts["excluded_duplicate_brand_name"] = sum(len(r) - 1 for r in by_identity.values())
    rng.shuffle(candidates)
    chosen = {row["code"]: row for row in candidates[:args.products]}

    roles = defaultdict(lambda: defaultdict(set))
    table = pq.read_table(args.products_parquet, columns=["code", "images"])
    for code, images in zip(table["code"].to_pylist(), table["images"].to_pylist()):
        if code in chosen:
            for item in images or []:
                key = item.get("key") or ""
                if "_" in key and item.get("imgid") is not None:
                    roles[code][str(item["imgid"])].add(key.split("_")[0])
    folders = {folder(code): code for code in chosen}
    available = defaultdict(set)
    pattern = re.compile(r"^/?(data/\d{3}/\d{3}/\d{3}/\d+)/(\d+)\.400\.jpg$")
    with gzip.open(args.data_keys, "rt") as source:
        for line in source:
            match = pattern.match(line.strip())
            if match and match.group(1) in folders:
                available[folders[match.group(1)]].add(match.group(2))

    rows, two_view = [], []
    for code, row in chosen.items():
        front_id = Path(row["image_key"]).name.split(".")[0]
        extras = []
        for imgid in available[code] - {front_id}:
            found = roles[code].get(imgid, set())
            role = next((r for r in ROLE_ORDER if r in found), "unselected")
            if role not in skip_roles:
                extras.append((ROLE_ORDER.index(role), int(imgid), role))
        views = [(front_id, "front")] + [(str(i), role) for _, i, role in sorted(extras)[:1]]
        if len(views) == 2:
            two_view.append(code)
        for view, (imgid, role) in enumerate(views):
            key = f"{folder(code)}/{imgid}.400.jpg"
            rows.append({**{k: row.get(k, "") for k in FIELDS},
                         "file_name": f"images/{code.zfill(13)[:3]}/{code}_{imgid}.400.jpg",
                         "image_key": key, "image_url": BASE + key, "view": view, "role": role})
    validation = set(rng.sample(sorted(two_view), min(args.validation_products, len(two_view))))
    for row in rows:
        row["split"] = "validation" if row["code"] in validation else "train"
    output.mkdir(parents=True, exist_ok=True)
    with (output / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: (r["code"], r["view"])))
    summary = {**counts, "selected_products": len(chosen), "products_with_two_views": len(two_view),
               "photos": len(rows), "validation_products": len(validation),
               "second_view_roles": dict(Counter(r["role"] for r in rows if r["view"] == 1)),
               "seed": args.seed, "skipped_second_view_roles": sorted(skip_roles),
               "rules": ("Random sample of US products with a name and an available front photo; one barcode per "
                         "normalized brand+name; evaluation products excluded by barcode and brand+name. Second view "
                         "prefers another front, then unselected, packaging, ingredients; skipped roles are never used."),
               "source": "Open Food Facts (ODbL data, CC BY-SA images); keep image_url attribution"}
    write_json(output / "subset.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
