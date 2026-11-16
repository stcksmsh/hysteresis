"""WO44 chunk-joining methods (docs/JOIN_RULES.md sections 2-3). Pure numpy except decode_gesture (torch, frozen t1a2/runB decoder). Brain env."""
import numpy as np

CH, WIN = 50, 40                      # rows per token, tokens per decoder window
HOP = 20                              # overlap decoding: window start every 20 tokens
RAMP = 50                             # method C: rows over which a join jump is removed


def _dec_window(vq, tok, voc, a, sd):
    import torch
    c1, c2 = torch.as_tensor(np.asarray(tok["c1"])[a:a + WIN]).long(), torch.as_tensor(np.asarray(tok["c2"])[a:a + WIN]).long()
    zq = vq.vq.vq1.cb[c1] + vq.vq.vq2.cb[c2]
    a_n = torch.as_tensor(voc["vig"][np.asarray(tok["v"])[a:a + WIN]], dtype=torch.float32)
    with torch.no_grad():
        return vq.dec(zq[None], a_n[None])[0].numpy() * sd                 # (2000, 5) degrees


def decode_gesture(tok, voc, vq, sd, method):
    """tokens (c1, c2, v arrays of length n) -> gesture (n * 50, 5) degrees. 'blocks' = E1 (independent 40-token blocks, step 40), 'overlap' = 40-token windows every 20 tokens, Hann-weighted and normalised"""
    n = len(tok["c1"])
    if method == "blocks":
        return np.concatenate([_dec_window(vq, tok, voc, a, sd) for a in range(0, n, WIN)])
    starts = list(range(0, n - WIN + 1, HOP))
    if starts[-1] + WIN < n:
        starts.append(n - WIN)
    r = np.arange(WIN * CH)
    w = np.sin(np.pi * (r + 0.5) / (WIN * CH)) ** 2
    num, den = np.zeros((n * CH, 5)), np.zeros((n * CH, 1))
    for s in starts:
        ww = w.copy()
        if s == starts[0]:
            ww[:WIN * CH // 2] = 1.0                                          # no earlier window: keep the first half whole
        if s == starts[-1]:
            ww[WIN * CH // 2:] = 1.0
        g = _dec_window(vq, tok, voc, s, sd)
        num[s * CH:(s + WIN) * CH] += g * ww[:, None]
        den[s * CH:(s + WIN) * CH] += ww[:, None]
    return num / den


def build_rows(tok, post0, voc, vq, sd, method):
    """as t1b_t2.decode_rows (posture pchip + gesture), the gesture by `method` -> (n * 50 + 1, 5) float32"""
    from scipy.interpolate import PchipInterpolator
    n = len(tok["c1"])
    g = decode_gesture(tok, voc, vq, sd, method)
    p = np.asarray(tok["p"]).reshape(n, -1)
    d = sum(voc["post"][i][p[:, i]] for i in range(p.shape[1]))
    knots = post0 + np.vstack([np.zeros((1, 5)), np.cumsum(d, 0)])
    post = PchipInterpolator(np.arange(n + 1) * CH, knots, axis=0)(np.arange(n * CH + 1))
    rows = post.copy()
    rows[:-1] += g
    rows[-1] += g[-1]
    return rows.astype(np.float32)


def concat_raw(chunks):
    """chunks (n, 51, 5): raw chunks (row 50 = continuation) -> (n * 50 + 1, 5), method A0"""
    rows = chunks[:, :CH].reshape(-1, 5)
    return np.vstack([rows, rows[-1:]]).astype(np.float32)


def concat_ramp(chunks, ramp=RAMP):
    """method C: raw concatenation with each join's jump d = chunks[i, 0] - chunks[i-1, 50] removed over `ramp` rows (cosine, exactly zero from row `ramp`)"""
    c = np.asarray(chunks, np.float64)[:, :CH].copy()
    r = np.arange(min(ramp, CH))
    s = 0.5 * (1 + np.cos(np.pi * r / ramp))
    for i in range(1, len(c)):
        d = chunks[i, 0] - chunks[i - 1, CH]
        c[i, :len(r)] -= d[None] * s[:, None]
    rows = c.reshape(-1, 5)
    return np.vstack([rows, rows[-1:]]).astype(np.float32)
