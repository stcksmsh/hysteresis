"""WO45 step 2b (BRAIN_SPEC 7.76.3), report only, nothing adopted. Brain env. Reads controls/q50 (realised q50 + lamp) and the T0 target rows; writes grammar/refine.json and docs/CONTROLS_REFINE_REPORT.md.

    controls_refine.py [WINDOWS_PER_DATASET]     default 300 windows per dataset, seed 45010 (random kept windows, one per file where possible)

1. amplitude (lamp bounding-box diagonal of the token, m) vs speed (vl, lamp RMS speed) vs the combined vigour: Pearson / Spearman, and R^2 of the combined vigour on both.
2. sharpness at 2 / 3 / 4 / 6 Hz on the realised lamp, on the human-retargeted TARGET lamp (forward kinematics of the 100 Hz target rows taken every second row, before guard / spinal / limiter / servo), and on the realised lamp plus white noise
   of sigma 0.01 .. 1 mm per axis (noise model: additive Gaussian, independent per axis and sample, on the 50 Hz lamp position; a 12-bit encoder on a 0.3 m link is about 0.5 mm).
3. pause as occupancy and duration at 2, 4, 8 s: share of pause samples per block, pause-run duration quantiles, Spearman of the per-token pause probability with the block occupancy.
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import controls_lib as C  # noqa: E402
import m3f_report as R  # noqa: E402

B = Path("/secondary/hyst-data/body")
Q50 = B / "controls/q50"
ROOTS = {"finedance": B / "t0/seq/finedance", "aioz": B / "t0/seq/aioz", "phantom": B / "t0_phantom/seq", "motorica": B / "t0_motorica/seq"}
CUTS = (2.0, 3.0, 4.0, 6.0)
SIGMAS_MM = (0.01, 0.03, 0.1, 0.3, 1.0)
SCALES = (2, 4, 8)


def pearson(a, b):
    m = np.isfinite(a) & np.isfinite(b)
    return float(np.corrcoef(a[m], b[m])[0, 1])


def spearman(a, b):
    m = np.isfinite(a) & np.isfinite(b)
    return pearson(rankdata(a[m]), rankdata(b[m]))


def sharp_at(q50, lamp, hz):
    old = C.SHARP_HZ
    C.SHARP_HZ = hz
    try:
        return C.raw_window(q50, lamp)["sharp"]
    finally:
        C.SHARP_HZ = old


def amplitude(lamp):
    p = lamp[:C.NTOK * C.TOK].reshape(C.NTOK, C.TOK, 3)
    return np.linalg.norm(p.max(1) - p.min(1), axis=1)


def runs(mask):
    d = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
    return np.flatnonzero(d == -1) - np.flatnonzero(d == 1)


def one_dataset(ds, n, seed):
    rng = np.random.default_rng(seed)
    files = sorted((Q50 / ds).glob("*.npz"))
    pick = rng.permutation(len(files))
    amp, vl, vig, sh = [], [], [], {k: [] for k in ["real", "target"] + [f"noise{s}" for s in SIGMAS_MM]}
    occ = {s: [] for s in SCALES}
    ptok = {s: [] for s in SCALES}
    dur = []
    got = 0
    for i in pick:
        if got >= n:
            break
        p = files[i]
        z = np.load(p)
        if len(z["win"]) == 0:
            continue
        c = np.load(B / "controls" / ds / p.name)
        t = np.load(ROOTS[ds] / p.name)
        w = int(rng.integers(len(z["win"])))
        q, lamp = z["q50"][w].astype(float), z["lamp"][w]
        a = int(z["win"][w]) * 2000
        tgt = np.asarray(t["targets"], float)[a:a + 2001:2]
        if len(tgt) != 1001:
            continue
        lt = R.fk_points(tgt)[:, 5]
        amp.append(amplitude(lamp))
        vl.append(c["vl"][w])
        vig.append(c["vigour"][w])
        for hz in CUTS:
            for key, l in (("real", lamp), ("target", lt)) + tuple((f"noise{s}", lamp + rng.standard_normal(lamp.shape) * s * 1e-3) for s in SIGMAS_MM):
                sh[key].append((hz, sharp_at(q, l, hz)))
        v = np.linalg.norm(np.gradient(lamp, axis=0) * C.FS, axis=1)
        pm = C.pause_mask(v)[:C.NTOK * C.TOK]
        for s in SCALES:
            L = s * C.FS
            nb = len(pm) // L
            occ[s].append(pm[:nb * L].reshape(nb, L).mean(1))
            ptok[s].append(c["pause_prob"][w][:nb * (L // C.TOK)].reshape(nb, L // C.TOK).mean(1))
        dur += list(runs(pm) / C.FS)
        got += 1
    amp, vl, vig = (np.concatenate(x) for x in (amp, vl, vig))
    out = dict(windows=got, tokens=int(len(amp)))
    za, zs = (np.log(amp + 0.01) - np.log(amp + 0.01).mean()) / np.log(amp + 0.01).std(), (np.log(vl + 0.01) - np.log(vl + 0.01).mean()) / np.log(vl + 0.01).std()
    X = np.stack([za, zs, np.ones_like(za)], 1)
    beta = np.linalg.lstsq(X, vig, rcond=None)[0]
    r2 = 1 - ((vig - X @ beta) ** 2).sum() / ((vig - vig.mean()) ** 2).sum()
    out["amplitude_speed_vigour"] = dict(pearson_amp_speed=pearson(amp, vl), spearman_amp_speed=spearman(amp, vl), pearson_amp_vigour=pearson(amp, vig), spearman_amp_vigour=spearman(amp, vig),
                                         pearson_speed_vigour=pearson(vl, vig), spearman_speed_vigour=spearman(vl, vig), r2_vigour_on_log_amp_and_log_speed=float(r2), beta_log_amp_log_speed=beta[:2].tolist(),
                                         amp_quantiles_m=np.percentile(amp, [5, 25, 50, 75, 95]).tolist(), speed_quantiles=np.percentile(vl, [5, 25, 50, 75, 95]).tolist())
    sharp = {}
    for key, rows in sh.items():
        arr = {}
        for hz in CUTS:
            x = np.concatenate([r[1] for r in rows if r[0] == hz])
            arr[f"{hz:g}Hz"] = dict(median=float(np.nanmedian(x)), p25=float(np.nanpercentile(x, 25)), p75=float(np.nanpercentile(x, 75)), undefined_share=float(np.isnan(x).mean()))
        sharp[key] = arr
    out["sharpness"] = sharp
    pa = {}
    for s in SCALES:
        o, pt = np.concatenate(occ[s]), np.concatenate(ptok[s])
        pa[f"{s}s"] = dict(blocks=int(len(o)), occupancy_mean=float(o.mean()), occupancy_quantiles=np.percentile(o, [50, 75, 90, 99]).tolist(), share_blocks_over_half_paused=float((o > 0.5).mean()),
                           spearman_token_pause_vs_block_occupancy=spearman(pt, o))
    d = np.array(dur)
    pa["pause_runs"] = dict(count=int(len(d)), duration_quantiles_s=np.percentile(d, [10, 50, 90, 99]).tolist() if len(d) else None, share_over_1s=float((d > 1).mean()) if len(d) else None)
    out["pause"] = pa
    return out


def main(n=300):
    res = {ds: one_dataset(ds, n, 45010) for ds in ROOTS}
    (B / "grammar" / "refine.json").write_text(json.dumps(res, indent=1))
    L = ["# Control refinements (WO45 step 2b; report only, nothing adopted)", "",
         "Sample: %d random kept windows per dataset (one per file, seed 45010), realised stage, tokens of 0.5 s; code `scripts/body/controls_refine.py`, numbers in `grammar/refine.json`. Motorica: aggregates only." % n, "",
         "## 1. Vigour split into amplitude and speed", "",
         "Amplitude = diagonal of the lamp's bounding box over the token (m); speed = lamp RMS speed `vl` (m/s); vigour = the combined control. Correlations over tokens (Pearson / Spearman).", "",
         "| dataset | tokens | amp-speed | amp-vigour | speed-vigour | R^2 of vigour on log amp + log speed | amp median m | speed median m/s |", "|---|---|---|---|---|---|---|---|"]
    for ds, r in res.items():
        a = r["amplitude_speed_vigour"]
        L.append(f"| {ds} | {r['tokens']} | {a['pearson_amp_speed']:.2f} / {a['spearman_amp_speed']:.2f} | {a['pearson_amp_vigour']:.2f} / {a['spearman_amp_vigour']:.2f} | {a['pearson_speed_vigour']:.2f} / {a['spearman_speed_vigour']:.2f} | "
                 f"{a['r2_vigour_on_log_amp_and_log_speed']:.3f} | {a['amp_quantiles_m'][2]:.3f} | {a['speed_quantiles'][2]:.3f} |")
    L += ["", "## 2. Sharpness cutoff (median over tokens; undefined share in brackets)", "",
          "`target` = forward kinematics of the human-retargeted target rows (every second 100 Hz row), before guard, spinal layer, limiter and servo. `noise s` = realised lamp plus white Gaussian noise of s mm per axis (50 Hz samples).", ""]
    keys = list(next(iter(res.values()))["sharpness"].keys())
    for ds, r in res.items():
        L += [f"### {ds}", "", "| source | " + " | ".join(f"{h:g} Hz" for h in CUTS) + " |", "|---|" + "---|" * len(CUTS)]
        for k in keys:
            L.append(f"| {k} | " + " | ".join(f"{r['sharpness'][k][f'{h:g}Hz']['median']:.3f} ({r['sharpness'][k][f'{h:g}Hz']['undefined_share']:.2f})" for h in CUTS) + " |")
        L.append("")
    L += ["## 3. Pause as occupancy and duration", "", "| dataset | scale | blocks | mean occupancy | median / p90 / p99 | share of blocks > 0.5 paused | Spearman(token pause prob, block occupancy) |", "|---|---|---|---|---|---|---|"]
    for ds, r in res.items():
        for s in SCALES:
            p = r["pause"][f"{s}s"]
            q = p["occupancy_quantiles"]
            L.append(f"| {ds} | {s} s | {p['blocks']} | {p['occupancy_mean']:.3f} | {q[0]:.2f} / {q[2]:.2f} / {q[3]:.2f} | {p['share_blocks_over_half_paused']:.3f} | {p['spearman_token_pause_vs_block_occupancy']:.2f} |")
    L += ["", "Pause-run durations (s, p10 / p50 / p90 / p99) and share of runs over 1 s: " + "; ".join(
        f"{ds}: {r['pause']['pause_runs']['duration_quantiles_s']} , {r['pause']['pause_runs']['share_over_1s']}" for ds, r in res.items()), "",
        "Nothing in A changes because of this report without a ruling (BRAIN_SPEC 7.76.3)."]
    (HERE.parents[1] / "docs" / "CONTROLS_REFINE_REPORT.md").write_text("\n".join(L) + "\n")
    print("REFINE DONE", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 300)
