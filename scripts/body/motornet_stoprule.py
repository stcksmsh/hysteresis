"""WO29A: numbers for the 7.45.5 stop rule, per shown setting. Numbers only, no judgement.
Per joint: position-spectrum peak (Hann, 12 s, DC excluded, bins > 0.1 Hz), whether it lies within one bin (1/12 Hz) of 100/60 Hz; activity PR.
    motornet_stoprule.py CLIPS_DIR
"""
import json
import sys
from pathlib import Path

import numpy as np

HZ, BEAT = 50, 100 / 60
d = Path(sys.argv[1])
rows = {}
for it in json.loads((d / "manifest.json").read_text()):
    if it["part"] != 1:
        continue
    q = np.loadtxt(d / it["csv"], delimiter=",", skiprows=8)[:, 1:]
    X = q - q.mean(0)
    P = np.abs(np.fft.rfft(X * np.hanning(len(X))[:, None], axis=0)) ** 2
    f = np.fft.rfftfreq(len(X), 1 / HZ)
    pk = [float(f[np.argmax(np.where(f > 0.1, P[:, j], 0))]) for j in range(5)]
    r = np.load(d / it["activity"]).astype(float)
    lam = np.clip(np.linalg.eigvalsh(np.cov(r.T)), 0, None)
    rows[it["setting"]] = dict(peak_hz=[round(p, 3) for p in pk], at_beat=[bool(abs(p - BEAT) <= 1 / 12) for p in pk],
                               pr=float(lam.sum() ** 2 / (lam ** 2).sum()))
    print(it["setting"], rows[it["setting"]])
print("beat Hz", BEAT, "bin Hz", 1 / 12)
(d.parent / "stoprule_numbers.json").write_text(json.dumps(rows, indent=1))
