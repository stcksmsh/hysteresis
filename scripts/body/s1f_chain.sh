#!/bin/bash
# WO25 launcher: arms iii+D, iii+Df, seeds 6,7; exactly 6 threads, cores 6-11; resume-safe (rerun the same unit to continue).
cd /secondary/Programming/Github/Hysteresis/.claude/worktrees/body-m3f/scripts/body || exit 1
mkdir -p /secondary/hyst-data/body/s1f
exec taskset -c 6-11 /secondary/hyst-env/body/bin/python -u s1f_chain.py --epochs 1000 --seeds 6,7 --root /secondary/hyst-data/body/s1f >> /secondary/hyst-data/body/s1f/chain.log 2>&1
