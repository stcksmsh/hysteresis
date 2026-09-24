//! hyst-audio — playback, clock, live analysis (R1). See
//! `SINTEZA_IMPLEMENTATION_PLAN.md` §4 (R1) for scope.

pub mod beat;
pub mod clock;
pub mod delay_line;
pub mod dsp;
pub mod features;
pub mod playback;
pub mod wav_source;

pub use beat::{BarTracker, BeatTracker};
pub use clock::AudioClock;
pub use delay_line::DelayLine;
pub use features::FeatureExtractor;
pub use playback::{Playback, PlaybackError};
pub use wav_source::{WavSource, WavSourceError};
