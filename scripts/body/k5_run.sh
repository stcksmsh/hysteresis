#!/bin/bash
# K5 run control (WO10). One detached, capped service; pause / continue / stop / start again, no loss. See K5_RUN.md.
#   k5_run.sh start      start, or start again from the last checkpoint (idempotent: nothing happens if the unit already runs)
#   k5_run.sh pause      systemctl --user freeze  (instant, memory kept, paused time is not compute)
#   k5_run.sh continue   systemctl --user thaw
#   k5_run.sh stop       systemctl --user stop    (finishes the round in progress, ~60 s, writes the checkpoint, exits 0)
#   k5_run.sh status
# Environment: K5_OUT (default /secondary/hyst-data/body/k5/run1), K5_UNIT (default hyst-wo10-k5run), K5_ARGS (extra k5_train.py arguments, tests only).
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${K5_OUT:-/secondary/hyst-data/body/k5/run1}
UNIT=${K5_UNIT:-hyst-wo10-k5run}
case "$1" in
  start)
    mkdir -p "$OUT"
    systemd-run --user --unit="$UNIT" -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=600% -p TimeoutStopSec=180 --working-directory="$HERE" \
      -E OMP_NUM_THREADS=6 -E PYTHONHASHSEED=0 -E PYTHONPATH="$HERE" \
      bash -c "exec /secondary/hyst-env/body/bin/python -u k5_train.py --out '$OUT' $K5_ARGS >> '$OUT/run.log' 2>&1" ;;
  check)    # only the K5 check on best.pkl (unit hyst-wo10-k5check, 14 GB), resume-safe: finished policies and finished rollout batches are reused
    systemd-run --user --unit="${K5_CHECK_UNIT:-hyst-wo10-k5check}" -p MemoryMax=14G -p MemorySwapMax=0 -p CPUQuota=600% -p TimeoutStopSec=180 --working-directory="$HERE" \
      -E OMP_NUM_THREADS=6 -E PYTHONHASHSEED=0 -E PYTHONPATH="$HERE" \
      bash -c "exec /secondary/hyst-env/body/bin/python -u k5_eval.py --policy '$OUT/best.pkl' --out '$OUT/eval' >> '$OUT/check.log' 2>&1" ;;
  pause)    systemctl --user freeze "$UNIT" ;;
  continue) systemctl --user thaw "$UNIT" ;;
  stop)     systemctl --user stop "$UNIT" ;;
  status)   systemctl --user show "$UNIT" -p ActiveState -p SubState -p FreezerState; tail -n 3 "$OUT/run.log"; cat "$OUT/progress.json" 2>/dev/null | head -c 400; echo ;;
  *) echo "usage: $0 start|pause|continue|stop|status"; exit 2 ;;
esac
