#!/bin/bash
# WO13B: detached, capped unit (14 GB, 8 cores). Usage: chain_wo13.sh grid | chain_wo13.sh main JERK SWITCH. Re-run to resume.
D=/secondary/hyst-data/body/m3f
W=/secondary/Programming/Github/Hysteresis/.claude/worktrees/body-m3f/scripts/body
mkdir -p $D/grid $D/abl
systemd-run --user --unit=hyst-wo13-m3f-$1-$(date +%H%M) -p MemoryMax=14G -p MemorySwapMax=0 \
  -p StandardOutput=append:$D/chain_$1.log -p StandardError=append:$D/chain_$1.err --working-directory=$W \
  -E XLA_PYTHON_CLIENT_PREALLOCATE=false /secondary/hyst-env/body/bin/python -u chain_wo13.py "$@"
