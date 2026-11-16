"""WO44 run (docs/JOIN_RULES.md). Brain env.   T1B_POST=2 python -u join_run.py [PROCS]
Builds every material x method (commanded rows), simulates the realised stage, measures; resumable per song -> /secondary/hyst-data/body/join/{rows,q50}/<song>.npz, measures.json."""
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import join_lib as J  # noqa: E402
import t1b_t2 as T2  # noqa: E402
import t1b_t2b as B  # noqa: E402

OUT = Path("/secondary/hyst-data/body/join")
JN = B.JN
COPIES = T2.TR.COPIES


def songs():
    idx = T2.TR.song_index()
    return [(k, idx[k]["split"]) for k in sorted(idx) if idx[k]["split"] in ("validation", "test") and T2.usable(k)]


def chunk_tokens(db, keys, pick, cache):
    """(db index, copy) picks -> token dict (c1, c2, v, p) of the picked train tokens"""
    c1, c2, v, p = [], [], [], []
    for i, c in pick:
        si, t = db["ref"][i]
        f = (keys[si], COPIES[c])
        if f not in cache:
            cache[f] = np.load(T2.OUT / "tokens" / f"{f[0]}__{f[1]}.npz")
        z = cache[f]
        c1.append(z["code1"][t]), c2.append(z["code2"][t]), v.append(z["vbin"][t]), p.append(np.asarray(z["pent"][t]).reshape(-1))
    return dict(c1=np.array(c1), c2=np.array(c2), v=np.array(v), p=np.array(p))


def timed(f):
    t = time.perf_counter()
    r = f()
    return r, time.perf_counter() - t


def build_song(key, split, ctx):
    """-> (dict name -> (rows (6001, 5), variant), dict name -> build seconds)"""
    vq, sd, voc, norm, db, _ = ctx
    h = T2.human_window(key)
    out, cost = {}, {}
    for c in COPIES:
        out[f"H|{c}"] = (h[c]["rows"], c[:2])
        for m in ("blocks", "overlap"):
            out[f"HJ|{m}|{c}"] = (J.build_rows(h[c]["tok"], h[c]["post0"], voc, vq, sd, m), c[:2])
    post0 = h["V1"]["post0"]
    cf = OUT / "controls" / f"{key}.npz"
    if not cf.exists():                                                            # test songs reuse E1's stored controls (identical procedure and seeds for the rest)
        ef = T2.OUT / "t2" / "controls" / f"{key}.npz"
        if ef.exists():
            z = np.load(ef)
            d = dict(retrieval=z["retrieval"], random=z["random"], retrieval_pick=z["retrieval_pick"], random_pick=z["random_pick"])
        else:
            music = B.token_features(key, norm)[T2.K0:T2.K1]
            r1, c1 = B.chain(db, music, np.random.default_rng(B.SEED_CTRL), sd, True)
            r2, c2 = B.chain(db, music, np.random.default_rng(B.SEED_CTRL + 1), sd, False)
            d = dict(retrieval=r1, random=r2, retrieval_pick=np.array(c1), random_pick=np.array(c2))
        cf.parent.mkdir(parents=True, exist_ok=True)
        np.savez(cf, **d)
    ctl = np.load(cf)
    cache = {}
    for name, short in (("retrieval", "RT"), ("random", "RN")):
        pick = ctl[f"{name}_pick"]
        ch = np.stack([db["rows"][c, i] for i, c in pick])                         # (120, 51, 5) raw chunks
        out[f"{short}|raw"] = (J.concat_raw(ch), "V1")
        assert np.allclose(out[f"{short}|raw"][0], ctl[name], atol=1e-3), "stored control != rebuilt raw concatenation"
        out[f"{short}|ramp"], cost[f"{short}|ramp"] = timed(lambda: (J.concat_ramp(ch), "V1"))
        tok = chunk_tokens(db, db["keys"], pick, cache)
        for m in ("blocks", "overlap"):
            out[f"{short}|{m}"], cost[f"{short}|{m}"] = timed(lambda: (J.build_rows(tok, post0, voc, vq, sd, m), "V1"))
    gf = Path(T2.OUT / "e1" / "seed41101" / "t2" / "gen" / f"{key}.npz")
    if split == "test" and gf.exists():
        g = np.load(gf)
        tok = {k: g[f"{k}_0"] for k in ("c1", "c2", "v", "p")}
        for m in ("blocks", "overlap"):
            out[f"M|{m}"], cost[f"M|{m}"] = timed(lambda: (J.build_rows(tok, post0, voc, vq, sd, m), "V1"))
        assert np.array_equal(out["M|blocks"][0], g["rows_0"]), "A1 != E1 stored model rows"
    return out, cost


def sim(a):
    ok, q, st = B.sim_full(a)
    return q


def measure(q50, rows, sd=None):
    import bdesc
    import jitter_diag as JD
    import t1b_t2_lib as L
    import v3_lib as V
    q = q50.astype(float)
    hp = bdesc.hand_points(q)
    sp = L.hand_speed(hp, 50.0)
    lamp = V.pos_measures(hp, 50.0)
    jit = JD.all_joints(q, 50.0, JN)
    jerk, _ = L.endpoint_jerk_dirchanges(hp, 50.0)
    d = q - rows[::2][:len(q)]
    return dict(lamp_p_gt3=lamp["p_gt3"], lamp_p_gt6=lamp["p_gt6"], joint_p_gt3={j: jit[j]["p_gt3"] for j in JN}, joint_mean_p_gt3=float(np.mean([jit[j]["p_gt3"] for j in JN])),
                hand_jerk=jerk, frozen_share=float((sp < 0.05).mean()), cmd_vs_real_rms=float(np.sqrt(((d - d.mean(0)) ** 2).mean(0)).mean()))


def main(procs):
    import torch
    import t1a2_train as TR2
    torch.set_num_threads(1)
    vq = TR2.make("B")
    vq.load_state_dict(torch.load("/secondary/hyst-data/body/t1a2/runB/best.pt"))
    vq.eval()
    sd = B.sd_scale()
    voc, norm = T2.vocab(), T2.TR.load_norm()
    db = B.train_db(norm)
    ctx = (vq, sd, voc, norm, db, None)
    for d in ("rows", "q50"):
        (OUT / d).mkdir(parents=True, exist_ok=True)
    mf = OUT / "measures.json"
    res = json.loads(mf.read_text()) if mf.exists() else {}
    with mp.get_context("spawn").Pool(procs) as pool:
        for key, split in songs():
            if key in res:
                continue
            t = time.time()
            built, cost = build_song(key, split, ctx)
            names = list(built)
            qs = pool.map(sim, [(built[n][0].astype(float), None, built[n][1]) for n in names])
            np.savez_compressed(OUT / "rows" / f"{key}.npz", **{n: built[n][0] for n in names})
            np.savez_compressed(OUT / "q50" / f"{key}.npz", **dict(zip(names, qs)))
            res[key] = dict(split=split, cond={n: measure(q, built[n][0]) for n, q in zip(names, qs)}, build_s=cost)
            mf.write_text(json.dumps(res))
            print(key, split, len(names), "conditions", round(time.time() - t), "s", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 6)
