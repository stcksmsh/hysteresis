"""Second pulse flash check material (docs/PULSE_FLASH2_RULES.md). Brain env.   pulse_flash2.py
-> pulse/flash2/<id>.mp4, manifest.json, key.json, selection.json. Reuses pulse_run helpers and beatv_clicks_visual rendering."""
import json
import math
import random
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import beatv_clicks_visual as V  # noqa: E402
import pulse_flash as F1  # noqa: E402
import pulse_run as R  # noqa: E402

B = R.B
OUT = B / "pulse" / "flash2"
FAILS = ["aioz_8JQ0zHmZBIg_05_0_1950", "aioz_SZhU9XTCUiM_13_0_1950"]
DS_ORDER = ["finedance", "aioz", "phantom", "motorica"]


def load(key):
    j = json.loads((B / "pulse/songs" / f"{key}.json").read_text())
    z = np.load(B / "pulse/songs" / f"{key}.npz")
    lib = R.load_beats(B / "beatv/librosa" / f"{key}.json")
    return j, np.array(j["events"]), lib, z["rms"]


def pick_start(key, avoid=None):
    j, ev, lib, rms = load(key)
    whole = j["whole"]["level_vs_lib"]
    med = float(np.median(rms))
    best = None
    for s in range(10, int(j["duration_s"] - 40) + 1):
        lo, hi = float(s), s + 30.0
        if avoid is not None and abs(s - avoid) < 30:
            continue
        if float(np.median(rms[int(lo * 100):int(hi * 100)])) < med:
            continue
        p, l = R.series_stats(ev, lo, hi), R.series_stats(lib, lo, hi)
        if p["n"] < 8 or l["n"] < 8:
            continue
        r = p["tempo_bpm"] / l["tempo_bpm"]
        lv = R.level(r)[0]
        k = (lv != whole["nearest"], abs(math.log(r / whole["ratio"])), s)
        if best is None or k < best[0]:
            best = (k, dict(start=float(s), ratio=float(r), level=lv, level_kept=lv == whole["nearest"], whole_ratio=whole["ratio"], whole_level=whole["nearest"]))
    if best is None:
        raise RuntimeError(f"no excerpt for {key}")
    return best[1]


def choose():
    first = {v["song"]: v["start_s"] for v in json.loads((B / "pulse/flash/key.json").read_text())["items"].values()}
    rng = random.Random(49301)
    wavs = {kk: w for ds, kk, w in R.songs()}
    pools = {}
    for p in sorted((B / "pulse/songs").glob("*.json")):
        j = json.loads(p.read_text())
        k = j["key"]
        lev = j["whole"]["level_vs_lib"]["nearest"]
        if k in first or j["duration_s"] < 50 or lev not in ("2/3", "3/2") or not (B / "beatv/librosa" / f"{k}.json").exists():
            continue
        if k not in wavs or not Path(wavs[k]).exists():
            continue
        pools.setdefault((lev, j["dataset"]), []).append(k)
    songs = []
    for lev in ("2/3", "3/2"):
        for ds in DS_ORDER:
            pool = sorted(pools[(lev, ds)])
            rng.shuffle(pool)
            songs.append(dict(song=pool[0], dataset=ds, role=f"new {lev}", pool=len(pool)))
    for k in FAILS:
        songs.append(dict(song=k, dataset="aioz", role="failure", avoid=first[k]))
    return songs


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    wavs = {kk: w for ds, kk, w in R.songs()}
    sel = choose()
    for s in sel:
        s.update(pick_start(s["song"], s.get("avoid")))
        print(s, flush=True)
    (OUT / "selection.json").write_text(json.dumps(sel, indent=1))
    items = []
    for s in sel:
        _, ev, lib, _ = load(s["song"])
        for src, e in (("pulse", ev), ("lib", lib)):
            items.append(dict(s, src=src, ev=e))
    random.Random(49302).shuffle(items)
    import librosa
    import soundfile as sf
    clips, key, cache = [], {}, {}
    for i, it in enumerate(items):
        cid = f"Q{i:02d}"
        song, start = it["song"], it["start"]
        if song not in cache:
            w = OUT / f"_{song}.wav"
            y, _ = librosa.load(wavs[song], sr=V.SR, mono=True)
            sf.write(w, y[int(start * V.SR):int((start + V.LEN) * V.SR)], V.SR)
            cache[song] = w
        b = it["ev"][(it["ev"] >= start) & (it["ev"] < start + V.LEN)] - start
        V.render(cache[song], b, OUT / f"{cid}.mp4")
        clips.append(dict(id=cid, kind="single", file=f"{cid}.mp4", question=F1.QS[0]["q"], questions=F1.QS, song=song, dataset=it["dataset"], excerpt_start_s=start))
        key[cid] = dict(song=song, dataset=it["dataset"], source=it["src"], role=it["role"], start_s=start, n_flashes=int(len(b)), local_only=it["dataset"] == "motorica")
        print(cid, song, it["src"], len(b), "flashes", flush=True)
    for w in cache.values():
        w.unlink()
    (OUT / "manifest.json").write_text(json.dumps(dict(labels=F1.QS[0]["labels"], clips=clips), indent=1))
    (OUT / "key.json").write_text(json.dumps(dict(seed=49302, items=key), indent=1))
    print("PULSE FLASH2 DONE", len(clips), flush=True)


if __name__ == "__main__":
    main()
