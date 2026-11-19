#!/bin/bash
# WO17: detached, capped unit (14 GB, 8 cores). Re-run to resume.
D=/secondary/hyst-data/body/m3f/rerun4
W=/secondary/Programming/Github/Hysteresis/.claude/worktrees/body-m3f/scripts/body
mkdir -p $D
systemd-run --user --unit=hyst-wo17-rerun4-$(date +%H%M) -p MemoryMax=14G -p MemorySwapMax=0 \
  -p StandardOutput=append:$D/chain.log -p StandardError=append:$D/chain.err --working-directory=$W \
  -E XLA_PYTHON_CLIENT_PREALLOCATE=false /secondary/hyst-env/body/bin/python -u chain_wo17.py
