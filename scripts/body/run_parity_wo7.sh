#!/bin/bash
# WO7: one detached, capped unit (4 threads, 6 GB). Waits for mains (ADP1/online = 1), then runs the determinism tests and the parity run. Re-run to resume.
D=/secondary/hyst-data/body/parity
W=$(cd "$(dirname "$0")" && pwd)
mkdir -p $D
systemd-run --user --unit=hyst-wo7-parity-$(date +%H%M) -p MemoryMax=6G -p MemorySwapMax=0 -p CPUQuota=400% \
  -p StandardOutput=append:$D/run.log -p StandardError=append:$D/run.err --working-directory=$W \
  -E OMP_NUM_THREADS=4 -E XLA_FLAGS="--xla_cpu_multi_thread_eigen=true intra_op_parallelism_threads=4" \
  bash -c 'until [ "$(cat /sys/class/power_supply/ADP1/online)" = 1 ]; do sleep 20; done; echo "mains on $(date)";
  /secondary/hyst-env/body/bin/python -u -m unittest -v test_parity_wo7 > '$D'/unittest.log 2>&1; echo "tests exit $? $(date)";
  /secondary/hyst-env/body/bin/python -u parity_wo7.py '$D'; echo "parity exit $? $(date)"'
