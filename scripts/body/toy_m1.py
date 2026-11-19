"""M1 toy: 1 h of babbling, small model, must beat persistence at +100 ms on 10 min of held-out babbling (mean NLL and MSE).

    /secondary/hyst-env/brain/bin/python toy_m1.py [--epochs 30] [--hidden 128]
"""
import argparse

import numpy as np
import torch

import cerebellum as C

D = "/secondary/hyst-data/body/"
ap = argparse.ArgumentParser()
ap.add_argument("--epochs", type=int, default=30)
ap.add_argument("--hidden", type=int, default=128)
ap.add_argument("--threads", type=int, default=12)
a = ap.parse_args()
torch.set_num_threads(a.threads)
tr, he = np.load(D + "toy_train.npz"), np.load(D + "toy_held.npz")
st = C.Stats(tr["obs"], tr["tgt"])
Xtr, (Ytr, Vtr) = C.features(tr["obs"], tr["tgt"], st), C.labels(tr["obs"], st)
Xhe, (Yhe, Vhe) = C.features(he["obs"], he["tgt"], st), C.labels(he["obs"], st)
net = C.train(Xtr, Ytr, Vtr, a.epochs, hidden=a.hidden)
ridge = C.Ridge().fit(Xtr, Ytr, Vtr)
ev = C.evaluate(net, Xhe, Yhe, Vhe, ridge, C.persistence_var(Ytr, Vtr))
for h, name in enumerate(C.HNAMES):
    print(name, {k: (round(float(v["nll"][:, h].mean()), 4), round(float(v["mse"][:, h].mean()), 4)) for k, v in ev.items()}, "(nll, mse)")
m, p = ev["model"], ev["persistence"]
ok = m["nll"][:, 2].mean() < p["nll"][:, 2].mean() and m["mse"][:, 2].mean() < p["mse"][:, 2].mean()
print("TOY", "PASS" if ok else "FAIL", "model beats persistence at +100 ms (nll and mse)")
