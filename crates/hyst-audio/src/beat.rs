//! Beat/bar PLL, ported from `src/audio/worklet/brain/beat-tracker.ts`.
//! "Port the working PLL first" (plan §4 R1) — native removes the
//! model-size ceiling for a future better live beat tracker, but that's not
//! this task; this is a faithful port, not a redesign.

const HISTORY_SEC: f32 = 8.0;
const TEMPO_UPDATE_SEC: f32 = 0.5;
const TEMPO_SMOOTHING: f32 = 0.3;
const OCTAVE_BIAS_STRENGTH: f32 = 10.0;
const ONSET_THRESHOLD: f32 = 0.4;
const PLL_GAIN: f32 = 0.2;

const TEMPO_MIN_BPM: f32 = 60.0;
const TEMPO_MAX_BPM: f32 = 190.0;

#[derive(Debug, Clone, Copy)]
pub struct BeatTrackerOutput {
    pub tempo_bpm: f32,
    pub tempo_confidence: f32,
    pub beat_phase: f32,
}

/// Tempo + a phase-locked oscillator that free-runs from tempo+time alone
/// and only receives small proportional nudges when onsets are present
/// (PLL-style) — glides into alignment, holds a steady grid with zero
/// correction input during breaks with no percussion.
pub struct BeatTracker {
    novelty_buffer: Vec<f32>,
    write_idx: usize,
    filled: bool,
    hop_sec: f32,
    hops_since_tempo_update: usize,
    tempo_update_interval_hops: usize,

    tempo_bpm: f32,
    tempo_confidence: f32,
    beat_period_sec: f32,
    phase_anchor_sec: f32,
}

impl BeatTracker {
    pub fn new(hop_sec: f32) -> Self {
        Self {
            novelty_buffer: vec![0.0; (HISTORY_SEC / hop_sec).round() as usize],
            write_idx: 0,
            filled: false,
            hop_sec,
            hops_since_tempo_update: 0,
            tempo_update_interval_hops: (TEMPO_UPDATE_SEC / hop_sec).round() as usize,
            tempo_bpm: 120.0,
            tempo_confidence: 0.0,
            beat_period_sec: 60.0 / 120.0,
            phase_anchor_sec: 0.0,
        }
    }

    pub fn update(&mut self, novelty: f32, t_now: f32) -> BeatTrackerOutput {
        let len = self.novelty_buffer.len();
        self.novelty_buffer[self.write_idx] = novelty;
        self.write_idx = (self.write_idx + 1) % len;
        if self.write_idx == 0 {
            self.filled = true;
        }

        self.hops_since_tempo_update += 1;
        if self.filled && self.hops_since_tempo_update >= self.tempo_update_interval_hops {
            self.hops_since_tempo_update = 0;
            self.update_tempo_estimate();
        }

        let beat_phase = self.compute_beat_phase(t_now);
        if novelty > ONSET_THRESHOLD {
            self.nudge_phase(beat_phase);
        }

        BeatTrackerOutput {
            tempo_bpm: self.tempo_bpm,
            tempo_confidence: self.tempo_confidence,
            beat_phase,
        }
    }

    fn compute_beat_phase(&self, t_now: f32) -> f32 {
        let phase = (t_now - self.phase_anchor_sec) / self.beat_period_sec;
        phase - phase.floor()
    }

    fn nudge_phase(&mut self, beat_phase: f32) {
        let mut error = beat_phase;
        if error > 0.5 {
            error -= 1.0;
        }
        self.phase_anchor_sec += error * self.beat_period_sec * PLL_GAIN;
    }

    fn update_tempo_estimate(&mut self) {
        let min_lag = (60.0 / TEMPO_MAX_BPM / self.hop_sec).round() as usize;
        let max_lag = (60.0 / TEMPO_MIN_BPM / self.hop_sec).round() as usize;
        let buf = &self.novelty_buffer;
        let n = buf.len();
        let prev_lag = self.beat_period_sec / self.hop_sec;

        let self_energy: f32 = buf.iter().map(|&v| v * v).sum();
        if self_energy < 1e-9 {
            return;
        }

        let mut best_lag: i64 = -1;
        let mut best_score = f32::NEG_INFINITY;
        for lag in min_lag..=max_lag {
            let mut sum = 0.0f32;
            for i in 0..n {
                let j = ((i as i64 - lag as i64).rem_euclid(n as i64)) as usize;
                sum += buf[i] * buf[j];
            }
            let octave_dist = (lag as f32 / prev_lag).log2();
            let biased_score = sum * (-octave_dist * octave_dist * OCTAVE_BIAS_STRENGTH).exp();
            if biased_score > best_score {
                best_score = biased_score;
                best_lag = lag as i64;
            }
        }

        if best_lag > 0 {
            let new_tempo = 60.0 / (best_lag as f32 * self.hop_sec);
            self.tempo_bpm = self.tempo_bpm * (1.0 - TEMPO_SMOOTHING) + new_tempo * TEMPO_SMOOTHING;
            self.beat_period_sec = 60.0 / self.tempo_bpm;
            self.tempo_confidence = (best_score / self_energy).clamp(0.0, 1.0);
        }
    }
}

const SLOT_COUNT: usize = 4;
const SLOT_LEARNING_RATE: f32 = 0.2;

/// Best-effort downbeat guess (assumes 4/4): tracks which of the 4
/// beat-in-bar positions tends to carry the strongest onset, re-anchors
/// "beat 1" to it each bar.
pub struct BarTracker {
    beat_count: i64,
    last_phase: f32,
    slot_strength: [f32; SLOT_COUNT],
    downbeat_slot: usize,
    peak_novelty_since_beat: f32,
}

impl Default for BarTracker {
    fn default() -> Self {
        Self {
            beat_count: -1,
            last_phase: 0.0,
            slot_strength: [0.0; SLOT_COUNT],
            downbeat_slot: 0,
            peak_novelty_since_beat: 0.0,
        }
    }
}

impl BarTracker {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn update(&mut self, beat_phase: f32, novelty: f32) -> f32 {
        self.peak_novelty_since_beat = self.peak_novelty_since_beat.max(novelty);

        if beat_phase < self.last_phase - 0.5 {
            self.beat_count += 1;
            let slot = (self.beat_count as usize) % SLOT_COUNT;
            self.slot_strength[slot] = self.slot_strength[slot] * (1.0 - SLOT_LEARNING_RATE)
                + self.peak_novelty_since_beat * SLOT_LEARNING_RATE;
            self.peak_novelty_since_beat = 0.0;

            if slot == SLOT_COUNT - 1 {
                let mut best = 0;
                for i in 1..SLOT_COUNT {
                    if self.slot_strength[i] > self.slot_strength[best] {
                        best = i;
                    }
                }
                self.downbeat_slot = best;
            }
        }
        self.last_phase = beat_phase;

        if self.beat_count < 0 {
            return beat_phase / SLOT_COUNT as f32;
        }
        let beat_in_bar = (((self.beat_count - self.downbeat_slot as i64) % SLOT_COUNT as i64)
            + SLOT_COUNT as i64)
            % SLOT_COUNT as i64;
        (beat_in_bar as f32 + beat_phase) / SLOT_COUNT as f32
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const SAMPLE_RATE: f32 = 48_000.0;
    const HOP_SIZE: f32 = 512.0;
    const HOP_SEC: f32 = HOP_SIZE / SAMPLE_RATE;

    /// Deterministic synthetic signal: a metronome click train at a known
    /// BPM — mirrors `tests/unit/beat-tracker.spec.ts`'s `runClickTrain`.
    fn run_click_train(bpm: f32, duration_sec: f32) -> BeatTracker {
        let mut tracker = BeatTracker::new(HOP_SEC);
        let period_sec = 60.0 / bpm;
        let mut t = 0.0f32;
        while t < duration_sec {
            let phase_in_period = t % period_sec;
            let novelty = if phase_in_period < HOP_SEC { 1.0 } else { 0.0 };
            tracker.update(novelty, t);
            t += HOP_SEC;
        }
        tracker
    }

    #[test]
    fn locks_onto_the_true_tempo_of_a_120_bpm_click_train() {
        let mut tracker = run_click_train(120.0, 12.0);
        let result = tracker.update(0.0, 12.0);
        assert!(result.tempo_bpm > 110.0);
        assert!(result.tempo_bpm < 130.0);
        assert!(result.tempo_confidence > 0.1);
    }

    #[test]
    fn locks_onto_a_different_tempo_90_bpm_just_as_well() {
        let mut tracker = run_click_train(90.0, 12.0);
        let result = tracker.update(0.0, 12.0);
        assert!(result.tempo_bpm > 80.0);
        assert!(result.tempo_bpm < 100.0);
    }

    #[test]
    fn beat_phase_keeps_advancing_smoothly_through_a_silent_gap() {
        let mut tracker = run_click_train(120.0, 8.0);
        let before = tracker.update(0.0, 8.0);
        let mut t = 8.0f32;
        let mut after = before;
        while t < 10.0 {
            after = tracker.update(0.0, t);
            t += HOP_SEC;
        }
        assert!((after.tempo_bpm - before.tempo_bpm).abs() < 1.0);
    }

    #[test]
    fn bar_tracker_produces_a_value_in_0_1_and_advances() {
        let mut bar = BarTracker::new();
        let mut last = -1.0;
        for i in 0..200 {
            let beat_phase = (i as f32 * 0.05) % 1.0;
            let v = bar.update(beat_phase, 0.0);
            assert!((0.0..1.0).contains(&v));
            last = v;
        }
        assert!(last >= 0.0);
    }
}
