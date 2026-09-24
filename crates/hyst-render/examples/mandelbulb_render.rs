//! Audio-driven proof that the raymarched Mandelbulb pass (`passes::mandelbulb`)
//! renders a real, moving clip reacting to a real track — mirrors
//! `audio_driven_render.rs`'s WAV -> `hyst_audio::FeatureExtractor` ->
//! `SignalBus` pattern, but deliberately does NOT wire through
//! `Renderer`/`FrameParams` (this pass isn't part of the memory-field/bloom/
//! composite/beam pipeline yet, see the crate README for what that would
//! need). Renders straight from `render_mandelbulb`, camera+color driven by
//! [`MandelbulbDiveDriver`] (a stateful, `dt`-integrated driver — see that
//! struct's doc in `passes/mandelbulb.rs` for why) plus real audio signals,
//! and — if `ffmpeg` is on `PATH` — encodes into an mp4 under
//! `test-output/`.
//!
//! Run: `cargo run -p hyst-render --example mandelbulb_render --release -- <path/to.wav>`
//! (release matters — raymarching 8 iterations x up to 440 steps per pixel
//! at the closest dive depth, 9x supersampled, is real per-fragment cost).
//!
//! **This session's rewrite** (previously: "the mandelbulb is bad, we
//! should zoom in deep... also the palette is very bad and illegible"):
//! replaced the old stateless `driven_by_time(t)` + hand-rolled
//! `mandelbulb_state`/`beat_pulse`/`smoothed_energy` local variables with
//! [`MandelbulbDiveDriver::update`] — the driver now owns all of that state
//! itself (dive depth, rotation, hue smoothing, beat-flash decay), advanced
//! once per rendered frame with a real `dt`. This is the same shape
//! `passes::julia::JuliaDriver` already uses; see `passes/mandelbulb.rs`'s
//! module doc for the real depth/epsilon/step-budget numbers behind the new
//! deep dive, and its `palette` doc for the new cosine-gradient multi-hue
//! shading wired to `SignalBus::chroma_root_hue`.
//!
//! **Prior sessions' bugs, still relevant context**: an earlier version of
//! `mandelbulb_state` fed `driven_by_time(t * (0.6 + 0.8 * bus.sub))` —
//! scaling the phase argument itself by a swinging audio value, which made
//! the effective elapsed time non-monotonic frame to frame and read as
//! "rotates/zooms, then snaps back." Fixed by driving phase off `t` alone.
//! A version before that overwrote the whole zoom-dive distance every
//! frame with an unsmoothed `3.2 - 0.9*energy`. Neither mistake is
//! reachable any more now that `MandelbulbDiveDriver` owns the state
//! directly (there is no external `t`/distance override left to get wrong)
//! — but the lesson stands for any future change here: never scale a
//! monotonic phase argument by a non-monotonic audio value; modulate a
//! rate being integrated instead.

use std::io::Write;
use std::path::PathBuf;

use hyst_audio::{FeatureExtractor, WavSource};
use hyst_render::passes::beam::{render_beam, Segment};
use hyst_render::passes::mandelbulb::{render_mandelbulb_perturbed, MandelbulbInfiniteDiveDriver};
use hyst_render::{GpuContext, OffscreenTarget};

const FPS: f32 = 30.0;
const DURATION_SECS: f32 = 90.0;
const WIDTH: u32 = 1024;
const HEIGHT: u32 = 1024;

fn main() {
    let wav_path = std::env::args()
        .nth(1)
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            let home = std::env::var("HOME").expect("HOME must be set to find the default WAV");
            PathBuf::from(home).join("Music/Singles/Published/hysteresis/hysteresis.wav")
        });
    println!("loading {}", wav_path.display());
    let wav = WavSource::load(&wav_path).expect("failed to load WAV");

    let mono: Vec<f32> = if wav.channels == 1 {
        wav.samples.clone()
    } else {
        wav.samples
            .chunks(wav.channels as usize)
            .map(|frame| frame.iter().sum::<f32>() / frame.len() as f32)
            .collect()
    };

    const FFT_SIZE: usize = 2048;
    const HOP_SIZE: usize = 512;
    let mut extractor = FeatureExtractor::new(FFT_SIZE, HOP_SIZE, wav.sample_rate as f32);

    let hops_per_sec = wav.sample_rate as f32 / HOP_SIZE as f32;
    let hop_stride = (hops_per_sec / FPS).round().max(1.0) as usize;
    let total_frames = (DURATION_SECS * FPS) as usize;

    let out_dir = std::env::var_os("MANDELBULB_OUT_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("test-output"));
    std::fs::create_dir_all(&out_dir).expect("create test-output dir");

    let ctx = GpuContext::new_blocking().expect("no GPU adapter available — cannot render");
    let target = OffscreenTarget::new(&ctx, WIDTH, HEIGHT);
    let aspect = WIDTH as f32 / HEIGHT as f32;

    let mut hop_count = 0usize;
    let mut frame_index = 0usize;
    let dt = 1.0 / FPS;
    let mut driver = MandelbulbInfiniteDiveDriver::new();
    println!("initial anchor = {:?}", driver.anchor());

    let start = std::time::Instant::now();
    'outer: for chunk in mono.chunks(HOP_SIZE) {
        let buses = extractor.push_samples(chunk);
        for bus in buses {
            if hop_count.is_multiple_of(hop_stride) {
                let (anchor, state) = driver.update(dt, &bus);
                render_mandelbulb_perturbed(&ctx, &target, anchor, &state, aspect)
                    .expect("render_mandelbulb_perturbed failed");
                render_beam(
                    &ctx,
                    &target,
                    &lissajous_segments(frame_index as f32 * dt, bus.energy),
                    [1.0, 1.0, 1.0],
                    0.5 + 2.0 * state.flash,
                    aspect,
                    0.012,
                )
                .expect("render_beam failed");
                let pixels = target.read_pixels(&ctx).expect("readback failed");
                write_ppm(
                    &out_dir.join(format!("frame_{frame_index:04}.ppm")),
                    &pixels,
                    WIDTH,
                    HEIGHT,
                );
                frame_index += 1;
                if frame_index >= total_frames {
                    break 'outer;
                }
            }
            hop_count += 1;
        }
    }
    let elapsed = start.elapsed();
    println!(
        "rendered {frame_index} frames at {WIDTH}x{HEIGHT} in {:.2}s ({:.1} ms/frame avg) to {}",
        elapsed.as_secs_f32(),
        elapsed.as_secs_f32() * 1000.0 / frame_index.max(1) as f32,
        out_dir.display()
    );
    println!(
        "final anchor = {:?}, rebases fired = {}",
        driver.anchor(),
        driver.rebase_count()
    );

    if which_ffmpeg().is_some() {
        let mp4_path = out_dir.join("mandelbulb_render.mp4");
        let status = std::process::Command::new("ffmpeg")
            .args([
                "-y",
                "-framerate",
                &FPS.to_string(),
                "-i",
                out_dir.join("frame_%04d.ppm").to_str().unwrap(),
                "-pix_fmt",
                "yuv420p",
                mp4_path.to_str().unwrap(),
            ])
            .status()
            .expect("failed to spawn ffmpeg");
        if status.success() {
            println!("encoded video: {}", mp4_path.display());
        } else {
            eprintln!("ffmpeg exited with {status}");
        }
    } else {
        println!(
            "ffmpeg not found on PATH — leaving raw .ppm frames in {}",
            out_dir.display()
        );
    }
}

/// Same Lissajous beam-path helper as `audio_driven_render.rs` (copied, not
/// shared — this is example code, see that file's own version for the
/// Julia-driven demo): a closed Lissajous curve in NDC-ish [-1,1] space,
/// amplitude driven by `energy` so louder passages widen the beam pattern.
fn lissajous_segments(t: f32, energy: f32) -> Vec<Segment> {
    const POINTS: usize = 220;
    let amp = 0.35 + 0.35 * energy;
    let phase = t * 0.6;
    let point = |theta: f32| -> [f32; 2] {
        [
            amp * (3.0 * theta + phase).sin(),
            amp * (2.0 * theta + phase * 0.5).sin(),
        ]
    };
    (0..POINTS)
        .map(|i| {
            let theta0 = i as f32 / POINTS as f32 * std::f32::consts::TAU;
            let theta1 = (i + 1) as f32 / POINTS as f32 * std::f32::consts::TAU;
            Segment {
                p0: point(theta0),
                p1: point(theta1),
            }
        })
        .collect()
}

fn which_ffmpeg() -> Option<PathBuf> {
    std::env::var_os("PATH").and_then(|paths| {
        std::env::split_paths(&paths)
            .map(|dir| dir.join("ffmpeg"))
            .find(|full_path| full_path.is_file())
    })
}

fn write_ppm(path: &std::path::Path, rgba: &[u8], width: u32, height: u32) {
    let mut file = std::fs::File::create(path).expect("create ppm frame");
    write!(file, "P6\n{width} {height}\n255\n").unwrap();
    let mut rgb = Vec::with_capacity((width * height * 3) as usize);
    for px in rgba.chunks(4) {
        rgb.extend_from_slice(&px[0..3]);
    }
    file.write_all(&rgb).unwrap();
}
