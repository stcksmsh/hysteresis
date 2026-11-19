#!/bin/bash
# WO15B: render the clips as a detached, capped unit (14 GB). Re-run to resume (finished files are kept).
D=/secondary/hyst-data/body/m3f/rerun3/clips
W=/secondary/Programming/Github/Hysteresis/.claude/worktrees/body-m3f/scripts/body
mkdir -p $D
systemd-run --user --unit=hyst-wo15-clips-$(date +%H%M) -p MemoryMax=14G -p MemorySwapMax=0 \
  -p StandardOutput=append:$D/clips.log -p StandardError=append:$D/clips.err --working-directory=$W \
  -E PATH=/usr/local/bin:/usr/bin:/bin:/secondary/hyst-env/brain/bin /secondary/hyst-env/body/bin/python -u m3f_clips.py "$@"
