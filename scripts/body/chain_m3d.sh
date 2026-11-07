#!/bin/bash
# Launch the whole M3d chain as one detached, memory-capped unit (waits for the running grid unit first). Re-run this to resume after an interruption.
D=/secondary/hyst-data/body/m3d
W=/secondary/Programming/Github/Hysteresis/.claude/worktrees/body-m3d/scripts/body
systemd-run --user --unit=hyst-wo5-m3d-chain-$(date +%H%M) -p MemoryMax=9G -p MemorySwapMax=0 \
  -p StandardOutput=append:$D/chain.log -p StandardError=append:$D/chain.err --working-directory=$W \
  /secondary/hyst-env/body/bin/python -u chain_m3d.py
