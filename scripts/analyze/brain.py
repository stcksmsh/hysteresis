"""Ports of src/audio/worklet/brain/{beat-tracker,build-detector,drop-detector,break-detector,activity,novelty}.ts."""
import math

import numpy as np

from .dsp import (TEMPO_MAX_BPM, TEMPO_MIN_BPM, AdaptiveNormalizer, EnvelopeFollower,  # noqa: F401
                  js_round)

# ---- beat-tracker.ts ----
HISTORY_SEC = 8
TEMPO_UPDATE_SEC = 0.5
TEMPO_SMOOTHING = 0.3
OCTAVE_BIAS_STRENGTH = 10
BT_ONSET_THRESHOLD = 0.4
PLL_GAIN = 0.2


class BeatTracker:
    def __init__(self, hop_sec: float):
        self.hop_sec = hop_sec
        self.novelty_buffer = np.zeros(js_round(HISTORY_SEC / hop_sec), dtype=np.float32)
        self.write_idx = 0
        self.filled = False
        self.hops_since_tempo_update = 0
        self.tempo_update_interval_hops = js_round(TEMPO_UPDATE_SEC / hop_sec)
        self.tempo_bpm = 120.0
        self.tempo_confidence = 0.0
        self.beat_period_sec = 60 / 120
        self.phase_anchor_sec = 0.0
        n = len(self.novelty_buffer)
        self._min_lag = js_round(60 / TEMPO_MAX_BPM / hop_sec)
        self._max_lag = js_round(60 / TEMPO_MIN_BPM / hop_sec)
        lags = np.arange(self._min_lag, self._max_lag + 1)
        self._lags = lags
        self._idx = (np.arange(n)[None, :] - lags[:, None] + n) % n

    def update(self, novelty: float, t_now: float):
        self.novelty_buffer[self.write_idx] = novelty
        self.write_idx = (self.write_idx + 1) % len(self.novelty_buffer)
        if self.write_idx == 0:
            self.filled = True
        self.hops_since_tempo_update += 1
        if self.filled and self.hops_since_tempo_update >= self.tempo_update_interval_hops:
            self.hops_since_tempo_update = 0
            self._update_tempo_estimate()
        phase = (t_now - self.phase_anchor_sec) / self.beat_period_sec
        beat_phase = phase - math.floor(phase)
        if novelty > BT_ONSET_THRESHOLD:
            error = beat_phase
            if error > 0.5:
                error -= 1
            self.phase_anchor_sec += error * self.beat_period_sec * PLL_GAIN
        return self.tempo_bpm, self.tempo_confidence, beat_phase

    def _update_tempo_estimate(self):
        buf = self.novelty_buffer.astype(np.float64)
        prev_lag = self.beat_period_sec / self.hop_sec
        self_energy = float(np.cumsum(buf * buf)[-1])
        if self_energy < 1e-9:
            return
        sums = np.cumsum(buf[None, :] * buf[self._idx], axis=1)[:, -1].tolist()
        best_lag = -1
        best_score = -math.inf
        for lag, s in zip(self._lags.tolist(), sums):
            octave_dist = math.log2(lag / prev_lag)
            biased = s * math.exp(-octave_dist * octave_dist * OCTAVE_BIAS_STRENGTH)
            if biased > best_score:
                best_score = biased
                best_lag = lag
        if best_lag > 0:
            new_tempo = 60 / (best_lag * self.hop_sec)
            self.tempo_bpm = self.tempo_bpm * (1 - TEMPO_SMOOTHING) + new_tempo * TEMPO_SMOOTHING
            self.beat_period_sec = 60 / self.tempo_bpm
            self.tempo_confidence = max(0, min(1, best_score / self_energy))


SLOT_COUNT = 4
SLOT_LEARNING_RATE = 0.2


class BarTracker:
    def __init__(self):
        self.beat_count = -1
        self.last_phase = 0.0
        self.slot_strength = np.zeros(SLOT_COUNT, dtype=np.float32)
        self.downbeat_slot = 0
        self.peak_novelty_since_beat = 0.0

    def update(self, beat_phase: float, novelty: float) -> float:
        self.peak_novelty_since_beat = max(self.peak_novelty_since_beat, novelty)
        if beat_phase < self.last_phase - 0.5:
            self.beat_count += 1
            slot = self.beat_count % SLOT_COUNT
            self.slot_strength[slot] = (float(self.slot_strength[slot]) * (1 - SLOT_LEARNING_RATE)
                                        + self.peak_novelty_since_beat * SLOT_LEARNING_RATE)
            self.peak_novelty_since_beat = 0.0
            if slot == SLOT_COUNT - 1:
                best = 0
                for i in range(1, SLOT_COUNT):
                    if self.slot_strength[i] > self.slot_strength[best]:
                        best = i
                self.downbeat_slot = best
        self.last_phase = beat_phase
        if self.beat_count < 0:
            return beat_phase / SLOT_COUNT
        beat_in_bar = (((self.beat_count - self.downbeat_slot) % SLOT_COUNT) + SLOT_COUNT) % SLOT_COUNT
        return (beat_in_bar + beat_phase) / SLOT_COUNT


# ---- build-detector.ts ----
class BuildDetector:
    FAST_MS = 600
    SLOW_MS = 6000
    INTEGRATION_GAIN = 0.06
    DECAY_PER_HOP = 0.0015

    def __init__(self, hop_ms: float):
        self.centroid_fast = EnvelopeFollower(self.FAST_MS, self.FAST_MS, hop_ms)
        self.centroid_slow = EnvelopeFollower(self.SLOW_MS, self.SLOW_MS, hop_ms)
        self.sub_fast = EnvelopeFollower(self.FAST_MS, self.FAST_MS, hop_ms)
        self.sub_slow = EnvelopeFollower(self.SLOW_MS, self.SLOW_MS, hop_ms)
        self.progress = 0.0

    def update(self, centroid: float, sub: float) -> float:
        c_rise = max(0, self.centroid_fast.update(centroid) - self.centroid_slow.update(centroid))
        s_rise = max(0, self.sub_fast.update(sub) - self.sub_slow.update(sub))
        rise = (c_rise + s_rise) / 2
        self.progress += rise * self.INTEGRATION_GAIN - self.DECAY_PER_HOP
        self.progress = max(0, min(1, self.progress))
        return self.progress

    def reset(self):
        self.progress = 0.0


# ---- break-detector.ts ----
class BreakDetector:
    LOW_ENERGY_MS = 2000
    ONSET_ACTIVITY_MS = 1500
    TENSION_ATTACK_MS = 500
    TENSION_RELEASE_MS = 1200
    ONSET_ACTIVITY_SCALE = 3
    ENTER = 0.4
    EXIT = 0.25

    def __init__(self, hop_ms: float):
        self.low_slow = EnvelopeFollower(self.LOW_ENERGY_MS, self.LOW_ENERGY_MS, hop_ms)
        self.onset_slow = EnvelopeFollower(self.ONSET_ACTIVITY_MS, self.ONSET_ACTIVITY_MS, hop_ms)
        self.tension_env = EnvelopeFollower(self.TENSION_ATTACK_MS, self.TENSION_RELEASE_MS, hop_ms)
        self.in_break = False

    def update(self, low_energy: float, novelty: float, t_now: float):
        low = self.low_slow.update(low_energy)
        onset_activity = self.onset_slow.update(novelty)
        raw = (1 - low) * (1 - min(1, onset_activity * self.ONSET_ACTIVITY_SCALE))
        tension = self.tension_env.update(max(0, raw))
        event = None
        if not self.in_break and tension > self.ENTER:
            self.in_break = True
            event = ('breakStart', tension, t_now)
        elif self.in_break and tension < self.EXIT:
            self.in_break = False
            event = ('breakEnd', 1 - tension, t_now)
        return tension, event


# ---- activity.ts ----
class FullnessTracker:
    FAST_MS = 80
    SUSTAIN_MS = 1800
    SLOW_MS = 3000
    CREST_FAST_MS = 60
    CREST_PENALTY_GAIN = 0.6

    def __init__(self, hop_ms: float):
        self.fast = EnvelopeFollower(self.FAST_MS, self.FAST_MS, hop_ms)
        self.sustained = EnvelopeFollower(self.SUSTAIN_MS, self.SUSTAIN_MS, hop_ms)
        self.slow = EnvelopeFollower(self.SLOW_MS, self.SLOW_MS, hop_ms)
        self.crest_peak = EnvelopeFollower(self.CREST_FAST_MS, self.CREST_FAST_MS, hop_ms)

    def update(self, low_energy: float):
        fast = self.fast.update(low_energy)
        sustained = self.sustained.update(low_energy)
        slow = self.slow.update(low_energy)
        peak = self.crest_peak.update(fast)
        crest = fast / peak if peak > 1e-6 else 1
        penalty = min(1, abs(crest - 1) * self.CREST_PENALTY_GAIN)
        return max(0, sustained * (1 - penalty)), slow


class OnsetDensityTracker:
    ONSET_RATE_MS = 1500
    ONSET_BASELINE_MS = 4000
    SCALE = 3

    def __init__(self, hop_ms: float):
        self.rate = EnvelopeFollower(self.ONSET_RATE_MS, self.ONSET_RATE_MS, hop_ms)
        self.baseline = EnvelopeFollower(self.ONSET_BASELINE_MS, self.ONSET_BASELINE_MS, hop_ms)

    def update(self, onset_activity: float) -> float:
        """Returns `jump` (the only field DropDetector reads)."""
        rate = self.rate.update(onset_activity)
        baseline = self.baseline.update(onset_activity)
        return rate * self.SCALE - baseline * self.SCALE


# ---- novelty.ts ----
class NoveltyRingBuffer:
    """Cosine max-similarity against a ring of 7-vectors. The per-pair dot/norm sums are
    sequential over components (as in cosineSimilarity); only the loop over buffered
    vectors is batched."""

    def __init__(self, capacity: int, dim: int = 7):
        self.capacity = capacity
        self.dim = dim
        self.vecs = np.zeros((capacity, dim))
        self.norms = np.zeros(capacity)  # sqrt(normB), same value cosineSimilarity computes
        self.count = 0
        self.write_index = 0

    def max_similarity(self, vec) -> float:
        if self.count == 0:
            return 0.0
        a = list(vec)
        v = self.vecs[: self.count]
        dot = a[0] * v[:, 0]
        norm_a = a[0] * a[0]
        for i in range(1, self.dim):
            dot = dot + a[i] * v[:, i]
            norm_a = norm_a + a[i] * a[i]
        denom = math.sqrt(norm_a) * self.norms[: self.count]
        ok = denom > 1e-6
        s = np.where(ok, dot / np.where(ok, denom, 1.0), 0.0)
        best = float(s.max())
        return best if best > 0 else 0.0

    def push(self, vec) -> None:
        a = list(vec)
        norm_b = a[0] * a[0]
        for i in range(1, self.dim):
            norm_b = norm_b + a[i] * a[i]
        if self.count < self.capacity:
            slot = self.count
            self.count += 1
        else:
            slot = self.write_index
            self.write_index = (self.write_index + 1) % self.capacity
        self.vecs[slot] = a
        self.norms[slot] = math.sqrt(norm_b)


# ---- drop-detector.ts ----
FULLNESS_THRESHOLD = 0.5
ONSET_JUMP_MIN = 0.06
NOVELTY_WINDOW_SEC = 4
NOVELTY_THRESHOLD = 0.3
NOVELTY_HOLD_SEC = 3.0
CONFIRM_WINDOW_SEC = 0.3
CONFIRM_ELEVATED_FRACTION = 0.5
ELEVATED_MARGIN = 0.08
BEAT_SNAP_LOOKAHEAD_SEC = 0.15
REFRACTORY_SEC = 8.0
STARTUP_GRACE_SEC = 4.0


class DropDetector:
    def __init__(self, hop_ms: float):
        self.fullness_tracker = FullnessTracker(hop_ms)
        self.onset_density_tracker = OnsetDensityTracker(hop_ms)
        self.novelty = NoveltyRingBuffer(max(1, js_round((NOVELTY_WINDOW_SEC * 1000) / hop_ms)))
        self.novelty_peak = 0.0
        self.refractory_until = 0.0
        self.armed_at = None
        self.armed_baseline = 0.0
        self.armed_peak_fullness = 0.0
        self.elevated_hops = 0
        self.window_hops = 0
        self.hop_sec = hop_ms / 1000
        self.started_at = None

    def update(self, low_energy: float, onset_activity: float, vec, beat_phase: float,
               tempo_bpm: float, t_now: float):
        """Returns (strength, t) or None."""
        if self.started_at is None:
            self.started_at = t_now
        fullness, slow = self.fullness_tracker.update(low_energy)
        onset_jump = self.onset_density_tracker.update(onset_activity)
        novelty_value = 1 - self.novelty.max_similarity(vec)
        self.novelty.push(vec)
        self.novelty_peak = max(novelty_value, self.novelty_peak * math.exp(-self.hop_sec / NOVELTY_HOLD_SEC))

        if t_now - self.started_at < STARTUP_GRACE_SEC or t_now < self.refractory_until:
            self._disarm()
            return None

        if self.armed_at is None:
            rhythmic = fullness > FULLNESS_THRESHOLD and onset_jump > ONSET_JUMP_MIN and self.novelty_peak > NOVELTY_THRESHOLD
            soft = fullness > FULLNESS_THRESHOLD and self.novelty_peak > NOVELTY_THRESHOLD
            if rhythmic or soft:
                self.armed_at = t_now
                self.armed_baseline = slow
                self.armed_peak_fullness = fullness
                self.elevated_hops = 0
                self.window_hops = 0
            return None

        self.armed_peak_fullness = max(self.armed_peak_fullness, fullness)
        self.window_hops += 1
        if low_energy > self.armed_baseline + ELEVATED_MARGIN:
            self.elevated_hops += 1
        if t_now - self.armed_at < CONFIRM_WINDOW_SEC:
            return None
        if self.elevated_hops / max(1, self.window_hops) < CONFIRM_ELEVATED_FRACTION:
            self._disarm()
            return None
        if tempo_bpm > 0:
            beat_period_sec = 60 / tempo_bpm
            sec_to_next_beat = (1 - beat_phase) * beat_period_sec
            if sec_to_next_beat > self.hop_sec and sec_to_next_beat <= BEAT_SNAP_LOOKAHEAD_SEC:
                return None
        strength = max(0, min(1, self.armed_peak_fullness))
        self._disarm()
        self.refractory_until = t_now + REFRACTORY_SEC
        return strength, t_now

    def _disarm(self):
        self.armed_at = None
        self.armed_peak_fullness = 0.0
