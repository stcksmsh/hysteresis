#!/bin/bash
# dialstudy_sheets.sh: per clip a 12-frame contact sheet (1 fps, 4x3) and a 3-frame strip (2, 6, 10 s) in $D/work/sheets; then two review images (8 strips each).
D=/secondary/hyst-data/body/dialstudy; C=$D/clips; S=$D/work/sheets; mkdir -p $S
for f in $C/*.mp4; do
  id=$(basename $f .mp4)
  ffmpeg -v error -y -i $f -vf "fps=1,scale=320:180,tile=4x3" -frames:v 1 $S/$id.sheet.png
  ffmpeg -v error -y -i $f -vf "select='eq(n,60)+eq(n,180)+eq(n,300)',scale=320:180,tile=3x1" -frames:v 1 -vsync 0 $S/$id.strip.png
done
ls $S/*.strip.png | head -8 | xargs -I{} echo -i {} | xargs ffmpeg -v error -y $(ls $S/*.strip.png | head -8 | sed 's/^/-i /' | tr '\n' ' ') -filter_complex "vstack=inputs=8" $S/review1.png
ffmpeg -v error -y $(ls $S/*.strip.png | tail -8 | sed 's/^/-i /' | tr '\n' ' ') -filter_complex "vstack=inputs=8" $S/review2.png
ls $S/*.strip.png | head -8 | xargs -n1 basename > $S/review1.txt; ls $S/*.strip.png | tail -8 | xargs -n1 basename > $S/review2.txt
