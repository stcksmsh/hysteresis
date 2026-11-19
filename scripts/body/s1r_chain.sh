#!/bin/bash
# WO22 Stage 1 rerun launcher: seeds 2,3, cores 6-11, resume-safe (rerun the same unit to continue).
cd /secondary/Programming/Github/Hysteresis/.claude/worktrees/body-m3f/scripts/body || exit 1
mkdir -p /secondary/hyst-data/body/s1r
exec taskset -c 6-11 /secondary/hyst-env/body/bin/python -u s1_chain.py --epochs 1000 --seeds 2,3 --root /secondary/hyst-data/body/s1r >> /secondary/hyst-data/body/s1r/chain.log 2>&1
