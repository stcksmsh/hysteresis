import pickle
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aist_load import load_pkl  # noqa: E402


def test_numpy_dict_loads():
    d = {"keypoints3d": np.arange(12.0).reshape(2, 2, 3)}
    out = load_pkl(pickle.dumps(d))
    assert np.array_equal(out["keypoints3d"], d["keypoints3d"])


class _Evil:
    def __reduce__(self):
        import os
        return os.system, ("echo pwned",)


def test_other_globals_refused():
    with pytest.raises(pickle.UnpicklingError):
        load_pkl(pickle.dumps(_Evil()))
