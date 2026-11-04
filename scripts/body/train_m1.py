"""Train the M1 cerebellum and fit its baselines on the same training data; save one bundle for check_m1.py.

    /secondary/hyst-env/brain/bin/python -u train_m1.py TRAIN.npz OUT.pt --epochs 40 [--hidden 128] [--layers 1] [--threads 12]
Resumes nothing (a run is ~1 h locally); a per-epoch checkpoint is written next to OUT.pt as OUT.pt.ckpt for inspection.
"""
import argparse
import time

import numpy as np
import torch

import cerebellum as C

ap = argparse.ArgumentParser()
ap.add_argument("train")
ap.add_argument("out")
ap.add_argument("--epochs", type=int, default=40)
ap.add_argument("--hidden", type=int, default=128)
ap.add_argument("--layers", type=int, default=1)
ap.add_argument("--threads", type=int, default=12)
ap.add_argument("--lr", type=float, default=2e-3)
ap.add_argument("--seed", type=int, default=0)
a = ap.parse_args()
torch.set_num_threads(a.threads)
t0 = time.time()
d = np.load(a.train)
obs, tgt = d["obs"], d["tgt"]
st = C.Stats(obs, tgt)
X, (Y, V) = C.features(obs, tgt, st), C.labels(obs, st)
del obs, tgt
print("data", X.shape, f"{time.time() - t0:.0f}s", flush=True)
net = C.train(X, Y, V, a.epochs, hidden=a.hidden, layers=a.layers, lr=a.lr, seed=a.seed, log=lambda s: print(s, flush=True), ckpt=a.out + ".ckpt")
ridge = C.Ridge().fit(X, Y, V)
pvar = C.persistence_var(Y, V)
net.eval()
C.save_bundle(a.out, net, st, ridge, pvar, a.hidden, a.layers, {"epochs": a.epochs, "train_seconds": time.time() - t0, "train": a.train, "lr": a.lr, "seed": a.seed})
print("saved", a.out, f"total {time.time() - t0:.0f}s", flush=True)
