"""K5 data (work order 8, docs/BRAIN_SPEC.md 7.19 A3): splits, B7 epoch-6 lanes, 60 s windows. Brain env (/secondary/hyst-env/brain). Nothing is normalised in the stored files.

    k5_data.py splits  [--out DIR]     splits.json: K5 train = training-side artists minus the validation artists (val_artists.json); check = the held-out songs
    k5_data.py windows [--out DIR]     windows.json (needs only the feature files' lengths)
    k5_data.py lanes   [--out DIR]     lanes/<split>/<id>.npz + lanes_manifest.json, check first, then train, then val; resume-safe (existing files are kept)

Lane definitions (the toy's interface, m3d_toy.py / tm3c.brain_state; one song, T frames at 100 Hz, B7 epoch 6 run over the whole song in 6,000-frame chunks with the state carried):
  y (nb, 8)    nb = T // 50 blocks of 0.5 s, columns Y_NAMES: arousal (one-pole of the per-frame total surprisal, rise 1 s / fall 8 s, linear dt/tau as the toy, from 0, value at the
               block's last frame), surprisal (mean total surprisal over the block), l3_cos, l3_sin (mean cos / sin of the phase of the L3 mode with the largest mean |h| in the block),
               logpow_L1..L4 (log of the block-mean over frames of the mean over the layer's modes of |h|^2, floor 1e-8)
  phi_end, omega (nb,)   the L3 mode's phase at the block end (rad), its rate (rad/s, unwrapped within the block, clamped to +-8 pi): the toy's phi / omega, the phase coupling input
  s10 (nb10, 5)  nb10 = T // 10, stamped at frame 10 k + 9: surprisal L1..L4, total (nats; NaN before a layer's first value, total = sum of the layers that have one)
  arousal_b7 (nb10,), power10 (nb10, 4)  B7's own arousal signal (L1 + L2 surprisal) and the raw band power (mean |h|^2), at the same stamps
total surprisal per frame = sum over the layers of braindump.surprisal (NaN before 2h - 1 frames counts as 0, as in the mindState lanes). Partial last block dropped.
The block/lane at index b describes frames [50 b, 50 b + 50): the arm's loop must read block b - 1 while moving in block b (the toy's `prev`).
"""
import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "brain"))
CORPUS = Path("/secondary/hyst-data/brain/corpus")
OUT = Path("/secondary/hyst-data/body/k5")
VAL_JSON = HERE.parent / "brain" / "val_artists.json"
BLOCK, WIN_BLOCKS, STRIDE_BLOCKS = 50, 120, 60                  # 0.5 s; 60 s; training-window stride 30 s (50 % overlap)
FRACS = (0.25, 0.5, 0.75)
Y_NAMES = ["arousal", "surprisal", "l3_cos", "l3_sin", "logpow_L1", "logpow_L2", "logpow_L3", "logpow_L4"]
CHUNK = 6000


# ---------------------------------------------------------------------------------------------------------------- splits
def read_rows(path=CORPUS / "final_corpus.csv"):
    return [{"id": f"{int(r['id']):06d}", "split": r["split"], "artist": int(r["artist_id"]), "hours": float(r["hours"])} for r in csv.DictReader(open(path, newline=""))]


def make_splits(rows, val_artists):
    va = set(val_artists)
    sel = lambda f: [r for r in rows if f(r)]
    parts = {"train": sel(lambda r: r["split"] == "train" and r["artist"] not in va), "val": sel(lambda r: r["split"] == "train" and r["artist"] in va),
             "check": sel(lambda r: r["split"] == "heldout")}
    art = {k: {r["artist"] for r in v} for k, v in parts.items()}
    for a, b in (("train", "val"), ("train", "check"), ("val", "check")):
        assert not (art[a] & art[b]), f"artist overlap {a}/{b}"
    assert len({r["id"] for r in rows}) == len(rows) and sum(len(v) for v in parts.values()) == len(rows)
    assert va <= {r["artist"] for r in rows if r["split"] == "train"}, "validation artist outside the training side"
    return {k: {"n_songs": len(v), "n_artists": len(art[k]), "hours": round(sum(r["hours"] for r in v), 4), "ids": [r["id"] for r in v],
                "artists": sorted(art[k])} for k, v in parts.items()}


def cmd_splits(out):
    s = make_splits(read_rows(), json.loads(VAL_JSON.read_text())["artists"])
    s["note"] = "train = training-side artists minus validation artists (val_artists.json); val = those validation artists (tuning only); check = held-out songs. Hours from final_corpus.csv."
    (out / "splits.json").write_text(json.dumps(s))
    print({k: {a: v[a] for a in ("n_songs", "n_artists", "hours")} for k, v in s.items() if isinstance(v, dict)})
    return s


# ---------------------------------------------------------------------------------------------------------------- windows
def n_frames(sid):
    return int(np.load(CORPUS / "features" / f"{sid}.npy", mmap_mode="r").shape[0])


def train_windows(nb, stride=STRIDE_BLOCKS):
    return list(range(0, nb - WIN_BLOCKS + 1, stride))


def check_windows(nb):
    """-> [(frac, start_block, clamped)]; start = floor(frac * nb), moved back to nb - 120 when the window would run past the end."""
    return [(f, min(int(f * nb), nb - WIN_BLOCKS), int(f * nb) > nb - WIN_BLOCKS) for f in FRACS]


def cmd_windows(out):
    sp = json.loads((out / "splits.json").read_text())
    tw, cw, short, clamp = [], [], [], 0
    for sid in sp["train"]["ids"]:
        nb = n_frames(sid) // BLOCK
        tw += [[sid, b] for b in train_windows(nb)]
    for sid in sp["check"]["ids"]:
        nb = n_frames(sid) // BLOCK
        if nb < WIN_BLOCKS:
            short.append(sid)
            continue
        for f, b, c in check_windows(nb):
            cw.append([sid, f, b, c])
            clamp += c
    w = {"window_blocks": WIN_BLOCKS, "block_s": 0.5, "train_stride_blocks": STRIDE_BLOCKS, "train": tw, "check": cw, "check_songs_shorter_than_60s": short,
         "rule": "train: every start 0, 60, 120, ... blocks with start + 120 <= nb (stride 30 s). check: start = floor(frac * nb) for frac 0.25 / 0.5 / 0.75, moved back to nb - 120 "
                 "(flag clamped = true) when it would run past the end; a song with nb < 120 is listed and has no window."}
    (out / "windows.json").write_text(json.dumps(w))
    print(len(tw), "train windows,", len(cw), "check windows,", clamp, "clamped,", len(short), "short songs")


# ---------------------------------------------------------------------------------------------------------------- lanes
def one_pole_frames(s, tau_up=1.0, tau_down=8.0, dt=0.01):
    a, out = 0.0, np.empty(len(s), np.float64)
    for i, v in enumerate(s):
        a += (v - a) * (dt / (tau_up if v > a else tau_down))
        out[i] = a
    return out


def song_lanes(model, x):
    """x (T, 46) core input -> the lane dict of the module docstring."""
    import torch
    import braindump as bd
    import core
    T = len(x)
    nl = len(core.BANDS)
    err, lv, pw, ar = [[] for _ in range(nl)], [[] for _ in range(nl)], [[] for _ in range(nl)], []
    ang, om = [], []
    st = model.init_state(1)
    with torch.no_grad():
        for a in range(0, T, CHUNK):
            out, st = model(torch.from_numpy(x[a:a + CHUNK])[None], st)
            for i, o in enumerate(out):
                err[i].append(o["err"][0].numpy()), lv[i].append(o["logvar"][0].numpy())
                pw[i].append((o["h"][0].real ** 2 + o["h"][0].imag ** 2).mean(-1).numpy())
            ar.append(out[0]["arousal"][0].numpy())
            h3, nbc = out[2]["h"][0], len(out[2]["h"][0]) // BLOCK
            if nbc:
                hb = h3[:nbc * BLOCK].reshape(nbc, BLOCK, -1)
                m = hb.abs().mean(1).argmax(-1)
                hm = hb[torch.arange(nbc), :, m]
                ang.append(torch.angle(hm).numpy())
    cat = lambda v: np.concatenate(v, 0)
    err, lv, pw = [cat(v) for v in err], [cat(v) for v in lv], np.stack([cat(v) for v in pw], 1)
    sur = np.stack([bd.surprisal(err[i], lv[i], h) for i, h in enumerate(core.HORIZONS)], 1)
    total = np.nansum(sur, 1)
    ang = cat(ang)
    nb, nb10 = T // BLOCK, T // 10
    unw = np.unwrap(ang, axis=1)
    omega = np.clip((unw[:, -1] - unw[:, 0]) / ((BLOCK - 1) * 0.01), -8 * math.pi, 8 * math.pi)
    a_end = one_pole_frames(total)[BLOCK - 1::BLOCK][:nb]
    y = np.concatenate([a_end[:, None], total[:nb * BLOCK].reshape(nb, BLOCK).mean(1)[:, None], np.cos(ang).mean(1)[:, None], np.sin(ang).mean(1)[:, None],
                        np.log(np.maximum(pw[:nb * BLOCK].reshape(nb, BLOCK, nl).mean(1), 1e-8))], 1)
    s10 = np.concatenate([sur[9:nb10 * 10:10], total[9:nb10 * 10:10, None]], 1)
    f = lambda a: np.asarray(a, np.float32)
    return {"y": f(y), "phi_end": f(ang[:, -1]), "omega": f(omega), "s10": f(s10), "arousal_b7": f(cat(ar)[9:nb10 * 10:10]),
            "power10": f(pw[:nb10 * 10].reshape(nb10, 10, nl).mean(1))}


def cmd_lanes(out, threads):
    import torch
    import b2
    import core
    import train
    import braindump as bd
    import train_b7
    torch.set_num_threads(threads)
    sp = json.loads((out / "splits.json").read_text())
    model, meta = train_b7.load_model7(bd.CKPT)
    mean, std = bd.stats()
    man = {"checkpoint": str(bd.CKPT), "checkpoint_epoch": meta.get("epoch"), "y_names": Y_NAMES, "songs": {}}
    t0, done_s = time.time(), 0.0
    for split in ("check", "train", "val"):
        d = out / "lanes" / split
        d.mkdir(parents=True, exist_ok=True)
        for sid in sp[split]["ids"]:
            p = d / f"{sid}.npz"
            if not p.exists():
                feats = np.load(CORPUS / "features" / f"{sid}.npy").astype(np.float32)
                x = b2.build_inputs(feats, json.loads((CORPUS / "grids" / f"{sid}.json").read_text())["beats"], mean, std)
                t1 = time.time()
                z = song_lanes(model, x)
                tmp = d / f"{sid}.tmp.npz"
                np.savez_compressed(tmp, frames=len(x), **z)
                tmp.replace(p)
                done_s += len(x) / 100.0
                print(f"{split} {sid} {len(x) / 100:.0f}s lanes {time.time() - t1:.1f}s (elapsed {time.time() - t0:.0f}s, {done_s / 3600:.2f} audio h)", flush=True)
    for split in ("check", "train", "val"):
        for sid in sp[split]["ids"]:
            z = np.load(out / "lanes" / split / f"{sid}.npz")
            man["songs"][sid] = {"split": split, "frames": int(z["frames"]), "blocks": int(z["y"].shape[0]), "bytes": (out / "lanes" / split / f"{sid}.npz").stat().st_size}
    man["seconds_this_run"], man["audio_hours_this_run"] = time.time() - t0, done_s / 3600
    (out / "lanes_manifest.json").write_text(json.dumps(man))
    print("manifest", len(man["songs"]), "songs")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=("splits", "windows", "lanes"))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--threads", type=int, default=6)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    {"splits": lambda: cmd_splits(out), "windows": lambda: cmd_windows(out), "lanes": lambda: cmd_lanes(out, a.threads)}[a.what]()


if __name__ == "__main__":
    main()
