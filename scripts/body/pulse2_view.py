"""WO51 viewing material (docs/PULSE2_RULES.md section 8; prepared, NOT served). Brain env.   pulse2_view.py
The 20 excerpts of the two pulse flash checks (pulse/flash/key.json, pulse/flash2/key.json: same songs, same starts), each shown with pulse v2
events and with librosa beats = 40 items, same rendering as before (beatv_clicks_visual.render). Pulse v2 flash peak brightness = 0.15 + 0.85 x
that event's confidence; librosa flashes at 1. Two questions per item. Ids Q00..Q39 in a seeded random order (51101).
-> pulse2/view/<id>.mp4, manifest.json, key.json"""
import json
import random
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import beatv_clicks_visual as V  # noqa: E402
import pulse2_run as PR  # noqa: E402
import pulse_run as R  # noqa: E402

B = R.B
OUT = B / "pulse2" / "view"
SEED = 51101
B_MIN = 0.15
QS = [dict(q="Is it the right speed?", labels=["right", "too fast", "too slow"]), dict(q="Is it steady?", labels=["yes", "switches"])]


def brightness(conf):
    return B_MIN + (1.0 - B_MIN) * np.clip(np.asarray(conf, float), 0.0, 1.0)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    wavs = {k: w for _, k, w in R.songs()}
    items = []
    for e in PR.view_excerpts():
        z = np.load(B / "pulse2/songs" / f"{e['song']}.npz")
        lib = R.load_beats(B / "beatv/librosa" / f"{e['song']}.json")
        items.append(dict(e, src="pulse2", ev=z["events"], bright=brightness(z["event_conf"])))
        items.append(dict(e, src="lib", ev=lib, bright=np.ones(len(lib))))
    random.Random(SEED).shuffle(items)
    import librosa
    import soundfile as sf
    clips, key, cache = [], {}, {}
    for i, it in enumerate(items):
        cid = f"Q{i:02d}"
        song, start = it["song"], it["start_s"]
        if song not in cache:
            w = OUT / f"_{song}.wav"
            y, _ = librosa.load(wavs[song], sr=V.SR, mono=True)
            sf.write(w, y[int(start * V.SR):int((start + V.LEN) * V.SR)], V.SR)
            cache[song] = w
        m = (it["ev"] >= start) & (it["ev"] < start + V.LEN)
        V.render(cache[song], it["ev"][m] - start, OUT / f"{cid}.mp4", bright=it["bright"][m])
        clips.append(dict(id=cid, kind="single", file=f"{cid}.mp4", question=QS[0]["q"], questions=QS, song=song, dataset=it["dataset"], excerpt_start_s=start))
        key[cid] = dict(song=song, dataset=it["dataset"], source=it["src"], check=it["check"], start_s=start, n_flashes=int(m.sum()),
                        brightness_median=float(np.median(it["bright"][m])) if m.any() else None, local_only=it["dataset"] == "motorica")
        print(cid, song, it["src"], int(m.sum()), "flashes", flush=True)
    for w in cache.values():
        w.unlink()
    (OUT / "manifest.json").write_text(json.dumps(dict(labels=QS[0]["labels"], clips=clips), indent=1))
    (OUT / "key.json").write_text(json.dumps(dict(seed=SEED, brightness=f"pulse2: {B_MIN} + {1 - B_MIN:.2f} x event confidence; lib: 1", items=key), indent=1))
    print("PULSE2 VIEW DONE", len(clips), flush=True)


if __name__ == "__main__":
    main()
