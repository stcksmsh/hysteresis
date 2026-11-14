"""Stage 3 side-car reports (work order 27, docs/STAGE3_SIDECAR_RULES.md, BRAIN_SPEC 7.41.3). Body env. Report only: never writes into the run folder, never signals its unit.

    s3_sidecar.py watch --run DIR --out DIR [--poll 60] [--test] [--no-clip]      the watcher (poll train.log, per validation: hinge activity; at round 400 also the clip)
    s3_sidecar.py hinges --ckpt PKL --out JSON [--run DIR]                         hinge activity of one checkpoint (test / manual)
    s3_sidecar.py clip --best PKL --out DIR [--seconds 60] [--start 60]            the Instant Crush clip of one best.pkl (test / manual)
Run with `taskset -c 12-17` (cores 6-11 belong to the run) under systemd-run, mains only. One arm.
"""
import argparse
import json
import os
import pickle
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("JAX_PLATFORMS", "cpu")

S3 = Path("/secondary/hyst-data/body/s3")
K5 = Path("/secondary/hyst-data/body/k5")
ONLINE = Path("/sys/class/power_supply/ADP1/online")
HAND_V, JOLT, ACC = 1.2, 9.0, 4.8
LIM_DEG = 100.0
G_NAMES = ["energy", "jerk", "hand_v", "jolt", "acc", "floor", "lim"]
VALID_FROM, NB, BLOCK = 8, 120, 50
N_WIN = 16
VAL_RE = re.compile(r"validation at round (\d+): (.*)")
PASS2_CSV = Path("/secondary/hyst-data/body/k5p2/check/songs/instant-crush.pass2.csv")
AUDIO = Path("/secondary/hyst-data/brain/author/audio/instant-crush.m4a")
PREVIEW = Path("/secondary/hyst-data/cargo-target-wo12/release/examples/ensemble_preview")
RECORD = HERE.parent / "author" / "record_ensemble.cjs"
SLOW_PY = "/secondary/hyst-env/brain/bin/python"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def wait_mains():
    while ONLINE.read_text().strip() != "1":
        log("on battery: waiting")
        time.sleep(30)


# ---------------------------------------------------------------------------------------------------------------- pure counting (tested without JAX rollouts)
def share_stats(q, energy, jerk, thr, cfg_plane):
    """q (E, NB, 50, 5) deg at 100 Hz, energy/jerk (E, NB) block outputs -> dict of shares (rules section 2). Blocks >= VALID_FROM are scored."""
    import jax
    import jax.numpy as jnp
    import m3d_jax as J
    import m3f_jax as F
    E = q.shape[0]
    qf = jnp.asarray(q, jnp.float32).reshape(E, NB * BLOCK, 5)
    hp = np.asarray(jax.vmap(J.hand_points)(qf))[:, 1::2].astype(np.float64)              # 50 Hz hand points, odd control steps: point j belongs to block j // 25
    hv = np.sqrt(((hp[:, 1:] - hp[:, :-1]) ** 2).sum(-1) + 1e-18) * 50.0                  # newest point k + 1
    hj = np.abs(hv[:, 1:] - hv[:, :-1]) * 50.0                                            # newest point k + 2
    ha = np.sqrt(((hp[:, 2:] - 2 * hp[:, 1:-1] + hp[:, :-2]) ** 2).sum(-1) + 1e-18) * 50.0 ** 2
    p0 = VALID_FROM * (BLOCK // 2)                                                        # first scored 50 Hz point index (200)
    sv, sj, sa = hv[:, p0 - 1:], hj[:, p0 - 2:], ha[:, p0 - 2:]
    P = np.asarray(jax.vmap(F.fk_all)(qf)).astype(np.float64)                             # (E, steps, 6, 3)
    s0 = VALID_FROM * BLOCK
    P = P[:, s0:]
    m_cc = np.minimum((P[:, :, 1:5, 2] - F.FLOOR_M).min(-1), P[:, :, 5, 2] - F.FLOOR_M - F.DISC_M)
    plane = 0.0 if cfg_plane is None else cfg_plane
    m_tr = np.minimum(P[:, :, 1:5, 2].min(-1) - F.LINK_R - plane, P[:, :, 5, 2] - F.DISC_M - plane)
    bends = np.abs(np.asarray(qf)[:, s0:][:, :, F.BENDS]) >= LIM_DEG
    e, j = np.asarray(energy)[:, VALID_FROM:], np.asarray(jerk)[:, VALID_FROM:]
    frac = lambda a: float(np.mean(a))
    return {"hand_v": frac(sv >= HAND_V), "jolt": frac(sj >= JOLT), "acc": frac(sa >= ACC), "floor": frac(m_cc <= 0), "floor_trained": frac(m_tr <= 0), "lim": frac(bends),
            "lim_any_bend": frac(bends.any(-1)), "energy": frac(e >= thr["energy"]), "jerk": frac(j >= thr["jerk"]),
            "n": {"hand_samples_50hz": int(sv.size), "control_steps": int(m_cc.size), "bend_pairs": int(bends.size), "blocks": int(e.size)}}


def mean_g(r):
    """The trainer's own chunk-mean violations (s3_loss.limit_g) over the scored blocks of the same rollout, for reference."""
    sl = lambda k: np.asarray(r[k])[:, VALID_FROM:].mean()
    return {"hand_v": float(sl("hand_v") / HAND_V), "jolt": float(sl("jolt") / JOLT), "acc": float(sl("acc") / ACC), "floor": float(sl("floor") / 0.05), "lim": float(sl("lim"))}


# ---------------------------------------------------------------------------------------------------------------- hinge activity of one checkpoint
_ENV = {}


def env(run_dir):
    """Heavy objects built once per process: cerebellum, thresholds, compiled functions, the 16 fixed validation windows (the trainer's own path)."""
    if _ENV:
        return _ENV
    import k5_train as T
    import k5p2_train as P2
    import m3e_jax as M
    import s3_data as D
    import s3_loss as L
    cfg = P2.CFG
    C = M.load_cb()
    work = Path(os.environ.get("S3R_WORK", S3 / "run_report" / "work"))
    work.mkdir(parents=True, exist_ok=True)
    f = work / "corpus_sd.json"
    shutil.copyfile(Path(run_dir) / "corpus_sd.json", f)                                  # read of the run folder, written elsewhere
    floor_sd = np.array(json.loads(f.read_text()))
    splits = json.loads((K5 / "splits.json").read_text())
    dtoy = D.build_toy3(K5, S3, "val", T.val_windows(K5, splits)[:N_WIN], floor_sd)
    _, thr = D.load_inputs(S3)
    _ENV.update(cfg=cfg, C=C, fns=L.make_fns(C, cfg), dtoy=dtoy, thr={k: float(thr[k]) for k in ("energy", "jerk")}, work=work)
    return _ENV


def hinges_of(ckpt_path, run_dir):
    import jax
    import jax.numpy as jnp
    import m3f
    e = env(run_dir)
    d = pickle.loads(Path(ckpt_path).read_bytes())
    t = d["trainer"]
    P = jax.tree_util.tree_map(jnp.asarray, t["P"])
    n = len(e["dtoy"].y)
    t0 = time.time()
    r = m3f.rollout(e["fns"], e["cfg"], e["C"], P, e["dtoy"], np.arange(n), "argmax", jax.random.PRNGKey(4242), 8, 4242)
    secs_roll = time.time() - t0
    sh = share_stats(r["q"], r["energy"], r["jerk"], e["thr"], e["cfg"].get("plane"))
    return {"round": int(t["epoch"]), "shares": sh, "mean_g_same_windows": mean_g(r), "mu": dict(zip(G_NAMES, np.asarray(t["mu"]).tolist())),
            "muD": {"fast": float(t["muD"][0]), "slow": float(t["muD"][1])}, "Dest_in_checkpoint": {"fast": t["Dest"][0], "slow": t["Dest"][1]},
            "extra_val_last": (d["extra"]["val"][-1] if d["extra"]["val"] else None), "rollout_secs": secs_roll, "windows": n}


# ---------------------------------------------------------------------------------------------------------------- the round-400 clip
def slow_lanes_ready(work):
    f = Path(work) / "instant-crush.slow.npz"
    if not f.exists():
        subprocess.run(["taskset", "-c", "12-17", SLOW_PY, "-u", str(HERE / "s3_sidecar_slow.py"), "--out", str(f)], check=True, cwd=HERE)
    return f


def shoulder_cells(rows):
    """Shoulder sd (joint column 1, deg) and occupied 5 cm hand cells: s0_measure.hand / cells / cell_dist (CELL 0.05 m), repeated here because s0_measure needs sklearn (brain env only)."""
    import m3f_report as R
    h = R.fk_points(np.asarray(rows, float))[:, 5]
    c = np.floor(h / 0.05).astype(np.int64)
    return {"shoulder_sd_deg": float(np.std(rows[:, 1])), "occupied_5cm_cells": int(len(np.unique(c, axis=0))), "rows": int(len(rows))}


def mp4_720(src, dst):
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)]))
    vk = int(27 * 8388.6 / dur - 96)
    while True:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", "scale=1280:720", "-c:v", "libx264", "-preset", "slow", "-b:v", f"{vk}k", "-maxrate", f"{vk * 3 // 2}k", "-bufsize", f"{vk * 3}k",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(dst)], check=True)
        if Path(dst).stat().st_size < 30 * 1024 * 1024:
            return
        vk = vk * 9 // 10


def make_clip(best_path, out_dir, run_dir, start=60, seconds=60, name="instant-crush-r400-60s", label="Stage 3 policy", max_blocks=None):
    """Whole-song argmax rollout of best.pkl on Instant Crush, joint CSV, 60 s render, the four numbers (rules section 3)."""
    import jax
    import jax.numpy as jnp
    import arm_sim
    import k5_video_roll as VR
    import k5p2_eval as EV
    import hf_share
    e = env(run_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    b = pickle.loads(Path(best_path).read_bytes())
    P = jax.tree_util.tree_map(jnp.asarray, b["P"])
    z = np.load(VR.DANCED / "lanes" / "instant-crush.npz")
    inps, _ = EV.episode_inputs(z["y"], z["phi_end"], z["omega"])
    slow = np.clip(np.load(slow_lanes_ready(e["work"]))["slow"].astype(float), -8.0, 8.0)
    assert slow.shape == (inps["x"].shape[1], 13), (slow.shape, inps["x"].shape)
    prev = np.concatenate([np.zeros_like(slow[:1]), slow[:-1]], 0)[None]
    inps["x"] = jnp.concatenate([inps["x"], jnp.asarray(prev)], -1)
    if max_blocks:
        inps = {k: v[:, :max_blocks] for k, v in inps.items()}
    padded, nb = EV.pad_chunks(inps, VR.CB)
    t0 = time.time()
    r = EV.rollout_song(e["fns"], b.get("cfg") or e["cfg"], e["C"], P, padded)
    log(f"song rollout {nb} blocks in {time.time() - t0:.0f} s")
    rows = VR.csv_rows(r["q"][:nb], r["q0"])
    csv = out / "instant-crush.s3.csv"
    csv.write_text(arm_sim.csv_text(rows, hz=50, name=f"instant-crush.s3.r{b['round']}"))
    html = out / "instant-crush-s3.html"
    subprocess.run([str(PREVIEW), str(html), "../audio/instant-crush.m4a", "--joint-csv", str(csv)], check=True, capture_output=True)
    html.write_text(html.read_text().replace("K5 policy", label))
    raw = out / f"{name}.raw.mp4"
    env_ = {**os.environ}
    env_.pop("HYST_FAST", None)
    subprocess.run(["node", str(RECORD), str(html), str(AUDIO), str(raw), str(start), str(seconds)], check=True, env=env_, capture_output=True)
    final = out / f"{name}.mp4"
    mp4_720(raw, final)
    raw.unlink()
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(final)]))
    a, c = start * 50, (start + seconds) * 50
    p2 = hf_share.read_csv(PASS2_CSV)[0]
    res = {"policy_round": int(b["round"]), "clip": str(final), "size_bytes": final.stat().st_size, "duration_s": dur, "window_s": [start, start + seconds], "csv": str(csv), "song_blocks": nb,
           "stage3_r": shoulder_cells(rows[a:c]), "pass2": shoulder_cells(p2[a:c]), "pass2_csv": str(PASS2_CSV)}
    (out / "clip_numbers.json").write_text(json.dumps(res, indent=1))
    return res


# ---------------------------------------------------------------------------------------------------------------- the watcher
def validations(train_log):
    """-> {round: (line index, text, last 'epoch {...}' record before it or None)} of the validation lines in the log."""
    out, last = {}, None
    for i, line in enumerate(Path(train_log).read_text(errors="replace").splitlines()):
        if "] epoch {" in line:
            try:
                last = json.loads(line.split("epoch ", 1)[1])
            except ValueError:
                pass
        m = VAL_RE.search(line)
        if m:
            out[int(m.group(1))] = (i, line.strip(), last)
    return out


def run_unit_active():
    p = subprocess.run(["systemctl", "--user", "list-units", "hyst-wo26b-run-*", "--state=active", "--no-legend"], capture_output=True, text=True)
    return bool(p.stdout.strip())


def copy_with_epoch(run, rd, R, tries=3):
    """Copy ckpt.pkl (or ckpt.prev.pkl when the run already moved on) whose epoch is R to rd/ and load it. -> path or None (missed)."""
    for attempt in range(tries):
        got = []
        for nm in ("ckpt.pkl", "ckpt.prev.pkl"):
            src = Path(run) / nm
            if not src.exists():
                continue
            dst = rd / nm
            try:
                shutil.copyfile(src, dst)
                ep = pickle.loads(dst.read_bytes())["trainer"]["epoch"]
            except Exception as ex:  # noqa: BLE001
                log(f"round {R}: copy of {nm} failed to load ({ex!r})")
                continue
            got.append((nm, ep))
            if ep == R:
                return dst, got
        if any(ep > R for _, ep in got) and all(ep != R for _, ep in got):
            return None, got                                                             # the run has moved past R: missed, no reconstruction
        time.sleep(30)
    return None, got


def summary_line(R, h, val_text, rec):
    s = h["shares"]
    f = lambda k: f"{k} {100 * s[k]:.2f}%"
    mu = " ".join(f"{k} {v:.3f}" for k, v in h["mu"].items())
    return (f"round {R}: shares {' | '.join(f(k) for k in ('hand_v', 'jolt', 'acc', 'floor', 'lim', 'energy', 'jerk'))} (floor_trained {100 * s['floor_trained']:.2f}%, lim_any_bend {100 * s['lim_any_bend']:.2f}%); "
            f"mu {mu}; muD fast {h['muD']['fast']:.3f} slow {h['muD']['slow']:.3f}; D_fast {rec.get('D_fast') if rec else None} D_slow {rec.get('D_slow') if rec else None}; {val_text}")


def process(R, info, run, out, clip=True, force_clip_round=400):
    rd = Path(out) / str(R)
    rd.mkdir(parents=True, exist_ok=True)
    idx, text, rec = info
    wait_mains()
    ck, got = copy_with_epoch(run, rd, R)
    summ = Path(out) / "summary.txt"
    if ck is None:
        msg = f"round {R}: MISSED (checkpoint epochs seen {got}); {text}"
        log(msg)
        with open(summ, "a") as f:
            f.write(msg + "\n")
        (rd / "hinges.json").write_text(json.dumps({"round": R, "missed": True, "epochs_seen": got, "log_line": text}))
        return
    best = Path(run) / "best.pkl"
    if best.exists():
        shutil.copyfile(best, rd / "best.pkl")
    h = hinges_of(ck, run)
    h.update({"validation_round": R, "log_line": text, "epoch_record_in_log": rec, "D_fast": rec.get("D_fast") if rec else None, "D_slow": rec.get("D_slow") if rec else None,
              "record_epoch_is_R_minus_1": bool(rec and rec.get("epoch") == R - 1), "cores": "taskset -c 12-17", "copied_at": time.strftime("%Y-%m-%d %H:%M:%S")})
    (rd / "hinges.json").write_text(json.dumps(h, indent=1, default=float))
    with open(summ, "a") as f:
        f.write(summary_line(R, h, text, rec) + "\n")
    log(f"round {R}: hinges written")
    if clip and R == force_clip_round and (rd / "best.pkl").exists():
        # a fresh process: the clip code can be fixed after the watcher is armed, and a clip failure cannot take the watcher down
        wait_mains()
        cmd = ["taskset", "-c", "12-17", sys.executable, "-u", str(HERE / "s3_sidecar.py"), "clip", "--best", str(rd / "best.pkl"), "--out", str(rd), "--run", str(run)]
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE)
        (rd / "clip.log").write_text(p.stdout + "\n--- stderr ---\n" + p.stderr)
        with open(summ, "a") as f:
            f.write(f"round {R} clip: {'ok, see ' + str(rd / 'clip_numbers.json') if p.returncode == 0 else 'FAILED rc ' + str(p.returncode) + ', see ' + str(rd / 'clip.log')}\n")
        log(f"clip rc {p.returncode}")


def watch(run, out, poll=60, test=False, clip=True, clip_round=400):
    run, out = Path(run), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    tl = run / "train.log"
    armed = time.strftime("%Y-%m-%d %H:%M:%S")
    first = validations(tl)
    summ = out / "summary.txt"
    with open(summ, "a") as f:
        f.write(f"watcher armed {armed} on {run}; validation rounds already in the log: {sorted(first)}\n")
    for R, info in sorted(first.items()):
        if not (out / str(R) / "hinges.json").exists():
            if test:
                process(R, info, run, out, clip=False)
            else:
                msg = f"round {R}: MISSED (validation line already in the log when the watcher was armed at {armed}); {info[1]}"
                log(msg)
                (out / str(R)).mkdir(parents=True, exist_ok=True)
                (out / str(R) / "hinges.json").write_text(json.dumps({"round": R, "missed": True, "reason": "armed late", "log_line": info[1]}))
                with open(summ, "a") as f:
                    f.write(msg + "\n")
    if test:
        return
    quiet = time.time()
    while True:
        time.sleep(poll)
        new = {R: i for R, i in validations(tl).items() if not (out / str(R) / "hinges.json").exists()}
        for R, info in sorted(new.items()):
            quiet = time.time()
            try:
                process(R, info, run, out, clip=clip, force_clip_round=clip_round)
            except Exception as ex:  # noqa: BLE001  a failed round is recorded and skipped, the watcher goes on
                log(f"round {R}: FAILED {ex!r}")
                (out / str(R)).mkdir(parents=True, exist_ok=True)
                if not (out / str(R) / "hinges.json").exists():
                    (out / str(R) / "hinges.json").write_text(json.dumps({"round": R, "failed": repr(ex)}))
                with open(summ, "a") as f:
                    f.write(f"round {R}: FAILED {ex!r}\n")
        done = any(R >= 977 for R in validations(tl))
        if done:
            log("final validation seen: exit")
            return
        if not run_unit_active() and time.time() - quiet > 600:
            log("run unit no longer active: exit")
            return


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("watch")
    w.add_argument("--run", default=str(S3 / "run"))
    w.add_argument("--out", default=str(S3 / "run_report"))
    w.add_argument("--poll", type=int, default=60)
    w.add_argument("--test", action="store_true", help="process the validation lines already in the log, then exit (never the run)")
    w.add_argument("--no-clip", action="store_true")
    w.add_argument("--clip-round", type=int, default=400)
    h = sub.add_parser("hinges")
    h.add_argument("--ckpt", required=True)
    h.add_argument("--out", required=True)
    h.add_argument("--run", default=str(S3 / "run"))
    c = sub.add_parser("clip")
    c.add_argument("--best", required=True)
    c.add_argument("--out", required=True)
    c.add_argument("--run", default=str(S3 / "run"))
    c.add_argument("--start", type=int, default=60)
    c.add_argument("--seconds", type=int, default=60)
    c.add_argument("--max-blocks", type=int, help="test only")
    c.add_argument("--name", default="instant-crush-r400-60s")
    a = ap.parse_args()
    if a.cmd == "watch":
        watch(a.run, a.out, a.poll, a.test, not a.no_clip, a.clip_round)
    elif a.cmd == "hinges":
        Path(a.out).write_text(json.dumps(hinges_of(a.ckpt, a.run), indent=1, default=float))
    else:
        print(json.dumps(make_clip(a.best, a.out, a.run, a.start, a.seconds, a.name, max_blocks=a.max_blocks), indent=1))


if __name__ == "__main__":
    main()
