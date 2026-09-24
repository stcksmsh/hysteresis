//! cpal output stream wiring: the app owns audio output (implementation
//! plan §0.3/§4 R1). Ties together `AudioClock` (sample-accurate position),
//! `DelayLine` (deliberate output-latency compensation), and
//! `FeatureExtractor` (live bus signals) into one playing stream.
//!
//! **Real-hardware verification is a flagged, user-run step, not something
//! this session runs automatically** — matching this project's own
//! long-standing discipline (see `docs/LEGACY_TS.md`'s many "not yet
//! verified in a browser" notes) of not silently claiming a check that
//! needs a human ear/eye actually happened. `cargo test` never opens a real
//! output device; see this module's `examples`-style doc for how to
//! actually listen.
//!
//! **Not real-time-safe yet, flagged deliberately**: the callback below
//! allocates (a scratch `Vec` per callback) and runs the full feature
//! extractor synchronously on the audio thread. Fine for this first pass —
//! matches the plan's "port faithfully first, optimize second" — but a
//! glitch-free installation build needs this moved off the audio thread
//! (a lock-free ring buffer to a dedicated analysis thread) before relying
//! on it for a real show. Flagged, not fixed, this session.

use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};

use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use hyst_core::SignalBus;

use crate::clock::AudioClock;
use crate::delay_line::DelayLine;
use crate::features::FeatureExtractor;
use crate::wav_source::WavSource;

#[derive(Debug, thiserror::Error)]
pub enum PlaybackError {
    #[error("no default output device available")]
    NoOutputDevice,
    #[error("failed to query default output config: {0}")]
    DefaultConfig(#[from] cpal::DefaultStreamConfigError),
    #[error(
        "source sample rate {source_hz} Hz doesn't match the output device's {device_hz} Hz \
         (resampling isn't implemented yet — implementation plan §4 R1 doesn't ask for it; \
         flagged as follow-up work, not done here)"
    )]
    SampleRateMismatch { source_hz: u32, device_hz: u32 },
    #[error("unsupported channel mapping: {source_channels} source channel(s) -> {device_channels} device channel(s)")]
    UnsupportedChannelMapping {
        source_channels: u16,
        device_channels: u16,
    },
    #[error("failed to build output stream: {0}")]
    BuildStream(#[from] cpal::BuildStreamError),
    #[error("failed to start output stream: {0}")]
    PlayStream(#[from] cpal::PlayStreamError),
}

/// A playing track: owns the cpal stream (dropping this stops playback),
/// the master clock, and the latest analyzed `SignalBus`.
pub struct Playback {
    clock: Arc<AudioClock>,
    bus: Arc<Mutex<SignalBus>>,
    delay_frames_target: Arc<AtomicUsize>,
    _stream: cpal::Stream, // kept alive; playback stops when this drops
}

impl Playback {
    /// `output_latency_capacity_frames` is the hard ceiling on how much
    /// delay `set_output_latency_ms` can ever apply, fixed here so the audio
    /// callback never reallocates the delay line's buffer mid-stream — a
    /// few hundred ms (e.g. `sample_rate / 2`) comfortably covers any real
    /// servo travel time (plan §4 R1 calls for "a few ms").
    pub fn new(
        source: WavSource,
        output_latency_capacity_frames: usize,
    ) -> Result<Self, PlaybackError> {
        let host = cpal::default_host();
        let device = host
            .default_output_device()
            .ok_or(PlaybackError::NoOutputDevice)?;
        let default_config = device.default_output_config()?;
        let device_channels = default_config.channels();
        let device_sample_rate = default_config.sample_rate().0;

        if device_sample_rate != source.sample_rate {
            return Err(PlaybackError::SampleRateMismatch {
                source_hz: source.sample_rate,
                device_hz: device_sample_rate,
            });
        }
        if source.channels != device_channels && source.channels != 1 && device_channels != 1 {
            return Err(PlaybackError::UnsupportedChannelMapping {
                source_channels: source.channels,
                device_channels,
            });
        }

        let clock = Arc::new(AudioClock::new(device_sample_rate));
        let bus = Arc::new(Mutex::new(SignalBus::default()));
        let delay_frames_target = Arc::new(AtomicUsize::new(0));

        let mut delay_line =
            DelayLine::new(device_channels as usize, output_latency_capacity_frames);
        let mut extractor = FeatureExtractor::new(2048, 512, device_sample_rate as f32);

        let source_channels = source.channels as usize;
        let out_channels = device_channels as usize;
        let source_samples = source.samples;
        let mut read_frame: usize = 0;
        let source_frames = source_samples.len() / source_channels.max(1);

        let stream_clock = clock.clone();
        let stream_bus = bus.clone();
        let stream_delay_target = delay_frames_target.clone();

        let err_fn = |err| eprintln!("hyst-audio output stream error: {err}");

        let stream = device.build_output_stream(
            &default_config.into(),
            move |output: &mut [f32], _info: &cpal::OutputCallbackInfo| {
                let frames = output.len() / out_channels;
                delay_line.set_delay_frames(stream_delay_target.load(Ordering::Relaxed));

                let mut input_buf = vec![0.0f32; frames * out_channels];
                let mut mono_buf = vec![0.0f32; frames];

                for f in 0..frames {
                    if read_frame >= source_frames {
                        break; // past end of track: rest of both buffers stays silence
                    }
                    let frame_start = read_frame * source_channels;
                    let source_frame = &source_samples[frame_start..frame_start + source_channels];
                    let mono = source_frame.iter().sum::<f32>() / source_channels as f32;
                    mono_buf[f] = mono;

                    let out_frame = &mut input_buf[f * out_channels..(f + 1) * out_channels];
                    if source_channels == out_channels {
                        out_frame.copy_from_slice(source_frame);
                    } else if source_channels == 1 {
                        out_frame.fill(source_frame[0]); // mono source -> every device channel
                    } else {
                        out_frame.fill(mono); // multi-channel source -> mono device, downmixed
                    }
                    read_frame += 1;
                }

                stream_clock.advance(frames as u64);
                let hops = extractor.push_samples(&mono_buf);
                if let Some(latest) = hops.into_iter().last() {
                    if let Ok(mut guard) = stream_bus.lock() {
                        *guard = latest;
                    }
                }

                delay_line.process(&input_buf, output);
            },
            err_fn,
            None,
        )?;

        stream.play()?;

        Ok(Self {
            clock,
            bus,
            delay_frames_target,
            _stream: stream,
        })
    }

    pub fn clock(&self) -> Arc<AudioClock> {
        self.clock.clone()
    }

    /// The most recently completed hop's `SignalBus` (live bus signals —
    /// plan §4 R1's third done-when criterion).
    pub fn latest_bus(&self) -> SignalBus {
        self.bus.lock().expect("bus mutex poisoned").clone()
    }

    /// Deliberate output-latency compensation (plan §4 R1): delays what
    /// reaches the speaker without delaying what `AudioClock`/the feature
    /// extractor see, clamped to the capacity given at construction.
    pub fn set_output_latency_ms(&self, ms: f32) {
        let frames = ((ms / 1000.0) * self.clock.sample_rate() as f32).round() as usize;
        self.delay_frames_target.store(frames, Ordering::Relaxed);
        self.clock.set_output_latency_frames(frames as u64);
    }
}
