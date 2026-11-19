#!/bin/bash
# WO16: re-simulate both seeds' held-out argmax rollouts with diagnostics (6 threads), then analyse. Run detached (systemd-run, MemoryMax=10G).
set -e
cd /secondary/Programming/Github/Hysteresis/.claude/worktrees/body-m3f/scripts/body
while [ "$(cat /sys/class/power_supply/ADP1/online)" != "1" ]; do sleep 30; done
export OMP_NUM_THREADS=6 XLA_FLAGS="--xla_cpu_multi_thread_eigen=true intra_op_parallelism_threads=6" JAX_PLATFORMS=cpu
OUT=/secondary/hyst-data/body/m3f/rerun3/diag
for s in 0 1; do
  taskset -c 0-5 /secondary/hyst-env/body/bin/python -u m3f_park_diag.py /secondary/hyst-data/body/m3f/rerun3/seed$s/try1 $OUT/seed$s > $OUT/sim_seed$s.log 2>&1
done
echo sim done > $OUT/sim_done.txt
