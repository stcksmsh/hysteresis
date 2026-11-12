#!/bin/bash
# motornet_render.sh [ID ...]   WO29A: render the gated clips of work/ to clips/ with round 1's recorder path (dialstudy_render.sh, same camera and framing).
D=/secondary/hyst-data/body/motornet_toy
mkdir -p $D/work $D/clips
[ -f $D/work/silence12.m4a ] || cp /secondary/hyst-data/body/dialstudy/work/silence12.m4a $D/work/silence12.m4a
export DIAL_W=$D/work DIAL_C=$D/clips
exec "$(cd "$(dirname "$0")" && pwd)/dialstudy_render.sh" "$@"
