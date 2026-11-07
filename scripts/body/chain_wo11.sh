#!/bin/bash
# WO11: seed 2 (Trainer seed 1) of try 1 and A1-A3 as one detached, capped unit (14 GB, 8 cores). Re-run to resume.
D=/secondary/hyst-data/body/m3e/seed2
W=/secondary/Programming/Github/Hysteresis/.claude/worktrees/body-m3e/scripts/body
mkdir -p $D
systemd-run --user --unit=hyst-wo11-m3e-chain-$(date +%H%M) -p MemoryMax=14G -p MemorySwapMax=0 \
  -p StandardOutput=append:$D/chain.log -p StandardError=append:$D/chain.err --working-directory=$W \
  -E XLA_PYTHON_CLIENT_PREALLOCATE=false /secondary/hyst-env/body/bin/python -u chain_wo11.py
