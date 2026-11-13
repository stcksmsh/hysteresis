"""WO32B retarget look test driver. Rules: docs/RETARGET_RULES.md. Output root /secondary/hyst-data/body/retarget_look/.

    retarget_run.py clips      body env: seeded picks, V1 and V2 sims, gates, replacements, audio excerpts -> work/C<nn>_V<1|2>.{csv,json}, work/picks.json
    retarget_run.py prep       brain env: whole-song beat grid + cortex lanes for the 2 reference clips' songs (seed 32021)
    retarget_run.py refs       body env: round-1 S03 on those clips' music/window -> work/C<nn>_R1S03.{csv,json}
    retarget_run.py manifest   body env: numbers.json + manifest.json (after the render)
Data and audio stay outside git.
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
OUT = Path("/secondary/hyst-data/body/retarget_look")
W = OUT / "work"
CLIPS = OUT / "clips"
FD = Path("/secondary/hyst-data/datasets/finedance/data/finedance")
ROUND1 = Path("/secondary/hyst-data/body/motornet_toy")
SEED, SHOW_S, PRE_S, N_CLIPS = 32011, 20.0, 1.5, 10
JN = ("base_yaw", "shoulder", "elbow", "wrist_bend", "wrist_roll")


def catalogue():
    """-> {seq id: (genre lowercase, song name, n_frames)}, eligible = at least 25 s"""
    cat = {}
    for p in sorted((FD / "motion").glob("*.npy")):
        lab = json.loads((FD / "label_json" / f"{p.stem}.json").read_text())
        cat[p.stem] = (lab["style2"].lower(), lab["name"], int(np.load(p, mmap_mode="r").shape[0]))
    return cat


def pick(k, order, cat):
    """candidate k of the seeded stream: genre order[k % len], sequence and window start from default_rng(SEED + 100 + k)"""
    g = order[k % len(order)]
    el = sorted(s for s, (gg, _, n) in cat.items() if gg == g and n / 30.0 >= REF_MIN)
    r = np.random.default_rng(SEED + 100 + k)
    s = el[int(r.integers(len(el)))] if len(el) > 1 else el[0]
    n = cat[s][2]
    return dict(k=k, genre=g, seq=s, song=cat[s][1], start_s=float(r.uniform(5.0, n / 30.0 - SHOW_S)))


REF_MIN = 25.0


def patch_gates():
    import dialstudy as D
    import motornet as M
    D.CLIP_S = SHOW_S
    M.WARM_S = PRE_S
    return D, M


_ANG = {}


def human(seq):
    import retarget as RT
    if seq not in _ANG:
        _ANG[seq] = RT.sequence_angles(FD / "motion" / f"{seq}.npy")
    return _ANG[seq]


def sim_variant(c, var):
    """pick c, variant 'V1'|'V2' -> q50 (1001, 5), contacts, limiter shares, gate dict"""
    import retarget as RT
    D, M = patch_gates()
    v = human(c["seq"])[0 if var == "V1" else 1]
    i0 = round(c["start_s"] * RT.FPS)
    y = RT.to_commands(RT.referenced(v, i0), var)
    G = RT.to_100hz(y, c["start_s"] - PRE_S, SHOW_S + PRE_S)
    q50, contacts = M.simulate_goals(G)
    lim = M.limiter_out(G)[round(PRE_S * 100):]
    tgt = G[round(PRE_S * 100):]
    p = lambda a: np.percentile(a, 95, axis=0) - np.percentile(a, 5, axis=0)
    share = (p(lim) / np.maximum(p(tgt), 1e-9)).tolist()
    g = D.gate_values(q50, contacts)
    mv = M.motion_values(q50)
    ok, parts = D.judge(g, M.THR)
    parts["motion"] = mv["extent_m"] >= M.MIN_EXTENT_M and mv["min_stretch_speed"] >= M.MIN_SPEED
    gates = dict(passed=bool(ok and parts["motion"]), parts=parts, values={**g, **mv}, thresholds=M.THR)
    return q50, share, gates


def excerpt(seq, start, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-t", f"{SHOW_S}", "-i", str(FD / "music_wav" / f"{seq}.wav"),
                    "-ac", "2", "-ar", "48000", "-c:a", "aac", "-b:a", "192k", str(out)], check=True)


def numbers_of(q50, share, gates):
    import m3f_report as R
    h = R.fk_points(q50)[:, 5]
    sp = np.linalg.norm(np.diff(h, axis=0), axis=1) * 50
    return dict(limiter_share=dict(zip(JN, share)), limiter_cut=dict(zip(JN, [1 - s for s in share])), gates=gates["values"],
                gates_parts=gates["parts"], joint_p5_p95=dict(zip(JN, [[float(np.percentile(q50[:, j], 5)), float(np.percentile(q50[:, j], 95))] for j in range(5)])),
                mean_hand_speed=float(sp.mean()))


def cmd_clips():
    import arm_sim
    import dialstudy as D
    W.mkdir(parents=True, exist_ok=True)
    cat = catalogue()
    order = [str(g) for g in np.random.default_rng(SEED).permutation(sorted({v[0] for v in cat.values()}))]
    print("genre order", order, flush=True)
    slots, failures, k = [], [], 0
    cache = {}
    def attempt(c):
        res = {}
        for var in ("V1", "V2"):
            q50, share, g = sim_variant(c, var)
            res[var] = (q50, share, g)
        ok = all(r[2]["passed"] for r in res.values())
        print(f"cand {c['k']} {c['genre']} seq {c['seq']} start {c['start_s']:.1f}", "ok" if ok else "FAIL",
              {v: {p: x for p, x in r[2]["parts"].items() if not x} for v, r in res.items()}, flush=True)
        if not ok:
            failures.append(dict(cand=c, **{v: dict(parts=r[2]["parts"], values=r[2]["values"]) for v, r in res.items()}))
        return ok, res
    while len(slots) < N_CLIPS:
        c = pick(k, order, cat)
        k += 1
        ok, res = attempt(c)
        if ok:
            slots.append((c, res))
        if k > 200:
            sys.exit("too many failures: STOP")
    # a failed candidate is replaced by the next pick in the stream; slot order = candidate order (rules (e))
    picks = []
    for n, (c, res) in enumerate(slots, 1):
        cid = f"C{n:02d}"
        for var, (q50, share, g) in res.items():
            (W / f"{cid}_{var}.csv").write_text(arm_sim.csv_text(q50, D.HZ, name=f"{cid}_{var}"))
            (W / f"{cid}_{var}.json").write_text(json.dumps(dict(id=f"{cid}_{var}", clip=cid, variant=var, pick=c, gates=g, numbers=numbers_of(q50, share, g)), indent=1))
        excerpt(c["seq"], c["start_s"], W / f"{cid}.m4a")
        picks.append(dict(clip=cid, **c))
    (W / "picks.json").write_text(json.dumps(dict(genre_order=order, picks=picks, candidates_used=k, failures=failures), indent=1))
    print("clips done, candidates", k, "failures", len(failures))


def ref_clips():
    r = np.random.default_rng(32021).choice(N_CLIPS, 2, replace=False)
    return sorted(int(i) for i in r)


def cmd_prep():
    import torch
    torch.set_num_threads(6)
    import b2
    import motornet_music as MM
    from analyze.structure import analyze_mix
    from analyze.wav import DecodedWav
    picks = json.loads((W / "picks.json").read_text())["picks"]
    (W / "wav").mkdir(exist_ok=True)
    for i in ref_clips():
        c = picks[i]
        wav = W / "wav" / f"{c['seq']}.wav"
        if not wav.exists():
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(FD / "music_wav" / f"{c['seq']}.wav"), "-ac", "1", "-ar", "44100", str(wav)], check=True)
        bj = W / f"{c['seq']}.beats.json"
        if not bj.exists():
            y = b2.load_mono(wav)
            d = analyze_mix(DecodedWav(44100, [y], len(y) / 44100))
            bj.write_text(json.dumps({"beats": d["beats"], "tempo": d["tempo"]}))
        if not (W / f"{c['seq']}.lanes.npz").exists():
            MM.cmd_lanes(str(wav), str(bj), str(W / f"{c['seq']}.lanes.npz"))
        print("lanes", c["clip"], c["seq"], flush=True)


def cmd_refs():
    import arm_sim
    import dialstudy as D
    import motornet_music as MM
    import motornet as M
    M.calibration()                                                      # the one fit, at round 1's 12 s, before SHOW_S changes
    patch_gates()
    M.SHOW_S = SHOW_S
    M.WARM_S = 10.0
    st = json.loads((ROUND1 / "settings.json").read_text())["settings"]
    s03 = next(s for s in st if s["id"] == "S03")
    picks = json.loads((W / "picks.json").read_text())["picks"]
    for i in ref_clips():
        c = picks[i]
        lanes = np.load(W / f"{c['seq']}.lanes.npz")
        q50, _, g = M.run_setting(s03["values"], u_fn=MM.music_input(lanes, c["start_s"], 10.0))
        cid = c["clip"]
        (W / f"{cid}_R1S03.csv").write_text(arm_sim.csv_text(q50, D.HZ, name=f"{cid}_R1S03"))
        (W / f"{cid}_R1S03.json").write_text(json.dumps(dict(id=f"{cid}_R1S03", clip=cid, variant="R1_S03", pick=c, setting="S03", setting_values=s03["values"], gates=g,
                                                          numbers=numbers_of(q50, [1.0] * 5, g)), indent=1))
        print(cid, "R1S03 passed", g["passed"], g["parts"], flush=True)


def cmd_manifest():
    picks = json.loads((W / "picks.json").read_text())["picks"]
    refs = [f"C{i + 1:02d}" for i in ref_clips()]
    man, nums = [], {}
    for c in picks:
        cid = c["clip"]
        credit = f'"{c["song"]}", FineDance dataset (Li et al., ICCV 2023), used locally for research'
        for var in ("V1", "V2") + (("R1_S03",) if cid in refs else ()):
            sid = f"{cid}_{'R1S03' if var == 'R1_S03' else var}"
            j = json.loads((W / f"{sid}.json").read_text())
            assert j["gates"]["passed"] and (CLIPS / f"{sid}.mp4").exists(), sid
            man.append(dict(id=sid, kind="single", file=f"{sid}.mp4", variant=var, clip=cid, genre=c["genre"], source_seq=c["seq"],
                            window_start_s=c["start_s"], csv=f"{sid}.csv", music_credit=credit))
            nums[sid] = j["numbers"]
    rng = np.random.default_rng(32031)
    pair_clips = sorted(int(i) for i in rng.choice(N_CLIPS, 5, replace=False))
    r2 = np.random.default_rng(32041)
    n_v1 = 2 + int(r2.integers(2))
    v1_first = {int(i) for i in r2.choice(5, n_v1, replace=False)}
    for pi, ci in enumerate(pair_clips):
        c = picks[ci]
        a, b = ("V1", "V2") if pi in v1_first else ("V2", "V1")
        man.append(dict(id=f"PAIR_{c['clip']}", kind="pair", files=[f"{c['clip']}_{a}.mp4", f"{c['clip']}_{b}.mp4"], variants=[a, b], clip=c["clip"], genre=c["genre"]))
    (OUT / "manifest.json").write_text(json.dumps(man, indent=1))
    (OUT / "numbers.json").write_text(json.dumps(nums, indent=1))
    print("manifest", len(man), "items; pairs", pair_clips, "V1 first in", sorted(v1_first))


if __name__ == "__main__":
    {"clips": cmd_clips, "prep": cmd_prep, "refs": cmd_refs, "manifest": cmd_manifest}[sys.argv[1]]()
