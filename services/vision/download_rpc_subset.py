"""Download a reproducible, class-balanced RPC subset through the Kaggle CLI."""
import argparse
import json
import random
import shutil
import subprocess
import tempfile
import time
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image
from prepare_rpc import prepare

DATASET = "diyer22/retail-product-checkout-dataset"


def select(root, train_count, eval_count, seed):
    plans = {}
    categories = None
    for split, count in [("train2019", train_count), ("val2019", eval_count), ("test2019", eval_count)]:
        data = json.loads((root / f"instances_{split}.json").read_text())
        current = sorted(data["categories"], key=lambda row: row["id"])
        if categories is not None and current != categories:
            raise ValueError(f"Category metadata differs in {split}")
        categories = current
        images = {row["id"]: row for row in data["images"]}
        by_class = defaultdict(list)
        for annotation in data["annotations"]:
            if not annotation.get("iscrowd", 0):
                by_class[annotation["category_id"]].append(annotation)
        rng = random.Random(seed)
        chosen = []
        for category in categories:
            candidates = sorted(by_class[category["id"]], key=lambda row: row["id"])
            rng.shuffle(candidates)
            seen = set()
            for row in candidates:
                if row["image_id"] in seen:
                    continue
                seen.add(row["image_id"])
                chosen.append(row)
                if len(seen) == count:
                    break
            if len(seen) < count:
                raise ValueError(f"Not enough distinct images for category {category['id']} in {split}")
        filenames = sorted({images[row["image_id"]]["file_name"] for row in chosen})
        for filename in filenames:
            if Path(filename).name != filename:
                raise ValueError(f"Expected a plain RPC image filename: {filename}")
        plans[split] = {"annotation_ids": sorted(row["id"] for row in chosen), "filenames": filenames}
    return plans


def valid_image(path):
    if not path.is_file():
        return False
    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except (OSError, ValueError):
        return False


def fetch(root, split, filename):
    target = root / split / filename
    if valid_image(target):
        return
    remote = f"retail_product_checkout/{split}/{filename}"
    for attempt in range(3):
        if shutil.disk_usage(root).free < 6 * 1024**3:
            raise RuntimeError("Less than 6 GiB free; stopped to leave room for model artifacts")
        with tempfile.TemporaryDirectory(prefix="rpc-download-", dir=root) as temporary:
            staging = Path(temporary)
            command = ["kaggle", "datasets", "download", DATASET, "-f", remote, "-p", temporary, "--unzip", "--quiet"]
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=120)
                if result.returncode:
                    raise RuntimeError(f"Kaggle failed for {remote}: {result.stderr[-500:]}")
                matches = list(staging.rglob(filename))
                if matches:
                    shutil.copyfile(matches[0], target.with_suffix(".partial"))
                else:
                    # Some CLI/proxy combinations leave a zip even with --unzip.
                    found = False
                    for archive in staging.rglob("*.zip"):
                        with zipfile.ZipFile(archive) as zipped:
                            members = [entry for entry in zipped.infolist() if Path(entry.filename).name == filename]
                            if not members:
                                continue
                            if len(members) != 1 or members[0].file_size > 50 * 1024**2:
                                raise ValueError(f"Unexpected archive contents for {remote}")
                            with zipped.open(members[0]) as source, target.with_suffix(".partial").open("wb") as destination:
                                shutil.copyfileobj(source, destination)
                            found = True
                            break
                    if not found:
                        raise RuntimeError(f"Kaggle returned no expected image for {remote}")
                partial = target.with_suffix(".partial")
                if not valid_image(partial):
                    raise RuntimeError(f"Downloaded file is not a valid image: {remote}")
                partial.replace(target)
                return
            except (RuntimeError, OSError, subprocess.TimeoutExpired, zipfile.BadZipFile) as error:
                if attempt == 2:
                    raise RuntimeError(f"Download failed after retries: {remote}. {error}") from error
                time.sleep(2 * (attempt + 1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rpc-root", default="datasets/rpc")
    parser.add_argument("--output", default="datasets/rpc-subset-manifests")
    parser.add_argument("--train-per-class", type=int, default=5)
    parser.add_argument("--eval-per-class", type=int, default=2)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    if min(args.train_per_class, args.eval_per_class, args.workers) < 1:
        parser.error("Counts and workers must be positive")
    root = Path(args.rpc_root).resolve()
    plans = select(root, args.train_per_class, args.eval_per_class, args.seed)
    jobs = [(split, filename) for split, plan in plans.items() for filename in plan["filenames"]]
    for split, plan in plans.items():
        print(f"{split}: {len(plan['annotation_ids'])} product crops from {len(plan['filenames'])} images", flush=True)
    print(f"Free disk: {shutil.disk_usage(root).free / 1024**3:.1f} GiB", flush=True)
    if args.plan_only:
        return
    if shutil.which("kaggle") is None:
        parser.error("Install the Kaggle CLI first")
    for split in plans:
        (root / split).mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(fetch, root, split, filename) for split, filename in jobs]
        try:
            for completed, future in enumerate(as_completed(futures), start=1):
                future.result()
                if completed % 25 == 0 or completed == len(jobs):
                    print(f"Images ready: {completed}/{len(jobs)}", flush=True)
        except BaseException:
            for future in futures:
                future.cancel()
            raise
    selected = {split: set(plan["annotation_ids"]) for split, plan in plans.items()}
    prepare(root, args.output, selected_annotations=selected)
    output = Path(args.output)
    selection = {"seed": args.seed, "train_per_class": args.train_per_class, "eval_per_class": args.eval_per_class,
                 "purpose": "Small infrastructure trial; not the full RPC benchmark", "splits": plans}
    (output / "selection.json").write_text(json.dumps(selection, indent=2))
    print(f"Ready. Use train.py --data-dir {output}", flush=True)


if __name__ == "__main__":
    main()
