"""WO42 report (body env): docs/T0_PHANTOM_REPORT.md + SOURCE_OUT/numbers.json from the npz files, split.json, catalogues, bandlimit.json. Numbers only, no verdict.
FineDance is the reference (its seq npz in t0/seq/finedance, same measures). Aggregates only: nothing per Motorica file is written to the report.   python -u t0_phantom_report.py"""
import collections
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jitter_diag as J  # noqa: E402
import retarget_run as RR  # noqa: E402
import t0_chain as C  # noqa: E402
import t0_lib as T  # noqa: E402
import t0_phantom_run as PR  # noqa: E402

FD = Path("/secondary/hyst-data/body/t0")
DOCS = HERE.parents[1] / "docs"
JN = RR.JN


def med(v):
    return float(np.median(v)) if len(v) else None


def source_numbers(name, cat, seqdir, split):
    """cat: units; seqdir: dir of npz; split: key -> (group, split)"""
    rows, gen, jit, amp, missing = collections.defaultdict(lambda: collections.defaultdict(float)), collections.defaultdict(lambda: collections.defaultdict(float)), collections.defaultdict(list), collections.defaultdict(list), []
    for c in cat:
        k = c["key"]
        if k not in split:
            continue
        for copy in C.COPIES:
            p = seqdir / f"{k}__{copy}.npz"
            if not p.exists():
                missing.append(p.name)
                continue
            z = np.load(p)
            n, ok = int(z["n_win"]), z["win_pass"]
            tail = (c["t30"] - 1) / T.FPS - n * T.WIN_S
            for key, counters in (((copy, split[k][1]), rows), ((c["genre"], copy), gen)):
                r = counters[key]
                r["dancers"] += 1
                r["windows"] += n
                r["windows_kept"] += int(ok.sum())
                r["hours_total"] += c["hours"]
                r["hours_usable"] += int(ok.sum()) * T.WIN_S / 3600
                r["tails_dropped"] += int(tail > 1e-9)
                for pn, col in zip(z["win_part_names"], np.asarray(z["win_parts"]).T if n else []):
                    r["failed_" + str(pn)] += int((~col).sum())
            if copy in ("V1", "V2") and len(z["targets"]) > 200:
                jit[copy].append(J.all_joints(np.asarray(z["targets"], float), 100.0, JN))
                g = np.asarray(z["gesture"], float)
                rowsel = np.concatenate([np.arange(i * 2000, min((i + 1) * 2000, len(g))) for i in range(n) if ok[i]] or [np.zeros(0, int)])
                if len(rowsel) > 100:
                    gs = g[rowsel]
                    amp[copy].append(dict(rms=np.sqrt((gs ** 2).mean(0)).tolist(), p5=np.percentile(gs, 5, axis=0).tolist(), p95=np.percentile(gs, 95, axis=0).tolist()))
    jitter = {v: {j: {m: med([d[j][m] for d in L]) for m in ("acc_sign_changes_per_s", "p_gt3")} for j in JN} for v, L in jit.items()}
    amplitude = {v: {j: {m: med([a[m][i] for a in L]) for m in ("rms", "p5", "p95")} for i, j in enumerate(JN)} for v, L in amp.items()}
    return dict(name=name, missing=missing, by_copy_split={"|".join(k): dict(v) for k, v in rows.items()}, by_genre_copy={"|".join(k): dict(v) for k, v in gen.items()}, jitter=jitter, gesture_amplitude=amplitude)


def main():
    fd_cat = json.loads((FD / "catalogue_fd.json").read_text())
    fd_split = {k: (r["group"], r["split"]) for r in json.loads((FD / "split.json").read_text())["groups"] for k in r["members"]}
    fd = source_numbers("finedance", fd_cat, FD / "seq" / "finedance", fd_split)
    res, L = {"finedance": fd}, []
    L += ["# T0 for PhantomDance and Motorica: report (work order 42, BRAIN_SPEC 7.69; numbers only, no verdict)", "",
          "Rules and mapping `T0_PHANTOM_RULES.md`; T0 as `T0_RULES.md` (gates at 1.25, V1 / V2 + mirror, cutoffs 2.50 / 5.75 Hz). FineDance = the reference, same measures, same code. Aggregates only:",
          "Motorica data and anything derived stay on this laptop; no per-file Motorica numbers are written here.", ""]
    for source in ("phantom", "motorica"):
        s = PR.SRC[source]
        cat = json.loads((s["out"] / "catalogue.json").read_text())
        spj = json.loads((s["out"] / "split.json").read_text())
        split = {k: (r["group"], r["split"]) for r in spj["groups"] for k in r["members"]}
        d = source_numbers(source, cat, s["out"] / "seq", split)
        d.update(split_seed=spj["seed"], split_groups={x: sum(1 for r in spj["groups"] if r["split"] == x) for x in ("train", "validation", "test")}, excluded=spj["excluded_by_check_or_danced_match"],
                 also_in_finedance_by_name=spj["also_in_finedance_by_name"], sequences=len(cat), hours=sum(c["hours"] for c in cat))
        res[source] = d
        (s["out"] / "numbers.json").write_text(json.dumps(d, indent=1))
        tot = collections.defaultdict(float)
        for k, v in d["by_copy_split"].items():
            c_ = k.split("|")[0]
            tot["win" + c_] += v["windows"]
            tot["kept" + c_] += v["windows_kept"]
            tot["h" + c_] += v["hours_usable"]
        L += [f"## {source}", "", f"- Sequences {d['sequences']}, {d['hours']:.3f} h, split seed {d['split_seed']}, groups per split {d['split_groups']}. Missing npz: {len(d['missing'])}. "
              f"Excluded as check / danced song: {d['excluded']}. Also in FineDance by name: {d['also_in_finedance_by_name']}"
              + (" (PhantomDance carries no names; by audio hash none can match, the sample rates differ)." if source == "phantom" else "."), "",
              "### Hours kept after the gates (20 s windows, per copy)", "", "| copy | windows | kept | share | usable h |", "|---|---|---|---|---|"]
        for c_ in C.COPIES:
            L.append(f"| {c_} | {int(tot['win' + c_])} | {int(tot['kept' + c_])} | {tot['kept' + c_] / max(tot['win' + c_], 1):.2f} | {tot['h' + c_]:.2f} |")
        L += ["", f"Four copies together: {sum(tot['h' + c_] for c_ in C.COPIES):.2f} usable hours.", "", "### By split", "", "| copy | split | dancers | windows | kept | usable h | failed parts |", "|---|---|---|---|---|---|---|"]
        for k, v in sorted(d["by_copy_split"].items()):
            fp = ", ".join(f"{kk[7:]} {int(vv)}" for kk, vv in v.items() if kk.startswith("failed_") and vv)
            L.append(f"| {k.split('|')[0]} | {k.split('|')[1]} | {int(v['dancers'])} | {int(v['windows'])} | {int(v['windows_kept'])} | {v['hours_usable']:.2f} | {fp} |")
        L += ["", "### Genres (V1 copy)", "", "| genre | dancers | hours | usable h | kept share |", "|---|---|---|---|---|"]
        for k, v in sorted(d["by_genre_copy"].items()):
            if k.endswith("|V1"):
                L.append(f"| {k.split('|')[0]} | {int(v['dancers'])} | {v['hours_total']:.2f} | {v['hours_usable']:.2f} | {v['windows_kept'] / max(v['windows'], 1):.2f} |")
    # FineDance reference counts
    tot = collections.defaultdict(float)
    for k, v in fd["by_copy_split"].items():
        tot["win" + k.split("|")[0]] += v["windows"]
        tot["kept" + k.split("|")[0]] += v["windows_kept"]
    L += ["", "## FineDance reference (kept share per copy)", "", "| copy | windows | kept | share |", "|---|---|---|---|"]
    for c_ in C.COPIES:
        L.append(f"| {c_} | {int(tot['win' + c_])} | {int(tot['kept' + c_])} | {tot['kept' + c_] / max(tot['win' + c_], 1):.2f} |")
    L += ["", "## Jitter of the stored targets (median over dancers; 100 Hz; acc sign changes per s | power > 3 Hz)", "",
          "| variant | joint | FineDance | PhantomDance | Motorica |", "|---|---|---|---|---|"]
    for v in ("V1", "V2"):
        for j in JN:
            cell = lambda src: (lambda m: f"{m['acc_sign_changes_per_s']:.2f} \\| {m['p_gt3']:.4f}" if m and m['acc_sign_changes_per_s'] is not None else "-")(res[src]["jitter"].get(v, {}).get(j))
            L.append(f"| {v} | {j} | {cell('finedance')} | {cell('phantom')} | {cell('motorica')} |")
    L += ["", "## Gesture amplitude (target minus 0.5 Hz posture; kept windows only; median over dancers; deg; rms, p5 .. p95)", "",
          "| variant | joint | FineDance | PhantomDance | Motorica |", "|---|---|---|---|---|"]
    for v in ("V1", "V2"):
        for j in JN:
            cell = lambda src: (lambda m: f"{m['rms']:.1f}, {m['p5']:.1f} .. {m['p95']:.1f}" if m and m['rms'] is not None else "-")(res[src]["gesture_amplitude"].get(v, {}).get(j))
            L.append(f"| {v} | {j} | {cell('finedance')} | {cell('phantom')} | {cell('motorica')} |")
    bl = Path("/secondary/hyst-data/body/t0_phantom/bandlimit.json")
    if bl.exists():
        b = json.loads(bl.read_text())
        L += ["", "## Band limit (7.69 overseer note)", "",
              f"5 FineDance songs ({', '.join(b['songs'])}), first {b['seconds_each']} s each, original against the same audio low-passed at 8 kHz (zero-phase Butterworth order 8). "
              "Differences are in the standardised units of the cortex input (46 columns = 44 ear features + 2 beat-phase columns); mean over the 5 songs.", "",
              "| column | rms difference | correlation |", "|---|---|---|"]
        for c_, r in b["rms_diff_standardised"].items():
            L.append(f"| {c_} | {r:.3f} | {b['corr'][c_]:.3f} |")
        L += ["", "Cortex lane shift (mean abs difference; the lane's own standard deviation in brackets; mean over the 5 songs):", ""]
        for k, v in b["lane_shift"].items():
            a = np.mean(np.array(v), 0)
            L.append(f"- {k}: {a[0]:.4f} ({a[1]:.4f})" + (f", correlation {a[2]:.3f}" if len(a) > 2 else ""))
        L += ["", "Share of the power above 8 kHz in the source audio (20 songs each, first 60 s): " + "; ".join(f"{k}: median {v['median']:.2e}, p90 {v['p90']:.2e}, max {v['max']:.2e}" for k, v in b["share_power_above_8k"].items()) + "."]
    (DOCS / "T0_PHANTOM_REPORT.md").write_text("\n".join(L) + "\n")
    print("report written")


if __name__ == "__main__":
    main()
