"""WO46 part 2 tables (docs/METRIC_RULES.md) from metric/results -> docs/METRIC_TABLES.md (+ metric/summary.json). Brain env.   metric_report.py
Motorica rows are aggregates over song groups (no per-file values)."""
import json
import pickle
from pathlib import Path

import numpy as np
from scipy.stats import rankdata, spearmanr

HERE = Path(__file__).resolve().parent
B = Path("/secondary/hyst-data/body")
OUT = B / "metric"
DOCS = HERE.parents[1] / "docs"
DS = ("finedance", "aioz", "phantom", "motorica")
LEV = ("beat", "half_beat", "half_time", "bar")
TYPES = ["E1", "E2", "E4", "E5"] + [f"E3_{j}" for j in range(5)]
JN = ["yaw", "shoulder", "elbow", "wrist bend", "wrist roll"]
NB = 2000
LAGS_MS = np.arange(-250, 251, 25)
DELAYS = np.arange(-4, 5)


def load():
    rs = []
    for ds in DS:
        for p in sorted((OUT / "results" / ds).glob("*.pkl")):
            r = pickle.loads(p.read_bytes())
            r["var"] = r["name"].split("__")[1][:2]
            rs.append(r)
    return rs


def by_group(rs, f):
    """f(result) -> array or None; mean over a group's sequences -> (groups, array (G, ...))"""
    g = {}
    for r in rs:
        v = f(r)
        if v is not None:
            g.setdefault(r["group"], []).append(v)
    ks = sorted(g)
    return ks, np.array([np.nanmean(np.array(g[k], float), 0) for k in ks]) if ks else np.zeros((0,))


def boot(x, seed=46101, stat=lambda a: np.nanmean(a, 0)):
    """x (G, ...) -> (estimate, lo, hi) by resampling groups"""
    x = np.asarray(x, float)
    if len(x) < 2:
        return stat(x) if len(x) else np.nan, np.nan, np.nan
    rng = np.random.default_rng(seed)
    b = np.array([stat(x[rng.integers(len(x), size=len(x))]) for _ in range(NB)])
    return stat(x), np.nanpercentile(b, 2.5, 0), np.nanpercentile(b, 97.5, 0)


def fmt(t, d=3):
    e, lo, hi = t
    return "-" if not np.isfinite(e) else f"{e:.{d}f} [{lo:.{d}f}, {hi:.{d}f}]"


def sel(rs, ds, var):
    return [r for r in rs if r["ds"] == ds and r["var"] == var]


# ---------------------------------------------------------------------------------------------------- A: phase
def phase_tables(rs):
    L = []
    for var in ("V1", "V2"):
        for st in ("ALL", "PASS"):
            for ds in DS:
                sub = sel(rs, ds, var)
                for li, lev in enumerate(LEV):
                    L += [f"#### {ds} {var} {st}: {lev}" + (" (provisional)" if lev in ("half_time", "bar") else ""), "",
                          "| event | groups | events/min | R real [95 %] | R - shuffled-IBI [95 %] | R - other-song grids [95 %] | pooled preferred phase | spread of per-song phases (R) | chance R ~ 1/sqrt(n) |", "|---|---|---|---|---|---|---|---|---|"]
                    for ty in TYPES:
                        def f(r, k=0):
                            x = r["phase"].get((st, ty))
                            return None if x is None or x["real"] is None or x["n"] < 30 else x
                        gk, Rr = by_group(sub, lambda r: (lambda x: None if x is None else np.array([x["real"][0][li], x["real"][1][li], x["n"]]))(f(r)))
                        _, Rs = by_group(sub, lambda r: (lambda x: None if x is None or x.get("shuf") is None else x["shuf"][0][li])(f(r)))
                        _, Rd = by_group(sub, lambda r: (lambda x: None if x is None or x.get("donor") is None else x["donor"][0][li])(f(r)))
                        if not len(gk):
                            L.append(f"| {ty} | 0 | - | - | - | - | - | - | - |")
                            continue
                        ev = float(np.median([r["numbers"]["rate"][ty] for r in sub]))
                        Rg = Rr[:, 0]
                        vec = Rr[:, 0] * np.exp(2j * np.pi * Rr[:, 1])
                        pref = (np.angle(np.nanmean(vec)) / (2 * np.pi)) % 1
                        spread = float(abs(np.nanmean(np.exp(2j * np.pi * Rr[:, 1]))))
                        exs = Rg - Rs if len(Rs) == len(Rg) else np.full(len(Rg), np.nan)
                        exd = Rg - Rd if len(Rd) == len(Rg) else np.full(len(Rg), np.nan)
                        L.append(f"| {ty if ty[:2] != 'E3' else 'E3 ' + JN[int(ty[3])]} | {len(gk)} | {ev:.0f} | {fmt(boot(Rg))} | {fmt(boot(exs))} | {fmt(boot(exd))} | {pref:.2f} | {spread:.2f} | {1 / np.sqrt(np.nanmedian(Rr[:, 2])):.3f} |")
                    L.append("")
    return L


def lag_tables(rs):
    L = []
    for var in ("V1", "V2"):
        for ds in DS:
            sub = sel(rs, ds, var)
            for gi, grid in ((2, "beat"), (3, "half-beat")):
                L += [f"#### {ds} {var} ALL: hit rate H(L), +-50 ms window, grid {grid}; cell = real [excess over shuffled-IBI, 95 %]; every lag shown", "",
                      "| lag ms | " + " | ".join(TYPES) + " |", "|---|" + "---|" * len(TYPES)]
                cols = {}
                for ty in TYPES:
                    def hv(r, k):
                        x = r["phase"].get(("ALL", ty))
                        return None if x is None or x["real"] is None or x["n"] < 30 or x.get("shuf") is None else (x["real"][gi] if k == 0 else x["shuf"][gi])
                    _, a = by_group(sub, lambda r: hv(r, 0))
                    _, b = by_group(sub, lambda r: hv(r, 1))
                    cols[ty] = (a, b) if len(a) and len(a) == len(b) else None
                for i, lg in enumerate(LAGS_MS):
                    row = []
                    for ty in TYPES:
                        c = cols[ty]
                        if c is None:
                            row.append("-")
                            continue
                        e = boot(c[0][:, i] - c[1][:, i])
                        row.append(f"{np.nanmean(c[0][:, i]):.3f} [{e[0]:+.3f}; {e[1]:+.3f}, {e[2]:+.3f}]")
                    L.append(f"| {lg} | " + " | ".join(row) + " |")
                L.append("")
    return L


# ---------------------------------------------------------------------------------------------------- C: tempo, density, pauses
def spearman_boot(x, y, seed=46104):
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if len(x) < 8:
        return (np.nan, np.nan, np.nan), len(x)
    f = lambda idx: spearmanr(x[idx], y[idx])[0]                                   # noqa: E731
    rng = np.random.default_rng(seed)
    b = [f(rng.integers(len(x), size=len(x))) for _ in range(NB)]
    return (f(np.arange(len(x))), np.nanpercentile(b, 2.5), np.nanpercentile(b, 97.5)), len(x)


def density_tables(rs):
    L = []
    for var in ("V1", "V2"):
        L += [f"#### {var}: Spearman across song groups [95 % boot by song]", "", "| dataset | pair | n groups | rho [95 %] |", "|---|---|---|---|"]
        for ds in DS:
            sub = sel(rs, ds, var)
            num = lambda k: by_group(sub, lambda r: r["numbers"][k])[1]            # noqa: E731
            rate = lambda ty: by_group(sub, lambda r: r["numbers"]["rate"][ty])[1]    # noqa: E731
            if not len(sub):
                continue
            pairs = [(f"{ty} rate vs tempo", rate(ty), num("tempo")) for ty in ("E1", "E2", "E4", "E5")] + [(f"{ty} rate vs onset density", rate(ty), num("onset_density")) for ty in ("E1", "E2", "E4", "E5")]
            for pn in ("pause_occ", "long_occ"):
                for qn in ("onset_density", "P1", "P2"):
                    pairs.append((f"{pn} vs {qn}", num(pn), num(qn)))
            for name, a, b in pairs:
                (e, lo, hi), n = spearman_boot(np.asarray(a, float), np.asarray(b, float))
                L.append(f"| {ds} | {name} | {n} | {e:.2f} [{lo:.2f}, {hi:.2f}] |")
        L.append("")
        L += [f"#### {var}: pause numbers (ALL), mean over song groups", "", "| dataset | tempo BPM | onset density /s | P1 | P2 | pause occupancy | 2-8 s pause occupancy | > 8 s occupancy | 2-8 s pauses per min | mean 2-8 s duration (s) |", "|---|---|---|---|---|---|---|---|---|---|"]
        for ds in DS:
            sub = sel(rs, ds, var)
            if not sub:
                continue
            v = [np.nanmean(by_group(sub, lambda r, k=k: r["numbers"][k])[1]) for k in ("tempo", "onset_density", "P1", "P2", "pause_occ", "long_occ", "over8_occ", "long_n_per_min", "long_mean_dur")]
            L.append(f"| {ds} | " + " | ".join(f"{x:.3f}" for x in v) + " |")
        L.append("")
    return L


# ---------------------------------------------------------------------------------------------------- D: structure
def struct_tables(rs):
    L = []
    for var in ("V1", "V2"):
        for st in ("ALL", "PASS"):
            for ds in DS:
                sub = sel(rs, ds, var)
                keys = sorted({k for r in sub for k in r.get("struct", {}) if k[0] == st})
                for key in keys:
                    _, mname, kind, half = key
                    L += [f"#### {ds} {var} {st}: music {mname}, motion {kind}, scale {half} tokens ({half / 2:g} s); delay = music after motion", "",
                          "| delay s | boundary hit share | circular-shift null | hit excess [95 %] | novelty corr | null mean [null 95 % band mean] | corr excess [95 %] |" + (" repetition rho | null | excess [95 %] |" if half == 4 else ""),
                          "|---|---|---|---|---|---|---|" + ("---|---|---|" if half == 4 else "")]
                    def arr(name):
                        return by_group(sub, lambda r: r["struct"][key][name] if key in r.get("struct", {}) else None)[1]
                    A = {n: arr(n) for n in ("hit", "hit_null", "corr", "corr_null", "corr_lo", "corr_hi")}
                    if half == 4:
                        A["rep"], A["rep_null"] = arr("rep"), arr("rep_null")
                    for i, d in enumerate(DELAYS):
                        h = boot(A["hit"][:, i] - A["hit_null"][:, i])
                        c = boot(A["corr"][:, i] - A["corr_null"][:, i])
                        row = f"| {d / 2:+.1f} | {np.nanmean(A['hit'][:, i]):.3f} | {np.nanmean(A['hit_null'][:, i]):.3f} | {fmt(h)} | {np.nanmean(A['corr'][:, i]):.3f} | {np.nanmean(A['corr_null'][:, i]):.3f} [{np.nanmean(A['corr_lo'][:, i]):.2f}, {np.nanmean(A['corr_hi'][:, i]):.2f}] | {fmt(c)} |"
                        if half == 4:
                            row += f" {np.nanmean(A['rep'][:, i]):.3f} | {np.nanmean(A['rep_null'][:, i]):.3f} | {fmt(boot(A['rep'][:, i] - A['rep_null'][:, i]))} |"
                        L.append(row)
                    L.append(f"(groups {len(A['hit'])}; motion boundaries per sequence median {np.median([r['struct'][key]['n_mot'] for r in sub if key in r.get('struct', {})]):.0f}, music boundaries {np.median([r['struct'][key]['n_mus'] for r in sub if key in r.get('struct', {})]):.0f})")
                    L.append("")
    return L


# ---------------------------------------------------------------------------------------------------- E: side table (0c on whole songs)
CTL = ["vigour", "vj", "vl", "height", "sharp", "pause_prob", "accent_mean", "dir_z"]
MEAS = ["rms_db", "flux", "onset", "low_db", "high_db", "centroid", "dyn_range", "beat_strength"]


def lagged(r, L):
    c, a = r["tokens"]["ctl"].astype(float), r["tokens"]["ac"].astype(float)
    n = len(c)
    if L >= 0:
        return c[:n - L], a[L:]
    return c[-L:], a[:n + L]


def side_table(rs, var="V1"):
    L = []
    rng = np.random.default_rng(46107)
    for ds in DS:
        sub = [r for r in sel(rs, ds, var) if "tokens" in r]
        if not sub:
            continue
        groups = sorted({r["group"] for r in sub})
        L += [f"#### {ds} {var} ALL tokens: Spearman (ranks once per dataset), control of token k vs measure of token k+L; global | within-song (group mean removed) | per-song median (groups >= 60 tokens); cell = value [95 % boot by song, 200]", "",
              "| control | measure | lag -2 | lag -1 | lag 0 | lag +1 | lag +2 |", "|---|---|---|---|---|---|---|"]
        # per group lagged pairs
        cache = {}
        for lg in (-2, -1, 0, 1, 2):
            gx = {g: [] for g in groups}
            for r in sub:
                x, y = lagged(r, lg)
                gx[r["group"]].append((x, y))
            cache[lg] = {g: (np.concatenate([a for a, _ in v]), np.concatenate([b for _, b in v])) for g, v in gx.items()}
        for ci, cn in enumerate(CTL):
            for mi, mn in enumerate(MEAS):
                if ds != "finedance" and mn == "beat_strength" and not np.isfinite(sub[0]["tokens"]["ac"][:, 7]).any():
                    pass
                cells = []
                for lg in (-2, -1, 0, 1, 2):
                    X = {g: cache[lg][g][0][:, ci] for g in groups}
                    Y = {g: cache[lg][g][1][:, mi] for g in groups}
                    allx = np.concatenate(list(X.values()))
                    ally = np.concatenate(list(Y.values()))
                    ok = np.isfinite(allx) & np.isfinite(ally)
                    if ok.sum() < 100:
                        cells.append("-")
                        continue
                    rx, ry = np.full(len(allx), np.nan), np.full(len(allx), np.nan)
                    rx[ok], ry[ok] = rankdata(allx[ok]), rankdata(ally[ok])
                    off = np.cumsum([0] + [len(X[g]) for g in groups])
                    suff = []                                                       # per group sufficient statistics of global and within-song Pearson on ranks
                    for gi, g in enumerate(groups):
                        a, b = rx[off[gi]:off[gi + 1]], ry[off[gi]:off[gi + 1]]
                        m = np.isfinite(a) & np.isfinite(b)
                        a, b = a[m], b[m]
                        n = len(a)
                        suff.append([n, a.sum(), b.sum(), (a * a).sum(), (b * b).sum(), (a * b).sum(), ((a - a.mean()) * (b - b.mean())).sum() if n else 0, ((a - a.mean()) ** 2).sum() if n else 0, ((b - b.mean()) ** 2).sum() if n else 0])
                    S = np.array(suff, float)

                    def vals(idx):
                        s = S[idx].sum(0)
                        n = s[0]
                        g = (s[5] - s[1] * s[2] / n) / np.sqrt((s[3] - s[1] ** 2 / n) * (s[4] - s[2] ** 2 / n))
                        w = s[6] / np.sqrt(s[7] * s[8])
                        return g, w
                    g0, w0 = vals(np.arange(len(groups)))
                    bs = np.array([vals(rng.integers(len(groups), size=len(groups))) for _ in range(200)])
                    per = []
                    for gi in range(len(groups)):
                        if S[gi, 0] >= 60 and S[gi, 7] > 0 and S[gi, 8] > 0:
                            per.append(S[gi, 6] / np.sqrt(S[gi, 7] * S[gi, 8]))
                    pm = np.median(per) if per else np.nan
                    cells.append(f"{g0:+.2f} [{np.nanpercentile(bs[:, 0], 2.5):+.2f}, {np.nanpercentile(bs[:, 0], 97.5):+.2f}] | {w0:+.2f} [{np.nanpercentile(bs[:, 1], 2.5):+.2f}, {np.nanpercentile(bs[:, 1], 97.5):+.2f}] | {pm:+.2f}")
                L.append(f"| {cn} | {mn} | " + " || ".join(cells) + " |")
        L.append("")
    return L


def main():
    rs = load()
    print(len(rs), "results")
    parts = [("A. Phase concentration (rules section 4)", phase_tables(rs)), ("B. Lead/lag scan, every lag", lag_tables(rs)), ("C. Tempo, density, pauses (section 5)", density_tables(rs)),
             ("D. Whole-song structure (section 6)", struct_tables(rs)), ("E. Side table: control vs acoustics on whole songs (WO43 step 0c)", side_table(rs))]
    L = ["# Metric tables (WO46 part 2; generated by `scripts/body/metric_report.py`, do not edit)", "",
         "Provisional: half-time and bar levels (no downbeat source). ALL = whole sequence, PASS = only inside T0-passing 20 s windows. Motorica rows are aggregates only.", ""]
    for t, p in parts:
        L += [f"## {t}", ""] + p
    (DOCS / "METRIC_TABLES.md").write_text("\n".join(L))
    n = {ds: len({r["group"] for r in rs if r["ds"] == ds and r["var"] == "V1"}) for ds in DS}
    (OUT / "summary.json").write_text(json.dumps(dict(n_results=len(rs), v1_groups=n)))
    print("tables written", n)


if __name__ == "__main__":
    main()
