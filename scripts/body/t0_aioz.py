"""WO37 Builder B: AIOZ-GDANCE validity check (BRAIN_SPEC 7.56.10 / 7.59.2.4). Report-only; no retarget, split or tokens.
Commands (body env, cores 14-17):  python -u t0_aioz.py ref   -> FineDance reference percentiles (aioz_ref.json; push BEFORE `check`)
                                   python -u t0_aioz.py check -> measures + prune of every AIOZ person-sequence -> aioz_measures.json, aioz_keep.json
The .pkl files are untrusted: only `load_pkl` (restricted unpickler: numpy arrays and plain containers) ever opens them.
"""
import io
import json
import pickle
import sys
import wave
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

sys.path.insert(0, str(Path(__file__).resolve().parent))
import retarget as RT  # noqa: E402
import v3_lib as L  # noqa: E402

AIOZ = Path("/secondary/hyst-data/datasets/aioz/data")
OUT = Path("/secondary/hyst-data/body/t0")
FROZEN_DEG_S = 1.0
_ALLOWED = {("numpy", "ndarray"), ("numpy", "dtype"), ("numpy.core.multiarray", "_reconstruct"), ("numpy._core.multiarray", "_reconstruct"),
            ("numpy.core.multiarray", "scalar"), ("numpy._core.multiarray", "scalar")}


class _Restricted(pickle.Unpickler):
    def find_class(self, module, name):
        if (module, name) in _ALLOWED:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f"refused global {module}.{name}")


def load_pkl(path):
    """restricted unpickle: numpy arrays + dict/list/tuple/str/number only; anything else (os.system, eval, ...) raises UnpicklingError"""
    with open(path, "rb") as f:
        return _Restricted(io.BytesIO(f.read()), encoding="latin1").load()


def aa_to_mats(aa):
    """(T, 72) or (T, 66) axis-angle -> (T, 22, 3, 3) local rotations (first 22 SMPL joints = FineDance's SMPL-H body joints, same order)"""
    aa = np.asarray(aa, float)
    return Rotation.from_rotvec(aa.reshape(len(aa), -1, 3)[:, :22].reshape(-1, 3)).as_matrix().reshape(-1, 22, 3, 3)


def mats_to_aa(R):
    return Rotation.from_matrix(R.reshape(-1, 3, 3)).as_rotvec().reshape(len(R), 66)


def to_retarget_input(aa, trans):
    """adapter: AIOZ (axis-angle (T, 72), trans (T, 3)) -> the retarget code's motion array (T, 315): cols 0:3 translation, 3: 52 x 6D (first two ROWS of each matrix); hand joints identity"""
    T = len(aa)
    out = np.zeros((T, 315))
    out[:, :3] = trans
    r6 = np.tile(np.array([1.0, 0, 0, 0, 1, 0]), (T, 52, 1))
    r6[:, :22] = aa_to_mats(aa).reshape(T, 22, 9)[:, :, :6]
    out[:, 3:] = r6.reshape(T, 312)
    return out


def from_retarget_input(a):
    """inverse for the 22 body joints: (T, 315) -> axis-angle (T, 66), trans (T, 3)"""
    a = np.asarray(a, float)
    return mats_to_aa(RT.six_to_matrix(a[:, 3:].reshape(-1, 52, 6)[:, :22])), a[:, :3]


def fk_mats(R, trans):
    """local rotations (T, 22, 3, 3) + root translation (T, 3) -> world joint positions (T, 22, 3); same skeleton and pelvis height as v3_lib.fk"""
    G = np.zeros(R.shape)
    P = np.zeros((len(R), 22, 3))
    for j in range(22):
        p = L.PARENT[j]
        if p < 0:
            G[:, j] = R[:, j]
            P[:, j] = trans + np.array([0.0, L.PELVIS_H, 0.0])
        else:
            G[:, j] = G[:, p] @ R[:, j]
            P[:, j] = P[:, p] + np.einsum("tij,j->ti", G[:, p], L.OFF[j])
    return P


def measures_raw(R, trans, fps):
    """p3 = power share > 3 Hz (Step A measure) of the two human end points (right wrist rel. right shoulder; head rel. pelvis);
    ang (T-1, 22) per-joint angular speed deg/s; root (T-1,) root speed m/s; P world positions"""
    P = fk_mats(R, trans)
    p3 = [L.pos_measures(P[:, 21] - P[:, 17], fps)["p_gt3"], L.pos_measures(P[:, 15] - P[:, 0], fps)["p_gt3"]]
    rel = np.einsum("tjik,tjil->tjkl", R[:-1], R[1:])          # R_t^T R_{t+1}
    ang = np.degrees(np.arccos(np.clip((np.trace(rel, axis1=2, axis2=3) - 1) / 2, -1, 1))) * fps
    root = np.linalg.norm(np.diff(trans, axis=0), axis=1) * fps
    return dict(p3=p3, ang=ang, root=root, P=P)


def reference():
    """FineDance (30 fps): p95 over sequences of the two end-point p3; p99.9 over all frames of per-joint angular speed and of root speed"""
    OUT.mkdir(parents=True, exist_ok=True)
    p3, angs, roots = [], [], []
    for f in sorted((L.FD / "motion").glob("*.npy")):
        a = np.load(f).astype(np.float64)
        m = measures_raw(RT.six_to_matrix(a[:, 3:].reshape(-1, 52, 6)[:, :22]), a[:, :3], 30.0)
        p3.append(m["p3"]); angs.append(m["ang"]); roots.append(m["root"])
    p3 = np.array(p3)
    jp = np.percentile(np.concatenate(angs), 99.9, axis=0)
    live = jp >= FROZEN_DEG_S                      # joints still in FineDance (p99.9 < 1 deg/s: feet, identity) are excluded from measure (2): any AIOZ motion there would trip a zero threshold
    rp = float(np.percentile(np.concatenate(roots), 99.9))
    ref = dict(n_sequences=len(p3), fps=30, p3_wrist_p95=float(np.percentile(p3[:, 0], 95)), p3_head_p95=float(np.percentile(p3[:, 1], 95)),
               p3_wrist_median=float(np.median(p3[:, 0])), p3_head_median=float(np.median(p3[:, 1])), joint_ang_p999=jp.tolist(), live_joints=np.flatnonzero(live).tolist(), root_speed_p999=rp,
               # context: what the same rule would do to FineDance itself
               fd_share_any_joint_over_p999_median=float(np.median([(a[:, live] > jp[live]).any(1).mean() for a in angs])),
               fd_share_root_over_p999_median=float(np.median([(r > rp).mean() for r in roots])),
               fd_prune_share_rule2=float(np.mean([(a[:, live] > jp[live]).any(1).mean() > 0.01 for a in angs])),
               fd_prune_share_all_rules=float(np.mean([bool((p3[i] > np.percentile(p3, 95, axis=0)).any() or (angs[i][:, live] > jp[live]).any(1).mean() > 0.01
                                                     or (roots[i] > rp).mean() > 0.01 or (angs[i].max(1) < FROZEN_DEG_S).mean() > 0.2) for i in range(len(angs))])),
               fd_share_joint_p95=float(np.percentile([(a[:, live] > jp[live]).any(1).mean() for a in angs], 95)),
               fd_share_root_p95=float(np.percentile([(r > rp).mean() for r in roots], 95)),
               fd_frozen_share_median=float(np.median([(a.max(1) < FROZEN_DEG_S).mean() for a in angs])),
               fd_frozen_share_max=float(max((a.max(1) < FROZEN_DEG_S).mean() for a in angs)))
    (OUT / "aioz_ref.json").write_text(json.dumps(ref, indent=1))
    print(json.dumps(ref, indent=1))


def wav_secs(path):
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def check():
    ref = json.loads((OUT / "aioz_ref.json").read_text())
    jp = np.array(ref["joint_ang_p999"]); live = np.array(ref["live_joints"])
    meta = {}
    for sp in ("train", "val", "test"):
        for ln in (AIOZ / f"{sp}_labels.csv").read_text().splitlines()[1:]:
            c = ln.split(",")
            meta[c[0]] = (c[1] if len(c) > 1 else "", c[2] if len(c) > 2 else "")
    seqs = []
    for p in sorted((AIOZ / "motions_smpl").glob("*.pkl")):
        d = load_pkl(p)
        poses, trans = np.asarray(d["smpl_poses"], float), np.asarray(d["root_trans"], float)
        seqs.append((p.stem, poses, trans, poses.shape[1] / wav_secs(AIOZ / "musics" / f"{p.stem}.wav")))
    vals, cnt = np.unique(np.round([s[3] for s in seqs], 1), return_counts=True)
    mode = float(vals[cnt.argmax()])
    rows, keep, keep_cal = [], [], []
    for n, poses, trans, fps in seqs:
        for pi in range(poses.shape[0]):
            T = poses.shape[1]
            r = dict(id=n, person=pi, frames=T, fps_derived=fps, genre=meta.get(n, ("", ""))[0], style=meta.get(n, ("", ""))[1])
            if abs(fps - mode) / mode > 0.02:
                r["drop"] = ["fps"]; rows.append(r); continue
            R = aa_to_mats(poses[pi])
            m = measures_raw(R, trans[pi], fps)
            r.update(p3_wrist=m["p3"][0], p3_head=m["p3"][1], share_ang_over=float((m["ang"][:, live] > jp[live]).any(1).mean()),
                     share_root_over=float((m["root"] > ref["root_speed_p999"]).mean()), share_frozen=float((m["ang"].max(1) < FROZEN_DEG_S).mean()),
                     mean_head_height=float(m["P"][:, 15, 1].mean()), head_height_drift_m_per_s=float(np.polyfit(np.arange(T) / fps, m["P"][:, 15, 1], 1)[0]))
            why = [k for k, bad in (("hf_power", r["p3_wrist"] > ref["p3_wrist_p95"] or r["p3_head"] > ref["p3_head_p95"]), ("joint_speed", r["share_ang_over"] > 0.01),
                                    ("root_jump", r["share_root_over"] > 0.01), ("frozen", r["share_frozen"] > 0.20)) if bad]
            r["drop"] = why
            # calibrated variant (FOR USER): the 1 % thresholds of (2)/(3) replaced by FineDance's own p95 of the same shares (the literal 1 % prunes ~58 % of FineDance itself)
            r["drop_cal"] = [k for k in why if k not in ("joint_speed", "root_jump")] + [k for k, bad in (("joint_speed", r["share_ang_over"] > max(0.01, ref["fd_share_joint_p95"])),
                             ("root_jump", r["share_root_over"] > max(0.01, ref["fd_share_root_p95"]))) if bad]
            if not why:
                keep.append(dict(id=n, person=pi, frames=T, fps=fps, style=r["style"]))
            if not r["drop_cal"]:
                keep_cal.append(dict(id=n, person=pi, frames=T, fps=fps, style=r["style"]))
            rows.append(r)
    (OUT / "aioz_measures.json").write_text(json.dumps(dict(mode_fps=mode, rows=rows)))
    (OUT / "aioz_keep.json").write_text(json.dumps(keep))
    (OUT / "aioz_keep_calibrated.json").write_text(json.dumps(keep_cal))
    print(f"calibrated variant kept {len(keep_cal)} ({len(keep_cal) / len(rows):.1%})")
    print(f"mode fps {mode}; person-sequences {len(rows)}; kept {len(keep)} ({len(keep) / len(rows):.1%})")


if __name__ == "__main__":
    {"ref": reference, "check": check}[sys.argv[1]]()
