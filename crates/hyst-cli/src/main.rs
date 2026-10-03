//! Native CPU-only score inspection. No browser, audio device, or hardware output.

use std::fs;
use std::io::{self, Write};
use std::path::Path;

use hyst_audio::{AudioClock, WavSource};
use hyst_compile::Score;
use hyst_output::{ChoreographyOutput, ClockPosition};

const USAGE: &str = "usage:\n  hyst score-sample SCORE_JSON SECONDS [SVG_PATH]\n  hyst score-trace SCORE_JSON WAV_PATH [FPS] [LATENCY_MS]\n\nscore-trace is offline sample-clock simulation, not live playback. Redirect NDJSON stdout to save it.";

fn fail(message: impl AsRef<str>) -> Result<(), String> {
    Err(format!("{}\n{USAGE}", message.as_ref()))
}

fn parse_finite(value: &str, label: &str, min: f64, max: f64) -> Result<f64, String> {
    let parsed: f64 = value
        .parse()
        .map_err(|_| format!("{label} must be a number"))?;
    if !parsed.is_finite() || parsed < min || parsed > max {
        return Err(format!("{label} must be finite and in {min}..={max}"));
    }
    Ok(parsed)
}

fn parse_fps(value: &str) -> Result<u32, String> {
    let fps = parse_finite(value, "FPS", 1.0, 240.0)?;
    if fps.fract() != 0.0 {
        return Err("FPS must be a whole number in 1..=240".into());
    }
    Ok(fps as u32)
}

fn load_output(path: &str) -> Result<ChoreographyOutput, String> {
    let json = fs::read_to_string(path).map_err(|e| format!("failed to read score {path}: {e}"))?;
    let score: Score =
        serde_json::from_str(&json).map_err(|e| format!("invalid score JSON {path}: {e}"))?;
    ChoreographyOutput::new(score).map_err(|e| format!("invalid score {path}: {e}"))
}

fn write_json_line(writer: &mut impl Write, value: &impl serde::Serialize) -> Result<bool, String> {
    let line = serde_json::to_string(value).map_err(|e| e.to_string())?;
    match writeln!(writer, "{line}") {
        Ok(()) => Ok(true),
        Err(error) if error.kind() == io::ErrorKind::BrokenPipe => Ok(false),
        Err(error) => Err(format!("stdout write failed: {error}")),
    }
}

fn command_sample(args: &[String]) -> Result<(), String> {
    if !(2..=3).contains(&args.len()) {
        return fail("score-sample requires SCORE_JSON SECONDS [SVG_PATH]");
    }
    let seconds = parse_finite(&args[1], "SECONDS", f64::NEG_INFINITY, f64::INFINITY)?;
    let output = load_output(&args[0])?;
    let frame = output.sample_at(seconds)?;
    if let Some(svg_path) = args.get(2) {
        fs::write(svg_path, hyst_previz::native::render_score_svg(&frame))
            .map_err(|e| format!("failed to write SVG {}: {e}", Path::new(svg_path).display()))?;
    }
    let mut stdout = io::BufWriter::new(io::stdout().lock());
    let _ = write_json_line(&mut stdout, &frame)?;
    match stdout.flush() {
        Ok(()) => {}
        Err(error) if error.kind() == io::ErrorKind::BrokenPipe => {}
        Err(error) => return Err(format!("stdout flush failed: {error}")),
    }
    Ok(())
}

fn trace_source_frames(total_frames: u64, sample_rate: u32, fps: u32) -> Vec<u64> {
    let mut positions = vec![0];
    let numerator = u64::from(sample_rate);
    let denominator = u64::from(fps);
    let mut index = 1_u64;
    loop {
        let frame = (index.saturating_mul(numerator) + denominator / 2) / denominator;
        if frame >= total_frames {
            break;
        }
        if frame > *positions.last().unwrap() {
            positions.push(frame);
        }
        index += 1;
    }
    if *positions.last().unwrap() != total_frames {
        positions.push(total_frames);
    }
    positions
}

fn command_trace(args: &[String]) -> Result<(), String> {
    if !(2..=4).contains(&args.len()) {
        return fail("score-trace requires SCORE_JSON WAV_PATH [FPS] [LATENCY_MS]");
    }
    let fps = match args.get(2) {
        Some(value) => parse_fps(value)?,
        None => 30,
    };
    let latency_ms = match args.get(3) {
        Some(value) => parse_finite(value, "LATENCY_MS", 0.0, 5000.0)?,
        None => 0.0,
    };
    let output = load_output(&args[0])?;
    let wav = WavSource::load(&args[1]).map_err(|e| e.to_string())?;
    if wav.sample_rate == 0 || wav.channels == 0 {
        return Err(format!(
            "invalid WAV {}: sample rate and channel count must be nonzero",
            args[1]
        ));
    }
    let source_frames = u64::try_from(wav.samples.len()).map_err(|_| "WAV is too large")?
        / u64::from(wav.channels.max(1));
    let duration = source_frames as f64 / f64::from(wav.sample_rate);
    let tolerance = 1.0 / f64::from(wav.sample_rate) + 1e-6;
    if (output.duration() - duration).abs() > tolerance {
        return Err(format!(
            "score duration {:.9}s does not match WAV duration {:.9}s (tolerance {:.9}s)",
            output.duration(),
            duration,
            tolerance
        ));
    }
    let clock = AudioClock::new(wav.sample_rate);
    clock.set_output_latency_secs(latency_ms / 1000.0);
    let mut previous = 0;
    let mut stdout = io::BufWriter::new(io::stdout().lock());
    for source_frame in trace_source_frames(source_frames, wav.sample_rate, fps) {
        clock.advance(source_frame - previous);
        previous = source_frame;
        let frame = output.sample_clock(&clock, ClockPosition::Audible)?;
        if !write_json_line(&mut stdout, &frame)? {
            return Ok(());
        }
    }
    // Source ended. Tolerated one-sample score/WAV skew plus delayed output tail must both drain.
    let score_frames = (output.duration() * f64::from(wav.sample_rate)).ceil() as u64;
    let tail = clock.output_latency_frames() + score_frames.saturating_sub(source_frames);
    if tail > 0 {
        let mut prior_tail = 0;
        for tail_frame in trace_source_frames(tail, wav.sample_rate, fps)
            .into_iter()
            .skip(1)
        {
            clock.advance(tail_frame - prior_tail);
            prior_tail = tail_frame;
            let frame = output.sample_clock(&clock, ClockPosition::Audible)?;
            if !write_json_line(&mut stdout, &frame)? {
                return Ok(());
            }
        }
    }
    match stdout.flush() {
        Ok(()) => {}
        Err(error) if error.kind() == io::ErrorKind::BrokenPipe => {}
        Err(error) => return Err(format!("stdout flush failed: {error}")),
    }
    Ok(())
}

fn run(args: &[String]) -> Result<(), String> {
    let Some((command, rest)) = args.split_first() else {
        return fail("missing command");
    };
    match command.as_str() {
        "score-sample" => command_sample(rest),
        "score-trace" => command_trace(rest),
        _ => fail(format!("unknown command: {command}")),
    }
}

fn main() {
    let args = std::env::args().skip(1).collect::<Vec<_>>();
    if matches!(args.first().map(String::as_str), Some("--help" | "-h")) {
        println!("{USAGE}");
        return;
    }
    if let Err(error) = run(&args) {
        eprintln!("hyst: {error}");
        std::process::exit(2);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn parser_rejects_nan_and_invalid_fps() {
        assert!(parse_finite("NaN", "SECONDS", f64::NEG_INFINITY, f64::INFINITY).is_err());
        assert!(parse_fps("-0.01").is_err());
        assert!(parse_fps("30.5").is_err());
        assert!(parse_fps("241").is_err());
    }
    #[test]
    fn source_frame_grid_is_monotonic_and_includes_exact_endpoint() {
        assert_eq!(trace_source_frames(10, 10, 3), vec![0, 3, 7, 10]);
        assert_eq!(trace_source_frames(1, 48_000, 30), vec![0, 1]);
    }
    #[test]
    fn no_args_and_bad_commands_are_errors() {
        assert!(run(&[]).is_err());
        assert!(run(&["nope".into()]).is_err());
    }

    #[test]
    fn score_inputs_reject_malformed_and_nan_and_svg_escapes_metadata() {
        let root = std::env::temp_dir().join(format!("hyst-cli-test-{}", std::process::id()));
        let score_path = root.with_extension("score.json");
        let svg_path = root.with_extension("svg");
        fs::write(&score_path, "not json").unwrap();
        assert!(command_sample(&[score_path.display().to_string(), "0".into()]).is_err());
        assert!(command_sample(&[score_path.display().to_string(), "NaN".into()]).is_err());
        let score = Score {
            duration: 1.0,
            limits: hyst_compile::JointLimits::default(),
            cues: vec![hyst_compile::Cue {
                start: 0.0,
                end: 1.0,
                gesture: "<safe>".into(),
                reason: "fixture".into(),
                energy: 0.5,
                accent: 0.25,
                arrival_anchor: None,
                knots: vec![
                    hyst_compile::Knot {
                        time: 0.0,
                        phase: "start".into(),
                        joints: [105.0, -65.0, -20.0],
                        velocity: [0.0; 3],
                        acceleration: [0.0; 3],
                    },
                    hyst_compile::Knot {
                        time: 1.0,
                        phase: "end".into(),
                        joints: [105.0, -65.0, -20.0],
                        velocity: [0.0; 3],
                        acceleration: [0.0; 3],
                    },
                ],
            }],
        };
        fs::write(&score_path, serde_json::to_string(&score).unwrap()).unwrap();
        let output = load_output(&score_path.display().to_string()).unwrap();
        let frame = output.sample_at(-1.0).unwrap();
        fs::write(&svg_path, hyst_previz::native::render_score_svg(&frame)).unwrap();
        let svg = fs::read_to_string(svg_path).unwrap();
        assert!(svg.contains("&lt;safe&gt;"));
    }
}
