"""WO53 part A: mismatch-test material. Rules: docs/MISMATCH_RULES.md (read first). Brain env.

    mismatch_build.py plan        draw the 20 pairs + 5 repeats -> mismatch/material_key.json, mismatch/work/<id>_V?.csv|json, mismatch/work/<id>.m4a
    (render: RETARGET_ROOT=/secondary/hyst-data/body/mismatch/render_root HYST_BATTERY_OK=1 taskset -c 6-13 scripts/body/retarget_render.sh)
    mismatch_build.py assemble    one 21.5 s clip per item -> mismatch/clips_src/<id>.mp4, manifest.json
    mismatch_build.py checks      clip_checks.json, order_checks.json
Pure logic (draw_plan, tempo_ok, rms rules) is in the first half so the tests need no audio device or renderer. Nothing is served.
"""
import json
import random
import subprocess
import sys
from pathlib import Path

import numpy as np

B = Path("/secondary/hyst-data/body")
OUT = B / "mismatch"
LISTS = {"finedance": B / "t0/lanes_list_fd.json", "aioz": B / "t0/lanes_list_aioz.json", "phantomdance": B / "t0_phantom/lanes_list.json", "motorica": B / "t0_motorica/lanes_list.json"}
Q50 = {"finedance": "finedance", "phantomdance": "phantom", "motorica": "motorica"}
QUOTA = {"finedance": 7, "phantomdance": 7, "motorica": 6}
SEED, EXC, SR_RMS, SR_OUT, GAP = 53101, 10.0, 22050, 44100, 1.5
HALF = int(EXC * SR_OUT)
GAP_START, SECOND_START = HALF, HALF + int(GAP * SR_OUT)           # 441,000 and 507,150
TOTAL = SECOND_START + HALF                                          # 948,150
TEMPO_TOL = 0.05
Q_WHICH = {"q": "Which fits the music better?", "labels": ["first", "second", "same"]}
Q_CONF = {"q": "Confidence?", "labels": ["low", "medium", "high"]}


# ------------------------------------------------------------------ pure logic
def tempo_ok(real_bpm, foil_bpm, tol=TEMPO_TOL):
    return abs(foil_bpm / real_bpm - 1.0) <= tol + 1e-9


def tempo_bpm(beats):
    return 60.0 / float(np.median(np.diff(beats)))


def excerpt_ok(rms10, median, start, dur):
    """7.75 Q3: RMS of the 10 s at or above the song's own median, inside [10 s, dur - 10 s]"""
    return start >= 10.0 and start + EXC <= dur - 10.0 and rms10 >= median


def shift_foil(rng, start, dur):
    """-> (offset_s, outside_q3) or None. |offset| in [2, 6] on a 0.1 grid, sign random, flipped if it does not fit (Q3 window preferred)"""
    mag = rng.randint(20, 60) / 10.0
    sign = rng.choice([-1, 1])
    fits = lambda o, lo, hi: lo <= start + o and start + o + EXC <= hi
    for lo, hi, flag in ((10.0, dur - 10.0, False), (0.0, dur, True)):
        for s in (sign, -sign):
            if fits(s * mag, lo, hi):
                return round(s * mag, 1), flag
    return None


def balanced(rng, n, a, b):
    """n labels, as equal as possible, shuffled; for even n exactly n/2 each"""
    out = [a] * (n // 2) + [b] * (n - n // 2)
    rng.shuffle(out)
    return out


def assign(rng):
    """-> per dataset list of (version, kind) with the totals of docs/MISMATCH_RULES.md: V1 10 / V2 10, shifted 10 / different 10, 3-4 of each kind per dataset"""
    fd_v1 = rng.choice([3, 4]); v1 = {"finedance": fd_v1, "phantomdance": 7 - fd_v1, "motorica": 3}
    fd_sh = rng.choice([3, 4]); sh = {"finedance": fd_sh, "phantomdance": 7 - fd_sh, "motorica": 3}
    out = {}
    for ds, n in QUOTA.items():
        vs = ["V1"] * v1[ds] + ["V2"] * (n - v1[ds]); ks = ["shifted"] * sh[ds] + ["different_song"] * (n - sh[ds])
        rng.shuffle(vs); rng.shuffle(ks)
        out[ds] = list(zip(vs, ks))
    return out


def draw_sides_and_repeats(rng, kinds):
    """kinds: 20 kinds in pair order -> (real_side list, repeat pair indices). 5 / 5 sides per kind; repeats 5, >= 2 per kind, none twice"""
    side = [None] * len(kinds)
    for k in ("shifted", "different_song"):
        idx = [i for i, x in enumerate(kinds) if x == k]
        for i, s in zip(idx, balanced(rng, len(idx), "first", "second")):
            side[i] = s
    sh = [i for i, x in enumerate(kinds) if x == "shifted"]; di = [i for i, x in enumerate(kinds) if x == "different_song"]
    rng.shuffle(sh); rng.shuffle(di)
    rep = sh[:2] + di[:2] + [rng.choice(sh[2:] + di[2:])]
    return side, rep


# ------------------------------------------------------------------ audio helpers
def load_mono(wav, sr):
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(wav), "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"], capture_output=True, check=True)
    return np.frombuffer(p.stdout, np.float32)


def rms(a):
    return float(np.sqrt(np.mean(np.square(a, dtype=np.float64)))) if len(a) else 0.0


class Song:
    def __init__(self, key, wav):
        self.key, self.wav = key, wav
        self.y = load_mono(wav, SR_RMS)
        self.dur = len(self.y) / SR_RMS
        n = int(self.dur // EXC)
        self.median = float(np.median([rms(self.y[int(k * EXC * SR_RMS):int((k + 1) * EXC * SR_RMS)]) for k in range(n)])) if n else 1e9

    def rms10(self, start):
        return rms(self.y[int(round(start * SR_RMS)):int(round((start + EXC) * SR_RMS))])

    def ok(self, start):
        return excerpt_ok(self.rms10(start), self.median, start, self.dur)

    def starts(self, lo, hi):
        return [t / 2 for t in range(int(lo * 2), int(hi * 2) + 1) if self.ok(t / 2)]


# ------------------------------------------------------------------ plan
def songs_of(ds):
    return {it["key"]: it["wav"] for it in json.loads(LISTS[ds].read_text())}


def beats_of(key):
    p = B / "beatv/librosa" / f"{key}.json"
    return np.asarray(json.loads(p.read_text())["beats"], float) if p.exists() else None


def movement_pool(ds):
    """song -> {version: [(win, q50 index)]} of the kept windows that passed the gate again (V1 / V2 only, never the mirror copies)"""
    out = {}
    for p in sorted((B / "controls/q50" / Q50[ds]).glob("*__V[12].npz")):
        key, ver = p.stem.split("__")
        z = np.load(p)
        out.setdefault(key, {})[ver] = [(int(w), i) for i, w in enumerate(z["win"]) if bool(z["gate_again"][i])]
    return out


def cmd_plan():
    rng = random.Random(SEED)
    plan = assign(rng)
    lists = {ds: songs_of(ds) for ds in LISTS}
    cache = {}

    def song(key):
        if key not in cache:
            ds = next(d for d in LISTS if key in lists[d])
            cache[key] = Song(key, lists[ds][key])
        return cache[key]

    pairs, used_songs = [], set()
    for ds in QUOTA:
        pool = movement_pool(ds)
        keys = [k for k in sorted(pool) if k in lists[ds]]
        rng.shuffle(keys)
        todo = list(plan[ds])
        for key in keys:
            if not todo:
                break
            if key in used_songs:
                continue
            ver, kind = todo[0]
            wins = pool[key].get(ver)
            if not wins:
                continue
            try:
                s = song(key)
            except Exception as e:  # noqa: BLE001
                print("skip", key, e, file=sys.stderr); continue
            cand = [(w, i, o) for w, i in wins for o in np.arange(0, EXC + 0.01, 0.5) if s.ok(20.0 * w + o) and 20 * w + o + EXC <= 20 * w + 20]
            if not cand:
                continue
            rng.shuffle(cand)
            for w, i, o in cand:
                start = 20.0 * w + float(o)
                foil = None
                if kind == "shifted":
                    r = shift_foil(rng, start, s.dur)
                    if r:
                        foil = dict(song=key, dataset=ds, offset_s=r[0], excerpt_start_s=round(start + r[0], 1), tempo_bpm_real=None, tempo_bpm_foil=None, tempo_ratio=None); outside = r[1]
                else:
                    foil, outside = pick_diff_foil(rng, key, ds, s, lists, song, used_songs), False
                if foil:
                    pairs.append(dict(dataset=ds, version=ver, kind=kind, song=key, window=w, q_index=i, window_offset_s=float(o), excerpt_start_s=start, excerpt_end_s=start + EXC,
                                      foil=foil, foil_outside_q3=outside, rms_real=s.rms10(start), rms_foil=song(foil["song"]).rms10(foil["excerpt_start_s"])))
                    used_songs.add(key)
                    if kind == "different_song":
                        used_songs.add(foil["song"])
                    todo.pop(0)
                    break
        if todo:
            raise SystemExit(f"{ds}: could not fill {len(todo)} pairs")
    rng.shuffle(pairs)
    sides, rep = draw_sides_and_repeats(rng, [p["kind"] for p in pairs])
    items = {}
    for n, (p, sd) in enumerate(zip(pairs, sides), 1):
        pid = f"P{n:02d}"
        items[pid] = dict(id=pid, repeat=False, repeat_of=None, real_side=sd, **p)
    reps = list(rep); rng.shuffle(reps)
    for n, i in enumerate(reps, 1):
        o = items[f"P{i + 1:02d}"]
        items[f"R{n:02d}"] = {**o, "id": f"R{n:02d}", "repeat": True, "repeat_of": o["id"], "real_side": "second" if o["real_side"] == "first" else "first"}
    key = dict(version=1, seed=SEED, rule=dict(threshold=0.70, flip_form="lower95 > 0.5 + f/2"), items=items)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "material_key.json").write_text(json.dumps(key, indent=1, default=float))
    write_work(items, lists)
    print("planned", len(items), "items")


def pick_diff_foil(rng, key, ds, s, lists, song, used):
    bs = beats_of(key)
    if bs is None or len(bs) < 4:
        return None
    t_real = tempo_bpm(bs)
    order = [d for d in (ds, *[x for x in LISTS if x != ds])]
    for d in order:
        ks = [k for k in sorted(lists[d]) if k != key and k not in used]
        rng.shuffle(ks)
        for k in ks:
            b = beats_of(k)
            if b is None or len(b) < 4 or not tempo_ok(t_real, tempo_bpm(b)):
                continue
            try:
                f = song(k)
            except Exception:  # noqa: BLE001
                continue
            st = f.starts(10.0, f.dur - 10.0 - EXC)
            if st:
                t0 = rng.choice(st)
                return dict(song=k, dataset=d, offset_s=None, excerpt_start_s=t0, tempo_bpm_real=t_real, tempo_bpm_foil=tempo_bpm(b), tempo_ratio=tempo_bpm(b) / t_real)
    return None


def write_work(items, lists):
    """one retarget_render work file per distinct movement: <pid>_<ver>.csv/json and the real music as <pid>.m4a (the page video does not depend on it, checked in assemble)"""
    import arm_sim
    W = OUT / "render_root/work"
    W.mkdir(parents=True, exist_ok=True)
    for it in items.values():
        if it["repeat"]:
            continue
        z = np.load(B / "controls/q50" / Q50[it["dataset"]] / f"{it['song']}__{it['version']}.npz")
        a = int(round(it["window_offset_s"] * 50))
        q = z["q50"][it["q_index"]][a:a + int(EXC * 50) + 1].astype(float)
        cid = f"{it['id']}_{it['version']}"
        (W / f"{cid}.csv").write_text(arm_sim.csv_text(q, 50, name=cid))
        (W / f"{cid}.json").write_text(json.dumps(dict(id=cid, clip=it["id"], variant=it["version"], gates=dict(passed=True, note="stored realised q50 of a kept window, gate_again true"))))
        wav = lists[it["dataset"]][it["song"]]
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{it['excerpt_start_s']:.3f}", "-t", f"{EXC}", "-i", str(wav), "-ac", "2", "-ar", "48000", "-c:a", "aac", "-b:a", "192k", str(W / f"{it['id']}.m4a")], check=True)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    if sys.argv[1] == "plan":
        cmd_plan()


# ------------------------------------------------------------------ assemble
def run(*a):
    subprocess.run([str(x) for x in a], check=True, capture_output=True)


def read_wav_slice(wav, start, sr=SR_OUT):
    a = load_mono(wav, sr)
    return a[int(round(start * sr)):int(round(start * sr)) + HALF]


def compose_audio(real, foil, side, ra, fa):
    """-> (float32 array of TOTAL samples, gain_real, gain_foil): RMS match of the two halves to their mean, pure gain, peak < 0.99"""
    target = 0.5 * (rms(real) + rms(foil))
    gr, gf = target / rms(real), target / rms(foil)
    peak = max(np.abs(real).max() * gr, np.abs(foil).max() * gf)
    if peak >= 0.99:
        k = 0.99 / peak; gr, gf = gr * k, gf * k
    out = np.zeros(TOTAL, np.float32)
    first, second = (real * gr, foil * gf) if side == "first" else (foil * gf, real * gr)
    out[:HALF], out[SECOND_START:] = first, second
    return out, float(gr), float(gf)


def write_wav16(path, a):
    import soundfile as sf
    sf.write(str(path), a, SR_OUT, subtype="PCM_16")


def cmd_assemble():
    key = json.loads((OUT / "material_key.json").read_text())
    items = key["items"]
    lists = {ds: songs_of(ds) for ds in LISTS}
    wavs = {k: w for d in lists.values() for k, w in d.items()}
    W, R, CS = OUT / "work", OUT / "render_root/clips", OUT / "clips_src"
    for d in (W / "wav", W / "half", CS):
        d.mkdir(parents=True, exist_ok=True)
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30", "-g", "30", "-an", "-map_metadata", "-1"]
    run("ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=30:d=1.5", *enc, W / "half/black.mp4")
    for it in items.values():
        orig = items[it["repeat_of"]] if it["repeat"] else it
        half = W / "half" / f"{orig['id']}.mp4"
        if not half.exists():
            run("ffmpeg", "-v", "error", "-y", "-i", R / f"{orig['id']}_{orig['version']}.mp4", "-t", "10", *enc, half)
        real = read_wav_slice(wavs[it["song"]], it["excerpt_start_s"])
        foil = read_wav_slice(wavs[it["foil"]["song"]], it["foil"]["excerpt_start_s"])
        a, gr, gf = compose_audio(real, foil, it["real_side"], None, None)
        it["gain_real"], it["gain_foil"] = gr, gf
        it["rms_real"], it["rms_foil"] = rms(real), rms(foil)
        write_wav16(W / "wav" / f"{it['id']}.wav", a)
        lst = W / "half" / f"{it['id']}.txt"
        lst.write_text("".join(f"file '{p}'\n" for p in (half, W / "half/black.mp4", half)))
        vid = W / "half" / f"{it['id']}_v.mp4"
        run("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", vid)
        run("ffmpeg", "-v", "error", "-y", "-i", vid, "-i", W / "wav" / f"{it['id']}.wav", "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-ar", str(SR_OUT), "-ac", "1", "-t", "21.5", "-map_metadata", "-1", "-fflags", "+bitexact", "-flags:v", "+bitexact", "-flags:a", "+bitexact", CS / f"{it['id']}.mp4")
    (OUT / "material_key.json").write_text(json.dumps(key, indent=1, default=float))
    man = [dict(id=i, file=f"clips_src/{i}.mp4", kind="single", questions=[Q_WHICH, Q_CONF]) for i in sorted(items)]
    (OUT / "manifest.json").write_text(json.dumps(dict(clips=man), indent=1))
    print("assembled", len(man))


if __name__ == "__main__" and sys.argv[1] == "assemble":
    cmd_assemble()


# ------------------------------------------------------------------ checks
def frames_gray(path, w=160, h=90):
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"scale={w}:{h}", "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True, check=True)
    return np.frombuffer(p.stdout, np.uint8).reshape(-1, h, w)


def xcorr_lag(a, ref, maxlag=2500):
    """lag (samples, positive = a later than ref) of the correlation peak and the normalised correlation there"""
    n = len(ref)
    best = (0, -2.0)
    r = ref - ref.mean(); rn = np.linalg.norm(r)
    for lag in range(-maxlag, maxlag + 1, 1):
        seg = a[max(0, lag):max(0, lag) + n] if lag >= 0 else np.concatenate([np.zeros(-lag, np.float32), a[:n + lag]])
        if len(seg) < n:
            continue
        s = seg - seg.mean(); d = np.linalg.norm(s) * rn
        c = float(s @ r / d) if d else 0.0
        if c > best[1]:
            best = (lag, c)
    return best


def limit_ratios(csv):
    import arm_sim as M0
    rows = np.array([[float(x) for x in l.split(",")[1:]] for l in Path(csv).read_text().splitlines() if l and l[0].isdigit()])
    sp = np.abs(np.diff(rows, axis=0)) * 50; ac = np.abs(np.diff(rows, 2, axis=0)) * 2500
    lim = np.array(M0.M.LIMITS, float)                 # (5, 2): speed deg/s, accel deg/s^2
    return float((sp.max(0) / lim[:, 0]).max()), float((ac.max(0) / lim[:, 1]).max())


def cmd_checks(session=None):
    key = json.loads((OUT / "material_key.json").read_text())["items"]
    lists = {ds: songs_of(ds) for ds in LISTS}
    wavs = {k: w for d in lists.values() for k, w in d.items()}
    res, W = {}, OUT / "work"
    for i, it in sorted(key.items()):
        c = {}
        clip = OUT / "clips_src" / f"{i}.mp4"
        pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-show_entries", "stream=codec_type,nb_read_frames,duration,sample_rate:format=duration:format_tags:stream_tags", "-of", "json", str(clip)], capture_output=True, check=True).stdout)
        v = next(s for s in pr["streams"] if s["codec_type"] == "video"); au = next(s for s in pr["streams"] if s["codec_type"] == "audio")
        c["frames"] = int(v["nb_read_frames"]); c["frames_ok"] = c["frames"] == 645
        c["format_duration_s"] = float(pr["format"]["duration"]); c["duration_ok"] = abs(c["format_duration_s"] - 21.5) <= 1 / 30 + 1e-3
        c["metadata_tags"] = pr["format"].get("tags", {}); c["metadata_clean"] = not any(t for k, t in c["metadata_tags"].items() if k not in ("major_brand", "minor_version", "compatible_brands", "encoder", "handler_name"))
        wav = load_mono(W / "wav" / f"{i}.wav", SR_OUT)
        c["wav_samples"] = len(wav); c["wav_samples_ok"] = len(wav) == TOTAL
        c["gap_wav_max_abs"] = float(np.abs(wav[GAP_START:SECOND_START]).max()); c["gap_digital_silence"] = c["gap_wav_max_abs"] == 0.0
        g = frames_gray(clip)
        c["gap_frame_mean_max"] = float(g[300:345].mean(axis=(1, 2)).max()); c["gap_black"] = c["gap_frame_mean_max"] < 2.0
        c["halves_frames_identical"] = bool(np.array_equal(g[:300], g[345:645]))
        dec = load_mono(clip, SR_OUT)
        side = it["real_side"]
        realwav = read_wav_slice(wavs[it["song"]], it["excerpt_start_s"]) * (it["gain_real"])
        ra = 0 if side == "first" else SECOND_START
        # sample-for-sample on the pre-encode wav (int16 quantisation <= 1/32768 + rounding)
        c["real_half_max_abs_diff_wav"] = float(np.abs(wav[ra:ra + HALF] - realwav).max()); c["real_half_sample_exact"] = c["real_half_max_abs_diff_wav"] <= 2 / 32768
        lag, cor = xcorr_lag(dec[ra:ra + HALF + 2600], realwav[:HALF])
        c["aac_real_lag_samples"], c["aac_real_corr"] = lag, cor
        c["aac_start_ok"] = abs(lag) <= 1024 and cor > 0.99
        fa = SECOND_START if side == "first" else 0
        fw = read_wav_slice(wavs[it["foil"]["song"]], it["foil"]["excerpt_start_s"]) * it["gain_foil"]
        c["rms_ratio_halves"] = rms(wav[ra:ra + HALF]) / rms(wav[fa:fa + HALF]); c["rms_match_ok"] = abs(c["rms_ratio_halves"] - 1) <= 0.01
        c["peak"] = float(np.abs(wav).max()); c["peak_ok"] = c["peak"] < 0.99
        orig = key[it["repeat_of"]] if it["repeat"] else it
        sp, ac = limit_ratios(OUT / f"render_root/work/{orig['id']}_{orig['version']}.csv")
        c["speed_ratio_max"], c["accel_ratio_max"] = sp, ac; c["limits_ok"] = sp <= 1.0 + 1e-3 and ac <= 1.0 + 1e-3
        c["pass"] = all(v for k, v in c.items() if k.endswith("_ok") or k in ("gap_digital_silence", "gap_black", "halves_frames_identical", "metadata_clean"))
        res[i] = c
    (OUT / "clip_checks.json").write_text(json.dumps(res, indent=1, default=float))
    print("clip checks pass:", sum(c["pass"] for c in res.values()), "/", len(res))


if __name__ == "__main__" and sys.argv[1] == "checks":
    cmd_checks()
