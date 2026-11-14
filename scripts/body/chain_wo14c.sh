#!/bin/bash
# WO14C: detached, capped unit (14 GB, 8 cores). Re-run to resume.
D=/secondary/hyst-data/body/m3f/rerun2
W=/secondary/Programming/Github/Hysteresis/.claude/worktrees/body-m3f/scripts/body
mkdir -p $D
systemd-run --user --unit=hyst-wo14c-m3f-rerun2-$(date +%H%M) -p MemoryMax=14G -p MemorySwapMax=0 \
  -p StandardOutput=append:$D/chain.log -p StandardError=append:$D/chain.err --working-directory=$W \
  -E XLA_PYTHON_CLIENT_PREALLOCATE=false /secondary/hyst-env/body/bin/python -u chain_wo14c.py
