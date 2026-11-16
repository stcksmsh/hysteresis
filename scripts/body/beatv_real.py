"""WO47 steps V2 (realised) and V1 (docs/BEATV_RULES.md sections 1 and 3) on the WO46 whole-sequence realised motion. Brain env.   beatv_real.py [PROCS]
Per sequence (V1 and V2 copies, four datasets) -> beatv/real/<dataset>/<name>.pkl: BAS (lamp and joints, project and librosa grids, music/kin variants, shifted-beat chance) and V1 window statistics
(events E1, E2, E4, E5, E3 yaw; both grids). Resumable; per-file errors logged to beatv/real_failed.txt."""
import json
import multiprocessing as mp
import pickle
import sys
import zlib
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "brain"))
sys.path.insert(0, str(HERE.parent))
import beatv_lib as BL  # noqa: E402
import controls_stats as CS  # noqa: E402
import metric_lib as M  # noqa: E402

B = Path("/secondary/hyst-data/body")
OUT = B / "beatv"
EVENTS = ["E1", "E2", "E4", "E5", "E3_0"]
_c = {}


def consts():
    if "c" not in _c:
        import metric_run as R
        A, p90, _ = R.consts()
        _c["c"] = (A, p90, R.lamp_p90(), R.beats_path)
    return _c["c"]


def summarise(w):
    """window dicts -> per-sequence summary"""
    if not w:
        return None
    R = np.array([x["R"] for x in w])
    c = (np.array([x["R113"] for x in w]) + np.array([x["R087"] for x in w])) / 2
    p = np.array([x["Rperm"] for x in w])
    return dict(n_win=len(w), R=float(R.mean()), ctl=float(c.mean()), perm=float(p.mean()), exc_med=float(np.median(R - c)), exc_perm_med=float(np.median(R - p)), share_gt=float((R > c).mean()),
                resid_med=float(np.median([x["resid"] for x in w])), vec=complex(np.mean([x["vec"] for x in w])), n_ev_med=float(np.median([x["n"] for x in w])),
                chance=float(np.mean([np.sqrt(np.pi) / (2 * np.sqrt(x["n"])) for x in w])))


def run_one(args):
    ds, path = args
    dst = OUT / "real" / ds / (path.stem + ".pkl")
    if dst.exists():
        return path.name, "skip"
    try:
        A, p90, P, beats_path = consts()
        lk = CS.lane_key(path.name)
        lf = OUT / "librosa" / f"{lk}.json"
        if not lf.exists() or not beats_path(lk).exists():
            return path.name, "no grid"
        z = np.load(path)
        q50, lamp = z["q50"].astype(float), z["lamp"].astype(float)
        grids = dict(proj=np.array(json.loads(beats_path(lk).read_text())["beats"], float), lib=np.array(json.loads(lf.read_text())["beats"], float))
        if min(len(g) for g in grids.values()) < 12:
            return path.name, "few beats"
        dur = len(q50) / 50.0
        rng = np.random.default_rng(47104 + zlib.crc32(path.name.encode()))
        res = dict(ds=ds, name=path.name, lk=lk, group=str(z["group"]), split=str(z["split"]), var=path.stem.split("__")[1][:2], dur=dur, n_beats={k: len(v) for k, v in grids.items()})
        # V2 realised: kinematic beats = minima of the smoothed lamp speed and of each joint's |angular velocity|
        speeds = {"lamp": np.linalg.norm(np.gradient(lamp, axis=0) * 50, axis=1)}
        for j in range(5):
            speeds[f"j{j}"] = np.abs(np.gradient(q50[:, j]) * 50)
        bas = {}
        for sn, sp in speeds.items():
            kb = BL.kin_beats(sp, 50)
            for gn, g in grids.items():
                for mode in ("music", "kin"):
                    bas[(sn, gn, mode)] = (BL.bas(g, kb, dur, mode=mode), BL.bas_chance(g, kb, dur, rng, mode=mode))
        res["bas"] = bas
        # V1: events (WO46 definitions) against local lines
        ev = M.events(q50, lamp, A, p90, P)
        v1 = {}
        whole = {}
        for e in EVENTS:
            t = ev[e]
            for gn, g in grids.items():
                v1[(e, gn)] = summarise(BL.local_windows(t, g, rng))
            tt = t[(t >= grids["proj"][0]) & (t < grids["proj"][-1])]
            whole[e] = float(M.resultant(M.phases(tt, grids["proj"], "beat"))[0]) if len(tt) >= 30 else np.nan
        res["v1"], res["whole_R"] = v1, whole
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_suffix(".tmp")
        tmp.write_bytes(pickle.dumps(res))
        tmp.replace(dst)
        return path.name, "ok"
    except Exception as e:
        with open(OUT / "real_failed.txt", "a") as f:
            f.write(f"{ds} {path.name} {type(e).__name__}: {e}\n")
        return path.name, "failed"


def main(procs=6):
    consts()
    jobs = [(ds, p) for ds in CS.DS for p in sorted((B / "metric/q50" / ds).glob("*.npz"))]
    cnt = {}
    with mp.get_context("spawn").Pool(procs) as pool:
        for i, (name, st) in enumerate(pool.imap_unordered(run_one, jobs, chunksize=2)):
            cnt[st] = cnt.get(st, 0) + 1
            if i % 100 == 0:
                print(i, "/", len(jobs), name, st, cnt, flush=True)
    print("REAL DONE", cnt, flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 6)
