#!/bin/bash
# WO21: base diag rollout of 24 held-out songs, then the three single-bound relaxations on the first 3 of them. 3 threads on cores 12-14.
cd "$(dirname "$(readlink -f "$0")")"
PY=/secondary/hyst-env/body/bin/python
O=/secondary/hyst-data/body/s0/ceiling
S3=$($PY - <<'EOF' 2>/dev/null
import json
ids = json.load(open("/secondary/hyst-data/body/k5/splits.json"))["check"]["ids"]
print(",".join(ids[::max(1, len(ids) // 24)][:3]))
EOF
)
taskset -c 12-14 $PY -u s0_ceiling.py roll --variant base --n 24 --out $O
for v in amp c freq; do taskset -c 12-14 $PY -u s0_ceiling.py roll --variant $v --songs "$S3" --out $O; done
echo all-done
