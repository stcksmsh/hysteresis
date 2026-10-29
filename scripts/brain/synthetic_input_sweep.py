import sys
sys.path.insert(0, __import__('os').path.dirname(__file__))
import numpy as np, grfnn
from scipy.ndimage import gaussian_filter1d

rng = np.random.default_rng(0)


def clicks(rate, dur, width=0.03, height=4.0):
    x = np.zeros(int(dur * 100)); t = 0.25
    while t < dur:
        x[int(round(t * 100))] = 1.0; t += 1 / rate
    x = gaussian_filter1d(x, width * 100)
    return height * x / x.max()


noise = np.abs(rng.standard_normal(4000)) * 1.0
for c in (0.05, 0.1, 0.2):
    grfnn.C_IN = c
    row = []
    for rate in (2.0, 1.5):
        x = clicks(rate, 40); r = grfnn.pulse(x, x)
        row.append((rate, round(float(np.median(r['readout_freq'][2500:])), 2), round(float(r['readout_amp'][2500:].mean()), 2)))
    # input = standardised click bump added to noise
    xn = clicks(2.0, 40) + noise[:4000]
    rn = grfnn.pulse(xn, xn)
    rz = grfnn.pulse(noise, noise)
    print(f'C_IN {c}: clicks {row}; clicks+noise readout {np.median(rn["readout_freq"][2500:]):.2f} Hz amp {rn["readout_amp"][2500:].mean():.2f}; noise only: max bank amp {rz["amp"][2500:].max():.3f}, mean readout amp {rz["readout_amp"][2500:].mean():.3f}, beats {len(rz["beats"])}')
