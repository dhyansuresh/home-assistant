"""Prepare Roboflow R2P3 (COCO boxes) as grouped category-classification crops for train.py.

The Roboflow export places rotated copies of one photo in different splits, so its
train/valid/test folders are not independent. This script pools all three exports,
groups every crop by its source photo (IMG_####), and assigns whole groups to
train/validation/test deterministically, stratified by each photo's main category.
"""
import argparse
import hashlib
import json
import os
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

from prepare_openfoodfacts import write_json

SOURCE_PHOTO = re.compile(r"^(IMG_\d+)")


def prepare(source, output, fractions=(0.7, 0.15, 0.15), max_side=448, min_box=32, seed=42):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new output directory to preserve earlier preparations")
    crops, categories = [], None
    for export in ("train", "valid", "test"):
        coco = json.loads((source / export / "_annotations.coco.json").read_text())
        names = {c["id"]: c["name"] for c in coco["categories"]}
        if categories is None:
            categories = names
        elif categories != names:
            raise ValueError("R2P3 exports use different category lists")
        images = {i["id"]: i for i in coco["images"]}
        for annotation in coco["annotations"]:
            image = images[annotation["image_id"]]
            match = SOURCE_PHOTO.match(image["file_name"])
            if not match:
                raise ValueError(f"Cannot identify source photo: {image['file_name']}")
            crops.append({"export": export, "file": image["file_name"], "group": match.group(1),
                          "category": names[annotation["category_id"]], "bbox": annotation["bbox"]})
    # Category 0 is Roboflow's unused supercategory ("food").
    used = sorted({c["category"] for c in crops})
    catalog = [{"label": i, "product_id": f"r2p3:{name.lower().replace(' ', '_')}", "display_name": name,
                "source_metadata": {"r2p3_category": name}, "metadata_verified": False, "level": "category"}
               for i, name in enumerate(used)]
    label_of = {name: i for i, name in enumerate(used)}

    groups = defaultdict(list)
    for crop in crops:
        groups[crop["group"]].append(crop)
    by_category = defaultdict(list)
    for group, members in sorted(groups.items()):
        by_category[Counter(c["category"] for c in members).most_common(1)[0][0]].append(group)
    assignment, rng = {}, random.Random(seed)
    for category, members in sorted(by_category.items()):
        rng.shuffle(members)
        n_val, n_test = round(len(members) * fractions[1]), round(len(members) * fractions[2])
        for i, group in enumerate(members):
            assignment[group] = "validation" if i < n_val else "test" if i < n_val + n_test else "train"

    rows, seen, dropped = {"train": [], "validation": [], "test": []}, set(), Counter()
    for crop in crops:
        split = assignment[crop["group"]]
        x, y, w, h = crop["bbox"]
        with Image.open(source / crop["export"] / crop["file"]) as photo:
            # Boxes are in stored pixel coordinates; Roboflow exports have no EXIF rotation to apply.
            photo = photo.convert("RGB")
            box = (max(0, round(x)), max(0, round(y)), min(photo.width, round(x + w)), min(photo.height, round(y + h)))
            if box[2] - box[0] < min_box or box[3] - box[1] < min_box:
                dropped["box_too_small"] += 1
                continue
            image = photo.crop(box)
        image.thumbnail((max_side, max_side))
        pixels = hashlib.sha256(str(image.size).encode() + image.tobytes()).hexdigest()
        if pixels in seen:
            dropped["duplicate_pixels"] += 1
            continue
        seen.add(pixels)
        name = f"{Path(crop['file']).stem}_{box[0]}_{box[1]}_{box[2]}_{box[3]}.jpg"
        path = output / "crops" / split / crop["category"].lower().replace(" ", "_") / name
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path, quality=95)
        rows[split].append({"label": label_of[crop["category"]], "path": os.path.relpath(path, output),
                            "capture_group": f"r2p3:{crop['group']}", "source": "Roboflow R2P3 v1",
                            "source_file": f"{crop['export']}/{crop['file']}", "source_bbox": crop["bbox"],
                            "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "pixel_sha256": pixels})

    counts = {split: Counter(r["label"] for r in values) for split, values in rows.items()}
    blocking = [f"{split}: no examples for {name}" for split in rows for name in used
                if not counts[split][label_of[name]]]
    metadata = {"mode": "grouped_train_validation_test", "ready_for_training": not blocking,
                "blocking_errors": blocking, "source": "https://universe.roboflow.com/object-detection/r2p3",
                "categories": len(catalog), "split_counts": {s: len(v) for s, v in rows.items()},
                "source_photos": {s: len({r["capture_group"] for r in v}) for s, v in rows.items()},
                "split_rule": f"Grouped by source IMG id, stratified by main category, seed {seed}, fractions {list(fractions)}",
                "roboflow_split_leakage": {"source_photos": len(groups),
                                           "photos_in_multiple_exports": sum(len({c["export"] for c in m}) > 1
                                                                             for m in groups.values())},
                "crop": {"max_side": max_side, "min_box": min_box}, "dropped": dict(dropped),
                "per_class": {name: {s: counts[s][label_of[name]] for s in rows} for name in used},
                "evaluation": ("Generic grocery category of ground-truth box crops (6 classes). Rotated copies of a "
                               "source photo stay in one split, so split counts overstate independent photos. Not exact "
                               "product identity, detection accuracy, unknown rejection, or calibrated confidence."),
                "license": "Public Domain (Roboflow export README)"}
    write_json(output / "dataset.json", metadata)
    write_json(output / "labels.json", catalog)
    for split, values in rows.items():
        (output / f"{split}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in values))
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="data/R2P3")
    parser.add_argument("--output", default="datasets/r2p3-prepared")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    summary = prepare(args.source, args.output, seed=args.seed)
    print(json.dumps(summary, indent=2))
