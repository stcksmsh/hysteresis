#!/usr/bin/env python3
"""Join a dial-study session's answers with its key into docs/DIALSTUDY_REPORT.md (WO28B).

  dialstudy_report.py --session SESSION_DIR [--out docs/DIALSTUDY_REPORT.md]

Tables only: the intended setting next to Kosta's label. No verdict, no score, no counts of correct answers.
"""
import argparse, csv, json
from pathlib import Path

DIALS = ["vigour", "stiffness", "roundness", "lag", "posture"]


def intent_text(i):
    i = i or {}
    k = i.get("kind")
    if k == "dial":
        return f"{i.get('dial')} {i.get('level')}"
    if k == "preset":
        return f"preset {i.get('preset')}"
    return "all neutral" if k == "neutral" else str(k or "?")


def cell(s):
    return str(s if s not in (None, "") else "-").replace("|", "/").replace("\n", " ")


def table(head, rows):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows])


def report(session):
    session = Path(session)
    key = json.loads((session / "key" / "key.json").read_text())["key"]
    with open(session / "answers.csv", newline="") as f:
        ans = {r[0]: r for r in csv.reader(f) if r}
    label = lambda code: ans[code][1] if code in ans else "(not answered)"
    note = lambda code: ans[code][2] if code in ans else ""
    singles = {c: k for c, k in key.items() if k.get("set") != "D"}
    pairs = {c: k for c, k in key.items() if k.get("set") == "D"}
    order = lambda kv: (str(kv[1].get("set")), str(kv[1].get("id")))
    out = ["# Dial study report", "",
           "Kosta's labels next to what was set. No verdict and no score here: what it means is Kosta's call.",
           "Dial notes (ranges, preset values, servo plausibility): see `docs/DIALSTUDY_DIALS.md`.", ""]

    out += ["## Every clip", "", table(["id", "set", "intended", "effector", "label", "note"],
            [[k.get("id"), k.get("set"), intent_text(k.get("intent")), k.get("effector"), label(c), note(c)] for c, k in sorted(singles.items(), key=order)]), ""]

    by = {}
    for c, k in singles.items():
        i = k.get("intent") or {}
        by[(i.get("kind"), i.get("dial"), i.get("level"), i.get("preset"), k.get("effector"))] = c
    neutral = next((label(c) for (kind, *_), c in by.items() if kind == "neutral"), "(none)")
    out += ["## Per dial: low / neutral / high", "", table(["dial", "low", "neutral (all dials neutral)", "high"],
            [[d] + [next((label(c) for (kind, dl, lv, _, _), c in by.items() if kind == "dial" and dl == d and lv == lvl), "(none)") for lvl in ("low",)]
             + [neutral] + [next((label(c) for (kind, dl, lv, _, _), c in by.items() if kind == "dial" and dl == d and lv == "high"), "(none)")] for d in DIALS]), ""]

    presets = sorted({k["intent"].get("preset") for k in singles.values() if (k.get("intent") or {}).get("kind") == "preset"})
    ball = lambda p, eff: next((c for (kind, _, _, pr, ef), c in by.items() if kind == "preset" and pr == p and ef == eff), None)
    out += ["## Presets (ball): intended vs label", "", table(["preset", "label", "note"],
            [[p, label(ball(p, "ball")) if ball(p, "ball") else "(none)", note(ball(p, "ball")) if ball(p, "ball") else ""] for p in presets]), ""]

    effs = ["ball", "lamp", "gripper"]
    out += ["## End effectors: the same preset", "", table(["preset"] + effs,
            [[p] + [label(ball(p, e)) if ball(p, e) else "(none)" for e in effs] for p in presets]), ""]

    if pairs:
        rows = []
        for c, k in sorted(pairs.items(), key=order):
            a = ans.get(c)
            chosen = {"first": k.get("first"), "second": k.get("second")}.get(a[1], "-") if a else "(not answered)"
            rows.append([k.get("id"), intent_text(k.get("intent")), a[1] if a else "(not answered)", chosen, note(c)])
        out += ["## Set D: which render fits the music", "", table(["excerpt", "intended", "pick", "chosen render", "note"], rows), ""]
    else:
        out += ["## Set D", "", "Not run (no pairs in this session).", ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", required=True)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "docs" / "DIALSTUDY_REPORT.md"))
    a = ap.parse_args()
    Path(a.out).write_text(report(a.session) + "\n")
    print("wrote", a.out)


if __name__ == "__main__":
    main()
