"""WO41 Kosta's label clips (BRAIN_SPEC 7.68.6/7.68.11): 39 test+validation FineDance song groups, one seeded sequence per group, three seeded 15 s passages each,
a still frame + audio (h264 + aac), one manifest for dialstudy_session.py (label set calm / sad / tense / energetic / light). Brain env, ffmpeg.

    t1b_labelclips.py [OUTDIR]       default /secondary/hyst-data/body/t1b/labels (resumable: an existing clip is kept)
Passage starts: the span [10 s, duration - 15 s] is cut in three equal parts, one seeded start per part (no overlap). Seed 36401. passages.json (not in the manifest) keeps group, sequence, start, split.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

T0 = Path("/secondary/hyst-data/body/t0")
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/secondary/hyst-data/body/t1b/labels")
WAVS = "/secondary/hyst-data/datasets/finedance/data/finedance/music_wav/{}.wav"
LABELS = ["calm", "sad", "tense", "energetic", "light"]
SEED, LEN = 36401, 15.0


def main():
    rng = np.random.default_rng(SEED)
    groups = [g for g in json.loads((T0 / "split.json").read_text())["groups"] if "finedance" in g["dataset"] and g["split"] in ("test", "validation")]
    (OUT / "clips").mkdir(parents=True, exist_ok=True)
    still = OUT / "still.png"
    if not still.exists():
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x202428:s=640x360", "-frames:v", "1", str(still)], check=True)
    clips, meta = [], []
    for g in sorted(groups, key=lambda g: g["group"]):
        seq = g["members"][rng.integers(len(g["members"]))]
        wav = WAVS.format(seq.split("_")[1])
        dur = sf.info(wav).duration
        span = (dur - LEN) - 10.0
        starts = [10.0 + span * (i + rng.random()) / 3 for i in range(3)] if span > 0 else [max(0.0, dur - LEN)] * 3
        for i, st in enumerate(starts):
            cid = f"{g['group']}_p{i}"
            f = OUT / "clips" / f"{cid}.mp4"
            if not f.exists():
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "5", "-i", str(still), "-ss", f"{st:.3f}", "-t", str(LEN), "-i", wav,
                                "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-shortest", str(f) + ".part.mp4"], check=True)
                Path(str(f) + ".part.mp4").replace(f)
            clips.append(dict(id=cid, file=f"clips/{cid}.mp4", song=g["group"], excerpt_start_s=round(st, 3)))
            meta.append(dict(id=cid, group=g["group"], seq=seq, start_s=round(st, 3), split=g["split"]))
    (OUT / "manifest.json").write_text(json.dumps(dict(labels=LABELS, clips=clips), indent=1))
    (OUT / "passages.json").write_text(json.dumps(meta, indent=1))
    print(len(groups), "groups", len(clips), "clips")


main()
