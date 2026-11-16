"""WO47 tables (docs/BEATV_RULES.md) -> docs/BEATV_TABLES.md. Brain env.   beatv_report.py
Motorica rows are aggregates only."""
import glob
import json
import pickle
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
import sys  # noqa: E402
sys.path.insert(0, str(HERE))
import beatv_lib as BL  # noqa: E402

B = Path("/secondary/hyst-data/body")
OUT = B / "beatv"
DOCS = HERE.parents[1] / "docs"
DS = ("finedance", "aioz", "phantom", "motorica")
NB, SEED = 2000, 47101
PUB = 0.2120


def boot(x, stat=np.nanmedian):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) < 3:
        return stat(x) if len(x) else np.nan, np.nan, np.nan
    rng = np.random.default_rng(SEED)
    b = [stat(x[rng.integers(len(x), size=len(x))]) for _ in range(NB)]
    return stat(x), np.percentile(b, 2.5), np.percentile(b, 97.5)


def fmt(t, d=3):
    return "-" if not np.isfinite(t[0]) else f"{t[0]:.{d}f} [{t[1]:.{d}f}, {t[2]:.{d}f}]"


def per_group(rs, f):
    g = {}
    for r in rs:
        v = f(r)
        if v is not None and np.isfinite(v):
            g.setdefault(r["group"], []).append(v)
    return np.array([np.mean(v) for v in g.values()])


def raw_tables():
    rs = [json.load(open(p)) for p in sorted(glob.glob(str(OUT / "raw/*.json")))]
    L = [f"### V2 raw FineDance ground truth ({len(rs)} files, whole sequences, sigma 0.1 s)", "",
         f"Published: BAS 0.2120 (Lodge, CVPR 2024, Table 1 / 4). Far = outside [{PUB * .75:.3f}, {PUB * 1.25:.3f}].", "",
         "| kinematic beats from | music beats | variant | BAS mean [95 %] | median | shifted-beat chance mean [95 %] | BAS - chance [95 %] | inside +-25 % of 0.2120 |", "|---|---|---|---|---|---|---|---|"]
    for kn, kd in (("angular-speed proxy (main, deviation)", "proxy"), ("approximate FK (deviation)", "fk")):
        for gn, gd in (("librosa", "lib"), ("project grid", "proj")):
            for mode, md in (("sum over music beats (code reading, main)", "music"), ("sum over kinematic beats (paper text)", "kin")):
                v = np.array([r[f"bas_{kd}_{gd}_{md}"] for r in rs])
                c = np.array([r[f"chance_{kd}_{gd}_{md}"] for r in rs])
                m = boot(v, np.mean)
                L.append(f"| {kn} | {gn} | {mode} | {fmt(m)} | {np.median(v):.3f} | {fmt(boot(c, np.mean))} | {fmt(boot(v - c, np.mean))} | {'yes' if PUB * .75 <= m[0] <= PUB * 1.25 else 'no'} |")
    L += ["", f"Median kinematic beats per file {np.median([r['n_kin_proxy'] for r in rs]):.0f} (proxy), librosa beats {np.median([r['n_lib'] for r in rs]):.0f}, duration {np.median([r['dur'] for r in rs]):.0f} s.", ""]
    k = np.array([r["v3_best_k"] for r in rs])
    c = np.array([r["v3_cmax"] for r in rs])
    z = np.array([r["v3_z"] for r in rs])
    d = np.array([r["v3_k_first"] - r["v3_k_last"] for r in rs if "v3_k_first" in r])
    ex = np.array([r["v3_cmax"] > r["v3_null95"] for r in rs])
    L += ["### V3 raw per-file sync (whole-body motion energy vs onset envelope, shifts -1..+1 s, step 33 ms; k > 0 = music after motion)", "",
          f"- best offset (frames), quantiles 5/25/50/75/95: {np.percentile(k, [5, 25, 50, 75, 95]).round(1).tolist()}; share |k| <= 1 frame: {np.mean(np.abs(k) <= 1):.3f}; share |k| <= 3 frames (0.1 s): {np.mean(np.abs(k) <= 3):.3f}",
          f"- strength: max correlation median {np.median(c):.3f} (quartiles {np.percentile(c, 25):.3f}, {np.percentile(c, 75):.3f}); z against 200 circular shifts median {np.median(z):.2f}; share of files above their own 95th percentile of shifted maxima {ex.mean():.3f} (5 % expected by chance)",
          f"- drift (best offset first minute minus last minute, {len(d)} files >= 150 s): quantiles 5/25/50/75/95 {np.percentile(d, [5, 25, 50, 75, 95]).round(1).tolist()}; share |drift| > 2 frames {np.mean(np.abs(d) > 2):.3f}", ""]
    return L, rs


def v3_curve():
    f = OUT / "v3.json"
    if not f.exists():
        return []
    r = json.loads(f.read_text())
    L = ["### V3 mean cross-correlation curves (mean over files of c(k))", ""]
    for key, nm, kmax, fs in (("raw", "raw FineDance motion energy", 30, 30), ("V1_lamp", "realised V1 lamp speed", 50, 50), ("V2_lamp", "realised V2 lamp speed", 50, 50), ("V1_joints", "realised V1 summed |joint velocity|", 50, 50), ("V2_joints", "realised V2 summed |joint velocity|", 50, 50)):
        cs = np.array([v[key]["c"] for v in r.values() if key in v])
        ks = np.array([v[key]["k"] for v in r.values() if key in v])
        cm = np.array([v[key]["cmax"] for v in r.values() if key in v])
        z = np.array([v[key]["z"] for v in r.values() if key in v])
        mean = cs.mean(0)
        sel = list(range(0, 2 * kmax + 1, max(1, kmax // 10)))
        L += [f"#### {nm} ({len(cs)} files): best offset quantiles 5/25/50/75/95 (ms) {(np.percentile(ks, [5, 25, 50, 75, 95]) / fs * 1000).round(0).tolist()}, share |offset| <= 50 ms {np.mean(np.abs(ks) / fs <= 0.05):.3f}, max corr median {np.median(cm):.3f}, z median {np.median(z):.2f}", "",
              "| shift ms | " + " | ".join(f"{(i - kmax) / fs * 1000:.0f}" for i in sel) + " |", "|---|" + "---|" * len(sel), "| mean c(k) | " + " | ".join(f"{mean[i]:+.3f}" for i in sel) + " |", ""]
    return L


def real_tables():
    rs = []
    for ds in DS:
        for p in sorted((OUT / "real" / ds).glob("*.pkl")):
            rs.append(pickle.loads(p.read_bytes()))
    L = ["### V2 realised stage: BAS (sigma 0.1 s; music-beat sum main), mean over song groups [95 % boot]", "",
         "| dataset | variant | kinematic beats | grid | BAS [95 %] | shifted-beat chance [95 %] | BAS - chance [95 %] | BAS (kinematic-beat sum) | chance |", "|---|---|---|---|---|---|---|---|---|"]
    for ds in DS:
        for var in ("V1", "V2"):
            sub = [r for r in rs if r["ds"] == ds and r["var"] == var]
            if not sub:
                continue
            for sn in ("lamp", "j0", "j1", "j2", "j3", "j4"):
                for gn in ("proj", "lib"):
                    b = per_group(sub, lambda r: r["bas"][(sn, gn, "music")][0])
                    c = per_group(sub, lambda r: r["bas"][(sn, gn, "music")][1])
                    bk = per_group(sub, lambda r: r["bas"][(sn, gn, "kin")][0])
                    ck = per_group(sub, lambda r: r["bas"][(sn, gn, "kin")][1])
                    L.append(f"| {ds} | {var} | {sn} | {gn} | {fmt(boot(b, np.mean))} | {fmt(boot(c, np.mean))} | {fmt(boot(b - c, np.mean))} | {np.mean(bk):.3f} | {np.mean(ck):.3f} |")
    L += ["", "### V1 local phase locking (windows of 8 beats, hop 2): per-song median of (R real - mean R of the x1.13 / x0.87 period controls); dataset value = median over song groups [95 % boot]; second excess against permuted-interval controls", "",
          "| dataset | variant | events | grid | songs | windows (median per seq) | median excess vs period controls | median excess vs permuted intervals | mean R real | mean R control | chance R | share windows R > control | median line-fit residual ms | whole-song R (project grid) |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for ds in DS:
        for var in ("V1", "V2"):
            sub = [r for r in rs if r["ds"] == ds and r["var"] == var]
            for e in ("E1", "E2", "E4", "E5", "E3_0"):
                for gn in ("proj", "lib"):
                    S = [(r["group"], r["v1"].get((e, gn))) for r in sub]
                    S = [(g, s) for g, s in S if s]
                    if not S:
                        continue

                    def pg(key):
                        d = {}
                        for g, s in S:
                            d.setdefault(g, []).append(s[key])
                        return np.array([np.mean(v) for v in d.values()])
                    ex = pg("exc_med")
                    nw = np.median([s["n_win"] for g, s in S])
                    wr = per_group(sub, lambda r: r["whole_R"][e])
                    L.append(f"| {ds} | {var} | {e} | {gn} | {len(ex)} | {nw:.0f} | {fmt(boot(ex))} | {fmt(boot(pg('exc_perm_med')))} | {pg('R').mean():.3f} | {pg('ctl').mean():.3f} | {pg('chance').mean():.3f} | {pg('share_gt').mean():.3f} | {np.median(pg('resid_med')) * 1000:.1f} | {np.nanmean(wr):.3f} |")
    return L, rs


def raw_v1(rawrs):
    """raw FineDance kinematic-speed minima in local windows"""
    L = ["### V1 raw FineDance mocap (kinematic-speed minima, 30 fps)", "", "| grid | songs | median excess vs period controls [95 %] | median excess vs permuted intervals [95 %] | mean R | mean control R | share windows R > control | whole-song R |", "|---|---|---|---|---|---|---|---|"]
    for gn, gd in (("project", "proj"), ("librosa", "lib")):
        ex, exp_, R_, C_, sh, wr = [], [], [], [], [], []
        for r in rawrs:
            key = r["key"]
            g = np.array(json.loads((B / "t1b/cortex/beats" / f"{key}.json").read_text())["beats"]) if gd == "proj" else np.array(json.loads((OUT / "librosa" / f"{key}.json").read_text())["beats"])
            w = BL.local_windows(np.array(r["raw_minima"]), g, np.random.default_rng(47104))
            if not w:
                continue
            Rr = np.array([x["R"] for x in w])
            c = (np.array([x["R113"] for x in w]) + np.array([x["R087"] for x in w])) / 2
            ex.append(np.median(Rr - c))
            exp_.append(np.median(Rr - np.array([x["Rperm"] for x in w])))
            R_.append(Rr.mean())
            C_.append(c.mean())
            sh.append((Rr > c).mean())
            t = np.array(r["raw_minima"])
            t = t[(t >= g[0]) & (t < g[-1])]
            ph = ((t - g[:-1][np.clip(np.searchsorted(g, t) - 1, 0, len(g) - 2)]) / np.diff(g)[np.clip(np.searchsorted(g, t) - 1, 0, len(g) - 2)])
            wr.append(abs(np.exp(2j * np.pi * ph).mean()))
        L.append(f"| {gn} | {len(ex)} | {fmt(boot(ex))} | {fmt(boot(exp_))} | {np.mean(R_):.3f} | {np.mean(C_):.3f} | {np.mean(sh):.3f} | {np.mean(wr):.3f} |")
    return L + [""]


def main():
    L = ["# Beat verification tables (WO47; generated by `scripts/body/beatv_report.py`, do not edit)", ""]
    rl, rawrs = raw_tables()
    L += rl + v3_curve()
    real, _ = real_tables()
    L += real + [""] + raw_v1(rawrs)
    (DOCS / "BEATV_TABLES.md").write_text("\n".join(L))
    print("tables written")


if __name__ == "__main__":
    main()
