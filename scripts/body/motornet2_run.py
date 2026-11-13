"""WO30B driver (body env). Rules: docs/MOTORNET2_RULES.md.

    motornet2_run.py sample     draw (seed 30011), gate each candidate silent + 5 songs, keep 8, round-1 S03 reference gates, Part A sims, stop rule
    motornet2_run.py clips      Part B sims (seed 30031): the new setting and round-1 S03 on each song's 30 s excerpt (after sample, if the stop rule did not hit)
    motornet2_run.py manifest   after the renders: manifest.json, numbers.json
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

import arm_sim
import dialstudy as D
import motornet as M
import motornet2 as M2
import motornet_measure as ME
import motornet_music as MM

ROOT = Path("/secondary/hyst-data/body/motornet_toy2")
W2, C2, LN = ROOT / "work", ROOT / "clips", ROOT / "lanes"
R1 = Path("/secondary/hyst-data/body/motornet_toy")
W3 = R1 / "work3"
AUDIO = Path("/secondary/hyst-data/audio/checkset")
SEED_DRAW, SEED_PICK = 30011, 30031
NKEEP, MAXDRAW = 8, 2000
SONGS = [("blue-lagoon", "Blue Lagoon - Masayoshi Takanaka.mp3", 20.0),
         ("schizoid-man", "King Crimson - 21st Century Schizoid Man (Including Mirrors) - King Crimson.mp3", 58.0),
         ("epitaph", "King Crimson - Epitaph (Including March For No Reason and Tomorrow And Tomorrow) - King Crimson.mp3", 345.0),
         ("breathe", "Pink Floyd - Breathe (In The Air) (2023 Remaster) - Pink Floyd.mp3", 77.0),
         ("one-of-these-days", "Pink Floyd - One Of These Days (Official Audio) - Pink Floyd.mp3", 237.0)]
DANCED = ("instant-crush", "five-years", "presence")
FIT = json.loads((ROOT / "motornet2_fit.json").read_text())
M2.INPUT_S = np.array([FIT["input_scale"]["s_slow"], FIT["input_scale"]["s_fast"]])
M.SPINAL_F = FIT["spinal_f"]


def l4_norm():
    """projection of L4 (3 danced songs pooled) -> one mean and sd per signal"""
    p = np.concatenate([np.load(LN / f"{s}.npz")["l4"] @ M2.NET["Pl4"] for s in DANCED])
    return p.mean(0), p.std(0)


def song_inputs(slug):
    """-> dict of the song's lanes: beat y (blocks, 8), l4p (n10, 4) standardised+clipped, energy net, energy raw, arousal std, arousal raw"""
    mu, sd = l4_norm()
    z = np.load(LN / f"{slug}.npz")
    am, asd = MM.arousal_norm()
    e = np.load(LN / f"{slug}.energy.npz")
    return dict(beat_y=np.load(W3 / f"{slug}.lanes.npz")["y"], l4p=np.clip((z["l4"] @ M2.NET["Pl4"] - mu) / sd, -3, 3), energy=e["net"], energy_raw=e["raw"],
                arousal=np.clip((z["arousal_b7"] - am) / asd, -3, 3), arousal_raw=z["arousal_b7"])


def song_u(slug, start):
    s = song_inputs(slug)
    return M2.music_input(s["beat_y"], s["l4p"], s["energy"], s["arousal"], start)


def ref_run(c, slug, start):
    """round-1 network and inputs (unchanged), 10 s warm-up + 30 s"""
    lanes = np.load(W3 / f"{slug}.lanes.npz")
    Y, Rt = M.run_net(c, MM.music_input(lanes, start, M.WARM_S), round((M2.WARM_S + M2.SHOW_S) / M2.DT))
    G = M.spinal(M.to_targets(Y))
    q, contacts = M.simulate_goals(G)
    ok, parts, vals = M2.gate(q, contacts)
    nw = round(M2.WARM_S / M2.DT)
    return q, Rt[nw::2][:len(q)].astype(np.float32), dict(passed=ok, parts=parts, values=vals, thresholds=M.THR)


def save(cid, q, r, g, **extra):
    W2.mkdir(parents=True, exist_ok=True)
    (W2 / f"{cid}.csv").write_text(arm_sim.csv_text(q, D.HZ, name=cid))
    np.save(W2 / f"{cid}.activity.npy", r)
    (W2 / f"{cid}.json").write_text(json.dumps(dict(id=cid, effector="lamp", gates=g, **extra), indent=1))


def joint_stats(q):
    yaw = q[:, 0]
    n3 = round(3 * D.HZ)
    mm = np.convolve(yaw, np.ones(n3) / n3, "valid")
    return dict(base_yaw_p5p95=float(M2.p595(q[:, 0:1])[0]), shoulder_p5p95=float(M2.p595(q[:, 1:2])[0]),
                facing_drift_deg=float(yaw[-n3:].mean() - yaw[:n3].mean()), facing_mm3s_range_deg=float(mm.max() - mm.min()))


def cmd_sample():
    rng = np.random.default_rng(SEED_DRAW)
    lo, hi = np.log(M2.C_LO), np.log(M2.C_HI)
    us = {slug: song_u(slug, st) for slug, _, st in SONGS}
    settings, discards, kept = [], [], 0
    for d in range(1, MAXDRAW + 1):
        c = np.exp(rng.uniform(lo, hi, M2.NCTRL))
        runs = {}
        failed = []
        q, r, g = M2.run_setting(c)
        runs["silent"] = (q, r, g)
        if not g["passed"]:
            failed.append(("silent", [k for k, v in g["parts"].items() if not v], g["values"]["extent_m"]))
        for slug, _, st in SONGS:
            qs, rs, gs = M2.run_setting(c, us[slug])
            if not gs["passed"]:
                failed.append((slug, [k for k, v in gs["parts"].items() if not v], gs["values"]["extent_m"]))
        if not failed:
            kept += 1
            sid = f"S{kept:02d}"
            settings.append(dict(id=sid, values=[float(x) for x in c], draw_index=d))
            save(f"A_{sid}", q, r, g, part="A", setting=sid, setting_values=[float(x) for x in c], network="round2")
            print(f"draw {d} KEEP {sid}", flush=True)
        else:
            discards.append(dict(draw_index=d, values=[float(x) for x in c], failed=[dict(run=a, gates=b, extent_m=e) for a, b, e in failed]))
            print(f"draw {d} DISCARD", [(a, b) for a, b, _ in failed], flush=True)
        if kept == NKEEP:
            break
    per_gate, per_song = {}, {}
    for x in discards:
        for f in x["failed"]:
            per_song[f["run"]] = per_song.get(f["run"], 0) + 1
            for k in f["gates"]:
                per_gate[k] = per_gate.get(k, 0) + 1
    ref = []
    s3 = next(s for s in json.loads((R1 / "settings.json").read_text())["settings"] if s["id"] == "S03")
    for slug, _, st in SONGS:
        q, r, g = ref_run(s3["values"], slug, st)
        ref.append(dict(song=slug, passed=g["passed"], failed=[k for k, v in g["parts"].items() if not v], values=g["values"]))
        print("round-1 S03", slug, "passed", g["passed"], flush=True)
    stats = {}
    for s in settings:
        q = arm_sim_read(W2 / f"A_{s['id']}.csv")
        r = np.load(W2 / f"A_{s['id']}.activity.npy")
        stats[s["id"]] = dict(pr=M2.pr_per_population(r), **joint_stats(q))
    hit = all(v["pr"]["slow"] < 3 and v["pr"]["fast"] < 3 for v in stats.values()) and all(v["base_yaw_p5p95"] < 20 for v in stats.values())
    out = dict(seeds=dict(draw=SEED_DRAW, pick=SEED_PICK), draws=d, kept=kept, settings=settings, discards=discards, discards_per_gate=per_gate, discards_per_run=per_song,
               round1_s03_gates=ref, silent_stats=stats, stop_rule_hit=bool(hit))
    (ROOT / "settings.json").write_text(json.dumps(out, indent=1))
    print("draws", d, "kept", kept, "discards", len(discards), per_gate, per_song, "STOP RULE HIT" if hit else "stop rule not hit")
    for sid, v in stats.items():
        print(sid, v)
    if kept < NKEEP:
        print("FEWER THAN 8 KEPT")
        sys.exit(2)
    sys.exit(3 if hit else 0)


def arm_sim_read(p):
    return ME.read_csv(p)


def cmd_clips():
    st = json.loads((ROOT / "settings.json").read_text())
    shown = st["settings"]
    rng = np.random.default_rng(SEED_PICK)
    pick = rng.choice(len(shown), 5, replace=False)
    s3 = next(s for s in json.loads((R1 / "settings.json").read_text())["settings"] if s["id"] == "S03")
    pairs, bad = [], []
    for n, ((slug, f, start), i) in enumerate(zip(SONGS, pick), 1):
        s = shown[int(i)]
        q, r, g = M2.run_setting(s["values"], song_u(slug, start))
        save(f"B{n}_new", q, r, g, part="B", pair=n, setting=s["id"], setting_values=s["values"], song=slug, start_s=start, network="round2")
        q1, r1, g1 = ref_run(s3["values"], slug, start)
        save(f"B{n}_s03", q1, r1, g1, part="B", pair=n, setting="R1_S03", setting_values=s3["values"], song=slug, start_s=start, network="round1")
        print(f"B{n} {slug} new {s['id']} passed {g['passed']} {g['parts']}; round-1 S03 passed {g1['passed']} {g1['parts']}", flush=True)
        pairs.append(dict(pair=n, song=slug, new=s["id"], new_passed=g["passed"], s03_passed=g1["passed"], s03_failed=[k for k, v in g1["parts"].items() if not v]))
        if not g["passed"]:
            bad.append(f"B{n}_new")
    (W2 / "pairs.json").write_text(json.dumps(dict(pick=[int(i) for i in pick], pairs=pairs), indent=1))
    print("pairs", json.dumps(pairs))
    if bad:
        print("GATE FAILURES in new setting:", bad, "-> STOP for the overseer")
        sys.exit(2)


def cmd_excerpts():
    """30 s excerpts (aac) of the five songs and 30 s of silence, in work/"""
    W2.mkdir(parents=True, exist_ok=True)
    for slug, f, st in SONGS:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(st), "-t", "30", "-i", str(AUDIO / f), "-c:a", "aac", str(W2 / f"{slug}.m4a")], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "30", "-c:a", "aac", str(W2 / "silence30.m4a")], check=True)


def cmd_manifest():
    import shutil
    C2.mkdir(parents=True, exist_ok=True)
    st = json.loads((ROOT / "settings.json").read_text())
    pairs = json.loads((W2 / "pairs.json").read_text())["pairs"]
    items, nums = [], {}
    pop = [0] * M2.NS + [1] * M2.NF
    for j in sorted(W2.glob("[AB]*.json")):
        if j.name == "pairs.json":
            continue
        r = json.loads(j.read_text())
        cid = r["id"]
        mp4 = C2 / f"{cid}.mp4"
        if not (r["gates"]["passed"] and mp4.exists()):
            print("skipped (not rendered or failed):", cid)
            continue
        for ext in (".csv", ".activity.npy"):
            shutil.copy(W2 / f"{cid}{ext}", C2 / f"{cid}{ext}")
        q, act = ME.read_csv(W2 / f"{cid}.csv"), np.load(W2 / f"{cid}.activity.npy")
        h = ME.hand_path(W2 / f"{cid}.csv")
        two = r["network"] == "round2"
        nums[cid] = dict(setting=r["setting"], network=r["network"], hand_speed=float(ME.hand_speed(h).mean()), **joint_stats(q),
                         pr=M2.pr_per_population(act) if two else dict(all=ME.participation_ratio(act)))
        items.append(dict(id=cid, part=r["part"], files=[mp4.name], setting=r["setting"], song=r.get("song"), excerpt_start_s=r.get("start_s"), csv=f"{cid}.csv",
                          activity=f"{cid}.activity.npy", network=r["network"], population_index=pop if two else None, pair=r.get("pair"), gates=r["gates"]))
    songs = {}
    for n, (slug, f, start) in enumerate(SONGS, 1):
        s = song_inputs(slug)
        a, b = int(start * 10), int((start + 30) * 10)
        songs[slug] = dict(excerpt_start_s=start, ear_energy_raw=float(s["energy_raw"][a:b].mean()), ear_energy_input=float(s["energy"][a:b].mean()),
                           arousal_raw=float(s["arousal_raw"][a:b].mean()), arousal_input=float(s["arousal"][a:b].mean()))
    (C2 / "manifest.json").write_text(json.dumps(items, indent=1))
    (ROOT / "numbers.json").write_text(json.dumps(dict(clips=nums, songs=songs), indent=1))
    print(len(items), "clips")


if __name__ == "__main__":
    {"sample": cmd_sample, "clips": cmd_clips, "excerpts": cmd_excerpts, "manifest": cmd_manifest}[sys.argv[1]]()
