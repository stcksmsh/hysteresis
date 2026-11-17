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


def check():
    """every clip: video and audio stream about 30 s; flash count in key.json = events in the window; for pulse v2 items the decoded disc
    brightness at each flash's first frame matches 0.15 + 0.85 x confidence (correlation over all flashes of the item) -> view/check.json"""
    import subprocess
    key = json.loads((OUT / "key.json").read_text())["items"]
    out, bad = {}, []
    for cid, k in sorted(key.items()):
        f = OUT / f"{cid}.mp4"
        pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "csv=p=0", str(f)], capture_output=True, text=True).stdout.split()
        d = {s.split(",")[0]: float(s.split(",")[1]) for s in pr}
        if k["source"] == "pulse2":
            z = np.load(B / "pulse2/songs" / f"{k['song']}.npz")
            ev, br = z["events"], brightness(z["event_conf"])
        else:
            ev = R.load_beats(B / "beatv/librosa" / f"{k['song']}.json"); br = np.ones(len(ev))
        m = (ev >= k["start_s"]) & (ev < k["start_s"] + V.LEN)
        row = dict(video_s=d.get("video"), audio_s=d.get("audio"), n_key=k["n_flashes"], n_events=int(m.sum()))
        v = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(f), "-vf", "crop=60:60:290:150,format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
        fr = np.frombuffer(v, np.uint8).reshape(-1, 60, 60).mean((1, 2))
        idx = np.minimum(np.ceil((ev[m] - k["start_s"]) * V.FPS - 1e-9).astype(int), len(fr) - 1)
        lum = (fr[idx] - V.BG.mean()) / (255 - V.BG.mean())
        want = np.array([V.intensity(i / V.FPS, ev[m] - k["start_s"], br[m]) for i in idx])    # incl. the fade to that frame
        row["brightness_corr"] = float(np.corrcoef(lum, want)[0, 1]) if k["source"] == "pulse2" and np.std(want) > 0 else None
        row["brightness_mae"] = float(np.mean(np.abs(lum - want)))
        ok = abs((d.get("video") or 0) - V.LEN) < 0.05 and abs((d.get("audio") or 0) - V.LEN) < 0.1 and row["n_key"] == row["n_events"] and row["brightness_mae"] < 0.1
        row["ok"] = bool(ok)
        if not ok:
            bad.append(cid)
        out[cid] = row
        print(cid, row, flush=True)
    (OUT / "check.json").write_text(json.dumps(dict(bad=bad, items=out), indent=1))
    print("PULSE2 VIEW CHECK", len(out), "items,", len(bad), "bad", bad, flush=True)


if __name__ == "__main__":
    check() if sys.argv[1:] == ["check"] else main()
