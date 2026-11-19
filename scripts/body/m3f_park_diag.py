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
BOUNDARY, BOUNDARY_TOL = 109.5, 1.0   # WO16b: holds within 1 deg of the target-clip boundary
STALL_NM = 30 * 0.0980665             # make_arm.STALL_NM (provisional Feetech STS3215 12 V stall torque, 2.94 N.m); the position actuators clip to +-this (forcerange)
KP_NM_RAD = STALL_NM / np.radians(10.0)    # make_arm.KP: full stall torque at 10 deg error


def replay_5deg(cfg, qpose, tgt_pose, j, side, secs=2.0):
    """Plain MuJoCo (the body of cfg; soft joint limits, no hard stop) from the hold pose, joint j's servo target 5 deg inside the stop vs the target held in the run: the joint's end position
    (signed, stop at +110) and mean actuator torque over the last 0.5 s. Shows whether the servo can hold the joint off the stop against gravity."""
    import mujoco
    import m3f_jax as F
    m = F.body_model(cfg)[0]
    out = {}
    for name, tj in (("target_inside_by_5deg", side * (STOP - 5.0)), ("as_run_target", float(tgt_pose[j]))):
        d = mujoco.MjData(m)
        d.qpos[:] = np.radians(qpose)
        ctrl = np.radians(np.asarray(tgt_pose, float))
        ctrl[j] = np.radians(tj)
        d.ctrl[:] = ctrl
        mujoco.mj_forward(m, d)
        n, tail = int(secs / m.opt.timestep), int(0.5 / m.opt.timestep)
        f = []
        for k in range(n):
            mujoco.mj_step(m, d)
            if k >= n - tail:
                f.append(d.actuator_force[j])
        out[name] = {"target_deg": float(side * tj), "end_q_deg": float(side * np.degrees(d.qpos[j])), "mean_actuator_Nm_last_0.5s": float(side * np.mean(f))}
    return out


# ---------------------------------------------------------------------------------------------------------------- holds
def find_holds(q, at=STOP, tol=TOL_DEG):
    """q (E, T, 5) deg -> list of dicts (episode, joint, side, start, end) with start/end in control steps (end exclusive)."""
    out = []
    for e in range(q.shape[0]):
        for j, name in JOINTS.items():
            on = np.abs(np.abs(q[e, :, j]) - at) < tol
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
    gap, base = {}, (yz ** 2).mean(-1)                           # per-block gap with the scoring run's own shifts (m3d.time_shuffled_gap: rng seed 0, 20 shifts per episode in [8, NB - 8]); base = loss of predicting the mean
    for nm in pred:
        rng_s = np.random.default_rng(0)
        g_ = np.empty((E, NB))
        for e in range(E):
            ls = [((pred[nm][e] - np.roll(yz[e], int(rng_s.integers(8, NB - 8 + 1)), axis=0)) ** 2).mean(-1) for _ in range(20)]
            g_[e] = np.mean(ls, 0) - matched[nm][e]
        gap[nm] = g_
    # mean over blocks >= EVAL_FROM = the scoring run's a_gap_mean (checked against result.json below)
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

    # WO16b H1b: the motor cortex's own outputs per block (recomputed from the saved inputs xin; u = clip(pi @ sigmoid(theta) + MOD tanh(amod), 0, 1), rows (freq, amp, centre, lag) x 5 joints)
    Pj = jax.tree_util.tree_map(jnp.asarray, ck["P"])
    _, amod_all, _ = jax.vmap(jax.vmap(lambda x: J.motor_cortex(Pj, x)))(jnp.asarray(saved["xin"]))
    amod_all = np.asarray(amod_all)
    u_pre = (np.asarray(pi) @ (1.0 / (1.0 + np.exp(-np.asarray(ck["P"]["theta"]))))) + J.MOD * np.tanh(amod_all)          # (E, NB, 20) before the clip to [0, 1]
    u_pre = u_pre.reshape(E, NB, 4, 5)
    u_clip = np.clip(u_pre, 0.0, 1.0)

    def row_of(h):
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
                       "share_centre_at_or_beyond_clip_bound": float((ce >= CLIP_BOUND).mean()), "share_centre_on_generator_limit_110": float((ce >= STOP - 1e-3).mean()),
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
        # 7. (WO16b H7) torque / gravity. actuator_force = joint torque in N.m (position actuator, gear 1, clipped to +-STALL_NM by forcerange); qfrc_bias = gravity + velocity terms (gravity torque on the joint = -qfrc_bias);
        #    qfrc_constraint = joint-limit + contact force; all read from the substep just integrated, averaged over the 5 substeps (actmax = max |actuator_force| over them). Signed so that the stop is at +.
        tq = {}
        for jj, nm in ((j, "held_joint"), (1, "shoulder")):
            a, am_, bi, co = sd_ * g("act")[e, sl, jj], g("actmax")[e, sl, jj], -sd_ * g("bias")[e, sl, jj], sd_ * g("con")[e, sl, jj]
            tq[nm] = {"actuator_Nm": stats(a), "share_actuator_at_stall": float((am_ >= STALL_NM * (1 - 1e-3)).mean()), "share_mean_actuator_ge_98pct_stall": float((np.abs(a) >= 0.98 * STALL_NM).mean()),
                      "gravity_torque_toward_stop_Nm": stats(bi), "share_gravity_toward_stop": float((bi > 0).mean()), "constraint_torque_Nm": stats(co),
                      "gravity_droop_deg_equiv_kp": float(bi.mean() / KP_NM_RAD * 180.0 / np.pi)}
        row["torque"] = tq
        row["torque"]["replay_held_5deg_inside"] = replay_5deg(cfg, q[e, (s + en) // 2], tgt[e, (s + en) // 2], j, sd_)
        # 3b. (WO16b H1b) the motor cortex's outputs for the held joint on the blocks wholly inside the stretch
        uc, ua = u_pre[e, bl, 2, j], u_pre[e, bl, 1, j]
        near = lambda u: ((np.clip(u, 0, 1) <= 0.02) | (np.clip(u, 0, 1) >= 0.98))
        row["network"] = {"n_blocks": b1 - b0,
                          "centre_u_preclip": stats(uc), "amp_u_preclip": stats(ua),
                          "share_centre_u_within_2pct_of_bound": float(near(uc).mean()), "share_amp_u_within_2pct_of_bound": float(near(ua).mean()),
                          "share_centre_u_preclip_outside_0_1": float(((uc < 0) | (uc > 1)).mean()), "share_amp_u_preclip_outside_0_1": float(((ua < 0) | (ua > 1)).mean()),
                          "share_centre_u_at_hold_side_bound": float(((np.clip(uc, 0, 1) <= 0.02) if sd_ < 0 else (np.clip(uc, 0, 1) >= 0.98)).mean()),
                          "centre_amod_tanh_abs_mean": float(np.abs(np.tanh(amod_all[e, bl, 10 + j])).mean()), "share_centre_amod_tanh_abs_gt_0.98": float((np.abs(np.tanh(amod_all[e, bl, 10 + j])) > 0.98).mean()),
                          "centre_prototype_u_mean": float((np.asarray(pi)[e, bl] @ (1.0 / (1.0 + np.exp(-np.asarray(ck["P"]["theta"]))))).reshape(-1, 4, 5)[:, 2, j].mean())}
        return row
    per = [row_of(h) for h in holds]
    bholds_all = find_holds(q, BOUNDARY, BOUNDARY_TOL)
    stopmask = {(h["episode"], h["joint"]): h for h in holds}
    bholds = []
    for h in bholds_all:
        on_stop = np.abs(np.abs(q[h["episode"], h["start"]:h["end"], h["joint"]]) - STOP) < TOL_DEG
        h["share_on_stop"] = float(on_stop.mean())
        if h["share_on_stop"] < 0.5:                                # boundary-only: not (mostly) a stop hold
            bholds.append(h)
    per_b = [row_of(h) for h in bholds]

    # pooled
    tot = sum(r["duration_s"] for r in per)
    wmean = lambda f: float(sum(f(r) * r["duration_s"] for r in per) / tot) if tot else None
    pooled = {"n_holds": len(per), "total_hold_s": tot, "per_joint_s": {nm: float(sum(r["duration_s"] for r in per if r["name"] == nm)) for nm in JOINTS.values()}}
    pooled["clip"] = {k: wmean(lambda r, k=k: r["clip"][k]) for k in ("share_pre_beyond_stop_110", "share_pre_at_or_beyond_clip_bound_109.5", "share_held_target_on_clip_bound", "share_centre_at_or_beyond_clip_bound", "share_centre_on_generator_limit_110", "share_pre_inside_range_below_109.5")}
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
    brain["kappa_per_joint"] = {JOINTS.get(j, str(j)): brain_block(kappa[..., j], nm) for j in range(5) for nm in [str(j)]}
    onehot = np.eye(8)[prog]
    pin, pout = onehot[inside].mean(0), onehot[outside].mean(0)
    tv_obs = 0.5 * np.abs(pin - pout).sum()
    nullv = []
    for _ in range(N_PERM):
        m2 = np.stack([np.roll(hb_full[e], int(rng.integers(8, NB - 7))) for e in range(E)])
        a, b = m2 & valid_blocks, (~m2) & valid_blocks
        nullv.append(0.5 * np.abs(onehot[a].mean(0) - onehot[b].mean(0)).sum() if a.any() else 0.0)
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
    obs, p = perm_diff(base, hb_full, valid_blocks & ~(hb_any & ~hb_full), rng)
    ob["baseline_loss_predict_mean"] = {"inside_mean": float(base[inside].mean()), "outside_mean": float(base[outside].mean()), "diff": float(obs), "perm_p": float(p)}
    for nm in pred:
        ob[f"{nm}_loss_over_baseline"] = {"inside": float(matched[nm][inside].mean() / base[inside].mean()), "outside": float(matched[nm][outside].mean() / base[outside].mean())}
    ob["scoring_gap_reproduced"] = rep_gap
    ob["scoring_gap_in_result_json"] = {"ext": res["result"]["argmax"]["ext"]["a_gap_mean"], "int": res["result"]["argmax"]["int"]["a_gap_mean"]}
    pooled["observer"] = ob
    # share of time on a stop, per joint (all episodes), for reference
    pooled["time_on_stop_share"] = {nm: float((np.abs(np.abs(q[..., j]) - STOP) < TOL_DEG).mean()) for j, nm in JOINTS.items()}
    def tq_pool(rows, tot_):
        wm = lambda f: float(sum(f(r) * r["duration_s"] for r in rows) / tot_) if tot_ else None
        o = {}
        for nm in ("held_joint", "shoulder"):
            o[nm] = {"share_actuator_at_stall": wm(lambda r, nm=nm: r["torque"][nm]["share_actuator_at_stall"]), "share_mean_actuator_ge_98pct_stall": wm(lambda r, nm=nm: r["torque"][nm]["share_mean_actuator_ge_98pct_stall"]),
                     "actuator_Nm_mean": wm(lambda r, nm=nm: r["torque"][nm]["actuator_Nm"]["mean"]), "share_gravity_toward_stop": wm(lambda r, nm=nm: r["torque"][nm]["share_gravity_toward_stop"]),
                     "gravity_toward_stop_Nm_mean": wm(lambda r, nm=nm: r["torque"][nm]["gravity_torque_toward_stop_Nm"]["mean"]), "constraint_Nm_mean": wm(lambda r, nm=nm: r["torque"][nm]["constraint_torque_Nm"]["mean"]),
                     "gravity_droop_deg_equiv_kp_mean": wm(lambda r, nm=nm: r["torque"][nm]["gravity_droop_deg_equiv_kp"])}
        for k in ("target_inside_by_5deg", "as_run_target"):
            e_ = [r["torque"]["replay_held_5deg_inside"][k]["end_q_deg"] for r in rows]
            o["replay_" + k] = {"end_q_deg_mean": float(np.mean(e_)), "end_q_deg_min": float(np.min(e_)), "end_q_deg_max": float(np.max(e_)),
                                "share_end_within_1deg_of_target": float(np.mean([abs(r["torque"]["replay_held_5deg_inside"][k]["end_q_deg"] - r["torque"]["replay_held_5deg_inside"][k]["target_deg"]) < 1.0 for r in rows]))}
        return o

    def net_pool(rows, tot_):
        wm = lambda f: float(sum(f(r) * r["duration_s"] for r in rows) / tot_) if tot_ else None
        return {k: wm(lambda r, k=k: r["network"][k]) for k in ("share_centre_u_within_2pct_of_bound", "share_amp_u_within_2pct_of_bound", "share_centre_u_preclip_outside_0_1", "share_amp_u_preclip_outside_0_1",
                                                                  "share_centre_u_at_hold_side_bound", "share_centre_amod_tanh_abs_gt_0.98", "centre_prototype_u_mean")}
    pooled["torque"] = tq_pool(per, tot)
    pooled["network"] = net_pool(per, tot)
    tot_b = sum(r["duration_s"] for r in per_b)
    wmb = lambda f: float(sum(f(r) * r["duration_s"] for r in per_b) / tot_b) if tot_b else None
    bpool = {"n_holds": len(per_b), "total_hold_s": tot_b, "n_all_within_1deg_of_109.5": len(bholds_all), "per_joint_s": {nm: float(sum(r["duration_s"] for r in per_b if r["name"] == nm)) for nm in JOINTS.values()},
             "share_pre_at_or_beyond_clip_bound_109.5": wmb(lambda r: r["clip"]["share_pre_at_or_beyond_clip_bound_109.5"]), "share_held_target_on_clip_bound": wmb(lambda r: r["clip"]["share_held_target_on_clip_bound"]),
             "amp_eff_deg_mean": wmb(lambda r: r["clip"]["amp_eff_deg"]["mean"]), "share_steps_with_hit": wmb(lambda r: r["endstop"]["share_steps_with_hit"]),
             "any_contact_share": wmb(lambda r: r["contact"]["any_share"]), "share_on_stop_mean": float(np.mean([h["share_on_stop"] for h in bholds])) if bholds else None}
    if per_b:
        bpool["torque"], bpool["network"] = tq_pool(per_b, tot_b), net_pool(per_b, tot_b)
    return {"holds": per, "pooled": pooled, "boundary_holds": per_b, "boundary_pooled": bpool}


def m3d_obs_apply(O, x):
    import m3d_jax as J
    return J.observer_apply(O, x)


def verdicts(S):
    """one line per hypothesis, from the pooled numbers of both seeds"""
    out = {}
    pooled = {s: S[s]["pooled"] for s in S}
    tot = sum(p["total_hold_s"] for p in pooled.values())
    w = lambda f: sum(f(p) * p["total_hold_s"] for p in pooled.values()) / tot
    c1 = w(lambda p: p["clip"]["share_pre_at_or_beyond_clip_bound_109.5"])
    c1c = w(lambda p: p["clip"]["share_centre_on_generator_limit_110"])
    c1x = w(lambda p: p["clip"]["share_pre_beyond_stop_110"])
    out["H1"] = {"supported": bool(c1 > 0.5), "number": f"commanded pre-clip target at or beyond the 109.5 deg clip bound for {100 * c1:.1f} % of hold time (generator centre on its own +-110 limit {100 * c1c:.1f} %; "
                 f"the target exceeds 110.0 only {100 * c1x:.1f} % of the time, by float noise, and the clip removes at most 0.5 deg); generator amplitude mean {w(lambda p: p['clip']['amp_eff_deg_mean']):.2f} deg, "
                 f"phase still advancing {w(lambda p: p['clip']['phase_advance_rad_per_s_mean']):.1f} rad/s"}
    c2 = w(lambda p: p["stillness"]["share_pre_inside_range_and_amp_eff_lt_5deg"])
    out["H2"] = {"supported": bool(c2 > 0.5), "number": f"{100 * c2:.1f} % of hold time with the commanded target inside the range (< 109.5) and generator amplitude < {AMP_STILL_DEG:.0f} deg"}
    c3 = w(lambda p: p["contact"]["any_share"])
    out["H3"] = {"supported": bool(c3 > 0.5), "number": f"{100 * c3:.1f} % of hold time with any active contact"}
    c4 = w(lambda p: p["endstop"]["share_steps_with_hit"])
    out["H4"] = {"supported": bool(c4 > 0.5), "number": f"the hard stop acted in {100 * c4:.1f} % of the hold's control steps"}
    ps = {s: pooled[s]["brain"]["programs"]["perm_p"] for s in pooled}
    out["H5"] = {"supported": bool(all(p < 0.01 for p in ps.values())), "supported_per_seed": {s: bool(ps[s] < 0.01) for s in ps},
                 "number": "program distribution inside vs outside holds, TV distance " + ", ".join(f"seed {s}: {pooled[s]['brain']['programs']['tv_distance']:.3f} (perm p {ps[s]:.4f})" for s in pooled)}
    obs = {s: pooled[s]["observer"] for s in pooled}
    lower = {s: bool(all(obs[s][f"{nm}_loss"]["diff"] < 0 and obs[s][f"{nm}_loss"]["perm_p"] < 0.01 for nm in ("ext", "int"))) for s in obs}
    gapbig = {s: bool(all(obs[s][f"{nm}_gap"]["diff"] > 0 and obs[s][f"{nm}_gap"]["perm_p"] < 0.01 for nm in ("ext", "int"))) for s in obs}
    out["H6"] = {"supported": bool(all(lower.values()) and all(gapbig.values())), "lower_loss_per_seed": lower, "larger_shuffle_gap_per_seed": gapbig,
                 "number": "decoder loss inside minus outside holds " + "; ".join(
                     f"seed {s} ext {obs[s]['ext_loss']['diff']:+.3f} (p {obs[s]['ext_loss']['perm_p']:.3f}), int {obs[s]['int_loss']['diff']:+.3f} (p {obs[s]['int_loss']['perm_p']:.3f}), "
                     f"predict-mean baseline {obs[s]['baseline_loss_predict_mean']['diff']:+.3f}; shuffle gap ext {obs[s]['ext_gap']['diff']:+.3f} (p {obs[s]['ext_gap']['perm_p']:.2f}), "
                     f"int {obs[s]['int_gap']['diff']:+.3f} (p {obs[s]['int_gap']['perm_p']:.2f})" for s in obs)}
    n1 = w(lambda p: p["network"]["share_centre_u_within_2pct_of_bound"])
    n1c = w(lambda p: p["network"]["share_centre_u_preclip_outside_0_1"])
    n1a = w(lambda p: p["network"]["share_amp_u_within_2pct_of_bound"])
    out["H1b"] = {"supported": bool(n1 > 0.5), "number": f"motor-cortex centre output u[2, joint] (u = clip(pi @ sigmoid(theta) + 0.2 tanh(amod[10 + joint]), 0, 1), bounds [0, 1], pre-clip range [-0.2, 1.2]) within 2 % of a bound for {100 * n1:.1f} % of hold blocks "
                  f"(at the hold-side bound {100 * w(lambda p: p['network']['share_centre_u_at_hold_side_bound']):.1f} %, pre-clip outside [0, 1] {100 * n1c:.1f} %, tanh(amod) saturated > 0.98 {100 * w(lambda p: p['network']['share_centre_amod_tanh_abs_gt_0.98']):.1f} %, "
                  f"prototype-only u mean {w(lambda p: p['network']['centre_prototype_u_mean']):.3f}); amplitude output u[1, joint] within 2 % of a bound {100 * n1a:.1f} %"}
    t = {k: w(lambda p, k=k: p["torque"]["held_joint"][k]) for k in ("share_actuator_at_stall", "share_gravity_toward_stop", "gravity_toward_stop_Nm_mean", "actuator_Nm_mean", "gravity_droop_deg_equiv_kp_mean", "constraint_Nm_mean")}
    ts = w(lambda p: p["torque"]["shoulder"]["share_actuator_at_stall"])
    rin = {s: pooled[s]["torque"]["replay_target_inside_by_5deg"] for s in pooled}
    grav = bool(t["share_gravity_toward_stop"] > 0.5 and t["gravity_droop_deg_equiv_kp_mean"] > 0.5)
    out["H7"] = {"supported": bool(t["share_actuator_at_stall"] > 0.5), "gravity_pushes_into_stop": grav,
                 "number": f"held-joint actuator torque (mean {t['actuator_Nm_mean']:+.2f} N.m, stop-positive) at the {STALL_NM:.2f} N.m stall for {100 * t['share_actuator_at_stall']:.1f} % of hold time (shoulder {100 * ts:.1f} %); gravity torque on the held joint points into the stop "
                           f"{100 * t['share_gravity_toward_stop']:.1f} % of the time, mean {t['gravity_toward_stop_Nm_mean']:+.2f} N.m = {t['gravity_droop_deg_equiv_kp_mean']:+.1f} deg servo droop at kp {KP_NM_RAD:.1f} N.m/rad (the clipped target is 0.5 deg inside the stop); constraint torque {t['constraint_Nm_mean']:+.3f} N.m; "
                           "replay in plain MuJoCo with the target 5 deg inside the stop ends at " + ", ".join(f"seed {s} mean {rin[s]['end_q_deg_mean']:.1f} deg (min {rin[s]['end_q_deg_min']:.1f}, {100 * rin[s]['share_end_within_1deg_of_target']:.0f} % of holds within 1 deg of the 105 deg target)" for s in rin)}
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
