#!/bin/bash
# K5-pass2 check and videos after training (WO18). Waits until the training run has finished (progress.json "done" set and unit hyst-wo14-a2 not active), then:
# check -> songs -> summary (k5p2_eval.py, 6 threads) -> k5p2_render.sh. Resume-safe: run the same command again after a stop. Launch detached with a cap (see k5p2_chain_launch note in the night log):
#   systemd-run --user --unit=hyst-wo18-NAME -p MemoryMax=14G -p MemorySwapMax=0 -p WorkingDirectory=<this dir> /abs/path/k5p2_chain.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
RUN=/secondary/hyst-data/body/k5p2/run; OUT=/secondary/hyst-data/body/k5p2/check
PY=/secondary/hyst-env/body/bin/python
mkdir -p "$OUT"
while ! python3 -I -c "import json,sys; sys.exit(0 if json.load(open('$RUN/progress.json')).get('done') else 1)" || systemctl --user is-active --quiet hyst-wo14-a2; do sleep 60; done
echo "training finished: $(python3 -I -c "import json; d=json.load(open('$RUN/progress.json')); print(d['done'], 'round', d['round'], 'best', max(v['ext_a'] for v in d['val']))")"
export OMP_NUM_THREADS=6
cd "$HERE"
for step in check songs summary; do
  /usr/bin/taskset -c 6-11 $PY -u k5p2_eval.py $step --policy "$RUN/best.pkl" --out "$OUT" || { echo "$step failed"; exit 1; }
done
"$HERE/k5p2_render.sh"
echo "chain done"
