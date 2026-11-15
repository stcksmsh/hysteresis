"""WO41 T2 driver (docs/T1B_RULES.md section 6). Brain env.

    t1b_t2.py gen SEED [--run DIR] [--nsamp 8]       free-running dances (60 s from 10 s) for every FineDance test song -> DIR/t2/gen/<seq>_s<i>.npz
    t1b_t2.py swap SEED [--run DIR]                  true vs 3 tempo-matched swapped-music likelihoods + 2 s history truncation -> DIR/t2/swap.json
DIR defaults to t1b/e1/seed<SEED>. Dance = tokens 20..139 (10 s .. 70 s); the listener and planner run from song start (token 0).
"""
import json
import sys
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import t1b_model as M  # noqa: E402
import t1b_train as TR  # noqa: E402
import t1b_t2_lib as L  # noqa: E402

OUT = TR.OUT
T0 = Path("/secondary/hyst-data/body/t0")
K0, K1 = 20, 140                                            # dance tokens 20..139
NTOK = K1
FR = 100 * NTOK // 2                                        # 7000 frames of music needed
NUC = 0.9
SEED_SWAP, SEED_GEN = 36201, 36501


def vocab():
    v = np.load(OUT / "vocab.npz")
    return dict(vig=v["vig_centres"], post=[v["post_centres"]] + ([v["post_centres2"]] if "post_centres2" in v.files else []))


def load_model(run):
    m = TR.make_model(0)
    m.load_state_dict(torch.load(Path(run) / "best.pt"))
    return m.eval()


def cortex_window(key, norm, frames=FR):
    x = np.load(OUT / "cortex" / f"{key}.npy", mmap_mode="r")[:frames].astype(np.float32)
    x = np.clip((x - norm[0]) / norm[1], -TR.CLIP_X, TR.CLIP_X)
    if len(x) < frames:
        x = np.concatenate([x, np.zeros((frames - len(x), x.shape[1]), np.float32)])
    return torch.from_numpy(x.reshape(frames // 2, 2, -1).mean(1))[None]            # (1, frames/2, 2105)


def read_steps(st, ntok):
    """listener states (1, T50, 256) -> (1, ntok, 256): token k reads step 25 k - 13 (zeros before the first step)"""
    idx = torch.arange(ntok) * 25 - M.LAG
    out = st[:, idx.clamp(min=0)]
    out[:, idx < 0] = 0
    return out


def nucleus(logits, p, gen):
    pr = torch.softmax(logits, -1)
    s, i = pr.sort(-1, descending=True)
    keep = (s.cumsum(-1) - s) < p
    s = s * keep
    s = s / s.sum(-1, keepdim=True)
    return i.gather(-1, torch.multinomial(s, 1, generator=gen))[:, 0]


@torch.no_grad()
def generate(model, lis, gen, p=NUC):
    """free-running planner: lis (B, ntok, 256) -> dict c1, c2, v, p (B, ntok[, S]) sampled with nucleus p on every head, the previous sampled token fed back"""
    pl = model.planner
    B, N = lis.shape[:2]
    st, prev = pl.zero_state(B), None
    out = dict(c1=[], c2=[], v=[], p=[])
    for k in range(N):
        f, st = pl.forward_step(st, lis[:, k], prev)
        lg = pl.logits(f, None)
        c1 = nucleus(lg["c1"], p, gen)
        c2 = nucleus(pl.logits(f, c1)["c2"], p, gen)
        v = nucleus(lg["v"], p, gen)
        p1 = nucleus(lg["p"][0], p, gen)
        ps = [p1]
        if len(pl.n_post) > 1:
            ps.append(nucleus(pl.logits(f, c1, torch.stack(ps, 1))["p"][1], p, gen))
        ps = torch.stack(ps, 1)
        prev = (c1, c2, v, ps, torch.ones(B, dtype=torch.bool))
        for kk, val in zip(("c1", "c2", "v", "p"), (c1, c2, v, ps)):
            out[kk].append(val)
    return {k: torch.stack(v, 1) for k, v in out.items()}


def decode_rows(tok, post0, voc, vq, sd):
    """tokens of the dance (ntok = 120): c1, c2, v (n,), p (n, S) -> commanded rows (6001, 5) degrees = pchip(posture knots) + decoded gesture, and the scaled gestures (n, 50, 5)"""
    from scipy.interpolate import PchipInterpolator
    n = len(tok["c1"])
    c1, c2 = torch.as_tensor(tok["c1"]).long(), torch.as_tensor(tok["c2"]).long()
    zq = vq.vq.vq1.cb[c1] + vq.vq.vq2.cb[c2]
    a_n = torch.as_tensor(voc["vig"][np.asarray(tok["v"])], dtype=torch.float32)
    ges = []
    with torch.no_grad():
        for a in range(0, n, 40):
            ges.append(vq.dec(zq[a:a + 40][None], a_n[a:a + 40][None])[0].numpy())
    g = np.concatenate(ges) * sd                                                  # (n * 50, 5) degrees
    d = sum(voc["post"][i][np.asarray(tok["p"])[:, i]] for i in range(np.asarray(tok["p"]).shape[1]))
    knots = post0 + np.vstack([np.zeros((1, 5)), np.cumsum(d, 0)])
    post = PchipInterpolator(np.arange(n + 1) * 50, knots, axis=0)(np.arange(n * 50 + 1))
    rows = post.copy()
    rows[:-1] += g
    rows[-1] += g[-1]
    return rows.astype(np.float32), (g / sd).reshape(n, 50, 5).astype(np.float32)


def test_songs(split="test"):
    return sorted(k for k, v in TR.song_index().items() if v["split"] == split)


def human_window(key):
    """per copy: rows (6001, 5) targets, posture row at token 20, tokens dict of the dance (tokens 20..139), ok mask"""
    out = {}
    for c in TR.COPIES:
        z = np.load(T0 / "seq" / "finedance" / f"{key}__{c}.npz")
        t = np.load(OUT / "tokens" / f"{key}__{c}.npz")
        sl = slice(K0, K1)
        out[c] = dict(rows=np.asarray(z["targets"][K0 * 50:K1 * 50 + 1], np.float32), post0=np.asarray(z["posture"][K0 * 50], np.float64),
                      tok=dict(c1=t["code1"][sl], c2=t["code2"][sl], v=t["vbin"][sl], p=t["pent"][sl].reshape(len(t["pent"][sl]), -1)), ok=t["ok"][sl], n=len(t["code1"]),
                      gest=np.asarray(z["gesture"][K0 * 50:K1 * 50], np.float32))
    return out


def usable(key):
    """a test song gives a dance if its audio covers 70 s and its token files cover tokens 0..139 (the T0 gate does not decide: generation is free-running, the human reference keeps all rows)"""
    if np.load(OUT / "cortex" / f"{key}.npy", mmap_mode="r").shape[0] < FR:
        return False
    return min(len(np.load(OUT / "tokens" / f"{key}__{c}.npz")["code1"]) for c in TR.COPIES) >= K1


def cmd_gen(seed, run, nsamp):
    import t1a2_train as TR2
    torch.set_num_threads(4)
    model = load_model(run)
    vq = TR2.make("B")
    vq.load_state_dict(torch.load("/secondary/hyst-data/body/t1a2/runB/best.pt"))
    vq.eval()
    sd = np.asarray(json.loads(TR.Path("/secondary/hyst-data/body/t1a/scale.json").read_text())["sd"], np.float32)
    voc, norm = vocab(), TR.load_norm()
    (Path(run) / "t2" / "gen").mkdir(parents=True, exist_ok=True)
    gen = torch.Generator().manual_seed(SEED_GEN + seed)
    for key in test_songs():
        if not usable(key):
            continue
        f = Path(run) / "t2" / "gen" / f"{key}.npz"
        if f.exists():
            continue
        with torch.no_grad():
            st, _ = model.listener(cortex_window(key, norm))
        lis = read_steps(st, NTOK).repeat(nsamp, 1, 1)
        tok = generate(model, lis, gen)
        hw = human_window(key)["V1"]
        res = {}
        for i in range(nsamp):
            t = {k: v[i, K0:K1].numpy() for k, v in tok.items()}
            rows, g = decode_rows(t, hw["post0"], voc, vq, sd)
            for k, v in t.items():
                res[f"{k}_{i}"] = v
            res[f"rows_{i}"], res[f"gest_{i}"] = rows, g
        np.savez(str(f) + ".tmp.npz", **res)
        Path(str(f) + ".tmp.npz").replace(f)
        print("gen", key, flush=True)


def tempo_bpm(key):
    b = json.loads((OUT / "cortex" / "beats" / f"{key}.json").read_text())
    return 60.0 / b["ibi_median"] if b.get("ibi_median") else None


def partners(key, pool, bpm, rng, n=3):
    """seeded: up to n partners from `pool` (validation first) with tempo within 5 %, then half / double tempo -> (list, how many by half/double)"""
    near = [k for k in pool if k != key and bpm[k] and abs(bpm[k] / bpm[key] - 1) <= 0.05]
    pick = list(rng.permutation(near)[:n])
    hd = 0
    if len(pick) < n:
        alt = [k for k in pool if k != key and k not in pick and bpm[k] and (abs(bpm[k] / (2 * bpm[key]) - 1) <= 0.05 or abs(bpm[k] / (0.5 * bpm[key]) - 1) <= 0.05)]
        extra = list(rng.permutation(alt)[:n - len(pick)])
        hd = len(extra)
        pick += extra
    return [str(p) for p in pick], hd


@torch.no_grad()
def teacher_ll(model, lis, toks, ok):
    """mean head cross-entropy per ok token (nats) over the dance tokens 20..139, the 4 copies pooled; lis (1, NTOK, 256), toks dict of (4, NTOK), ok (4, NTOK) float"""
    ce, _, _ = M.run_window(model, lis.repeat(4, 1, 1), toks, model.planner.zero_state(4), None)
    tot = sum(v for v in ce.values())[:, K0:K1]
    w = ok[:, K0:K1]
    return float((tot * w).sum() / w.sum().clamp_min(1))


def full_tokens(key):
    cs, _ = TR.load_tokens(key)
    n = NTOK
    tok = {k: torch.from_numpy(np.stack([c[k][:n] for c in cs])).long() for k in ("c1", "c2", "v", "p")}
    return tok, torch.from_numpy(np.stack([c["ok"][:n] for c in cs]).astype(np.float32))


@torch.no_grad()
def truncated_lis(model, x50, hist_s=2.0):
    """listener state read by each token when the listener only heard the last hist_s seconds (zero state at the start of that stretch)"""
    n = int(hist_s * 50)
    xs, zero = [], []
    for k in range(NTOK):
        j = 25 * k - M.LAG
        if j < 0:
            zero.append(k)
            xs.append(torch.zeros(n, x50.shape[-1]))
        else:
            seg = x50[0, max(0, j + 1 - n):j + 1]
            xs.append(torch.cat([torch.zeros(n - len(seg), x50.shape[-1]), seg]) if len(seg) < n else seg)
    st, _ = model.listener(torch.stack(xs))
    lis = st[:, -1][None].clone()
    lis[:, zero] = 0
    return lis


def cmd_swap(seed, run):
    torch.set_num_threads(4)
    model = load_model(run)
    norm = TR.load_norm()
    idx = TR.song_index()
    songs = [k for k in test_songs() if usable(k)]
    val = [k for k, v in idx.items() if v["split"] == "validation" and np.load(OUT / "cortex" / f"{k}.npy", mmap_mode="r").shape[0] >= FR]
    bpm = {k: tempo_bpm(k) for k in set(songs) | set(val)}
    rng = np.random.default_rng(SEED_SWAP)                                         # same partners for every model seed (the seed is in the rules, not the run)
    res = []
    for key in songs:
        toks, ok = full_tokens(key)
        if ok[:, K0:K1].sum() == 0:
            continue
        x = cortex_window(key, norm)
        with torch.no_grad():
            st, _ = model.listener(x)
        true = teacher_ll(model, read_steps(st, NTOK), toks, ok)
        pk, hd = partners(key, val, bpm, rng)
        sw = []
        for q in pk:
            with torch.no_grad():
                sq, _ = model.listener(cortex_window(q, norm))
            sw.append(teacher_ll(model, read_steps(sq, NTOK), toks, ok))
        tr = teacher_ll(model, truncated_lis(model, x), toks, ok)
        res.append(dict(song=key, bpm=bpm[key], partners=pk, half_double=hd, true=true, swapped=sw, diff=(float(np.mean(sw)) - true) if sw else None, truncated=tr, trunc_minus_true=tr - true))
        print("swap", key, res[-1]["diff"], flush=True)
    d = [r["diff"] for r in res if r["diff"] is not None]                         # log-likelihood gap = (mean swapped NLL) - (true NLL) > 0 when the true music fits better
    m, lo, hi = L.bootstrap_mean_ci(d)
    out = dict(songs=res, n_songs=len(res), n_with_partners=len(d), n_no_partner=len(res) - len(d), n_half_double=int(sum(r["half_double"] for r in res)),
               mean_gap_nats=m, ci95=[lo, hi], stop_swapped=bool(lo <= 0 <= hi), mean_trunc_minus_true=float(np.mean([r["trunc_minus_true"] for r in res])))
    (Path(run) / "t2").mkdir(parents=True, exist_ok=True)
    (Path(run) / "t2" / "swap.json").write_text(json.dumps(out, indent=1))
    print({k: v for k, v in out.items() if k != "songs"})


if __name__ == "__main__":
    a = sys.argv[1:]
    seed = int(a[1])
    run = a[a.index("--run") + 1] if "--run" in a else str(OUT / "e1" / f"seed{seed}")
    if a[0] == "gen":
        cmd_gen(seed, run, int(a[a.index("--nsamp") + 1]) if "--nsamp" in a else 8)
    else:
        cmd_swap(seed, run)
