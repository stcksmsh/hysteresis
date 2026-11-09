#!/bin/bash
# WO26A reference run of s3_eval.py on pass2 best.pkl (cores 6-11, mains only). Waits for the data chain unit (needs tempo_rms.json), then runs the tests and the evaluation.
cd /secondary/Programming/Github/Hysteresis/.claude/worktrees/body-k5video/scripts/body || exit 1
while systemctl --user is-active --quiet ${DATA_UNIT:-hyst-wo26a-data1}; do sleep 60; done
[ -f /secondary/hyst-data/body/s3/tempo_rms.json ] || { echo "no tempo_rms.json: data chain failed"; exit 1; }
while [ "$(cat /sys/class/power_supply/ADP1/online)" != "1" ]; do echo "waiting for mains $(date +%T)"; sleep 30; done
PY=/secondary/hyst-env/brain/bin/python
taskset -c 6-11 $PY -m unittest test_s3_data 2>&1 | tail -15
taskset -c 6-11 $PY -u s3_eval.py --policy /secondary/hyst-data/body/k5p2/run/best.pkl --out /secondary/hyst-data/body/s3/eval_pass2 \
  --rollouts /secondary/hyst-data/body/s0/pass2 --check-dir /secondary/hyst-data/body/k5p2/check || exit 1
echo EVAL_DONE
