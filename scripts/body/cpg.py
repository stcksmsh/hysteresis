"""M2: spinal pattern generators (docs/BODY_BRAIN_PLAN.md §7). No learning.

One phase oscillator per joint; the joint target is `centre + amplitude * cos(phase)`. The brain commands, at 10 Hz and per joint:
frequency (0.1-4 Hz), amplitude (deg), centre (deg) and the lag (0-0.5 cycle) by which the joint trails the joint before it.
    dphase_i/dt = 2 pi f_i (1 + COUPLING * sin(phase_{i-1} - 2 pi lag_i - phase_i))        (joint 0 has no neighbour: coupling 0)
so a positive lag makes the neighbour trail. Rate limits keep the targets smooth and inside the limits:
  * every parameter slews toward its commanded value (frequency 2 Hz/s, lag 0.25 cycle/s, centre and amplitude 0.1 x the joint's speed limit);
  * the used frequency is capped so the oscillation alone stays under 0.8 x the joint's speed limit and 0.7 x its acceleration limit
    (amplitude * 2 pi f * (1 + COUPLING) <= 0.8 v; amplitude * (2 pi f (1 + COUPLING))^2 <= 0.7 a);
  * bends: centre + amplitude stays inside the joint range; the two continuous joints: amplitude capped at +-180 deg (overseer default, FOR USER).
Per control step the target moves by at most (0.8 + 0.1 + 0.1) x speed limit x dt.
"""
import math

import numpy as np

from arm_sim import swing_margin
from make_arm import LIMITS, NEUTRAL_DEG, RANGE_DEG

COUPLING = 0.25
F_MIN, F_MAX = 0.1, 4.0
LAG_MAX = 0.5
AMP_CAP_CONTINUOUS = 180.0
V = np.array([v for v, _ in LIMITS])
A = np.array([a for _, a in LIMITS])
LO = np.array([-180.0 if r is None else r[0] for r in RANGE_DEG])      # centre range
HI = np.array([180.0 if r is None else r[1] for r in RANGE_DEG])
BEND = np.array([r is not None for r in RANGE_DEG])


class CPG:
    def __init__(self, dt=0.01):
        self.dt = dt
        self.reset()

    def reset(self, centre=None):
        self.phase = np.zeros(5)
        self.freq, self.lag, self.amp = np.full(5, 0.5), np.zeros(5), np.zeros(5)
        self.centre = np.array(NEUTRAL_DEG if centre is None else centre, float)
        self.goal = {"freq": self.freq.copy(), "lag": self.lag.copy(), "amp": self.amp.copy(), "centre": self.centre.copy()}

    def command(self, freq, amp, centre, lag):
        """Set the goals (clipped to the command ranges). The used values slew toward them in `step`."""
        self.goal["freq"] = np.clip(freq, F_MIN, F_MAX)
        self.goal["amp"] = np.clip(amp, 0.0, np.where(BEND, HI, AMP_CAP_CONTINUOUS))
        self.goal["centre"] = np.clip(centre, LO, HI)
        self.goal["lag"] = np.clip(lag, 0.0, LAG_MAX)

    def _slew(self, cur, goal, rate):
        return cur + np.clip(goal - cur, -rate * self.dt, rate * self.dt)

    def step(self):
        """One control period -> target (5,) degrees."""
        g, dt = self.goal, self.dt
        self.freq = self._slew(self.freq, g["freq"], 2.0)
        self.lag = self._slew(self.lag, g["lag"], 0.25)
        self.centre = self._slew(self.centre, g["centre"], 0.1 * V)
        self.amp = self._slew(self.amp, g["amp"], 0.1 * V)
        amp = np.where(BEND, np.minimum(self.amp, HI - np.abs(self.centre)), self.amp)
        amp = np.maximum(amp, 0.0)
        # cap the frequency actually used so the oscillation stays under its share of speed and acceleration
        w = 2 * math.pi * (1 + COUPLING)
        with np.errstate(divide="ignore"):
            f_cap = np.minimum(0.8 * V / np.maximum(amp, 1e-9) / w, np.sqrt(0.7 * A / np.maximum(amp, 1e-9)) / w)
        f = np.minimum(self.freq, f_cap)
        lead = np.concatenate([[0.0], self.phase[:-1] - 2 * math.pi * self.lag[1:]])
        pull = np.concatenate([[0.0], np.sin(lead[1:] - self.phase[1:])])
        self.phase = self.phase + dt * 2 * math.pi * f * (1 + COUPLING * pull)
        return self.centre + amp * np.cos(self.phase)


def random_commands(rng, freq=(0.1, 4.0), amp_frac=(0.0, 1.0), centre_box=None, lag=(0.0, 0.5), floor_margin_m=None):
    """One random command (freq, amp, centre, lag), each (5,). amp is a fraction of the largest amplitude the joint allows at that centre.
    With `floor_margin_m`, draws again until every corner of the swept box clears the floor rule by that margin (arm_sim.swing_margin)."""
    lo, hi = (LO, HI) if centre_box is None else centre_box
    while True:
        c = rng.uniform(lo, hi)
        a_max = np.where(BEND, HI - np.abs(c), AMP_CAP_CONTINUOUS)
        a = rng.uniform(*amp_frac, 5) * a_max
        if floor_margin_m is None or swing_margin(c, a) >= floor_margin_m:
            return rng.uniform(*freq, 5), a, c, rng.uniform(*lag, 5)
