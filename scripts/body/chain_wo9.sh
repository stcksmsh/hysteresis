#!/bin/bash
# WO9: Part 1 + Part 2 as one detached, capped unit (14 GB, 8 cores); waits for mains power before each step. Re-run to resume.
D=/secondary/hyst-data/body/m3e
W=/secondary/Programming/Github/Hysteresis/.claude/worktrees/body-m3e/scripts/body
mkdir -p $D/ablations
systemd-run --user --unit=hyst-wo9-m3e-chain-$(date +%H%M) -p MemoryMax=14G -p MemorySwapMax=0 \
  -p StandardOutput=append:$D/ablations/chain.log -p StandardError=append:$D/ablations/chain.err --working-directory=$W \
  -E XLA_PYTHON_CLIENT_PREALLOCATE=false /secondary/hyst-env/body/bin/python -u chain_wo9.py
