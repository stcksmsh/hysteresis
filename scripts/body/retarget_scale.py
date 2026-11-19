"""WO32B: the one scale step. Pools every FineDance sequence (frames from 5 s on), per variant and joint p2/p98 -> mid, half, s; writes docs/RETARGET_SCALE.json.
Joint angles only: nothing rendered or viewed. Rules (c). Run: python -u retarget_scale.py
"""
import json
import sys

import numpy as np

import retarget as RT

files = sorted((RT.ROOT / "motion").glob("*.npy"))
pool = {"V1": [], "V2": []}
det_bad, elbow_med, nwin = 0, [], 0
for k, p in enumerate(files):
    rot = RT.load_rotations(p)
    for j, Rm in rot.items():                                            # sanity: orthonormal rotations
        det_bad += int(np.abs(np.linalg.det(Rm) - 1).max() > 1e-3)
    v1, v2 = RT.human_angles(rot)
    n = round(RT.WIN_S * RT.FPS)
    for i in range(round(RT.REF_S * RT.FPS), len(v1) - n + 1, round(RT.STRIDE_S * RT.FPS)):
        pool["V1"].append(RT.referenced(v1, i)[i:i + n + 1]); pool["V2"].append(RT.referenced(v2, i)[i:i + n + 1])
        nwin += 1
    elbow_med.append(np.median(v1[:, 2]))
    if k % 40 == 0:
        print(k, p.name, flush=True)
out = {"note": "pooled p2-p98 over all 20 s windows (starts every 5 s from 5 s) of all FineDance sequences, yaw and twist relative to the window start; y = centre + s (x - mid) (shoulder: centre - s (x - mid)); rules (c)",
       "centre": RT.CENTRE.tolist(), "target_half": RT.TARGET_HALF.tolist(), "windows": nwin, "sequences": len(files), "frames": int(sum(len(a) for a in pool["V1"]))}
for var in ("V1", "V2"):
    X = np.concatenate(pool[var])
    p2, p98 = np.percentile(X, 2, axis=0), np.percentile(X, 98, axis=0)
    half = (p98 - p2) / 2
    out[var] = dict(p2=p2.tolist(), p98=p98.tolist(), mid=((p2 + p98) / 2).tolist(), half=half.tolist(), s=(RT.TARGET_HALF / half).tolist())
out["sanity"] = dict(non_orthonormal_joint_files=det_bad, v1_elbow_flexion_median_of_medians=float(np.median(elbow_med)),
                     v1_elbow_flexion_p2_p98=[out["V1"]["p2"][2], out["V1"]["p98"][2]])
json.dump(out, open(RT.SCALE_FILE, "w"), indent=1)
print(json.dumps({k: out[k] for k in ("sequences", "windows", "frames", "sanity")}, indent=1))
for var in ("V1", "V2"):
    print(var, "mid", np.round(out[var]["mid"], 1), "half", np.round(out[var]["half"], 1), "s", np.round(out[var]["s"], 3))
