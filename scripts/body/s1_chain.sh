#!/bin/bash
# Stage 1 chain launcher: cores 6-11, resume-safe (rerun the same unit to continue).
cd /secondary/Programming/Github/Hysteresis/.claude/worktrees/body-m3f/scripts/body || exit 1
exec taskset -c 6-11 /secondary/hyst-env/body/bin/python -u s1_chain.py --epochs 1000 --root /secondary/hyst-data/body/s1 >> /secondary/hyst-data/body/s1/chain.log 2>&1
