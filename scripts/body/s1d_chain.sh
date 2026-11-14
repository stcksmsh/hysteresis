#!/bin/bash
# WO24 launcher: arms ii, iii, iii+D, seeds 4,5; exactly 6 threads, cores 6-11; resume-safe (rerun the same unit to continue).
cd /secondary/Programming/Github/Hysteresis/.claude/worktrees/body-m3f/scripts/body || exit 1
mkdir -p /secondary/hyst-data/body/s1d
exec taskset -c 6-11 /secondary/hyst-env/body/bin/python -u s1d_chain.py --epochs 1000 --seeds 4,5 --root /secondary/hyst-data/body/s1d >> /secondary/hyst-data/body/s1d/chain.log 2>&1
