> Historical RPC workflow, superseded for US-product training by D-023. Use VISION_TRAINING.md for the current dataset. Environment notes and readiness claims below describe the earlier experiment.

# SigLIP2 training on AMD ROCm

This is a runnable training path, not a connected inference service. Run commands from the repository root on the AMD instance. The starting environment reported by the owner is PyTorch 2.9.1 (provider build), ROCm 7.2, Transformers 4.57.6, one AMD Radeon device with 48 GiB reported memory. The exact Radeon SKU and a full training run remain unverified.

## Selected data and model

Use [RPC](https://rpc-dataset.github.io/) as the public baseline and `google/siglip2-base-patch16-224` as the fixed-resolution SigLIP2 encoder. FixRes uses the SigLIP architecture supported by `AutoModelForImageClassification`. The new product classifier is randomly initialized; missing classifier weights and unused text-encoder weights when loading the base model are expected. This trains image classification, not image/text contrastive alignment. The OpenAI coordinator is not part of training.

RPC has 200 categories, 53,739 single-product training images, 6,000 multi-product validation images and 24,000 multi-product test images. License: CC BY-NC-SA 4.0; retain attribution and review suitability before commercial reuse. Verify that its specific products match the intended demo. A category identity does not prove complete brand/flavor/package-size metadata. `labels.json` preserves source category metadata and assigns namespaced IDs such as `rpc:1`; these are not global barcodes. Do not invent readable names or attach retailer prices until the team verifies an exact catalog mapping.

The preparation script uses annotated bounding boxes for all splits. Validation and test therefore measure classification on ground-truth product crops, not detection, counting, or recognition on an arbitrary full frame. The first webcam experiment should show one product close to the camera. Multiple-product scenes require a separate future detection/cropping step.

## 1. Get the code onto the GPU

On your laptop, review and commit the changed training files, then push your vision branch. On the GPU, inside its existing clone:

```bash
git switch dev1/vision-baseline
git pull --ff-only origin dev1/vision-baseline
python -m pip install -r services/vision/requirements-training.txt
unset TRANSFORMERS_CACHE
export HF_HOME="$PWD/.cache/huggingface"
```

Use the provider's Python environment (`/opt/venv/bin/python` if that is the active interpreter). Do not replace its working PyTorch/ROCm packages with a generic PyTorch installation. Training dependencies are separate from the lightweight vision HTTP dependencies. `HF_HOME` must be set in each new shell or your instance configuration.

## 2. Download and extract RPC

Obtain the official release through the [authors' Kaggle distribution](https://www.kaggle.com/datasets/diyer22/retail-product-checkout-dataset). Accept its terms and download/extract it on the GPU's persistent disk. The published release is roughly 15 GB; allow room for extraction, caches and training checkpoints. If using Kaggle's CLI, keep its credentials outside Git and follow the CLI's current authentication instructions; no credentials are needed by our preparation script.

Locate the directory containing this structure (an archive may add an outer directory):

```text
datasets/rpc/
  train2019/                 # JPEG images
  val2019/
  test2019/
  instances_train2019.json
  instances_val2019.json
  instances_test2019.json
```

Prepare manifests without duplicating images:

```bash
python services/vision/prepare_rpc.py --rpc-root datasets/rpc --output datasets/rpc-manifests
```

This validates category consistency, image paths and bounding-box dimensions, preserves original category metadata and records annotation hashes and per-class counts. It needs all three official splits. Paths in the manifests are absolute to this instance; regenerate them if you move the data. Image decoding and image-bound checks occur when a crop is loaded. Keep source datasets, manifests and trained weights out of Git.

## 3. Run a short GPU trial

```bash
python services/vision/train.py --output models/rpc-smoke --stage head --max-steps 20 --limit-train 400 --limit-eval 200 --batch-size 8 --accumulation 1
```

This downloads the model, trains the classifier briefly in full precision, evaluates a small subset and saves `models/rpc-smoke/final`. Confirm finite losses, a nonzero trainable parameter count, the expected GPU/ROCm fields in `run.json`, and a saved model/processor. The subsets are random and smoke accuracy is not a benchmark. The script rejects CPU training unless `--allow-cpu` is explicitly supplied. AMD uses PyTorch's `cuda` device interface.

Reload that saved checkpoint in a separate process:

```bash
python services/vision/train.py --model models/rpc-smoke/final --output models/rpc-smoke-reload --evaluate-only --limit-eval 200
```

If either command fails, fix that failure before a long run. A visible GPU alone does not prove compatibility with every model operation. Output directories must be new unless resuming a Trainer checkpoint.

## 4. Train the classifier, then fine-tune the encoder

Train just the classifier, preserving pretrained encoder weights:

```bash
python services/vision/train.py --output models/rpc-head --stage head --epochs 3 --learning-rate 0.001
```

Then initialize from the best saved head run and unfreeze the image encoder:

```bash
python services/vision/train.py --model models/rpc-head/final --output models/rpc-finetuned --stage finetune --epochs 3 --learning-rate 0.00001
```

These are starting hyperparameters, not tuned recommendations. Default batch size 8 with accumulation 4 gives an effective batch of 32 on one GPU. Both phases use deterministic checkpoint preprocessing without random crops/flips, preserving package text. The fine-tuning phase trains the full image encoder plus classifier; no text encoder is trained. Start in full precision. After successful forward/backward/save/reload, try a new run with `--precision bf16` only if supported, or test `--precision fp16`; compare stability before committing to it. If memory runs out, lower `--batch-size`; accumulation allows preserving the effective batch. No FlashAttention or fused optimizer is required.

If interrupted, resume a saved `checkpoint-N` with `--resume models/rpc-finetuned/checkpoint-N`, preserving the original stage, model argument, output, data and hyperparameters. Checkpoints are saved at epoch boundaries, so an early interruption may have no resumable checkpoint.

## 5. Final evaluation and interpretation

Choose settings using validation only. Run the official test crops once the experiment is selected:

```bash
python services/vision/train.py --model models/rpc-finetuned/final --output models/rpc-final-test --evaluate-only --eval-split test
```

Outputs include top-1 (`eval_accuracy`) and top-3 accuracy, Trainer metrics, model configuration/weights, image processor and class catalog. `run.json` records arguments, library/GPU versions, resolved model commit where available, and manifest hashes. Dataset preparation records source annotation hashes. Preserve the parent run folders to retain the two-stage training history. Compare head-only versus fine-tuned validation results; head-only is a baseline, not evidence that the encoder was fine-tuned.

Next collect fresh webcam/iPhone photos of actual supported demo products and measure their accuracy separately. Keep complete capture sessions apart when preparing train/validation/test; do not randomly split neighboring video frames. Exact size variants require verified distinct labels and enough visually informative photos. Unsupported brands remain unsupported, regardless of RPC benchmark accuracy.

This classifier always ranks known classes. It does not implement unknown rejection or calibrated confidence. Before connecting inference to inventory, evaluate out-of-catalog products, establish an abstention rule on separate validation data, and preserve mandatory user confirmation. The existing FastAPI vision endpoint remains a stub.

## Price lookup: separate proposed extension

The owner proposed a specialist agent that searches Amazon, Walmart and other retailers after identification. No retailer integration is implemented here, and this proposal does not add another agent to the recognition training pipeline. Start with a reviewed P1 issue owned by Agent/Backend. Match verified brand, variant, package size and pack count; reject uncertain matches. Return retailer, product URL, currency, price, observation time and relevant location/availability context. Explicitly distinguish unit prices, multipacks, promotions, shipping and membership prices. Treat retailer text as untrusted data. If access fails, report unavailable; never manufacture a price. Link observations to a verified catalog identity, never directly to an unmapped RPC numeric class. Do not train changing retailer prices into the vision model.

## Existing Food101 work

The prior `train.py` is preserved verbatim as `train_food101.py`, including any pre-existing edits. It is an archive of the experiment, not part of these commands. Existing saved ViT checkpoints remain untouched. A ViT Food101 checkpoint cannot initialize the SigLIP2 architecture; start from the selected SigLIP2 pretrained checkpoint.

## Local validation performed

Synthetic RPC-shaped fixtures verified manifest generation, contiguous label mapping and image crops. A tiny randomly initialized CPU SigLIP classifier verified a classifier update, frozen encoder behavior, encoder gradients after unfreezing and identical logits after save/reload. These checks do not establish real RPC accuracy or AMD compatibility.

The complete training command also passed two-step head training, two-step encoder fine-tuning, and saved-model test evaluation using synthetic fixtures and a tiny random CPU model under local Transformers 5.19. Cloud Transformers 4.57.6 and real RPC/AMD execution still require the documented short trial. `git diff --check` passed.

## Limited storage: RPC subset trial

The current Radeon instance has 25 GB persistent `/workspace` and a 4 GB memory-backed `/tmp`. Keep downloads and caches under `/workspace`. To avoid retaining a full archive and full extracted dataset, download the three official annotation JSON files individually using the Kaggle CLI, then extract their ZIPs if `--unzip` leaves archives.

`download_rpc_subset.py` defaults to 5 training crops and 2 validation/test crops per class, sampled deterministically from distinct source images within each class. It downloads only the referenced images via Kaggle's per-file endpoint, with two concurrent CLI requests, retries, image validation, resume by skipping valid files, and a 6 GiB free-space reserve. Original train/validation/test memberships remain separate. It writes subset manifests and selection provenance, preserving source annotation files. Larger counts may not fit; inspect the plan and monitor space. These small sets verify infrastructure and are not adequate evidence of final model performance.

```bash
python services/vision/download_rpc_subset.py --plan-only
python services/vision/download_rpc_subset.py
python services/vision/train.py --data-dir datasets/rpc-subset-manifests --output models/rpc-subset-smoke --stage head --max-steps 20 --batch-size 8 --accumulation 1
```

Run in the JupyterLab terminal: its proxy reaches Kaggle while the SSH shell has lacked the same outbound access. Do not run the full preparation command against this partially downloaded image tree. Use the subset manifests with `--data-dir` in every training/evaluation command. Increasing subset size changes evaluation data; do not compare scores as if test populations stayed fixed. Per-image requests can take time and may encounter rate limits; rerun the same command to resume.

Local synthetic checks passed deterministic sampling, selected-manifest generation, mocked per-image ZIP extraction, and skip-on-resume behavior. Actual RPC image downloads through the cloud proxy remain unverified.
