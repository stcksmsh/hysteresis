"""WO41 T2, part 2 (docs/T1B_RULES.md sections 5-6): controls, realised simulation, per-dance measures. Brain env.

    t1b_t2b.py ctrl                         retrieval + random-chunk dances for the usable test songs -> t1b/t2/controls/<seq>.npz (seed-independent)
    t1b_t2b.py real SEED [--run DIR] [PROCS]  realised simulation (guard, spinal, limiter, servo, v2p) of human copies, model sample 0, both controls; gates on 3 x 20 s windows -> DIR/t2/real/<seq>.npz
    t1b_t2b.py measures SEED [--run DIR]    every per-dance measure -> DIR/t2/measures.json (per-song values kept)
"""
import json
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import t1b_t2 as T2  # noqa: E402
import t1b_t2_lib as L  # noqa: E402

OUT, TR = T2.OUT, T2.TR
SEED_CTRL, MCAND, W_TRANS = 36101, 8, 1.0
PRE = 150
JN = ("base_yaw", "shoulder", "elbow", "wrist_bend", "wrist_roll")


def sd_scale():
    return np.asarray(json.loads(Path("/secondary/hyst-data/body/t1a/scale.json").read_text())["sd"], np.float32)


def token_features(key, norm):
    """listener-free music feature of every token k >= 2: mean of the standardised 2105-wide cortex rows over the 50 frames ending at the decision frame 50 k - 25 -> (ntok, 2105) float32 (rows k < 2 are zero)"""
    x = np.load(OUT / "cortex" / f"{key}.npy", mmap_mode="r")
    n = len(x) // 50
    out = np.zeros((n, x.shape[1]), np.float32)
    c = np.zeros((1, x.shape[1]))
    for k in range(2, n):
        a, b = 50 * k - 75, 50 * k - 25
        if a < 0 or b > len(x):
            continue
        out[k] = np.clip((np.asarray(x[a:b], np.float32).mean(0) - norm[0]) / norm[1], -TR.CLIP_X, TR.CLIP_X)
    return out


def train_db(norm, max_seq=None):
    """database over the train split: music features (unique per seq, token), rows of the 4 copies: dict(feat (N, 2105) unit-norm, ref (N, 2) seq index / token, rows (4, N, 51, 5))"""
    cache = OUT / "t2" / "db.npz"
    if cache.exists():
        z = np.load(cache)
        return dict(feat=z["feat"].astype(np.float32), ref=z["ref"], rows=z["rows"], keys=list(z["keys"]))
    idx = TR.song_index()
    keys = sorted(k for k, v in idx.items() if v["split"] == "train")[:max_seq]
    feats, ref, rows = [], [], []
    for si, k in enumerate(keys):
        f = token_features(k, norm)
        zs = [np.load(T2.T0 / "seq" / "finedance" / f"{k}__{c}.npz") for c in TR.COPIES]
        nt = min(len(f), min(int(z["n_win"]) * 40 for z in zs))
        keep = np.arange(2, nt)
        if not len(keep):
            continue
        feats.append(f[keep])
        ref += [(si, int(t)) for t in keep]
        rows.append(np.stack([np.stack([np.asarray(z["targets"][50 * t:50 * t + 51], np.float32) for t in keep]) for z in zs]))
    feat = np.concatenate(feats)
    feat /= np.linalg.norm(feat, axis=1, keepdims=True) + 1e-9
    db = dict(feat=feat, ref=np.array(ref), rows=np.concatenate(rows, 1), keys=keys)
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez(cache, feat=feat.astype(np.float16), ref=db["ref"], rows=db["rows"], keys=np.array(keys))
    return db


def chain(db, music, rng, sd, use_music):
    """Viterbi over the dance tokens: candidates = MCAND nearest (cosine; random if not use_music) database tokens x 4 copies; unary = 1 - cos (0 for random), transition = W_TRANS x
    joint-space jump between the previous chunk's last row and the next chunk's first row (scaled by sd) -> rows (6001, 5)"""
    n = len(music)
    cand = []
    for i in range(n):
        if use_music:
            m = music[i] / (np.linalg.norm(music[i]) + 1e-9)
            s = db["feat"] @ m
            top = np.argpartition(-s, MCAND)[:MCAND]
            un = np.repeat(1 - s[top], 4)
        else:
            top = rng.integers(len(db["feat"]), size=MCAND)
            un = np.zeros(MCAND * 4)
        cand.append((np.repeat(top, 4), np.tile(np.arange(4), MCAND), un))
    unary = np.stack([c[2] for c in cand])
    first = lambda i: db["rows"][cand[i][1], cand[i][0], 0] / sd
    last = lambda i: db["rows"][cand[i][1], cand[i][0], -1] / sd
    trans = lambda i: W_TRANS * np.linalg.norm(last(i)[:, None] - first(i + 1)[None], axis=2)
    path = L.viterbi(unary, trans)
    rows = np.concatenate([db["rows"][cand[i][1][p], cand[i][0][p], :50] for i, p in enumerate(path)])
    return np.vstack([rows, rows[-1:]]).astype(np.float32), [(int(cand[i][0][p]), int(cand[i][1][p])) for i, p in enumerate(path)]


def cmd_ctrl():
    norm = TR.load_norm()
    sd = sd_scale()
    db = train_db(norm)
    d = OUT / "t2" / "controls"
    d.mkdir(parents=True, exist_ok=True)
    for key in T2.test_songs():
        if not T2.usable(key) or (d / f"{key}.npz").exists():
            continue
        music = token_features(key, norm)[T2.K0:T2.K1]
        r1, c1 = chain(db, music, np.random.default_rng(SEED_CTRL), sd, True)
        r2, c2 = chain(db, music, np.random.default_rng(SEED_CTRL + 1), sd, False)
        np.savez(d / f"{key}.npz", retrieval=r1, random=r2, retrieval_pick=np.array(c1), random_pick=np.array(c2))
        print("ctrl", key, flush=True)


# ---------------------------------------------------------------- realised simulation

def sim_full(args):
    """-> (gate passed, q50, dict(guard_share, limit_hit_share, speed_sat_share)) for rows (n, 5), pre-roll rows or None, variant 'V1' | 'V2'. As t1a2_realised.sim_one, plus limiter statistics."""
    rows, pre, var = args
    import dialstudy as D
    import make_arm_v2p as P
    import motornet as M
    import retarget as RT
    import retarget_limiter as FX
    import retarget_run as RR
    RR.patch_gates()
    K = RT.to_commands(np.zeros((1, 5)), var)[0]
    sh = np.zeros(5)
    sh[[0, 4]] = (rows[0] - K)[[0, 4]]
    pre = np.repeat(rows[:1], PRE, 0) if pre is None else pre
    G, gs = P.guard(np.concatenate([pre, rows]) - sh)
    S = M.spinal(G)
    q50, contacts = FX.simulate_goals(S)
    g = RR.gates_v2p(q50, contacts, gs)
    lo, hi = D.LO + D.CLIP_MARGIN, D.HI - D.CLIP_MARGIN
    hit = float(((S < lo) | (S > hi)).any(1).mean())
    tgt, tv, sat = S[0].copy(), np.zeros(5), 0
    for s in S:
        tgt, tv = FX.step(tgt, tv, s)
        sat += bool((np.abs(tv) >= 0.99 * D.LIM_V).any())
    return bool(g["passed"]), np.asarray(q50, np.float32), dict(guard_share=float(gs), limit_hit_share=hit, speed_sat_share=sat / len(S))


def gate_windows(rows, human_pre):
    """three 20 s windows of a 60 s dance: [(rows 2001, pre or None)]"""
    out = []
    for i in range(3):
        a = 2000 * i
        pre = human_pre if i == 0 else rows[a - PRE:a]
        out.append((rows[a:a + 2001].astype(float), None if pre is None else np.asarray(pre, float)))
    return out


def jobs_for(key, run):
    """list of (name, args list) for one song"""
    h = T2.human_window(key)
    gen = np.load(Path(run) / "t2" / "gen" / f"{key}.npz")
    ctl = np.load(OUT / "t2" / "controls" / f"{key}.npz")
    z = np.load(T2.T0 / "seq" / "finedance" / f"{key}__V1.npz")
    items = {}
    for c in TR.COPIES:
        zz = np.load(T2.T0 / "seq" / "finedance" / f"{key}__{c}.npz")
        items[f"human_{c}"] = (h[c]["rows"], np.asarray(zz["targets"][T2.K0 * 50 - PRE:T2.K0 * 50], np.float32), c[:2])
    items["model"] = (gen["rows_0"], None, "V1")
    items["retrieval"] = (ctl["retrieval"], None, "V1")
    items["random"] = (ctl["random"], None, "V1")
    jobs = []
    for name, (rows, pre, var) in items.items():
        jobs.append((name, "full", (rows.astype(float), None if pre is None else pre.astype(float), var)))
        for i, (r, p) in enumerate(gate_windows(rows, pre)):
            jobs.append((name, f"gate{i}", (r, p, var)))
    return jobs


def run_job(a):
    n, k, args = a
    ok, q, st = sim_full(args)
    return n, k, ok, q, st


def cmd_real(seed, run, procs):
    d = Path(run) / "t2" / "real"
    d.mkdir(parents=True, exist_ok=True)
    keys = [k for k in T2.test_songs() if T2.usable(k) and (Path(run) / "t2" / "gen" / f"{k}.npz").exists() and (OUT / "t2" / "controls" / f"{k}.npz").exists()]
    with mp.get_context("spawn").Pool(procs) as pool:
        for key in keys:
            if (d / f"{key}.npz").exists():
                continue
            res = pool.map(run_job, jobs_for(key, run))
            out = {}
            for n, k, ok, q, st in res:
                out[f"{n}|{k}|ok"] = ok
                out[f"{n}|{k}|stats"] = json.dumps(st)
                if k == "full":
                    out[f"{n}|q50"] = q
            np.savez(str(d / key) + ".tmp.npz", **out)
            Path(str(d / key) + ".tmp.npz").replace(d / f"{key}.npz")
            print("real", key, flush=True)


# ---------------------------------------------------------------- measures

def music_for(key, norm):
    """per-token music feature of the dance tokens, beats (s from dance start), ee token means, ear lane and layer-4 states over the dance frames"""
    lane = np.load(T2.T0 / "lanes" / f"{key}.npz")
    x = np.load(OUT / "cortex" / f"{key}.npy", mmap_mode="r")
    fr = slice(T2.K0 * 50, T2.K1 * 50)
    ear = np.asarray(x[fr, 2061:2105], np.float32)
    h4 = np.asarray(x[fr, 3 * 512:4 * 512], np.float32)
    beats = np.asarray(json.loads((OUT / "cortex" / "beats" / f"{key}.json").read_text())["beats"]) - T2.K0 * 0.5
    ee = np.asarray(lane["ee"])
    eet = np.array([ee[5 * k:5 * k + 5].mean() for k in range(T2.K0, T2.K1)])
    return token_features(key, norm)[T2.K0:T2.K1], beats[(beats >= 0) & (beats < 60)], eet, ear, h4


def post_of(rows):
    from scipy.signal import butter, filtfilt
    b, a = butter(2, 0.5 / 50.0)
    return filtfilt(b, a, rows, axis=0)


def dance_measures(q50, rows, tok, gest, mus, vig_centres, sd):
    """all per-dance numbers (realised q50 at 50 Hz for body measures; commanded rows at 100 Hz for tokens/posture)"""
    import jitter_diag as J
    import bdesc
    feat, beats, eet, ear, h4 = mus
    hp = bdesc.hand_points(q50.astype(float))
    sp = L.hand_speed(hp, 50.0)
    jit = J.all_joints(q50.astype(float), 50.0, JN)
    jerk, dirc = L.endpoint_jerk_dirchanges(hp, 50.0)
    tmove = np.hstack([rows[:-1].reshape(120, 50, 5).mean(1), np.abs(np.diff(rows, axis=0))[:, :].reshape(-1, 50, 5)[:120].mean(1)]) if len(rows) >= 6001 else None
    tmove = (tmove - tmove.mean(0)) / (tmove.std(0) + 1e-9)
    ss = {f"selfsim_{w}tok": L.selfsim_corr(feat, tmove, w) for w in (4, 16, 60)}
    post = post_of(rows)
    dp = np.linalg.norm(np.diff(post[::50], axis=0) / sd, axis=1)
    ph = bdesc.hand_points(post[:-1].astype(float))[:, 2].reshape(120, 50).mean(1)          # posture height: hand height (z up) of the posture-only trajectory, per token
    ev_on, ev_up = L.detect_events(ear)
    ev_sl = L.slow_changes(h4)
    vig = vig_centres[np.asarray(tok["v"])]
    return dict(joint_range=L.range_p5_p95(q50).tolist(), jitter={j: dict(jit[j]) for j in JN}, frozen_longest_s=L.frozen_longest_s(sp, 50.0), hand_jerk=jerk, hand_dir_changes_per_s=dirc,
                hand_speed_mean=float(sp.mean()), beat_alignment=L.beat_alignment(sp, 50.0, beats), ident_repeat=L.ident_repeat_share(tok["c1"], tok["c2"]),
                triples_per_min=L.triples_per_min(tok["c1"], tok["c2"], tok["v"], tok["p"], 1.0), approx_repeat=L.approx_repeat(gest),
                vigour_energy_corr=float(np.corrcoef(vig, eet)[0, 1]) if np.std(vig) > 0 and np.std(eet) > 0 else None, **ss,
                posture_height_energy_corr=float(np.corrcoef(ph, eet)[0, 1]) if np.std(ph) > 0 and np.std(eet) > 0 else None, posture_range=L.range_p5_p95(post).tolist(), posture_change_per_token=float(dp.mean()),
                event_onset=L.event_response(sp, 50.0, ev_on), event_energy=L.event_response(sp, 50.0, ev_up), event_slow=L.event_response(sp, 50.0, ev_sl),
                n_events=[int(len(ev_on)), int(len(ev_up)), int(len(ev_sl))],
                cmd_vs_real_rms=np.sqrt((((q50 - rows[::2][:len(q50)]) - (q50 - rows[::2][:len(q50)]).mean(0)) ** 2).mean(0)).tolist())


def cmd_measures(seed, run):
    import torch
    sd = sd_scale()
    voc = T2.vocab()
    norm = TR.load_norm()
    res = {}
    for f in sorted((Path(run) / "t2" / "real").glob("fd_*.npz")):
        key = f.stem
        r = np.load(f)
        gen = np.load(Path(run) / "t2" / "gen" / f"{key}.npz")
        ctl = np.load(OUT / "t2" / "controls" / f"{key}.npz")
        h = T2.human_window(key)
        mus = music_for(key, norm)
        entry = {}
        toks = {"model": ({k: gen[f"{k}_0"] for k in ("c1", "c2", "v", "p")}, gen["gest_0"], gen["rows_0"])}
        for c in TR.COPIES:
            toks[f"human_{c}"] = (h[c]["tok"], (h[c]["gest"] / sd).reshape(120, 50, 5), h[c]["rows"])
        for name in ("retrieval", "random"):                                       # controls carry rows only (no codes): token-code measures are None
            toks[name] = None
        for name in sorted({k.split("|")[0] for k in r.files}):
            q = r[f"{name}|q50"]
            gates = [bool(r[f"{name}|gate{i}|ok"]) for i in range(3)]
            st = json.loads(str(r[f"{name}|full|stats"]))
            if toks.get(name) is not None:
                tok, ges, rows = toks[name]
                entry[name] = dance_measures(q, rows, tok, ges, mus, voc["vig"], sd)
            else:
                rows = ctl[name]
                tok = dict(c1=np.zeros(120, int), c2=np.zeros(120, int), v=np.zeros(120, int), p=np.zeros((120, 1), int))
                ges = (rows[:-1].reshape(120, 50, 5) - post_of(rows)[:-1].reshape(120, 50, 5)) / sd
                m = dance_measures(q, rows, tok, ges, mus, voc["vig"], sd)
                for k in ("ident_repeat", "triples_per_min", "vigour_energy_corr"):
                    m[k] = None                                                    # no token codes for controls
                entry[name] = m
            entry[name].update(gate_share=float(np.mean(gates)), **st)
        res[key] = entry
        print("measures", key, flush=True)
    (Path(run) / "t2" / "measures.json").write_text(json.dumps(res))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "ctrl":
        cmd_ctrl()
    else:
        seed = int(a[1])
        run = a[a.index("--run") + 1] if "--run" in a else str(OUT / "e1" / f"seed{seed}")
        if a[0] == "real":
            cmd_real(seed, run, int(a[-1]) if a[-1].isdigit() and a[-2] != "--run" and len(a) > 2 else 6)
        else:
            cmd_measures(seed, run)
