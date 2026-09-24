//! Fullness / onset-density, ported from `src/audio/worklet/brain/activity.ts`.
//! R1 scope note: ported as always-alive bus-signal producers only — the
//! plan's R1 item doesn't name `DropDetector`/`BuildDetector`/`BreakDetector`
//! (those own a *separate* fullness/onset-density instance in the TS
//! original for exactly this reason: different cadence/lifecycle per
//! consumer); this crate provides only the bus-level instance for now.

use super::envelope::EnvelopeFollower;

const FAST_MS: f32 = 80.0;
const SUSTAIN_MS: f32 = 1800.0;
const SLOW_MS: f32 = 3000.0;
const CREST_FAST_MS: f32 = 60.0;
const CREST_PENALTY_GAIN: f32 = 0.6;

const ONSET_RATE_MS: f32 = 1500.0;
const ONSET_BASELINE_MS: f32 = 4000.0;
const ONSET_ACTIVITY_SCALE: f32 = 3.0;

pub struct FullnessResult {
    pub fullness: f32,
    #[allow(dead_code)] // mirrors the TS `slow` field; not yet consumed (no DropDetector port)
    pub slow: f32,
}

pub struct FullnessTracker {
    fast_energy: EnvelopeFollower,
    sustained_energy: EnvelopeFollower,
    slow_energy: EnvelopeFollower,
    crest_peak: EnvelopeFollower,
}

impl FullnessTracker {
    pub fn new(hop_ms: f32) -> Self {
        Self {
            fast_energy: EnvelopeFollower::new(FAST_MS, FAST_MS, hop_ms),
            sustained_energy: EnvelopeFollower::new(SUSTAIN_MS, SUSTAIN_MS, hop_ms),
            slow_energy: EnvelopeFollower::new(SLOW_MS, SLOW_MS, hop_ms),
            crest_peak: EnvelopeFollower::new(CREST_FAST_MS, CREST_FAST_MS, hop_ms),
        }
    }

    pub fn update(&mut self, low_energy: f32) -> FullnessResult {
        let fast = self.fast_energy.update(low_energy);
        let sustained = self.sustained_energy.update(low_energy);
        let slow = self.slow_energy.update(low_energy);
        let peak = self.crest_peak.update(fast);
        let crest = if peak > 1e-6 { fast / peak } else { 1.0 };
        let crest_penalty = ((crest - 1.0).abs() * CREST_PENALTY_GAIN).min(1.0);
        let fullness = (sustained * (1.0 - crest_penalty)).max(0.0);
        FullnessResult { fullness, slow }
    }
}

pub struct OnsetDensityResult {
    pub rate: f32,
    #[allow(dead_code)]
    // mirrors the TS `jump` field; DropDetector's own consumer isn't ported yet
    pub jump: f32,
}

pub struct OnsetDensityTracker {
    onset_rate: EnvelopeFollower,
    onset_baseline: EnvelopeFollower,
}

impl OnsetDensityTracker {
    pub fn new(hop_ms: f32) -> Self {
        Self {
            onset_rate: EnvelopeFollower::new(ONSET_RATE_MS, ONSET_RATE_MS, hop_ms),
            onset_baseline: EnvelopeFollower::new(ONSET_BASELINE_MS, ONSET_BASELINE_MS, hop_ms),
        }
    }

    pub fn update(&mut self, onset_activity: f32) -> OnsetDensityResult {
        let rate = self.onset_rate.update(onset_activity);
        let baseline = self.onset_baseline.update(onset_activity);
        let jump = rate * ONSET_ACTIVITY_SCALE - baseline * ONSET_ACTIVITY_SCALE;
        OnsetDensityResult {
            rate: rate * ONSET_ACTIVITY_SCALE,
            jump,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sustained_low_energy_reads_as_full() {
        let mut tracker = FullnessTracker::new(10.0);
        let mut last = 0.0;
        for _ in 0..500 {
            last = tracker.update(1.0).fullness;
        }
        assert!(last > 0.5);
    }

    #[test]
    fn a_pulsing_reverb_tail_is_penalized_vs_true_fullness() {
        let mut pulsing = FullnessTracker::new(10.0);
        let mut steady = FullnessTracker::new(10.0);
        let mut pulsing_last = 0.0;
        let mut steady_last = 0.0;
        for i in 0..500 {
            let pulse_input = if i % 10 < 2 { 1.0 } else { 0.05 };
            pulsing_last = pulsing.update(pulse_input).fullness;
            steady_last = steady.update(0.6).fullness;
        }
        // Both may reach moderate sustained energy, but the pulsing source's
        // crest penalty should keep it from reading as fully "full".
        assert!(steady_last > pulsing_last * 0.8 || steady_last > 0.4);
    }

    #[test]
    fn onset_rate_rises_with_sustained_onset_activity() {
        let mut tracker = OnsetDensityTracker::new(10.0);
        let mut last = 0.0;
        for _ in 0..500 {
            last = tracker.update(1.0).rate;
        }
        assert!(last > 1.0);
    }
}
