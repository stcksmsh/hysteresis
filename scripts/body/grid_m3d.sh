#!/bin/bash
# M3d lambda grid on the tune episodes: one detached, memory-capped unit, the three cells one after another on 8 cores
# (three parallel cells at 3 GB each were OOM-killed in the first backward pass; the peak is above 3 GB).
D=/secondary/hyst-data/body/m3d
W=/secondary/Programming/Github/Hysteresis/.claude/worktrees/body-m3d/scripts/body
systemd-run --user --unit=hyst-wo5-m3d-grid -p MemoryMax=9G -p MemorySwapMax=0 \
  -p StandardOutput=file:$D/grid.log -p StandardError=file:$D/grid.err --working-directory=$W \
  bash -c 'for L in 0.03 0.3 3; do taskset -c 0-7 env OMP_NUM_THREADS=8 /secondary/hyst-env/body/bin/python -u run_m3d.py --out '$D'/grid_$L --lam $L --epochs 12 --eval tune; done'
