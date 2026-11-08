"""K5-pass2 check (work order 18; docs/BRAIN_SPEC.md 7.18-7.32). Provisional servo model (Feetech STS3215 12 V assumed). One arm. Imports k5_eval / k5_train / k5_video_* / m3f* / k5p2_train; edits none.

    k5p2_eval.py check   --policy best.pkl --out DIR [--max-windows N]     the K5 check on the 1,071 held-out windows (3 per song, 357 songs): trained / untrained / kappa = 0, WO7 observer procedure,
                                                                           per-song paired bootstrap, ARGMAX decides, sampled reported; plus the report-only lines on the held-out rollouts
    k5p2_eval.py songs   --policy best.pkl --out DIR [--songs a,b] [--max-blocks N]
                                                                           the three danced songs as ONE continuous episode each (WO12 recipe on the pass2 body): joint CSV, hyst check-csv,
                                                                           (e'1)/(e'2) against hf_v47_eprime_reference.json, report-only lines, readability per 60 s
    k5p2_eval.py summary --out DIR                                         DIR/summary.json from the two parts (bar components with intervals, verdicts)
Resume-safe: a finished json / csv / npz is kept, finished rollout batches are kept. SIGTERM stops after the current batch.

Pass2 = the policy of k5p2_train.CFG (cfg is read from best.pkl when present). The bar (7.26-7.30): ARGMAX external (a) interval above 0 AND paired (a)_trained - (a)_untrained interval above 0
(K5 bar, k5_eval.py); `hyst check-csv` accepted on each danced song; (e'1) <= limit_acc and (e'2) <= limit_gt1 per song (reference json). Everything else is report only; the kappa = 0 difference
decides the inner-rhythm wording (7.31.3). End stops: m3f_endstop.analyse (hand acceleration and jerk within +-0.05 s of an event vs the whole trajectory, 50 and 100 Hz, pooled over episodes
and mean of per-episode values); for a danced song the "episodes" are its whole-song trajectory (one) and its full 60 s segments (a last partial segment is not used there).
"""
import argparse
import json
import pickle
import subprocess
import sys
import time
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

import arm_sim
import k5_eval as E
import k5_train as T
import k5_video_breaches as VB
import k5_video_roll as VR
import k5_video_seg as SEG
import k5p2_train as P2
import m3d
import m3d_controls as K
import m3e_jax as M
import m3f
import m3f_controls as MFC
import m3f_endstop as ES
import m3f_jax as F
import m3f_park_diag as D
import m3f_gate17 as G17
import m3f_report as R

REF = Path(__file__).resolve().parent.parent.parent / "docs" / "hf_v47_eprime_reference.json"
HYST = "/secondary/hyst-data/cargo-target-wo12/release/hyst"
SONGS = VR.SONGS
SEG_BLOCKS = 120


def jdump(o):
    return json.dumps(o, default=lambda x: x.tolist() if hasattr(x, "tolist") else float(x))


def load_policy(path):
    d = pickle.loads(Path(path).read_bytes())
    t = d["trainer"] if "trainer" in d else d
    cfg = d.get("cfg") or P2.CFG
    return jax.tree_util.tree_map(jnp.asarray, t["P"]), t["stats"], cfg


def make_fns(C, cfg):
    return m3f.make_fns(C, cfg, P2.OPTS)


# ---------------------------------------------------------------------------------------------------------------- shared report-only lines
def clip_boundary(q):
    """q (E, T, 5) deg at 100 Hz -> holds >= 2 s within 1 deg of 109.5 and under half on the stop (as m3f_gate17)."""
    kept = []
    for h in D.find_holds(q, D.BOUNDARY, D.BOUNDARY_TOL):
        on = np.abs(np.abs(q[h["episode"], h["start"]:h["end"], h["joint"]]) - D.STOP) < D.TOL_DEG
        if on.mean() < 0.5:
            kept.append({"episode": h["episode"], "joint": h["name"], "start_s": h["start"] / 100.0, "end_s": h["end"] / 100.0})
    return {"n": len(kept), "total_s": float(sum(k["end_s"] - k["start_s"] for k in kept)), "per_joint_s": {nm: float(sum(k["end_s"] - k["start_s"] for k in kept if k["joint"] == nm)) for nm in D.JOINTS.values()}}


def endstops(q4, workdir, name):
    """q4 (E, NB, 50, 5) -> m3f_endstop.analyse summary (per-event list dropped)."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    np.savez(workdir / f"{name}_argmax_4.npz", q=q4)
    a = ES.analyse(workdir, name, "argmax")
    return {"summary": a["summary"], "n_events": len(a["per_event"])}


def report_lines(q4, workdir, name):
    """The report-only lines for q4 (E, NB, 50, 5) deg at 100 Hz (E windows, or E = 1 whole song): (e), contact, within 2 deg / on a stop, holds, parking, end stops."""
    q = q4.reshape(len(q4), -1, 5)
    ep = R.eprime_rollout(q4)
    out = {"e": {"mean": ep["e_mean"], "per_episode": ep["e"]}, "eprime": {k: ep[k] for k in ("acc_p99", "fast", "contact", "contact_s")} | {k: ep[k] for k in ep if k.endswith("_mean")},
           "near_limit": {k: {kk: vv for kk, vv in v.items() if kk != "within_per_episode"} for k, v in R.near_limit(q4).items()},
           "parking": G17.parking(q), "clip_boundary_holds": clip_boundary(q), "stop_holds_ge_2s": {"n": len(D.find_holds(q)), "total_s": float(sum((h["end"] - h["start"]) / 100.0 for h in D.find_holds(q)))},
           "shoulder_at_limit_share": float((np.abs(np.abs(q[..., 1]) - ES.LIMIT_DEG) < ES.TOL).mean()),
           "end_stops": endstops(q4, workdir, name)}
    return out


# ---------------------------------------------------------------------------------------------------------------- the K5 check on the held-out windows
def stitched_q(rolldir, name, mode="argmax"):
    """The held-out windows' joint trajectories from the cached batches of the evaluation rollout (k = 4)."""
    fs = sorted(Path(rolldir).glob(f"{name}_{mode}_4_b*.npz"), key=lambda p: int(p.stem.rsplit("_b", 1)[1]))
    return np.concatenate([np.load(f)["q"] for f in fs])


def evaluate(P, name, combo, songs, stats, C, fns, cfg, modes, outdir, log):
    f = outdir / f"{name}.json"
    if f.exists():
        return json.loads(f.read_text())
    res = P2.score_modes(fns, cfg, C, P, stats, combo, modes, str(outdir / "rollouts"), name, log)
    for m in res.values():
        for d in ("ext", "int"):
            m[d]["song"] = E.song_stats(m[d]["a_gaps"], songs)
    f.write_text(jdump(res))
    return res


def run_check(a, log):
    out = Path(a.out)
    (out / "rollouts").mkdir(parents=True, exist_ok=True)
    k5 = Path(a.k5)
    w = json.loads((k5 / "windows.json").read_text())
    order = T.train_order(w["train"])
    chk = [(r[0], r[2]) for r in w["check"]][:a.max_windows]
    songs = [s for s, _ in chk]
    combo = P2.combine(P2.build_toy(k5, "train", T.obs_windows(order)), P2.build_toy(k5, "check", chk))
    C = M.load_cb()
    P, stats, cfg = load_policy(a.policy)
    fns = make_fns(C, cfg)
    modes = tuple(a.modes.split(","))
    res = {"trained": evaluate(P, "trained", combo, songs, stats, C, fns, cfg, modes, out, log)}
    for name, Q in (("untrained", MFC.initial_policy(cfg)), ("trained_kappa0", K.with_kappa(P, np.zeros(5)))):
        res[name] = evaluate(Q, name, combo, songs, stats, C, fns, cfg, modes, out, log)
    kap = np.array(res["trained"][modes[0]]["kappa_mean"])
    summ = {"cfg": cfg, "n_songs": len(set(songs)), "n_windows": len(chk), "kappa_trained_means": kap.tolist(), "modes": {}}
    for m in modes:
        s = {}
        for dec in ("ext", "int"):
            tr = res["trained"][m][dec]
            s[dec] = {"trained": {k: tr["song"][k] for k in ("a_song_mean", "a_ci", "a_pass")},
                      **{f"paired_vs_{c}": {k: v for k, v in E.paired_songs(tr["a_gaps"], res[c][m][dec]["a_gaps"], songs).items() if k != "per_episode"} for c in ("untrained", "trained_kappa0")}}
            s[dec]["beats_untrained"] = bool(s[dec]["paired_vs_untrained"]["ci"][0] > 0)
            s[dec]["beats_kappa0"] = bool(s[dec]["paired_vs_trained_kappa0"]["ci"][0] > 0)
        t = res["trained"][m]
        s["b_rms_nonroll"], s["c_mi"], s["c_p"], s["programs_used"] = t["b_rms_nonroll"], t["c_mi"], t["c_p"], t["programs_used"]
        cnt = np.asarray(t.get("program_counts", []), float)
        s["program_counts"], s["program_top_share"] = cnt.tolist(), (float(cnt.max() / cnt.sum()) if cnt.sum() else None)
        s["eprime_heldout"] = {k: t["eprime"][k] for k in t["eprime"] if k.endswith("_mean")}
        s["k5_pass"] = bool(s["ext"]["trained"]["a_pass"] and s["ext"]["beats_untrained"]) if m == "argmax" else None
        summ["modes"][m] = s
    q4 = stitched_q(out / "rollouts", "trained")
    summ["report_only_heldout_windows_trained_argmax"] = report_lines(q4, out / "work_heldout", "trained")
    (out / "check.json").write_text(jdump(summ))
    log("check summary: " + json.dumps({m: {"k5_pass": v["k5_pass"], "ext_a": v["ext"]["trained"]["a_song_mean"], "ext_a_ci": v["ext"]["trained"]["a_ci"], "beats_untrained": v["ext"]["beats_untrained"],
                                           "beats_kappa0": v["ext"]["beats_kappa0"]} for m, v in summ["modes"].items()}))
    return summ


# ---------------------------------------------------------------------------------------------------------------- the danced songs
def episode_inputs(y, phi_end, omega):
    """k5_video_roll.episode_inputs plus the L3 order parameter input R of the previous block (as k5p2_train.WindowToyF)."""
    inps, yz = VR.episode_inputs(y, phi_end, omega)
    ty = m3d.transform_state(np.asarray(y, float)[None])
    r = np.clip(np.hypot(ty[..., 2], ty[..., 3]), 0.0, 1.0)
    inps["R"] = jnp.asarray(np.concatenate([np.zeros_like(r[:, :1]), r[:, :-1]], 1))
    return inps, yz


KEEP = ("q", "desc", "idesc", "pi", "logits", "kappa", "ms", "energy")


def rollout_song(fns, cfg, C, P, inps, max_blocks=None, cb=VR.CB, start_seed=VR.START_SEED, log=None):
    """One continuous episode over the blocks of `inps` (argmax, the cfg's block function; carry never reset). -> dict with q (nb, 50, 5) deg at 100 Hz, q0, and KEEP outputs."""
    nb = inps["x"].shape[1] if max_blocks is None else max_blocks
    q0 = m3d.start_poses(1, start_seed)
    carry = jax.vmap(lambda q: F.init_carry(cfg, q, C))(jnp.asarray(q0))
    outs = []
    t0 = time.time()
    for c0 in range(0, nb, cb):
        c1 = min(c0 + cb, nb)
        if c1 - c0 < cb:                                   # a last partial chunk: only whole chunks (nb is a multiple of cb in the real run)
            break
        carry, o = fns["hard"]["argmax"](P, carry, m3d.take(inps, c0, c1))
        outs.append({k: np.asarray(o[k])[0] for k in KEEP})
        T.check()
        if log and (c0 // cb) % 10 == 0:
            log(f"  block {c0}/{nb} ({time.time() - t0:.0f} s)")
    r = {k: np.concatenate([o[k] for o in outs], 0) for k in outs[0]}
    r["q0"] = q0[0]
    return r


def pad_chunks(inps, cb):
    """Pad the per-block inputs to a multiple of cb blocks by repeating the last block (the padded outputs are dropped)."""
    nb = inps["x"].shape[1]
    pad = (-nb) % cb
    if not pad:
        return inps, nb
    return {k: jnp.concatenate([v, jnp.repeat(v[:, -1:], pad, 1)], 1) for k, v in inps.items()}, nb


def check_csv(path):
    p = subprocess.run([HYST, "check-csv", str(path)], capture_output=True, text=True)
    return {"accepted": p.returncode == 0 and "accepted" in p.stdout, "returncode": p.returncode, "output_head": "\n".join(p.stdout.splitlines()[:12])}


def fit_observers(out, cfg, stats, k5):
    """The check's trained-argmax observer-training rollouts (cached by the check step) -> fresh observers, as SEG.fit_observers does for try 1."""
    w = json.loads((Path(k5) / "windows.json").read_text())
    toy = P2.build_toy(k5, "train", T.obs_windows(T.train_order(w["train"])))
    rolls = []
    for k in range(4):
        d = np.load(Path(out) / "rollouts" / f"trained_argmax_{k}_b0.npz")
        rolls.append({x: d[x] for x in d.files})
    return m3f.fresh_observers(cfg, rolls, toy.yz, stats)


def run_songs(a, log):
    out = Path(a.out)
    sd = out / "songs"
    sd.mkdir(parents=True, exist_ok=True)
    C = M.load_cb()
    P, stats, cfg = load_policy(a.policy)
    fns = make_fns(C, cfg)
    ref = json.loads(REF.read_text())
    Oe = Oi = None
    res = {}
    for name in a.songs.split(","):
        T.check()
        T.wait_mains(log)
        f = sd / f"{name}.json"
        if f.exists():
            res[name] = json.loads(f.read_text())
            log(f"{name}: kept")
            continue
        npz, csv = sd / f"{name}.pass2.npz", sd / f"{name}.pass2.csv"
        z = np.load(Path(a.lanes) / f"{name}.npz")
        inps, yz = episode_inputs(z["y"], z["phi_end"], z["omega"])
        if a.max_blocks:
            inps = {k: v[:, :a.max_blocks] for k, v in inps.items()}
            yz = yz[:, :a.max_blocks]
        padded, nb = pad_chunks(inps, VR.CB)
        if npz.exists() and csv.exists():
            r = dict(np.load(npz))
        else:
            log(f"{name}: {nb} blocks ({nb / 2:.0f} s)")
            r = rollout_song(fns, cfg, C, P, padded, log=log)
            r = {k: (v[:nb] if k != "q0" else v) for k, v in r.items()}
            rows = VR.csv_rows(r["q"], r["q0"])
            csv.write_text(arm_sim.csv_text(rows, hz=50, name=f"{name}.pass2"))
            tmp = Path(str(npz) + ".tmp.npz")
            np.savez_compressed(tmp, yz=yz[0], rows50=rows, **r)
            tmp.replace(npz)
        q4 = r["q"][None]
        rep = report_lines(q4, sd / "work", name)
        full = (nb // SEG_BLOCKS) * SEG_BLOCKS
        rep["end_stops_60s_segments"] = endstops(r["q"][:full].reshape(-1, SEG_BLOCKS, 50, 5), sd / "work", name + "-seg") if full else None
        rep["csv_seconds"], rep["audio_blocks"] = float((len(VR.csv_rows(r["q"], r["q0"])) - 1) / 50), nb
        cnt = np.bincount(np.argmax(r["pi"], -1), minlength=r["pi"].shape[-1]).astype(float)
        rep["programs"] = {"counts": cnt.tolist(), "used": int((cnt > 0).sum()), "top_share": float(cnt.max() / cnt.sum())}
        rep["check_csv"] = check_csv(csv)
        rep["breach_counts"] = VB.count(csv)
        e1, e2 = rep["eprime"]["acc_p99"][0], rep["eprime"]["fast"][0]
        lim = ref[name]
        rep["eprime_vs_v47"] = {"e1": e1, "e1_limit": lim["limit_acc"], "e1_pass": bool(e1 <= lim["limit_acc"]), "e2": e2, "e2_limit": lim["limit_gt1"], "e2_pass": bool(e2 <= lim["limit_gt1"]),
                                "v47_acc_p99": lim["acc_p99"], "v47_gt1": lim["gt1"]}
        if Oe is None:
            Oe, Oi = fit_observers(out, cfg, stats, a.k5)
        rep["readability_per_60s"] = SEG.song_segments({k: r[k] for k in ("desc", "idesc")}, yz[0], Oe, Oi, stats)
        f.write_text(jdump(rep))
        res[name] = rep
        log(f"{name}: check-csv {'accepted' if rep['check_csv']['accepted'] else 'REFUSED'}; e'1 {e1:.3f} (<= {lim['limit_acc']:.3f}) e'2 {e2:.5f} (<= {lim['limit_gt1']:.5f}); "
            f"programs {rep['programs']['used']}; contact {rep['eprime']['contact_s'][0]:.1f} s; shoulder at limit {rep['shoulder_at_limit_share']:.4f}")
    return res


# ---------------------------------------------------------------------------------------------------------------- summary
def run_summary(a, log):
    out = Path(a.out)
    chk = json.loads((out / "check.json").read_text())
    songs = {p.stem: json.loads(p.read_text()) for p in sorted((out / "songs").glob("*.json"))}
    am = chk["modes"]["argmax"]
    comp = {"k5_ext_a_above_0": am["ext"]["trained"]["a_pass"], "k5_beats_untrained": am["ext"]["beats_untrained"], "k5_pass": am["k5_pass"]}
    for n, s in songs.items():
        comp[f"check_csv_{n}"] = s["check_csv"]["accepted"]
        comp[f"eprime1_{n}"], comp[f"eprime2_{n}"] = s["eprime_vs_v47"]["e1_pass"], s["eprime_vs_v47"]["e2_pass"]
    summ = {"components": comp, "pass2_bar": bool(all(comp.values())), "k5_check": chk, "songs": {n: {k: v for k, v in s.items() if k != "readability_per_60s"} for n, s in songs.items()},
            "readability_per_60s": {n: s["readability_per_60s"] for n, s in songs.items()},
            "kappa0_wording": {m: {d: {"mean": chk["modes"][m][d]["paired_vs_trained_kappa0"]["mean"], "ci": chk["modes"][m][d]["paired_vs_trained_kappa0"]["ci"]} for d in ("ext", "int")} for m in chk["modes"]}}
    (out / "summary.json").write_text(jdump(summ))
    log("components: " + json.dumps(comp) + f" | pass2 bar {'MET' if summ['pass2_bar'] else 'NOT met'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=("check", "songs", "summary"))
    ap.add_argument("--policy", default="/secondary/hyst-data/body/k5p2/run/best.pkl")
    ap.add_argument("--out", default="/secondary/hyst-data/body/k5p2/check")
    ap.add_argument("--k5", default=str(T.K5))
    ap.add_argument("--modes", default="argmax,sample")
    ap.add_argument("--max-windows", type=int, help="test only: the first N check windows")
    ap.add_argument("--songs", default=",".join(SONGS))
    ap.add_argument("--lanes", default=str(VR.DANCED / "lanes"))
    ap.add_argument("--max-blocks", type=int, help="test only: the first N blocks of each song")
    a = ap.parse_args()
    T.install_signals()
    t0 = time.time()
    log = lambda s: print(f"[{time.time() - t0:7.0f}s] {s}", flush=True)
    T.wait_mains(log)
    {"check": run_check, "songs": run_songs, "summary": run_summary}[a.what](a, log)


if __name__ == "__main__":
    try:
        main()
    except T.Interrupted:
        print("interrupted; finished batches are kept, rerun the same command to resume", flush=True)
        sys.exit(0)
