"""WO42 look clips (BRAIN_SPEC 7.69.3), 6 per source. Rules: docs/T0_PHANTOM_RULES.md section 4. Body env (MuJoCo sim for the gates). Output SOURCE_OUT/look/{work,clips,manifest.json}.

    t0_phantom_look.py SOURCE clips      seeded picks, sim, gates, audio excerpts -> look/work/C<n>_V<1|2>.{csv,json}, C<n>.m4a, picks.json
    (render: RETARGET_ROOT=SOURCE_OUT/look scripts/body/retarget_render.sh)
    t0_phantom_look.py SOURCE manifest   manifest.json of singles for dialstudy_session.py (labels "follow") + numbers.json
No clip is selected by eye: candidates are drawn by seed and kept by the gates only.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "brain"))
sys.path.insert(0, str(HERE.parent))
import t0_phantom_run as PR  # noqa: E402
import retarget as RT  # noqa: E402
import retarget_run as RR  # noqa: E402

N_CLIPS = 6
SHOW_S = RR.SHOW_S
CREDIT = {"phantom": 'PhantomDance dataset (Li et al., AAAI 2022), used locally for research',
          "motorica": 'Motorica Dance Dataset (Alexanderson et al. 2023; Valle-Perez et al. 2021), used locally for research; music by M.P.A Mario Perez Amigo (street) and Stockholm Swing All Stars (jazz)'}


def strata(source, cat):
    if source == "motorica":
        return [("genre", g) for g in ("jazz", "street", "misc", "jazz", "street", "misc")]
    ids = sorted(c["key"] for c in cat)
    parts = np.array_split(np.arange(len(ids)), N_CLIPS)
    return [("keys", {ids[i] for i in p}) for p in parts]


def pick(source, cat, k, slot, taken, stratum):
    kind, val = stratum
    el = sorted((c for c in cat if c["t30"] / 30.0 >= 25.0 and c["key"] not in taken and (c["genre"] == val if kind == "genre" else c["key"] in val)), key=lambda c: c["key"])
    if not el:
        return None
    r = np.random.default_rng(PR.SRC[source]["seed"] + 100 + k)
    c = el[int(r.integers(len(el)))]
    return dict(k=k, slot=slot, key=c["key"], seq=c["key"], genre=c["genre"], song=c["name"], start_s=float(r.uniform(5.0, c["t30"] / 30.0 - SHOW_S)), variant="V1" if slot % 2 == 0 else "V2")


def cmd_clips(source):
    import arm_sim
    import dialstudy as D
    s = PR.SRC[source]
    W = s["out"] / "look" / "work"
    W.mkdir(parents=True, exist_ok=True)
    cat = json.loads((s["out"] / "catalogue.json").read_text())
    by = {c["key"]: c for c in cat}
    sp = {k for r in json.loads((s["out"] / "split.json").read_text())["groups"] for k in r["members"]}
    cat = [c for c in cat if c["key"] in sp]
    st = strata(source, cat)
    slots, fails, k = [], [], 0
    while len(slots) < N_CLIPS and k < 200:
        slot = len(slots)
        c = pick(source, cat, k, slot, {x[0]["key"] for x in slots}, st[slot])
        k += 1
        if c is None:
            print("no eligible sequence for slot", slot, flush=True)
            break
        if c["key"] not in RR._ANG:
            RR._ANG[c["key"]] = RT.human_angles(PR.load(source, by[c["key"]])[0])
        q50, share, g, sh = RR.sim_variant(c, c["variant"])
        print(f"cand {c['k']} slot {slot} {c['variant']} {c['key']} {c['genre']} start {c['start_s']:.1f}", "ok" if g["passed"] else "FAIL " + str([p for p, x in g["parts"].items() if not x]), flush=True)
        if g["passed"]:
            slots.append((c, q50, share, g, sh))
        else:
            fails.append(dict(cand=c, parts=g["parts"], values=g["values"]))
    picks = []
    for n, (c, q50, share, g, sh) in enumerate(slots, 1):
        cid, var = f"C{n:02d}", c["variant"]
        (W / f"{cid}_{var}.csv").write_text(arm_sim.csv_text(q50, D.HZ, name=f"{cid}_{var}"))
        (W / f"{cid}_{var}.json").write_text(json.dumps(dict(id=f"{cid}_{var}", clip=cid, variant=var, pick=c, gates=g, numbers=RR.numbers_of(q50, share, g, sh)), indent=1))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{c['start_s']:.3f}", "-t", f"{SHOW_S}", "-i", by[c["key"]]["wav"], "-ac", "2", "-ar", "48000", "-c:a", "aac", "-b:a", "192k", str(W / f"{cid}.m4a")], check=True)
        picks.append(dict(clip=cid, **c))
    (W / "picks.json").write_text(json.dumps(dict(seed=s["seed"], picks=picks, candidates_used=k, failures=fails), indent=1))
    print("clips", len(picks), "candidates", k)
    if len(picks) < N_CLIPS:
        sys.exit(3)


def cmd_manifest(source):
    s = PR.SRC[source]
    L, W, C = s["out"] / "look", s["out"] / "look" / "work", s["out"] / "look" / "clips"
    picks = json.loads((W / "picks.json").read_text())["picks"]
    man, nums = [], {}
    for p in picks:
        sid = f"{p['clip']}_{p['variant']}"
        j = json.loads((W / f"{sid}.json").read_text())
        assert j["gates"]["passed"] and (C / f"{sid}.mp4").exists(), sid
        man.append(dict(id=sid, kind="single", labels="follow", file=f"clips/{sid}.mp4", variant=p["variant"], clip=p["clip"], genre=p["genre"], source_seq=p["seq"], window_start_s=p["start_s"],
                        csv=f"work/{sid}.csv", music_credit=f'"{p["song"]}", {CREDIT[source]}'))
        nums[sid] = j["numbers"]
    (L / "manifest.json").write_text(json.dumps(man, indent=1))
    (L / "numbers.json").write_text(json.dumps(nums, indent=1))
    print("manifest", len(man), "items")


if __name__ == "__main__":
    a = sys.argv[1:]
    {"clips": cmd_clips, "manifest": cmd_manifest}[a[1]](a[0])
