//! Layer 1 DSP primitives, ported from `src/audio/worklet/`. Pure, sample-
//! buffer-in/values-out — no audio-device or clock concerns here, those live
//! in `crate::clock`/`crate::playback`.

pub mod activity;
pub mod bands;
pub mod chroma;
pub mod envelope;
pub mod fft;
pub mod onset;
pub mod spectral;
