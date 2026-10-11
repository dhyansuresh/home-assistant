# Test the saved HomePilot model on a fresh photo

The fine-tuned cloud model is reported saved at `/workspace/models/off-finetuned/final`.

1. Upload `predict_product.py` to `/workspace/home-assistant/services/vision/` in JupyterLab.
2. Photograph one of the same exact products from the training catalog. Use a new photo of the real package with the brand/flavor/size visible. A training image reused here tests loading but does not measure recognition on a new view.
3. Create `/workspace/home-assistant/test-images` and upload the photo as `product.jpg`.
4. In the JupyterLab terminal:

```bash
cd /workspace/home-assistant
python services/vision/predict_product.py --model /workspace/models/off-finetuned/final --image test-images/product.jpg --top-k 5
```

The command loads the saved model without downloading a checkpoint and runs on the AMD GPU. It prints five ranked product IDs, source names, and scores. Check the barcode ID against the real item: source names and sizes have not all been verified. Record whether the correct exact product is ranked first, in the first three, or missing from the first five.

Start with 5–10 different catalog products. Keep a record of the actual barcode, photo filename, first prediction and whether it was correct; then vary angle, distance and lighting. Also try an item outside the catalog: the current classifier still produces known-product candidates for it. Unknown-product rejection is not implemented, so do not treat a high score as verified recognition or automatically save an inventory change.

Scores are softmax rankings, not calibrated confidence percentages. The model trained on one source image per product; new-photo accuracy has not been measured. This testing script does not integrate with the app's HTTP endpoint or modify inventory.
