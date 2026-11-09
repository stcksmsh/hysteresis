#!/bin/bash
# WO26A data chain (detached unit, 6 threads, cores 6-11): slow-stream raw L4 blocks -> PCA fit -> slow lanes -> tempo and RMS. Resume-safe; mains power only (polls ADP1).
cd /secondary/Programming/Github/Hysteresis/.claude/worktrees/body-k5video/scripts/body || exit 1
PY=/secondary/hyst-env/brain/bin/python
wait_mains() { while [ "$(cat /sys/class/power_supply/ADP1/online)" != "1" ]; do echo "waiting for mains $(date +%T)"; sleep 30; done; }
wait_mains
taskset -c 6-11 $PY -u s3_slow.py raw --threads 6 || exit 1
taskset -c 6-11 $PY -u s3_slow.py fit || exit 1
taskset -c 6-11 $PY -u s3_slow.py build || exit 1
wait_mains
taskset -c 6-11 $PY -u s3_tempo_rms.py --workers 6 || exit 1
echo CHAIN_DONE
