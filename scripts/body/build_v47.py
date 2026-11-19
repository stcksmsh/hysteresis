"""M1 out-of-distribution set (BRAIN_SPEC §7.13 D2): the 18 v47 arm trajectories (3 danced songs x 6 hexagon arms, 100 Hz joint CSVs from
`hyst score-csv --hz 100 --agent N`, mode Off) replayed in physics as servo targets (no pattern generator), split into whole 60 s segments
(the partial tail of each song is dropped). Also reports how much the raw targets exceed M0's speed / acceleration limits and the joint ranges
(the sim's limiter and range clip act on them; the trajectories are kept either way).

    python build_v47.py CSV_DIR OUT.npz
Provisional servo model (Feetech STS3215 12 V assumed; kp, rotor inertia, damping 1.5, acceleration share 0.25).
"""
import json
import sys

import numpy as np

import arm_sim
import babble          # noqa: F401  (obs layout is shared)

SONGS = ("ic", "fy", "pr")
SEG = 6000


def load_csv(path):
    rows = [l for l in open(path) if l[0] != "#" and not l.startswith("time_s")]
    return np.array([[float(v) for v in r.split(",")][1:] for r in rows])


def replay(tgt):
    """Physics replay of (n, 5) degree targets at 100 Hz from the first pose. -> obs (n, 15), applied-target (n, 5)."""
    sim = arm_sim.ArmSim()
    sim.reset(tgt[0])
    obs, applied = np.empty((len(tgt), 15), np.float32), np.empty((len(tgt), 5), np.float32)
    for k, t in enumerate(tgt):
        p = sim.step(t)
        obs[k] = np.concatenate([p["pos_deg"], p["vel_deg_s"], p["load_nm"]])
        applied[k] = sim.tgt
    return obs, applied


def excess(tgt):
    """Fraction of 100 Hz steps whose raw target change exceeds the limits, per joint (speed, acceleration), and outside the joint ranges."""
    v = np.abs(np.diff(tgt, axis=0)) * 100
    a = np.abs(np.diff(tgt, 2, axis=0)) * 100 ** 2
    return {"speed": (v > arm_sim.LIM_V).mean(0).tolist(), "accel": (a > arm_sim.LIM_A).mean(0).tolist(),
            "range": ((tgt < arm_sim.LO) | (tgt > arm_sim.HI)).mean(0).tolist(),
            "max_speed_x": (v.max(0) / arm_sim.LIM_V).tolist(), "max_accel_x": (a.max(0) / arm_sim.LIM_A).tolist()}


def main(csv_dir, out):
    O, T, meta, rep = [], [], [], {}
    for si, s in enumerate(SONGS):
        for arm in range(6):
            tgt = load_csv(f"{csv_dir}/{s}-{arm}.csv")
            obs, applied = replay(tgt)
            rep[f"{s}-{arm}"] = {**excess(tgt), "applied_vs_raw_rms_deg": np.sqrt(((applied - tgt) ** 2).mean(0)).tolist(), "steps": len(tgt)}
            for g in range(len(tgt) // SEG):
                sl = slice(g * SEG, (g + 1) * SEG)
                O.append(obs[sl])
                T.append(tgt[sl].astype(np.float32))
                meta.append((si, arm, g))
    np.savez(out, obs=np.stack(O), tgt=np.stack(T), meta=np.array(meta))
    json.dump(rep, open(out.replace(".npz", ".excess.json"), "w"), indent=1)
    print(out, len(O), "segments")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
