#!/usr/bin/env bash
# B7 (BRAIN_SPEC 7.2, 7.4): train (up to 8 epochs, early stopping patience 2, 24 h hard stop), then C1 to C5 on the best checkpoint.
# NOT STARTED until the overseer says go.
#
#   [BATCH=8] [GRAD_CKPT=1] bash scripts/brain/launch_b7.sh     (inside a memory-capped systemd-run scope)
#
# Re-running after an interruption resumes from last.pt. BATCH and GRAD_CKPT are the engineering knobs of the 4.7 memory ladder.
set -euo pipefail
cd "$(dirname "$0")"
PY=/secondary/hyst-env/brain/bin/python
C=/secondary/hyst-data/brain/corpus
B=/secondary/hyst-data/brain/b7
K=$B/ckpt
R=$B/results
BATCH=${BATCH:-8}
mkdir -p "$R" "$K"
M=(--manifest "$C/manifest.json" --stats "$C/feature_stats.npz")
V=(--val-artists "$PWD/val_artists.json")

echo "[1/3] training: batch $BATCH${GRAD_CKPT:+, gradient checkpointing}"
$PY -u train_b7.py "${M[@]}" "${V[@]}" --out "$K/phase" --batch "$BATCH" ${GRAD_CKPT:+--grad-checkpoint} | tee -a "$B/train.log"

echo "[2/3] checks C1 to C5 on the best checkpoint"
$PY -u check_b7.py --ckpt "$K/phase/best.pt" "${M[@]}" "${V[@]}" --out "$R" | tee -a "$B/check.log"

echo "[3/3] DEAM/MERP arousal r (reported only)"
$PY -u check_b7.py --ckpt "$K/phase/best.pt" "${M[@]}" "${V[@]}" --out "$R" --precheck-only --core2b /secondary/hyst-data/brain/b3/core2b_arousal.npz | tee -a "$B/check.log" || echo "pre-check failed (reported only)" >> "$B/check.log"
echo "finished"
