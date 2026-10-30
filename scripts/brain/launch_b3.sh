#!/usr/bin/env bash
# B3 launch (BRAIN_SPEC, "Go for B3 training"): prep, main training with grid phase, checks on its final checkpoint, then the
# no-phase ablation inside what is left of the 3 x 10 h training cap, then the ablation comparison.
#
#   [LIST=/secondary/hyst-data/brain/corpus/final_corpus.csv] [HASHES=extra_sha256sum_file] [EPOCHS=8] bash scripts/brain/launch_b3.sh
#
# Re-running after an interruption resumes: prep skips finished grids, train.py resumes from last.pt (the cap counts training wall time
# across resumes; held-out evaluation is not counted). The list's own sha256 column (audio) is the committed hash list.
set -euo pipefail
cd "$(dirname "$0")"
PY=/secondary/hyst-env/brain/bin/python
C=/secondary/hyst-data/brain/corpus
B=/secondary/hyst-data/brain/b3
R=$B/results
K=$B/ckpt
LIST=${LIST:-$C/final_corpus.csv}
EPOCHS=${EPOCHS:-8}
CAP_H=30
mkdir -p "$R" "$K"
M=(--manifest "$C/manifest.json" --stats "$C/feature_stats.npz")

echo "[1/5] prep: verify hashes and statistics, add offline-grid beats, write manifest"
$PY prep_corpus.py corpus "$LIST" ${HASHES:+--hashes "$HASHES"} --out "$C"

echo "[2/5] main model, with grid phase: $EPOCHS epochs or the cap"
$PY train.py "${M[@]}" --out "$K/phase" --epochs "$EPOCHS" --batch 8 --cap-hours "$CAP_H" | tee -a "$B/train_phase.log"

echo "[3/5] checks on the final checkpoint"
$PY check_b3.py --ckpt "$K/phase/last.pt" "${M[@]}" --out "$R" | tee -a "$B/check.log"
$PY check_b3.py --ckpt "$K/phase/last.pt" "${M[@]}" --out "$R" --precheck-only | tee -a "$B/check.log" || echo "pre-check failed (reported only)" >> "$B/check.log"

echo "[4/5] no-phase ablation, inside the cap"
LEFT=$($PY - "$K/phase/last.pt" "$CAP_H" <<'PYEOF'
import sys, torch
m = torch.load(sys.argv[1], weights_only=False)["meta"]
print(max(0.0, float(sys.argv[2]) - m["wall_s"] / 3600))
PYEOF
)
if awk "BEGIN{exit !($LEFT >= 1.0)}"; then
  $PY train.py "${M[@]}" --out "$K/nophase" --epochs "$EPOCHS" --batch 8 --cap-hours "$LEFT" --no-phase | tee -a "$B/train_nophase.log"
  DONE=$($PY - "$K/nophase/last.pt" "$EPOCHS" <<'PYEOF'
import sys, torch
m = torch.load(sys.argv[1], weights_only=False)["meta"]
print("yes" if m["epoch"] == int(sys.argv[2]) and not m["stopped_by_cap"] else "no")
PYEOF
)
else
  DONE=no
fi

echo "[5/5] ablation comparison"
if [ "$DONE" = yes ]; then
  $PY check_b3.py --ckpt "$K/phase/last.pt" --ckpt-nophase "$K/nophase/last.pt" "${M[@]}" --out "$R" --ablation-only
else
  echo "no-phase ablation not run: it did not finish $EPOCHS epochs inside the cap (${LEFT} h left after the main run)" | tee "$R/ablation_not_run.txt"
fi
echo "finished"
