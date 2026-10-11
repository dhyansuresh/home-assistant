# SigLIP2 training with Open Food Facts on AMD ROCm

The current dataset is `data/openfoodfacts`: actual product photos and `manifest.csv`. The owner replaced the RPC data with this US-tagged Open Food Facts batch on 2026-10-10. RPC is no longer the selected US-product training source; its previous workflow is retained in [RPC_TRAINING_ARCHIVE.md](RPC_TRAINING_ARCHIVE.md).

This is a training workflow. The vision HTTP endpoint is still a stub, and unknown rejection remains to be implemented and evaluated. Price lookup is separate from image training.

## Training now with the approved images

The owner approved the current photos. Use [OFF_TRAINING_EXPERIMENT.md](OFF_TRAINING_EXPERIMENT.md) to train on all 1,620 existing images with explicit `--training-only`. This experiment does not require additional images or verified package sizes. Independent evaluation remains unavailable. The stricter workflow below is for preparing measured train/validation/test runs.

## What the audit found

- 1,620 rows, 1,620 distinct product codes, and 1,620 decodable JPEGs: **one photo per product**.
- Images are user-approved; product metadata has not been fully reviewed. Ten names, 20 brands and 430 quantities are missing. Every category is blank; categories are not needed for barcode-level classification.
- No exact decoded-pixel duplicates were found. Fifty-five photos have a short side under 128 pixels; inspect their readable detail.
- The quantity field is unreliable. In the sampled photos, Trader Joe’s lemon curd (`00078504`) shows 10.5 oz (300 g), while its record says 30 g. Do not copy serving sizes into package labels.
- The source README says these were selected from the first 10,000 records tagged `en:united-states` in export revision `cc3b846`. That is a partial, ordered sample, not a representative US catalog or verified current availability.
- The downloads are raw contributor photos associated with selected fronts. Some need cropping/rejection; they are not guaranteed to be clean front packshots.

**This batch alone cannot provide independent train/validation/test examples for an exact-product classifier.** Preparation creates a review catalog and reports that the strict train/validation/test workflow is blocked. The separate training-only experiment can proceed. It never duplicates a photo into different splits or invents labels. Augmented copies are not independent evaluation examples.

## 1. Audit and review locally

From the repository root with the existing Python environment:

```bash
python services/vision/prepare_openfoodfacts.py
```

Generated files in `datasets/off-prepared/`:

- `REPORT.md` and `dataset.json`: actual counts, source hashes and readiness.
- `review.html`: searchable, self-contained photo gallery with editable labels. Corrections remain in the browser until **Download review.csv** is clicked. Replace `datasets/off-prepared/review.csv` with that download. Keep code values as text if using a spreadsheet, so leading zeros survive.
- `review.csv`: editable image inventory; never overwritten on reruns.
- `candidates.jsonl`: image dimensions, checksums, source records and quality flags.
- `labels.json`, `train.jsonl`, `validation.jsonl`, `test.jsonl`: empty until the selected reviewed data passes the checks. A failed rebuild clears previously generated training manifests to prevent accidentally training stale data.

The source photos and source manifest are not changed. Rerun preparation after review edits or new photos. To intentionally start a fresh review, use a new `--output` directory. `--review PATH` reads a particular edited CSV.

## 2. Assemble a small, verified product set

Start with 20–50 products that the team can physically photograph. This is a proposed starting scope, not an accuracy guarantee. Verify the brand, flavor, package size, pack count, and barcode against the physical package and photo. Reject unusable photos or mismatched records. Use `approved` only after checking those details; supported states are `unreviewed`, `approved`, and `rejected`.

Save new photos inside `data/openfoodfacts/webcam/`. Add one row per new image to the review CSV. Copy the reviewed product identity fields from that product's row, then change the image path and source. Exact identity fields must match across that product's rows.

| Field | Meaning |
| --- | --- |
| `code` | Original product code as text; training uses namespaced ID `off:<code>`. Do not infer package size or normalize away leading zeros. |
| `image_path` | Relative to `data/openfoodfacts`, such as `webcam/00078504/session-a/01.jpg`. |
| `product_name`, `brands`, `quantity` | Reviewed identity, including flavor, full package size and pack count where relevant. |
| `review_status` | `approved` for verified usable images; other rows remain outside training. |
| `split` | Explicitly assign `train`, `validation`, or `test`. |
| `capture_group` | Real capture-session identifier. All neighboring frames and all products photographed in that session stay in one split. For OFF photos the generated group preserves the original photo identity. |
| `source` | `Open Food Facts` or, for example, `HomePilot webcam`. |
| `image_url`, `product_url` | Keep original source links. They may be empty for your own captures. |
| `notes` | Review evidence, corrections and rejection reasons. |

Use catalog photos plus session A for training, a different session B for validation, and session C for the final test. Change lighting/background/viewpoint between sessions. Aim initially for 20–40 training photos and 5–10 validation/test photos each per product, adjusting after inspecting the learning curve. The code's minimum of one unique example in every split per class only permits an infrastructure trial; it is not adequate performance evidence.

Do not randomly split adjacent video frames. Keep resized/augmented copies in the original split. The builder detects exact pixel duplicates and conflicting group assignments, but cannot prove independently collected sessions or catch all near-duplicates. All selected classes need all three splits. At least two reviewed classes are required.

```bash
python services/vision/prepare_openfoodfacts.py
python services/vision/train.py --check-data
```

On the current one-photo/unreviewed batch, the second command must stop with a clear data-readiness message, before loading a model. After the data passes, paths are relative to the manifest directory and survive transferring the same repository layout to Linux.

## 3. Transfer to AMD

Keep source photos, review files, prepared manifests, caches and weights outside Git. `/data/` is now ignored, but the 1,622 dataset files already staged by the owner remain staged: `.gitignore` does not remove index entries. Review and unstage those additions before a code commit; do not delete the local photos.

If GitHub access on the GPU is still unavailable, use file transfer from the **Mac terminal**, using the host/port from the active instance panel:

```bash
cd "/Volumes/Sandisk SSD/Projects/home assistant"
tar -czf /tmp/homepilot-off-training.tgz services/vision/train.py services/vision/prepare_openfoodfacts.py services/vision/requirements-training.txt data/openfoodfacts datasets/off-prepared docs/VISION_TRAINING.md
scp -P 33491 /tmp/homepilot-off-training.tgz root@36.150.116.206:/workspace/
```

That address/port is the last instance reported in this chat; replace it if the instance changed. Extract into a **new directory** on the GPU to preserve any cloud-side edits:

```bash
mkdir -p /workspace/homepilot-off-training
cd /workspace/homepilot-off-training
tar -xzf /workspace/homepilot-off-training.tgz
```

Use a new directory name for later transfers. The prepared relative paths work with this layout. The 25 GB persistent disk is sufficient for the current small image batch plus a modest run, but monitor free space as photos and checkpoints grow. Keep caches and outputs under `/workspace`, not the 4 GB temporary filesystem.

## 4. Verify the AMD environment and run a short trial

The owner reported Python 3.14.4, PyTorch `2.13.0+rocm10.0.0`, `torch.version.hip` `7.15.26333`, Transformers 4.57.6, and a Radeon Pro W7900D with 48 GiB. A GPU tensor calculation passed. Full SigLIP2 forward/backward/save/reload on that instance remains unverified.

Run network-dependent setup in the **JupyterLab terminal**, whose configured proxy previously reached the package mirror and Hugging Face. Preserve the provider's working PyTorch/ROCm installation:

```bash
python -m pip install -r services/vision/requirements-training.txt
unset TRANSFORMERS_CACHE
export HF_HOME="$PWD/.cache/huggingface"
python services/vision/train.py --check-data
python services/vision/train.py --output models/off-smoke --stage head --max-steps 20 --batch-size 8 --accumulation 1
python services/vision/train.py --model models/off-smoke/final --output models/off-smoke-reload --evaluate-only
```

The default data directory is now `datasets/off-prepared`. Use `--data-dir` to override it. Start from `google/siglip2-base-patch16-224`: FixRes uses the SigLIP classification architecture. A newly initialized classifier is expected. This path trains product classification; it does not train a text encoder or an OpenAI model. A previous RPC or Food101 classifier cannot be reused with a new product-label map.

The short trial must show finite losses and successful save/reload. Its accuracy is not a benchmark. Fresh output directories are required. AMD uses PyTorch's `cuda` interface; CPU requires explicit `--allow-cpu` for tiny local tests. The trainer verifies dataset readiness, label coverage, file checksums and split separation before any model download.

## 5. Train and evaluate

After the short GPU trial succeeds:

```bash
python services/vision/train.py --output models/off-head --stage head --epochs 3 --learning-rate 0.001
python services/vision/train.py --model models/off-head/final --output models/off-finetuned --stage finetune --epochs 3 --learning-rate 0.00001
python services/vision/train.py --model models/off-finetuned/final --output models/off-final-test --evaluate-only --eval-split test
```

Choose hyperparameters using validation only, then evaluate the selected checkpoint on the test set. Compare head-only and encoder-fine-tuned validation results. These learning rates and epoch counts are starting defaults. Batch size 8 and accumulation 4 give effective batch size 32 on one GPU. Default full precision avoids assuming mixed-precision support; try `--precision bf16` only after a successful trial and hardware support check. Keep checkpoint preprocessing consistent between training and inference; this version does not add random augmentation.

`run.json` records versions, GPU, arguments, manifest hashes, class counts and trainable parameter count. `final/` holds weights, processor and `labels.json`. The trainer checks saved product IDs before reusing a local checkpoint. Resume epoch checkpoints using `--resume models/off-finetuned/checkpoint-N` and the original stage/model/data/settings.

Top-1/top-3 scores apply only to the known catalog. This classifier always ranks known classes; it does not implement calibrated confidence or unknown rejection. Collect unsupported products separately, choose an abstention rule on validation evidence, and preserve user confirmation before inventory changes. Photos from new webcam/iPhone sessions are the relevant deployment evaluation.

## Validation and sources

Run the preparation tests with:

```bash
python -m unittest discover -s services/vision/tests -v
```

The tests use synthetic images to check independent splits, duplicate rejection, corrupt files, identity consistency, preserved reviews and portable paths. Validation on 2026-10-10: six preparation tests passed. An offline tiny SigLIP classifier completed two head-training steps, two encoder-fine-tuning steps and saved-model test evaluation under local Transformers 5.19. The real unreviewed batch was correctly rejected before model loading, and changing a prepared image was detected. These tests verify training mechanics only, not recognition quality or AMD compatibility.

- [Open Food Facts product records](https://huggingface.co/datasets/openfoodfacts/product-database)
- [Official image collection](https://openfoodfacts.github.io/openfoodfacts-server/api/aws-images-dataset/)
- [Open Food Facts licensing and attribution](https://openfoodfacts.github.io/openfoodfacts-server/api/tutorials/license-be-on-the-legal-side/)
- [SigLIP2 FixRes checkpoint](https://huggingface.co/google/siglip2-base-patch16-224)

Retain source URLs and attribution when distributing permitted photos or derived data. The prior `train_food101.py` and saved models are preserved as experiments.
