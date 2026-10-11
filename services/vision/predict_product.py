"""Inspect ranked candidates from a local HomePilot classifier using a fresh photo."""
import argparse
import json
from pathlib import Path

import torch
from PIL import Image, ImageOps
from transformers import AutoImageProcessor, AutoModelForImageClassification


def predict(model_dir, image_path, top_k=5, allow_cpu=False):
    model_dir = Path(model_dir).resolve()
    if top_k < 1:
        raise ValueError('top-k must be positive')
    catalog = json.loads((model_dir / 'labels.json').read_text())
    entries = {row['label']: row for row in catalog}
    if len(entries) != len(catalog) or set(entries) != set(range(len(catalog))):
        raise ValueError('labels.json must contain unique contiguous numeric labels')
    if allow_cpu:
        device = 'cpu'
    elif torch.cuda.is_available() and torch.version.hip:
        device = 'cuda'
    else:
        raise ValueError('AMD GPU unavailable; use --allow-cpu only for local testing')
    processor = AutoImageProcessor.from_pretrained(model_dir, local_files_only=True)
    model = AutoModelForImageClassification.from_pretrained(
        model_dir, local_files_only=True, attn_implementation='eager')
    if model.config.num_labels != len(catalog):
        raise ValueError('Classifier size and labels.json differ')
    for label, row in entries.items():
        if model.config.id2label.get(label) != row['product_id']:
            raise ValueError('Model label mapping and labels.json differ')
    with Image.open(image_path) as source:
        photo = ImageOps.exif_transpose(source).convert('RGB')
        photo.load()
    model.to(device).eval()
    batch = {key: value.to(device) for key, value in processor(images=photo, return_tensors='pt').items()}
    with torch.inference_mode():
        logits = model(**batch).logits[0].float()
        if not torch.isfinite(logits).all():
            raise ValueError('Model produced non-finite scores')
        scores, indices = logits.softmax(dim=-1).topk(min(top_k, len(catalog)))
    candidates = []
    for score, label in zip(scores.tolist(), indices.tolist()):
        row = entries[label]
        candidates.append({'rank':len(candidates)+1, 'product_id':row['product_id'],
                           'display_name':row.get('display_name',row['product_id']),
                           'softmax_score':round(score,6),
                           'source_metadata':row.get('source_metadata', {}),
                           'metadata_verified':row.get('metadata_verified',False)})
    return {'image':str(Path(image_path).resolve()), 'model':str(model_dir),
            'device':torch.cuda.get_device_name(0) if device=='cuda' else 'CPU',
            'candidates':candidates, 'requires_confirmation':True,
            'unknown_detection':'not_implemented',
            'note':'Ranked candidates only. Scores are not calibrated confidence. This classifier also ranks known products for an unfamiliar object.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True, help='Local final model folder including labels.json')
    parser.add_argument('--image', required=True)
    parser.add_argument('--top-k', type=int, default=5)
    parser.add_argument('--allow-cpu', action='store_true')
    args = parser.parse_args()
    print(json.dumps(predict(args.model,args.image,args.top_k,args.allow_cpu),indent=2,ensure_ascii=False))


if __name__ == '__main__':
    main()
