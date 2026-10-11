"""Run: python -m unittest discover -s services/vision/tests -v"""
import csv
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

VISION = Path(__file__).resolve().parents[1]
# This fallback also allows the isolated staging copy to run before installation.
if not (VISION / 'prepare_openfoodfacts.py').exists():
    VISION = Path(__file__).resolve().parent
sys.path.insert(0, str(VISION))
from prepare_openfoodfacts import FIELDS, prepare


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'data'
        self.out = self.base / 'prepared'
        (self.root / 'images').mkdir(parents=True)
        rows = []
        for i, code in enumerate(('00012345', '00012346')):
            Image.new('RGB', (160, 200), (i*100, 20, 30)).save(self.root / 'images' / f'{code}_1.400.jpg')
            rows.append({'code': code, 'image_key': 'data/1.400.jpg', 'product_name': f'Product {i}',
                         'brands': 'Fixture', 'quantity': '12 oz', 'source': 'Synthetic fixture'})
        with (self.root / 'manifest.csv').open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)

    def complete_review(self):
        prepare(self.root, self.out)
        with (self.out / 'review.csv').open() as f:
            rows = list(csv.DictReader(f))
        all_rows = []
        for i, row in enumerate(rows):
            for j, split in enumerate(('train', 'validation', 'test')):
                path = f'images/{row["code"]}_{split}.jpg'
                Image.new('RGB', (160, 200), (i*90, j*80, 90)).save(self.root / path)
                all_rows.append({**row, 'image_path': path, 'review_status': 'approved', 'split': split,
                                 'capture_group': f'session-{split}'})
        self.write_review(all_rows)
        return all_rows

    def write_review(self, rows):
        with (self.out / 'review.csv').open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS); writer.writeheader(); writer.writerows(rows)

    def test_single_unreviewed_photo_does_not_create_training_split(self):
        report = prepare(self.root, self.out)
        self.assertFalse(report['ready_for_training'])
        self.assertEqual(report['valid_images'], 2)
        self.assertEqual((self.out/'train.jsonl').read_text(), '')
        self.assertIn('00012345', (self.out/'review.csv').read_text())

    def test_review_is_preserved_and_paths_survive_move(self):
        rows = self.complete_review()
        before = (self.out/'review.csv').read_bytes()
        self.assertTrue(prepare(self.root, self.out)['ready_for_training'])
        self.assertEqual(before, (self.out/'review.csv').read_bytes())
        catalog = json.loads((self.out/'labels.json').read_text())
        self.assertEqual(catalog[0]['product_id'], 'off:00012345')
        moved = self.base / 'moved'
        shutil.copytree(self.root, moved/'data'); shutil.copytree(self.out, moved/'prepared')
        row = json.loads((moved/'prepared'/'train.jsonl').read_text().splitlines()[0])
        self.assertFalse(Path(row['path']).is_absolute())
        self.assertTrue((moved/'prepared'/row['path']).is_file())

    def test_identical_pixels_cannot_cross_splits_or_labels(self):
        rows = self.complete_review()
        shutil.copyfile(self.root/rows[0]['image_path'], self.root/rows[4]['image_path'])
        report = prepare(self.root, self.out)
        self.assertFalse(report['ready_for_training'])
        self.assertTrue(any('Repeated image pixels' in e for e in report['blocking_errors']))

    def test_capture_session_cannot_cross_splits(self):
        rows = self.complete_review(); rows[1]['capture_group'] = rows[0]['capture_group']; self.write_review(rows)
        self.assertTrue(any('multiple splits' in e for e in prepare(self.root, self.out)['blocking_errors']))

    def test_missing_size_inconsistent_identity_and_corruption_block(self):
        rows = self.complete_review()
        rows[0]['quantity'] = ''; rows[1]['quantity'] = '30 oz'
        self.write_review(rows)
        (self.root/rows[4]['image_path']).write_text('not a jpeg')
        report = prepare(self.root, self.out)
        self.assertFalse(report['ready_for_training'])
        self.assertEqual(len(report['invalid_images']), 1)
        self.assertEqual((self.out/'train.jsonl').read_text(), '')

    def test_path_traversal_is_rejected(self):
        rows = self.complete_review(); rows[0]['image_path'] = '../secret.jpg'; self.write_review(rows)
        report = prepare(self.root, self.out)
        self.assertFalse(report['ready_for_training'])
        self.assertIn('inside the dataset root', report['invalid_images'][0]['error'])


if __name__ == '__main__':
    unittest.main()
