#!/usr/bin/env bash
# Train/validate/test separate MIMEX (28 products) and R2P3 (6 categories) classifiers on the AMD GPU.
# For each dataset: (A) base SigLIP2 head, (B) OFF-finetuned encoder + new head, (C) B with the encoder unfrozen.
# The run with the best validation accuracy is then evaluated once on the held-out test split.
# Usage (repo root): OFF_MODEL=/workspace/models/off-finetuned/final RUN=/workspace/models/run1 bash services/vision/train_mimex_r2p3.sh [mimex|r2p3]
set -euo pipefail
OFF_MODEL=${OFF_MODEL:-/workspace/models/off-finetuned/final}
RUN=${RUN:?Set RUN to a new output directory, for example /workspace/models/mimex-r2p3-1}
COMMON=(--batch-size "${BATCH:-8}" --accumulation "${ACCUM:-4}" --precision "${PRECISION:-fp32}" --epochs "${EPOCHS:-3}")
TRAIN="python services/vision/train.py"

for name in ${@:-mimex r2p3}; do
  data=datasets/$name-prepared
  out=$RUN/$name
  $TRAIN --data-dir "$data" --check-data
  # Needs Hugging Face access for google/siglip2-base-patch16-224; SKIP_BASE=1 skips this comparison run.
  [ -n "${SKIP_BASE:-}" ] || $TRAIN --data-dir "$data" --stage head --output "$out/a-base-head" "${COMMON[@]}"
  $TRAIN --data-dir "$data" --stage head --model "$OFF_MODEL" --new-head --output "$out/b-off-head" "${COMMON[@]}"
  $TRAIN --data-dir "$data" --stage finetune --model "$out/b-off-head/final" --output "$out/c-off-finetune" "${COMMON[@]}"
  best=$(python - "$out" <<'EOF'
import json, sys
from pathlib import Path
runs = {p.parent.name: json.loads(p.read_text()) for p in sorted(Path(sys.argv[1]).glob("*/validation_results.json"))}
for run, m in runs.items():
  print(f"{run:16s} val top1={m['eval_accuracy']:.4f} top3={m['eval_top3_accuracy']:.4f}", file=sys.stderr)
print(max(runs, key=lambda r: runs[r]["eval_accuracy"]))
EOF
)
  echo "Selected by validation: $best" >&2
  $TRAIN --data-dir "$data" --model "$out/$best/final" --output "$out/test-$best" --evaluate-only --eval-split test --batch-size "${BATCH:-8}"
done
