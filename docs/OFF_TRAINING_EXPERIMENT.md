# Train using the existing approved Open Food Facts photos

The owner approved the 1,620 existing photos. They can be used now for an experimental 1,620-class classifier, using the source barcode IDs as labels. Additional photos are not a prerequisite for this training-only experiment. One example per class is highly prone to memorization; fresh-photo performance remains unmeasured.

Missing product names, brands and quantities do not block this experiment. They remain unverified source metadata and must not be presented as verified package details. No validation/test copies, invented labels, or accuracy estimates are created.

## On the AMD instance

Upload the updated `services/vision/train.py`, `prepare_off_experiment.py`, and `prepare_openfoodfacts.py`, plus `data/openfoodfacts` (including `manifest.csv`, `image_approval.json`, and `images/`). Keep the same layout under `/workspace/home-assistant`. Run in the Jupyter terminal if that is where Hugging Face network access works. Preserve the provider's installed ROCm PyTorch.

```bash
cd /workspace/home-assistant
python services/vision/prepare_off_experiment.py
python services/vision/train.py --data-dir datasets/off-experiment --training-only --check-data
export HF_HOME=/workspace/hf-cache
unset TRANSFORMERS_CACHE
python services/vision/train.py --data-dir datasets/off-experiment --training-only --stage head --max-steps 20 --output /workspace/models/off-smoke --batch-size 8 --accumulation 4 --precision fp32
```

Preparation refuses to overwrite an existing output folder; choose a new `--output` and matching `--data-dir` to rebuild. The smoke run only verifies that actual model loading, GPU training, and saving work; 20 steps do not cover all 1,620 images with these batch settings.

After the smoke run succeeds, run full head training followed by encoder fine-tuning:

```bash
python services/vision/train.py --data-dir datasets/off-experiment --training-only --stage head --epochs 3 --output /workspace/models/off-head --batch-size 8 --accumulation 4 --precision fp32
python services/vision/train.py --data-dir datasets/off-experiment --training-only --stage finetune --model /workspace/models/off-head/final --epochs 3 --output /workspace/models/off-finetuned --batch-size 8 --accumulation 4 --precision fp32
```

These are initial experiment settings, not validated optimums. No best checkpoint is selected using evaluation accuracy. The saved result is `/workspace/models/off-finetuned/final`. Training loss measures fitting to these source images, not real-world recognition. The existing strict reviewed train/validation/test workflow remains available for later measured evaluation. Never evaluate these same training photos as an independent test.

Local validation: tiny offline CPU head training and encoder tuning exercise saving and reload; real AMD SigLIP2 training must still be run on the cloud instance.

Implementation reference: [Hugging Face Trainer configuration](https://huggingface.co/docs/transformers/v4.57.1/en/main_classes/trainer).
