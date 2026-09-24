//! Ported from `src/audio/worklet/envelope.ts`.

/// Attack/release envelope follower, run once per analysis hop.
pub struct EnvelopeFollower {
    value: f32,
    initialized: bool,
    attack_coeff: f32,
    release_coeff: f32,
}

impl EnvelopeFollower {
    pub fn new(attack_ms: f32, release_ms: f32, hop_ms: f32) -> Self {
        Self {
            value: 0.0,
            initialized: false,
            attack_coeff: (-hop_ms / attack_ms).exp(),
            release_coeff: (-hop_ms / release_ms).exp(),
        }
    }

    pub fn update(&mut self, input: f32) -> f32 {
        // Seed from the first real input rather than climbing from 0 — see
        // the TS original's comment: avoids a spurious "rise" reading for
        // the first several seconds of playback on any paired fast/slow
        // envelope (build/break detectors).
        if !self.initialized {
            self.value = input;
            self.initialized = true;
            return self.value;
        }
        let coeff = if input > self.value {
            self.attack_coeff
        } else {
            self.release_coeff
        };
        self.value = coeff * self.value + (1.0 - coeff) * input;
        self.value
    }
}

/// Tracks a slowly-decaying running peak and normalizes against it, so raw
/// magnitudes with no fixed scale settle into 0..1 without manual
/// calibration.
pub struct AdaptiveNormalizer {
    peak: f32,
    decay_coeff: f32,
}

impl AdaptiveNormalizer {
    pub fn new(decay_ms: f32, hop_ms: f32) -> Self {
        Self {
            peak: 1e-6,
            decay_coeff: (-hop_ms / decay_ms).exp(),
        }
    }

    pub fn normalize(&mut self, value: f32) -> f32 {
        self.peak = value.max(self.peak * self.decay_coeff);
        if self.peak > 1e-6 {
            (value / self.peak).min(1.0)
        } else {
            0.0
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn envelope_seeds_from_first_input_not_zero() {
        let mut env = EnvelopeFollower::new(10.0, 300.0, 10.0);
        assert_eq!(env.update(0.5), 0.5);
    }

    #[test]
    fn envelope_attacks_faster_than_it_releases() {
        let mut fast_release = EnvelopeFollower::new(10.0, 10.0, 10.0);
        let mut slow_release = EnvelopeFollower::new(10.0, 500.0, 10.0);
        fast_release.update(1.0);
        slow_release.update(1.0);
        let f = fast_release.update(0.0);
        let s = slow_release.update(0.0);
        assert!(s > f, "slower release should decay less per step");
    }

    #[test]
    fn normalizer_settles_toward_1_at_the_running_peak() {
        let mut norm = AdaptiveNormalizer::new(6000.0, 10.0);
        for _ in 0..50 {
            norm.normalize(1.0);
        }
        assert!((norm.normalize(1.0) - 1.0).abs() < 1e-3);
    }

    #[test]
    fn normalizer_never_exceeds_1() {
        let mut norm = AdaptiveNormalizer::new(6000.0, 10.0);
        norm.normalize(0.1);
        assert!(norm.normalize(10.0) <= 1.0);
    }
}
