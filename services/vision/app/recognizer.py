"""SigLIP2 embedding recognizer: rank registered gallery products for one image, or return unknown.

A gallery (register_gallery.py) stores normalized reference-photo embeddings and, when the
checkpoint has a text tower, one name/brand text embedding per product. Ranking fuses image and
text similarity; unknown is decided on the best reference-photo cosine similarity. Returned scores
are the raw ranking values (fused z-scores, or cosine for small galleries), not probabilities.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps

FUSION_MIN_PRODUCTS = 5  # z-score fusion is unstable for tiny galleries; rank by image there
TEXT_WEIGHT = 0.5  # fresh MIMEX-session check: image 71.0%, equal fusion 72.4%, half-weight text 74.0% top-1


def pick_device(requested: str | None = None) -> str:
    if requested:
        return requested
    if torch.cuda.is_available():  # ROCm builds expose the AMD GPU as cuda
        return "cuda"
    return "mps" if torch.backends.mps.is_available() else "cpu"


def open_rgb(source) -> Image.Image:
    with Image.open(source) as image:
        rgb = ImageOps.exif_transpose(image).convert("RGB")
        rgb.load()
    return rgb


def product_text(product: dict) -> str:
    parts = [product.get("brand") or "", product["name"], product.get("size_label") or ""]
    return ("a photo of " + " ".join(p.strip() for p in parts if p and p.strip())).lower()


def _features(output):
    return getattr(output, "pooler_output", output)


class Encoder:
    """Loads a SigLIP image-text checkpoint once and embeds images/texts (L2-normalized)."""

    def __init__(self, model: str, device: str | None = None, batch_size: int = 32):
        from transformers import AutoModel, AutoProcessor

        self.model_name = model
        self.device = pick_device(device)
        self.processor = AutoProcessor.from_pretrained(model)
        self.model = AutoModel.from_pretrained(model, attn_implementation="eager").to(self.device).eval()
        if not hasattr(self.model, "get_image_features"):
            raise ValueError("Checkpoint must be a SigLIP image-text model (AutoModel with get_image_features)")
        self.has_text = hasattr(self.model, "get_text_features")
        self.batch_size = batch_size

    @torch.inference_mode()
    def images(self, images: list[Image.Image]) -> np.ndarray:
        out = []
        for start in range(0, len(images), self.batch_size):
            pixels = self.processor(images=images[start:start + self.batch_size], return_tensors="pt")["pixel_values"]
            features = _features(self.model.get_image_features(pixel_values=pixels.to(self.device))).float()
            out.append(torch.nn.functional.normalize(features, dim=-1).cpu().numpy())
        return np.concatenate(out) if out else np.zeros((0, 0), np.float32)

    @torch.inference_mode()
    def texts(self, texts: list[str]) -> np.ndarray:
        out = []
        for start in range(0, len(texts), self.batch_size):
            batch = self.processor(text=texts[start:start + self.batch_size], padding="max_length", max_length=64,
                                   truncation=True, return_tensors="pt").to(self.device)
            features = _features(self.model.get_text_features(**batch)).float()
            out.append(torch.nn.functional.normalize(features, dim=-1).cpu().numpy())
        return np.concatenate(out)


def standardize(values: np.ndarray) -> np.ndarray:
    return (values - values.mean()) / max(float(values.std()), 1e-6)


class Gallery:
    def __init__(self, directory: str | Path):
        directory = Path(directory)
        self.metadata = json.loads((directory / "gallery.json").read_text())
        arrays = np.load(directory / "embeddings.npz")
        self.products = self.metadata["products"]
        self.image = arrays["image"].astype(np.float32)
        self.image_product = arrays["image_product"].astype(np.int64)
        self.text = arrays["text"].astype(np.float32) if "text" in arrays.files else None
        if len(self.image) != len(self.image_product) or not len(self.products):
            raise ValueError("Gallery embeddings and products are inconsistent")
        if set(self.image_product.tolist()) != set(range(len(self.products))):
            raise ValueError("Every gallery product needs at least one reference photo")
        digest = hashlib.sha256((directory / "embeddings.npz").read_bytes()).hexdigest()[:12]
        self.gallery_id = f"{self.metadata.get('name', directory.name)}-{digest}"

    def score(self, query: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Return (ranking score, best reference-photo cosine) per product for one query embedding."""
        reference = self.image @ query
        image_best = np.full(len(self.products), -1.0, np.float32)
        np.maximum.at(image_best, self.image_product, reference)
        if self.text is not None and len(self.products) >= FUSION_MIN_PRODUCTS:
            ranking = standardize(image_best) + TEXT_WEIGHT * standardize(self.text @ query)
        else:
            ranking = image_best
        return ranking, image_best


class Recognizer:
    def __init__(self, model: str, gallery: str | Path, *, device: str | None = None,
                 unknown_threshold: float | None = None, top_k: int = 3):
        self.gallery = Gallery(gallery)
        if self.gallery.metadata.get("model") not in (None, model):
            raise ValueError(f"Gallery was built with {self.gallery.metadata['model']}, not {model}; rebuild it")
        self.encoder = Encoder(model, device)
        self.threshold = unknown_threshold if unknown_threshold is not None else \
            self.gallery.metadata.get("suggested_unknown_threshold", {}).get("value")
        if self.threshold is None:
            raise ValueError("No unknown threshold: register at least two photos of two products, or set one explicitly")
        self.top_k = top_k
        self.model_id = f"{Path(model).name if Path(model).exists() else model}+gallery:{self.gallery.gallery_id}"

    def recognize(self, image: Image.Image) -> dict:
        query = self.encoder.images([image])[0]
        ranking, image_best = self.gallery.score(query)
        order = np.argsort(-ranking)
        best = float(image_best.max())  # unknown uses the closest reference photo of any product
        if best < self.threshold:
            return {"unknown": True, "candidates": [], "best_similarity": best}
        candidates = []
        for rank, index in enumerate(order[:self.top_k], start=1):
            product = self.gallery.products[int(index)]
            candidates.append({"name": product["name"], "brand": product.get("brand") or None,
                               "size_label": product.get("size_label") or None, "rank": rank,
                               "score": round(float(ranking[index]), 4)})
        return {"unknown": False, "candidates": candidates, "best_similarity": best}
