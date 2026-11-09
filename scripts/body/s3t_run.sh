#!/bin/bash
# WO26B Stage 3 run (overseer's launch, with the user's go): the full pass, 977 rounds, validations every 200 rounds and at the end, best.pkl, early stop, compute box 30 h, resumable
# (rerun the same unit to continue). Exactly 6 threads, cores 6-11. Mains wait as built. Launch detached and memory-capped:
#   systemd-run --user --unit=hyst-wo26b-run-<fresh> -p MemoryMax=14G -p MemorySwapMax=0 --working-directory=<this dir> <this script>
cd /secondary/Programming/Github/Hysteresis/.claude/worktrees/body-m3f/scripts/body || exit 1
mkdir -p /secondary/hyst-data/body/s3/run
echo "threads: 6, taskset -c 6-11" >> /secondary/hyst-data/body/s3/run/train.log
exec taskset -c 6-11 /secondary/hyst-env/body/bin/python -u s3_train.py --out /secondary/hyst-data/body/s3/run >> /secondary/hyst-data/body/s3/run/train.log 2>&1
