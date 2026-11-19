#!/bin/bash
# Work order 27: test of the round-400 clip path on the timed-round best.pkl (10 s of the 60-120 s window). Cores 12-17. The test video is deleted afterwards by hand.
cd "$(dirname "$0")" || exit 1
O=/secondary/hyst-data/body/s3/run_report/_test_clip
mkdir -p $O
while [ "$(cat /sys/class/power_supply/ADP1/online)" != 1 ]; do sleep 30; done
exec taskset -c 12-17 /secondary/hyst-env/body/bin/python -u s3_sidecar.py clip --best /secondary/hyst-data/body/s3/train_timed/best.pkl --out $O --seconds 10 --max-blocks 144 --name test10s > $O/clip.log 2>&1
