"""Scoring for B1 gates 1-3 (docs/BRAIN_SPEC.md 2.2). Tested on synthetic data only (test_scoring.py); the committed
pass rules are the constants and docstrings here. Nothing in this file has been run on a test set.

Metrics: mir_eval F-measure at +-70 ms, CMLt, AMLt (beats before 5 s are dropped from both sides, mir_eval.beat.trim_beats),
tempo error, median phase error. Intervals: 95 % percentile bootstrap over clips, BOOT_N resamples, seed BOOT_SEED.

Gate 1 (non-inferiority): per set (Ballroom, GTZAN) and per metric (F-measure, AMLt), the lower bound of the
    interval of the mean over clips of (B1 - PLL) >= GATE1_MARGIN (-0.05). All four must hold.
Gate 2 (holding through gaps), at the end of a 4 s gap, for both gap kinds:
    1. median over clips of B1's phase error <= 70 ms;
    2. upper bound of the interval of (median B1 error - median PLL error) <= +10 ms;
    3. median over clips of (mean readout amplitude over the last 0.5 s of the gap) / (mean over the 0.5 s before the gap) >= 0.5.
    Phase error at the end of a gap: for the annotated beats in the last 2 s of the gap, the median distance (ms) from each to
    the nearest beat of the system's own readout (hysteresis rule included). 2 s and 8 s gaps are computed the same way and
    reported. Pulse amplitude (3) is that of the oscillator which was the readout just before the gap, at the gap's end.
    How often the readout switched oscillator during the gap is reported per kind.
    The pulse-amplitude criterion tests a critical (alpha = 0) bank: without input its amplitude decays, so the result
    reflects the published alpha; with alpha > 0 the bank would sustain itself and criterion 3 would pass trivially.
Gate 3 (meter): per clip, R = mean amplitude of the oscillator nearest f_b / 3 over mean amplitude of the oscillator nearest f_b / 2
    (time means from 5 s on), f_b = the median frequency of B1's readout oscillator from 5 s on; AUC of R for triple against duple
    meter >= 0.75 and permutation p < 0.01 (PERM_N label permutations, seed PERM_SEED). Reported beside it: the same with f_b = the annotated
    tempo, and the share of clips where f_b is half or double the annotated tempo (within 8 %).
"""
import numpy as np
import mir_eval

BOOT_N = 2000
BOOT_SEED = 20261030
PERM_N = 10000
PERM_SEED = 20261031
F_TOL = 0.07
TRIM_S = 5.0
GATE1_MARGIN = -0.05
GATE2_PHASE_MS = 70.0
GATE2_VS_PLL_MS = 10.0
GATE2_AMP_RATIO = 0.5
GATE3_AUC = 0.75
GATE3_P = 0.01
END_WINDOW_S = 2.0
PHASE_CAP_MS = 1000.0
AMP_WINDOW_S = 0.5


def tempo_hz(beats):
    b = np.asarray(beats, dtype=float)
    return 1.0 / float(np.median(np.diff(b))) if len(b) >= 2 else float("nan")


def phase_error_ms(ref, est):
    """Median over reference beats of the distance (ms) to the nearest estimated beat; inf when there is nothing to compare."""
    ref, est = np.asarray(ref, float), np.asarray(est, float)
    if len(ref) == 0 or len(est) == 0:
        return float("inf")
    d = np.abs(ref[:, None] - est[None, :]).min(axis=1)
    return float(np.median(d) * 1000.0)


def beat_metrics(ref, est):
    """F-measure, CMLt, AMLt (mir_eval, trimmed), tempo error (relative, estimated vs annotated), median phase error (ms)."""
    ref_t = mir_eval.beat.trim_beats(np.asarray(ref, float))
    est_t = mir_eval.beat.trim_beats(np.asarray(est, float))
    if len(ref_t) < 2 or len(est_t) < 2:
        return {"f": 0.0, "cmlt": 0.0, "amlt": 0.0, "tempo_error": float("nan"), "phase_ms": float("inf")}
    f = mir_eval.beat.f_measure(ref_t, est_t, f_measure_threshold=F_TOL)
    _, cmlt, _, amlt = mir_eval.beat.continuity(ref_t, est_t)
    return {"f": float(f), "cmlt": float(cmlt), "amlt": float(amlt),
            "tempo_error": abs(tempo_hz(est_t) - tempo_hz(ref_t)) / tempo_hz(ref_t), "phase_ms": phase_error_ms(ref_t, est_t)}


def bootstrap(stat, n_clips, n=BOOT_N, seed=BOOT_SEED):
    """95 % percentile interval of stat(index array) over resamples of the clips."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n_clips, size=(n, n_clips))
    vals = np.array([stat(i) for i in idx])
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def gate1(b1, pll):
    """b1, pll: {set: {metric: per-clip array}} for the same clips. Returns the intervals and the verdict."""
    rows, ok = {}, True
    for name in b1:
        for metric in ("f", "amlt"):
            d = np.asarray(b1[name][metric], float) - np.asarray(pll[name][metric], float)
            lo, hi = bootstrap(lambda i, d=d: d[i].mean(), len(d))
            passed = lo >= GATE1_MARGIN
            ok &= passed
            rows[f"{name}.{metric}"] = {"b1": float(np.mean(b1[name][metric])), "pll": float(np.mean(pll[name][metric])),
                                        "diff": float(d.mean()), "lo": lo, "hi": hi, "pass": bool(passed)}
    return {"rows": rows, "pass": bool(ok)}


def gap_end_error_ms(ref, est, end_s, window=END_WINDOW_S):
    """Phase error at the end of a gap (see the module docstring); nan if no annotated beat is in the window."""
    ref = np.asarray(ref, float)
    r = ref[(ref >= end_s - window) & (ref <= end_s)]
    return phase_error_ms(r, est) if len(r) else float("nan")


def amplitude_ratio(bank_amp, k, start_s, end_s, rate=100.0, window=AMP_WINDOW_S):
    """Gate 2 criterion 3: the amplitude of oscillator k, the readout oscillator just before the gap (not the current readout),
    mean over the last `window` s of the gap, over its mean over the `window` s before the gap. bank_amp is (frames, oscillators)."""
    w = int(round(window * rate))
    a, b = int(round(start_s * rate)), int(round(end_s * rate))
    before = float(np.mean(bank_amp[max(0, a - w):a, k]))
    end = float(np.mean(bank_amp[max(0, b - w):b, k]))
    return end / before if before > 0 else float("nan")


def readout_switches(readout_index, start_s, end_s, rate=100.0):
    """How often the readout moved to another oscillator during the gap."""
    a, b = int(round(start_s * rate)), int(round(end_s * rate))
    seg = np.asarray(readout_index[a:b])
    return int(np.count_nonzero(np.diff(seg)))


def gate2(err_b1, err_pll, ratios):
    """Arrays over the clips of one gap length and kind. Returns the three quantities and the verdict (rules for a 4 s gap)."""
    e1, e2 = np.asarray(err_b1, float), np.asarray(err_pll, float)
    keep = ~np.isnan(e1) & ~np.isnan(e2)          # nan: no annotated beat in the window; inf (no estimate) is capped
    e1, e2, r = np.minimum(e1[keep], PHASE_CAP_MS), np.minimum(e2[keep], PHASE_CAP_MS), np.asarray(ratios, float)[keep]
    med1, med2 = float(np.median(e1)), float(np.median(e2))
    lo, hi = bootstrap(lambda i: np.median(e1[i]) - np.median(e2[i]), len(e1))
    med_ratio = float(np.nanmedian(r))
    checks = {"phase": med1 <= GATE2_PHASE_MS, "vs_pll": hi <= GATE2_VS_PLL_MS, "amplitude": med_ratio >= GATE2_AMP_RATIO}
    return {"clips": int(len(e1)), "median_b1_ms": med1, "median_pll_ms": med2, "diff_lo": lo, "diff_hi": hi,
            "median_amp_ratio": med_ratio, "checks": {k: bool(v) for k, v in checks.items()}, "pass": bool(all(checks.values()))}


def amp_at(freqs, amp, hz, from_s=TRIM_S, rate=100.0):
    """Time-mean amplitude (from `from_s` on) of the oscillator nearest `hz` (clamped to the bank)."""
    k = int(np.argmin(np.abs(np.log(freqs) - np.log(np.clip(hz, freqs[0], freqs[-1])))))
    return float(np.mean(amp[int(from_s * rate):, k]))


def meter_ratio(freqs, amp, f_beat):
    return amp_at(freqs, amp, f_beat / 3.0) / max(amp_at(freqs, amp, f_beat / 2.0), 1e-12)


def auc(scores, labels):
    """P(score of a random positive > score of a random negative), ties half (rank form)."""
    s, y = np.asarray(scores, float), np.asarray(labels, bool)
    from scipy.stats import rankdata
    ranks = rankdata(s)
    n1, n0 = int(y.sum()), int((~y).sum())
    return float((ranks[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def permutation_p(scores, labels, n=PERM_N, seed=PERM_SEED):
    """One-sided: share of label permutations with AUC at least the observed one, with the +1 correction."""
    rng = np.random.default_rng(seed)
    y = np.asarray(labels, bool)
    obs = auc(scores, y)
    hits = sum(auc(scores, rng.permutation(y)) >= obs for _ in range(n))
    return obs, (hits + 1) / (n + 1)


def gate3(ratios, triple):
    a, p = permutation_p(ratios, triple)
    return {"auc": a, "p": p, "pass": bool(a >= GATE3_AUC and p < GATE3_P), "clips": int(len(ratios)), "triple": int(np.sum(triple))}


def half_or_double_share(f_b, f_ann, tol=0.08):
    r = np.asarray(f_b, float) / np.asarray(f_ann, float)
    half = np.abs(r - 0.5) <= 0.5 * tol
    double = np.abs(r - 2.0) <= 2.0 * tol
    return {"half": float(half.mean()), "double": float(double.mean()), "either": float((half | double).mean())}
