#!/bin/bash
# TS-vs-Python analyzer equivalence run. usage: run_equiv.sh OUT_DIR NAME=WAV [NAME=WAV ...]
# Run from the repo (or worktree) root with node_modules present. One input at a time, niced.
# Writes OUT/NAME.ts.json, OUT/NAME.py.json, OUT/report.tsv, OUT/times.tsv.
set -uo pipefail
PY=/secondary/hyst-env/analyze-py/bin/python
out=$1; shift
mkdir -p "$out"
: > "$out/report.tsv"; : > "$out/times.tsv"
rc=0
for spec in "$@"; do
  name=${spec%%=*}; wav=${spec#*=}
  s=$(date +%s.%N)
  nice -n 19 node_modules/.bin/tsx scripts/analyze.ts "$wav" "$out/$name.ts.json" > "$out/$name.ts.log" 2>&1
  m=$(date +%s.%N)
  PYTHONDONTWRITEBYTECODE=1 nice -n 19 $PY -I scripts/analyze.py "$wav" "$out/$name.py.json" > "$out/$name.py.log" 2>&1
  e=$(date +%s.%N)
  printf '%s\tts=%.1fs\tpy=%.1fs\n' "$name" "$(echo "$m - $s" | bc)" "$(echo "$e - $m" | bc)" >> "$out/times.tsv"
  $PY -I scripts/analyze/equiv/compare.py "$out/$name.ts.json" "$out/$name.py.json" "$name" >> "$out/report.tsv" || rc=1
  cmp -s "$out/$name.ts.json" "$out/$name.py.json" && echo "$name	BYTE-IDENTICAL" >> "$out/report.tsv"
done
exit $rc
