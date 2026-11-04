#!/bin/bash
# usage: h2_try.sh TRY MODE [extra toy_h2 args]; runs designs A B C in parallel (2 threads each); logs in /secondary/hyst-data/brain/h2/
try=$1; mode=$2; shift 2
cd "$(dirname "$0")"
mkdir -p /secondary/hyst-data/brain/h2
for d in A B C; do
  /secondary/hyst-env/brain/bin/python -u toy_h2.py $mode --design $d "$@" > /secondary/hyst-data/brain/h2/${try}_${mode}_$d.log 2>&1 &
done
wait
