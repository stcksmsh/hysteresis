#!/bin/bash
# WO26B timed round (overseer's word only): 2 real rounds (round 0 compiles) + the per-round D estimate + ONE validation; never the Stage 3 run.
# Exactly 6 threads, cores 6-11, mains only (the trainer waits for mains). Launch detached and memory-capped:
#   systemd-run --user --unit=hyst-wo26b-timed-<fresh> -p MemoryMax=14G -p MemorySwapMax=0 --working-directory=<this dir> <this script>
cd /secondary/Programming/Github/Hysteresis/.claude/worktrees/body-m3f/scripts/body || exit 1
mkdir -p /secondary/hyst-data/body/s3/train_timed
echo "threads: 6, taskset -c 6-11" >> /secondary/hyst-data/body/s3/train_timed/train.log
exec taskset -c 6-11 /secondary/hyst-env/body/bin/python -u s3_train.py --out /secondary/hyst-data/body/s3/train_timed --timed >> /secondary/hyst-data/body/s3/train_timed/train.log 2>&1
