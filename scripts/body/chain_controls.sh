#!/bin/bash
# WO7: M3d controls as one detached, capped unit (14 GB, 8 threads). Waits for mains power, then runs m3d_controls.py (resume-safe), then the full unit tests.
# Re-run this script to resume after an interruption. Output: /secondary/hyst-data/body/m3d/controls/ (summary.json, log.txt, unittest.log, wall_peak.txt)
D=/secondary/hyst-data/body/m3d/controls
W=/secondary/Programming/Github/Hysteresis/.claude/worktrees/body-m3d/scripts/body
PY=/secondary/hyst-env/body/bin/python
mkdir -p $D
systemd-run --user --unit=hyst-wo7-m3d-controls-$(date +%H%M) -p MemoryMax=14G -p MemorySwapMax=0 \
  -p StandardOutput=append:$D/log.txt -p StandardError=append:$D/err.txt --working-directory=$W \
  -E XLA_PYTHON_CLIENT_PREALLOCATE=false -E OMP_NUM_THREADS=8 \
  bash -c "while [ \"\$(cat /sys/class/power_supply/ADP1/online)\" != 1 ]; do sleep 30; done; date +%s > $D/start.txt;
    taskset -c 0-7 $PY -u m3d_controls.py && taskset -c 0-7 $PY -m unittest -v test_m3d > $D/unittest.log 2>&1;
    date +%s > $D/end.txt; cat /sys/fs/cgroup/user.slice/user-\$(id -u).slice/user@\$(id -u).service/app.slice/\$(systemctl --user show -p ControlGroup --value | xargs basename)/memory.peak > $D/peak.txt 2>&1"
