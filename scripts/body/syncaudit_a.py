"""WO54 A1 synthetic probe. Rules: docs/SYNCAUDIT_RULES_A.md. Body env (/secondary/hyst-env/body). Report only: imports and calls the pipeline, edits nothing.

    syncaudit_a.py gen        synthetic songs and FineDance-format motion -> OUT/syn/
    syncaudit_a.py chain      stages 1-10 (loaded .. q50, lamp, raw FK) per sequence and copy -> OUT/chain.json, OUT/controls/q50/finedance/
    syncaudit_a.py items      mismatch-style items on the synthetic q50 (write_work: csv, m4a) -> OUT/material_key.json, OUT/render_root/work
    (render: RETARGET_ROOT=OUT/render_root HYST_BATTERY_OK=1 scripts/body/retarget_render.sh P01_V1 ...)
    syncaudit_a.py assemble   mismatch_build.cmd_assemble on the synthetic items -> OUT/clips_src
    syncaudit_a.py final      stages 11-14: csv, rendered frames, final clip audio vs video, foil shift -> OUT/final.json
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import syncaudit_lib as S  # noqa: E402

OUT = Path("/secondary/hyst-data/body/syncaudit/a")
SEQS = {"syn_arm30": ("arm", 30.0), "syn_arm50": ("arm", 50.0), "syn_mixed30": ("mixed", 30.0), "syn_torso30": ("torso", 30.0), "syn_pelvis30": ("pelvis", 30.0), "syn_feet30": ("feet", 30.0)}
MIXED = ("arm", "torso", "pelvis")
fam_of = lambda fam: (lambda i: MIXED[i % 3]) if fam == "mixed" else (lambda i: fam)
WIN = {"syn_arm30": 0, "syn_arm50": 1, "syn_mixed30": 0, "syn_torso30": 0, "syn_pelvis30": 0, "syn_feet30": 0}


def cmd_gen():
    import wave

    def write16(path, a):
        with wave.open(str(path), "wb") as f:
            f.setnchannels(1); f.setsampwidth(2); f.setframerate(S.SR)
            f.writeframes(np.round(np.clip(a, -1, 1) * 32767).astype("<i2").tobytes())
    (OUT / "syn").mkdir(parents=True, exist_ok=True)
    meta = {}
    for name, (fam, dur) in SEQS.items():
        ck = S.click_times(dur)
        np.save(OUT / "syn" / f"{name}.npy", S.synth_motion(ck, fam_of(fam), dur))
        write16(OUT / "syn" / f"{name}.wav", S.click_audio(ck, dur))
        meta[name] = dict(family=fam, dur_s=dur, clicks=ck, families=[fam_of(fam)(i) for i in range(len(ck))])
    (OUT / "syn" / "meta.json").write_text(json.dumps(meta, indent=1))
    print("gen", list(SEQS))


def stage_rows(name, copy):
    """-> {stage: (t, X(n, c), rate_hz, note)} for the synthetic sequence, the real code of t0_chain / controls_run, plus the stored q50 / lamp"""
    import lowpass_cutoff as LC
    import make_arm_v2p as P
    import motornet as M
    import retarget as RT
    import retarget_limiter as FX
    import t0_chain as C
    import t0_lib as T
    meta = json.loads((OUT / "syn" / "meta.json").read_text())[name]
    m = np.load(OUT / "syn" / f"{name}.npy")
    rot, trans = T.load_rot(OUT / "syn" / f"{name}.npy")
    var = copy[:2]
    v = T.angles_of(rot, var)
    vr = RT.referenced(v, 0)
    y = RT.to_commands(vr, var)
    yf = LC.lowpass(y, C.CUT[var])
    y2, yf2 = C.stage1(rot, copy)
    assert np.allclose(y, y2) and np.allclose(yf, yf2), "replicated stage 1 differs from t0_chain.stage1"
    tg, gs = C.target(yf)
    n30 = len(yf)
    t30, t100 = np.arange(n30) / 30.0, np.arange(len(tg)) / 100.0
    st = {"2 human_angles (30 Hz)": (t30, v, 30, ""), "3 to_commands (30 Hz)": (t30, y, 30, ""), "4 low-pass (30 Hz)": (t30, yf, 30, ""), "5 spline+guard target (100 Hz)": (t100, tg, 100, "")}
    return st, tg, rot, trans, meta, m


def window_stages(tg, w, var):
    """replicates controls_run.sim_file for window w step by step: -> stages dict and the q50, lamp (real code), asserts equal to the stored arrays"""
    import make_arm_v2p as P
    import motornet as M
    import retarget_limiter as FX
    import m3f_report as R
    import retarget_run as RR
    RR.patch_gates()                                    # sim_file does this first: WARM_S = 1.5 s, v2p body
    PRE, WIN_ROWS = 150, 2000
    tg = tg.astype(np.float32).astype(float)             # sim_file reads the targets back from the float32 T0 npz
    a = w * WIN_ROWS
    rows = tg[a:a + WIN_ROWS + 1]
    pre = tg[a - PRE:a] if a >= PRE else np.repeat(rows[:1], PRE, 0)
    import retarget as RT
    K = RT.to_commands(np.zeros((1, 5)), var)[0]
    sh = np.zeros(5)
    sh[[0, 4]] = (rows[0] - K)[[0, 4]]                    # sim_file: yaw and roll shifted so the window starts at the centre
    cat = np.concatenate([pre, rows]) - sh
    G, gs = P.guard(cat)
    Sp = M.spinal(G)
    q50, _ = FX.simulate_goals(Sp)
    t_cat = 20.0 * w + (np.arange(len(cat)) - PRE) / 100.0
    lamp = R.fk_points(np.asarray(q50, float))[:, 5]
    return {"6 window rows + pre-roll, guard (100 Hz)": (t_cat, G, 100, f"row i of the concatenation = window time 20 w + (i - {PRE}) / 100"),
            "7 spinal layer out (100 Hz)": (t_cat, Sp, 100, ""),
            "8 limiter+servo q50 (50 Hz)": (20.0 * w + np.arange(len(q50)) * 0.02, np.asarray(q50, float), 50, "row k = 20 w + k x 0.02 s as sim_file stores it"),
            "9 lamp point (50 Hz)": (20.0 * w + np.arange(len(q50)) * 0.02, np.asarray(lamp, float), 50, "")}, q50, lamp


def measure(t, X, clicks, lo, hi, gap=1.5):
    """per channel of X: (a) matched-filter lag of the dense click block 3-8 s (normalised cross-correlation of |x - median| with the ideal bump train, lag over +-0.4 s,
    parabolic, positive = movement later) and (b) per-impulse centroid / parabolic-peak offsets of the isolated clicks (>= 1.5 s from any other) inside [lo, hi].
    main = the channel with the highest matched-filter correlation"""
    X = X.reshape(len(X), -1)
    ck = [c for c in clicks if lo <= c <= hi]
    iso = S.isolated(clicks, gap)
    iso = [c for c in iso if lo <= c <= hi]
    dense = [c for c in clicks if 3.0 <= c <= 8.0]
    dt = float(t[1] - t[0])
    m = (t >= 3.0 - 0.8) & (t <= 8.0 + 0.8) & (t >= lo - 0.8) & (t <= hi + 0.8)
    ref = sum(S.bump(t[m], c) for c in dense) if m.any() and any(lo <= c <= hi for c in dense) else None
    res = {}
    for ch in range(X.shape[1]):
        r = dict(ptp=float(np.ptp(X[:, ch])))
        if ref is not None:
            x = np.abs(X[m, ch] - np.median(X[:, ch]))
            lag, cor = S.xcorr_lag_s(ref, x, dt, 0.4)
            r["train_lag_ms"], r["train_corr"] = 1000 * lag, cor
        c, p = S.offsets_ms(t, X[:, ch], iso, 0.8)
        r["centroid"], r["peak"] = S.summarise(c), S.summarise(p)
        r["per_impulse_centroid_ms"] = [None if np.isnan(x) else round(float(x), 3) for x in c]
        r["isolated_clicks"] = iso
        res[ch] = r
    main = max(res, key=lambda k: res[k].get("train_corr", res[k]["ptp"]))
    return dict(main_channel=int(main), main=res[main], channels=res)


def cmd_chain():
    import controls_run as CR
    import beatv_lib as BL
    import t0_lib as T
    CR.OUT = OUT / "controls"
    (OUT / "t0").mkdir(parents=True, exist_ok=True)
    allres = {}
    for name in SEQS:
        for copy in ("V1", "V2"):
            tag = f"{name}__{copy}"
            try:
                st, tg, rot, trans, meta, m = stage_rows(name, copy)
                clicks = meta["clicks"]
                res = {}
                fams = meta["families"]

                def put(key, t, X, lo, hi, rate, note=""):
                    if meta["family"] == "mixed":        # each family's clicks on their own: the channel that answers differs
                        for fam in MIXED:
                            ck = [c for c, f in zip(clicks, fams) if f == fam]
                            res[f"{key} [{fam}]"] = dict(**measure(t, X, ck, lo, hi, gap=1.4), rate=rate, note=note)
                    else:
                        res[key] = dict(**measure(t, X, clicks, lo, hi), rate=rate, note=note)
                # 1 loaded: audio (the wav through the loader the dataset uses: ffmpeg decode at 44.1 k mono) and motion (rotation angle of the family's joints)
                import mismatch_build as MB
                a = MB.load_mono(OUT / "syn" / f"{name}.wav", S.SR)
                off = S.audio_click_offsets_ms(a, clicks)
                res["1a loaded audio (44.1 kHz)"] = dict(main=dict(centroid=S.summarise(off), per_impulse_centroid_ms=[round(float(x), 4) for x in off]), rate=S.SR)
                R6 = m[:, 3:].reshape(len(m), 52, 6).astype(float)
                ang = np.zeros(len(m))
                from scipy.spatial.transform import Rotation as Rot
                for j in sorted({j for fam in set(meta["families"]) for j, _ in S.FAMILY_JOINTS[fam]}):
                    ang += np.degrees(np.linalg.norm(Rot.from_matrix(S._rows(R6[:, j])).as_rotvec(), axis=1))
                put("1b loaded motion (30 Hz, family joints' rotation angle)", np.arange(len(m)) / 30.0, ang[:, None], 0.75, len(m) / 30 - 0.75, 30)
                for k, (t, X, rate, note) in st.items():
                    put(k, t, X, 0.75, t[-1] - 0.75, rate, note)
                # windows: the stored q50 of controls_run.sim_file (real function) against the replication
                n_win = T.n_windows(len(m))
                w = WIN[name] if WIN[name] < n_win else 0
                p = OUT / "t0" / f"{tag}.npz"
                np.savez_compressed(p, targets=tg.astype(np.float32), win_pass=np.ones(n_win, bool), split="train", group="syn", weight=1.0)
                dstq = OUT / "controls/q50/finedance" / f"{tag}.npz"
                if not dstq.exists():
                    CR.sim_file(("finedance", p))
                z = np.load(dstq)
                wi = int(np.flatnonzero(z["win"] == w)[0])
                ws, q50, lamp = window_stages(tg, w, copy[:2])
                assert np.allclose(q50, z["q50"][wi], atol=1e-3), f"replicated window differs from controls_run.sim_file (max {np.abs(q50 - z['q50'][wi]).max():.4g} deg, tg float32)"
                lo, hi = 20.0 * w, 20.0 * w + 20.0
                for k, (t, X, rate, note) in ws.items():
                    put(k, t, X, max(lo, t[0]) + 0.75, min(hi, t[-1]) - 0.75, rate, note)
                    if k.startswith("9"):
                        tl = t[1:]
                        sp = np.linalg.norm(np.diff(X, axis=0), axis=1) * 50
                        put("9b lamp speed (50 Hz)", tl, sp[:, None], lo + 0.75, hi - 0.75, 50, "the WO52 signal")
                # 10 raw FK joints (WO53 B)
                R = BL.local_rots(m.astype(float))
                pos = BL.fk(R, m[:, :3].astype(float))
                for nm, j in (("right wrist", 21), ("left wrist", 20), ("right foot", 11), ("left foot", 10), ("right ankle", 8), ("left ankle", 7), ("pelvis", 0), ("head", 15)):
                    sp = np.linalg.norm(np.diff(pos[:, j], axis=0), axis=1) * 30
                    put(f"10 raw FK speed {nm} (30 Hz)", np.arange(1, len(m)) / 30.0 - 0.5 / 30, sp[:, None], 0.75, len(m) / 30 - 0.75, 30, "diff between frames k-1 and k stamped at the midpoint")
                allres[tag] = dict(window=w, stages=res)
                print(tag, "ok", flush=True)
            except Exception as e:  # noqa: BLE001
                allres[tag] = dict(error=f"{type(e).__name__}: {e}")
                print(tag, "FAILED", e, flush=True)
    (OUT / "chain.json").write_text(json.dumps(allres, indent=1, default=float))
    print("chain done")


SINES = [(f, fam) for f in (0.5, 1.0, 2.0) for fam in ("arm", "torso")]


def cmd_sine():
    """small-amplitude continuous probe: 20 deg sinusoid of the family's joints at 0.5, 1, 2 Hz through the same stages; delay by demodulation at f over the steady part of the window"""
    import controls_run as CR
    import t0_lib as T
    CR.OUT = OUT / "controls"
    (OUT / "t0").mkdir(parents=True, exist_ok=True)
    meta = {}
    for f, fam in SINES:
        name = f"sin_{fam}_{f}".replace(".", "p")
        np.save(OUT / "syn" / f"{name}.npy", S.synth_sine(f, 30.0, fam))
        meta[name] = dict(family=fam, dur_s=30.0, clicks=[], families=[])
    old = json.loads((OUT / "syn" / "meta.json").read_text())
    (OUT / "syn" / "meta.json").write_text(json.dumps({**old, **meta}, indent=1))
    out = {}
    for f, fam in SINES:
        name = f"sin_{fam}_{f}".replace(".", "p")
        for copy in ("V1", "V2"):
            tag = f"{name}__{copy}"
            try:
                st, tg, rot, trans, mt, m = stage_rows(name, copy)
                p = OUT / "t0" / f"{tag}.npz"
                np.savez_compressed(p, targets=tg.astype(np.float32), win_pass=np.ones(T.n_windows(len(m)), bool), split="train", group="syn", weight=1.0)
                dstq = OUT / "controls/q50/finedance" / f"{tag}.npz"
                if not dstq.exists():
                    CR.sim_file(("finedance", p))
                ws, q50, lamp = window_stages(tg, 0, copy[:2])
                res = {}
                t30 = np.arange(len(m)) / 30.0
                ang = np.zeros(len(m))
                from scipy.spatial.transform import Rotation as Rot
                R6 = m[:, 3:].reshape(len(m), 52, 6).astype(float)
                for j, _ in S.FAMILY_JOINTS[fam]:
                    ang += np.degrees(np.linalg.norm(Rot.from_matrix(S._rows(R6[:, j])).as_rotvec(), axis=1)) * np.sign(np.sin(2 * np.pi * f * t30) + 1e-12)
                allst = {"1b loaded motion (signed family angle)": (t30, ang[:, None]), **{k: (t, X) for k, (t, X, r, n) in {**st, **ws}.items()}}
                for k, (t, X) in allst.items():
                    X = X.reshape(len(X), -1)
                    lo = max(t[0], 5.0) if not k.startswith(("6", "7", "8", "9")) else 5.0
                    best = max(range(X.shape[1]), key=lambda c: S.demod_lag(t, X[:, c], f, lo, 18.0)[1])
                    tau, amp = S.demod_lag(t, X[:, best], f, lo, 18.0)
                    res[k] = dict(channel=best, lag_ms=tau, amp=amp)
                out[tag] = res
                print(tag, "ok", flush=True)
            except Exception as e:  # noqa: BLE001
                out[tag] = dict(error=f"{type(e).__name__}: {e}")
                print(tag, "FAILED", e, flush=True)
    (OUT / "sine.json").write_text(json.dumps(out, indent=1, default=float))


ITEMS = [  # id, song, version, window, offset in window (s), foil kind, foil song, foil shift / start, real side
    ("P01", "syn_arm30", "V1", 0, 9.5, "shifted", None, 3.0, "first"),
    ("P02", "syn_arm50", "V1", 1, 5.0, "shifted", None, -3.0, "second"),
    ("P03", "syn_torso30", "V1", 0, 9.5, "shifted", None, 4.0, "first"),
    ("P04", "syn_pelvis30", "V2", 0, 9.5, "shifted", None, -4.0, "second"),
    ("P05", "syn_arm30", "V2", 0, 9.5, "different_song", "syn_pelvis30", 9.5, "first")]


def patch_mb():
    import mismatch_build as MB
    MB.B, MB.OUT = OUT, OUT
    for ds in MB.LISTS:
        MB.LISTS[ds] = OUT / f"lists_{ds}.json"
    return MB


def cmd_items():
    """mismatch-style items on the synthetic q50: the real write_work (csv, m4a) and the key; paths patched to the probe's folder"""
    MB = patch_mb()
    meta = json.loads((OUT / "syn" / "meta.json").read_text())
    for ds in MB.LISTS:
        (OUT / f"lists_{ds}.json").write_text(json.dumps([dict(key=k, wav=str(OUT / "syn" / f"{k}.wav")) for k in SEQS] if ds == "finedance" else []))
    items = {}
    for pid, song, ver, w, o, kind, fsong, fval, side in ITEMS:
        z = np.load(OUT / "controls/q50/finedance" / f"{song}__{ver}.npz")
        qi = int(np.flatnonzero(z["win"] == w)[0])
        start = 20.0 * w + o
        foil = dict(song=song if kind == "shifted" else fsong, dataset="finedance", offset_s=fval if kind == "shifted" else None,
                    excerpt_start_s=start + fval if kind == "shifted" else fval, tempo_bpm_real=None, tempo_bpm_foil=None, tempo_ratio=None)
        items[pid] = dict(id=pid, repeat=False, repeat_of=None, kind=kind, real_side=side, dataset="finedance", version=ver, song=song, window=w, q_index=qi, window_offset_s=o,
                          excerpt_start_s=start, excerpt_end_s=start + 10.0, foil=foil, foil_outside_q3=False, rms_real=0.0, rms_foil=0.0)
    (OUT / "material_key.json").write_text(json.dumps(dict(version=1, seed=0, rule={}, items=items), indent=1))
    MB.write_work(items, {ds: MB.songs_of(ds) for ds in MB.LISTS})
    print("items", list(items))


def cmd_assemble():
    MB = patch_mb()
    MB.cmd_assemble()


def probe_json(path, *args):
    return json.loads(subprocess.run(["ffprobe", "-v", "error", "-of", "json", *args, str(path)], capture_output=True, check=True).stdout)


def gray_frames(path, w=320, h=180):
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-an", "-vf", f"scale={w}:{h}", "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True, check=True)
    return np.frombuffer(p.stdout, np.uint8).reshape(-1, h, w).astype(np.float32)


def motion_energy(fr):
    """mean |frame k - frame k-1| below the label rows, stamped at the midpoint (k - 0.5) / 30; returns (t, E)"""
    d = np.abs(np.diff(fr[:, 12:, :], axis=0)).mean(axis=(1, 2))
    return (np.arange(1, len(fr)) - 0.5) / 30.0, d


def click_positions(a, sr=S.SR, thr=0.3):
    """click centroid times (s) of the bursts above thr in a half of audio (sample resolution)"""
    idx = np.flatnonzero(np.abs(a) > thr)
    out, i = [], 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and idx[j + 1] - idx[j] < int(0.05 * sr):
            j += 1
        lo, hi = max(0, idx[i] - 60), idx[j] + 60
        w = np.abs(a[lo:hi]).astype(float)
        out.append(float((np.arange(lo, hi) * w).sum() / w.sum() / sr))
        i = j + 1
    return out


def cmd_final():
    MB = patch_mb()
    key = json.loads((OUT / "material_key.json").read_text())["items"]
    meta = json.loads((OUT / "syn" / "meta.json").read_text())
    res = {}
    for pid, it in key.items():
        r = {}
        song, start, side = it["song"], it["excerpt_start_s"], it["real_side"]
        fo = it["foil"]
        rel_real = [c - start for c in meta[song]["clicks"] if start <= c < start + 10.0]
        fstart = fo["excerpt_start_s"]
        rel_foil = [c - fstart for c in meta[fo["song"]]["clicks"] if fstart <= c < fstart + 10.0]
        base_real, base_foil = (0.0, 11.5) if side == "first" else (11.5, 0.0)
        # 11 csv
        csvp = OUT / f"render_root/work/{pid}_{it['version']}.csv"
        rows = np.array([[float(x) for x in l.split(",")] for l in csvp.read_text().splitlines() if l and l[0].isdigit()])
        z = np.load(OUT / "controls/q50/finedance" / f"{song}__{it['version']}.npz")
        a0 = int(round(it["window_offset_s"] * 50))
        q = z["q50"][it["q_index"]][a0:a0 + 501].astype(float)
        r["11 csv"] = dict(rows=int(len(rows)), time_col_max_err_s=float(np.abs(rows[:, 0] - np.arange(len(rows)) / 50.0).max()), q50_slice_max_err_deg=float(np.abs(rows[:, 1:] - q).max()),
                           note="row k of the csv = q50 row (window_offset x 50 + k); t = k / 0.02 exactly: offset 0 ms against the q50 stage")
        # 12 rendered frames vs q50 joint speed
        vp = OUT / f"render_root/clips/{pid}_{it['version']}.mp4"
        fr = gray_frames(vp)
        tv, E = motion_energy(fr)
        sp = np.abs(np.diff(q, axis=0)).sum(1) * 50.0
        ref = np.interp(tv, (np.arange(len(sp)) + 0.5) / 50.0, sp)
        lag, cor = S.xcorr_lag_s(ref, E, 1 / 30.0, 0.4)
        r["12 rendered frames (render mp4)"] = dict(frames=int(len(fr)), lag_ms=1000 * lag, corr=cor, note="xcorr of frame-difference energy against q50 summed joint speed; positive = video later than the csv")
        pr = probe_json(vp, "-show_entries", "stream=codec_type,start_time,start_pts,time_base,nb_frames,duration")
        r["12b render container"] = pr["streams"]
        # 13 final clip
        cp = OUT / "clips_src" / f"{pid}.mp4"
        au = MB.load_mono(cp, S.SR)
        wavp = OUT / "work/wav" / f"{pid}.wav"
        wv = MB.load_mono(wavp, S.SR)
        cl = {}
        for nm, base, rel in (("real", base_real, rel_real), ("foil", base_foil, rel_foil)):
            exp = [base + c for c in rel]
            cl[nm] = dict(expected_s=exp, pre_encode_wav_ms=S.summarise(S.audio_click_offsets_ms(wv, exp)), decoded_mp4_ms=S.summarise(S.audio_click_offsets_ms(au, exp)),
                          decoded_mp4_per_click_ms=[None if np.isnan(x) else round(float(x), 4) for x in S.audio_click_offsets_ms(au, exp)])
        fr2 = gray_frames(cp)
        t2, E2 = motion_energy(fr2)
        vid = {}
        for nm, base, rel in (("real", base_real, rel_real), ("foil", base_foil, rel_foil)):
            m = (t2 >= base) & (t2 < base + 10.0)
            ref2 = np.interp(t2[m] - base, (np.arange(len(sp)) + 0.5) / 50.0, sp)
            lg, cr = S.xcorr_lag_s(ref2, E2[m], 1 / 30.0, 0.4)
            iso = [c for c in rel if all(abs(c - d) >= 1.5 for d in rel if d != c)]
            c, pk = S.offsets_ms(t2[m] - base, E2[m], [x for x in iso], 0.6)
            vid[nm] = dict(lag_vs_csv_ms=1000 * lg, corr=cr, video_energy_vs_click_centroid_ms=S.summarise(c), per_click_ms=[None if np.isnan(x) else round(float(x), 2) for x in c])
        pc = probe_json(cp, "-show_entries", "stream=codec_type,start_time,start_pts,time_base,nb_frames,duration:format=start_time,duration")
        r["13 final clip"] = dict(audio_clicks=cl, video=vid, container=pc, note="video_energy_vs_click: centroid of frame-difference energy within +-0.6 s of an isolated audio click time; the video series is speed-like so this includes the q50 latency")
        # 14 foil construction
        hr = wv[int(base_real * S.SR):int((base_real + 10) * S.SR)]
        hf = wv[int(base_foil * S.SR):int((base_foil + 10) * S.SR)]
        pr_, pf_ = click_positions(hr), click_positions(hf)
        if it["kind"] == "shifted":
            offs = []
            for t in pf_:
                m = [x for x in pr_ if abs((x - t) - fo["offset_s"]) < 0.01]   # click c: real rel x = c - start, foil rel t = c - start - offset, so x - t = offset
                if m:
                    offs.append((m[0] - t) * S.SR)
            r["14 shifted foil"] = dict(stated_offset_s=fo["offset_s"], clicks_real=len(pr_), clicks_foil=len(pf_), matched=len(offs), measured_offset_samples_minus_stated=[round(float(o - fo["offset_s"] * S.SR), 3) for o in offs],
                                        measured_offset_s=[round(float(o / S.SR), 6) for o in offs])
        else:
            r["14 different-song foil"] = dict(foil_song=fo["song"], foil_start_s=fo["excerpt_start_s"], clicks_foil=len(pf_), expected=len(rel_foil))
        res[pid] = r
        print(pid, "ok", flush=True)
    (OUT / "final.json").write_text(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    {"gen": cmd_gen, "chain": cmd_chain, "sine": cmd_sine, "items": cmd_items, "assemble": cmd_assemble, "final": cmd_final}[sys.argv[1]]()
