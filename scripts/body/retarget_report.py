#!/usr/bin/env python3
"""Join a retarget look-test session's answers with its key and 32B's numbers.json into docs/RETARGET_REPORT.md (WO32A).

  retarget_report.py --session SESSION_DIR [--numbers numbers.json] [--out docs/RETARGET_REPORT.md]

Tables only. No verdict, no score. Singles: clip -> variant -> answer -> note, per-variant counts. Pairs: the order shown, the answer and the
variant it names. numbers.json (per clip and variant: limiter share per joint, gate values) is flattened generically: keys with "limit" or "cut"
in the path go to the limiter table, the rest to the gate table.
"""
import argparse, csv, json
from pathlib import Path

LOOK = ["yes", "sort of", "no"]


def cell(s):
    if isinstance(s, float):
        s = f"{s:.3g}"
    return str(s if s not in (None, "") else "-").replace("|", "/").replace("\n", " ")


def table(head, rows):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows])


def flat(d, pre=""):
    out = {}
    for k, v in (d.items() if isinstance(d, dict) else enumerate(d)):
        key = f"{pre}.{k}" if pre else str(k)
        if isinstance(v, (dict, list)):
            out.update(flat(v, key))
        else:
            out[key] = v
    return out


def number_rows(numbers):
    """Yield (clip, variant, flat dict). Accepts {clip: {variant: {...}}} (optionally under "clips"), or a list of dicts with clip/variant fields."""
    n = numbers.get("clips", numbers) if isinstance(numbers, dict) else numbers
    if isinstance(n, list):
        for e in n:
            yield e.get("clip", e.get("id", "-")), e.get("variant", "-"), flat({k: v for k, v in e.items() if k not in ("clip", "variant", "id")})
        return
    for clip, vs in n.items():
        if isinstance(vs, dict) and all(isinstance(v, dict) for v in vs.values()):
            for var, d in vs.items():
                yield clip, var, flat(d)
        else:
            yield clip, "-", flat(vs)


def build(session, numbers_path=None):
    session = Path(session)
    key = json.loads((session / "key" / "key.json").read_text())
    k = key["key"]
    with open(session / "answers.csv", newline="") as f:
        ans = {r[0]: r for r in csv.reader(f) if r}
    singles, pairs = [], []
    for code, m in k.items():
        a = ans.get(code)
        answer, note = (a[1], a[2]) if a else ("(unanswered)", "")
        if m.get("kind") == "pair":
            vs = m.get("variants") or ["?", "?"]
            named = {"first": vs[0], "second": vs[1]}.get(answer, "neither" if answer == "neither" else "-")
            pairs.append([m.get("clip"), m.get("id"), vs[0], vs[1], answer, named, note])
        else:
            singles.append([m.get("clip"), m.get("variant"), m.get("genre"), m.get("id"), answer, note])
    singles.sort(key=lambda r: (str(r[0]), str(r[1])))
    pairs.sort(key=lambda r: str(r[0]))
    out = ["# Retarget look test report", "", f"Session seed {key.get('seed')}. Tables only; no verdict.", ""]
    out += ["## Singles: clip, variant, answer, note", "", table(["clip", "variant", "genre", "id", "answer", "note"], singles), ""]
    variants = sorted({str(r[1]) for r in singles})
    counts = [[v] + [sum(1 for r in singles if str(r[1]) == v and r[4] == lab) for lab in LOOK] + [sum(1 for r in singles if str(r[1]) == v and r[4] == "(unanswered)")] for v in variants]
    out += ["## Singles: counts per variant", "", table(["variant"] + LOOK + ["unanswered"], counts), ""]
    out += ["## Pairs (order as shown)", "", table(["clip", "id", "first", "second", "answer", "names variant", "note"], pairs), ""]
    firsts = {}
    for r in pairs:
        firsts[r[2]] = firsts.get(r[2], 0) + 1
    out += [f"Variant shown first, pairs: {', '.join(f'{v} {n}' for v, n in sorted(firsts.items())) or '-'}.", ""]
    pc = {}
    for r in pairs:
        if r[4] != "(unanswered)":
            pc[r[5]] = pc.get(r[5], 0) + 1
    out += [f"Answers naming a variant (neither counted as such): {', '.join(f'{v} {n}' for v, n in sorted(pc.items())) or '-'}; unanswered {sum(1 for r in pairs if r[4] == '(unanswered)')}.", ""]
    if numbers_path:
        rows = list(number_rows(json.loads(Path(numbers_path).read_text())))
        lim, gate = [], []
        for clip, var, d in rows:
            for kk, v in d.items():
                (lim if any(s in kk.lower() for s in ("limit", "cut")) else gate).append([clip, var, kk, v])
        out += ["## Per-joint limiter cuts (numbers.json)", "", table(["clip", "variant", "value", "number"], lim) if lim else "None found.", ""]
        out += ["## Gate values and other measurements (numbers.json)", "", table(["clip", "variant", "value", "number"], gate) if gate else "None found.", ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", required=True); ap.add_argument("--numbers"); ap.add_argument("--out", default="docs/RETARGET_REPORT.md")
    a = ap.parse_args()
    Path(a.out).write_text(build(a.session, a.numbers))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
