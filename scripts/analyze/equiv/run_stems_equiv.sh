#!/bin/bash
# --stems equivalence on one song with identical stem WAVs.
# usage: run_stems_equiv.sh OUT_DIR WAV STEM_SRC   (run from the repo root, node_modules present)
set -uo pipefail
PY=/secondary/hyst-env/analyze-py/bin/python
out=$1; wav=$2; export STEM_SRC=$3
here=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$out/shim"; ln -sf "$here/fake_demucs.sh" "$out/shim/python3"
s=$(date +%s.%N)
PATH="$out/shim:$PATH" nice -n 19 node_modules/.bin/tsx scripts/analyze.ts "$wav" "$out/stems.ts.json" --stems > "$out/stems.ts.log" 2>&1
m=$(date +%s.%N)
HYST_DEMUCS_PYTHON="$here/fake_demucs.sh" nice -n 19 $PY -I scripts/analyze.py "$wav" "$out/stems.py.json" --stems > "$out/stems.py.log" 2>&1
e=$(date +%s.%N)
printf 'stems\tts=%.1fs\tpy=%.1fs\n' "$(echo "$m - $s" | bc)" "$(echo "$e - $m" | bc)" > "$out/times.tsv"
$PY -I "$here/compare.py" "$out/stems.ts.json" "$out/stems.py.json" stems | tee "$out/report.tsv"
