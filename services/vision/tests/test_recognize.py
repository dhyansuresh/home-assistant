"""Run: python -m unittest discover -s services/vision/tests -v  (no model download needed)"""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

VISION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VISION))
from app import main as service  # noqa: E402
from app.recognizer import Gallery, Recognizer  # noqa: E402


def unit(*values):
    v = np.array(values, np.float32)
    return v / np.linalg.norm(v)


class FakeEncoder:
    device = "cpu"

    def __init__(self, embedding):
        self.embedding = embedding

    def images(self, images):
        return np.stack([self.embedding for _ in images])


def write_gallery(folder, products, refs, owners, text=None):
    folder.mkdir()
    arrays = {"image": np.stack(refs), "image_product": np.array(owners)}
    if text is not None:
        arrays["text"] = np.stack(text)
    np.savez(folder / "embeddings.npz", **arrays)
    (folder / "gallery.json").write_text(json.dumps({"name": "test", "model": "fake", "products": products,
                                                     "suggested_unknown_threshold": {"value": 0.8}}))


def recognizer(gallery, query, threshold=0.8):
    r = Recognizer.__new__(Recognizer)
    r.gallery, r.encoder, r.threshold, r.top_k, r.model_id = Gallery(gallery), FakeEncoder(query), threshold, 3, "fake+gallery"
    return r


class RecognizerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.gallery = Path(self.temp.name) / "gallery"
        products = [{"name": "Pesto", "brand": "Barilla", "size_label": "190 g"}, {"name": "Ketchup", "brand": "Heinz"}]
        # Product 0 has two references; the best one should count, not the average.
        write_gallery(self.gallery, products, [unit(1, 0, 0), unit(0.2, 1, 0), unit(0, 0, 1)], [0, 0, 1])

    def test_best_reference_per_product_ranks_first(self):
        result = recognizer(self.gallery, unit(0.25, 1, 0)).recognize(Image.new("RGB", (8, 8)))
        self.assertFalse(result["unknown"])
        self.assertEqual([c["name"] for c in result["candidates"]], ["Pesto", "Ketchup"])
        self.assertEqual([c["rank"] for c in result["candidates"]], [1, 2])
        self.assertGreater(result["candidates"][0]["score"], result["candidates"][1]["score"])

    def test_below_threshold_is_unknown_with_no_candidates(self):
        result = recognizer(self.gallery, unit(1, 1, 1), threshold=0.9).recognize(Image.new("RGB", (8, 8)))
        self.assertEqual((result["unknown"], result["candidates"]), (True, []))

    def test_fused_scores_follow_rank(self):
        products = [{"name": f"P{i}"} for i in range(6)]
        refs = [unit(*np.eye(6)[i]) for i in range(6)]
        text = [unit(*np.eye(6)[(i + 1) % 6]) for i in range(6)]  # text disagrees with images
        folder = Path(self.temp.name) / "fused"
        write_gallery(folder, products, refs, list(range(6)), text)
        result = recognizer(folder, unit(1, 0.9, 0, 0, 0, 0), threshold=0.1).recognize(Image.new("RGB", (8, 8)))
        scores = [c["score"] for c in result["candidates"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_gallery_rejects_product_without_reference(self):
        folder = Path(self.temp.name) / "broken"
        write_gallery(folder, [{"name": "A"}, {"name": "B"}], [unit(1, 0)], [0])
        with self.assertRaises(ValueError):
            Gallery(folder)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        gallery = Path(temp.name) / "gallery"
        write_gallery(gallery, [{"name": "Pesto", "brand": "Barilla"}], [unit(1, 0)], [0])
        self.client = TestClient(service.app)
        service.state.update(recognizer=recognizer(gallery, unit(1, 0.1)), error=None)
        self.addCleanup(service.state.update, recognizer=None, error=None)

    def post(self, data, content_type="image/jpeg"):
        return self.client.post("/internal/recognize", files={"image": ("x.jpg", data, content_type)})

    def test_contract_shape(self):
        buffer = io.BytesIO()
        Image.new("RGB", (16, 16), "red").save(buffer, "JPEG")
        body = self.post(buffer.getvalue()).json()
        self.assertEqual(set(body), {"recognition_id", "model_id", "unknown", "requires_confirmation", "candidates"})
        self.assertIs(body["requires_confirmation"], True)
        self.assertEqual(set(body["candidates"][0]), {"name", "brand", "size_label", "rank", "score"})

    def test_rejects_bad_uploads(self):
        self.assertEqual(self.post(b"not an image").status_code, 400)
        self.assertEqual(self.post(b"hello", "text/plain").status_code, 400)
        self.assertEqual(self.post(b"").status_code, 400)
        self.assertEqual(self.post(b"0" * (service.MAX_IMAGE_BYTES + 1)).status_code, 413)

    def test_unloaded_model_is_503(self):
        service.state.update(recognizer=None, error="VISION_GALLERY is not configured")
        self.assertEqual(self.post(b"x").status_code, 503)


if __name__ == "__main__":
    unittest.main()
