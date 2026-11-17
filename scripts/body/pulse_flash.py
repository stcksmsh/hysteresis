"""WO48 flash-check material (docs/PULSE_RULES.md section 7; prepared, not served). Brain env.   pulse_flash.py
Same 10 songs, same 30 s excerpts and same rendering as beatv/clicks_visual (beatv_clicks_visual.render: white disc at each event, 120 ms fade, music
without clicks): one item at the pulse events and one at librosa's beats per song = 20 items, ids Q00..Q19 in a seeded random order (seed 48101).
-> pulse/flash/<id>.mp4, manifest.json (two questions per item, for dialstudy_session.py), key.json (which item is which)."""
import json
import random
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import beatv_clicks_visual as V  # noqa: E402

B = Path("/secondary/hyst-data/body")
OUT = B / "pulse" / "flash"
SEED = 48101
QS = [dict(q="Is the flash on the beat?", labels=["yes", "partly", "no"]), dict(q="Is it the right speed?", labels=["right", "too fast", "too slow"])]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ex = json.loads((B / "beatv/clicks_visual/key.json").read_text())["songs"]
    items = []
    for s in ex:
        song = s["song"]
        pulse = np.array(json.loads((B / "pulse/songs" / f"{song}.json").read_text())["events"])
        lib = np.array(json.loads((B / "beatv/librosa" / f"{song}.json").read_text())["beats"])
        for src, ev in (("pulse", pulse), ("lib", lib)):
            items.append(dict(song=song, dataset=s["dataset"], start=s["start_s"], src=src, ev=ev))
    random.Random(SEED).shuffle(items)
    clips, key, cache = [], {}, {}
    for i, it in enumerate(items):
        cid = f"Q{i:02d}"
        song, start = it["song"], it["start"]
        if song not in cache:
            w = OUT / f"_{song}.wav"
            V.excerpt_wav(song, start, w)
            cache[song] = w
        b = it["ev"][(it["ev"] >= start) & (it["ev"] < start + V.LEN)] - start
        V.render(cache[song], b, OUT / f"{cid}.mp4")
        clips.append(dict(id=cid, kind="single", file=f"{cid}.mp4", question=QS[0]["q"], questions=QS, song=song, dataset=it["dataset"], excerpt_start_s=start))
        key[cid] = dict(song=song, dataset=it["dataset"], source=it["src"], start_s=start, n_flashes=int(len(b)),
                        local_only=it["dataset"] == "motorica")
        print(cid, song, it["src"], len(b), "flashes", flush=True)
    for w in cache.values():
        w.unlink()
    (OUT / "manifest.json").write_text(json.dumps(dict(labels=QS[0]["labels"], clips=clips), indent=1))
    (OUT / "key.json").write_text(json.dumps(dict(seed=SEED, items=key), indent=1))
    print("PULSE FLASH DONE", len(clips), flush=True)


if __name__ == "__main__":
    main()
