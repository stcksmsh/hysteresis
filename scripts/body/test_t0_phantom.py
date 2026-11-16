"""WO42 adapter tests (body env, no data): PhantomDance world-quaternion -> local SMPL rotations; Motorica BVH Euler order and decimation."""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation as Rot

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t0_phantom as P  # noqa: E402


def _json(tmp, world):
    p = Path(tmp) / "m.json"
    p.write_text(json.dumps(dict(bone_name=list(P.SMPL_NAMES), root_positions=np.zeros((len(world), 3)).tolist(), rotations=world.tolist())))
    return p


def test_identity_world_is_identity_local():
    q = np.tile([0, 0, 0, 1.0], (4, 24, 1))
    with tempfile.TemporaryDirectory() as t:
        rot, trans, n = P.phantom_rot(_json(t, q))
    assert n == 4 and all(np.allclose(r, np.eye(3)) for r in rot.values())


def test_local_is_parent_inverse_times_world_after_x_flip():
    rng = np.random.default_rng(0)
    q = Rot.random(3 * 24, random_state=1).as_quat().reshape(3, 24, 4)
    with tempfile.TemporaryDirectory() as t:
        rot, _, _ = P.phantom_rot(_json(t, q))
    G = P.FLIP_X @ Rot.from_quat(q.reshape(-1, 4)).as_matrix().reshape(3, 24, 3, 3) @ P.FLIP_X
    for j in (9, 14, 17, 19, 21):                                          # chain world = parent world x local
        assert np.allclose(G[:, P.SMPL_PARENT[j]] @ rot[j], G[:, j], atol=1e-9)
    assert rng is not None


def test_x_flip_matches_quaternion_rule():
    r = Rot.random(5, random_state=2)
    m = P.FLIP_X @ r.as_matrix() @ P.FLIP_X
    x, y, z, w = r.as_quat().T
    assert np.allclose(Rot.from_quat(np.stack([x, -y, -z, w], 1)).as_matrix(), m, atol=1e-9)


def test_malformed_frame_ends_sequence():
    q = [[[0, 0, 0, 1.0]] * 24] * 5 + [[[0, 0, 0, 1.0]] * 12]
    with tempfile.TemporaryDirectory() as t:
        p = Path(t) / "m.json"
        p.write_text(json.dumps(dict(bone_name=list(P.SMPL_NAMES), root_positions=[[0, 0, 0]] * 9, rotations=q)))
        rot, trans, n = P.phantom_rot(p)
    assert n == 5 and len(trans) == 5 and len(rot[0]) == 5


def test_bvh_euler_order_and_decimation():
    names = ["Hips", "Spine", "Spine1", "Neck", "Head", "LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand", "RightShoulder", "RightArm", "RightForeArm", "RightHand"]
    hier = "HIERARCHY\n"
    for i, nm in enumerate(names):
        hier += (f"ROOT {nm}\n" if i == 0 else f"JOINT {nm}\n") + "{\nOFFSET 0 0 0\n" + ("CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation\n" if i == 0 else "CHANNELS 3 Zrotation Xrotation Yrotation\n")
        hier += "}\n"
    frames = 9
    row = [0.0, 100.0, 0.0] + [10.0, 20.0, 30.0] + [0.0, 0.0, 0.0] * (len(names) - 1)
    body = "MOTION\nFrames: %d\nFrame Time: %.7f\n" % (frames, 1 / 120) + "\n".join(" ".join(map(str, row)) for _ in range(frames)) + "\n"
    with tempfile.TemporaryDirectory() as t:
        p = Path(t) / "a.bvh"
        p.write_text(hier + body)
        rot, trans, n = P.motorica_rot(p)
    assert n == 3                                                          # frames 0, 4, 8 of 9
    assert np.allclose(rot[0][0], Rot.from_euler("ZXY", [10, 20, 30], degrees=True).as_matrix())
    assert np.allclose(rot[6], np.eye(3)) and np.allclose(trans[0], [0, 1.0, 0])
