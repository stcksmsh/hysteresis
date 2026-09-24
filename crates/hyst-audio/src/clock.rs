//! The master clock (implementation plan §4 R1): "the app always owns audio
//! output... therefore the app always has sample-accurate playback position
//! and owns the master clock." No TS precedent — the browser package never
//! owned output, it only reacted to whatever `AudioContext`/embed position
//! feed the host supplied.
//!
//! `logical_position_secs()` is the position the *source* is at — the frame
//! most recently pulled from the track and handed to analysis. Because the
//! app owns output, it can deliberately hold audio back before it reaches
//! the speaker (plan §4 R1's "deliberate output-latency compensation" — a
//! lever `SINTEZA_CHOREOGRAPHY.md` §6's servo-travel-time problem needs):
//! `audible_position_secs()` is what a listener actually hears *right now*,
//! always `output_latency_secs()` behind the logical position. A downstream
//! consumer (analysis, a compiled score, a servo command) that acts on the
//! logical position gets a head start on the audio the listener will hear
//! `output_latency` later — this is the whole mechanism, not a separate one.

use std::sync::atomic::{AtomicU64, Ordering};

#[derive(Debug)]
pub struct AudioClock {
    sample_rate: u32,
    frames_written: AtomicU64,
    output_latency_frames: AtomicU64,
}

impl AudioClock {
    pub fn new(sample_rate: u32) -> Self {
        Self {
            sample_rate,
            frames_written: AtomicU64::new(0),
            output_latency_frames: AtomicU64::new(0),
        }
    }

    pub fn sample_rate(&self) -> u32 {
        self.sample_rate
    }

    /// Called by the playback engine as it pulls `frames` frames from the
    /// source, once per audio callback.
    pub fn advance(&self, frames: u64) {
        self.frames_written.fetch_add(frames, Ordering::Relaxed);
    }

    pub fn frames_written(&self) -> u64 {
        self.frames_written.load(Ordering::Relaxed)
    }

    /// Sample-accurate: the exact frame the source is at, not a wall-clock
    /// estimate.
    pub fn logical_position_secs(&self) -> f64 {
        self.frames_written() as f64 / self.sample_rate as f64
    }

    pub fn set_output_latency_frames(&self, frames: u64) {
        self.output_latency_frames.store(frames, Ordering::Relaxed);
    }

    pub fn set_output_latency_secs(&self, secs: f64) {
        self.set_output_latency_frames((secs * self.sample_rate as f64).round() as u64);
    }

    pub fn output_latency_frames(&self) -> u64 {
        self.output_latency_frames.load(Ordering::Relaxed)
    }

    pub fn output_latency_secs(&self) -> f64 {
        self.output_latency_frames() as f64 / self.sample_rate as f64
    }

    /// What's actually reaching the speaker right now — always behind the
    /// logical position by the current output latency. Clamped to 0 (can't
    /// be negative at the very start of playback).
    pub fn audible_position_secs(&self) -> f64 {
        (self.logical_position_secs() - self.output_latency_secs()).max(0.0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn logical_position_is_sample_accurate() {
        let clock = AudioClock::new(48_000);
        clock.advance(48_000);
        assert_eq!(clock.logical_position_secs(), 1.0);
        clock.advance(24_000);
        assert_eq!(clock.logical_position_secs(), 1.5);
    }

    #[test]
    fn audible_position_lags_logical_by_output_latency() {
        let clock = AudioClock::new(48_000);
        clock.set_output_latency_secs(0.05); // 50ms
        clock.advance(48_000); // 1s of source pulled
        assert_eq!(clock.logical_position_secs(), 1.0);
        assert!((clock.audible_position_secs() - 0.95).abs() < 1e-9);
    }

    #[test]
    fn audible_position_never_goes_negative_at_start() {
        let clock = AudioClock::new(48_000);
        clock.set_output_latency_secs(0.05);
        clock.advance(100); // barely started
        assert_eq!(clock.audible_position_secs(), 0.0);
    }
}
