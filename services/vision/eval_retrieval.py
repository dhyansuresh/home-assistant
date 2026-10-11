"""Compare classification and embedding retrieval on held-out photos of known catalog products.

Gallery: the one training photo per product (data/openfoodfacts). Queries: different photos of the
same products (download_off_heldout.py). For each model this reports top-k accuracy for
  * classifier  - the saved classification head, when the checkpoint has one
  * embed_mean  - nearest gallery photo using mean-pooled encoder patches (what the head sees)
  * embed_pool  - nearest gallery photo using SigLIP's attention-pooled image embedding
  * text        - nearest product name/brand text (SigLIP image-text checkpoints only)
  * fused       - per-query standardized embed_pool + text scores, averaged
Near-duplicates of the trained photo are excluded. Scores are rankings, not calibrated confidence.
"""
import argparse
import csv
import json
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps
from transformers import AutoConfig, AutoImageProcessor, AutoModel, AutoModelForImageClassification, AutoProcessor

from prepare_openfoodfacts import read_csv, write_json

KS = (1, 5, 10)


def device():
    if torch.cuda.is_available():
        return "cuda"
    return "mps" if torch.backends.mps.is_available() else "cpu"


def load_images(paths):
    images = []
    for path in paths:
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.load()
        images.append(image)
    return images


@torch.inference_mode()
def encode_images(model, processor, paths, run_on, batch_size, classifier):
    mean, pooled, logits = [], [], []
    vision = model.vision_model
    for start in range(0, len(paths), batch_size):
        pixels = processor(images=load_images(paths[start:start + batch_size]), return_tensors="pt")["pixel_values"].to(run_on)
        output = vision(pixel_values=pixels)
        patches = output.last_hidden_state.mean(dim=1)
        mean.append(patches.float().cpu())
        if getattr(output, "pooler_output", None) is not None:
            pooled.append(output.pooler_output.float().cpu())
        if classifier:
            logits.append(model.classifier(patches).float().cpu())
    cat = lambda xs: torch.cat(xs).numpy() if xs else None
    return cat(mean), cat(pooled), cat(logits)


@torch.inference_mode()
def encode_texts(model, processor, texts, run_on, batch_size):
    out = []
    for start in range(0, len(texts), batch_size):
        batch = processor(text=texts[start:start + batch_size], padding="max_length", max_length=64,
                          truncation=True, return_tensors="pt").to(run_on)
        features = model.get_text_features(**batch)
        features = getattr(features, "pooler_output", features)
        out.append(features.float().cpu())
    return torch.cat(out).numpy()


def normalize(x):
    return x / np.linalg.norm(x, axis=1, keepdims=True).clip(1e-12)


def score(scores, truth, roles):
    """scores: queries x products (higher is better); truth: product index per query."""
    order = np.argsort(-scores, axis=1)
    rank = (order == truth[:, None]).argmax(axis=1)
    best = scores[np.arange(len(truth)), order[:, 0]]
    correct = rank == 0

    def summary(mask):
        return {"queries": int(mask.sum()), **{f"top{k}": float((rank[mask] < k).mean()) for k in KS}}

    result = {"all": summary(np.ones(len(truth), bool))}
    for role in sorted(set(roles)):
        result[role] = summary(np.array([r == role for r in roles]))
    result["top1_score_when_correct_median"] = float(np.median(best[correct])) if correct.any() else None
    result["top1_score_when_wrong_median"] = float(np.median(best[~correct])) if (~correct).any() else None
    return result


def evaluate(model_name, catalog, queries, args):
    run_on = device()
    config = AutoConfig.from_pretrained(model_name)
    classifier = any("ForImageClassification" in a for a in (config.architectures or []))
    if classifier:
        model = AutoModelForImageClassification.from_pretrained(model_name, attn_implementation="eager")
        labels = {v: int(k) for k, v in model.config.id2label.items()}
        if any(f"off:{row['code']}" not in labels for row in catalog):
            raise ValueError(f"{model_name} labels do not cover the evaluated catalog")
        head_index = np.array([labels[f"off:{row['code']}"] for row in catalog])
    else:
        model = AutoModel.from_pretrained(model_name, attn_implementation="eager")
    model.to(run_on).eval()
    processor = AutoImageProcessor.from_pretrained(model_name)
    started = time.time()
    g_mean, g_pool, _ = encode_images(model, processor, [r["path"] for r in catalog], run_on, args.batch_size, False)
    q_mean, q_pool, q_logits = encode_images(model, processor, [q["path"] for q in queries], run_on, args.batch_size, classifier)
    truth = np.array([q["product"] for q in queries])
    roles = [q["role"] for q in queries]
    results = {"model": model_name, "device": run_on, "classifier_checkpoint": classifier,
               "gallery_products": len(catalog), "seconds": None, "methods": {}}
    if classifier:
        results["methods"]["classifier"] = score(q_logits[:, head_index], truth, roles)
    results["methods"]["embed_mean"] = score(normalize(q_mean) @ normalize(g_mean).T, truth, roles)
    if g_pool is not None:
        results["methods"]["embed_pool"] = score(normalize(q_pool) @ normalize(g_pool).T, truth, roles)
    if not classifier and hasattr(model, "get_text_features") and not args.no_text:
        text_processor = AutoProcessor.from_pretrained(model_name)
        texts = [f"a photo of {row['brands']} {row['product_name']}".lower().strip() for row in catalog]
        t = encode_texts(model, text_processor, texts, run_on, args.batch_size)
        image_scores, text_scores = normalize(q_pool) @ normalize(g_pool).T, normalize(q_pool) @ normalize(t).T
        results["methods"]["text"] = score(text_scores, truth, roles)
        z = lambda x: (x - x.mean(axis=1, keepdims=True)) / x.std(axis=1, keepdims=True).clip(1e-12)
        results["methods"]["fused"] = score(z(image_scores) + z(text_scores), truth, roles)
    results["seconds"] = round(time.time() - started, 1)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="append", required=True, help="Hub ID or local folder; repeat to compare")
    parser.add_argument("--manifest", default="data/openfoodfacts/manifest.csv")
    parser.add_argument("--images", default="data/openfoodfacts/images")
    parser.add_argument("--heldout", default="data/openfoodfacts_heldout")
    parser.add_argument("--output", required=True, help="JSON results file")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--no-text", action="store_true")
    args = parser.parse_args()
    if Path(args.output).exists():
        parser.error("Output exists; choose a new results file")

    rows = sorted(read_csv(Path(args.manifest)), key=lambda r: r["code"])
    catalog = [{**r, "path": str(Path(args.images) / f"{r['code']}_{Path(r['image_key']).name}")} for r in rows]
    index = {r["code"]: i for i, r in enumerate(catalog)}
    heldout = Path(args.heldout)
    with (heldout / "heldout.csv").open(newline="", encoding="utf-8") as handle:
        queries = [{"path": str(heldout / r["image_path"]), "product": index[r["code"]], "role": r["role"]}
                   for r in csv.DictReader(handle) if r["near_duplicate_of_trained"] == "False"]
    counts = defaultdict(int)
    for q in queries:
        counts[q["role"]] += 1
    report = {"gallery": "one training photo per product", "queries": len(queries), "queries_by_role": dict(counts),
              "products_queried": len({q["product"] for q in queries}),
              "note": ("Known-catalog ranking only. Unknown rejection and calibrated confidence are not measured. "
                       "Nutrition/ingredient photos show a different package side than the gallery front photo."),
              "runs": []}
    for name in args.model:
        print(f"Evaluating {name}", flush=True)
        report["runs"].append(evaluate(name, catalog, queries, args))
        for method, values in report["runs"][-1]["methods"].items():
            print(f"  {method:11s} all top1={values['all']['top1']:.3f} top5={values['all']['top5']:.3f}"
                  + (f"  front top1={values['front']['top1']:.3f}" if "front" in values else "")
                  + (f"  unselected top1={values['unselected']['top1']:.3f}" if "unselected" in values else ""), flush=True)
    write_json(Path(args.output), report)


if __name__ == "__main__":
    main()
