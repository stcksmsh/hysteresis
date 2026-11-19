"""Compare two sidecar JSON files under the equivalence rule; print one report block.

Rule (fixed before any real comparison): identical key sets and array lengths;
identical non-float values (ints, strings, bools, null) and identical event/section
types and labels; every float within 1e-6 absolute OR 1e-9 relative of the TS value.
Reports per top-level field: element count, max abs diff, max rel diff, verdict.
usage: compare.py TS.json PY.json NAME   (exit 1 if any field fails)"""
import json
import sys


def walk(a, b, path, stats, errs):
    if isinstance(a, dict):
        if not isinstance(b, dict) or list(a.keys()) != list(b.keys()):
            errs.append(f'{path}: keys differ {list(a.keys())[:6]} vs {list(b.keys())[:6] if isinstance(b, dict) else type(b)}')
            return
        for k in a:
            walk(a[k], b[k], f'{path}.{k}', stats, errs)
    elif isinstance(a, list):
        if not isinstance(b, list) or len(a) != len(b):
            errs.append(f'{path}: length {len(a)} vs {len(b) if isinstance(b, list) else type(b)}')
            return
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, f'{path}[{i}]', stats, errs)
    elif isinstance(a, bool) or isinstance(a, str) or a is None:
        if a != b:
            errs.append(f'{path}: {a!r} vs {b!r}')
    else:
        if isinstance(b, (dict, list, str)) or b is None or isinstance(b, bool):
            errs.append(f'{path}: type {a!r} vs {b!r}')
            return
        d = abs(a - b)
        r = d / abs(a) if a != 0 else (0.0 if d == 0 else float('inf'))
        s = stats
        s['n'] += 1
        s['abs'] = max(s['abs'], d)
        s['rel'] = max(s['rel'], r) if d > 0 else s['rel']
        if not (d <= 1e-6 or r <= 1e-9):
            s['bad'] += 1
            if s['bad'] <= 3:
                errs.append(f'{path}: {a!r} vs {b!r} (abs {d:.3g}, rel {r:.3g})')


def main():
    ts, py, name = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), sys.argv[3]
    ok = True
    if list(ts.keys()) != list(py.keys()):
        print(f'{name}: TOP-LEVEL KEYS DIFFER {list(ts.keys())} vs {list(py.keys())}')
        ok = False
    for k in ts:
        if k not in py:
            continue
        stats = {'n': 0, 'abs': 0.0, 'rel': 0.0, 'bad': 0}
        errs = []
        walk(ts[k], py[k], k, stats, errs)
        n = len(ts[k]) if isinstance(ts[k], (list, dict)) else 1
        good = not errs and stats['bad'] == 0
        ok &= good
        print(f'{name}\t{k}\tlen={n}\tnums={stats["n"]}\tmaxabs={stats["abs"]:.3e}\tmaxrel={stats["rel"]:.3e}\t{"PASS" if good else "FAIL"}')
        for e in errs[:5]:
            print('   ', e)
    sys.exit(0 if ok else 1)


main()
