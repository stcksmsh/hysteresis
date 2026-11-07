#!/bin/bash
# usage: h3_try.sh TAG [extra toy_h3 args]; designs A B C one after another (4 threads; one run peaks near 2.4 GB, the unit cap is 5 GB). Logs in /secondary/hyst-data/brain/h3/
tag=$1; shift
cd "$(dirname "$0")"
mkdir -p /secondary/hyst-data/brain/h3
for d in A B C; do
  /secondary/hyst-env/brain/bin/python -u toy_h3.py --design $d --threads 4 "$@" > /secondary/hyst-data/brain/h3/${tag}_$d.log 2>&1
done
exit 0
