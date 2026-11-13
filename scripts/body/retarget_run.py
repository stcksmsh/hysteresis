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
    """20 s clips, 1.5 s pre-roll, and the v2p body (WO32C) in place of the v2f model: dialstudy.make_model is swapped in this process only; no v2f file is edited"""
    import dialstudy as D
    import make_arm_v2p as P
    import motornet as M
    D.CLIP_S = SHOW_S
    M.WARM_S = PRE_S
    D.make_model = P.make_model
    import retarget_limiter as FX
    M.simulate_goals = FX.simulate_goals                                 # rules (k): the limiter with range braking, for V1, V2 and the reference
    return D, M


GUARD_MAX = 0.10
LIMIT_TOL = 1.25                                                          # rules (l): look-test tolerance on speed and acceleration, not a hardware margin


def judge_v2p(g, mv, guard_share=None):
    """the v2p gate verdict from gate values g (dialstudy.gate_values with floor_m replaced), motion values mv and the guard share. dialstudy.judge computes "limits" at 1.05 inside
    its own verdict, so only its parts are used: "limits" is replaced by the 1.25 test of rules (l) and the verdict is all parts."""
    import dialstudy as D
    import motornet as M
    _, parts = D.judge(g, M.THR)
    parts["motion"] = bool(mv["extent_m"] >= M.MIN_EXTENT_M and mv["min_stretch_speed"] >= M.MIN_SPEED)
    parts["limits"] = bool(g["speed_ratio"] <= LIMIT_TOL and g["accel_ratio"] <= LIMIT_TOL and g["finite"])
    vals = {**g, **mv}
    if guard_share is not None:
        vals["guard_share"] = guard_share
        parts["guard"] = bool(guard_share <= GUARD_MAX)
    return dict(passed=bool(all(parts.values())), parts=parts, values=vals, thresholds={**M.THR, "guard_share_max": GUARD_MAX, "limit_tolerance": LIMIT_TOL})


def gates_v2p(q50, contact_substeps, guard_share=None):
    """the v2p gate dict: dialstudy.gate_values with floor_m replaced by the clearance margins of rules (j), plus minimum motion and, for retargeted clips, the guard share"""
    import dialstudy as D
    import make_arm_v2p as P
    import motornet as M
    g = D.gate_values(q50, contact_substeps)
    g["floor_m"] = float(P.margins(q50).min())
    return judge_v2p(g, M.motion_values(q50), guard_share)


def shoulder_numbers(G0, lim, q50, nw):
    """rules (l): commanded and realised shoulder acceleration (p50, p95, max, in multiples of the limit; 50 Hz rows, second difference x 2500 / limit), the limiter's share of 100 Hz
    frames that changed the shoulder command, and the shoulder RMS of (command - limiter output) in deg. G0: command rows (100 Hz, pre-roll included), lim: limiter output rows (same)."""
    import dialstudy as D
    acc = lambda r: np.abs(r[2:, 1] - 2 * r[1:-1, 1] + r[:-2, 1]) * 2500 / D.LIM_A[1]
    st = lambda a: dict(p50=float(np.percentile(a, 50)), p95=float(np.percentile(a, 95)), max=float(a.max()))
    cmd, out = G0[nw:], lim[nw:]
    d = cmd[:, 1] - out[:, 1]
    return dict(commanded_accel_x_limit=st(acc(cmd[::2])), realised_accel_x_limit=st(acc(q50)), limiter_share=float((np.abs(d) > 1e-6).mean()), rms_command_minus_limiter_deg=float(np.sqrt((d ** 2).mean())))


def sim_variant(c, var):
    """pick c, variant 'V1'|'V2' -> q50 (1001, 5), limiter shares, v2p gate dict (with the guard share), shoulder numbers"""
    import make_arm_v2p as P
    import retarget as RT
    import retarget_limiter as FX
    D, M = patch_gates()
    v = human(c["seq"])[0 if var == "V1" else 1]
    i0 = round(c["start_s"] * RT.FPS)
    y = RT.to_commands(RT.referenced(v, i0), var)
    G0 = RT.to_100hz(y, c["start_s"] - PRE_S, SHOW_S + PRE_S)
    G, gshare = P.guard(G0)
    q50, contacts = M.simulate_goals(G)
    nw = round(PRE_S * 100)
    full = FX.limiter_out(G)
    lim = full[nw:]
    tgt = G0[nw:]
    p = lambda a: np.percentile(a, 95, axis=0) - np.percentile(a, 5, axis=0)
    share = (p(lim) / np.maximum(p(tgt), 1e-9)).tolist()
    return q50, share, gates_v2p(q50, contacts, gshare), shoulder_numbers(G0, full, q50, nw)


def excerpt(seq, start, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-t", f"{SHOW_S}", "-i", str(FD / "music_wav" / f"{seq}.wav"),
                    "-ac", "2", "-ar", "48000", "-c:a", "aac", "-b:a", "192k", str(out)], check=True)


def numbers_of(q50, share, gates, shoulder=None):
    import m3f_report as R
    h = R.fk_points(q50)[:, 5]
    sp = np.linalg.norm(np.diff(h, axis=0), axis=1) * 50
    return dict(limiter_share=dict(zip(JN, share)), limiter_cut=dict(zip(JN, [1 - s for s in share])), gates=gates["values"],
                gates_parts=gates["parts"], guard_share=gates["values"].get("guard_share"), joint_p5_p95=dict(zip(JN, [[float(np.percentile(q50[:, j], 5)), float(np.percentile(q50[:, j], 95))] for j in range(5)])),
                mean_hand_speed=float(sp.mean()), shoulder=shoulder)


def cmd_clips():
    import collections
    import arm_sim
    import dialstudy as D
    W.mkdir(parents=True, exist_ok=True)
    cat = catalogue()
    order = [str(g) for g in np.random.default_rng(SEED).permutation(sorted({v[0] for v in cat.values()}))]
    print("genre order", order, flush=True)
    slots, failures, k = [], [], 0
    stats = dict(skipped_by_pick_rule={}, candidates=0, pass_V1=0, pass_V2=0, pass_both=0, discards={"V1": collections.Counter(), "V2": collections.Counter()}, guard_shares={"V1": [], "V2": []})
    while len(slots) < N_CLIPS and k < 200:
        c = pick(k, order, cat)
        k += 1
        res = {var: sim_variant(c, var) for var in ("V1", "V2")}
        stats["candidates"] = k
        for var, (q50, share, g, sh) in res.items():
            stats["pass_" + var] += int(g["passed"])
            stats["guard_shares"][var].append(g["values"]["guard_share"])
            for pn, x in g["parts"].items():
                if not x:
                    stats["discards"][var][pn] += 1
        ok = all(r[2]["passed"] for r in res.values())
        stats["pass_both"] += int(ok)
        skipped = ""
        if ok and c["seq"] in {x[0]["seq"] for x in slots}:
            ok, skipped = False, "pick rule: sequence already taken"
        elif ok and sum(1 for x in slots if x[0]["genre"] == c["genre"]) >= 2:
            ok, skipped = False, "pick rule: two of this genre already taken"
        if skipped:
            stats["skipped_by_pick_rule"][skipped] = stats["skipped_by_pick_rule"].get(skipped, 0) + 1
        print(f"cand {c['k']} {c['genre']} seq {c['seq']} start {c['start_s']:.1f}", "ok" if ok else ("SKIP " + skipped if skipped else "FAIL"),
              {v: [pn for pn, x in r[2]["parts"].items() if not x] for v, r in res.items()}, flush=True)
        if ok:
            slots.append((c, res))
        else:
            failures.append(dict(cand=c, **{v: dict(parts=r[2]["parts"], values=r[2]["values"]) for v, r in res.items()}))
    stats["discards"] = {v: dict(x) for v, x in stats["discards"].items()}
    stats["guard_share_median"] = {v: float(np.median(x)) for v, x in stats["guard_shares"].items()}
    stats["guard_shares"] = {v: [round(float(a), 4) for a in x] for v, x in stats["guard_shares"].items()}
    picks = []
    if len(slots) == N_CLIPS:
        for n, (c, res) in enumerate(slots, 1):
            cid = f"C{n:02d}"
            for var, (q50, share, g, sh) in res.items():
                (W / f"{cid}_{var}.csv").write_text(arm_sim.csv_text(q50, D.HZ, name=f"{cid}_{var}"))
                (W / f"{cid}_{var}.json").write_text(json.dumps(dict(id=f"{cid}_{var}", clip=cid, variant=var, pick=c, gates=g, numbers=numbers_of(q50, share, g, sh)), indent=1))
            excerpt(c["seq"], c["start_s"], W / f"{cid}.m4a")
            picks.append(dict(clip=cid, **c))
    (W / "picks.json").write_text(json.dumps(dict(genre_order=order, picks=picks, candidates_used=k, stats=stats, failures=failures), indent=1))
    summ = {x: stats[x] for x in ("candidates", "pass_V1", "pass_V2", "pass_both", "skipped_by_pick_rule", "discards", "guard_share_median")}
    if len(slots) < N_CLIPS:
        print("HOLD", json.dumps(summ))
        sys.exit(3)
    print("clips done", json.dumps(summ))


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
        q50, _, g0 = M.run_setting(s03["values"], u_fn=MM.music_input(lanes, c["start_s"], 10.0))
        g = gates_v2p(q50, g0["values"]["contact_substeps"])                      # v2p gates (the contact count came from the v2p sim: patch_gates swapped the model)
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
