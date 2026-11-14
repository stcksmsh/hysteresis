"""WO37 T0 library: mirror, split, weights, windows, posture/gesture, token pooling. Rules: docs/T0_RULES.md. Body env (numpy + scipy), pure functions, no data access."""
import sys
from pathlib import Path

import numpy as np
from scipy.signal import butter, filtfilt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import retarget as RT  # noqa: E402

FPS, WIN_S, TOK_S, PRE_S = 30, 20.0, 0.5, 1.5
WIN_TOK = int(WIN_S / TOK_S)
SEED, SHARES = 33001, (0.75, 0.10, 0.15)
ROT_JOINTS = (0, 3, 6, 9, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21)         # RT.JOINTS plus the left chain (collar 13, shoulder 16, elbow 18, wrist 20)
SWAP = {13: 14, 14: 13, 16: 17, 17: 16, 18: 19, 19: 18, 20: 21, 21: 20}   # SMPL left/right pairs among the loaded joints; the rest map to themselves
MIRROR_M = np.diag([-1.0, 1.0, 1.0])                                      # lateral axis = local x (retarget.XM is the right arm's bone axis)
PARENT_ALL = {**RT.PARENT, 13: 9, 16: 13, 18: 16, 20: 18}


def load_rot(path):
    """FineDance motion npy -> (dict joint -> (T,3,3) local rotations for ROT_JOINTS, root translation (T,3))"""
    a = np.load(path).astype(np.float64)
    r6 = a[:, 3:].reshape(len(a), 52, 6)
    return {j: RT.six_to_matrix(r6[:, j]) for j in ROT_JOINTS}, a[:, :3]


def mirror(rot, trans):
    """left/right mirror (rules 3): swap paired joints, R' = M R M, root lateral translation negated"""
    out = {j: MIRROR_M @ rot[SWAP.get(j, j)] @ MIRROR_M for j in rot}
    t = trans.copy()
    t[:, 0] = -t[:, 0]
    return out, t


def fk_synthetic(rot):
    """synthetic skeleton for the mirror test: world positions (T,3) of the right wrist (21) and the left wrist (20), pelvis at the origin"""
    off = {3: (0, .1, 0), 6: (0, .1, 0), 9: (0, .1, 0), 13: (.1, .1, 0), 14: (-.1, .1, 0), 16: (.1, 0, 0), 17: (-.1, 0, 0), 18: (.3, 0, 0), 19: (-.3, 0, 0), 20: (.25, 0, 0), 21: (-.25, 0, 0)}
    G, P = {0: rot[0]}, {0: np.zeros((len(rot[0]), 3))}
    for j in (3, 6, 9, 13, 14, 16, 17, 18, 19, 20, 21):
        p = PARENT_ALL[j]
        P[j] = P[p] + np.einsum("tij,j->ti", G[p], np.array(off[j], float))
        G[j] = G[p] @ rot[j]
    return P[21], P[20]


def angles_of(rot, variant):
    """stage-1 human angles of one variant ('V1' | 'V2'), un-referenced"""
    v1, v2 = RT.human_angles(rot)
    return v1 if variant == "V1" else v2


def n_windows(t30):
    """non-overlapping 20 s windows from the sequence start: window i spans frames 600 i .. 600 (i + 1) inclusive; the tail is dropped"""
    return max(0, (t30 - 1) // int(WIN_S * FPS))


def n_tokens(t30):
    return t30 // int(TOK_S * FPS)


def t100(t30):
    return int((t30 - 1) / FPS * 100 + 1e-9) + 1


def posture_gesture(target, hz=100.0, fc=0.5):
    """rules 4: posture = 2nd-order Butterworth filtfilt at fc Hz per whole sequence; gesture = target - posture"""
    b, a = butter(2, fc / (hz / 2))
    p = filtfilt(b, a, target, axis=0)
    return p, target - p


def hours_of_dancers(dancers):
    """dancers: list of (id, hours) of one group -> {id: weight} (7.59.8 weighting)"""
    w_song = max(h for _, h in dancers)
    tot = sum(h for _, h in dancers)
    return {i: (w_song / tot if tot > w_song else 1.0) for i, _ in dancers}


def make_groups(units):
    """units: list of dict(key, name, hash) -> list of groups (sorted lists of keys). Units sharing a stripped lower-case name or an audio hash are merged."""
    par = {u["key"]: u["key"] for u in units}

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    seen = {}
    for u in units:
        for tag in (("n", "".join(c for c in u["name"].lower() if c.isalnum())), ("h", u["hash"])):
            if not tag[1]:
                continue
            if tag in seen:
                par[find(u["key"])] = find(seen[tag])
            else:
                seen[tag] = u["key"]
    g = {}
    for u in units:
        g.setdefault(find(u["key"]), []).append(u["key"])
    return sorted(sorted(v) for v in g.values())


def split_groups(groups, seed=SEED):
    """seeded 75/10/15 over the groups (sorted by their first key): test = round(.15 n), validation = round(.10 n), rest train -> {first key: split}"""
    order = sorted(groups)
    n = len(order)
    n_te, n_va = round(SHARES[2] * n), round(SHARES[1] * n)
    perm = np.random.default_rng(seed).permutation(n)
    out = {}
    for rank, i in enumerate(perm):
        out[order[i][0]] = "test" if rank < n_te else ("validation" if rank < n_te + n_va else "train")
    return out


def pool_tokens(ear, h_abs, sur, aro, ee, y, n_tok):
    """rules 5. ear (T100, 44) standardised fast features at 100 Hz (frame t centred on t/100 s); h_abs (n10, 32) mode amplitudes at 10 Hz stamps; sur (n10, 4) per-layer surprisal (NaN allowed);
    aro, ee (n10,); y (nb, 8) 0.5 s block lane with cos, sin in columns 2, 3 (block i stamped (i + .5) * .5 s).
    -> (tokens (n_tok, 86) raw, mask (n_tok,) uint8); stamp 5k + j = frame 10 (5k + j) + 9"""
    f = 50
    tok = np.zeros((n_tok, 44 + 32 + 4 + 2 + 4), np.float32)
    mask = np.zeros(n_tok, np.uint8)
    n10 = len(aro)
    ty = (np.arange(len(y)) + 0.5) * 0.5
    for k in range(n_tok):
        a, b = k * f, (k + 1) * f
        tok[k, :44] = ear[a:min(b, len(ear))].mean(0) if a < len(ear) else 0.0
        s = slice(5 * k, min(5 * k + 5, n10))
        if s.start < n10:
            tok[k, 44:76] = h_abs[s].mean(0)
            ss = sur[s]
            ok = ~np.isnan(ss).all(1)
            if ok.any():
                tok[k, 76:80] = np.nanmean(ss[ok], 0)
            else:
                mask[k] = 1
            tok[k, 80], tok[k, 81] = aro[s].mean(), ee[s].mean()
        else:
            mask[k] = 1
        t0, tm = k * TOK_S, k * TOK_S + TOK_S / 2
        for c, col in enumerate((2, 3)):
            tok[k, 82 + c], tok[k, 84 + c] = np.interp(t0, ty, y[:, col]), np.interp(tm, ty, y[:, col])
    return tok, mask


TOKEN_COLS = ([f"ear{i}" for i in range(44)] + [f"mode_l{l + 1}g{g}" for l in range(4) for g in range(8)] + [f"surprisal_l{l + 1}" for l in range(4)]
              + ["arousal_b7", "ear_energy", "beat_cos_start", "beat_cos_mid", "beat_sin_start", "beat_sin_mid"])
NORM_FROM = 44                                                          # columns 0..43 are already standardised by bd.stats; clipped only


def fit_token_norm(tokens_masks):
    """train-split mean and sd per column over all train tokens (masked tokens excluded for the surprisal columns) -> dict"""
    X = np.concatenate([t for t, _ in tokens_masks])
    M = np.concatenate([m for _, m in tokens_masks]).astype(bool)
    mean, sd = np.zeros(X.shape[1]), np.ones(X.shape[1])
    for c in range(NORM_FROM, X.shape[1]):
        v = X[~M, c] if 76 <= c < 80 else X[:, c]
        mean[c], sd[c] = float(v.mean()), float(max(v.std(), 1e-8))
    return dict(columns=TOKEN_COLS, mean=mean.tolist(), sd=sd.tolist(), clip=3.0, n_tokens=int(len(X)), n_masked=int(M.sum()))


def standardise_tokens(tok, nm):
    return np.clip((tok - np.array(nm["mean"], np.float32)) / np.array(nm["sd"], np.float32), -3, 3).astype(np.float32)
