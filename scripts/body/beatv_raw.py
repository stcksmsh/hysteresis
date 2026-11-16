"""WO47 steps V2 (raw) and V3 (raw): docs/BEATV_RULES.md sections 0-2. Brain env.
    beatv_raw.py scan          scan every input (shape, finite, audio present) -> beatv/scan.json
    beatv_raw.py beats [P]     librosa beats of every song of the four datasets -> beatv/librosa/<key>.json (resumable, per-file errors logged to beatv/beats_failed.txt)
    beatv_raw.py raw [P]       raw FineDance: BAS (proxy and approximate FK), V3 sync scan, raw kinematic minima -> beatv/raw/<key>.json (resumable, errors in beatv/raw_failed.txt)"""
import json
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import beatv_lib as BL  # noqa: E402

B = Path("/secondary/hyst-data/body")
OUT = B / "beatv"
FD = Path("/secondary/hyst-data/datasets/finedance/data/finedance")
LISTS = {"finedance": B / "t0/lanes_list_fd.json", "aioz": B / "t0/lanes_list_aioz.json", "phantom": B / "t0_phantom/lanes_list.json", "motorica": B / "t0_motorica/lanes_list.json"}
SR = 22050


def songs():
    return [(ds, it["key"], it["wav"]) for ds in LISTS for it in json.loads(LISTS[ds].read_text())]


def librosa_beats(wav, hop=441):
    import librosa
    y, sr = librosa.load(wav, sr=SR)
    env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    _, b = librosa.beat.beat_track(onset_envelope=env, sr=sr, hop_length=hop, units="time")
    return [float(x) for x in b], float(len(y) / sr)


def log_fail(name, key, e):
    with open(OUT / name, "a") as f:
        f.write(f"{key} {type(e).__name__}: {e}\n")


def beats_one(a):
    ds, key, wav = a
    dst = OUT / "librosa" / f"{key}.json"
    if dst.exists():
        return key, "skip"
    try:
        b, dur = librosa_beats(wav)
        tmp = dst.with_suffix(".tmp")
        tmp.write_text(json.dumps(dict(beats=b, duration=dur)))
        tmp.replace(dst)
        return key, len(b)
    except Exception as e:
        log_fail("beats_failed.txt", key, e)
        return key, "failed"


def cmd_scan():
    bad, n = [], 0
    for ds, key, wav in songs():
        n += 1
        if not Path(wav).exists():
            bad.append((key, "no audio"))
    for p in sorted((FD / "motion").glob("*.npy")):
        m = np.load(p, mmap_mode="r")
        if m.ndim != 2 or m.shape[1] != 315 or len(m) < 300 or not np.isfinite(np.asarray(m)).all():
            bad.append((p.name, f"motion {m.shape}"))
        if not (FD / "music_wav" / f"{p.stem}.wav").exists():
            bad.append((p.name, "no wav"))
    (OUT / "scan.json").write_text(json.dumps(dict(songs=n, raw_files=len(list((FD / "motion").glob("*.npy"))), bad=bad)))
    print("scan", n, "songs", len(bad), "bad", bad[:10])


def cmd_beats(procs=6):
    (OUT / "librosa").mkdir(parents=True, exist_ok=True)
    jobs = songs()
    cnt = {}
    with mp.get_context("spawn").Pool(procs) as pool:
        for i, (k, st) in enumerate(pool.imap_unordered(beats_one, jobs, chunksize=2)):
            cnt["failed" if st == "failed" else "ok" if st != "skip" else "skip"] = cnt.get("failed" if st == "failed" else "ok" if st != "skip" else "skip", 0) + 1
            if i % 100 == 0:
                print(i, "/", len(jobs), k, st, cnt, flush=True)
    print("BEATS DONE", cnt, flush=True)


def raw_one(n):
    """n = '001' ... -> per-file results of V2 raw and V3 raw"""
    key = f"fd_{n}"
    dst = OUT / "raw" / f"{key}.json"
    if dst.exists():
        return key, "skip"
    try:
        import librosa
        m = np.load(FD / "motion" / f"{n}.npy").astype(float)
        R = BL.local_rots(m)
        sp = BL.angle_speed(R, 30)                                              # (T, 22) rad/s
        energy = sp.sum(1)                                                      # whole-body motion energy
        dur = len(m) / 30.0
        y, sr = librosa.load(str(FD / "music_wav" / f"{n}.wav"), sr=SR)
        env30 = librosa.onset.onset_strength(y=y, sr=sr, hop_length=735)
        lb = np.array(json.loads((OUT / "librosa" / f"{key}.json").read_text())["beats"])
        pb = np.array(json.loads((B / "t1b/cortex/beats" / f"{key}.json").read_text())["beats"])
        rng = np.random.default_rng(47102 + int(n))
        res = dict(key=key, dur=dur, n_lib=len(lb), n_proj=len(pb))
        pos = BL.fk(R, m[:, :3])
        speed_fk = np.linalg.norm(np.diff(pos, axis=0), axis=2).mean(1)
        speed_fk = np.r_[speed_fk, speed_fk[-1]] * 30
        for name, speed in (("proxy", energy / 22), ("fk", speed_fk)):
            kb = BL.kin_beats(speed, 30)
            for gname, g in (("lib", lb), ("proj", pb)):
                for mode in ("music", "kin"):
                    res[f"bas_{name}_{gname}_{mode}"] = BL.bas(g, kb, dur, mode=mode)
                    res[f"chance_{name}_{gname}_{mode}"] = BL.bas_chance(g, kb, dur, rng, mode=mode)
            res[f"n_kin_{name}"] = len(kb)
        # V3: sync scan of whole-body motion energy vs onset envelope, +-1 s in 1-frame steps
        M = min(len(energy), len(env30))
        a, e = energy[:M], env30[:M]
        k, c, z, p95, cc = BL.sync_scan(a, e, 30, rng)
        res.update(v3_best_k=k, v3_cmax=c, v3_z=z, v3_null95=p95, v3_c0=float(cc[30]))
        if M >= 30 * 150:
            k1, c1, *_ = BL.sync_scan(a[:1800], e[:1800], 30, rng, n_null=50, min_shift_frames=90)
            k2, c2, *_ = BL.sync_scan(a[-1800:], e[-1800:], 30, rng, n_null=50, min_shift_frames=90)
            res.update(v3_k_first=k1, v3_k_last=k2, v3_c_first=c1, v3_c_last=c2)
        # raw kinematic-speed minima for V1 (overseer/rawbeat.py recipe)
        from scipy.signal import find_peaks
        sm = np.convolve(energy, np.ones(3) / 3, "same")
        mins, _ = find_peaks(-sm, distance=6, prominence=np.std(energy) * 0.2)
        res["raw_minima"] = (mins / 30.0).tolist()
        tmp = dst.with_suffix(".tmp")
        tmp.write_text(json.dumps(res))
        tmp.replace(dst)
        return key, "ok"
    except Exception as e:
        log_fail("raw_failed.txt", key, e)
        return key, "failed"


def cmd_raw(procs=6):
    (OUT / "raw").mkdir(parents=True, exist_ok=True)
    ns = sorted(p.stem for p in (FD / "motion").glob("*.npy") if (B / "t1b/cortex/beats" / f"fd_{p.stem}.json").exists())
    cnt = {}
    with mp.get_context("spawn").Pool(procs) as pool:
        for i, (k, st) in enumerate(pool.imap_unordered(raw_one, ns)):
            cnt[st] = cnt.get(st, 0) + 1
            if i % 20 == 0:
                print(i, "/", len(ns), k, st, cnt, flush=True)
    print("RAW DONE", cnt, flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    OUT.mkdir(parents=True, exist_ok=True)
    {"scan": cmd_scan, "beats": cmd_beats, "raw": cmd_raw}[a[0]](*[int(x) for x in a[1:]])
