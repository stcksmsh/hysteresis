"""WO42 source adapters: PhantomDance json and Motorica BVH -> the (rot, trans) the T0 chain takes from FineDance (t0_lib.load_rot).
Rules and mapping: docs/T0_PHANTOM_RULES.md. Body env (numpy + scipy). No data access except the path given. Output frame = SMPL-H frame of FineDance
(right-handed, y up, subject faces +z, subject's left = +x; local rotations, rest pose T with right arm along -x)."""
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation as Rot

import t0_lib as T

SMPL_PARENT = (-1, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9, 12, 13, 14, 16, 17, 18, 19, 20, 21)    # SMPL 24 joints; PhantomDance bone_name order is the same
SMPL_NAMES = ("Pelvis", "L_Hip", "R_Hip", "Spine1", "L_Knee", "R_Knee", "Spine2", "L_Ankle", "R_Ankle", "Spine3", "L_Foot", "R_Foot", "Neck", "L_Collar", "R_Collar", "Head",
              "L_Shoulder", "R_Shoulder", "L_Elbow", "R_Elbow", "L_Wrist", "R_Wrist", "L_Hand", "R_Hand")
FLIP_X = np.diag([-1.0, 1.0, 1.0])                                  # Unity (left-handed, x right) -> SMPL (right-handed, x = subject's left): negate x; R' = F R F


def phantom_rot(path):
    """PhantomDance motion json -> (rot dict joint -> (T,3,3) local rotations for t0_lib.ROT_JOINTS, translation (T,3) m, n_frames).
    rotations are WORLD quaternions (x, y, z, w) in Unity axes; local = parent_world^T world after the x flip. A malformed frame (list length != 24)
    ends the sequence (file 000: last of 4106 frames has 12 entries; its root_positions has 6408 rows, the first T are kept)."""
    d = json.loads(Path(path).read_text())
    assert list(d["bone_name"]) == list(SMPL_NAMES), d["bone_name"]
    rl = d["rotations"]
    n = next((i for i, f in enumerate(rl) if len(f) != 24), len(rl))
    q = np.asarray(rl[:n], np.float64)                              # (T, 24, 4)
    G = FLIP_X @ Rot.from_quat(q.reshape(-1, 4)).as_matrix().reshape(n, 24, 3, 3) @ FLIP_X
    L = G.copy()
    for j in range(1, 24):
        L[:, j] = np.swapaxes(G[:, SMPL_PARENT[j]], 1, 2) @ G[:, j]
    trans = np.asarray(d["root_positions"][:n], np.float64) * np.array([-1.0, 1.0, 1.0])
    return {j: L[:, j] for j in T.ROT_JOINTS}, trans, n


MOTORICA_MAP = {0: "Hips", 3: "Spine", 9: "Spine1", 12: "Neck", 15: "Head", 13: "LeftShoulder", 16: "LeftArm", 18: "LeftForeArm", 20: "LeftHand",
                14: "RightShoulder", 17: "RightArm", 19: "RightForeArm", 21: "RightHand"}              # SMPL joint 6 (spine2) has no Motorica joint: identity


def read_bvh(path):
    """-> (names, channel order per joint, data (frames, channels), frame time). Only what the Motorica files use: ROOT/JOINT/End Site, 6 channels at the root, 3 elsewhere."""
    text = Path(path).read_text().split("\n")
    names, chans = [], {}
    i = 0
    while not text[i].startswith("MOTION"):
        t = text[i].split()
        if t and t[0] in ("ROOT", "JOINT"):
            names.append(t[1])
        if t and t[0] == "CHANNELS":
            chans[names[-1]] = t[2:2 + int(t[1])]
        i += 1
    n = int(text[i + 1].split()[1])
    ft = float(text[i + 2].split()[2])
    data = np.array([list(map(float, ln.split())) for ln in text[i + 3:i + 3 + n]])
    return names, chans, data, ft


def motorica_rot(path, fps_out=30):
    """Motorica BVH (120 fps, cm, Y up, ZXY channel order) -> (rot dict as phantom_rot, translation (T,3) in m at fps_out, n_frames).
    Decimated by taking every (fps_in/fps_out)-th frame. Local rotation = Rz Rx Ry in the listed channel order; BVH rest pose = T-pose with the axes of the SMPL rest pose."""
    names, chans, data, ft = read_bvh(path)
    step = round(1 / ft / fps_out)
    assert abs(step * fps_out * ft - 1) < 1e-3, ft
    data = data[::step]
    col, c = {}, 0
    for nm in names:
        col[nm] = c
        c += len(chans.get(nm, []))
    assert c == data.shape[1]
    rot = {}
    for j, nm in MOTORICA_MAP.items():
        ch = chans[nm]                                              # 6 channels at every joint in some files (positions constant), 3 elsewhere: take the rotation channels by name
        idx = [k for k, x in enumerate(ch) if x.endswith("rotation")]
        order = "".join(ch[k][0] for k in idx)                      # e.g. "ZXY"
        assert len(idx) == 3 and idx == list(range(idx[0], idx[0] + 3)), ch
        rot[j] = Rot.from_euler(order, data[:, col[nm] + idx[0]:col[nm] + idx[0] + 3], degrees=True).as_matrix()
    rot[6] = np.broadcast_to(np.eye(3), rot[3].shape).copy()
    trans = data[:, col["Hips"]:col["Hips"] + 3] / 100.0
    return {j: rot[j] for j in T.ROT_JOINTS}, trans, len(data)
