#!/bin/bash
# t1b_t2_run.sh IDX   full T2 for E1 seed IDX (1..3) on its 4 cores: gen, swap, real, measures, diversity (controls are shared: run `t1b_t2b.py ctrl` once first)
set -e
i=$1; seed=$((41100 + i)); a=$((2 + 4 * i)); b=$((a + 3))
ROOT=$(cd "$(dirname "$0")/../.." && pwd); cd $ROOT
export T1B_POST=2; P=/secondary/hyst-env/brain/bin/python; L=/secondary/hyst-data/body/t1b/logs/t2_seed$seed.log
for step in "t1b_t2.py gen $seed" "t1b_t2.py swap $seed" "t1b_t2b.py real $seed 3" "t1b_t2b.py measures $seed" "t1b_t2d.py diversity $seed"; do
  echo "== $step" >> $L; taskset -c $a-$b $P -u scripts/body/$step >> $L 2>&1
done
echo T2DONE >> $L
