//! Absolute-time playback for resolved 3D ensemble scores.

use hyst_audio::AudioClock;
use hyst_compile::ensemble::{EnsembleFrame, EnsembleScore};

use crate::choreography_output::ClockPosition;

pub struct EnsembleOutput {
    score: EnsembleScore,
}

impl EnsembleOutput {
    pub fn new(score: EnsembleScore) -> Result<Self, String> {
        score.validate()?;
        Ok(Self { score })
    }

    pub fn sample_at(&self, time_seconds: f64) -> Result<EnsembleFrame, String> {
        self.score.sample(time_seconds)
    }

    pub fn sample_clock(
        &self,
        clock: &AudioClock,
        position: ClockPosition,
    ) -> Result<EnsembleFrame, String> {
        if clock.sample_rate() == 0 {
            return Err("audio clock sample rate must be nonzero".into());
        }
        let seconds = match position {
            ClockPosition::Logical => clock.logical_position_secs(),
            ClockPosition::Audible => clock.audible_position_secs(),
        };
        self.sample_at(seconds)
    }

    pub fn score(&self) -> &EnsembleScore {
        &self.score
    }
}
