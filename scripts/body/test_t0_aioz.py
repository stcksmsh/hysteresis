"""tests for t0_aioz: python -m pytest scripts/body/test_t0_aioz.py (body env)"""
import os
import pickle
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t0_aioz as A  # noqa: E402
import v3_lib as L  # noqa: E402


class _Evil:
    def __reduce__(self):
        return (os.system, ("echo pwned > /dev/null",))


def test_restricted_unpickler_refuses_crafted_pickle(tmp_path):
    p = tmp_path / "evil.pkl"
    p.write_bytes(pickle.dumps({"smpl_poses": _Evil()}))
    with pytest.raises(pickle.UnpicklingError):
        A.load_pkl(p)


def test_restricted_unpickler_loads_numpy_dict(tmp_path):
    p = tmp_path / "ok.pkl"
    p.write_bytes(pickle.dumps({"smpl_poses": np.arange(6.0).reshape(1, 2, 3), "n": 2}))
    assert A.load_pkl(p)["smpl_poses"].shape == (1, 2, 3)


def test_adapter_round_trip_on_finedance():
    a = np.load(sorted((L.FD / "motion").glob("*.npy"))[0]).astype(np.float64)[:600]
    aa, tr = A.from_retarget_input(a)
    b = A.to_retarget_input(aa, tr)
    d6 = np.abs(b[:, 3:].reshape(-1, 52, 6)[:, :22] - a[:, 3:].reshape(-1, 52, 6)[:, :22]).max()
    assert d6 < 1e-4 and np.abs(b[:, :3] - a[:, :3]).max() == 0   # 6D of a (near-)orthonormal source; axis-angle in between
    aa2, _ = A.from_retarget_input(b)
    assert np.abs(A.aa_to_mats(aa2) - A.aa_to_mats(aa)).max() < 1e-9
    print("max abs 6D diff", d6)


def test_fk_matches_v3_lib():
    seq = sorted((L.FD / "motion").glob("*.npy"))[0].stem
    a = np.load(L.FD / "motion" / f"{seq}.npy").astype(np.float64)[:200]
    from retarget import six_to_matrix
    P = A.fk_mats(six_to_matrix(a[:, 3:].reshape(-1, 52, 6)[:, :22]), a[:, :3])
    assert np.abs(P - L.fk(seq, 0, 199)[0]).max() < 1e-9
