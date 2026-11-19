#!/usr/bin/env python
"""Mismatch test scorer (WO53 part A, BRAIN_SPEC 7.84 item 1). Schemas: docs/MISMATCH_RULES.md sections 5, 7, 8.

usage: mismatch_score.py SESSION_DIR
Reads answers.csv (no header: code,answer,note,timestamp,replays), key/key.json, key/material_key.json.
Writes mismatch_result.json and mismatch_result.md. Gives no verdict beyond rule met / not met.
"""
import csv, json, sys
from pathlib import Path
from scipy.stats import beta

THRESH = 0.70


def cp(k, n, alpha, two_sided):
    """Clopper-Pearson interval; one-sided returns (lower, 1.0) at level 1-alpha."""
    if n == 0:
        return (None, None)
    a = alpha / 2 if two_sided else alpha
    lo = 0.0 if k == 0 else float(beta.ppf(a, k, n - k + 1))
    hi = 1.0 if (k == n or not two_sided) else float(beta.ppf(1 - a, k + 1, n - k))
    return (lo, hi)


def load_answers(path):
    """code -> (which, confidence); last row wins."""
    out = {}
    with open(path, newline="") as f:
        for row in csv.reader(f):
            if len(row) < 2 or not row[0].strip():
                continue
            parts = row[1].split("|")
            if len(parts) != 2:
                raise ValueError(f"bad answer {row[1]!r} for code {row[0]}")
            which, conf = (p.strip().lower() for p in parts)
            if which not in ("first", "second", "same") or conf not in ("low", "medium", "high"):
                raise ValueError(f"bad answer {row[1]!r} for code {row[0]}")
            out[row[0].strip()] = (which, conf)
    return out


def presented(which, real_side):
    if which == "same":
        return "tie"
    return "real" if which == real_side else "foil"


def share(choices):
    real = sum(c == "real" for c in choices)
    foil = sum(c == "foil" for c in choices)
    n = real + foil
    d = {"n_non_tie": n, "n_real": real, "ties": sum(c == "tie" for c in choices), "n": len(choices),
         "real_pick_share": real / n if n else None}
    d["ci95"] = list(cp(real, n, 0.05, True))
    d["lower95_one_sided"] = cp(real, n, 0.05, False)[0]
    return d


def rule(d, flip):
    p, lo = d["real_pick_share"], d["lower95_one_sided"]
    if p is None or flip is None:
        return {"rule_met": None, "p_ge_0.70": None, "lower_gt_0.5_plus_f_half": None, "point_gt_0.5_plus_f_half": None}
    bound = 0.5 + flip / 2
    c1, c2 = p >= THRESH, lo > bound
    return {"rule_met": bool(c1 and c2), "p_ge_0.70": bool(c1), "lower_gt_0.5_plus_f_half": bool(c2),
            "point_gt_0.5_plus_f_half": bool(p > bound), "bound": bound}


def score(session):
    session = Path(session)
    ans = load_answers(session / "answers.csv")
    code2id = {c: v["id"] for c, v in json.load(open(session / "key/key.json"))["key"].items()}
    items = json.load(open(session / "key/material_key.json"))["items"]
    id2choice, id2conf = {}, {}
    for code, (which, conf) in ans.items():
        if code not in code2id:
            raise ValueError(f"answer code {code} not in key.json")
        i = code2id[code]
        id2choice[i] = presented(which, items[i]["real_side"])
        id2conf[i] = conf
    firsts = [i for i in id2choice if not items[i]["repeat"]]
    reps = [i for i in id2choice if items[i]["repeat"] and items[i]["repeat_of"] in id2choice]
    flips = [id2choice[r] != id2choice[items[r]["repeat_of"]] for r in reps]
    flip = sum(flips) / len(flips) if flips else None

    res = share([id2choice[i] for i in firsts])
    res.update(rule(res, flip))
    res["flip_rate"] = flip
    res["n_repeat_pairs"] = len(reps)
    res["answered"] = len(id2choice)
    res["complete"] = len(id2choice) == len(items)
    res["by_kind"] = {}
    for k in ("shifted", "different_song"):
        d = share([id2choice[i] for i in firsts if items[i]["kind"] == k])
        d["rule_exploratory"] = rule(d, flip)
        res["by_kind"][k] = d
    # confidence split over first presentations (repeats excluded, as for the share)
    res["by_confidence"] = {c: share([id2choice[i] for i in firsts if id2conf[i] == c]) for c in ("low", "medium", "high")}
    json.dump(res, open(session / "mismatch_result.json", "w"), indent=2)
    md = table(res)
    (session / "mismatch_result.md").write_text(md)
    return res, md


def f(x):
    return "-" if x is None else f"{x:.3f}"


def table(r):
    L = [f"rule met: {r['rule_met']}  (share>=0.70: {r['p_ge_0.70']}; lower95>0.5+f/2: {r['lower_gt_0.5_plus_f_half']}; "
         f"point>0.5+f/2: {r['point_gt_0.5_plus_f_half']})",
         f"answered {r['answered']}  complete {r['complete']}  repeats {r['n_repeat_pairs']}  flip rate {f(r['flip_rate'])}  ties {r['ties']}",
         "", "| group | n non-tie | ties | real-pick share | 95% CI | lower95 (1-sided) |", "|---|---|---|---|---|---|"]

    def row(name, d):
        L.append(f"| {name} | {d['n_non_tie']} | {d['ties']} | {f(d['real_pick_share'])} | {f(d['ci95'][0])}-{f(d['ci95'][1])} | {f(d['lower95_one_sided'])} |")
    row("all", r)
    for k, d in r["by_kind"].items():
        row(k + " (exploratory)", d)
    for c, d in r["by_confidence"].items():
        row("confidence " + c, d)
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    print(score(sys.argv[1])[1])
