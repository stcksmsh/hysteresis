"""WO14A (BRAIN_SPEC 7.28 condition): end-stop events of a --hard-clip run, computed from the saved evaluation rollouts (100 Hz joint positions, `rollouts/{name}_{mode}_4.npz`). Provisional servo model
(Feetech STS3215 12 V assumed).

The hard stop (m3f_jax.arm_step, cfg "clip") sets a joint that passed its range to exactly the limit and zeroes its speed, so a saved position sitting on +-110 deg (within 1e-6 deg) is a
control step in which the stop acted (the held target is 0.5 deg inside the range, so a joint is on the limit only when it was clipped). Per episode and joint:
  steps_at_limit  control steps (of 6000) with the joint on the limit;   events  onsets: a step on the limit whose previous step was not.
Hand acceleration and hand jerk (hand = last FK point; np.gradient, at 50 Hz as (e'1), and at the full 100 Hz) over each episode, and inside +-0.05 s of every event: p99 and max of the
magnitudes, per episode and pooled, plus per event (episode, joint, time, max acceleration and max jerk inside its window).
    m3f_endstop.py RUNDIR [RUNDIR ...]    each RUNDIR holds rollouts/ (the try) or controls/rollouts/; writes RUNDIR/endstop.json; prints a table.
"""
import json
import sys
from pathlib import Path

import numpy as np

import m3f_report as R

LIMIT_DEG, TOL = 110.0, 1e-6
JOINTS = {1: "shoulder", 2: "elbow", 3: "wrist_bend"}
WIN_S = 0.05


def derivs(P, hz):
    v = np.gradient(P, axis=0) * hz
    a = np.gradient(v, axis=0) * hz
    j = np.gradient(a, axis=0) * hz
    return np.linalg.norm(a, axis=1), np.linalg.norm(j, axis=1)


def episode(q):
    """q (T, 5) deg at 100 Hz -> dict."""
    P = R.fk_points(q)[:, 5]
    on = {n: np.abs(np.abs(q[:, j]) - LIMIT_DEG) < TOL for j, n in JOINTS.items()}
    ev = {n: np.flatnonzero(m & ~np.concatenate([[False], m[:-1]])) for n, m in on.items()}
    out = {"steps_at_limit": {n: int(m.sum()) for n, m in on.items()}, "events": {n: int(len(i)) for n, i in ev.items()}, "event_steps": {n: i.tolist() for n, i in ev.items()}}
    allev = np.unique(np.concatenate([i for i in ev.values()] + [np.zeros(0, int)])).astype(int)
    for hz, stride in ((100, 1), (50, 2)):
        a, jk = derivs(P[::stride], float(hz))
        w = int(round(WIN_S * hz))
        idx = np.unique(np.concatenate([np.arange(max(0, e // stride - w), min(len(a), e // stride + w + 1)) for e in allev])) if len(allev) else np.zeros(0, int)
        r = {"all": {"acc_p99": float(np.percentile(a, 99)), "acc_max": float(a.max()), "jerk_p99": float(np.percentile(jk, 99)), "jerk_max": float(jk.max())}}
        r["window"] = ({"n": int(len(idx)), "acc_p99": float(np.percentile(a[idx], 99)), "acc_max": float(a[idx].max()), "jerk_p99": float(np.percentile(jk[idx], 99)), "jerk_max": float(jk[idx].max())}
                       if len(idx) else None)
        out[f"hz{hz}"] = r
        out[f"_acc{hz}"], out[f"_jerk{hz}"], out[f"_stride{hz}"] = a, jk, stride
    return out


def per_event(q_ep, ep, e_idx, name):
    rows = []
    for n, steps in e_idx["event_steps"].items():
        for s in steps:
            row = {"episode": ep, "joint": n, "step": int(s), "t_s": s / 100.0}
            for hz in (100, 50):
                st = e_idx[f"_stride{hz}"]
                w = int(round(WIN_S * hz))
                lo, hi = max(0, s // st - w), min(len(e_idx[f"_acc{hz}"]), s // st + w + 1)
                row[f"acc_max_hz{hz}"] = float(e_idx[f"_acc{hz}"][lo:hi].max())
                row[f"jerk_max_hz{hz}"] = float(e_idx[f"_jerk{hz}"][lo:hi].max())
            rows.append(row)
    return rows


def analyse(rolldir, name, mode):
    q = np.load(Path(rolldir) / f"{name}_{mode}_4.npz")["q"]
    q = q.reshape(q.shape[0], -1, 5)
    eps, events = [], []
    for k, e in enumerate(q):
        r = episode(e)
        events += per_event(e, k, r, name)
        eps.append({kk: v for kk, v in r.items() if not kk.startswith("_")})
    ev_total = {n: int(sum(e["events"][n] for e in eps)) for n in JOINTS.values()}
    steps_total = {n: int(sum(e["steps_at_limit"][n] for e in eps)) for n in JOINTS.values()}
    summ = {"events_total": ev_total, "events_per_episode_mean": {n: ev_total[n] / len(eps) for n in ev_total}, "steps_at_limit_share": {n: steps_total[n] / (len(eps) * q.shape[1]) for n in steps_total},
            "episodes_with_event": int(sum(any(e["events"][n] for n in e["events"]) for e in eps)), "episodes": len(eps)}
    for hz in (100, 50):
        have = [e for e in eps if e[f"hz{hz}"]["window"]]
        pool = lambda key, part: float(np.mean([e[f"hz{hz}"][part][key] for e in have])) if have else None
        summ[f"hz{hz}"] = {"episodes_with_window": len(have), **{f"mean_{part}_{key}": pool(key, part) for part in ("all", "window") for key in ("acc_p99", "acc_max", "jerk_p99", "jerk_max")},
                           "max_window_acc": max((e[f"hz{hz}"]["window"]["acc_max"] for e in have), default=None), "max_all_acc": max(e[f"hz{hz}"]["all"]["acc_max"] for e in eps)}
    return {"per_episode": eps, "per_event": events, "summary": summ}


def main():
    for d in map(Path, sys.argv[1:]):
        res = {}
        for name in sorted({p.name.rsplit("_", 2)[0] for p in (d / "rollouts").glob("*_4.npz")}):
            res[name] = {mode: analyse(d / "rollouts", name, mode) for mode in ("argmax", "sample")}
        (d / "endstop.json").write_text(json.dumps(res, indent=1))
        for name, r in res.items():
            for mode, x in r.items():
                s = x["summary"]
                print(f"{d.name}/{name} {mode}: events/episode {({k: round(v, 2) for k, v in s['events_per_episode_mean'].items()})} at-limit share {({k: round(v, 4) for k, v in s['steps_at_limit_share'].items()})} "
                      f"episodes with event {s['episodes_with_event']}/{s['episodes']}")
                for hz in (50, 100):
                    h = s[f'hz{hz}']
                    if h["episodes_with_window"]:
                        print(f"    {hz} Hz hand acceleration p99 / max (window vs episode): {h['mean_window_acc_p99']:.2f} / {h['mean_window_acc_max']:.2f} vs {h['mean_all_acc_p99']:.2f} / {h['mean_all_acc_max']:.2f} m/s2;"
                              f" jerk p99 / max {h['mean_window_jerk_p99']:.0f} / {h['mean_window_jerk_max']:.0f} vs {h['mean_all_jerk_p99']:.0f} / {h['mean_all_jerk_max']:.0f} m/s3")


if __name__ == "__main__":
    main()
