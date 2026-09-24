//! Manual, human-run verification for R1's done-when (plan §4): play a WAV
//! through the real default output device, print clock position and a few
//! live bus signals as it plays, and demonstrate output-latency
//! compensation actually being applied.
//!
//! Deliberately NOT run by `cargo test` / CI — this opens a real audio
//! device and produces real, audible sound. Run it yourself:
//!
//! ```sh
//! cargo run -p hyst-audio --example play -- path/to/file.wav [latency_ms]
//! ```
//!
//! The WAV's sample rate must match your default output device's rate
//! (resampling isn't implemented yet, see `PlaybackError::SampleRateMismatch`).

use std::time::Duration;

use hyst_audio::{Playback, WavSource};

fn main() {
    let mut args = std::env::args().skip(1);
    let path = match args.next() {
        Some(p) => p,
        None => {
            eprintln!("usage: play <file.wav> [latency_ms]");
            std::process::exit(1);
        }
    };
    let latency_ms: f32 = args.next().and_then(|s| s.parse().ok()).unwrap_or(0.0);

    let source = WavSource::load(&path).expect("failed to load WAV");
    println!(
        "loaded {} ({} Hz, {} ch, {:.1}s)",
        path,
        source.sample_rate,
        source.channels,
        source.duration_secs()
    );

    // Generous capacity ceiling (0.5s worth of frames) so latency_ms below
    // (or anything a human types interactively later) has real headroom.
    let capacity_frames = (source.sample_rate as f32 * 0.5) as usize;
    let playback = Playback::new(source, capacity_frames).expect("failed to start playback");
    playback.set_output_latency_ms(latency_ms);
    println!("output latency set to {latency_ms} ms");

    for _ in 0..20 {
        std::thread::sleep(Duration::from_millis(500));
        let clock = playback.clock();
        let bus = playback.latest_bus();
        println!(
            "logical={:.2}s audible={:.2}s | energy={:.2} sub={:.2} low={:.2} centroid={:.2} \
             tempo={:.0}bpm conf={:.2} beatPhase={:.2}",
            clock.logical_position_secs(),
            clock.audible_position_secs(),
            bus.energy,
            bus.sub,
            bus.low,
            bus.centroid,
            bus.tempo_bpm,
            bus.tempo_confidence,
            bus.beat_phase,
        );
    }
}
