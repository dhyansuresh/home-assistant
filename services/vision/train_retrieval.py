"""Fine-tune SigLIP2 for product retrieval: image-text and multi-view image pairs (AMD ROCm).

Training data: an Open Food Facts subset from build_off_subset.py (front photo, product name/brand
text, optional second view) plus optional MIMEX webcam crops (prepare_mimex.py train split).
Loss: SigLIP sigmoid loss with same-product masking, so repeated MIMEX products and a product's two
views are positives rather than false negatives. Validation every epoch (and before training):
  * off_i2i / off_i2t - second view of held-out subset products -> their front photo / name text
  * mimex_text / mimex_proto - MIMEX validation session -> 28 product names / train-session image centroids
The best epoch by the mean of these top-1 scores is saved to best/. Evaluate final results on the
untouched 1,620-product set with eval_retrieval.py. Scores are rankings, not calibrated confidence.
"""
import argparse
import contextlib
import csv
import hashlib
import io
import json
import math
import random
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
import transformers
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoProcessor, get_cosine_schedule_with_warmup, set_seed


def text_for(brands, name):
    brand = (brands or "").split(",")[0].strip()
    return f"a photo of {brand} {name}".lower().replace("  ", " ").strip()


def open_rgb(path):
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.load()
    return image


def augment(image, rng):
    """Approximate webcam/phone conditions without mirroring package text."""
    w, h = image.size
    scale, ratio = rng.uniform(0.55, 1.0), math.exp(rng.uniform(math.log(3 / 4), math.log(4 / 3)))
    cw, ch = min(w, int(w * math.sqrt(scale * ratio))), min(h, int(h * math.sqrt(scale / ratio)))
    left, top = rng.randint(0, w - cw), rng.randint(0, h - ch)
    image = image.crop((left, top, left + cw, top + ch))
    if rng.random() < 0.5:
        image = image.rotate(rng.uniform(-20, 20), resample=Image.Resampling.BILINEAR, expand=True,
                             fillcolor=tuple(rng.randint(0, 255) for _ in range(3)))
    for enhancer in (ImageEnhance.Brightness, ImageEnhance.Contrast, ImageEnhance.Color):
        image = enhancer(image).enhance(rng.uniform(0.65, 1.35))
    if rng.random() < 0.3:
        image = image.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 1.8)))
    if rng.random() < 0.4:
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=rng.randint(35, 85))
        image = Image.open(io.BytesIO(buffer.getvalue())).convert("RGB")
    return image


def load_off(subset_dir, exclude_codes):
    subset_dir = Path(subset_dir)
    products, missing = {}, 0
    with (subset_dir / "manifest.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["code"] in exclude_codes:
                raise ValueError(f"Evaluation product {row['code']} is in the training subset")
            path = subset_dir / row["file_name"]
            if not path.is_file():
                missing += 1
                continue
            item = products.setdefault(row["code"], {"key": f"off:{row['code']}", "split": row["split"],
                                                     "text": text_for(row["brands"], row["product_name"]), "views": {}})
            item["views"][int(row["view"])] = str(path)
    train, validation = [], []
    for item in products.values():
        if 0 not in item["views"]:
            continue  # the front photo failed to download
        item["paths"] = [item["views"][v] for v in sorted(item["views"])]
        (validation if item["split"] == "validation" else train).append(item)
    return train, [v for v in validation if len(v["paths"]) == 2], missing


def load_mimex(data_dir, split):
    data_dir = Path(data_dir)
    names = {r["label"]: r for r in json.loads((data_dir / "labels.json").read_text())}
    rows = [json.loads(line) for line in (data_dir / f"{split}.jsonl").read_text().splitlines() if line.strip()]
    by_label = defaultdict(list)
    for row in rows:
        by_label[row["label"]].append(str(data_dir / row["path"]))
    return names, by_label


class Pairs(Dataset):
    def __init__(self, off_items, mimex_by_label, mimex_names, seed):
        self.items = [(i["key"], i["text"], i["paths"]) for i in off_items]
        for label, paths in mimex_by_label.items():
            entry = mimex_names[label]
            text = f"a photo of {entry['display_name']}".lower()
            self.items += [(entry["product_id"], text, paths) for _ in paths]  # one item per MIMEX image
        self.seed = seed
        self.epoch = 0

    def __len__(self):
        return len(self.items)

    def __getitem__(self, index):
        rng = random.Random(hash((self.seed, self.epoch, index)))
        key, text, paths = self.items[index]
        first, second = (rng.sample(paths, 2) if len(paths) > 1 else (paths[0], None))
        if key.startswith("off:") and len(paths) > 1:
            first, second = paths[0], paths[1]
        view1 = augment(open_rgb(first), rng)
        view2 = augment(open_rgb(second), rng) if second else None
        return key, text, view1, view2


class Collate:
    """Module-level (picklable) so DataLoader workers can use it under spawn/forkserver start methods."""

    def __init__(self, processor):
        self.processor = processor

    def __call__(self, batch):
        keys, texts, view1, view2 = zip(*batch)
        ids = {k: i for i, k in enumerate(dict.fromkeys(keys))}
        key_ids = torch.tensor([ids[k] for k in keys])
        has2 = torch.tensor([v is not None for v in view2])
        images = list(view1) + [v for v in view2 if v is not None]
        pixels = self.processor(images=images, return_tensors="pt")["pixel_values"]
        tokens = self.processor(text=list(texts), padding="max_length", max_length=64, truncation=True, return_tensors="pt")
        return pixels, tokens, key_ids, has2


def sigmoid_loss(a, b, same, scale, bias):
    logits = a @ b.T * scale.exp() + bias
    return -F.logsigmoid((2 * same.float() - 1) * logits).sum() / a.shape[0]


def features(output):
    return getattr(output, "pooler_output", output)


@torch.inference_mode()
def embed_images(model, processor, paths, device, batch_size, autocast):
    out = []
    for start in range(0, len(paths), batch_size):
        pixels = processor(images=[open_rgb(p) for p in paths[start:start + batch_size]], return_tensors="pt")
        with autocast():
            out.append(F.normalize(features(model.get_image_features(pixel_values=pixels["pixel_values"].to(device))).float(), dim=-1).cpu())
    return torch.cat(out)


@torch.inference_mode()
def embed_texts(model, processor, texts, device, batch_size, autocast):
    out = []
    for start in range(0, len(texts), batch_size):
        batch = processor(text=texts[start:start + batch_size], padding="max_length", max_length=64,
                          truncation=True, return_tensors="pt").to(device)
        with autocast():
            out.append(F.normalize(features(model.get_text_features(**batch)).float(), dim=-1).cpu())
    return torch.cat(out)


def topk(scores, truth, ks=(1, 5)):
    order = scores.argsort(dim=1, descending=True)
    rank = (order == truth[:, None]).float().argmax(dim=1)
    return {f"top{k}": float((rank < k).float().mean()) for k in ks}


def validate(model, processor, off_val, mimex, device, batch_size, autocast, proto_per_class=20):
    model.eval()
    results = {}
    if off_val:
        fronts = embed_images(model, processor, [i["paths"][0] for i in off_val], device, batch_size, autocast)
        seconds = embed_images(model, processor, [i["paths"][1] for i in off_val], device, batch_size, autocast)
        texts = embed_texts(model, processor, [i["text"] for i in off_val], device, batch_size, autocast)
        truth = torch.arange(len(off_val))
        results["off_i2i"] = topk(seconds @ fronts.T, truth)
        results["off_i2t"] = topk(seconds @ texts.T, truth)
        results["off_front_i2t"] = topk(fronts @ texts.T, truth)
    if mimex:
        names, train_by_label, val_by_label = mimex
        labels = sorted(names)
        texts = embed_texts(model, processor, [f"a photo of {names[l]['display_name']}".lower() for l in labels],
                            device, batch_size, autocast)
        rng = random.Random(0)
        protos = torch.stack([F.normalize(embed_images(model, processor, rng.sample(train_by_label[l], min(proto_per_class, len(train_by_label[l]))),
                                                       device, batch_size, autocast).mean(0), dim=0) for l in labels])
        queries, truth = [], []
        for i, l in enumerate(labels):
            sample = rng.sample(val_by_label[l], min(40, len(val_by_label[l])))
            queries += sample
            truth += [i] * len(sample)
        q = embed_images(model, processor, queries, device, batch_size, autocast)
        truth = torch.tensor(truth)
        results["mimex_text"] = topk(q @ texts.T, truth)
        results["mimex_proto"] = topk(q @ protos.T, truth)
    keys = [k for k in ("off_i2i", "off_i2t", "mimex_text", "mimex_proto") if k in results]
    results["selection_score"] = float(np.mean([results[k]["top1"] for k in keys]))
    model.train()
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--off-subset", default="data/off_retrieval_subset")
    parser.add_argument("--mimex", default="datasets/mimex-prepared", help="prepare_mimex.py output; '' to skip")
    parser.add_argument("--exclude-manifest", default="data/openfoodfacts/manifest.csv",
                        help="Evaluation products that must never appear in training")
    parser.add_argument("--model", default="google/siglip2-base-patch16-224")
    parser.add_argument("--output", required=True)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=128, help="Products per step; larger helps contrastive learning")
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    parser.add_argument("--text-lr-scale", type=float, default=0.5)
    parser.add_argument("--image-image-weight", type=float, default=1.0)
    parser.add_argument("--warmup", type=float, default=0.05)
    parser.add_argument("--precision", choices=["bf16", "fp32"], default="bf16")
    parser.add_argument("--gradient-checkpointing", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--max-steps", type=int, default=0, help="Stop early (smoke tests)")
    parser.add_argument("--limit-products", type=int, default=0, help="Use only N OFF training products (smoke tests)")
    parser.add_argument("--allow-cpu", action="store_true", help="Allow CPU/MPS for a tiny local test")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    output = Path(args.output)
    if output.exists() and any(output.iterdir()):
        parser.error("Output directory is not empty; choose a new run directory")
    if torch.cuda.is_available():
        device = "cuda"
    elif args.allow_cpu:
        device = "mps" if torch.backends.mps.is_available() else "cpu"
    else:
        parser.error("GPU unavailable. Verify the provider's ROCm/PyTorch environment, or pass --allow-cpu for a tiny test")
    if args.precision == "bf16" and not (device == "cuda" and torch.cuda.is_bf16_supported()):
        print("bf16 unavailable here; using fp32", flush=True)
        args.precision = "fp32"
    autocast = (lambda: torch.autocast("cuda", dtype=torch.bfloat16)) if args.precision == "bf16" else contextlib.nullcontext
    set_seed(args.seed)

    exclude = {r["code"] for r in csv.DictReader(open(args.exclude_manifest, newline="", encoding="utf-8-sig"))}
    off_train, off_val, missing = load_off(args.off_subset, exclude)
    if args.limit_products:
        off_train = off_train[:args.limit_products]
        off_val = off_val[:max(8, args.limit_products // 10)]
    mimex = None
    mimex_names, mimex_train = {}, {}
    if args.mimex:
        mimex_names, mimex_train = load_mimex(args.mimex, "train")
        _, mimex_val = load_mimex(args.mimex, "validation")
        if args.limit_products:
            mimex_train = {l: p[:4] for l, p in mimex_train.items()}
            mimex_val = {l: p[:2] for l, p in mimex_val.items()}
        mimex = (mimex_names, mimex_train, mimex_val)
    dataset = Pairs(off_train, mimex_train, mimex_names, args.seed)

    processor = AutoProcessor.from_pretrained(args.model)
    model = AutoModel.from_pretrained(args.model, attn_implementation="eager").to(device)
    if args.gradient_checkpointing:
        model.gradient_checkpointing_enable()
    ii_scale = torch.nn.Parameter(torch.tensor(math.log(10.0), device=device))
    ii_bias = torch.nn.Parameter(torch.tensor(-10.0, device=device))

    collate = Collate(processor)
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True, drop_last=len(dataset) > args.batch_size,
                        num_workers=args.workers, collate_fn=collate)  # workers restart each epoch so dataset.epoch reaches them
    steps = args.max_steps or args.epochs * len(loader)
    text_params = [p for n, p in model.named_parameters() if n.startswith("text_model")]
    other_params = [p for n, p in model.named_parameters() if not n.startswith("text_model") and n not in ("logit_scale", "logit_bias")]
    optimizer = torch.optim.AdamW([
        {"params": other_params, "lr": args.learning_rate},
        {"params": text_params, "lr": args.learning_rate * args.text_lr_scale},
        {"params": [model.logit_scale, model.logit_bias, ii_scale, ii_bias], "lr": 1e-4, "weight_decay": 0.0},
    ], weight_decay=0.05)
    scheduler = get_cosine_schedule_with_warmup(optimizer, int(steps * args.warmup), steps)

    output.mkdir(parents=True, exist_ok=True)
    provenance = {"arguments": vars(args), "torch": torch.__version__, "transformers": transformers.__version__,
                  "rocm": getattr(torch.version, "hip", None),
                  "gpu": torch.cuda.get_device_name(0) if device == "cuda" else device,
                  "off_train_products": len(off_train), "off_validation_products": len(off_val),
                  "off_missing_photos": missing, "mimex_train_images": sum(len(v) for v in mimex_train.values()),
                  "training_items": len(dataset), "steps": steps,
                  "subset_manifest_sha256": hashlib.sha256((Path(args.off_subset) / "manifest.csv").read_bytes()).hexdigest(),
                  "evaluation": "Validation = held-out subset products and MIMEX session 3; final test = eval_retrieval.py on the 1,620-product set."}
    (output / "run.json").write_text(json.dumps(provenance, indent=2))
    print(json.dumps(provenance, indent=2), flush=True)

    history = [{"epoch": 0, **validate(model, processor, off_val, mimex, device, args.batch_size, autocast)}]
    print(json.dumps(history[-1]), flush=True)
    best = history[-1]["selection_score"]
    model.train()
    step, started = 0, time.time()
    for epoch in range(1, args.epochs + 1):
        dataset.epoch = epoch
        for pixels, tokens, key_ids, has2 in loader:
            pixels, tokens, key_ids, has2 = pixels.to(device), tokens.to(device), key_ids.to(device), has2.to(device)
            with autocast():
                img = F.normalize(features(model.get_image_features(pixel_values=pixels)).float(), dim=-1)
                txt = F.normalize(features(model.get_text_features(**tokens)).float(), dim=-1)
            n = len(key_ids)
            img_keys = torch.cat([key_ids, key_ids[has2]])
            loss_it = sigmoid_loss(img, txt, img_keys[:, None] == key_ids[None, :], model.logit_scale, model.logit_bias)
            loss = loss_it
            loss_ii = torch.zeros((), device=device)
            if has2.any():
                first, second = img[:n][has2], img[n:]
                k = key_ids[has2]
                loss_ii = sigmoid_loss(first, second, k[:, None] == k[None, :], ii_scale, ii_bias)
                loss = loss + args.image_image_weight * loss_ii
            if not torch.isfinite(loss):
                raise RuntimeError(f"Non-finite loss at step {step}")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            step += 1
            if step % 20 == 0 or step == 1 or args.max_steps:
                print(json.dumps({"step": step, "epoch": epoch, "loss": round(loss.item(), 4), "image_text": round(loss_it.item(), 4),
                                  "image_image": round(loss_ii.item(), 4), "lr": scheduler.get_last_lr()[0],
                                  "elapsed_s": round(time.time() - started)}), flush=True)
            if step >= steps:
                break
        history.append({"epoch": epoch, "step": step, **validate(model, processor, off_val, mimex, device, args.batch_size, autocast)})
        print(json.dumps(history[-1]), flush=True)
        (output / "history.json").write_text(json.dumps(history, indent=2))
        if history[-1]["selection_score"] > best:
            best = history[-1]["selection_score"]
            model.save_pretrained(output / "best")
            processor.save_pretrained(output / "best")
            (output / "best" / "selected.json").write_text(json.dumps(history[-1], indent=2))
        if step >= steps:
            break
    if not (output / "best").exists():
        print("No epoch beat the starting model on validation; best/ not written.", flush=True)
    print(json.dumps({"best_selection_score": best, "baseline_selection_score": history[0]["selection_score"]}), flush=True)


if __name__ == "__main__":
    main()
