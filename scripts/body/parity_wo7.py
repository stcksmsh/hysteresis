"""WO7: M3d's MJX arm (one solver iteration) against full MuJoCo (default iterations), 60 s trajectories, same start pose and same per-step servo targets.

    parity_wo7.py OUT_DIR [--ckpt try1/ckpt.pkl] [--n-per-mode 4]

Targets: M3d spinal generators driven by the try-1 policy on held-out toy episodes (argmax and Gumbel-sampled program choice; the generators do not depend on the
arm, so targets are computed once), plus 2 v47 trajectories (build_v47 set, raw 100 Hz targets). Three arms are stepped from the same state with the same targets
(each applies its own copy of the same limiter): `mjx1` (M3d as used), `mujoco` (arm_sim.ArmSim, default solver iterations; the reference),
`mjxfull` (MJX with the default iterations; separates the solver-iteration effect from MJX-vs-MuJoCo implementation differences).
Descriptors: per 0.5 s block from block 4 (2 s of movement) on, exactly as M3d computes them (window of 2 s at 60 fps from the true joint positions), roll excluded.
Relative descriptor difference |a - b| / max(|b|, 1e-3), b = full MuJoCo.
"""
import argparse
import json
import pickle
import sys
from pathlib import Path

import jax
import jax.numpy as jnp
import mujoco
import numpy as np
from mujoco import mjx

import arm_sim
import make_arm as MA
import m3d
import m3d_jax as J

STEPS = 6000
WINDOWS = {"1s": 100, "10s": 1000, "60s": 6000}
EPS = 1e-3


def m3d_targets(P, toy, idx, mode, key):
    """Pattern-generator targets (E, 6000, 5) deg and start poses (E, 5): block_fn's generator half, no arm."""
    inps = toy.inputs(idx, key)
    q0 = jnp.asarray(m3d.start_poses(len(range(*idx.indices(len(toy.y)))), 4242))

    def block(cs, inp):
        logits, amod, kappa = J.motor_cortex(P, inp["x"])
        pi = J.program_weights(logits, inp["g"], 0.0, mode)
        goal = J.to_command(jnp.clip(pi @ jax.nn.sigmoid(P["theta"]) + J.MOD * jnp.tanh(amod), 0, 1).reshape(4, 5))

        def step(c, k):
            c, t = J.cpg_step(c, goal, inp["phi0"] + inp["om0"] * J.DT * (k + 1), kappa)
            return c, t
        return jax.lax.scan(step, cs, jnp.arange(J.BLOCK))

    def episode(q, inp):
        _, t = jax.lax.scan(block, J.cpg_init(q), inp)
        return t.reshape(-1, 5)
    return np.asarray(jax.jit(jax.vmap(episode))(q0, inps)), np.asarray(q0)


def run_mjx(model_x, q0, tgts):
    """(N, 5), (N, T, 5) -> q, qd (N, T, 5) deg, deg/s after each control step."""
    J.MX = model_x

    def one(q, t):
        d, tgt, tv = J.arm_init(q)

        def step(c, target):
            d, tgt, tv, _ = J.arm_step(*c, target)
            return (d, tgt, tv), (jnp.degrees(d.qpos), jnp.degrees(d.qvel))
        return jax.lax.scan(step, (d, tgt, tv), t)[1]
    q, qd = jax.jit(jax.vmap(one))(jnp.asarray(q0), jnp.asarray(tgts))
    return np.asarray(q), np.asarray(qd)


def run_mujoco(q0, tgts, xml=None):
    Q, QD = np.empty(tgts.shape), np.empty(tgts.shape)
    for i in range(len(tgts)):
        sim = arm_sim.ArmSim(xml)
        sim.reset(q0[i])
        for k, t in enumerate(tgts[i]):
            sim.step(t)
            Q[i, k], QD[i, k] = sim.q_deg, sim.qd_deg
    return Q, QD


def joint_stats(a, b):
    """a, b (N, T, 5) -> {window: {max, rms, per joint (5)}}; max over trajectories and steps of the window, rms pooled."""
    d = np.abs(a - b)
    return {w: {"max": d[:, :n].max((0, 1)).tolist(), "rms": np.sqrt((d[:, :n] ** 2).mean((0, 1))).tolist()} for w, n in WINDOWS.items()}


def block_descriptors(q, q0):
    """q (N, T, 5) deg -> (N, 116, 31) for blocks 4..119 as M3d computes them."""
    pad = np.concatenate([np.broadcast_to(q0[:, None], (len(q), 200, 5)), q], 1)
    win = np.stack([pad[:, 50 * (b + 1):50 * (b + 1) + 201] for b in range(m3d.VALID_FROM, m3d.NB)], 1)       # (N, B, 201, 5)
    f = jax.jit(jax.vmap(jax.vmap(lambda w: J.descriptors(J.window_frames(w)))))
    return np.asarray(f(jnp.asarray(win)))


def desc_stats(a, b):
    r = np.abs(a - b) / np.maximum(np.abs(b), EPS)                                                                 # (N, B, 31)
    return {"rel_median": np.median(r, (0, 1)).tolist(), "rel_p90": np.percentile(r, 90, (0, 1)).tolist(), "rel_max": r.max((0, 1)).tolist(),
            "rel_median_overall": float(np.median(r)), "rel_max_overall": float(r.max())}


def build_inputs(ckpt, n_per_mode):
    toy = m3d.Toy("/secondary/hyst-data/body/m3d/toy.npz")
    P = jax.tree_util.tree_map(jnp.asarray, pickle.loads(Path(ckpt).read_bytes())["P"])
    held = toy.sets["held"]
    tg, q0, names = [], [], []
    for mi, mode in enumerate(("argmax", "sample")):
        t, q = m3d_targets(P, toy, held, mode, jax.random.PRNGKey(7))
        for e in range(n_per_mode):
            ep = e + mi * n_per_mode                                                                    # distinct held-out episodes across the two modes
            tg.append(t[ep]), q0.append(q[ep]), names.append(f"m3d-{mode}-held{ep}")
    v = np.load("/secondary/hyst-data/body/v47set.npz")
    for i in (0, 62):
        tg.append(v["tgt"][i].astype(float)), q0.append(v["tgt"][i][0].astype(float)), names.append(f"v47-{tuple(v['meta'][i])}")
    return np.stack(tg), np.stack(q0), names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--ckpt", default="/secondary/hyst-data/body/m3d/try1/ckpt.pkl")
    ap.add_argument("--n-per-mode", type=int, default=4)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tg, q0, names = build_inputs(a.ckpt, a.n_per_mode)
    print("targets", tg.shape, names, flush=True)
    full = MA.final_xml()
    mfull = mujoco.MjModel.from_xml_string(full)
    print("iterations: mjx1", J.MODEL.opt.iterations, "full", mfull.opt.iterations, "solver", mfull.opt.solver, flush=True)
    r = {"mujoco": run_mujoco(q0, tg)}
    print("mujoco done", flush=True)
    r["mjx1"] = run_mjx(J.MX, q0, tg)
    print("mjx1 done", flush=True)
    r["mjxfull"] = run_mjx(mjx.put_model(mfull), q0, tg)
    print("mjxfull done", flush=True)
    D = {k: block_descriptors(v[0], q0) for k, v in r.items()}
    res = {"names": names, "iterations_full": int(mfull.opt.iterations), "solver": int(mfull.opt.solver)}
    for k in ("mjx1", "mjxfull"):
        res[k + "_vs_mujoco"] = {"q": joint_stats(r[k][0], r["mujoco"][0]), "qd": joint_stats(r[k][1], r["mujoco"][1]), "desc": desc_stats(D[k], D["mujoco"]),
                                 "per_traj_q_max": np.abs(r[k][0] - r["mujoco"][0]).max((1, 2)).tolist()}
    res["mjx1_vs_mjxfull"] = {"q": joint_stats(r["mjx1"][0], r["mjxfull"][0]), "desc": desc_stats(D["mjx1"], D["mjxfull"])}
    (out / "parity.json").write_text(json.dumps(res, indent=1))
    np.savez_compressed(out / "traj.npz", tgt=tg, q0=q0, **{f"{k}_q": v[0].astype(np.float32) for k, v in r.items()})
    print(json.dumps({k: res[k]["q"]["60s"] for k in res if k.endswith("mujoco")}), flush=True)


if __name__ == "__main__":
    sys.exit(main())
