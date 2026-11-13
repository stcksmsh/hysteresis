"""WO29C motor-network toy test Part 3 (music pairs). Rules: docs/MOTORNET_RULES.md, BRAIN_SPEC 7.46. Network unchanged.

    motornet_part3.py prep       brain env: per song decode, beat grid (analyze_mix, as the corpus grids), cortex lanes, 12 s audio excerpt
    motornet_part3.py clips      body env: draw 2 shown settings per song (seed 29031), simulate with music input, gate, write work3/P3_<n>_<a|b>.*
    motornet_part3.py replace    body env: replace the failing sims by 7.46.7
    motornet_part3.py manifest   body env: part3_numbers.json, manifest_parts124.json copy, manifest.json with the Part 3 items (after the render)
Audio stays outside git.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "brain"))
sys.path.insert(0, str(HERE.parent))
ROOT = Path("/secondary/hyst-data/body/motornet_toy")
W3 = ROOT / "work3"
C = ROOT / "clips"
AUDIO = Path("/secondary/hyst-data/audio/checkset")
SEED = 29031
# (slug, file, excerpt start s)
SONGS = [("blue-lagoon", "Blue Lagoon - Masayoshi Takanaka.mp3", 20.0),
         ("schizoid-man", "King Crimson - 21st Century Schizoid Man (Including Mirrors) - King Crimson.mp3", 58.0),
         ("epitaph", "King Crimson - Epitaph (Including March For No Reason and Tomorrow And Tomorrow) - King Crimson.mp3", 345.0),
         ("breathe", "Pink Floyd - Breathe (In The Air) (2023 Remaster) - Pink Floyd.mp3", 77.0),
         ("one-of-these-days", "Pink Floyd - One Of These Days (Official Audio) - Pink Floyd.mp3", 237.0)]


def cmd_prep():
    import torch
    torch.set_num_threads(6)
    import b2
    import motornet_music as MM
    from analyze.structure import analyze_mix
    from analyze.wav import DecodedWav
    (W3 / "wav").mkdir(parents=True, exist_ok=True)
    for slug, f, st in SONGS:
        wav = W3 / "wav" / f"{slug}.wav"
        if not wav.exists():
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(AUDIO / f), "-ac", "1", "-ar", "44100", str(wav)], check=True)
        bj = W3 / f"{slug}.beats.json"
        if not bj.exists():
            y = b2.load_mono(wav)
            d = analyze_mix(DecodedWav(44100, [y], len(y) / 44100))
            bj.write_text(json.dumps({"beats": d["beats"], "tempo": d["tempo"]}))
        if not (W3 / f"{slug}.lanes.npz").exists():
            MM.cmd_lanes(str(wav), str(bj), str(W3 / f"{slug}.lanes.npz"))
        MM.cmd_excerpt(str(AUDIO / f), str(st), str(W3 / f"{slug}.m4a"))
        print(slug, "ready", flush=True)


def cmd_clips():
    import arm_sim
    import dialstudy as D
    import motornet as M
    import motornet_music as MM
    st = json.loads((ROOT / "settings.json").read_text())
    shown = [s for s in st["settings"] if s["id"] <= "S10"]
    assert len(shown) == 10
    rng = np.random.default_rng(SEED)
    bad = []
    for n, (slug, f, start) in enumerate(SONGS, 1):
        pick = rng.choice(10, 2, replace=False)
        lanes = np.load(W3 / f"{slug}.lanes.npz")
        for k, i in zip("ab", pick):
            s = shown[int(i)]
            cid = f"P3_{n}{k}"
            q, r, g = M.run_setting(s["values"], u_fn=MM.music_input(lanes, start, M.WARM_S))
            (W3 / f"{cid}.csv").write_text(arm_sim.csv_text(q, D.HZ, name=cid))
            np.save(W3 / f"{cid}.activity.npy", r)
            (W3 / f"{cid}.json").write_text(json.dumps(dict(id=cid, effector="lamp", setting=s["id"], setting_values=s["values"], song=slug, start_s=start, gates=g), indent=1))
            print(cid, slug, s["id"], "passed", g["passed"], g["parts"], flush=True)
            if not g["passed"]:
                bad.append(cid)
    if bad:
        print("GATE FAILURES:", bad, "-> STOP for the overseer")
        sys.exit(2)


def cmd_replace():
    """7.44.3.4 / 7.46.7: continue default_rng(29031) after the 5 original pair draws (replayed, same calls); per failing render in song order draw
    one setting at a time (rng.integers(10); a skipped draw is consumed too), skip the pair's other setting and settings already failed for that song, first pass wins."""
    import arm_sim
    import dialstudy as D
    import motornet as M
    import motornet_music as MM
    shown = [s for s in json.loads((ROOT / "settings.json").read_text())["settings"] if s["id"] <= "S10"]
    rng = np.random.default_rng(SEED)
    pairs = [rng.choice(10, 2, replace=False) for _ in SONGS]
    log = {}
    for n, (slug, f, start) in enumerate(SONGS, 1):
        lanes = np.load(W3 / f"{slug}.lanes.npz")
        for k, i in zip("ab", pairs[n - 1]):
            cid = f"P3_{n}{k}"
            jp = W3 / f"{cid}.json"
            j = json.loads(jp.read_text())
            if j["gates"]["passed"]:
                continue
            orig = dict(setting=j["setting"], gates=j["gates"]["values"], parts=j["gates"]["parts"])
            failed = {int(i)}
            skip = {int(x) for x in pairs[n - 1]}
            rec, draws = [orig], 0
            while True:
                d = int(rng.integers(10))
                draws += 1
                if d in skip or d in failed:
                    continue
                s = shown[d]
                q, r, g = M.run_setting(s["values"], u_fn=MM.music_input(lanes, start, M.WARM_S))
                print(cid, "draw", draws, s["id"], "passed", g["passed"], g["parts"], flush=True)
                if g["passed"]:
                    break
                failed.add(d)
                rec.append(dict(setting=s["id"], gates=g["values"], parts=g["parts"]))
            jp.rename(W3 / f"{cid}.failed0.json")
            (W3 / f"{cid}.csv").write_text(arm_sim.csv_text(q, D.HZ, name=cid))
            np.save(W3 / f"{cid}.activity.npy", r)
            (W3 / f"{cid}.json").write_text(json.dumps(dict(id=cid, effector="lamp", setting=s["id"], setting_values=s["values"], song=slug, start_s=start,
                                                           gates=g, replaced=rec), indent=1))
            log[cid] = dict(replacement=s["id"], failed_before=rec)
    (W3 / "replacements.json").write_text(json.dumps(log, indent=1))
    print(json.dumps(log, indent=1))


def cmd_manifest():
    import motornet_measure as ME
    import motornet_music as MM
    shutil.copy(C / "manifest.json", ROOT / "manifest_parts124.json")
    items = json.loads((ROOT / "manifest_parts124.json").read_text())
    mu, sd = MM.arousal_norm()
    nums = {}
    for n, (slug, f, start) in enumerate(SONGS, 1):
        ar = np.asarray(np.load(W3 / f"{slug}.lanes.npz")["arousal_b7"])
        seg = ar[int(start * 10):int((start + 12) * 10)]
        raw = float(seg.mean())
        std = float(np.clip((seg - mu) / sd, -3, 3).mean())
        sp, files, csvs, acts, setts, gates, rep = [], [], [], [], [], [], []
        for k in "ab":
            cid = f"P3_{n}{k}"
            j = json.loads((W3 / f"{cid}.json").read_text())
            mp4 = C / f"{cid}.mp4"
            assert j["gates"]["passed"] and mp4.exists(), cid
            for ext in (".csv", ".activity.npy"):
                shutil.copy(W3 / f"{cid}{ext}", C / f"{cid}{ext}")
            sp.append(float(ME.hand_speed(ME.hand_path(C / f"{cid}.csv")).mean()))
            files.append(mp4.name); csvs.append(f"{cid}.csv"); acts.append(f"{cid}.activity.npy"); setts.append(j["setting"])
            rep.append([dict(setting=x["setting"], gates=x["gates"], parts=x["parts"]) for x in j.get("replaced", [])])
            gates.append(dict(passed=True, values=j["gates"]["values"], thresholds=j["gates"]["thresholds"]))
        nums[f"P3_{n}"] = dict(song=slug, excerpt_start_s=start, settings=setts, hand_speed=sp, arousal_raw=raw, arousal_std=std,
                               arousal_norm=dict(mean=mu, sd=sd, clip=3))
        items.append(dict(id=f"P3_{n}", part=3, files=files, setting=setts, song=slug, excerpt_start_s=start, csv=csvs, activity=acts,
                          hand_speed=sp, arousal_raw=raw, arousal_std=std, gates=gates, replaced=rep))
        if any(rep):
            nums[f"P3_{n}"]["replaced"] = rep
    (C / "manifest.json").write_text(json.dumps(items, indent=1))
    (ROOT / "part3_numbers.json").write_text(json.dumps(nums, indent=1))
    print(json.dumps(nums, indent=1))


if __name__ == "__main__":
    {"prep": cmd_prep, "clips": cmd_clips, "replace": cmd_replace, "manifest": cmd_manifest}[sys.argv[1]]()
