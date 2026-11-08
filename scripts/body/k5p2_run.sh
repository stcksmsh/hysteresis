#!/bin/bash
# K5-pass2 run (WO14B). Detached, memory-capped, 6 threads. The same command resumes (ckpt.pkl in OUT).
#   scripts/body/k5p2_run.sh UNIT_SUFFIX [extra k5p2_train.py args]
# Pause: systemctl --user freeze hyst-wo14-SUFFIX    thaw: systemctl --user thaw hyst-wo14-SUFFIX
# Stop (finishes the round, checkpoints, exit 0): systemctl --user stop hyst-wo14-SUFFIX
set -e
SUF=$1; shift
OUT=/secondary/hyst-data/body/k5p2/run
mkdir -p "$OUT"
cd "$(dirname "$(readlink -f "$0")")"
systemd-run --user --unit=hyst-wo14-"$SUF" -p MemoryMax=10G -p MemorySwapMax=0 -p TimeoutStopSec=300 -p WorkingDirectory="$(pwd)" \
  -p StandardOutput=append:"$OUT"/train.log -p StandardError=append:"$OUT"/train.log \
  -E OMP_NUM_THREADS=6 -E XLA_FLAGS=--xla_cpu_multi_thread_eigen=true \
  /usr/bin/taskset -c 6-11 /secondary/hyst-env/body/bin/python -u k5p2_train.py --out "$OUT" "$@"
