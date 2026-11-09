#!/bin/bash
# s0_v47_song.sh ID: WO19 Stage 0. The v47 one-arm (arm 0, hexagon Off) joint CSV of one held-out corpus song, headless, from its mp3. The steps of tracker-scratch/newsong/song.sh (steady tempo only):
#   ffmpeg -> stereo wav; analyze.py; dance_memory.py; Demucs htdemucs + htdemucs_6s (CPU); dance_stems.py; dance_structure.py; dance_notes.py; ensemble_preview --ring 6,0.8 --score; hyst score-csv --mode off --agent 0.
# Output: $O/<ID>/ (work files) and $O/<ID>-arm0.csv; per-stage seconds in $O/<ID>/timing.txt; the memory evidence's grid support in $O/<ID>/grid.txt (check it: a live-tempo song has a wrong grid).
# Resume-safe per stage (a finished output file is kept). Run with cores 6-11 and at most 6 threads. No Rust is built or changed.
set -eo pipefail
ID=$1
ROOT=$(cd "$(dirname "$(readlink -f "$0")")/../.." && pwd)
O=${S0_V47_OUT:-/secondary/hyst-data/body/s0/v47}
V=/secondary/hyst-env
TGT=/secondary/hyst-data/cargo-target-wo12/release
W=$O/$ID
mkdir -p "$W"
export UV_CACHE_DIR=$V/uv-cache TORCH_HOME=$V/torch-hub OMP_NUM_THREADS=6
T() { local n=$1; shift; local s=$(date +%s); "$@"; echo "$n $(( $(date +%s) - s ))" >> "$W/timing.txt"; }
cd "$ROOT"
wav=$W/$ID-stereo-analysis.wav
[ -f "$wav" ] || T ffmpeg ffmpeg -y -v error -i /secondary/hyst-data/brain/corpus/audio/$ID.mp3 -ar 44100 -ac 2 -c:a pcm_f32le "$wav"
[ -f "$W/$ID.m4a" ] || ffmpeg -y -v error -i "$wav" -c:a aac -b:a 256k "$W/$ID.m4a"
[ -f "$W/$ID.sidecar.json" ] || T analyze "$V/analyze-py/bin/python" -I scripts/analyze.py "$wav" "$W/$ID.sidecar.json" > "$W/analyze.log" 2>&1
[ -f "$W/$ID.memory.sidecar.json" ] || T memory python3 scripts/dance_memory.py "$wav" "$W/$ID.sidecar.json" "$W/$ID.memory.sidecar.json" "$W/$ID.memory.evidence.json" > "$W/memory.log" 2>&1
python3 -c "
import json,sys
e=json.load(open('$W/$ID.memory.evidence.json'))
print('grid', json.dumps({k:(round(v,3) if isinstance(v,float) else v) for k,v in e['gridFit'].items()}))
print('support', json.dumps({k:(round(v,3) if isinstance(v,float) else v) for k,v in e['measuredFluxGridSupport'].items()}))" > "$W/grid.txt"
S=$W/stems
for model in htdemucs htdemucs_6s; do
  [ -d "$S/$model/$ID-stereo-analysis" ] || T demucs-$model "$V/demucs/bin/python" -m demucs -n $model -d cpu --float32 --shifts 0 -o "$S" "$wav" > "$W/demucs-$model.log" 2>&1
done
[ -f "$W/$ID.stems.sidecar.json" ] || T stems python3 scripts/dance_stems.py "$W/$ID.memory.sidecar.json" "$S/htdemucs/$ID-stereo-analysis" "$W/$ID.stems.sidecar.json" "$W/$ID.stems.evidence.json" > "$W/stems.log" 2>&1
[ -f "$W/$ID.interpreted.sidecar.json" ] || T structure python3 scripts/dance_structure.py "$wav" "$W/$ID.stems.sidecar.json" "$W/$ID.interpreted.sidecar.json" "$W/$ID.structure.evidence.json" > "$W/structure.log" 2>&1
[ -f "$W/$ID.notes.sidecar.json" ] || T notes python3 scripts/dance_notes.py "$W/$ID.interpreted.sidecar.json" "$S/htdemucs_6s/$ID-stereo-analysis" "$W/$ID.notes.sidecar.json" > "$W/notes.log" 2>&1
[ -f "$W/$ID.score.json" ] || T export "$TGT/examples/ensemble_preview" "$W/$ID.html" "$ID.m4a" "$W/$ID.notes.sidecar.json" --ring 6,0.8 --score "$W/$ID.score.json" > "$W/export.log" 2>&1
T csv "$TGT/hyst" score-csv "$W/$ID.score.json" "$O/$ID-arm0.csv" --hz 50 --mode off --agent 0 > "$W/csv.log" 2>&1
echo "$ID done"
rm -rf "$S" "$W/$ID-stereo-analysis.wav" 2>/dev/null || true
