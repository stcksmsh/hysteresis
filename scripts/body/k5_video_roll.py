"""WO12 step 2: roll the K5 policy over each whole danced song as ONE continuous episode, ARGMAX. Body env (/secondary/hyst-env/body). Provisional servo model. One arm.

    k5_video_roll.py run [--songs a,b] [--policy best.pkl] [--lanes DIR] [--out DIR]     resume-safe: a song whose npz and csv exist is skipped
    k5_video_roll.py test                                                                 (also: python -m unittest test_k5_video)

The episode is the K5 training window's own recipe, extended: lanes -> arcsinh on arousal and surprisal (m3d.transform_state) -> causal 30 s running z-score (m3e.running_z) over the
WHOLE song from its start -> the cortex's inputs exactly as m3e.ToyE.inputs builds them (block b reads block b - 1) -> m3e_jax.block_fn in chunks of CB = 8 blocks (the K5 eval's own
chunk size), the whole carry (arm, MJX physics, CPG, cerebellum, closed-loop features, proprioception buffers) passed from chunk to chunk and never reset. Start pose: m3d.start_poses(1, 4242)
(the check's held-out start seed). ARGMAX program choice: the Gumbel input is never read, so no key is needed.

The joint trajectory is not an output of block_fn. `chunk_q` calls the unchanged m3e_jax.block_fn and reads that block's 50 joint rows from the new carry's `buf` (full[-200:], the last
50 rows are the block's own): same computation, no copy of the K5 code. Row i of the 50 Hz CSV is the pose at t = i / 50 s: row 0 the start pose, row i the pose after control step 2 i - 1.
A song's last partial block (T % 50 frames) is dropped by the lanes, so the CSV is 0.5 s x blocks long; the video holds the last pose until the audio ends.
"""
import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

import arm_sim
import k5_train as T
import m3d
import m3e
import m3e_jax as M

K5 = T.K5
DANCED = K5 / "danced"
POLICY = K5 / "run1" / "best.pkl"
SONGS = ("instant-crush", "five-years", "presence")
CB = 8
START_SEED = 4242


def load_policy(path=POLICY):
    d = pickle.loads(Path(path).read_bytes())
    return jax.tree_util.tree_map(jnp.asarray, d["P"]), d["stats"]


def episode_inputs(y, phi_end, omega):
    """Raw lanes of one song (nb, 8), (nb,), (nb,) -> the per-block inputs dict (E = 1) and the causal z-scored target yz (1, nb, 8)."""
    ty = m3d.transform_state(np.asarray(y, float)[None])
    yz = m3e.running_z(ty)
    sh = lambda a: np.concatenate([np.zeros_like(a[:, :1]), a[:, :-1]], 1)
    prev = sh(yz)
    x = np.concatenate([prev, prev - sh(prev)], -1)
    nb = x.shape[1]
    return {"x": jnp.asarray(x), "phi0": jnp.asarray(sh(np.asarray(phi_end, float)[None])), "om0": jnp.asarray(sh(np.asarray(omega, float)[None])),
            "g": jnp.zeros((1, nb, 8))}, yz


def make_chunk_q(C):
    def blk(P, c, i):
        c2, o = M.block_fn(C, P, "argmax", 0.0, c, i)
        return c2, {**o, "q": c2["buf"][-m3d.J.BLOCK:]}

    def chunk(P, carry, inps):
        return jax.vmap(lambda c, i: jax.lax.scan(lambda cc, ii: blk(P, cc, ii), c, i))(carry, inps)
    return jax.jit(chunk)


def rollout_song(fn, C, P, inps, start_seed=START_SEED, cb=CB, log=None):
    """One continuous episode over all the blocks of `inps`. -> dict of arrays (nb, ...) incl. q (nb, 50, 5) and q0 (5,)."""
    nb = inps["x"].shape[1]
    q0 = m3d.start_poses(1, start_seed)
    carry = jax.vmap(lambda q: M.init_carry(q, C))(jnp.asarray(q0))
    outs = []
    t0 = time.time()
    for c0 in range(0, nb, cb):
        carry, o = fn(P, carry, m3d.take(inps, c0, c0 + cb))
        outs.append({k: np.asarray(v)[0] for k, v in o.items()})
        if log and (c0 // cb) % 10 == 0:
            log(f"  block {c0}/{nb} ({time.time() - t0:.0f} s)")
    r = {k: np.concatenate([o[k] for o in outs], 0) for k in outs[0]}
    r["q0"] = q0[0]
    return r


def csv_rows(q, q0):
    """q (nb, 50, 5) degrees at 100 Hz after each control step -> (25 nb + 1, 5) rows at 50 Hz, row 0 = the start pose."""
    q100 = q.reshape(-1, 5)
    return np.concatenate([q0[None], q100[1::2]], 0)


def run_song(name, fn, C, P, lanes_dir, out, log):
    npz, csv = out / f"{name}.k5.npz", out / f"{name}.k5.csv"
    if npz.exists() and csv.exists():
        log(f"{name}: exists, kept")
        return
    z = np.load(Path(lanes_dir) / f"{name}.npz")
    inps, yz = episode_inputs(z["y"], z["phi_end"], z["omega"])
    log(f"{name}: {inps['x'].shape[1]} blocks ({inps['x'].shape[1] / 2:.0f} s)")
    r = rollout_song(fn, C, P, inps, log=log)
    rows = csv_rows(r["q"], r["q0"])
    csv.write_text(arm_sim.csv_text(rows, hz=50, name=f"{name}.k5"))
    tmp = Path(str(npz) + ".tmp.npz")
    np.savez_compressed(tmp, yz=yz[0], rows50=rows, **r)
    tmp.replace(npz)
    log(f"{name}: wrote {csv.name} ({len(rows)} rows, {(len(rows) - 1) / 50:.2f} s) and {npz.name}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=("run",))
    ap.add_argument("--songs", default=",".join(SONGS))
    ap.add_argument("--policy", default=str(POLICY))
    ap.add_argument("--lanes", default=str(DANCED / "lanes"))
    ap.add_argument("--out", default=str(DANCED))
    a = ap.parse_args()
    T.install_signals()
    t0 = time.time()
    log = lambda s: print(f"[{time.time() - t0:7.0f}s] {s}", flush=True)
    T.wait_mains(log)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    C = M.load_cb()
    P, _ = load_policy(a.policy)
    fn = make_chunk_q(C)
    for name in a.songs.split(","):
        T.check()
        T.wait_mains(log)
        run_song(name, fn, C, P, a.lanes, out, log)


if __name__ == "__main__":
    try:
        main()
    except T.Interrupted:
        print("interrupted; finished songs are kept, rerun the same command to resume", flush=True)
