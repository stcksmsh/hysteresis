"""WO53 part B (BRAIN_SPEC 7.84 item 3): WO52's movement rhythm on raw human joints before retargeting. Rules: docs/RAWRHYTHM_RULES.md. Brain env.

    rawrhythm.py scan [PROCS]       every raw source of WO52's sequences loads, finite, long enough -> rawrhythm/scan.json
    rawrhythm.py extract [PROCS]    per performance: 50 Hz joint speeds -> rhythm per WO52 analysis window -> rawrhythm/seq/<perf>.npz (resumable)
    rawrhythm.py assemble           row-aligned to rhythm/windows_<ds>.npz -> rawrhythm/windows_<ds>.npz
    rawrhythm.py analyse            WO52 analysis A for lamp + raw signals, period quantiles, paired bins -> results.json, songs_<ds>.npz
    rawrhythm.py tables             results.json -> rawrhythm/tables.md
Report only; nothing upstream is recomputed. Rhythm functions are imported from rhythm_events.py unchanged.
"""
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.spatial.transform import Rotation as Rot

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "brain"))
sys.path.insert(0, str(HERE.parent))
import beatv_lib as BL  # noqa: E402
import rhythm_events as RE  # noqa: E402

B = Path("/secondary/hyst-data/body")
OUT = B / "rawrhythm"
DS = RE.DS
FD = Path("/secondary/hyst-data/datasets/finedance/data/finedance")
CAT = {"aioz": B / "t0/catalogue_aioz.json", "phantom": B / "t0_phantom/catalogue.json", "motorica": B / "t0_motorica/catalogue.json"}
FPS_RAW, FS = 30, RE.FS
JOINTS = ("lwr", "rwr", "lft", "rft", "pel", "head")
SMPL_J = (20, 21, 7, 8, 0, 15)
BVH_J = ("LeftHand", "RightHand", "LeftFoot", "RightFoot", "Hips", "Head")
RAW_SIGS = tuple(JOINTS) + ("mean",) + tuple(j + "_rel" for j in JOINTS) + ("mean_rel",)
SIGS = ("lamp",) + RAW_SIGS
VAR_SIGS = ("lamp", "mean", "mean_rel")          # narrow and W4 variants
SEED_BOOT = 53201
QS = (5, 25, 50, 75, 95)


def perf_of(key):
    return key.rsplit("__", 1)[0]


# ---------------------------------------------------------------------------------------------------- raw positions (T, 6, 3) at 30 Hz, metres
def fk_world(G, root):
    """world rotations (T, >=22, 3, 3), root (T, 3) -> positions (T, 22, 3) with the generic skeleton of beatv_lib"""
    P = np.zeros((len(G), 22, 3))
    P[:, 0] = root
    for j in range(1, 22):
        p = BL.PARENT[j]
        P[:, j] = P[:, p] + np.einsum("tab,b->ta", G[:, p], BL.OFFSET[j])
    return P


def pos_finedance(perf):
    m = np.load(FD / "motion" / f"{perf[3:]}.npy").astype(np.float64)
    return BL.fk(BL.local_rots(m), m[:, :3])[:, SMPL_J]


def pos_aioz(c):
    import t0_aioz as A
    d = A.load_pkl(c["motion"])
    p = c["person"]
    R = A.aa_to_mats(np.asarray(d["smpl_poses"], np.float64)[p])
    return BL.fk(R, np.asarray(d["root_trans"], np.float64)[p])[:, SMPL_J]


def pos_phantom(c):
    import t0_phantom as TP
    d = json.loads(Path(c["motion"]).read_text())
    assert list(d["bone_name"]) == list(TP.SMPL_NAMES)
    rl = d["rotations"]
    n = next((i for i, f in enumerate(rl) if len(f) != 24), len(rl))
    q = np.asarray(rl[:n], np.float64)
    G = TP.FLIP_X @ Rot.from_quat(q.reshape(-1, 4)).as_matrix().reshape(n, 24, 3, 3) @ TP.FLIP_X
    root = np.asarray(d["root_positions"][:n], np.float64) * np.array([-1.0, 1.0, 1.0])
    return fk_world(G, root)[:, SMPL_J]


def parse_bvh(text):
    """-> names, parent index per joint, offset (J, 3), channels per joint, data (frames, channels), frame time"""
    lines = text.split("\n")
    names, parent, off, chans, stack = [], [], [], [], []
    i = 0
    while not lines[i].strip().startswith("MOTION"):
        t = lines[i].split()
        if t and t[0] in ("ROOT", "JOINT"):
            parent.append(stack[-1] if stack and stack[-1] is not None else -1)
            names.append(t[1])
            off.append(None)
            chans.append([])
            stack.append(len(names) - 1)
        elif t and t[0] == "End":
            stack.append(None)
        elif t and t[0] == "OFFSET" and stack[-1] is not None:
            off[stack[-1]] = [float(x) for x in t[1:4]]
        elif t and t[0] == "CHANNELS":
            chans[stack[-1]] = t[2:2 + int(t[1])]
        elif t and t[0] == "}":
            stack.pop()
        i += 1
    n = int(lines[i + 1].split()[1])
    ft = float(lines[i + 2].split()[2])
    data = np.array(" ".join(lines[i + 3:i + 3 + n]).split(), np.float64).reshape(n, -1)
    return names, parent, np.array(off, float), chans, data, ft


def bvh_positions(text, want, step=None, fps_out=FPS_RAW):
    """BVH text -> (positions (T, len(want), 3) in metres at fps_out, max std of non-root position channels in cm). Every `step`-th frame
    (default 1 / (ft fps_out)) as t0_phantom.motorica_rot; local rotation = intrinsic Euler in the listed channel order; root position channels."""
    names, parent, off, chans, data, ft = parse_bvh(text)
    step = step or round(1 / ft / fps_out)
    data = data[::step]
    col, c = [], 0
    for ch in chans:
        col.append(c)
        c += len(ch)
    assert c == data.shape[1], (c, data.shape)
    need = set()
    for nm in want:
        j = names.index(nm)
        while j >= 0:
            need.add(j)
            j = parent[j]
    T = len(data)
    G, P = {}, {}
    pos_std = 0.0
    for j in sorted(need):                                             # parents precede children in BVH order
        ch = chans[j]
        ri = [k for k, x in enumerate(ch) if x.endswith("rotation")]
        pi = [k for k, x in enumerate(ch) if x.endswith("position")]
        R = Rot.from_euler("".join(ch[k][0] for k in ri), data[:, [col[j] + k for k in ri]], degrees=True).as_matrix()
        if parent[j] < 0:
            P[j] = data[:, [col[j] + k for k in pi]] if pi else np.tile(off[j], (T, 1))
            G[j] = R
        else:
            if pi:
                pos_std = max(pos_std, float(data[:, [col[j] + k for k in pi]].std(0).max()))
            p = parent[j]
            P[j] = P[p] + np.einsum("tab,b->ta", G[p], off[j])
            G[j] = G[p] @ R
    return np.stack([P[names.index(nm)] for nm in want], 1) / 100.0, pos_std


POS_SD_MAX_CM = 1.0
_POS_SD = {}


def pos_motorica(c):
    pos, sd = bvh_positions(Path(c["motion"]).read_text(), BVH_J)
    _POS_SD["last"] = sd
    assert sd < POS_SD_MAX_CM, f"non-root position channels vary (sd {sd} cm)"
    return pos


def catalogues():
    out = {}
    for ds, p in CAT.items():
        out[ds] = {c["key"]: c for c in json.loads(p.read_text())}
    return out


def raw_positions(ds, perf, cat):
    if ds == "finedance":
        return pos_finedance(perf)
    return {"aioz": pos_aioz, "phantom": pos_phantom, "motorica": pos_motorica}[ds](cat[ds][perf])


# ---------------------------------------------------------------------------------------------------- speeds and rhythm
def speeds50(pos30):
    """(T, 6, 3) positions at 30 Hz -> dict signal -> 50 Hz speed (m/s), world and pelvis-relative, plus the means"""
    T = len(pos30)
    t30 = np.arange(T) / FPS_RAW
    n50 = int(np.floor((T - 1) / FPS_RAW * FS + 1e-9)) + 1
    t50 = np.arange(n50) / FS
    out = {}
    for suf, P in (("", pos30), ("_rel", pos30 - pos30[:, 4:5])):
        p50 = CubicSpline(t30, P.reshape(T, -1), axis=0)(t50).reshape(n50, 6, 3)
        sp = np.linalg.norm(np.gradient(p50, axis=0) * FS, axis=2)
        for i, j in enumerate(JOINTS):
            out[j + suf] = sp[:, i]
        out["mean" + suf] = sp.mean(1)
    return out


def rhythm_rows(sp, ws_starts):
    """speed dict, list of (W, start s) -> per signal (period, strength) arrays"""
    res = {s: (np.full(len(ws_starts), np.nan), np.zeros(len(ws_starts))) for s in RAW_SIGS}
    n = len(sp["mean"])
    for i, (Wn, a) in enumerate(ws_starts):
        i0 = int(round(a * FS))
        i1 = i0 + int(Wn) * FS
        if i1 > n:
            raise ValueError(f"window {a}+{Wn} beyond raw length {n / FS:.2f} s")
        for s in RAW_SIGS:
            p, st = RE.rhythm(sp[s][i0:i1])
            res[s][0][i] = p
            res[s][1][i] = st
    return res


# ---------------------------------------------------------------------------------------------------- driver
_CAT = {}


def _init():
    _CAT.update(catalogues())


def perf_rows():
    """ds -> perf -> sorted unique (W, start) of WO52's rows"""
    out = {}
    for ds in DS:
        z = np.load(B / f"rhythm/windows_{ds}.npz")
        perf = np.array([perf_of(k) for k in z["key"]])
        d = {}
        for p, Wn, a in zip(perf, z["W"], z["start"]):
            d.setdefault(p, set()).add((int(Wn), float(a)))
        out[ds] = {p: sorted(v) for p, v in d.items()}
    return out


def scan_one(args):
    ds, perf, rows = args
    try:
        pos = raw_positions(ds, perf, _CAT)
        assert pos.ndim == 3 and pos.shape[1:] == (6, 3), pos.shape
        assert np.isfinite(pos).all(), "non-finite"
        need = max(a + Wn for Wn, a in rows)
        have = (len(pos) - 1) / FPS_RAW
        assert have >= need - 1e-9, f"raw {have:.2f} s < needed {need:.2f} s"
        return ds, perf, (len(pos), _POS_SD.pop("last", None)), None
    except Exception as e:  # noqa: BLE001
        return ds, perf, None, repr(e)


def scan(procs):
    OUT.mkdir(parents=True, exist_ok=True)
    pr = perf_rows()
    jobs = [(ds, p, r) for ds in DS for p, r in sorted(pr[ds].items())]
    res = {ds: dict(performances=len(pr[ds]), ok=0, bad=[], frames=0, bvh_nonroot_pos_sd_max_cm=0.0) for ds in DS}
    with Pool(procs, initializer=_init) as pool:
        for i, (ds, perf, n, err) in enumerate(pool.imap_unordered(scan_one, jobs, chunksize=2)):
            if err:
                res[ds]["bad"].append([perf, err])
                print("BAD", ds, perf, err, flush=True)
            else:
                res[ds]["ok"] += 1
                res[ds]["frames"] += n[0]
                if n[1] is not None:
                    res[ds]["bvh_nonroot_pos_sd_max_cm"] = max(res[ds]["bvh_nonroot_pos_sd_max_cm"], n[1])
            if i % 200 == 0:
                print("scan", i, "/", len(jobs), flush=True)
    (OUT / "scan.json").write_text(json.dumps(res, indent=1))
    print("SCAN", {ds: (v["ok"], len(v["bad"])) for ds, v in res.items()}, flush=True)


def extract_one(args):
    ds, perf, rows = args
    dst = OUT / "seq" / ds / f"{perf}.npz"
    if dst.exists():
        return ds, perf, "skip"
    try:
        sp = speeds50(raw_positions(ds, perf, _CAT))
        r = rhythm_rows(sp, rows)
        tmp = dst.with_name(dst.stem + ".tmp.npz")
        np.savez(tmp, W=np.array([x[0] for x in rows]), start=np.array([x[1] for x in rows]),
                 **{f"per_{s}": r[s][0] for s in RAW_SIGS}, **{f"str_{s}": r[s][1] for s in RAW_SIGS})
        tmp.replace(dst)
        return ds, perf, "ok"
    except Exception as e:  # noqa: BLE001
        with open(OUT / "extract_failed.txt", "a") as f:
            f.write(f"{ds} {perf} {e!r}\n")
        return ds, perf, "failed"


def extract(procs):
    pr = perf_rows()
    for ds in DS:
        (OUT / "seq" / ds).mkdir(parents=True, exist_ok=True)
    jobs = [(ds, p, r) for ds in DS for p, r in sorted(pr[ds].items())]
    cnt = {}
    with Pool(procs, initializer=_init) as pool:
        for i, (ds, perf, st) in enumerate(pool.imap_unordered(extract_one, jobs, chunksize=2)):
            cnt[st] = cnt.get(st, 0) + 1
            if st == "failed":
                print("FAIL", ds, perf, flush=True)
            if i % 200 == 0:
                print("extract", i, "/", len(jobs), cnt, flush=True)
    print("EXTRACT DONE", cnt, flush=True)


def assemble(procs=None):
    for ds in DS:
        z = dict(np.load(B / f"rhythm/windows_{ds}.npz"))
        n = len(z["key"])
        out = {k: z[k] for k in ("key", "W", "win", "start", "lib", "pul", "conf", "group", "song", "per_lamp", "str_lamp")}
        for s in RAW_SIGS:
            out[f"per_{s}"], out[f"str_{s}"] = np.full(n, np.nan), np.zeros(n)
        out["raw_ok"] = np.zeros(n, bool)
        perf = np.array([perf_of(k) for k in z["key"]])
        for p in np.unique(perf):
            f = OUT / "seq" / ds / f"{p}.npz"
            if not f.exists():
                continue
            r = np.load(f)
            look = {(int(w), round(float(a), 6)): i for i, (w, a) in enumerate(zip(r["W"], r["start"]))}
            idx = np.flatnonzero(perf == p)
            j = np.array([look[(int(z["W"][i]), round(float(z["start"][i]), 6))] for i in idx])
            for s in RAW_SIGS:
                out[f"per_{s}"][idx] = r[f"per_{s}"][j]
                out[f"str_{s}"][idx] = r[f"str_{s}"][j]
            out["raw_ok"][idx] = True
        np.savez(OUT / f"windows_{ds}.npz", **out)
        print("assembled", ds, n, "rows", int(out["raw_ok"].sum()), "with raw", flush=True)


# ---------------------------------------------------------------------------------------------------- analysis
def quant(x):
    x = x[np.isfinite(x)]
    return [float(v) for v in np.percentile(x, QS)] if len(x) else None


def paired(raw_bin, lamp_bin):
    """two bin-code arrays (0 none .. 4 other) -> same share, independence expectation; also over rows where both are rhythmic"""
    out = {}
    for name, m in (("all", np.ones(len(raw_bin), bool)), ("both_rhythmic", (raw_bin > 0) & (lamp_bin > 0))):
        a, b = raw_bin[m], lamp_bin[m]
        if not len(a):
            out[name] = None
            continue
        pa = np.bincount(a, minlength=5) / len(a)
        pb = np.bincount(b, minlength=5) / len(b)
        out[name] = dict(n=int(len(a)), same=float((a == b).mean()), expected=float((pa * pb).sum()))
    return out


def analyse(procs=None):
    wo52 = json.loads((B / "rhythm/results.json").read_text())["A"]
    res, hist, songs = {}, {}, {ds: {} for ds in DS}
    stats = {}
    Z = {}
    for ds in DS:
        z = dict(np.load(OUT / f"windows_{ds}.npz"))
        Z[ds] = z
        groups, gid = np.unique(z["group"], return_inverse=True)
        for Wn in RE.WS:
            m = z["W"] == Wn
            zz = {k: v[m] for k, v in z.items()}
            g = gid[m]
            for src, col in (("librosa", "lib"), ("pulse2", "pul")):
                per = zz[col]
                tempo = {}
                ref = (z["W"] == 3) & np.isfinite(z[col])
                for s in np.unique(z["song"][ref]):
                    tempo[s] = float(np.median(z[col][ref & (z["song"] == s)]))
                rng1 = np.random.default_rng([RE.SEED_C1, DS.index(ds), Wn, int(src == "pulse2")])
                rng2 = np.random.default_rng([RE.SEED_C2, DS.index(ds), Wn, int(src == "pulse2")])
                c1, c2 = RE.chance_periods(per, zz["song"], zz["group"], tempo, rng1, rng2)
                for sig in SIGS:
                    for narrow in (False, True):
                        if Wn == 4 and narrow:
                            continue
                        var = "W4" if Wn == 4 else ("narrow" if narrow else "main")
                        if var != "main" and sig not in VAR_SIGS:
                            continue
                        movp, stren = zz[f"per_{sig}"], zz[f"str_{sig}"]
                        st = RE.song_stats(groups, g, movp, stren, per, c1, c2, narrow)
                        stats.setdefault((src, sig, var), {})[ds] = st
                        for f_, v in st.items():
                            songs[ds][f"{src}|{sig}|{var}|{f_}"] = v
                        if var == "main":
                            ok = np.isfinite(per) & np.isfinite(movp) & (stren >= RE.STRENGTH)
                            hist[f"{ds}|{src}|{sig}"] = np.histogram(np.log2(movp[ok] / per[ok]), np.arange(-3, 3.0001, 0.05))[0].tolist()
                print("A", ds, Wn, src, flush=True)
        songs[ds]["groups"] = groups
        np.savez(OUT / f"songs_{ds}.npz", **songs[ds])
    for (src, sig, var), v in stats.items():
        for ds in list(DS) + ["all"]:
            st = {f: np.concatenate([v[d][f] for d in DS]) for f in v[DS[0]]} if ds == "all" else v[ds]
            res[f"{ds}|{src}|{sig}|{var}"] = RE.summarise_A(st, RE.boot_idx(len(st["n_rh"]), SEED_BOOT))
    # lamp reproduction check against WO52 (point estimates)
    check = {}
    for ds in list(DS) + ["all"]:
        for src in ("librosa", "pulse2"):
            for var in ("main", "narrow", "W4"):
                a, b = res[f"{ds}|{src}|lamp|{var}"], wo52[f"{ds}|{src}|lamp|{var}|all"]
                d = max(abs(a["cluster"] - b["cluster"]), abs(a["c1"]["excess"] - b["c1"]["excess"]), abs(a["c2"]["excess"] - b["c2"]["excess"]), abs(a["conc"] - b["conc"]))
                check[f"{ds}|{src}|{var}"] = d
    # period quantiles and paired bins (W = 3, main)
    quants, pair = {}, {}
    for ds in list(DS) + ["all"]:
        zs = [Z[d] for d in DS] if ds == "all" else [Z[ds]]
        z = {k: np.concatenate([x[k] for x in zs]) for k in zs[0] if k not in ("key", "song", "group")}
        m3 = z["W"] == 3
        for sig in SIGS:
            p, s = z[f"per_{sig}"][m3], z[f"str_{sig}"][m3]
            rh = np.isfinite(p) & (s >= RE.STRENGTH)
            quants[f"{ds}|{sig}|period"] = quant(p[rh])
            quants[f"{ds}|{sig}|rhythmic_share"] = float(rh.mean())
            for src, col in (("librosa", "lib"), ("pulse2", "pul")):
                per = z[col][m3]
                quants[f"{ds}|{sig}|ratio|{src}"] = quant((p / per)[rh & np.isfinite(per)])
                if sig != "lamp":
                    ok = np.isfinite(per)
                    rb = RE.bins(p[ok] / per[ok], s[ok]).astype(int)
                    lb = RE.bins(z["per_lamp"][m3][ok] / per[ok], z["str_lamp"][m3][ok]).astype(int)
                    pair[f"{ds}|{src}|{sig}"] = paired(rb, lb)
    (OUT / "results.json").write_text(json.dumps(dict(A=res, hist=hist, quantiles=quants, paired=pair, lamp_vs_wo52_maxdiff=check,
                                                      raw_rows={ds: [int(Z[ds]["raw_ok"].sum()), int(len(Z[ds]["raw_ok"]))] for ds in DS}), indent=1))
    print("lamp vs WO52 max abs diff", max(check.values()), flush=True)
    print("ANALYSE DONE", flush=True)


def tables(procs=None):
    r = json.loads((OUT / "results.json").read_text())
    A = r["A"]
    f = lambda x: f"{x:.3f}"  # noqa: E731
    fc = lambda v, k: f"{v[k]:+.3f} [{v[k + '_ci'][0]:+.3f}, {v[k + '_ci'][1]:+.3f}]"  # noqa: E731
    L = []
    for var, sigs in (("main", SIGS), ("narrow", VAR_SIGS), ("W4", VAR_SIGS)):
        for src in ("librosa", "pulse2"):
            L += [f"### Ratio bins, {src}, variant {var} (shares of rhythmic windows; excess = cluster share minus chance, 95 % song-group bootstrap, seed {SEED_BOOT})", "",
                  "| dataset | signal | rhythmic share | 1/2 | 1 | 2 | other | cluster share | chance 1 | excess 1 [CI] | chance 2 | excess 2 [CI] | C | C excess 1 [CI] | C excess 2 [CI] |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
            for ds in list(DS) + ["all"]:
                for sig in sigs:
                    v = A[f"{ds}|{src}|{sig}|{var}"]
                    b = v["bin_share_rhythmic"]
                    L.append(f"| {ds} | {sig} | {f(1 - v['bin_share_all']['none'])} | {f(b['1/2'])} | {f(b['1'])} | {f(b['2'])} | {f(b['other'])} | {f(v['cluster'])} | "
                             f"{f(v['c1']['cluster_chance'])} | {fc(v['c1'], 'excess')} | {f(v['c2']['cluster_chance'])} | {fc(v['c2'], 'excess')} | "
                             f"{f(v['conc'])} | {fc(v['c1'], 'conc_excess')} | {fc(v['c2'], 'conc_excess')} |")
            L.append("")
    q = r["quantiles"]
    fq = lambda x: "-" if x is None else " / ".join(f"{v:.2f}" for v in x)  # noqa: E731
    L += ["### Movement period and ratio quantiles 5/25/50/75/95 (W = 3 s, rhythmic windows: strength >= 0.2)", "",
          "| dataset | signal | rhythmic share | period (s) | r librosa | r pulse v2 |", "|---|---|---|---|---|---|"]
    for ds in list(DS) + ["all"]:
        for sig in SIGS:
            L.append(f"| {ds} | {sig} | {q[f'{ds}|{sig}|rhythmic_share']:.3f} | {fq(q[f'{ds}|{sig}|period'])} | {fq(q[f'{ds}|{sig}|ratio|librosa'])} | {fq(q[f'{ds}|{sig}|ratio|pulse2'])} |")
    L.append("")
    P = r["paired"]
    L += ["### Paired per window, raw signal bin vs lamp bin (W = 3, main): share in the same bin / expected if independent (all rows with a beat period; rows where both rhythmic)", "",
          "| dataset | signal | librosa all | librosa both rhythmic | pulse v2 all | pulse v2 both rhythmic |", "|---|---|---|---|---|---|"]
    fp = lambda v: "-" if v is None else f"{v['same']:.3f} / {v['expected']:.3f} (n {v['n']})"  # noqa: E731
    for ds in list(DS) + ["all"]:
        for sig in RAW_SIGS:
            a, b = P[f"{ds}|librosa|{sig}"], P[f"{ds}|pulse2|{sig}"]
            L.append(f"| {ds} | {sig} | {fp(a['all'])} | {fp(a['both_rhythmic'])} | {fp(b['all'])} | {fp(b['both_rhythmic'])} |")
    L.append("")
    (OUT / "tables.md").write_text("\n".join(L))
    print("TABLES", OUT / "tables.md", flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    procs = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    if cmd in ("scan", "extract", "assemble", "analyse", "tables"):
        globals()[cmd](procs)
    else:
        print(__doc__)
