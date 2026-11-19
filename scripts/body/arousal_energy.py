#!/usr/bin/env python3
"""WO30A step 2, report only (BRAIN_SPEC 7.47.6): arousal_b7 and ear energy against Kosta's dials and the five excerpts.  Brain env.

  arousal_energy.py OUTDIR      OUTDIR/numbers.json, lags.csv, excerpts.csv, and docs/AROUSAL_ENERGY_REPORT.md
Method: each signal and each dial axis -> 2 s moving mean (20 samples at 10 Hz) -> every 5th sample (2 Hz); Pearson and Spearman at every lag
-2 .. +4 s in 0.5 s steps, dial behind music = positive; all lags reported, none picked.  Excerpts: mean over the 12 s shown, ranked.
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.stats import pearsonr, spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "brain"))
import ear_energy as ee

ROOT = Path(__file__).resolve().parents[2]
LANES = "/secondary/hyst-data/body/k5/danced/lanes/{}.npz"
DIAL2, DIAL1 = "/secondary/hyst-data/emotion/dial/dial2.json", "/secondary/hyst-data/emotion/dial/dial-ic-try1.json"
TOY = Path("/secondary/hyst-data/body/motornet_toy")
CHECK = {"blue-lagoon": ("Blue Lagoon - Masayoshi Takanaka.mp3", 20.0), "schizoid-man": ("King Crimson - 21st Century Schizoid Man (Including Mirrors) - King Crimson.mp3", 58.0),
         "epitaph": ("King Crimson - Epitaph (Including March For No Reason and Tomorrow And Tomorrow) - King Crimson.mp3", 345.0),
         "breathe": ("Pink Floyd - Breathe (In The Air) (2023 Remaster) - Pink Floyd.mp3", 77.0), "one-of-these-days": ("Pink Floyd - One Of These Days (Official Audio) - Pink Floyd.mp3", 237.0)}
DANCED = {"instant-crush": "song1.m4a", "five-years": "song2.m4a", "presence": "song3.m4a"}
LAGS = np.arange(-4, 9)  # steps of 0.5 s = -2 .. +4 s


def two_hz(x):
    return uniform_filter1d(np.asarray(x, float), 20, mode="nearest")[4::5]  # sample i at (i+.5)*.1 s -> grid 0.5, 1.0, ...


def on_lane_grid(t, v, n):
    return np.interp((np.arange(n) + 0.5) * 0.1, t, v)


def lag_rows(sig, dial):
    s, d = two_hz(sig), two_hz(dial)
    rows = []
    for k in LAGS:  # dial(t) against signal(t - lag): dial index i + k pairs with signal index i
        a, b = (s[:len(s) - k], d[k:]) if k >= 0 else (s[-k:], d[:len(d) + k])
        n = min(len(a), len(b)); a, b = a[:n], b[:n]
        rows.append(dict(lag_s=float(k) / 2, n=int(n), pearson=float(pearsonr(a, b)[0]), spearman=float(spearmanr(a, b)[0])))
    return rows


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    import b2
    feats = {}
    for s in DANCED:
        feats[s] = np.load(out / f"{s}.feat.npy")
    for s, (f, _) in CHECK.items():
        p = out / f"{s}.feat.npy"
        if not p.is_file():
            np.save(p, b2.fast_features(b2.decode(Path("/secondary/hyst-data/audio/checkset") / f)).astype(np.float32))
        feats[s] = np.load(p)
    ear = {s: ee.lane(f) for s, f in feats.items()}
    ar = {s: np.load(LANES.format(s))["arousal_b7"] for s in DANCED}
    ar.update({s: np.load(TOY / "work3" / f"{s}.lanes.npz")["arousal_b7"] for s in CHECK})
    d2, d1 = json.load(open(DIAL2)), json.load(open(DIAL1))
    dials = []  # (song, pass, axis, note, t, v)
    names = {"song1.m4a": "instant-crush", "song2.m4a": "five-years", "song3.m4a": "presence"}
    for t in d2["takes"]:
        if t["status"] != "done":
            continue
        x = np.array(t["samples"], float)
        for j, ax in enumerate(("energy",) if t["pass"] == "A" else ("light", "heavy")):
            dials.append((names[t["song"]], t["pass"], ax, "dial2", x[:, 0], x[:, 1 + j]))
    x = np.array(d1["songs"][0]["samples"], float)
    dials.append(("instant-crush", "A", "energy", "TRY1 (older pad, arousal axis, partial take)", x[:, 0], x[:, 2]))
    lag_out = []
    for song, ps, ax, src, t, v in dials:
        for name, sig in (("arousal_b7", ar[song]), ("ear_energy", ear[song])):
            n = len(sig)
            for r in lag_rows(sig, on_lane_grid(t, v, n)):
                lag_out.append(dict(song=song, pass_=ps, axis=ax, dial_source=src, signal=name, **r))
    both = []
    for s in ar:
        n = min(len(ar[s]), len(ear[s]))
        a, b = two_hz(ar[s][:n]), two_hz(ear[s][:n])
        both.append(dict(song=s, n=len(a), pearson=float(pearsonr(a, b)[0]), spearman=float(spearmanr(a, b)[0])))
    key = json.loads((TOY / "session_2026-11-13_part3" / "key" / "key.json").read_text())["key"]
    ans = {r[0]: r for r in csv.reader(open(TOY / "session_2026-11-13_part3" / "answers.csv"))}
    notes = {k["song"]: (ans[c][1], ans[c][2], k["first_setting"], k["second_setting"]) for c, k in key.items() if c in ans}
    ex = []
    for s, (_, st) in CHECK.items():
        sl = slice(int(round(st * 10)), int(round((st + 12) * 10)))
        e = ear[s][sl].mean()
        ex.append(dict(song=s, start_s=st, arousal_raw=float(ar[s][sl].mean()), ear_raw=float(e),
                       ear_std=float(np.clip((e - ee.norm()["mu"]) / ee.norm()["sd"], -3, 3))))
    mu, sd = _ar_norm(ar)
    for r in ex:
        r["arousal_std"] = float(np.clip((r["arousal_raw"] - mu) / sd, -3, 3))
        r["pick"], r["note"], r["first_setting"], r["second_setting"] = notes.get(r["song"], ("", "", "", ""))
    for k in ("arousal_raw", "ear_raw"):
        order = sorted(ex, key=lambda r: -r[k])
        for i, r in enumerate(order):
            r["rank_" + k] = i + 1
    (out / "numbers.json").write_text(json.dumps(dict(lags=lag_out, arousal_vs_ear=both, excerpts=ex), indent=1))
    for name, rows in (("lags.csv", lag_out), ("excerpts.csv", ex), ("arousal_vs_ear.csv", both)):
        with open(out / name, "w", newline="") as f:
            w = csv.DictWriter(f, rows[0].keys()); w.writeheader(); w.writerows(rows)
    (ROOT / "docs" / "AROUSAL_ENERGY_REPORT.md").write_text(report(lag_out, both, ex))
    print("done", len(lag_out), "lag rows")


def _ar_norm(ar):
    a = np.concatenate([ar[s] for s in DANCED])
    return float(a.mean()), float(a.std())


def f(x):
    return f"{x:.3f}" if isinstance(x, float) else str(x)


def tab(head, rows):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(f(c) for c in r) + " |" for r in rows])


def report(lag_out, both, ex):
    o = ["# Arousal and ear energy against Kosta's dials and the five excerpts (WO30A, BRAIN_SPEC 7.47)", "",
         "Numbers only. No verdict, no interpretation. Formula of ear energy: `docs/EAR_ENERGY_RULES.md`. Method: each signal and each dial axis "
         "is smoothed with a 2 s moving mean and taken at 2 Hz; Pearson and Spearman at every lag from -2 s to +4 s in 0.5 s steps "
         "(positive lag = dial behind the music). All lags are listed; none is picked. n is the number of 2 Hz pairs.", "",
         "**Instant Crush pass A is the first try on the older pad (file `dial-ic-try1.json`, arousal axis, take stopped at about 329 s): it is marked TRY1 in every table.**", ""]
    keys = []
    for r in lag_out:
        k = (r["song"], r["pass_"], r["axis"], r["dial_source"])
        if k not in keys:
            keys.append(k)
    for k in keys:
        song, ps, ax, src = k
        o += [f"## {song}, pass {ps}, {ax}" + (" (TRY1, older pad)" if src != "dial2" else ""), ""]
        rows = []
        for lag in sorted({r["lag_s"] for r in lag_out}):
            row = [f"{lag:+.1f}"]
            for sg in ("arousal_b7", "ear_energy"):
                r = next(r for r in lag_out if (r["song"], r["pass_"], r["axis"], r["dial_source"], r["signal"], r["lag_s"]) == (*k, sg, lag))
                row += [r["pearson"], r["spearman"]]
            row.append(r["n"])
            rows.append(row)
        o += [tab(["lag s", "arousal_b7 Pearson", "arousal_b7 Spearman", "ear energy Pearson", "ear energy Spearman", "n"], rows), ""]
    o += ["## arousal_b7 against ear energy, lag 0, per song", "", tab(["song", "n", "Pearson", "Spearman"], [[r["song"], r["n"], r["pearson"], r["spearman"]] for r in both]), "",
          "## The five excerpts (12 s shown in round 1), mean of each signal, ranked, beside Kosta's Part 3 notes", "",
          tab(["song", "start s", "arousal_b7 raw", "arousal_b7 std", "rank", "ear energy raw", "ear energy std", "rank", "settings first / second", "pick", "Kosta's note"],
              [[r["song"], r["start_s"], r["arousal_raw"], r["arousal_std"], r["rank_arousal_raw"], r["ear_raw"], r["ear_std"], r["rank_ear_raw"],
                f"{r['first_setting']} / {r['second_setting']}", r["pick"], r["note"].replace("|", "/").replace("\n", " ")] for r in ex]), ""]
    return "\n".join(o)


if __name__ == "__main__":
    main()
