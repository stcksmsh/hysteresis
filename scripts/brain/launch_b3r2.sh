#!/usr/bin/env bash
# B3 round 2 (BRAIN_SPEC 4.7): train (up to 12 epochs, early stopping, 20 h hard stop), checks on the best checkpoint, pre-check.
#
#   [BATCH=8] [GRAD_CKPT=1] bash scripts/brain/launch_b3r2.sh     (inside a memory-capped systemd-run scope)
#
# Re-running after an interruption resumes from last.pt. BATCH and GRAD_CKPT are the engineering knobs of the 4.7 memory ladder.
set -euo pipefail
cd "$(dirname "$0")"
PY=/secondary/hyst-env/brain/bin/python
C=/secondary/hyst-data/brain/corpus
B=/secondary/hyst-data/brain/b3r2
K=$B/ckpt
R=$B/results
BATCH=${BATCH:-8}
mkdir -p "$R" "$K"
M=(--manifest "$C/manifest.json" --stats "$C/feature_stats.npz")
V=(--val-artists "$PWD/val_artists.json")

echo "[1/3] training: batch $BATCH${GRAD_CKPT:+, gradient checkpointing}"
$PY -u train.py "${M[@]}" "${V[@]}" --out "$K/phase" --batch "$BATCH" ${GRAD_CKPT:+--grad-checkpoint} | tee -a "$B/train.log"

echo "[2/3] checks on the best checkpoint"
$PY -u check_b3.py --ckpt "$K/phase/best.pt" "${M[@]}" "${V[@]}" --out "$R" | tee -a "$B/check.log"

echo "[3/3] pre-check (reported only)"
$PY -u check_b3.py --ckpt "$K/phase/best.pt" "${M[@]}" --out "$R" --precheck-only --core2b /secondary/hyst-data/brain/b3/core2b_arousal.npz | tee -a "$B/check.log" || echo "pre-check failed (reported only)" >> "$B/check.log"
echo "finished"
