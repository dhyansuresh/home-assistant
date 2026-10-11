"""Build a recognition gallery: embed reference photos of known products for the vision service.

Demo products (recommended): one folder per product, 3-5 photos each, taken with the demo camera.
    gallery_photos/
      barilla_pesto/  product.json  1.jpg 2.jpg 3.jpg     product.json: {"name": "Pesto alla Genovese",
      heinz_ketchup/  1.jpg 2.jpg                                        "brand": "Barilla", "size_label": "190 g"}
Without product.json the folder name becomes the product name. Open Food Facts catalog photos can
be added with --off-manifest (one photo each; source names/brands are unverified).

With two or more photos for at least two products, a leave-one-out check reports how often a photo
matches its own product and suggests an unknown threshold. That check reuses registration photos, so
confirm it with fresh photos before relying on it.
"""
import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.recognizer import Encoder, open_rgb, product_text  # noqa: E402

IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".heic"}


def folder_products(root):
    products, refs = [], []
    for folder in sorted(p for p in Path(root).iterdir() if p.is_dir()):
        photos = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_TYPES)
        if not photos:
            continue
        info = json.loads((folder / "product.json").read_text()) if (folder / "product.json").exists() else {}
        name = (info.get("name") or folder.name.replace("_", " ")).strip()
        products.append({"name": name, "brand": info.get("brand"), "size_label": info.get("size_label"),
                         "source": "HomePilot photos", "metadata_verified": bool(info.get("verified", False))})
        refs += [(len(products) - 1, photo) for photo in photos]
    return products, refs


def off_products(manifest, images):
    products, refs = [], []
    with open(manifest, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            name = (row.get("product_name") or "").strip() or f"OFF {row['code']}"
            products.append({"name": name, "brand": (row.get("brands") or "").split(",")[0].strip() or None,
                             "size_label": None, "source": f"Open Food Facts {row['code']}", "metadata_verified": False})
            refs.append((len(products) - 1, Path(images) / f"{row['code']}_{Path(row['image_key']).name}"))
    return products, refs


def leave_one_out(image, owner):
    """Each photo vs. its product's other photos (genuine) and all other products (impostor)."""
    sims = image @ image.T
    np.fill_diagonal(sims, -np.inf)
    genuine, impostor = [], []
    for i in range(len(owner)):
        same = owner == owner[i]
        same[i] = False
        if same.any():
            genuine.append(float(sims[i, same].max()))
            impostor.append(float(sims[i, ~(owner == owner[i])].max()))
    if len(genuine) < 2 or len(set(owner.tolist())) < 2:
        return None
    genuine, impostor = np.array(genuine), np.array(impostor)
    # Every result is user-confirmed, so favour accepting known products: keep 95% of genuine matches.
    # Registration photos share a session, so fresh photos score lower; recheck with new photos.
    best = float(np.quantile(genuine, 0.05))
    return {"value": round(best, 4), "rule": "5th percentile of leave-one-out genuine similarity",
            "photos_checked": len(genuine),
            "top1_leave_one_out": float((genuine > impostor).mean()),
            "genuine_median": float(np.median(genuine)), "impostor_median": float(np.median(impostor)),
            "genuine_accepted_at_threshold": float((genuine >= best).mean()),
            "impostor_rejected_at_threshold": float((impostor < best).mean()),
            "note": "Computed from registration photos only; verify with fresh photos and unknown products."}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--photos", help="Folder with one subfolder of photos per product")
    parser.add_argument("--off-manifest", help="Open Food Facts manifest.csv to add as catalog products")
    parser.add_argument("--off-images", default="data/openfoodfacts/images")
    parser.add_argument("--model", default="google/siglip2-base-patch16-224")
    parser.add_argument("--output", required=True, help="New gallery folder, e.g. models/galleries/demo")
    parser.add_argument("--device")
    args = parser.parse_args()
    if not args.photos and not args.off_manifest:
        parser.error("Give --photos and/or --off-manifest")
    output = Path(args.output)
    if output.exists() and any(output.iterdir()):
        parser.error("Output folder is not empty; choose a new gallery folder")

    products, refs = [], []
    for loader, source in ((folder_products, args.photos), (off_products, args.off_manifest)):
        if source:
            new_products, new_refs = (loader(source) if loader is folder_products else loader(source, args.off_images))
            offset = len(products)
            products += new_products
            refs += [(offset + p, path) for p, path in new_refs]
    if not products:
        parser.error("No product photos found")
    keys = [(p["name"].lower(), (p["brand"] or "").lower(), (p["size_label"] or "").lower()) for p in products]
    if len(set(keys)) != len(keys):
        parser.error("Two products share the same name/brand/size; candidates would be indistinguishable")

    encoder = Encoder(args.model, args.device)
    print(f"Embedding {len(refs)} photos of {len(products)} products on {encoder.device}", flush=True)
    image = encoder.images([open_rgb(path) for _, path in refs])
    owner = np.array([p for p, _ in refs])
    arrays = {"image": image.astype(np.float32), "image_product": owner}
    if encoder.has_text:
        arrays["text"] = encoder.texts([product_text(p) for p in products]).astype(np.float32)
    check = leave_one_out(image, owner)
    output.mkdir(parents=True, exist_ok=True)
    np.savez(output / "embeddings.npz", **arrays)
    metadata = {"name": output.name, "model": args.model, "created_at": datetime.now(timezone.utc).isoformat(),
                "products": products, "text_embeddings": encoder.has_text,
                "references": [{"product": int(p), "image": str(path),
                                "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()} for p, path in refs],
                "suggested_unknown_threshold": check,
                "scores": "Raw cosine similarity for ranking; not calibrated confidence."}
    (output / "gallery.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"gallery": str(output), "products": len(products), "photos": len(refs),
                      "suggested_unknown_threshold": check}, indent=2))
    if check is None:
        print("No threshold suggested (needs 2+ photos for 2+ products). Set VISION_UNKNOWN_THRESHOLD explicitly.")


if __name__ == "__main__":
    main()
