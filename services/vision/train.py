"""SigLIP2 FixRes product classification on reviewed local image manifests."""
import argparse
import hashlib
import inspect
import json
from pathlib import Path

import numpy as np
import torch
import transformers
from PIL import Image, ImageOps
from torch.utils.data import Dataset
from transformers import AutoImageProcessor, AutoModelForImageClassification, Trainer, TrainingArguments, set_seed


class ProductCrops(Dataset):
    def __init__(self, manifest, limit=0, seed=42):
        manifest = Path(manifest).resolve()
        self.rows = [json.loads(line) for line in manifest.read_text().splitlines() if line.strip()]
        for row in self.rows:
            row["path"] = str((manifest.parent / row["path"]).resolve())
        if limit and limit < len(self.rows):
            rng = np.random.default_rng(seed)
            indices = rng.choice(len(self.rows), size=limit, replace=False)
            self.rows = [self.rows[int(i)] for i in indices]

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        with Image.open(row["path"]) as source:
            # RPC boxes use original pixel coordinates; unboxed OFF/webcam photos use EXIF orientation.
            image = (source if row.get("bbox") is not None else ImageOps.exif_transpose(source)).convert("RGB")
        if row.get("bbox") is not None:
            x, y, width, height = row["bbox"]
            left, top = max(0, x), max(0, y)
            right, bottom = min(image.width, x + width), min(image.height, y + height)
            if right <= left or bottom <= top:
                raise ValueError(f"Bounding box outside image: {row['path']}")
            image = image.crop((left, top, right, bottom))
        return {"image": image, "label": row["label"]}


def validate_data(data_dir, training_only=False):
    """Fail before downloading a model or allocating GPU memory for unusable data."""
    data_dir = Path(data_dir)
    metadata_path = data_dir / "dataset.json"
    metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
    if metadata.get("ready_for_training") is False:
        raise ValueError("Dataset is not ready: " + "; ".join(metadata.get("blocking_errors", []))
                         + ". See REPORT.md and review.html in the data directory.")
    if metadata.get("mode") == "training_only_experiment" and not training_only:
        raise ValueError("This dataset requires --training-only; independent evaluation is unavailable")
    catalog = json.loads((data_dir / "labels.json").read_text())
    ids = [row["product_id"] for row in catalog]
    labels = [row["label"] for row in catalog]
    if len(catalog) < 2 or len(set(ids)) != len(ids) or sorted(labels) != list(range(len(catalog))):
        raise ValueError("Need at least two unique product IDs and unique contiguous labels starting at zero")
    seen_paths, seen_hashes, seen_groups, counts = {}, {}, {}, {}
    seen_crops = set()
    for split in (("train",) if training_only else ("train", "validation", "test")):
        rows = ProductCrops(data_dir / f"{split}.jsonl").rows
        if not rows or {r["label"] for r in rows} != set(labels):
            raise ValueError(f"{split}: every known product needs independent examples")
        for row in rows:
            path = Path(row["path"])
            if not path.is_file():
                raise ValueError(f"Missing image: {path}")
            crop = (path, tuple(row.get("bbox") or ()))
            if (path in seen_paths and seen_paths[path] != split) or crop in seen_crops:
                raise ValueError(f"Repeated image/crop across dataset: {path}")
            seen_paths[path] = split
            seen_crops.add(crop)
            if row.get("file_sha256") and hashlib.sha256(path.read_bytes()).hexdigest() != row["file_sha256"]:
                raise ValueError(f"Image changed since preparation: {path}; rerun preparation")
            if row.get("pixel_sha256"):
                if row["pixel_sha256"] in seen_hashes:
                    raise ValueError("Duplicate photo pixels in prepared data")
                seen_hashes[row["pixel_sha256"]] = split
            group = row.get("capture_group")
            if group and group in seen_groups and seen_groups[group] != split:
                raise ValueError(f"Capture group spans splits: {group}")
            if group:
                seen_groups[group] = split
        counts[split] = len(rows)
    return catalog, metadata, counts


def metrics(prediction):
    logits = prediction.predictions
    if isinstance(logits, tuple):
        logits = logits[0]
    labels = prediction.label_ids
    ranked = np.argsort(logits, axis=1)[:, -min(3, logits.shape[1]):]
    return {"accuracy": float((logits.argmax(axis=1) == labels).mean()),
            "top3_accuracy": float((ranked == labels[:, None]).any(axis=1).mean())}


def class_report(prediction, catalog):
    logits = prediction.predictions[0] if isinstance(prediction.predictions, tuple) else prediction.predictions
    predicted, labels = logits.argmax(axis=1), prediction.label_ids
    names = [row["product_id"] for row in sorted(catalog, key=lambda row: row["label"])]
    confusion = np.zeros((len(names), len(names)), dtype=int)
    np.add.at(confusion, (labels, predicted), 1)
    per_class = {name: {"support": int(confusion[i].sum()),
                        "recall": float(confusion[i, i] / confusion[i].sum()) if confusion[i].sum() else None,
                        "precision": float(confusion[i, i] / confusion[:, i].sum()) if confusion[:, i].sum() else None}
                 for i, name in enumerate(names)}
    off_diagonal = [(int(confusion[i, j]), names[i], names[j]) for i in range(len(names))
                    for j in range(len(names)) if i != j and confusion[i, j]]
    return {"per_class": per_class,
            "top_confusions": [{"true": t, "predicted": p, "count": c} for c, t, p in sorted(off_diagonal, reverse=True)[:20]],
            "confusion_matrix": {"labels": names, "rows_true_columns_predicted": confusion.tolist()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="datasets/off-prepared")
    parser.add_argument("--model", default="google/siglip2-base-patch16-224")
    parser.add_argument("--output")
    parser.add_argument("--check-data", action="store_true", help="Validate prepared data and exit without loading a model")
    parser.add_argument("--training-only", action="store_true", help="Experimental training without validation, test metrics or best-model selection")
    parser.add_argument("--stage", choices=["head", "finetune"], default="head")
    parser.add_argument("--epochs", type=float, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--accumulation", type=int, default=4)
    parser.add_argument("--learning-rate", type=float)
    parser.add_argument("--max-steps", type=int, default=-1)
    parser.add_argument("--limit-train", type=int, default=0)
    parser.add_argument("--limit-eval", type=int, default=0)
    parser.add_argument("--precision", choices=["fp32", "fp16", "bf16"], default="fp32")
    parser.add_argument("--evaluate-only", action="store_true")
    parser.add_argument("--eval-split", choices=["validation", "test"], default="validation")
    parser.add_argument("--resume", help="Trainer checkpoint directory; same stage/data/settings required")
    parser.add_argument("--new-head", action="store_true",
                        help="Reuse --model's image encoder with a newly initialized classifier for this dataset's labels")
    parser.add_argument("--allow-cpu", action="store_true", help="Only for a small local test")
    args = parser.parse_args()
    if args.training_only and (args.evaluate_only or args.eval_split == "test"):
        parser.error("--training-only cannot evaluate a validation or test set")
    if args.new_head and (args.evaluate_only or args.resume):
        parser.error("--new-head starts a new classifier; it cannot be evaluated or resumed directly")
    data_dir = Path(args.data_dir)
    try:
        catalog, metadata, split_counts = validate_data(data_dir, training_only=args.training_only)
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))
    if args.check_data:
        print(json.dumps({"products": len(catalog), "splits": split_counts, "ready": True}, indent=2))
        return
    if not args.output:
        parser.error("--output is required for training/evaluation")
    if args.eval_split == "test" and not args.evaluate_only:
        parser.error("Use test only for final evaluation, not training/model selection")
    if not torch.cuda.is_available() and not args.allow_cpu:
        parser.error("GPU unavailable. Verify the provider's ROCm/PyTorch environment")
    if not args.allow_cpu and not torch.version.hip:
        parser.error("This AMD training path requires a ROCm build of PyTorch")
    if args.precision == "bf16" and (not torch.cuda.is_available() or not torch.cuda.is_bf16_supported()):
        parser.error("BF16 not reported as supported; start with fp32")
    output = Path(args.output).resolve()
    if output.exists() and any(output.iterdir()) and not args.resume:
        parser.error("Output directory is not empty; choose a new run directory or --resume")
    set_seed(42)
    id2label = {row["label"]: row["product_id"] for row in catalog}
    for directory in [None if args.new_head else args.model, args.resume]:
        if not directory:
            continue
        saved = Path(directory) / "labels.json"
        if args.resume and directory == args.resume and not saved.exists():
            saved = Path(directory).parent / "labels.json"
        if saved.exists():
            previous = {r["label"]: r["product_id"] for r in json.loads(saved.read_text())}
            if previous != id2label:
                parser.error("Saved checkpoint product labels differ; start a new classifier from the base model")
    processor = AutoImageProcessor.from_pretrained(args.model)
    model = AutoModelForImageClassification.from_pretrained(
        args.model, num_labels=len(catalog), id2label=id2label,
        label2id={value: key for key, value in id2label.items()}, attn_implementation="eager",
        ignore_mismatched_sizes=args.new_head)
    if args.new_head:
        # Same-sized label sets would otherwise keep the old classifier's unrelated weights.
        model.classifier.reset_parameters()
    if args.stage == "head":
        for name, parameter in model.named_parameters():
            parameter.requires_grad = name.startswith("classifier.")
    else:
        for parameter in model.parameters():
            parameter.requires_grad = True
    if not any(p.requires_grad for p in model.parameters()):
        raise ValueError("No trainable classifier parameters found")

    def collate(examples):
        batch = processor(images=[row["image"] for row in examples], return_tensors="pt")
        batch["labels"] = torch.tensor([row["label"] for row in examples], dtype=torch.long)
        return batch

    evaluation = None if args.training_only else ProductCrops(data_dir / f"{args.eval_split}.jsonl", args.limit_eval)
    training = None if args.evaluate_only else ProductCrops(data_dir / "train.jsonl", args.limit_train)
    # v4 takes a ratio separately; v5 supports fractional warmup_steps.
    warmup = ({"warmup_ratio": 0.1} if "warmup_ratio" in inspect.signature(TrainingArguments).parameters
              else {"warmup_steps": 0.1})
    config = TrainingArguments(
        output_dir=str(output), remove_unused_columns=False,
        eval_strategy="no" if args.training_only else "epoch", save_strategy="epoch", save_total_limit=2,
        learning_rate=args.learning_rate or (1e-3 if args.stage == "head" else 1e-5),
        per_device_train_batch_size=args.batch_size, per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.accumulation, num_train_epochs=args.epochs,
        max_steps=args.max_steps, optim="adamw_torch", weight_decay=0.01,
        fp16=args.precision == "fp16", bf16=args.precision == "bf16", use_cpu=args.allow_cpu,
        dataloader_num_workers=0, logging_steps=1 if args.max_steps > 0 else 20,
        report_to="none", load_best_model_at_end=not (args.evaluate_only or args.training_only),
        metric_for_best_model="accuracy", seed=42, **warmup)
    trainer = Trainer(model=model, args=config, train_dataset=training, eval_dataset=evaluation,
                      data_collator=collate, processing_class=processor, compute_metrics=metrics)
    output.mkdir(parents=True, exist_ok=True)
    provenance = {"arguments": vars(args), "torch": torch.__version__, "transformers": transformers.__version__,
                  "rocm": torch.version.hip, "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
                  "resolved_model_commit": getattr(model.config, "_commit_hash", None),
                  "evaluation": metadata.get("evaluation", "Prepared product crops; not detection accuracy or calibrated confidence"),
                  "split_counts": split_counts,
                  "trainable_parameters": sum(p.numel() for p in model.parameters() if p.requires_grad),
                  "manifest_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                      for path in sorted(data_dir.glob("*.json*"))}}
    (output / "run.json").write_text(json.dumps(provenance, indent=2))
    (output / "labels.json").write_text(json.dumps(catalog, indent=2, ensure_ascii=False))
    print(json.dumps(provenance, indent=2))
    if not args.evaluate_only:
        result = trainer.train(resume_from_checkpoint=args.resume)
        trainer.save_metrics("train", result.metrics)
        final = output / "final"
        trainer.save_model(str(final))
        processor.save_pretrained(final)
        (final / "labels.json").write_text(json.dumps(catalog, indent=2, ensure_ascii=False))
    if not args.training_only:
        prediction = trainer.predict(evaluation, metric_key_prefix="eval")
        scores = prediction.metrics
        trainer.save_metrics(args.eval_split, scores)
        (output / f"{args.eval_split}_report.json").write_text(
            json.dumps(class_report(prediction, catalog), indent=2, ensure_ascii=False))
        print(json.dumps(scores, indent=2))
    else:
        print("Experimental model saved. No held-out accuracy measured.")


if __name__ == "__main__":
    main()
