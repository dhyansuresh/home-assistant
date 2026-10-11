"""Prepare the local Anilot/MIMEX snapshot as grouped train/validation/test manifests for train.py.

Official MIMEX test rows stay in test. The official train rows are split by `sample_id`
(capture sample), so validation never shares a sample with training.
"""
import argparse
import hashlib
import io
import json
import os
from collections import Counter
from pathlib import Path

from PIL import Image

from prepare_openfoodfacts import write_json


def pixel_hash(data):
    with Image.open(io.BytesIO(data)) as source:
        image = source.convert("RGB")
        return hashlib.sha256(str(image.size).encode() + image.tobytes()).hexdigest(), image.size, source.format


def prepare(source, output, validation_samples=("3",)):
    from datasets import Image as ImageFeature, load_from_disk

    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new output directory to preserve earlier preparations")
    dataset = load_from_disk(str(source / "dataset"))
    download = json.loads((source / "download.json").read_text())
    names = dataset["train"].features["label"].names
    if dataset["test"].features["label"].names != names:
        raise ValueError("MIMEX train/test label names differ")
    catalog = [{"label": i, "product_id": f"mimex:{name}", "display_name": name.replace("_", " "),
                "source_metadata": {"mimex_label": name}, "metadata_verified": False}
               for i, name in enumerate(names)]

    rows, seen = {"train": [], "validation": [], "test": []}, {}
    dropped = Counter()
    (output / "images").mkdir(parents=True)
    for official in ("train", "test"):
        table = dataset[official].cast_column("image", ImageFeature(decode=False))
        for record in table:
            sample = str(record["sample_id"])
            split = "test" if official == "test" else ("validation" if sample in validation_samples else "train")
            data = record["image"]["bytes"]
            pixels, size, fmt = pixel_hash(data)
            if names[record["label"]] != record["product_name"]:
                raise ValueError(f"Label/product_name mismatch for {record['image_hash']}")
            if pixels in seen:
                # An identical photo in two places cannot count as independent evidence.
                first = seen[pixels]
                dropped["duplicate_pixels"] += 1
                if first["split"] != split or first["label"] != record["label"]:
                    first["conflict"] = True
                continue
            extension = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}.get(fmt)
            if not extension:
                raise ValueError(f"Unexpected image format {fmt}")
            path = output / "images" / split / names[record["label"]] / f"{record['image_hash']}.{extension}"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            row = {"label": record["label"], "path": os.path.relpath(path, output),
                   "capture_group": f"mimex:sample-{sample}", "source": "Anilot/MIMEX",
                   "source_split": official, "image_hash": record["image_hash"], "width": size[0], "height": size[1],
                   "file_sha256": hashlib.sha256(data).hexdigest(), "pixel_sha256": pixels}
            seen[pixels] = {"split": split, "label": record["label"], "row": row}
            rows[split].append(row)
    conflicts = [item["row"] for item in seen.values() if item.get("conflict")]
    for row in conflicts:
        # Remove the kept copy too when the same pixels were also in another split or label.
        for split in rows:
            if row in rows[split]:
                rows[split].remove(row)
                (output / row["path"]).unlink()
        dropped["cross_split_or_label_duplicates_removed"] += 1

    counts = {split: Counter(r["label"] for r in values) for split, values in rows.items()}
    blocking = [f"{split}: no examples for {names[label]}" for split in rows
                for label in range(len(names)) if not counts[split][label]]
    metadata = {"mode": "grouped_train_validation_test", "ready_for_training": not blocking,
                "blocking_errors": blocking, "source": download["source"], "source_revision": download["revision"],
                "products": len(catalog), "split_counts": {s: len(v) for s, v in rows.items()},
                "split_rule": {"train": "official train, sample_id not in " + ",".join(validation_samples),
                               "validation": "official train, sample_id in " + ",".join(validation_samples),
                               "test": "official test (all sample_id values)"},
                "sample_ids": {s: sorted({r["capture_group"] for r in v}) for s, v in rows.items()},
                "dropped": dict(dropped),
                "per_class": {names[l]: {s: counts[s][l] for s in rows} for l in range(len(names))},
                "evaluation": ("MIMEX product crops; validation and test use capture samples not seen in training. "
                               "Not detection accuracy, unknown rejection, or calibrated confidence. "
                               "MIMEX classes are brand-level and not verified barcode/package-size variants."),
                "license": "MIT per Hugging Face card; cite Tur et al., RTSI 2024"}
    write_json(output / "dataset.json", metadata)
    write_json(output / "labels.json", catalog)
    for split, values in rows.items():
        (output / f"{split}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in values))
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="data/mimex")
    parser.add_argument("--output", default="datasets/mimex-prepared")
    parser.add_argument("--validation-sample", action="append", dest="validation_samples",
                        help="Official-train sample_id held out for validation (default: 3)")
    args = parser.parse_args()
    summary = prepare(args.source, args.output, tuple(args.validation_samples or ("3",)))
    print(json.dumps({k: v for k, v in summary.items() if k != "per_class"}, indent=2))
