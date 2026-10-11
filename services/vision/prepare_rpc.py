"""Create classification manifests from the official RPC COCO annotations."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def prepare(root, output, selected_annotations=None):
    root, output = Path(root).resolve(), Path(output)
    prepared = {}
    categories = None
    for split, source in [("train", "train2019"), ("validation", "val2019"), ("test", "test2019")]:
        annotation_path = root / f"instances_{source}.json"
        data = json.loads(annotation_path.read_text())
        current = sorted(data["categories"], key=lambda row: row["id"])
        if categories is not None and current != categories:
            raise ValueError(f"Category mappings differ in {annotation_path}")
        categories = current
        mapping = {row["id"]: index for index, row in enumerate(categories)}
        images = {row["id"]: row for row in data["images"]}
        rows = []
        for annotation in data["annotations"]:
            if selected_annotations is not None and annotation["id"] not in selected_annotations[source]:
                continue
            if annotation.get("iscrowd", 0):
                continue
            image = images[annotation["image_id"]]
            path = (root / source / image["file_name"]).resolve()
            if not path.is_relative_to(root / source):
                raise ValueError(f"Image path escapes split directory: {path}")
            if not path.is_file():
                raise FileNotFoundError(path)
            x, y, width, height = annotation["bbox"]
            if width <= 0 or height <= 0:
                raise ValueError(f"Invalid bounding box: {annotation['bbox']}")
            rows.append({"path": str(path), "bbox": [x, y, width, height],
                         "label": mapping[annotation["category_id"]],
                         "image_id": image["id"], "annotation_id": annotation["id"]})
        if not rows or set(row["label"] for row in rows) != set(mapping.values()):
            raise ValueError(f"Empty split or missing product classes: {split}")
        prepared[split] = (rows, hashlib.sha256(annotation_path.read_bytes()).hexdigest())
    output.mkdir(parents=True, exist_ok=True)
    # Keep all original metadata; numeric RPC categories must not be invented into brands/sizes.
    catalog = [{"label": index, "product_id": f"rpc:{row['id']}",
                "display_name": str(row.get("name", row["id"])), "rpc_category": row}
               for index, row in enumerate(categories)]
    (output / "labels.json").write_text(json.dumps(catalog, indent=2, ensure_ascii=False))
    metadata = {"source": "https://rpc-dataset.github.io/", "license": "CC BY-NC-SA 4.0",
                "image_root": str(root), "evaluation": "Ground-truth bounding-box crops; not detection or whole-frame accuracy",
                "splits": {}}
    for split, (rows, digest) in prepared.items():
        (output / f"{split}.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        metadata["splits"][split] = {"objects": len(rows), "annotation_sha256": digest,
                                     "class_counts": dict(Counter(row["label"] for row in rows))}
    (output / "dataset.json").write_text(json.dumps(metadata, indent=2))
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rpc-root", required=True)
    parser.add_argument("--output", default="datasets/rpc-manifests")
    args = parser.parse_args()
    prepare(args.rpc_root, args.output)
