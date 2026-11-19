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
    PRE, WIN_ROWS = 150, 2000
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


def measure(t, X, clicks, lo, hi):
    """per channel: centroid and parabolic-peak offsets (ms) of the clicks inside [lo, hi]; main = the channel with the largest peak-to-peak"""
    ck = [c for c in clicks if lo <= c <= hi]
    X = np.atleast_2d(X.T).T if X.ndim == 1 else X
    res = {}
    for ch in range(X.shape[1]):
        c, p = S.offsets_ms(t, X[:, ch], ck)
        res[ch] = dict(ptp=float(np.ptp(X[:, ch])), centroid=S.summarise(c), peak=S.summarise(p), per_impulse_centroid_ms=[None if np.isnan(x) else round(float(x), 3) for x in c], clicks=ck)
    main = max(res, key=lambda k: res[k]["ptp"])
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
                res["1b loaded motion (30 Hz, family joints' rotation angle)"] = dict(**measure(np.arange(len(m)) / 30.0, ang[:, None], clicks, 0.75, len(m) / 30 - 0.75), rate=30)
                for k, (t, X, rate, note) in st.items():
                    res[k] = dict(**measure(t, X, clicks, 0.75, t[-1] - 0.75), rate=rate, note=note)
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
                assert np.allclose(q50, z["q50"][wi], atol=1e-3), "replicated window differs from controls_run.sim_file"
                lo, hi = 20.0 * w, 20.0 * w + 20.0
                for k, (t, X, rate, note) in ws.items():
                    res[k] = dict(**measure(t, X, clicks, max(lo, t[0]) + 0.75, min(hi, t[-1]) - 0.75), rate=rate, note=note)
                    if k.startswith("9"):
                        tl = t[1:]
                        sp = np.linalg.norm(np.diff(X, axis=0), axis=1) * 50
                        res["9b lamp speed (50 Hz)"] = dict(**measure(tl, sp[:, None], clicks, lo + 0.75, hi - 0.75), rate=50, note="the WO52 signal")
                # 10 raw FK joints (WO53 B)
                R = BL.local_rots(m.astype(float))
                pos = BL.fk(R, m[:, :3].astype(float))
                for nm, j in (("right wrist", 21), ("left wrist", 20), ("right ankle", 8), ("left ankle", 7), ("pelvis", 0), ("head", 15)):
                    sp = np.linalg.norm(np.diff(pos[:, j], axis=0), axis=1) * 30
                    res[f"10 raw FK speed {nm} (30 Hz)"] = dict(**measure(np.arange(1, len(m)) / 30.0 - 0.5 / 30, sp[:, None], clicks, 0.75, len(m) / 30 - 0.75), rate=30, note="diff between frames k-1 and k stamped at the midpoint")
                allres[tag] = dict(window=w, stages=res)
                print(tag, "ok", flush=True)
            except Exception as e:  # noqa: BLE001
                allres[tag] = dict(error=f"{type(e).__name__}: {e}")
                print(tag, "FAILED", e, flush=True)
    (OUT / "chain.json").write_text(json.dumps(allres, indent=1, default=float))
    print("chain done")


if __name__ == "__main__":
    {"gen": cmd_gen, "chain": cmd_chain}[sys.argv[1]]()
