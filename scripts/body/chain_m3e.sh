#!/bin/bash
# WO8: the whole M3e chain as one detached, capped unit (14 GB, 8 cores); waits for mains power before every step. Re-run to resume after an interruption.
D=/secondary/hyst-data/body/m3e
W=/secondary/Programming/Github/Hysteresis/.claude/worktrees/body-m3e/scripts/body
mkdir -p $D
systemd-run --user --unit=hyst-wo8-m3e-chain-$(date +%H%M) -p MemoryMax=14G -p MemorySwapMax=0 \
  -p StandardOutput=append:$D/chain.log -p StandardError=append:$D/chain.err --working-directory=$W \
  -E XLA_PYTHON_CLIENT_PREALLOCATE=false /secondary/hyst-env/body/bin/python -u chain_m3e.py
