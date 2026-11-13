"""WO35 Q2 (report only): why does the realised shoulder of C04_V2 sit about 10 deg off the command in seconds 8-12 of the clip?
Checks: command vs limiter output vs realised (same time base), the guard, the end stops, column/floor contact in the window, gravity sag (the same clip re-simulated with gravity off, and a static
servo-hold test with MuJoCo's own gravity torque against the position servo's stiffness). Run (body env): python -u v3_q2.py -> /secondary/hyst-data/body/retarget_look/v3/q2.json
"""
import json
import sys
from pathlib import Path

import mujoco
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jitter_diag as J  # noqa: E402
import retarget as RT  # noqa: E402
import retarget_run as RR  # noqa: E402

OUT = Path("/secondary/hyst-data/body/retarget_look")


def sim_with(G, gravity=True, record_contacts=False):
    """FX.simulate_goals loop with optional gravity switch and per-substep contact bookkeeping; returns q50 (n, 5), contact geom names seen in the window"""
    import dialstudy as D
    import make_arm_v2p as P
    import motornet as M
    import retarget_limiter as FX
    m = P.make_model(1.0, 1.5)
    if not gravity:
        m.opt.gravity[:] = 0
    d = mujoco.MjData(m)
    d.qpos[:] = np.radians(G[0])
    d.ctrl[:] = np.radians(G[0])
    mujoco.mj_forward(m, d)
    tgt, tv = G[0].copy(), np.zeros(5)
    lo_r, hi_r = np.radians(D.LO), np.radians(D.HI)
    nw = round(M.WARM_S / M.DT)
    rows, seen, torques = [], {}, []
    for i, g in enumerate(G):
        tgt, tv = FX.step(tgt, tv, g)
        d.ctrl[:] = np.radians(tgt)
        for _ in range(5):
            mujoco.mj_step(m, d)
            qc = np.clip(d.qpos, lo_r, hi_r)
            d.qvel[:] = np.where(qc != d.qpos, 0.0, d.qvel)
            d.qpos[:] = qc
            for k in range(d.ncon):
                n = tuple(sorted((mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, d.contact[k].geom1) or str(d.contact[k].geom1),
                                  mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, d.contact[k].geom2) or str(d.contact[k].geom2))))
                seen[n] = seen.get(n, 0) + 1
        if i >= nw and (i - nw) % 2 == 0:
            rows.append(np.degrees(d.qpos))
            torques.append(float(d.qfrc_bias[1]))                                   # gravity + Coriolis generalised force on the shoulder
    return np.array(rows), seen, np.array(torques), m


def main():
    import dialstudy as D
    import make_arm_v2p as P
    import motornet as M
    import retarget_limiter as FX
    RR.patch_gates()
    picks = {p["clip"]: p for p in json.loads((OUT / "work" / "picks.json").read_text())["picks"]}
    c = picks["C04"]
    v = RR.human(c["seq"])[1]
    y = RT.to_commands(RT.referenced(v, round(c["start_s"] * RT.FPS)), "V2")
    G0 = RT.to_100hz(y, c["start_s"] - RR.PRE_S, RR.SHOW_S + RR.PRE_S)
    G, gshare = P.guard(G0)
    nw = round(RR.PRE_S * 100)
    L = FX.limiter_out(G)
    q, seen, tau, model = sim_with(G, True)
    qg, _, _, _ = sim_with(G, False)
    shown = J.read_csv(OUT / "work" / "C04_V2.csv")
    t = np.arange(len(q)) / 50.0
    w = (t >= 8) & (t <= 12)
    cmd50, lim50 = G[nw::2][:len(q)], L[nw::2][:len(q)]
    held = (np.abs(G - G0).max(1) > 0)[nw:]
    th = np.radians(np.array([0, 1, 1, 1, 1]) * 0)
    # servo stiffness and gravity torque at the window's mean pose
    kp = float(model.actuator_gainprm[1, 0])
    pose = np.mean(q[w], axis=0)
    d = mujoco.MjData(model)
    d.qpos[:] = np.radians(pose)
    mujoco.mj_forward(model, d)
    grav = float(d.qfrc_bias[1])                                                       # static gravity torque on the shoulder joint at that pose (N m)
    res = dict(
        rebuilt_matches_shown_csv_max_abs_deg=float(np.abs(q - shown).max()),
        window_s=[8, 12],
        shoulder_deg=dict(command_mean=float(cmd50[w, 1].mean()), limiter_out_mean=float(lim50[w, 1].mean()), realised_mean=float(q[w, 1].mean()),
                          realised_minus_command_mean=float((q[w, 1] - cmd50[w, 1]).mean()), realised_minus_command_min_max=[float((q[w, 1] - cmd50[w, 1]).min()), float((q[w, 1] - cmd50[w, 1]).max())],
                          realised_minus_limiter_mean=float((q[w, 1] - lim50[w, 1]).mean()), limiter_minus_command_mean=float((lim50[w, 1] - cmd50[w, 1]).mean()),
                          limiter_minus_command_abs_max=float(np.abs(lim50[w, 1] - cmd50[w, 1]).max())),
        full_clip_realised_minus_command_mean_deg=float((q[:, 1] - cmd50[:, 1]).mean()),
        gravity_off=dict(realised_minus_command_mean_in_window=float((qg[w, 1] - cmd50[w, 1]).mean()), full_clip_mean=float((qg[:, 1] - cmd50[:, 1]).mean()), max_abs_in_window=float(np.abs(qg[w, 1] - cmd50[w, 1]).max())),
        guard=dict(share_of_frames_held_whole_clip=gshare, frames_held_in_window=int(held[800:1200].sum())),
        end_stops=dict(shoulder_range_deg=[float(q[w, 1].min()), float(q[w, 1].max())], limit_deg=[-110, 110], min_distance_to_limit_deg=float(110 - np.abs(q[w, 1]).max())),
        contacts_seen_by_geom_pair_over_the_whole_clip=[{"pair": list(k), "substeps": v} for k, v in seen.items()],
        servo=dict(kp_Nm_per_rad=kp, stall_Nm=float(model.actuator_forcerange[1, 1]), static_gravity_torque_shoulder_Nm_at_window_mean_pose=grav,
                   sag_deg_if_gravity_over_kp=float(np.degrees(grav / kp)), window_mean_pose_deg=pose.tolist()),
        gravity_torque_shoulder_Nm_in_window=dict(mean=float(tau[w].mean()), min=float(tau[w].min()), max=float(tau[w].max())))
    (OUT / "v3" / "q2.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
