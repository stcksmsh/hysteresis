"""WO45B A checks (docs/A_RULES.md section 6 + addendum 1). Brain env. No training.

    grammar_checks.py run SEED [PROCS]     all checks for one trained seed -> grammar/checks/seed<SEED>.json   (resumable per check group)
Measures per token (realised trajectory): vigour, height, sharpness, pause probability, direction z, accent centre of mass; per window: direction-change rate, base-rotation speed.
Direction-change rate = times per second the lamp velocity direction turns by more than 90 degrees over 0.2 s (speed > 0.05 m/s at both ends). Base-rotation speed = RMS of d(base yaw)/dt (deg/s).
"""
import json
import os
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import grammar_data as GD  # noqa: E402
import grammar_model as GM  # noqa: E402
import grammar_train as GT  # noqa: E402

G = GD.G
OUT = G / "checks"
HIST, NB, SEED_START, SEED_BOOT = 4, 2000, 45003, 45002
MEAS = ["vigour", "height", "sharp", "pause", "dirz", "acccom", "dirchg", "basespeed"]
CTLS = ["vigour", "height", "accent", "sharp", "direction", "pause"]
NSAMP = 2
_W = {}


def worker_init():
    torch.set_num_threads(1)
    import t1b_tokens as TK
    voc = np.load(G / "vocab.npz")
    _W["vq"], _W["voc"] = TK.load_vq(), {k: voc[k] for k in voc.files}
    _W["sd"] = np.asarray(json.loads(GD.SCALE.read_text())["sd"], np.float32)
    _W["norm"] = json.loads((GD.B / "controls/norm.json").read_text())


def decode_rows(tok, sd=None, voc=None, vq=None, stage2=True):
    """tok: c1, c2, v, p1, p2 (40,) -> commanded rows (2001, 5) deg: pchip(window-relative absolute posture knots at token centres) + A1 gesture (one 40-token decoder window)"""
    from scipy.interpolate import PchipInterpolator
    sd, voc, vq = sd if sd is not None else _W["sd"], voc or _W["voc"], vq or _W["vq"]
    c1, c2 = torch.as_tensor(np.asarray(tok["c1"])).long(), torch.as_tensor(np.asarray(tok["c2"])).long()
    zq = vq.vq.vq1.cb[c1] + (vq.vq.vq2.cb[c2] if stage2 else 0)
    a_n = torch.as_tensor(voc["vig_centres"][np.asarray(tok["v"])], dtype=torch.float32)
    with torch.no_grad():
        g = vq.dec(zq[None], a_n[None])[0].numpy() * sd
    post = voc["post_mu"] + voc["post_sd"] * (voc["post_c1"][np.asarray(tok["p1"])] + voc["post_c2"][np.asarray(tok["p2"])])
    x = np.concatenate([[0], np.arange(40) * 50 + 25, [2000]])
    knots = np.vstack([post[:1], post, post[-1:]])
    rows = PchipInterpolator(x, knots, axis=0)(np.arange(2001))
    rows[:-1] += g
    rows[-1] += g[-1]
    return rows


def ctl_measures(raw):
    """raw 18-vectors (..., 18) -> (..., 6): vigour, height, sharp (nan undefined), pause, dirz (nan undefined), accent centre of mass (nan if flat/undefined)"""
    r = np.asarray(raw, float)
    pat = r[..., 2:10]
    com = (pat * np.arange(8)).sum(-1) / np.maximum(pat.sum(-1), 1e-9)
    return np.stack([r[..., 0], r[..., 1], np.where(r[..., 15] > 0, r[..., 10], np.nan), r[..., 14], np.where(r[..., 16] > 0, r[..., 13], np.nan), np.where(r[..., 17] > 0, com, np.nan)], -1)


def sim_job(a):
    """(tokens dict, var) -> realised measures. Returns dict(ctl (40,18), dirchg, basespeed, p_gt3, frozen_any, frozen_frames, joint_p_gt3) or None on failure"""
    tok, var = a
    try:
        import bdesc
        import controls_lib as C
        import jitter_diag as J
        import m3f_report as R
        import t1a2_realised as RE
        import v3_lib as V
        from t1a_eval import JN
        rows = decode_rows(tok)
        _, q50 = RE.sim_one((rows.astype(float), None, var[:2]))
        q = q50.astype(float)
        lamp = R.fk_points(q)[:, 5]
        c = C.finalise(C.raw_window(q, lamp), _W["norm"], version=2)["ctl"]
        v = np.gradient(lamp, axis=0) * C.FS
        sp = np.linalg.norm(v, axis=1)
        k = 10
        cos = (v[:-k] * v[k:]).sum(1) / np.maximum(sp[:-k] * sp[k:], 1e-9)
        turn = (cos < 0) & (sp[:-k] > 0.05) & (sp[k:] > 0.05)
        dirchg = float((np.diff(turn.astype(int)) == 1).sum()) / (len(lamp) / C.FS)
        base = float(np.sqrt(((np.gradient(q[:, 0]) * C.FS) ** 2).mean()))
        pm = V.pos_measures(bdesc.hand_points(q), 50.0)
        d = np.diff(np.concatenate([[0], (sp < 0.05).astype(np.int8), [0]]))
        runs = np.flatnonzero(d == -1) - np.flatnonzero(d == 1)
        fr = runs[runs > 3 * C.FS]
        jit = J.all_joints(q, 50.0, JN)
        jm = float(np.mean([jit[j]["p_gt3"] for j in jit])) if jit else float("nan")
        return dict(ctl=c, dirchg=dirchg, basespeed=base, p_gt3=float(pm["p_gt3"]), frozen_any=bool(len(fr)), frozen_frames=float(fr.sum()) / len(sp), joint_p_gt3=jm)
    except Exception as e:  # noqa: BLE001
        return dict(error=repr(e))


# ------------------------------------------------------------------ setup


class Setup:
    def __init__(self, seed):
        torch.set_num_threads(2)
        self.stats = dict(np.load(G / "stats.npz"))
        self.voc = json.loads((G / "vocab.json").read_text())
        self.model = GM.Grammar(n_genre=len(self.voc["genres"]))
        self.model.load_state_dict(torch.load(G / "runs" / f"seed{seed}" / "best.pt"))
        self.model.eval()
        self.gm, self.gs = self.stats["global_mean"], np.maximum(self.stats["global_sd"], 1e-3)
        self.seed = seed
        tr = GD.load("train")
        raw = tr["ctl"].reshape(-1, GD.CD).astype(np.float64)
        v = GD.valid_mask(raw)
        self.q = {j: np.percentile(raw[v[:, j], j], [10, 90]) for j in (0, 1, 10, 14)}
        self.tr_sd = raw.std(0)
        te = GT.Data(("validation", "test"), self.stats, self.voc)
        self.te = te
        z = te.z
        rng = np.random.default_rng(SEED_START)
        pick = []
        for dsid, n in ((0, 100), (1, 50), (2, 25), (3, 25)):
            cand = rng.permutation(np.flatnonzero(z["dsid"] == dsid))
            cnt = {}
            got = []
            for i in cand:
                g = str(z["group"][i])
                if cnt.get(g, 0) < 2:
                    cnt[g] = cnt.get(g, 0) + 1
                    got.append(i)
                if len(got) >= n:
                    break
            pick += got
        self.idx = np.array(sorted(pick))[:int(os.environ.get("HYST_CHK_N", 10 ** 9))]
        self.groups = z["group"][self.idx]
        self.raw = z["ctl"][self.idx].astype(np.float64)

    def to_cn(self, raw):
        cn = (raw - self.gm) / self.gs
        cn = np.where(GT.valid_dims(raw), cn, 0.0)
        cn[..., 15:] = raw[..., 15:]
        return torch.from_numpy(cn.astype(np.float32))

    @torch.no_grad()
    def generate(self, cn, seed, hist=HIST, idx=None):
        """cn (n, 40, 18) standardised requested controls for the windows self.idx (or idx); tokens < hist teacher-forced -> dict of (n, 40) long tensors c1, c2, v, p1, p2"""
        m, d = self.model, self.te
        ii = torch.from_numpy(self.idx if idx is None else idx)
        n = len(ii)
        assert cn.shape[0] == n, f"controls for {cn.shape[0]} windows, {n} starts"
        gen = torch.Generator().manual_seed(seed)
        style = m.style_vec(d.ds[ii], d.copy[ii], d.genre[ii])
        feat = m.ctl_feat(cn, torch.ones(n, GM.N_TOKENS))
        st, prev = m.zero_state(style), None
        out = {k: torch.zeros(n, GM.N_TOKENS, dtype=torch.long) for k in ("c1", "c2", "v", "p1", "p2")}
        gold = dict(c1=d.c1[ii], c2=d.c2[ii], v=d.v[ii], p1=d.p1[ii], p2=d.p2[ii])

        def samp(l):
            p = torch.softmax(l, -1)
            sp, si = p.sort(-1, descending=True)
            keep = (sp.cumsum(-1) - sp) < 0.9
            sp = sp * keep
            return si.gather(-1, torch.multinomial(sp / sp.sum(-1, keepdim=True), 1, generator=gen))[:, 0]

        for k in range(GM.N_TOKENS):
            f, st = m.step(st, feat[:, k], style, prev)
            if k < hist:
                t = {a: gold[a][:, k] for a in gold}
            else:
                lg = m.heads(f)
                c1 = samp(lg["c1"])
                lg = m.heads(f, c1)
                c2 = samp(lg["c2"])
                v = samp(lg["v"])
                p1 = samp(lg["p1"])
                p2 = samp(m.heads(f, c1, p1)["p2"])
                t = dict(c1=c1, c2=c2, v=v, p1=p1, p2=p2)
            for a in t:
                out[a][:, k] = t[a]
            prev = (t["c1"], t["c2"], t["v"], t["p1"], t["p2"])
        return out


class ZeroMotif(torch.nn.Module):
    """ablation: the motif state stays zero at every update"""

    def forward(self, x, m):
        return torch.zeros_like(m)


def boot(vals, groups, rng=None):
    """vals (n,) with nan allowed, groups (n,) -> mean, lo, hi: song-level bootstrap (mean per song first), NB resamples"""
    rng = np.random.default_rng(SEED_BOOT)
    vals = np.asarray(vals, float)
    gs = np.unique(groups)
    sm = np.array([np.nanmean(vals[groups == g]) if np.isfinite(vals[groups == g]).any() else np.nan for g in gs])
    sm = sm[np.isfinite(sm)]
    if not len(sm):
        return [None, None, None]
    b = sm[rng.integers(0, len(sm), (NB, len(sm)))].mean(1)
    return [float(sm.mean()), float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]


def run_sims(pool, S, toks, tag, log):
    """toks: dict of (n, 40) tensors/arrays for the starts; each start repeated NSAMP times upstream -> list of sim_job results"""
    n = len(toks["c1"])
    var = [GD.COPIES[int(c)] for c in S.te.copy[torch.from_numpy(S.idx)]]
    jobs = [({k: np.asarray(toks[k][i]) for k in ("c1", "c2", "v", "p1", "p2")}, var[i % len(S.idx)]) for i in range(n)]
    res = pool.map(sim_job, jobs, chunksize=4)
    bad = [r["error"] for r in res if "error" in r]
    if bad:
        log(f"{tag}: {len(bad)} failed, first {bad[0]}")
    return res


def summarise(res, S, n):
    """sim results of one condition (NSAMP * n) -> per-start dict of realised per-token measures (n, 40, 6), win scalars (n, 4)"""
    ok = [r for r in res if "error" not in r]
    ref = ok[0]
    tm, ws = np.full((len(res), 40, 6), np.nan), np.full((len(res), 5), np.nan)
    for i, r in enumerate(res):
        if "error" in r:
            continue
        tm[i] = ctl_measures(r["ctl"])
        ws[i] = [r["dirchg"], r["basespeed"], r["p_gt3"], float(r["frozen_any"]), r["frozen_frames"]]
    tm = tm.reshape(NSAMP, n, 40, 6)
    ws = ws.reshape(NSAMP, n, 5)
    ctl = np.stack([r["ctl"] if "error" not in r else np.full((40, 18), np.nan) for r in res]).reshape(NSAMP, n, 40, 18)
    return dict(tm=np.nanmean(tm, 0), ws=np.nanmean(ws, 0), ctl=ctl)


def win_meas(sm):
    """(n, 8) measures per start: token mean over tokens 8..39 of the 6 token measures, then dirchg, basespeed"""
    return np.concatenate([np.nanmean(sm["tm"][:, 8:], 1), sm["ws"][:, :2]], 1)


def cond_cn(S, name, kind, cvar=None):
    """requested raw controls (n, 40, 18) for a condition"""
    raw = S.raw.copy()
    return raw


def check_all(seed, procs, log):
    S = Setup(seed)
    n = len(S.idx)
    res = {}
    OUT.mkdir(exist_ok=True)
    rep = lambda x: np.concatenate([x] * NSAMP)
    rep_t = lambda t: {k: torch.cat([v] * NSAMP) for k, v in t.items()}
    with mp.get_context("spawn").Pool(procs, initializer=worker_init) as pool:

        def condition(name, raw):
            cn = S.to_cn(raw)
            toks = [S.generate(cn, seed * 100 + s) for s in range(NSAMP)]
            toks = {k: torch.cat([t[k] for t in toks]) for k in toks[0]}
            r = run_sims(pool, S, {k: v.numpy() for k, v in toks.items()}, name, log)
            sm = summarise(r, S, n)
            sm["tok"] = toks
            log(f"{name} done")
            return sm

        # human reference (re-joined human A1) and A with own oracle controls
        d = S.te
        ii = torch.from_numpy(S.idx)
        hum_tok = {k: np.concatenate([getattr(d, k)[ii].numpy()] * NSAMP) for k in ("c1", "c2", "v", "p1", "p2")}
        hj = summarise(run_sims(pool, S, hum_tok, "HJ", log), S, n)
        base = condition("own", S.raw)
        res["groups"] = [str(g) for g in S.groups]
        res["dsid"] = d.z["dsid"][S.idx].tolist()
        human_meas = ctl_measures(S.raw)
        hmeas = np.concatenate([np.nanmean(human_meas[:, 8:], 1)], 1)
        sd_h = np.nanstd(hmeas, 0)                                     # train-sd stand-in: spread of the human starts' own window means
        sd_h = np.concatenate([sd_h, [np.nanstd(hj["ws"][:, 0]), np.nanstd(hj["ws"][:, 1])]])
        mb = win_meas(base)

        # 2. intervention matrix
        raw0 = S.raw

        def with_control(raw, c, lev):
            r = raw.copy()
            sl = slice(HIST, 40)
            if c in ("vigour", "height", "sharp", "pause"):
                j = dict(vigour=0, height=1, sharp=10, pause=14)[c]
                r[:, sl, j] = S.q[j][lev]
                if c == "sharp":
                    r[:, sl, 15] = 1
            elif c == "accent":
                w = 1.5 - np.arange(8) / 7.0
                w = w if lev == 0 else w[::-1]
                r[:, sl, 2:10] = w
                r[:, sl, 17] = 1
            elif c == "direction":
                r[:, sl, 11:14] = [0, 0, -1.0 if lev == 0 else 1.0]
                r[:, sl, 16] = 1
            return r

        iv = {}
        for c in CTLS:
            lo, hi = condition(f"iv_{c}_lo", with_control(raw0, c, 0)), condition(f"iv_{c}_hi", with_control(raw0, c, 1))
            diff = win_meas(hi) - win_meas(lo)
            iv[c] = dict(effect={m: boot(diff[:, k] / sd_h[k], S.groups) for k, m in enumerate(MEAS)})
        res["intervention"] = iv
        combos = (("vigour", "height"), ("vigour", "sharp"), ("height", "pause"), ("sharp", "pause"))
        cb = {}
        for a, b in combos:
            ms = {}
            for la in (0, 1):
                for lb in (0, 1):
                    ms[(la, lb)] = win_meas(condition(f"cb_{a}{la}_{b}{lb}", with_control(with_control(raw0, a, la), b, lb)))
            ka, kb = MEAS.index({"sharp": "sharp"}.get(a, a)), MEAS.index({"sharp": "sharp"}.get(b, b))
            cb[f"{a}x{b}"] = dict(**{f"effect_{a}_at_{b}_{'lo' if lb == 0 else 'hi'}": boot((ms[(1, lb)][:, ka] - ms[(0, lb)][:, ka]) / sd_h[ka], S.groups) for lb in (0, 1)},
                                  **{f"effect_{b}_at_{a}_{'lo' if la == 0 else 'hi'}": boot((ms[(la, 1)][:, kb] - ms[(la, 0)][:, kb]) / sd_h[kb], S.groups) for la in (0, 1)})
        res["combinations"] = cb

        # 3. substitution
        rng = np.random.default_rng(SEED_START + 1)
        other = raw0.copy()
        dsid = d.z["dsid"][S.idx]
        allg, allraw, alld = d.z["group"], d.z["ctl"].astype(np.float64), d.z["dsid"]
        for i in range(n):
            c = np.flatnonzero((alld == dsid[i]) & (allg != S.groups[i]))
            other[i] = allraw[rng.choice(c)]
        shuf = raw0.copy()
        for i in range(n):
            shuf[i, HIST:] = raw0[i, HIST + rng.permutation(40 - HIST)]
        const = raw0.copy()
        for i in range(n):
            blk = raw0[i, HIST:]
            v = GT.valid_dims(blk)
            m = np.where(v.any(0), np.array([blk[v[:, j], j].mean() if v[:, j].any() else 0.0 for j in range(GD.CD)]), 0.0)
            const[i, HIST:] = m
            const[i, HIST:, 15:] = (blk[:, 15:].max(0))
        seqs = dict(own=raw0, other=other, shuffled=shuf, constant=const)
        outs = dict(own=base)
        for k in ("other", "shuffled", "constant"):
            outs[k] = condition(f"sub_{k}", seqs[k])
        sub = {}
        for k, o in outs.items():
            req = ctl_measures(seqs[k])[:, HIST:]
            for k2, o2 in outs.items():
                realised = ctl_measures(o2["ctl"].mean(0))[:, HIST:] if False else np.nanmean(np.stack([ctl_measures(c_) for c_ in o2["ctl"]]), 0)[:, HIST:]
                err = np.nanmean(np.abs(req - realised) / np.maximum(S.tr_sd[[0, 1, 10, 14, 13, 13]][None, None], 1e-6) * 1.0, (1, 2))
                sub[f"request_{k}__output_{k2}"] = dict(std_abs_err=boot(err, S.groups))
            if k != "constant":
                realised = np.nanmean(np.stack([ctl_measures(c_) for c_ in outs[k]["ctl"]]), 0)[:, HIST:]
                rr = []
                for i in range(n):
                    cs = []
                    for j in range(6):
                        a_, b_ = req[i, :, j], realised[i, :, j]
                        m = np.isfinite(a_) & np.isfinite(b_)
                        if m.sum() > 5 and a_[m].std() > 1e-9 and b_[m].std() > 1e-9:
                            cs.append(np.corrcoef(a_[m], b_[m])[0, 1])
                    rr.append(np.mean(cs) if cs else np.nan)
                sub[f"request_{k}__pearson_with_own_request"] = boot(np.array(rr), S.groups)
        res["substitution"] = sub

        # 4. jitter / frozen vs HJ, 4b posture/gesture split
        tk = base["tok"]
        mix = {}
        mix["A_posture_human_gesture"] = {**{k: hum_tok[k] for k in ("c1", "c2", "v")}, "p1": tk["p1"].numpy(), "p2": tk["p2"].numpy()}
        mix["human_posture_A_gesture"] = {**{k: tk[k].numpy() for k in ("c1", "c2", "v")}, "p1": hum_tok["p1"], "p2": hum_tok["p2"]}
        mixr = {k: summarise(run_sims(pool, S, v, k, log), S, n) for k, v in mix.items()}
        conds = dict(A=base, HJ=hj, **mixr)
        jf = {}
        for k, sm in conds.items():
            jf[k] = dict(p_gt3_mean=boot(sm["ws"][:, 2], S.groups), ratio_to_HJ=boot(sm["ws"][:, 2] / np.maximum(hj["ws"][:, 2], 1e-9), S.groups), frozen_any_share=boot(sm["ws"][:, 3], S.groups),
                         frozen_frame_share=boot(sm["ws"][:, 4], S.groups), dirchg=boot(sm["ws"][:, 0], S.groups))
        res["jitter_frozen"] = jf

        # 5. coherence, with motif ablation
        import t1b_tokens as TK
        cb1 = TK.load_vq().vq.vq1.cb.numpy().astype(np.float64)
        fam = TK.nearest(cb1, TK.kmeans(cb1, 32, 45004))
        zero_motif = GM.Grammar.step
        orig = S.model.motif
        S.model.motif = ZeroMotif()
        abl = condition("ablate_motif", S.raw)
        S.model.motif = orig

        def coh(ctlv, c1):
            out = {}
            sel = [0, 1, 10, 14]
            x = np.nan_to_num(ctlv[..., sel])
            x = (x - x.reshape(-1, 4).mean(0)) / np.maximum(x.reshape(-1, 4).std(0), 1e-6)
            for L in (4, 8):
                a, b = x[:, :-L], x[:, L:]
                cos = (a * b).sum(-1) / np.maximum(np.linalg.norm(a, axis=-1) * np.linalg.norm(b, axis=-1), 1e-9)
                out[f"ctl_cos_L{L}"] = cos.mean(1)
                f = fam[np.asarray(c1)]
                out[f"family_same_L{L}"] = (f[:, L:] == f[:, :-L]).mean(1)
            return out

        n_ = n
        hum_c = coh(S.raw, d.c1[ii].numpy())
        coh_r = {}
        for name, ctlv, c1 in (("A", base["ctl"].mean(0), base["tok"]["c1"][:n_].numpy()), ("A_motif_ablated", abl["ctl"].mean(0), abl["tok"]["c1"][:n_].numpy())):
            o = coh(ctlv, c1)
            coh_r[name] = {k: dict(value=boot(v, S.groups), ratio_to_human=boot(v / np.where(np.abs(hum_c[k]) > 1e-9, hum_c[k], np.nan), S.groups)) for k, v in o.items()}
        coh_r["human"] = {k: dict(value=boot(v, S.groups)) for k, v in hum_c.items()}
        res["coherence"] = coh_r

        # 1. residual-code utilisation
        tr = GD.load("train")
        va = GD.load("validation")
        c1t, c2t = tr["code1"].reshape(-1), tr["code2"].reshape(-1)
        p2 = np.bincount(c2t, minlength=1024) / len(c2t)
        H2 = float(-(p2[p2 > 0] * np.log(p2[p2 > 0])).sum())
        joint = np.zeros((1024, 1024))
        np.add.at(joint, (c1t, c2t), 1)
        pj = joint / joint.sum()
        pc1 = pj.sum(1)
        Hj = float(-(pj[pj > 0] * np.log(pj[pj > 0])).sum())
        Hc1 = float(-(pc1[pc1 > 0] * np.log(pc1[pc1 > 0])).sum())
        Hcond = Hj - Hc1
        # model predictive entropy of the code-2 head, teacher forced on the pooled held-out starts
        ent = []
        with torch.no_grad():
            m = S.model
            ii2 = torch.from_numpy(S.idx)
            cn = S.to_cn(S.raw)
            style = m.style_vec(d.ds[ii2], d.copy[ii2], d.genre[ii2])
            feat = m.ctl_feat(cn, torch.ones(n, 40))
            st, prev = m.zero_state(style), None
            for k in range(40):
                f, st = m.step(st, feat[:, k], style, prev)
                lg = m.heads(f, d.c1[ii2, k])
                p = torch.softmax(lg["c2"], -1)
                ent.append(-(p * torch.log(p.clamp_min(1e-12))).sum(-1))
                prev = (d.c1[ii2, k], d.c2[ii2, k], d.v[ii2, k], d.p1[ii2, k], d.p2[ii2, k])
        _w = {}
        worker_init()
        rg = []
        for i in range(min(60, n)):
            tok = {k: getattr(d, k)[int(S.idx[i])].numpy() for k in ("c1", "c2", "v", "p1", "p2")}
            full = decode_rows(tok)
            one = decode_rows(tok, stage2=False)
            rg.append(float(np.sqrt(((full - one) ** 2).mean()) / np.sqrt(((full - full.mean(0)) ** 2).mean())))
        res["residual"] = dict(stage2_codes_used_share=float((p2 > 0).mean()), stage2_perplexity=float(np.exp(H2)), H_c2_nats=H2, H_c2_given_c1_nats=float(Hcond), mutual_information_nats=float(H2 - Hcond),
                               model_mean_entropy_c2_head_nats=float(torch.stack(ent).mean()), decoded_stage2_rms_ratio_median=float(np.median(rg)), decoded_stage2_rms_ratio_quartiles=np.percentile(rg, [25, 75]).tolist(),
                               note="plug-in conditional entropy from train counts: biased downward for rare c1 codes")
    return res


def main():
    a = sys.argv[1:]
    assert a[0] == "run"
    seed, procs = int(a[1]), int(a[2]) if len(a) > 2 else 8
    OUT.mkdir(exist_ok=True)
    f = open(G / "logs" / f"checks{seed}.log", "a")
    log = lambda s: (f.write(s + "\n"), f.flush())
    r = check_all(seed, procs, log)
    (OUT / f"seed{seed}.json").write_text(json.dumps(r, indent=1))
    log("CHECKS DONE")


if __name__ == "__main__":
    main()
