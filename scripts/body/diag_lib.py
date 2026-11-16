"""WO46 part 1 (docs/DIAG_RULES.md): posture/gesture swaps of token dicts (c1, c2, v, p). Pure numpy."""
import numpy as np

GESTURE = ("c1", "c2", "v")


def swap(posture_src, gesture_src):
    """token dict with the posture entries `p` of posture_src and the gesture codes (c1, c2, v) of gesture_src, slot by slot"""
    n = len(gesture_src["c1"])
    assert len(posture_src["p"]) == n, "token counts differ"
    d = {k: np.asarray(gesture_src[k]) for k in GESTURE}
    d["p"] = np.asarray(posture_src["p"])
    return d
