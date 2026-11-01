"""B7 checks C1 to C5 (docs/BRAIN_SPEC.md 7.4), one script, from a checkpoint: `check_b7.py --ckpt best.pt --manifest M.json --stats S.npz`.

Written and committed before any result. Pass rules are the spec's. It reuses check_b3.py (bootstrap, baselines, the 4.4 and 4.5 constructions);
everything the spec leaves open is fixed here and in B7_NOTES.md:
  lanes       as check_b3: per layer NLL (nats per feature) of the prediction made 2h/10 bins earlier, stamped where its target window completes;
              total = the sum over layers. B7's recognition, novelty and the recall source time are read at the 10 Hz bins (frame 10k + 9, stamped
              0.1 (k + 1)); one read serves a 0.5 s block (core_b7.py), so these lanes are piecewise constant over 5 bins.
  variants    ablations switch a module off at evaluation time on the same weights (core_b7 `relay_on`, `retrieval_on`, `modulation`):
              "relay off"       = the relay input and the head skip are zero;
              "retrieval off"   = the retrieved value and the recognition are zeroed at the relay input; novelty is still computed (C2, C5);
              "hippocampus off" (C5) = the same zeroing as retrieval off;
              "modulation frozen" = dev = 0 (the arousal frozen at any constant: its running mean started at its first value equals it).
  C1          H = S F S against N = S' F S of 4.4 (same seeds, plan and crossfades as check_b3.habituation). (a) Mean recognition over the second S
              (the bins stamped inside it) per song; paired H - N over songs, 95 % bootstrap interval above 0. (b) The top-1 retrieval of a block
              "points into the first S" when the entry time t of the top-1 entry lies in [0, 16] s (the first S's span in H); the share is
              pooled over all blocks (their 10 Hz bins) inside the second S of all songs in H (a bin without an eligible entry counts as not
              pointing); needs >= 0.5. Pass if both hold. The median per-song share is reported.
  C2          check_b3.habituation rule on B7 (total surprisal; drop = N - H on the second S; interval above 0 and median drop / SD of the song's
              8 s window means >= 0.25), and with retrieval off the drop shrinks: the paired bootstrap interval of (drop with retrieval - drop
              without), per song, lies above 0. Pass if both hold. The surprisal SD is the song's full-song total of the full model.
  C3          4.5 applied to the novelty lane (1 - recognition) instead of surprisal, with the z of 4.5 (post 1 s minus pre 5 s over the SD of the
              1 s window means in the 30 s before), same cuts and seeds. Pass: z >= 3 on >= 80 % of cross-song cuts and the paired cross - within
              interval above 0. 4.5 on total surprisal is rerun and reported.
  C4          (a) held-out NLL (sum over the 4 layers of the per-feature mean NLL, per song) with the modulation frozen minus the full model's:
              the paired bootstrap interval above 0. (b) Per layer and song: the effective time constant of each 0.5 s block is the median over
              modes of -dt / ln|lam_eff| = median(dt / nu) / e; the arousal of a block is the arousal known at its start (the last frame of the
              previous block; 0 in the first block); top quartile = the n/4 blocks with the highest arousal, bottom quartile = the n/4 lowest
              (stable ranking); rel = (median tau in the top quartile - median in the bottom) / median in the bottom. A layer passes when the
              absolute median over songs of rel is >= 0.10 and the share of songs whose rel has the sign of that median is >= 0.70. (b) passes when all four layers pass with one common sign (the claim names one direction: "shorten" for
              negative, "lengthen" for positive). C4 passes when (a) and (b) do.
  C5          4.3 rerun as committed on B7 (same baselines, fitted as in round 2 on the training artists without the validation artists; ridge AR
              and persistence and B2 variances as in check_b3): (i) the paired bootstrap interval of (baseline NLL - B7 NLL) above 0 against all
              three baselines, (ii) B7's pooled MSE <= 0.95 x ridge AR's. Reported with the same gate for relay off, hippocampus off,
              modulation frozen.
  reported    PAC (check_b3.pac_pairs on the first --pac-songs held-out songs, no claim), DEAM/MERP arousal r (--precheck), per-layer MSE and NLL,
              every B3 claim measured again (4.4 and 4.5 on total surprisal are in C2 and C3).
All numbers go to results.json in --out. With --smoke the run is marked smoke and may not write into RESULTS_DIR.
"""
import argparse
import contextlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import b2  # noqa: E402
import check_b3 as cb  # noqa: E402
import core  # noqa: E402
import train  # noqa: E402
import train_b7  # noqa: E402
import val_split  # noqa: E402

RESULTS_DIR = Path("/secondary/hyst-data/brain/b7/results")
SCRATCH_DIR = Path("/secondary/hyst-data/brain/b7/scratch")
EVAL_CHUNK = cb.EVAL_CHUNK
BLOCK = 50
MSE_MARGIN = 0.05
C1_SHARE = 0.5
C4_REL, C4_SHARE = 0.10, 0.70
VARIANTS = {"full": {}, "relay_off": {"relay": False}, "hippocampus_off": {"retrieval": False}, "modulation_frozen": {"modulation": "frozen"}}


@contextlib.contextmanager
def variant(model, relay=True, retrieval=True, modulation="on"):
    old = (model.relay_on, model.retrieval_on, model.modulation)
    model.relay_on, model.retrieval_on, model.modulation = relay, retrieval, modulation
    try:
        yield
    finally:
        model.relay_on, model.retrieval_on, model.modulation = old


# ---- model runs -----------------------------------------------------------------------------------------------------------

def bins7(model, x, chunk=EVAL_CHUNK, signals=False):
    """Whole song, state carried. -> dict: mean[4], logvar[4] (nb, 44); recognition, novelty, source_t (nb,) at the 10 Hz bins; tau (4, nblocks)
    effective time constants; arousal (T,) per frame; x[4] (T, 128) layer outputs if `signals`."""
    nb = len(x) // b2.STRIDE
    state = model.init_state()
    acc = {k: [[] for _ in range(4)] for k in ("mean", "logvar", "tau", "x")}
    hip = {k: [] for k in ("recognition", "novelty", "source_t")}
    arousal = []
    with torch.no_grad():
        for a in range(0, len(x), chunk):
            out, state = model(torch.from_numpy(x[a:a + chunk])[None], state)
            j = np.arange(a, a + out[0]["mean"].shape[1])
            keep = torch.from_numpy((j % b2.STRIDE == b2.STRIDE - 1) & (j // b2.STRIDE < nb))
            for i, o in enumerate(out):
                acc["mean"][i].append(o["mean"][0][keep].numpy())
                acc["logvar"][i].append(o["logvar"][0][keep].numpy())
                acc["tau"][i].append(o["tau_eff"][0].numpy())
                if signals:
                    acc["x"][i].append(o["x"][0].numpy())
            for k in hip:
                hip[k].append(out[0]["hippo"][k][0][keep].numpy())
            arousal.append(out[0]["arousal"][0].numpy())
    res = {k: [np.concatenate(v) for v in acc[k]] for k in ("mean", "logvar", "tau")}
    res["tau"] = np.stack(res["tau"])
    res.update({k: np.concatenate(v) for k, v in hip.items()})
    res["arousal"] = np.concatenate(arousal)
    if signals:
        res["x"] = [np.concatenate(v) for v in acc["x"]]
    return res


def lanes7(model, x):
    """check_b3's lanes (total, L1..L4, sigma) of B7's heads plus recognition, novelty, source_t at the 10 Hz bins."""
    r = bins7(model, x)
    lanes = b2.surprisal_lanes(r["mean"], r["logvar"], x[:, :core.FEAT])[0]
    lanes["sigma"] = np.stack([np.exp(0.5 * v).mean(1) for v in r["logvar"]], 1)
    lanes.update({k: r[k] for k in ("recognition", "novelty", "source_t")})
    return lanes


# ---- C1 -------------------------------------------------------------------------------------------------------------------

class C1Collector:
    """Hook for check_b3.habituation: the second S's mean recognition in H and N, and in H the share of top-1 entries inside the first S."""

    def __init__(self):
        self.rec = {"H": {}, "N": {}}
        self.pointing = {}

    def __call__(self, sid, name, lanes, t0, t1):
        self.rec[name][sid] = cb.lane_mean(lanes["recognition"], t0, t1)
        if name == "H":
            k = np.arange(len(lanes["source_t"]))
            sel = (0.1 * (k + 1) > t0 + 1e-9) & (0.1 * (k + 1) <= t1 + 1e-9)
            s = lanes["source_t"][sel]
            self.pointing[sid] = (int(((s >= 0) & (s <= cb.HAB_PASSAGE)).sum()), int(sel.sum()))


def c1_stats(col, share_gate=C1_SHARE):
    ids = [s for s in col.rec["H"] if s in col.rec["N"]]
    diff = [col.rec["H"][s] - col.rec["N"][s] for s in ids]
    if not diff:
        return {"n_songs": 0, "pass": False}
    lo, hi, pt = cb.boot_ci(diff)
    hits, tot = sum(h for h, _ in col.pointing.values()), sum(n for _, n in col.pointing.values())
    share = hits / max(tot, 1)
    per_song = [h / max(n, 1) for h, n in col.pointing.values()]
    return {"n_songs": len(ids), "recognition_H_minus_N_mean": pt, "ci": [lo, hi], "above_0": bool(lo > 0),
            "mean_recognition_H": float(np.mean([col.rec["H"][s] for s in ids])), "mean_recognition_N": float(np.mean([col.rec["N"][s] for s in ids])),
            "pointing_share_pooled": share, "pointing_share_median_per_song": float(np.median(per_song)), "n_retrievals": tot,
            "pass": bool(lo > 0 and share >= share_gate)}


# ---- C2, C3 ---------------------------------------------------------------------------------------------------------------

def c2_stats(drops_on, sds, drops_off):
    """drops_*: per-song drops (same songs, same order). -> check_b3.hab_stats plus the paired (with - without retrieval) interval."""
    res = cb.hab_stats(drops_on, sds)
    lo, hi, pt = cb.boot_ci(np.asarray(drops_on) - np.asarray(drops_off))
    res["drop_without_retrieval_mean"] = float(np.mean(drops_off))
    res["with_minus_without"] = {"mean": pt, "ci": [lo, hi], "above_0": bool(lo > 0)}
    res["rule_4_4"] = res["pass"]
    res["pass"] = bool(res["rule_4_4"] and lo > 0)
    return res


def c3_stats(rows):
    """rows from check_b3.splice(extra=("novelty",)): the gate of 4.5 on the novelty z, and 4.5 on total surprisal."""
    nov = [{"cross": r["cross_novelty"], "within": r["within_novelty"]} for r in rows]
    return {"novelty": cb.splice_stats(nov), "total_surprisal_4_5_rerun": cb.splice_stats(rows)}


# ---- C4 -------------------------------------------------------------------------------------------------------------------

def tau_rel(tau, arousal, frac=0.25):
    """tau: (4, nblocks) effective time constants of a song; arousal: (T,) per frame. -> (4,) relative difference (top quartile - bottom) / bottom
    of the median tau, quartiles by the arousal known at the block start (the previous block's last frame; 0 in block 0)."""
    nblk = tau.shape[1]
    a0 = np.concatenate([[0.0], arousal[BLOCK - 1::BLOCK]])[:nblk]
    order = np.argsort(a0, kind="stable")
    q = max(1, int(nblk * frac))
    bot, top = order[:q], order[-q:]
    return np.array([(np.median(t[top]) - np.median(t[bot])) / np.median(t[bot]) for t in tau])


def c4b_stats(rels, min_rel=C4_REL, min_share=C4_SHARE):
    """rels: (songs, 4). Per layer: the median over songs, the share of songs with that median's sign, and the pass rule."""
    rels = np.asarray(rels)
    per = {}
    for i, name in enumerate(b2.LAYERS):
        med = float(np.median(rels[:, i]))
        share = float(np.mean(np.sign(rels[:, i]) == np.sign(med))) if med != 0 else 0.0
        per[name] = {"median_rel": med, "share_same_sign": share, "pass": bool(abs(med) >= min_rel and share >= min_share)}
    signs = {np.sign(v["median_rel"]) for v in per.values()}
    ok = all(v["pass"] for v in per.values()) and len(signs) == 1
    direction = None if not ok else ("shorten" if next(iter(signs)) < 0 else "lengthen")
    return {"layers": per, "pass": bool(ok), "direction": direction}


def c4a_stats(nll_full, nll_frozen):
    lo, hi, pt = cb.boot_ci(np.asarray(nll_frozen) - np.asarray(nll_full))
    return {"frozen_minus_full_mean": pt, "ci": [lo, hi], "pass": bool(lo > 0)}


# ---- C5 -------------------------------------------------------------------------------------------------------------------

def c5_gate(scores, name="b7", margin=MSE_MARGIN):
    """check_b3.gate_43 for model `name`, with the spec's wording for the MSE: against ridge AR."""
    res = cb.gate_43(scores, b3=name, margin=margin)
    ridge = res["mse"]["ar_ridge"]
    res["mse_ratio_to_ridge_ar"] = res["mse"][name] / ridge
    res["pass_vs_ridge_ar"] = bool(all(v["above_0"] for v in res["baselines"].values()) and res["mse"][name] <= (1 - margin) * ridge)
    res["pass"] = res["pass_vs_ridge_ar"]
    return res


# ---- the run --------------------------------------------------------------------------------------------------------------

def run_all(args, log=print):
    t0 = time.time()
    mean, std = train.load_stats(args.stats)
    raw = json.loads(Path(args.manifest).read_text())
    audio = {t["id"]: t["audio"] for t in raw}
    tracks = cb.load_manifest(args.manifest)
    tr = [t for t in tracks if t.split == "train"]
    if args.val_artists:
        tr = val_split.split_tracks(tr, val_split.load(args.val_artists))[0]
    tr = tr[:args.train_limit]
    ho = [t for t in tracks if t.split == "heldout"][:args.heldout_limit]
    load = lambda t: train.load_inputs(t, mean, std)
    audio_of = lambda sid: b2.decode(audio[sid])
    model, meta = train_b7.load_model7(args.ckpt)
    res = {"smoke": args.smoke, "checkpoint": str(args.ckpt), "val_artists": args.val_artists, "n_train_tracks_for_baselines": len(tr), "n_heldout_tracks": len(ho),
           "checkpoint_meta": {k: meta.get(k) for k in ("epoch", "wall_s", "params", "stopped_by_cap", "phase", "best_epoch", "cut", "stopped_early", "beta", "chunk", "batch", "grad_checkpoint")},
           "seeds": {"boot": cb.SEED_BOOT, "hab": cb.SEED_HAB, "splice": cb.SEED_SPLICE, "pac": cb.SEED_PAC}}
    log("fitting baselines")
    train_x, train_z = cb.Lazy(tr, load), cb.Lazy(tr, lambda t: load(t)[:, :core.FEAT])
    methods = {"persistence": cb.Persistence().fit(train_z), "ar_ridge": cb.ARRidge().fit(train_z)}
    res["ar_alpha"] = methods["ar_ridge"].alpha
    methods["b2"] = cb.B2Method.fit(meta["phase"], train_x, head_norm=meta.get("head_norm", True))
    del train_x

    log("scoring held-out songs")
    names = ["b7", *methods]
    scores = {v: {"nll": [], "mse": [], "n": []} for v in VARIANTS}
    base_scores = {m: {"nll": [], "mse": [], "n": []} for m in methods}
    full_total, held, rels, nll_song = {}, [], [], {"full": [], "modulation_frozen": []}
    for t in ho:
        x = load(t)
        z = x[:, :core.FEAT]
        for v, kw in VARIANTS.items():
            with variant(model, **kw):
                r = bins7(model, x)
            for key, val in zip(("nll", "mse", "n"), cb.song_scores(r["mean"], r["logvar"], z)):
                scores[v][key].append(val)
            if v == "full":
                full_total[t.id] = b2.surprisal_lanes(r["mean"], r["logvar"], z)[0]["total"]
                rels.append(tau_rel(r["tau"], r["arousal"]))
        for m, mm in methods.items():
            for key, val in zip(("nll", "mse", "n"), cb.song_scores(*mm.bins(x), z)):
                base_scores[m][key].append(val)
        held.append((t.id, len(x) / 100.0, x[:, core.FEAT:]))
    arr = lambda s: {k: np.array(v) for k, v in s.items()}
    scores, base_scores = {v: arr(s) for v, s in scores.items()}, {m: arr(s) for m, s in base_scores.items()}
    res["C5"] = {v: c5_gate({**base_scores, "b7": scores[v]}) for v in VARIANTS}
    res["C5"]["full"]["variants_reported"] = {v: {k: res["C5"][v][k] for k in ("pass", "mse_ratio_to_ridge_ar", "baselines", "mse")} for v in VARIANTS if v != "full"}
    res["C4"] = {"a": c4a_stats(scores["full"]["nll"].sum(1), scores["modulation_frozen"]["nll"].sum(1)), "b": c4b_stats(rels), "rel_per_song": np.asarray(rels).tolist()}
    res["C4"]["pass"] = bool(res["C4"]["a"]["pass"] and res["C4"]["b"]["pass"])

    stats = (mean, std)
    full_fn = lambda x: lanes7(model, x)

    def off_fn(x):
        with variant(model, retrieval=False):
            return lanes7(model, x)

    log("C1 and C2: habituation constructions")
    col = C1Collector()
    drops, sds, skipped = cb.habituation(held, full_fn, audio_of, stats, full_total, hook=col)
    drops_off, sds_off, skipped_off = cb.habituation(held, off_fn, audio_of, stats, full_total)
    res["C1"] = {**c1_stats(col), "skipped": skipped}
    res["C2"] = {**(c2_stats(drops, sds, drops_off) if drops and skipped == skipped_off else {"n_songs": 0, "pass": False}), "skipped": skipped,
                 "drops": drops, "drops_without_retrieval": drops_off}
    log("C3: splice on the novelty lane and on surprisal")
    rows, skipped = cb.splice(held, full_fn, audio_of, stats, extra=("novelty",))
    res["C3"] = {**c3_stats(rows), "skipped": skipped} if rows else {"n_songs": 0, "pass": False, "skipped": skipped}
    res["C3"]["pass"] = bool(rows and res["C3"]["novelty"]["pass"])

    log("phase-amplitude coupling (reported)")
    pairs = {}
    for t in ho[:args.pac_songs]:
        for k, v in cb.pac_pairs(bins7(model, load(t), signals=True)["x"], cb.SEED_PAC).items():
            pairs.setdefault(k, []).append(v)
    res["pac_reported"] = {k: {"median_mi": float(np.median([a for a, _, _ in v])), "median_surrogate_mi": float(np.median([c for _, _, c in v])),
                               "frac_songs_p_below_0.05": float(np.mean([p < 0.05 for _, p, _ in v])), "n_songs": len(v)} for k, v in pairs.items()}
    if args.precheck:
        import precheck_data
        res["precheck_arousal_reported"] = precheck_data.run(model, stats, args.core2b, cb.precheck)
    res["wall_s"] = time.time() - t0
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--stats", required=True)
    ap.add_argument("--out")
    ap.add_argument("--val-artists")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--train-limit", type=int)
    ap.add_argument("--heldout-limit", type=int)
    ap.add_argument("--pac-songs", type=int, default=40)
    ap.add_argument("--precheck", action="store_true")
    ap.add_argument("--core2b")
    ap.add_argument("--precheck-only", action="store_true", help="only the DEAM/MERP arousal r (reported); writes precheck.json")
    args = ap.parse_args(argv)
    out = Path(args.out) if args.out else (SCRATCH_DIR / "smoke" if args.smoke else RESULTS_DIR)
    if args.smoke and RESULTS_DIR in (out, *out.parents):
        raise SystemExit("smoke results may not go to the results folder")
    if args.precheck_only:
        import precheck_data
        mean, std = train.load_stats(args.stats)
        model, _ = train_b7.load_model7(args.ckpt)
        out.mkdir(parents=True, exist_ok=True)
        (out / "precheck.json").write_text(json.dumps(precheck_data.run(model, (mean, std), args.core2b, cb.precheck), indent=1, default=float))
        return
    res = run_all(args)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps({k: res[k].get("pass") for k in ("C1", "C2", "C3", "C4", "C5")}, default=str))


if __name__ == "__main__":
    main()
