"""WO44 report tables (docs/JOIN_RULES.md sections 4-5) from /secondary/hyst-data/body/join/measures.json -> /secondary/hyst-data/body/join/summary.json + docs/JOIN_TABLES.md. Brain env."""
import json
from pathlib import Path

import numpy as np

OUT = Path("/secondary/hyst-data/body/join")
DOCS = Path(__file__).resolve().parents[2] / "docs"
COPIES = ("V1", "V1m", "V2", "V2m")
ROWS = [("H", "continuous human", None), ("HJ|blocks", "human re-joined, A1 blocks", "A1"), ("HJ|overlap", "human re-joined, B overlap", "B"),
        ("RT|raw", "retrieval, A0 raw (as E1)", "A0"), ("RT|ramp", "retrieval, C offset ramp", "C"), ("RT|blocks", "retrieval, A1 blocks", "A1"), ("RT|overlap", "retrieval, B overlap", "B"),
        ("RN|raw", "random chunks, A0 raw (as E1)", "A0"), ("RN|ramp", "random chunks, C offset ramp", "C"), ("RN|blocks", "random chunks, A1 blocks", "A1"), ("RN|overlap", "random chunks, B overlap", "B"),
        ("M|blocks", "model seed 41101, A1 blocks (as E1)", "A1"), ("M|overlap", "model seed 41101, B overlap", "B")]
SEED, NBOOT = 44001, 2000


def val(c, key, name, m):
    if name == "H":
        return float(np.mean([c[f"H|{k}"][m] for k in COPIES]))
    if name.startswith("HJ"):
        return float(np.mean([c[f"{name}|{k}"][m] for k in COPIES]))
    return float(c[name][m])


def boot(x, seed=SEED):
    rng = np.random.default_rng(seed)
    b = [x[rng.integers(len(x), size=len(x))].mean() for _ in range(NBOOT)]
    return float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))


def main():
    res = json.loads((OUT / "measures.json").read_text())
    songs = sorted(res)
    test = [k for k in songs if res[k]["split"] == "test"]
    summ = dict(n_songs=len(songs), n_test=len(test), rows={})
    iv = {}
    for label, ks in (("all", songs), ("test", test)):
        h = np.array([val(res[k]["cond"], k, "H", "lamp_p_gt3") for k in ks])
        iv[label] = [float(np.percentile(h, 10)), float(np.percentile(h, 90)), float(h.mean())]
    summ["human_interval_lamp_p_gt3_P10_P90_mean"] = iv
    L = ["| material / method | n | lamp p_gt3 mean | ratio to H, mean [95 % boot] | ratio median | ratio of means (lamp / joint-mean, E1 statistic) | in human interval | joint-mean p_gt3 ratio | hand jerk ratio | frozen share | cmd-vs-real RMS (deg) | build s per min |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, title, meth in ROWS:
        ks = test if name.startswith("M|") else songs
        if any(name not in res[k]["cond"] and not name.startswith(("H|", "HJ", "H")) for k in ks):
            continue
        g = lambda m: np.array([val(res[k]["cond"], k, name, m) for k in ks])
        h = lambda m: np.array([val(res[k]["cond"], k, "H", m) for k in ks])
        p, ph = g("lamp_p_gt3"), h("lamp_p_gt3")
        r = p / ph
        lo, hi = boot(r)
        i0, i1, _ = iv["test" if name.startswith("M|") else "all"]
        inside = bool(i0 <= p.mean() <= i1)
        jr = g("joint_mean_p_gt3") / h("joint_mean_p_gt3")
        jk = g("hand_jerk") / h("hand_jerk")
        bs = [res[k]["build_s"].get(name, None) for k in ks]
        bs = [b for b in bs if b is not None]
        summ["rows"][name] = dict(title=title, n=len(ks), lamp_mean=float(p.mean()), ratio_mean=float(r.mean()), ratio_ci=[lo, hi], ratio_median=float(np.median(r)), inside_interval=inside,
                                  joint_ratio_mean=float(jr.mean()), jerk_ratio_mean=float(jk.mean()), frozen=float(g("frozen_share").mean()), cmd_real=float(g("cmd_vs_real_rms").mean()),
                                  build_s_per_min=float(np.median(bs)) if bs else None, per_song_ratio=dict(zip(ks, map(float, r))))
        L.append(f"| {title} | {len(ks)} | {p.mean():.4f} | {r.mean():.2f} [{lo:.2f}, {hi:.2f}] | {np.median(r):.2f} | {p.mean() / ph.mean():.2f} / {g('joint_mean_p_gt3').mean() / h('joint_mean_p_gt3').mean():.2f} | {'yes' if inside else 'no'} | {jr.mean():.2f} | {jk.mean():.2f} | {g('frozen_share').mean():.3f} | {g('cmd_vs_real_rms').mean():.2f} | "
                 + (f"{np.median(bs):.2f}" if bs else "-") + " |")
    (OUT / "summary.json").write_text(json.dumps(summ, indent=1))
    t = [f"Human interval (lamp p_gt3, P10-P90 / mean), 37 songs: {iv['all'][0]:.4f}-{iv['all'][1]:.4f} / {iv['all'][2]:.4f}; 17 test songs: {iv['test'][0]:.4f}-{iv['test'][1]:.4f} / {iv['test'][2]:.4f}.", ""] + L
    (DOCS / "JOIN_TABLES.md").write_text("\n".join(t) + "\n")
    print("\n".join(t))


if __name__ == "__main__":
    main()
