"""The decoder of stage 3 (docs/EMOTION.md; docs/NEXT_DECODER_THEN_BRAIN.md, D2).

map     mood lanes (0..1; energy, power, rest...) -> 15-dim body vector in 0..1:  sigmoid(W lanes + b).
        Linear plus sigmoid is Lipschitz, so the body changes no faster than the (8 s smoothed) lanes do;
        that is the smoothness over time. Feasibility is the stretch ladder of body.rs, applied when a body
        is rendered (a body still infeasible after the ladder is a failed segment).
fit     W and b maximise the Pearson correlation between the distances of segment pairs in mood space and
        their distances in the surrogate's descriptor space (representational similarity), with a small
        penalty on W. The surrogate is a small network, body vector -> 37 descriptors, learned on rendered
        bodies; the check scores real renders, never the surrogate.
anchors the entries (body energy, size, time) <- mood.energy and (body weight) <- mood.power are constrained
        to be non-negative (energy up -> energy, size, sudden; power up -> strong weight). Height is not
        anchored, nothing else is constrained.
library the baseline: k-means clusters of mood matched to the body study's 8 regions by the representational
        similarity of the cluster centres and the regions' descriptors (no hand meaning), a segment taking
        the body of its cluster's region.
Training data only is ever passed in here.
"""
from __future__ import annotations

import itertools
import json
import pathlib

import numpy as np
import torch
from sklearn.cluster import KMeans

import common
import rsa

SEED_SURROGATE = 20261031
SEED_MAP = 20261032
SEED_KMEANS = 20261033
K_GRID = (2, 4, 8, 16)
INNER_FOLDS = 3
STEPS = 600
BATCH = 512
LEARNING_RATE = 0.03
WEIGHT_PENALTY = 1e-3
RSA_SEGMENTS = 1500          # segments per fold-score of the surrogate representational similarity
DIMS = ("curl_extension", "height", "arch", "time", "weight", "flow", "space", "succession_direction",
        "succession_delay", "initiation", "breath_depth", "breath_rate", "size", "energy", "rhythm")
ENERGY_LANE, POWER_LANE = 0, 1
ANCHORS = {ENERGY_LANE: ("energy", "size", "time"), POWER_LANE: ("weight",)}
STUDY = pathlib.Path("/secondary/hyst-data/bodystudy/r6")


# ------------------------------------------------------------------ surrogate

class Surrogate:
    """Body vector (15) -> standardised 37 descriptors."""

    def __init__(self, hidden=256, seed=SEED_SURROGATE):
        torch.manual_seed(seed)
        self.net = torch.nn.Sequential(torch.nn.Linear(15, hidden), torch.nn.SiLU(), torch.nn.Linear(hidden, hidden),
                                       torch.nn.SiLU(), torch.nn.Linear(hidden, 37))
        self.seed = seed
        self.mean = self.std = None

    def fit(self, bodies, desc, epochs=300, lr=2e-3, batch=512):
        self.mean, self.std = desc.mean(axis=0), desc.std(axis=0)
        self.std[self.std < 1e-8] = 1.0
        x = torch.tensor(bodies, dtype=torch.float32)
        y = torch.tensor((desc - self.mean) / self.std, dtype=torch.float32)
        gen = torch.Generator().manual_seed(self.seed)
        opt = torch.optim.Adam(self.net.parameters(), lr=lr)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs)
        for _ in range(epochs):
            order = torch.randperm(len(x), generator=gen)
            for i in range(0, len(x), batch):
                idx = order[i:i + batch]
                opt.zero_grad()
                torch.nn.functional.mse_loss(self.net(x[idx]), y[idx]).backward()
                opt.step()
            sched.step()
        for p in self.net.parameters():
            p.requires_grad_(False)
        return self

    def __call__(self, bodies):
        return self.net(bodies)

    def save(self, path):
        torch.save({"state": self.net.state_dict(), "mean": self.mean, "std": self.std, "seed": self.seed,
                    "hidden": self.net[0].out_features}, path)

    @classmethod
    def load(cls, path):
        blob = torch.load(path, weights_only=False)
        s = cls(blob["hidden"], blob["seed"])
        s.net.load_state_dict(blob["state"])
        for p in s.net.parameters():
            p.requires_grad_(False)
        s.mean, s.std = blob["mean"], blob["std"]
        return s

    def r2(self, bodies, desc):
        """Held-out R^2 per descriptor."""
        with torch.no_grad():
            pred = self.net(torch.tensor(bodies, dtype=torch.float32)).numpy()
        y = (desc - self.mean) / self.std
        return 1.0 - ((y - pred) ** 2).sum(axis=0) / ((y - y.mean(axis=0)) ** 2).sum(axis=0)


# ------------------------------------------------------------------------ map

class Map:
    """sigmoid(W lanes + b) with sign constraints on the anchor entries (softplus keeps them >= 0)."""

    def __init__(self, width, power_anchor=True, seed=SEED_MAP):
        g = torch.Generator().manual_seed(seed)
        self.raw = (torch.randn(15, width, generator=g) / np.sqrt(width)).requires_grad_(True)
        self.b = torch.zeros(15, requires_grad=True)
        self.positive = torch.zeros(15, width, dtype=torch.bool)
        for lane, names in ANCHORS.items():
            if lane == POWER_LANE and not power_anchor:
                continue
            for name in names:
                self.positive[DIMS.index(name), lane] = True
        self.mean = self.std = None      # standardisation of the lanes for distances

    @property
    def weights(self):
        return torch.where(self.positive, torch.nn.functional.softplus(self.raw), self.raw)

    def forward(self, lanes):
        return torch.sigmoid(lanes @ self.weights.T + self.b)

    def bodies(self, lanes):
        with torch.no_grad():
            return self.forward(torch.tensor(lanes, dtype=torch.float32)).numpy().astype(np.float64)

    def standardised(self, lanes):
        return (lanes - self.mean) / self.std


def _pearson(a, b):
    a, b = a - a.mean(), b - b.mean()
    return (a * b).sum() / (a.norm() * b.norm() + 1e-12)


def fit_map(lanes, surrogate, power_anchor=True, steps=STEPS, batch=BATCH, lr=LEARNING_RATE, penalty=WEIGHT_PENALTY,
            seed=SEED_MAP):
    """lanes (N, d) in 0..1 -> fitted Map. Segments alike in mood are pushed to bodies alike in the surrogate's
    descriptors; each step takes a random batch and the correlation over its segment pairs."""
    m = Map(lanes.shape[1], power_anchor, seed)
    m.mean, m.std = lanes.mean(axis=0), np.maximum(lanes.std(axis=0), 1e-8)
    z = torch.tensor(m.standardised(lanes), dtype=torch.float32)
    x = torch.tensor(lanes, dtype=torch.float32)
    rng = np.random.default_rng(seed)
    opt = torch.optim.Adam([m.raw, m.b], lr=lr)
    for _ in range(steps):
        idx = torch.tensor(rng.choice(len(x), size=min(batch, len(x)), replace=False))
        n = len(idx)
        iu = torch.triu_indices(n, n, 1)
        d_mood = torch.cdist(z[idx], z[idx])[iu[0], iu[1]]
        d_body = torch.cdist(surrogate(m.forward(x[idx])), surrogate(m.forward(x[idx])))[iu[0], iu[1]]
        opt.zero_grad()
        loss = -_pearson(d_mood, d_body) + penalty * (m.weights ** 2).sum()
        loss.backward()
        opt.step()
    return m


def surrogate_rsa(m, lanes, surrogate, n=RSA_SEGMENTS, seed=SEED_MAP):
    """Spearman of mood distances and surrogate-descriptor distances of the map's bodies, on <= n segments."""
    idx = np.random.default_rng(seed).permutation(len(lanes))[:n]
    with torch.no_grad():
        desc = surrogate(m.forward(torch.tensor(lanes[idx], dtype=torch.float32))).numpy()
    return rsa.rho(rsa.rank_matrix(m.standardised(lanes[idx])), rsa.rank_matrix(desc))


def inner_groups(songs, n_folds=INNER_FOLDS, seed=common.SEED_INNER):
    """Inner fold per segment, by song: a song is never in two folds."""
    uniq = np.array(sorted(set(songs)))
    which = dict(zip(np.random.default_rng(seed).permutation(uniq), np.arange(len(uniq)) % n_folds))
    return np.array([which[s] for s in songs])


def pick_k(scores):
    """The k with the best score; ties go to the smaller k."""
    return max(scores, key=lambda k: (scores[k], -k))


def choose_k(lanes, songs, surrogate, power_anchor=True, grid=K_GRID, **fit_args):
    """k rest lanes by 3 inner folds over the training songs: mean surrogate representational similarity on the
    held-out inner fold. Ties go to the smaller k. -> (k, {k: score})."""
    groups = inner_groups(songs)
    grid = [k for k in grid if k <= lanes.shape[1] - 2]
    scores = {}
    for k in grid:
        sub = lanes[:, :2 + k]
        per = []
        for f in range(INNER_FOLDS):
            m = fit_map(sub[groups != f], surrogate, power_anchor, **fit_args)
            per.append(surrogate_rsa(m, sub[groups == f], surrogate))
        scores[k] = float(np.mean(per))
    return pick_k(scores), scores


# -------------------------------------------------------------------- library

def load_regions(study=STUDY):
    """-> (bodies (8, 15) of the body study's regions, reference descriptors (2000, 37) of its sweep)."""
    regions = json.loads((pathlib.Path(study) / "regions.json").read_text())
    sweep = json.loads((pathlib.Path(study) / "sweep.json").read_text())["clips"]
    return (np.array([sweep[r["centre"]]["b"] for r in regions["regions"]]),
            np.array([c["desc"] for c in sweep]))


class Library:
    """Cluster the training mood into as many clusters as there are regions; give each cluster the region that makes
    the cluster centres' pairwise distances most like the regions' pairwise descriptor distances (Pearson over the
    pairs, all assignments tried, first best wins). Cluster c takes region assignment[c]. Training segments only."""

    def __init__(self, bodies, seed=SEED_KMEANS):
        self.bodies, self.seed = np.asarray(bodies), seed

    def fit(self, lanes_z, region_desc_z):
        n = len(self.bodies)
        self.kmeans = KMeans(n_clusters=n, n_init=10, random_state=self.seed).fit(lanes_z)
        iu = np.triu_indices(n, 1)
        mood = np.linalg.norm(self.kmeans.cluster_centers_[:, None] - self.kmeans.cluster_centers_[None], axis=2)[iu]
        body = np.linalg.norm(region_desc_z[:, None] - region_desc_z[None], axis=2)
        perms = np.array(list(itertools.permutations(range(n))))
        under = body[perms[:, iu[0]], perms[:, iu[1]]]                       # (assignments, pairs)
        a, b = mood - mood.mean(), under - under.mean(axis=1, keepdims=True)
        scores = (b @ a) / (np.linalg.norm(b, axis=1) * np.linalg.norm(a) + 1e-12)
        best = int(np.argmax(scores))                                          # the first best wins
        self.assignment, self.score = perms[best], float(scores[best])
        return self

    def regions(self, lanes_z):
        return self.assignment[self.kmeans.predict(lanes_z)]

    def decode(self, lanes_z):
        return self.bodies[self.regions(lanes_z)]
