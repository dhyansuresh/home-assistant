"""Prepare user-approved OFF images for training only; no synthetic evaluation split."""
import argparse
import hashlib
import json
import os
from pathlib import Path

from prepare_openfoodfacts import image_info, read_csv, safe_image_path, write_json


def prepare(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new output directory to preserve earlier preparations")
    manifest = root / "manifest.csv"
    approval = json.loads((root / "image_approval.json").read_text())
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    if approval.get("status") != "approved_by_user" or approval.get("manifest_sha256") != digest:
        raise ValueError("Image approval does not match this manifest")
    approved = {r['path']: r['sha256'] for r in approval['images']}
    rows = sorted(read_csv(manifest), key=lambda r: r['code'])
    catalog, training, codes, pixels = [], [], set(), set()
    for label, row in enumerate(rows):
        code = row['code']
        if not code.isdigit() or code in codes:
            raise ValueError("Expected one image per unique numeric product code")
        codes.add(code)
        relative = f"images/{code}_{Path(row['image_key']).name}"
        path = safe_image_path(root, relative)
        info = image_info(path)
        if approved.get(relative) != info['file_sha256']:
            raise ValueError(f"Image approval missing or stale: {relative}")
        if info['pixel_sha256'] in pixels:
            raise ValueError("Duplicate pixels across product labels need review")
        pixels.add(info['pixel_sha256'])
        catalog.append({'label': label, 'product_id': f'off:{code}', 'code': code,
                        'display_name': row.get('product_name') or f'OFF {code}',
                        'source_metadata': {k: row.get(k, '') for k in ('product_name', 'brands', 'quantity', 'product_url')},
                        'metadata_verified': False})
        training.append({'label': label, 'path': os.path.relpath(path, output),
                         'capture_group': f'off:{code}', 'source': 'Open Food Facts',
                         **{k: info[k] for k in ('file_sha256', 'pixel_sha256')}})
    if len(catalog) < 2:
        raise ValueError("Need at least two product classes")
    output.mkdir(parents=True, exist_ok=True)
    metadata = {'mode': 'training_only_experiment', 'ready_for_training': True,
                'ready_for_evaluation': False, 'source_manifest_sha256': digest,
                'approval_sha256': hashlib.sha256((root / 'image_approval.json').read_bytes()).hexdigest(),
                'products': len(catalog), 'split_counts': {'train': len(training), 'validation': 0, 'test': 0},
                'evaluation': 'Not performed: one image per product. Training loss is not recognition accuracy. Source metadata remains unverified.'}
    write_json(output / 'dataset.json', metadata)
    write_json(output / 'labels.json', catalog)
    (output / 'train.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in training))
    for split in ('validation', 'test'):
        (output / f'{split}.jsonl').write_text('')
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='data/openfoodfacts')
    parser.add_argument('--output', default='datasets/off-experiment')
    args = parser.parse_args()
    print(json.dumps(prepare(args.root, args.output), indent=2))
