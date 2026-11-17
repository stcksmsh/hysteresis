"""WO45B S-B clip candidates (docs/A_RULES.md section 7 + addendum 1). Brain env. Manifest only: nothing is served, no answers file is opened.

    grammar_clips.py work SEED     8 s excerpts of held-out FineDance songs: human, A own / other / shuffled / constant controls, and a sharpness-matched V1 vs V2 pair -> grammar/look/work (csv, json, m4a)
    (render: RETARGET_ROOT=/secondary/hyst-data/body/grammar/look HYST_BATTERY_OK=1 scripts/body/retarget_render.sh)
    grammar_clips.py manifest      grammar/look/manifest.json (kind "set", order shuffled by seed, key kept)
Excerpt rule: 16 tokens (8 s) starting at a token multiple of 4 inside a kept window; excerpt mean RMS >= the song's own median RMS (0.5 s RMS of the audio); not inside the first or last 10 s of the song;
the same excerpt (song, window, token range) in every condition. One excerpt per song, N_EXCERPTS songs, seeded. V1/V2 pair: K samples per style copy, the pair with the smallest difference of the excerpt's mean realised sharpness.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import grammar_checks as GC  # noqa: E402
import grammar_data as GD  # noqa: E402

LOOK = GD.G / "look"
FD = Path("/secondary/hyst-data/datasets/finedance/data/finedance")
N_EX, EXC, K = 6, 16, 8
CONDS = ["H", "O", "T", "F", "K", "P", "Q"]          # human, own, other, shuffled, constant, V1 sample, V2 sample


def song_rms(seq):
    a = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", str(FD / "music_wav" / f"{seq}.wav"), "-f", "f32le", "-ac", "1", "-ar", "8000", "-"], capture_output=True, check=True).stdout, np.float32)
    n = len(a) // 4000
    return np.sqrt((a[:n * 4000].reshape(n, 4000) ** 2).mean(1))               # 0.5 s RMS


def realise(tok, var):
    import m3f_report as R
    import t1a2_realised as RE
    rows = GC.decode_rows(tok)
    _, q50 = RE.sim_one((rows.astype(float), None, var[:2]))
    return q50.astype(float), R.fk_points(q50.astype(float))[:, 5]


def choose(S, seed):
    """-> list of (start index into S.idx order, token start s)"""
    z = S.te.z
    rng = np.random.default_rng(seed)
    cand = [i for i in rng.permutation(len(S.te.z["code1"])) if z["dsid"][i] == 0 and str(z["key"][i]).split("__")[1] in ("V1", "V2")]
    out, used, cache = [], set(), {}
    for i in cand:
        g = str(z["group"][i])
        if g in used:
            continue
        seq = g.split("_", 1)[1]
        if seq not in cache:
            try:
                cache[seq] = song_rms(seq)
            except Exception:  # noqa: BLE001
                cache[seq] = None
        r = cache[seq]
        if r is None or len(r) < 80:
            continue
        med = np.median(r)
        t0 = int(z["win"][i]) * 40
        for s in rng.permutation(np.arange(4, 40 - EXC + 1, 4)):
            a = t0 + int(s)
            if a * 0.5 < 10 or (a + EXC) * 0.5 > len(r) * 0.5 - 10 or a + EXC > len(r):
                continue
            if r[a:a + EXC].mean() >= med:
                out.append((int(i), int(s)))
                used.add(g)
                break
        if len(out) >= N_EX:
            break
    return out


def cmd_work(seed):
    GC.worker_init()
    torch.set_num_threads(4)
    S = GC.Setup(seed)
    sel = choose(S, 45020)
    z = S.te.z
    S.idx = np.array([i for i, _ in sel])
    S.raw = z["ctl"][S.idx].astype(np.float64)
    n = len(S.idx)
    rng = np.random.default_rng(45021)
    HIST = GC.HIST
    own = S.raw
    other, shuf, const = own.copy(), own.copy(), own.copy()
    for k in range(n):
        c = np.flatnonzero((z["dsid"] == 0) & (z["group"] != z["group"][S.idx[k]]))
        other[k] = z["ctl"][rng.choice(c)]
        shuf[k, HIST:] = own[k, HIST + rng.permutation(40 - HIST)]
        blk = own[k, HIST:]
        v = GC.GT.valid_dims(blk)
        const[k, HIST:] = [blk[v[:, j], j].mean() if v[:, j].any() else 0.0 for j in range(GD.CD)]
        const[k, HIST:, 15:] = blk[:, 15:].max(0)
    W = LOOK / "work"
    W.mkdir(parents=True, exist_ok=True)
    import arm_sim
    meta = []
    gens = {c: S.generate(S.to_cn(r), seed * 100 + j) for j, (c, r) in enumerate((("O", own), ("T", other), ("F", shuf), ("K", const)))}
    ii = torch.from_numpy(S.idx)
    for k, (i, s) in enumerate(sel):
        key = str(z["key"][i])
        var0 = key.split("__")[1]
        g = str(z["group"][i])
        t0 = (int(z["win"][i]) * 40 + s) * 0.5
        qs, sharps = {}, {}
        # human: the stored realised q50 of this window
        zz = np.load(GD.B / "controls/q50/finedance" / f"{key}.npz")
        wi = int(np.flatnonzero(zz["win"] == int(z["win"][i]))[0])
        qs["H"] = (zz["q50"][wi].astype(float), var0)
        for c in ("O", "T", "F", "K"):
            tok = {a: gens[c][a][k].numpy() for a in gens[c]}
            qs[c] = (realise(tok, var0)[0], var0)
        # sharpness-matched V1 vs V2: K samples per style copy, same start, same controls
        import controls_lib as C
        pool = {}
        for cp in (0, 1):
            S.te.copy[ii[k]] = cp
            for j in range(K):
                t = S.generate(S.to_cn(own[k:k + 1]), seed * 1000 + 10 * k + j, idx=S.idx[k:k + 1])
                tok = {a: t[a][0].numpy() for a in t}
                q, lamp = realise(tok, GD.COPIES[cp])
                sh = C.raw_window(q, lamp)["sharp"][s:s + EXC]
                pool[(cp, j)] = (q, float(np.nanmean(sh)), tok["c1"])
        S.te.copy[ii[k]] = int(z["copy"][i])
        best = min(((abs(pool[(0, a)][1] - pool[(1, b)][1]), a, b) for a in range(K) for b in range(K)))
        qs["P"], qs["Q"] = (pool[(0, best[1])][0], "V1"), (pool[(1, best[2])][0], "V2")
        v1s, v2s = [pool[(0, a)][1] for a in range(K)], [pool[(1, a)][1] for a in range(K)]
        rq = own[k, s:s + EXC]
        sharps = dict(P=pool[(0, best[1])][1], Q=pool[(1, best[2])][1], abs_diff=best[0], matched_on="realised sharpness of the realised q50 of each candidate (token mean over the excerpt)",
                      requested_sharp_own_controls=float(rq[rq[:, 15] > 0, 10].mean()) if (rq[:, 15] > 0).any() else None, pool_realised_sharp_v1=v1s, pool_realised_sharp_v2=v2s,
                      pool_mean_v1=float(np.mean(v1s)), pool_mean_v2=float(np.mean(v2s)), n_pairs_searched=K * K, code1_tokens_differ_share_v1_vs_v2_sample0=float((pool[(0, 0)][2] != pool[(1, 0)][2]).mean()))
        wav = FD / "music_wav" / f"{g.split('_', 1)[1]}.wav"
        for c, (q, var) in qs.items():
            cid = f"S{k + 1:02d}{c}"
            ex = q[25 * s:25 * (s + EXC) + 1]
            (W / f"{cid}_{var}.csv").write_text(arm_sim.csv_text(ex, 50, name=f"{cid}_{var}"))
            (W / f"{cid}_{var}.json").write_text(json.dumps(dict(id=f"{cid}_{var}", clip=cid, variant=var, gates=dict(passed=True, note="A generated / human realised excerpt"), pick=dict(excerpt=k + 1, condition=c))))
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0:.3f}", "-t", f"{EXC * 0.5}", "-i", str(wav), "-ac", "2", "-ar", "48000", "-c:a", "aac", "-b:a", "192k", str(W / f"{cid}.m4a")], check=True)
        meta.append(dict(excerpt=k + 1, song=g, key=key, window=int(z["win"][i]), token_start=s, song_time_s=t0, v1_v2_matching=sharps))
    (LOOK / "excerpts.json").write_text(json.dumps(meta, indent=1))
    print("SB work", len(meta), "excerpts", flush=True)


def cmd_manifest():
    meta = json.loads((LOOK / "excerpts.json").read_text())
    man = []
    for m in meta:
        k = m["excerpt"]
        rng = np.random.default_rng(45030 + k)
        for group, conds in (("conditions", ["H", "O", "T", "F", "K"]), ("copy_style", ["P", "Q"])):
            order = list(rng.permutation(conds))
            files = [f"clips/S{k:02d}{c}_{'V2' if c == 'Q' else ('V1' if c == 'P' else m['key'].split('__')[1])}.mp4" for c in order]
            man.append(dict(id=f"E{k:02d}_{group}", kind="set", files=files, key=order, excerpt=k, song=m["song"], song_time_s=m["song_time_s"], genre="finedance"))
    (LOOK / "manifest.json").write_text(json.dumps(man, indent=1))
    print("manifest", len(man), flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    {"work": lambda: cmd_work(int(a[1])), "manifest": cmd_manifest}[a[0]]()
