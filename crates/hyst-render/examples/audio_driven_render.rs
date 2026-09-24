//! R2 item 5: drive the render pipeline from real audio, not just static
//! uniforms. Loads a real WAV via `hyst_audio::WavSource`, runs it through
//! `hyst_audio::FeatureExtractor` to get real `SignalBus` hops (no realtime
//! playback needed — just push samples through), maps a couple of signals
//! onto visual params (`energy` -> bloom strength, `sub` -> memory-field
//! decay/flow strength), renders a few seconds of frames, and — if `ffmpeg`
//! is on `PATH` — encodes them into a short mp4 under `test-output/`
//! (gitignored; not a committed artifact).
//!
//! Run: `cargo run -p hyst-render --example audio_driven_render -- <path/to.wav>`
//! (defaults to `~/Music/Singles/Published/hysteresis/hysteresis.wav` if no
//! path is given — a real track on this machine, used to verify this once).

use std::io::Write;
use std::path::PathBuf;

use hyst_audio::{FeatureExtractor, WavSource};
use hyst_render::passes::beam::Segment;
use hyst_render::passes::julia::JuliaDriver;
use hyst_render::passes::memory_field::MemoryFieldParams;
use hyst_render::{FrameParams, GpuContext, Renderer};

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

    // Downmix to mono for the feature extractor (stereo placement/pan isn't
    // ported in hyst-audio yet — see its own module doc).
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

    // `JULIA_OUT_DIR` mirrors the sibling Mandelbulb demo's `MANDELBULB_OUT_DIR`
    // escape hatch — lets a concurrent render dodge sharing `test-output/`'s
    // frame filenames with another in-flight render of this same example.
    let out_dir = std::env::var_os("JULIA_OUT_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("test-output"));
    std::fs::create_dir_all(&out_dir).expect("create test-output dir");

    let ctx = GpuContext::new_blocking().expect("no GPU adapter available — cannot render");
    let mut renderer = Renderer::new(&ctx, WIDTH, HEIGHT);

    let mut hop_count = 0usize;
    let mut frame_index = 0usize;
    let mut t = 0.0f32;
    let dt = 1.0 / FPS;
    // hyst-audio's SignalBus.beat_pulse isn't computed yet (R1 deferred it —
    // see AGENTS.md); a decaying pulse from beat_phase wraparound, local to
    // this demo, is enough to make the beam visibly react to the beat.
    let mut last_beat_phase = 0.0f32;
    let mut beat_pulse = 0.0f32;
    // The Julia substrate's own motion/color now reacts to real audio via
    // a stateful driver (see `hyst_render::passes::julia::JuliaDriver`'s
    // own doc) — replaces the earlier `JuliaNavState::driven_by_time(t)`
    // call, which was a pure function of elapsed time only and never
    // responded to the music at all (user feedback: "too static... doesn't
    // evolve or react to music").
    let mut julia_driver = JuliaDriver::new();

    // Feed the whole track's samples through in HOP_SIZE-sized pushes so
    // `push_samples` yields exactly one SignalBus per hop, then render every
    // `hop_stride`-th hop as a video frame until we have enough for
    // DURATION_SECS at FPS.
    'outer: for chunk in mono.chunks(HOP_SIZE) {
        let buses = extractor.push_samples(chunk);
        for bus in buses {
            // Gate on tempo_confidence: before a real kick establishes
            // rhythm, BeatTracker's phase free-runs from a default/drifting
            // estimate with low confidence — pulsing on that phase's
            // wraparound anyway reads as the beam guessing wrong and
            // missing, before the real beat ever starts (reported: "tries
            // to glow to the BPM before the kick starts and misses").
            const TEMPO_LOCK_THRESHOLD: f32 = 0.2;
            if bus.tempo_confidence > TEMPO_LOCK_THRESHOLD && bus.beat_phase < last_beat_phase - 0.5
            {
                beat_pulse = 1.0;
            }
            last_beat_phase = bus.beat_phase;
            beat_pulse *= 0.85;

            if hop_count.is_multiple_of(hop_stride) {
                let julia = julia_driver.update(dt, &bus);
                let params = frame_params(&bus, t, beat_pulse, julia, chunk);
                let pixels = renderer
                    .render_frame(&ctx, &params)
                    .expect("render_frame failed");
                write_ppm(
                    &out_dir.join(format!("frame_{frame_index:04}.ppm")),
                    &pixels,
                    WIDTH,
                    HEIGHT,
                );
                frame_index += 1;
                t += dt;
                if frame_index >= total_frames {
                    break 'outer;
                }
            }
            hop_count += 1;
        }
    }
    println!("rendered {frame_index} frames to {}", out_dir.display());

    if which_ffmpeg().is_some() {
        let mp4_path = out_dir.join("audio_driven_render.mp4");
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

fn smoothstep(edge0: f32, edge1: f32, x: f32) -> f32 {
    let t = ((x - edge0) / (edge1 - edge0)).clamp(0.0, 1.0);
    t * t * (3.0 - 2.0 * t)
}

fn which_ffmpeg() -> Option<PathBuf> {
    std::env::var_os("PATH").and_then(|paths| {
        std::env::split_paths(&paths)
            .map(|dir| dir.join("ffmpeg"))
            .find(|full_path| full_path.is_file())
    })
}

/// A 3:2 Lissajous trace (`src/render/worker/scenes/julia/lissajous.ts` —
/// the real design intent for the beam's idle path), phase-drifting with
/// `t`, amplitude breathing with `energy`, base shape kept exactly as
/// before (user: "keep the current lissajous shape").
///
/// **Oscilloscope jitter (Task 4)**: on top of that unchanged base curve,
/// each point gets a small *perpendicular* displacement driven by the
/// track's own real per-hop mono samples (`hop_samples`, the demo's own raw
/// sample chunk for this hop — the most real/available signal, actual
/// waveform values rather than an amplitude-only stand-in), mapped one
/// sample per curve point (nearest-index resample from `HOP_SIZE` samples
/// down to `POINTS`). Perpendicular, not radial or tangential, because
/// that's the actual look of a real oscilloscope trace riding a Lissajous
/// path — the beam wobbles off the ideal curve rather than breathing
/// uniformly or bunching along it. Displacement is the tangent's normal
/// (analytic derivative of the parametric curve, not a finite-difference
/// approximation) scaled by a small fixed amount so the underlying shape
/// stays legible per the user's explicit ask.
fn lissajous_segments(t: f32, energy: f32, hop_samples: &[f32]) -> Vec<Segment> {
    // Segments only, no joint geometry (renderer.rs reverted that — see
    // its comment). High point count is safe and correct here: it just
    // shrinks the bend angle between consecutive segments until a flat
    // cap's notch is genuinely imperceptible, without any bead-chain risk
    // (that risk was specific to round joint discs, not segment density).
    const POINTS: usize = 220;
    // Small enough that the base Lissajous shape stays the dominant, easily
    // recognizable read; large enough that the jitter is actually visible as
    // a real trace wobble rather than disappearing into the beam's own
    // ~0.012 half-width.
    const JITTER_AMP: f32 = 0.03;
    let amp = 0.35 + 0.35 * energy;
    let phase = t * 0.6;
    let point = |theta: f32| -> [f32; 2] {
        [
            amp * (3.0 * theta + phase).sin(),
            amp * (2.0 * theta + phase * 0.5).sin(),
        ]
    };
    // Analytic d/dtheta of `point` above, used to build the curve's own
    // perpendicular (normal) direction at each theta.
    let tangent = |theta: f32| -> [f32; 2] {
        [
            amp * 3.0 * (3.0 * theta + phase).cos(),
            amp * 2.0 * (2.0 * theta + phase * 0.5).cos(),
        ]
    };
    let sample_at = |i: usize| -> f32 {
        if hop_samples.is_empty() {
            0.0
        } else {
            let idx = i * hop_samples.len() / POINTS;
            hop_samples[idx.min(hop_samples.len() - 1)]
        }
    };
    let wobbled = |i: usize, theta: f32| -> [f32; 2] {
        let base = point(theta);
        let tang = tangent(theta);
        let tang_len = (tang[0] * tang[0] + tang[1] * tang[1]).sqrt().max(1e-6);
        let normal = [-tang[1] / tang_len, tang[0] / tang_len];
        let s = sample_at(i);
        [
            base[0] + normal[0] * JITTER_AMP * s,
            base[1] + normal[1] * JITTER_AMP * s,
        ]
    };
    (0..POINTS)
        .map(|i| {
            let theta0 = i as f32 / POINTS as f32 * std::f32::consts::TAU;
            let theta1 = (i + 1) as f32 / POINTS as f32 * std::f32::consts::TAU;
            Segment {
                p0: wobbled(i, theta0),
                p1: wobbled(i + 1, theta1),
            }
        })
        .collect()
}

/// `sub` drives memory-field decay/flow (a bassier moment holds and moves
/// the feedback field more); `energy` drives bloom strength and the beam's
/// Lissajous amplitude; `beat_pulse` drives beam brightness; `julia` is
/// this frame's already-computed `JuliaDriver::update` output (the
/// substrate's own audio-reactive zoom/orbit/color — see that struct's
/// doc). Just enough real-signal wiring to prove the pipeline responds to
/// audio, not a final mix.
fn frame_params(
    bus: &hyst_core::SignalBus,
    t: f32,
    beat_pulse: f32,
    julia: hyst_render::passes::julia::JuliaNavState,
    hop_samples: &[f32],
) -> FrameParams {
    FrameParams {
        julia,
        memory_field: MemoryFieldParams {
            // Lower baseline than the first cut (was 0.85-0.95): trail
            // length scales like 1/(1-decay), so held-near-max decay for a
            // full 45s compounded into an ever-softening blur. 0.55-0.75
            // still gives real memory/smear, just shorter-lived.
            decay: 0.55 + 0.2 * bus.sub,
            aspect: 1.0,
            flow_uv: [t * 0.03, 0.0],
            flow_scale: 2.0,
            flow_strength: 0.01 + 0.05 * bus.sub,
            fold_count: 4.0,
            // "Earned symmetry": user feedback on the first cut (0.15+0.5*
            // energy) was "too frequent" — energy is above the old 0.3
            // threshold a lot of a real track, so symmetry was visible
            // most of the time, not rare/earned. Gate it: near-zero below
            // 0.65 energy, ramping only in the loudest moments.
            mirror_strength: smoothstep(0.65, 0.9, bus.energy) * 0.55,
        },
        persistence_decay: 0.8,
        // Task 3: real luminance-histogram stats taken this session (256x256
        // preview, full pipeline, 90 synthetic frames) found the old
        // threshold=0.3/strength=0.4-1.2/exposure=0.08 combo left a floor of
        // 38/255 (15%) that never dropped for the whole clip — bloom
        // spreading from nearly every pixel above a low threshold, compounded
        // by the memory field's documented fixed ~7x steady-state gain,
        // reads as a persistent haze over everything ("washed/murky").
        // Raising the threshold (fewer, genuinely-bright pixels feed bloom),
        // lowering bloom_strength's baseline, and lowering exposure measured
        // the floor down to 24/255 in the same synthetic probe — a real,
        // measured improvement, not a guess.
        bloom_threshold: 0.55,
        bloom_strength: 0.2 + 0.5 * bus.energy,
        exposure: 0.035,
        beam_segments: lissajous_segments(t, bus.energy, hop_samples),
        beam_color: [1.0, 1.0, 1.0],
        beam_intensity: 0.5 + 2.0 * beat_pulse,
    }
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
