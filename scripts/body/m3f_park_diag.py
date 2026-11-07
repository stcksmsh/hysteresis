"""WO16 (BRAIN_SPEC 7.31.1): diagnosis of the parked (stop-hold) behaviour in the WO15A toy seeds. Analysis only: no training, no cost, no change to any training path.

    m3f_park_diag.py SEEDDIR OUTDIR           re-simulate SEEDDIR's scored held-out argmax rollout with cfg["diag"] on (m3f_jax.arm_step_diag), write OUTDIR/sim.npz (the diagnostics) and
                                              OUTDIR/reproduction.json (re-simulated vs saved rollout)
    m3f_park_diag.py --analyse OUTROOT SEED..   read OUTROOT/seed*/sim.npz and the saved toy/ckpt, write OUTROOT/summary.json

Hold = a ranged joint (shoulder, elbow, wrist bend; 1, 2, 3) whose saved |q| is within TOL_DEG of 110 for >= 2 s (200 control steps) in a row. Provisional servo model (Feetech STS3215 12 V assumed).
"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np

STOP, TOL_DEG, MIN_STEPS = 110.0, 0.05, 200
CLIP_BOUND = 109.5                    # m3f_jax.CLIP_MARGIN_DEG inside the range
JOINTS = {1: "shoulder", 2: "elbow", 3: "wrist_bend"}
AMP_STILL_DEG = 5.0                   # "small amplitude" for chosen stillness
STEPS_BLOCK = 50
SEED_ROOT = "/secondary/hyst-data/body/m3f/rerun3"
TOY = "/secondary/hyst-data/body/m3d/toy.npz"
N_PERM = 2000


# ---------------------------------------------------------------------------------------------------------------- holds
def find_holds(q):
    """q (E, T, 5) deg -> list of dicts (episode, joint, side, start, end) with start/end in control steps (end exclusive)."""
    out = []
    for e in range(q.shape[0]):
        for j, name in JOINTS.items():
            on = np.abs(np.abs(q[e, :, j]) - STOP) < TOL_DEG
            i, T = 0, len(on)
            while i < T:
                if not on[i]:
                    i += 1
                    continue
                k = i
                while k < T and on[k]:
                    k += 1
                if k - i >= MIN_STEPS:
                    out.append({"episode": e, "joint": j, "name": name, "side": int(np.sign(q[e, i:k, j].mean())), "start": i, "end": k})
                i = k
    return out


# ---------------------------------------------------------------------------------------------------------------- simulation
def simulate(seeddir, outdir):
    import jax
    import m3e_jax as M
    import m3f
    import m3f_jax as F

    seeddir, outdir = Path(seeddir), Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    res = json.loads((seeddir / "result.json").read_text())
    cfg = dict(res["cfg"])
    assert cfg.get("clip") and cfg.get("ctc") == 0.006 and cfg.get("plane") == 0.053, cfg
    ck = pickle.loads((seeddir / "ckpt.pkl").read_bytes())
    import jax.numpy as jnp
    P = jax.tree_util.tree_map(jnp.asarray, ck["P"])
    toy = m3f.ToyF(res["args"]["toy"])
    C = M.load_cb()
    cb = res["args"]["chunk_blocks"]
    saved = np.load(seeddir / "rollouts" / "trained_argmax_4.npz")
    out = {}
    for tag, c in (("default", cfg), ("diag", {**cfg, "diag": True})):
        fns = m3f.make_fns(C, c, res["opts"])
        r = m3f.rollout(fns, c, C, P, toy, toy.sets[res["eval_set"]], "argmax", jax.random.PRNGKey(7), cb, 4242)
        out[tag] = r
        print(tag, "done", flush=True)
    rep = {}
    for tag, r in out.items():
        rep[tag] = {k: float(np.abs(r[k] - saved[k]).max()) for k in saved.files}
        rep[tag]["bit_identical_all_saved_keys"] = bool(all(np.array_equal(r[k], saved[k]) for k in saved.files))
    rep["default_vs_diag_bit_identical_all_saved_keys"] = bool(all(np.array_equal(out["default"][k], out["diag"][k]) for k in saved.files))
    (outdir / "reproduction.json").write_text(json.dumps(rep, indent=1))
    d = out["diag"]
    np.savez(outdir / "sim.npz", **{k: v for k, v in d.items() if k.startswith("dg_")}, q=d["q"])
    print(json.dumps({t: {"q_max_abs": rep[t]["q"], "all_identical": rep[t]["bit_identical_all_saved_keys"]} for t in ("default", "diag")}), flush=True)


# ---------------------------------------------------------------------------------------------------------------- analysis
def stats(x):
    x = np.asarray(x, float)
    return {"mean": float(x.mean()), "min": float(x.min()), "max": float(x.max())} if x.size else None


def runs(mask):
    """number of maximal True runs"""
    m = np.asarray(mask, bool)
    return int((m & ~np.concatenate([[False], m[:-1]])).sum())


def hold_blocks(holds, E, NB, full=True):
    """(E, NB) bool: blocks lying wholly inside a hold stretch (full) or overlapping one."""
    m = np.zeros((E, NB), bool)
    for h in holds:
        b0, b1 = (-(-h["start"] // STEPS_BLOCK), h["end"] // STEPS_BLOCK) if full else (h["start"] // STEPS_BLOCK, -(-h["end"] // STEPS_BLOCK))
        m[h["episode"], b0:b1] = True
    return m


def perm_diff(vals, mask, valid, rng, fn=None):
    """Circular-shift permutation (per episode, shift >= 8 blocks) of the hold mask. vals (E, NB) or (E, NB, K); mask, valid (E, NB).
    Statistic: mean over (mask & valid) minus mean over (~mask & valid) -> observed, p (two-sided)."""
    E, NB = mask.shape

    def stat(m):
        a, b = m & valid, (~m) & valid
        return vals[a].mean(0) - vals[b].mean(0)
    obs = stat(mask)
    null = []
    for _ in range(N_PERM):
        m2 = np.stack([np.roll(mask[e], int(rng.integers(8, NB - 7))) for e in range(E)])
        null.append(stat(m2))
    null = np.asarray(null)
    p = ((np.abs(null) >= np.abs(obs)).sum(0) + 1) / (N_PERM + 1)
    return obs, p


def analyse_seed(seed, root):
    import jax
    import jax.numpy as jnp
    import m3d
    import m3e
    import m3f
    import m3f_jax as F

    sdir = Path(SEED_ROOT) / f"seed{seed}" / "try1"
    res = json.loads((sdir / "result.json").read_text())
    cfg = res["cfg"]
    sim = np.load(Path(root) / f"seed{seed}" / "sim.npz")
    saved = np.load(sdir / "rollouts" / "trained_argmax_4.npz")
    q = saved["q"].reshape(saved["q"].shape[0], -1, 5)                   # the scored rollout (the re-simulation reproduces it, see reproduction.json)
    E, T, _ = q.shape
    NB = T // STEPS_BLOCK
    g = lambda k: sim["dg_" + k].reshape(E, T, -1)
    t_pre, centre, amp_raw, phase, tgt = g("t_pre"), g("centre"), g("amp"), g("phase"), g("tgt")
    hits, cf, cn, tgt_hit = g("hits"), g("cf"), g("cn"), g("tgt_hit")
    # effective amplitude of the generator (m3d_jax.cpg_step): bends are limited to CHI - |centre|, never negative
    import m3d_jax as J
    chi, bend = np.asarray(J.CHI), np.asarray(J.BEND)
    amp_eff = np.maximum(np.where(bend, np.minimum(amp_raw, chi - np.abs(centre)), amp_raw), 0.0)
    holds = find_holds(q)
    toy = m3f.ToyF(res["args"]["toy"])
    held = toy.sets[res["eval_set"]]
    y = toy.y[held]
    R = toy.R[held]
    ck = pickle.loads((sdir / "ckpt.pkl").read_bytes())
    stats_ = ck["stats"]
    pi, kappa = saved["pi"], saved["kappa"]
    prog = pi.argmax(-1)
    # fresh observers exactly as the scoring run (m3f.score_policy: trained on the four saved training rollouts, argmax)
    C = None
    rolls = [dict(np.load(sdir / "rollouts" / f"trained_argmax_{k}.npz")) for k in range(4)]
    yz_tr = toy.yz[toy.sets["train"]]
    Oe, Oi = m3f.fresh_observers(cfg, rolls, yz_tr, stats_)
    yz = toy.yz[held]
    pred = {}
    for nm, O, key, mu, sd in (("ext", Oe, "desc", stats_["dmu"], stats_["dsd"]), ("int", Oi, "idesc", stats_["imu"], stats_["isd"])):
        pred[nm] = np.asarray(jax.vmap(jax.vmap(lambda x: m3d_obs_apply(O, x)))(jnp.asarray(m3d.std_desc(saved[key], mu, sd))))
    matched = {nm: ((pred[nm] - yz) ** 2).mean(-1) for nm in pred}                              # (E, NB)
    shifted = {}
    for nm in pred:
        sh = [((pred[nm] - np.roll(yz, s, axis=1)) ** 2).mean(-1) for s in range(8, 28)]
        shifted[nm] = np.mean(sh, 0)
    gap = {nm: shifted[nm] - matched[nm] for nm in pred}
    # the same gap numbers the scoring run reports (reproduces result.json: ext/int a_gap_mean)
    rep_gap = {nm: float(np.mean([gap[nm][e, m3e.EVAL_FROM:].mean() for e in range(E)])) for nm in pred}
    # programs' commanded centres (sigmoid(theta) -> centre) for the program table
    P = ck["P"]
    u = 1.0 / (1.0 + np.exp(-np.asarray(P["theta"]))) if "theta" in P else None
    centre_cmd = (np.asarray(J.CLO) + u.reshape(-1, 4, 5)[:, 2] * (chi - np.asarray(J.CLO))) if u is not None else None
    amp_cmd = (u.reshape(-1, 4, 5)[:, 1] * np.where(bend, chi - np.abs(centre_cmd), 0.0)) if u is not None else None

    valid_blocks = np.zeros((E, NB), bool)
    valid_blocks[:, m3e.EVAL_FROM:] = True
    hb_full, hb_any = hold_blocks(holds, E, NB, True), hold_blocks(holds, E, NB, False)
    outside = valid_blocks & ~hb_any
    inside = valid_blocks & hb_full
    rng = np.random.default_rng(0)

    per = []
    for h in holds:
        e, j, s, en, sd_ = h["episode"], h["joint"], h["start"], h["end"], h["side"]
        sl = slice(s, en)
        n = en - s
        tp, ce, am, ae, ph, tg = sd_ * t_pre[e, sl, j], sd_ * centre[e, sl, j], amp_raw[e, sl, j], amp_eff[e, sl, j], phase[e, sl, j], sd_ * tgt[e, sl, j]
        qq = sd_ * q[e, sl, j]
        row = dict(h, start_s=s / 100.0, end_s=en / 100.0, duration_s=n / 100.0)
        # 1. clipping (all values signed so that the stop is at +110 on the side of the hold)
        row["clip"] = {"t_pre_deg": stats(tp), "centre_deg": stats(ce), "amp_raw_deg": stats(am), "amp_eff_deg": stats(ae),
                       "share_pre_beyond_stop_110": float((tp >= STOP).mean()), "share_pre_at_or_beyond_clip_bound_109.5": float((tp >= CLIP_BOUND).mean()),
                       "share_held_target_on_clip_bound": float((tg >= CLIP_BOUND - 1e-6).mean()), "held_target_deg": stats(tg),
                       "share_centre_at_or_beyond_clip_bound": float((ce >= CLIP_BOUND).mean()),
                       "t_pre_std_deg": float(tp.std()), "t_pre_peak_to_peak_deg": float(tp.max() - tp.min()),
                       "phase_advance_rad_per_s_mean": float(np.diff(ph).mean() * 100.0), "phase_advance_rad_per_s_min": float(np.diff(ph).min() * 100.0),
                       "share_pre_inside_range_below_109.5": float((tp < CLIP_BOUND).mean()),
                       "q_minus_held_target_deg": stats(qq - tg)}
        # 2. chosen stillness
        row["stillness"] = {"share_pre_inside_range_and_amp_eff_lt_5deg": float(((tp < CLIP_BOUND) & (ae < AMP_STILL_DEG)).mean()), "share_amp_eff_lt_5deg": float((ae < AMP_STILL_DEG).mean()),
                            "share_pre_inside_range": float((tp < CLIP_BOUND).mean())}
        # 3. contact
        c = {}
        for ci, nm in enumerate(F.CONTACT_CATS):
            f, k = cf[e, sl, ci], cn[e, sl, ci]
            c[nm] = {"share_steps_in_contact": float((k > 0).mean()), "force_N_mean_over_contact_steps": float(f[k > 0].mean()) if (k > 0).any() else 0.0, "force_N_max": float(f.max()), "n_contacts_max": float(k.max())}
        c["any_share"] = float((cn[e, sl].sum(-1) > 0).mean())
        row["contact"] = c
        # 4. end stop
        hh = hits[e, sl, j]
        dq = np.diff(q[e, :, j]) * 100.0                                                       # deg/s of the realised joint
        pre = np.abs(dq[max(0, s - 5):s]) if s > 0 else np.zeros(0)
        post = np.abs(dq[en - 1:en + 4]) if en < T else np.zeros(0)
        row["endstop"] = {"share_steps_with_hit": float((hh > 0).mean()), "hit_substeps_total": float(hh.sum()), "hit_substeps_per_step_mean": float(hh.mean()), "hit_runs": runs(hh > 0),
                          "first_hit_after_onset_steps": int(np.argmax(hh > 0)) if (hh > 0).any() else None,
                          "joint_speed_deg_s_5_steps_before_onset": float(pre.mean()) if pre.size else None, "joint_speed_deg_s_in_hold_mean": float(np.abs(dq[s:en - 1]).mean()),
                          "joint_speed_deg_s_5_steps_from_exit": float(post.mean()) if post.size else None,
                          "hits_in_5_steps_before_onset": float(hits[e, max(0, s - 5):s, j].sum()), "hits_in_5_steps_from_exit": float(hits[e, en - 1:en + 4, j].sum())}
        # 5. brain side (blocks wholly inside the stretch)
        b0, b1 = -(-s // STEPS_BLOCK), en // STEPS_BLOCK
        bl = slice(b0, b1)
        row["brain"] = {"n_blocks": b1 - b0, "program_counts": np.bincount(prog[e, bl], minlength=8).tolist(), "kappa_mean_joint": float(kappa[e, bl, j].mean()), "kappa_mean_all": float(kappa[e, bl].mean()),
                        "arousal_mean": float(y[e, bl, 0].mean()), "surprisal_mean": float(y[e, bl, 1].mean()), "L3_R_mean": float(R[e, bl].mean())}
        # 6. observer
        row["observer"] = {nm: {"loss_mean": float(matched[nm][e, bl].mean()), "gap_mean": float(gap[nm][e, bl].mean())} for nm in pred}
        per.append(row)

    # pooled
    tot = sum(r["duration_s"] for r in per)
    wmean = lambda f: float(sum(f(r) * r["duration_s"] for r in per) / tot) if tot else None
    pooled = {"n_holds": len(per), "total_hold_s": tot, "per_joint_s": {nm: float(sum(r["duration_s"] for r in per if r["name"] == nm)) for nm in JOINTS.values()}}
    pooled["clip"] = {k: wmean(lambda r, k=k: r["clip"][k]) for k in ("share_pre_beyond_stop_110", "share_pre_at_or_beyond_clip_bound_109.5", "share_held_target_on_clip_bound", "share_centre_at_or_beyond_clip_bound", "share_pre_inside_range_below_109.5")}
    pooled["clip"]["amp_eff_deg_mean"] = wmean(lambda r: r["clip"]["amp_eff_deg"]["mean"])
    pooled["clip"]["t_pre_peak_to_peak_deg_mean"] = wmean(lambda r: r["clip"]["t_pre_peak_to_peak_deg"])
    pooled["clip"]["phase_advance_rad_per_s_mean"] = wmean(lambda r: r["clip"]["phase_advance_rad_per_s_mean"])
    pooled["clip"]["q_minus_held_target_deg_mean"] = wmean(lambda r: r["clip"]["q_minus_held_target_deg"]["mean"])
    pooled["stillness"] = {k: wmean(lambda r, k=k: r["stillness"][k]) for k in ("share_pre_inside_range_and_amp_eff_lt_5deg", "share_amp_eff_lt_5deg", "share_pre_inside_range")}
    pooled["contact"] = {nm: {k: wmean(lambda r, nm=nm, k=k: r["contact"][nm][k]) for k in ("share_steps_in_contact", "force_N_mean_over_contact_steps")} for nm in F.CONTACT_CATS}
    pooled["contact"]["any_share"] = wmean(lambda r: r["contact"]["any_share"])
    pooled["contact"]["force_N_max_any_hold"] = {nm: max(r["contact"][nm]["force_N_max"] for r in per) if per else 0.0 for nm in F.CONTACT_CATS}
    pooled["endstop"] = {k: wmean(lambda r, k=k: r["endstop"][k]) for k in ("share_steps_with_hit", "hit_substeps_per_step_mean")}
    pooled["endstop"]["hit_runs_total"] = int(sum(r["endstop"]["hit_runs"] for r in per))
    sp_in = [r["endstop"]["joint_speed_deg_s_in_hold_mean"] for r in per]
    pooled["endstop"]["joint_speed_deg_s_in_hold_mean_of_stretches"] = float(np.mean(sp_in)) if sp_in else None

    # brain side pooled vs outside, with circular-shift permutation tests on the hold mask
    def brain_block(vals, nm):
        obs, p = perm_diff(vals, hb_full, valid_blocks & ~(hb_any & ~hb_full), rng)
        return {"inside_mean": float(np.asarray(vals)[inside].mean(0)), "outside_mean": float(np.asarray(vals)[outside].mean(0)), "diff": float(obs), "outside_sd": float(np.asarray(vals)[outside].std()), "perm_p": float(p)}
    # all blocks of a hold (any overlap) are excluded from "outside"; "inside" = wholly inside
    brain = {"n_blocks_inside": int(inside.sum()), "n_blocks_outside": int(outside.sum())}
    for nm, vals in (("arousal", y[..., 0]), ("surprisal", y[..., 1]), ("L3_R", R), ("kappa_mean_over_joints", kappa.mean(-1))):
        brain[nm] = brain_block(vals, nm)
    for j, nm in JOINTS.items():
        pass
    brain["kappa_per_joint"] = {JOINTS.get(j, str(j)): brain_block(kappa[..., j], nm) for j in range(5) for nm in [str(j)]}
    onehot = np.eye(8)[prog]
    pin, pout = onehot[inside].mean(0), onehot[outside].mean(0)
    tv_obs = 0.5 * np.abs(pin - pout).sum()
    nullv = []
    for _ in range(N_PERM):
        m2 = np.stack([np.roll(hb_full[e], int(rng.integers(8, NB - 7))) for e in range(E)])
        a, b = m2 & valid_blocks & ~(hb_any & ~hb_full & False), (~m2) & valid_blocks
        nullv.append(0.5 * np.abs(onehot[a & valid_blocks].mean(0) - onehot[b].mean(0)).sum() if a.any() else 0.0)
    brain["programs"] = {"inside_share": pin.tolist(), "outside_share": pout.tolist(), "tv_distance": float(tv_obs), "perm_p": float((np.sum(np.asarray(nullv) >= tv_obs) + 1) / (N_PERM + 1)),
                         "all_blocks_share": onehot[valid_blocks].mean(0).tolist()}
    if centre_cmd is not None:
        brain["programs"]["commanded_centre_deg_per_program"] = {nm: centre_cmd[:, j].round(1).tolist() for j, nm in JOINTS.items()}
        brain["programs"]["commanded_amp_deg_per_program"] = {nm: amp_cmd[:, j].round(1).tolist() for j, nm in JOINTS.items()}
    pooled["brain"] = brain

    # observer pooled
    ob = {}
    for nm in pred:
        for what, arr in (("loss", matched[nm]), ("gap", gap[nm])):
            obs, p = perm_diff(arr, hb_full, valid_blocks & ~(hb_any & ~hb_full), rng)
            ob[f"{nm}_{what}"] = {"inside_mean": float(arr[inside].mean()), "outside_mean": float(arr[outside].mean()), "diff": float(obs), "perm_p": float(p)}
    ob["scoring_gap_reproduced"] = rep_gap
    ob["scoring_gap_in_result_json"] = {"ext": res["result"]["argmax"]["ext"]["a_gap_mean"], "int": res["result"]["argmax"]["int"]["a_gap_mean"]}
    pooled["observer"] = ob
    # share of time on a stop, per joint (all episodes), for reference
    pooled["time_on_stop_share"] = {nm: float((np.abs(np.abs(q[..., j]) - STOP) < TOL_DEG).mean()) for j, nm in JOINTS.items()}
    return {"holds": per, "pooled": pooled}


def m3d_obs_apply(O, x):
    import m3d_jax as J
    return J.observer_apply(O, x)


def verdicts(S):
    """one line per hypothesis, from the pooled numbers of both seeds"""
    out = {}
    pooled = {s: S[s]["pooled"] for s in S}
    tot = sum(p["total_hold_s"] for p in pooled.values())
    w = lambda f: sum(f(p) * p["total_hold_s"] for p in pooled.values()) / tot
    c1 = w(lambda p: p["clip"]["share_pre_beyond_stop_110"])
    c1b = w(lambda p: p["clip"]["share_pre_at_or_beyond_clip_bound_109.5"])
    out["H1"] = {"supported": bool(c1 > 0.5), "number": f"commanded pre-clip target beyond the 110 deg stop for {100 * c1:.1f} % of hold time ({100 * c1b:.1f} % at or beyond the 109.5 deg clip bound)"}
    c2 = w(lambda p: p["stillness"]["share_pre_inside_range_and_amp_eff_lt_5deg"])
    out["H2"] = {"supported": bool(c2 > 0.5), "number": f"{100 * c2:.1f} % of hold time with the commanded target inside the range (< 109.5) and generator amplitude < {AMP_STILL_DEG:.0f} deg"}
    c3 = w(lambda p: p["contact"]["any_share"])
    out["H3"] = {"supported": bool(c3 > 0.5), "number": f"{100 * c3:.1f} % of hold time with any active contact"}
    c4 = w(lambda p: p["endstop"]["share_steps_with_hit"])
    out["H4"] = {"supported": bool(c4 > 0.5), "number": f"the hard stop acted in {100 * c4:.1f} % of the hold's control steps"}
    ps = {s: pooled[s]["brain"]["programs"]["perm_p"] for s in pooled}
    out["H5"] = {"supported": bool(all(p < 0.01 for p in ps.values())), "number": "program distribution inside vs outside holds, TV distance " + ", ".join(
        f"seed {s}: {pooled[s]['brain']['programs']['tv_distance']:.3f} (perm p {ps[s]:.4f})" for s in pooled)}
    obs = {s: pooled[s]["observer"] for s in pooled}
    easy = all(obs[s][f"{nm}_loss"]["diff"] < 0 and obs[s][f"{nm}_loss"]["perm_p"] < 0.01 for s in obs for nm in ("ext", "int"))
    out["H6"] = {"supported": bool(easy), "number": "decoder loss inside minus outside holds " + "; ".join(
        f"seed {s} ext {obs[s]['ext_loss']['diff']:+.3f} (p {obs[s]['ext_loss']['perm_p']:.3f}), int {obs[s]['int_loss']['diff']:+.3f} (p {obs[s]['int_loss']['perm_p']:.3f})" for s in obs)}
    return out


def main():
    if sys.argv[1] == "--analyse":
        root, seeds = sys.argv[2], [int(x) for x in sys.argv[3:]]
        S = {str(s): analyse_seed(s, root) for s in seeds}
        S["verdicts"] = verdicts({k: v for k, v in S.items()})
        (Path(root) / "summary.json").write_text(json.dumps(S, indent=1))
        print(json.dumps(S["verdicts"], indent=1))
        return 0
    simulate(sys.argv[1], sys.argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main())
