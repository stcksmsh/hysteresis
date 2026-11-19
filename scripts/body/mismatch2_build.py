"""WO55 part B: mismatch test round 2 material (re-timed, arm-only). Rules: docs/MISMATCH2_RULES.md (read first). Brain env.

    mismatch2_build.py plan        draw 20 pairs + 5 repeats -> retime/b/material_key.json, render_root/work/<id>_V?.csv|json, <id>.m4a
    (render: RETARGET_ROOT=/secondary/hyst-data/body/retime/b/render_root RETARGET_PAGE=armonly_page.py HYST_BATTERY_OK=1 taskset -c 6-13 scripts/body/retarget_render.sh IDS)
    mismatch2_build.py assemble    round-1 assembly (mismatch_build.cmd_assemble) into retime/b/, manifest gets the "intro" text
    mismatch2_build.py checks      round-1 clip checks + retime check + arm-only page check + overlap with round 1 -> clip_checks.json, retime_checks.json
    mismatch2_build.py order SESSION_DIR   round-1 order checks (mismatch_order) -> retime/b/order_checks.json
Round-1 functions are reused unchanged; only what docs/MISMATCH2_RULES.md section 0 changes is new here. Nothing is served.
"""
import json
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mismatch_build as M  # noqa: E402
from retime import L  # noqa: E402

B = M.B
OUT = B / "retime/b"
M.OUT = OUT                       # every round-1 function reads the module global at call time
R1KEY = B / "mismatch/material_key.json"
SEED = 53201
SHIFT_MIN, SHIFT_MAX = 4.0, 6.0
INTRO = ("Each clip shows the SAME arm movement twice, with a short black pause between the two halves. Only the music differs. "
         "In some clips the other music is the same song at a different moment, so both halves can sound alike; in others it is a "
         "different song. Question: in which half does the music fit the movement better? \"same\" is a valid answer. Please answer "
         "after the first pass of the clip, then give your confidence.")


# ------------------------------------------------------------------ pure logic
def shift_foil(rng, start, dur):
    """round 1's rule with |offset| uniform in [4, 6] s on a 0.1 grid -> (offset_s, outside_q3) or None"""
    mag = rng.randint(int(SHIFT_MIN * 10), int(SHIFT_MAX * 10)) / 10.0
    sign = rng.choice([-1, 1])
    fits = lambda o, lo, hi: lo <= start + o and start + o + M.EXC <= hi
    for lo, hi, flag in ((10.0, dur - 10.0, False), (0.0, dur, True)):
        for s in (sign, -sign):
            if fits(s * mag, lo, hi):
                return round(s * mag, 1), flag
    return None


def offsets(variant):
    """window offsets on the 0.5 s grid with offset + L + 10 <= 20 (the excerpt plus its L inside the kept window)"""
    return [o / 2 for o in range(0, 21) if o / 2 + L[variant] + M.EXC <= 20.0 + 1e-9]


def retimed_rows(qwin, offset_s, variant, hz=50):
    """q50 of one kept window (rows k at k / hz) -> the clip's 501 CSV rows at window time offset + L + k / hz (linear interpolation)"""
    t = (offset_s + L[variant]) * hz + np.arange(int(M.EXC * hz) + 1)
    assert t[-1] <= len(qwin) - 1 + 1e-9, "excerpt + L outside the kept window"
    x = np.arange(len(qwin))
    return np.stack([np.interp(t, x, qwin[:, j]) for j in range(qwin.shape[1])], axis=1)


def foil_candidates(rng, key, ds, lists, used):
    """-> [(dataset, song)]: every other dataset's songs (one seeded-shuffled pool) first, then the movement's own dataset"""
    other = [(d, k) for d in sorted(lists) if d != ds for k in sorted(lists[d]) if k not in used]
    same = [(ds, k) for k in sorted(lists[ds]) if k != key and k not in used]
    rng.shuffle(other); rng.shuffle(same)
    return other + same


def round1_songs():
    it = json.loads(R1KEY.read_text())["items"]
    return {s for x in it.values() for s in (x["song"], x["foil"]["song"])}


# ------------------------------------------------------------------ plan
def pick_diff_foil(rng, key, ds, lists, song, used):
    bs = M.beats_of(key)
    if bs is None or len(bs) < 4:
        return None
    t_real = M.tempo_bpm(bs)
    for d, k in foil_candidates(rng, key, ds, lists, used):
        b = M.beats_of(k)
        if b is None or len(b) < 4 or not M.tempo_ok(t_real, M.tempo_bpm(b)):
            continue
        try:
            f = song(k)
        except Exception:  # noqa: BLE001
            continue
        st = f.starts(10.0, f.dur - 10.0 - M.EXC)
        if st:
            return dict(song=k, dataset=d, offset_s=None, excerpt_start_s=rng.choice(st), tempo_bpm_real=t_real, tempo_bpm_foil=M.tempo_bpm(b),
                        tempo_ratio=M.tempo_bpm(b) / t_real), d == ds
    return None


def cmd_plan():
    rng = random.Random(SEED)
    plan = M.assign(rng)
    lists = {ds: M.songs_of(ds) for ds in M.LISTS}
    cache = {}

    def song(key):
        if key not in cache:
            ds = next(d for d in M.LISTS if key in lists[d])
            cache[key] = M.Song(key, lists[ds][key])
        return cache[key]

    r1 = round1_songs()
    pairs, used = [], set(r1)          # round-1 songs are excluded as movement and as foil
    for ds in M.QUOTA:
        pool = M.movement_pool(ds)
        keys = [k for k in sorted(pool) if k in lists[ds]]
        rng.shuffle(keys)
        todo = list(plan[ds])
        for key in keys:
            if not todo:
                break
            if key in used:
                continue
            ver, kind = todo[0]
            wins = pool[key].get(ver)
            if not wins:
                continue
            try:
                s = song(key)
            except Exception as e:  # noqa: BLE001
                print("skip", key, e, file=sys.stderr); continue
            cand = [(w, i, o) for w, i in wins for o in offsets(ver) if s.ok(20.0 * w + o)]
            if not cand:
                continue
            rng.shuffle(cand)
            for w, i, o in cand:
                start = 20.0 * w + float(o)
                foil, same_ds, outside = None, False, False
                if kind == "shifted":
                    r = shift_foil(rng, start, s.dur)
                    if r:
                        foil = dict(song=key, dataset=ds, offset_s=r[0], excerpt_start_s=round(start + r[0], 1), tempo_bpm_real=None, tempo_bpm_foil=None, tempo_ratio=None)
                        outside = r[1]
                else:
                    got = pick_diff_foil(rng, key, ds, lists, song, used | {key})
                    if got:
                        foil, same_ds = got
                if foil:
                    pairs.append(dict(dataset=ds, version=ver, kind=kind, song=key, window=w, q_index=i, window_offset_s=float(o), excerpt_start_s=start,
                                      excerpt_end_s=start + M.EXC, retime_L_s=L[ver], movement_csv_start_s=float(o) + L[ver], foil=foil,
                                      foil_outside_q3=outside, foil_same_dataset=same_ds, rms_real=s.rms10(start), rms_foil=song(foil["song"]).rms10(foil["excerpt_start_s"])))
                    used.add(key)
                    if kind == "different_song":
                        used.add(foil["song"])
                    todo.pop(0)
                    break
        if todo:
            raise SystemExit(f"{ds}: could not fill {len(todo)} pairs")
    rng.shuffle(pairs)
    sides, rep = M.draw_sides_and_repeats(rng, [p["kind"] for p in pairs])
    items = {}
    for n, (p, sd) in enumerate(zip(pairs, sides), 1):
        pid = f"P{n:02d}"
        items[pid] = dict(id=pid, repeat=False, repeat_of=None, real_side=sd, **p)
    reps = list(rep); rng.shuffle(reps)
    for n, i in enumerate(reps, 1):
        o = items[f"P{i + 1:02d}"]
        items[f"R{n:02d}"] = {**o, "id": f"R{n:02d}", "repeat": True, "repeat_of": o["id"], "real_side": "second" if o["real_side"] == "first" else "first"}
    key = dict(version=1, seed=SEED, rule=dict(threshold=0.70, flip_form="lower95 > 0.5 + f/2"), retime_L=L, items=items)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "material_key.json").write_text(json.dumps(key, indent=1, default=float))
    write_work(items, lists)
    print("planned", len(items), "items")


def q50_window(it):
    z = np.load(B / "controls/q50" / M.Q50[it["dataset"]] / f"{it['song']}__{it['version']}.npz")
    return z["q50"][it["q_index"]].astype(float)


def write_work(items, lists):
    """one retarget_render work file per distinct movement, CSV re-timed by L (rules section 0 item 1); the music m4a is the unshifted excerpt"""
    import subprocess
    import arm_sim
    W = OUT / "render_root/work"
    W.mkdir(parents=True, exist_ok=True)
    for it in items.values():
        if it["repeat"]:
            continue
        q = retimed_rows(q50_window(it), it["window_offset_s"], it["version"])
        cid = f"{it['id']}_{it['version']}"
        (W / f"{cid}.csv").write_text(arm_sim.csv_text(q, 50, name=cid))
        (W / f"{cid}.json").write_text(json.dumps(dict(id=cid, clip=it["id"], variant=it["version"], retime_L_s=it["retime_L_s"],
                                                       gates=dict(passed=True, note="stored realised q50 of a kept window, gate_again true, re-timed by L"))))
        wav = lists[it["dataset"]][it["song"]]
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{it['excerpt_start_s']:.3f}", "-t", f"{M.EXC}", "-i", str(wav), "-ac", "2", "-ar", "48000",
                        "-c:a", "aac", "-b:a", "192k", str(W / f"{it['id']}.m4a")], check=True)


# ------------------------------------------------------------------ assemble / checks / order
def cmd_assemble():
    M.cmd_assemble()
    man = json.loads((OUT / "manifest.json").read_text())
    (OUT / "manifest.json").write_text(json.dumps(dict(intro=INTRO, **man), indent=1))


def read_csv_rows(p):
    return np.array([[float(x) for x in l.split(",")] for l in Path(p).read_text().splitlines() if l and l[0].isdigit()])


def cmd_checks():
    import armonly_page
    M.cmd_checks()
    key = json.loads((OUT / "material_key.json").read_text())["items"]
    res = {}
    for i, it in sorted(key.items()):
        o = key[it["repeat_of"]] if it["repeat"] else it
        cid = f"{o['id']}_{o['version']}"
        rows = read_csv_rows(OUT / f"render_root/work/{cid}.csv")
        qw = q50_window(o)
        x = (o["window_offset_s"] + L[o["version"]]) * 50 + np.arange(len(rows))
        ref = np.stack([np.interp(x, np.arange(len(qw)), qw[:, j]) for j in range(5)], axis=1)
        page = (OUT / f"render_root/work/pages/{cid}.html").read_text()
        c = dict(retime_L_s=it["retime_L_s"], L_ok=it["retime_L_s"] == L[it["version"]], csv_rows=len(rows), rows_ok=len(rows) == 501,
                 time_col_max_err=float(np.abs(rows[:, 0] - np.arange(len(rows)) / 50).max()),
                 first_row_max_err_deg=float(np.abs(rows[0, 1:] - ref[0]).max()), all_rows_max_err_deg=float(np.abs(rows[:, 1:] - ref).max()),
                 arm_only_page=armonly_page.is_arm_only(page))
        c["retime_ok"] = c["L_ok"] and c["rows_ok"] and c["all_rows_max_err_deg"] <= 1e-3 and c["time_col_max_err"] <= 1e-6
        c["pass"] = c["retime_ok"] and c["arm_only_page"]
        res[i] = c
    r1 = round1_songs()
    P = [x for x in key.values() if not x["repeat"]]
    ov = {ds: sorted({s for x in P if x["dataset"] == ds for s in (x["song"], x["foil"]["song"]) if s in r1}) for ds in M.QUOTA}
    out = dict(items=res, overlap_round1=ov, overlap_ok=not any(ov.values()),
               foil_same_dataset=sorted(x["id"] for x in P if x["kind"] == "different_song" and x["foil_same_dataset"]),
               foil_datasets={x["id"]: [x["dataset"], x["foil"]["dataset"]] for x in P if x["kind"] == "different_song"},
               shift_offsets={x["id"]: x["foil"]["offset_s"] for x in P if x["kind"] == "shifted"},
               foil_outside_q3=sorted(x["id"] for x in P if x["foil_outside_q3"]))
    out["pass"] = all(c["pass"] for c in res.values()) and out["overlap_ok"]
    (OUT / "retime_checks.json").write_text(json.dumps(out, indent=1, default=float))
    print("retime checks pass:", sum(c["pass"] for c in res.values()), "/", len(res), "overlap ok:", out["overlap_ok"])


def cmd_order(session):
    import mismatch_order
    mismatch_order.OUT = OUT
    mismatch_order.main(session)


if __name__ == "__main__":
    {"plan": cmd_plan, "assemble": cmd_assemble, "checks": cmd_checks}.get(sys.argv[1], lambda: cmd_order(sys.argv[2]))()
