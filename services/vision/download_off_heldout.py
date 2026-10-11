"""Download additional Open Food Facts photos of already-trained products for held-out evaluation.

For each product in the trained manifest, list its other raw 400px uploads in the AWS key index,
excluding the exact photo used for training. Each photo is tagged with its role from the product
record (front, nutrition, ingredients, packaging, or unselected) so results can be split by view.
Exact and near-duplicate copies of the trained photo are flagged rather than treated as new views.
"""
import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import time
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageOps

from prepare_openfoodfacts import read_csv, write_json

BASE = "https://openfoodfacts-images.s3.eu-west-3.amazonaws.com/"
ROLE_ORDER = ("front", "unselected", "packaging", "ingredients", "nutrition")
FIELDS = ["code", "imgid", "role", "image_path", "image_key", "image_url", "trained_image_key",
          "file_sha256", "pixel_sha256", "dhash", "dhash_distance_to_trained", "near_duplicate_of_trained"]


def folder(code):
    padded = code.zfill(13)
    return f"data/{padded[:3]}/{padded[3:6]}/{padded[6:9]}/{padded[9:]}"


def dhash(image, size=8):
    gray = ImageOps.grayscale(image).resize((size + 1, size), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    bits = [pixels[r * (size + 1) + c] > pixels[r * (size + 1) + c + 1] for r in range(size) for c in range(size)]
    return int("".join("1" if b else "0" for b in bits), 2)


def image_hashes(data):
    with Image.open(io.BytesIO(data)) as source:
        if source.format != "JPEG":
            raise ValueError("not a JPEG")
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.load()
    return hashlib.sha256(str(image.size).encode() + image.tobytes()).hexdigest(), dhash(image)


def fetch(url, attempts=5):
    error = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "HomePilot-heldout-eval/1.0 (hackathon research)"})
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404):
                raise
            error = exc
        except Exception as exc:  # network errors are retried
            error = exc
        time.sleep(min(30, 2 ** attempt))
    raise error


def plan(manifest, products_parquet, data_keys, max_per_product):
    import pyarrow.parquet as pq

    trained = {row["code"]: row["image_key"] for row in read_csv(Path(manifest))}
    roles = defaultdict(lambda: defaultdict(set))
    table = pq.read_table(products_parquet, columns=["code", "images"])
    for code, images in zip(table["code"].to_pylist(), table["images"].to_pylist()):
        if code not in trained:
            continue
        for item in images or []:
            key = item.get("key") or ""
            if key.isdigit():
                roles[code][key]  # raw upload; role filled from selections below
            elif item.get("imgid") is not None and "_" in key:
                roles[code][str(item["imgid"])].add(key.split("_")[0])
    folders = {folder(code): code for code in trained}
    available = defaultdict(set)
    pattern = re.compile(r"^/?(data/\d{3}/\d{3}/\d{3}/\d+)/(\d+)\.400\.jpg$")
    with gzip.open(data_keys, "rt") as source:
        for line in source:
            match = pattern.match(line.strip())
            if match and match.group(1) in folders:
                available[folders[match.group(1)]].add(match.group(2))
    selected, counts = [], Counter()
    for code, trained_key in sorted(trained.items()):
        trained_id = Path(trained_key).name.split(".")[0]
        options = []
        for imgid in available[code] - {trained_id}:
            found = roles[code].get(imgid, set())
            role = next((r for r in ROLE_ORDER if r in found), "unselected")
            options.append((ROLE_ORDER.index(role), int(imgid), role))
        counts["products_with_extra_photo"] += bool(options)
        counts["extra_photos_available"] += len(options)
        for _, imgid, role in sorted(options)[:max_per_product]:
            key = f"{folder(code)}/{imgid}.400.jpg"
            selected.append({"code": code, "imgid": str(imgid), "role": role, "image_key": key,
                             "image_url": BASE + key, "trained_image_key": trained_key})
    counts["trained_products"] = len(trained)
    return selected, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="data/openfoodfacts/manifest.csv")
    parser.add_argument("--trained-images", default="data/openfoodfacts/images")
    parser.add_argument("--products-parquet", required=True, help="US product parquet with code and images columns")
    parser.add_argument("--data-keys", required=True, help="Open Food Facts AWS data_keys.gz index")
    parser.add_argument("--output", default="data/openfoodfacts_heldout")
    parser.add_argument("--max-per-product", type=int, default=3)
    parser.add_argument("--near-duplicate-bits", type=int, default=6, help="dHash Hamming distance treated as the same photo")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()

    output = Path(args.output)
    selected, counts = plan(args.manifest, args.products_parquet, args.data_keys, args.max_per_product)
    counts.update(Counter(f"selected_{row['role']}" for row in selected))
    print(json.dumps(dict(counts), indent=2), flush=True)
    if args.plan_only:
        return
    (output / "images").mkdir(parents=True, exist_ok=True)
    trained_dir = Path(args.trained_images)
    trained_hash = {}
    for row in read_csv(Path(args.manifest)):
        data = (trained_dir / f"{row['code']}_{Path(row['image_key']).name}").read_bytes()
        trained_hash[row["code"]] = image_hashes(data)

    def download(row):
        path = output / "images" / f"{row['code']}_{row['imgid']}.400.jpg"
        try:
            data = path.read_bytes() if path.exists() else None
            if data is not None:
                hashes = image_hashes(data)
            else:
                data = fetch(row["image_url"])
                hashes = image_hashes(data)
                path.with_suffix(".part").write_bytes(data)
                path.with_suffix(".part").replace(path)
        except Exception as exc:
            return {**row, "error": f"{type(exc).__name__}: {exc}"}
        pixels, digest = hashes
        trained_pixels, trained_digest = trained_hash[row["code"]]
        distance = bin(digest ^ trained_digest).count("1")
        return {**row, "image_path": path.relative_to(output).as_posix(),
                "file_sha256": hashlib.sha256(data).hexdigest(), "pixel_sha256": pixels, "dhash": f"{digest:016x}",
                "dhash_distance_to_trained": distance,
                "near_duplicate_of_trained": pixels == trained_pixels or distance <= args.near_duplicate_bits}

    with ThreadPoolExecutor(args.workers) as pool:
        results = list(pool.map(download, selected))
    good = [r for r in results if "error" not in r]
    failures = [r for r in results if "error" in r]
    with (output / "heldout.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(good)
    summary = {**counts, "downloaded": len(good), "failed": len(failures),
               "near_duplicates_of_trained": sum(r["near_duplicate_of_trained"] for r in good),
               "independent_views": sum(not r["near_duplicate_of_trained"] for r in good),
               "products_with_independent_view": len({r["code"] for r in good if not r["near_duplicate_of_trained"]}),
               "by_role": dict(Counter(r["role"] for r in good if not r["near_duplicate_of_trained"])),
               "failures": failures[:50],
               "use": "Held-out evaluation only. Never add these photos to training for the 1,620-product experiment.",
               "source": "Open Food Facts AWS images (CC BY-SA); keep image_url attribution"}
    write_json(output / "download.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k != "failures"}, indent=2))


if __name__ == "__main__":
    main()
