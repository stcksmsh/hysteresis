//! cargo run -p hyst-previz --example arm_preview -- output.html [track-url] [sidecar-json-file] [score-json-output]
use std::{env, fs, io, path::PathBuf};

fn main() -> io::Result<()> {
    let raw_args: Vec<_> = env::args_os().skip(1).collect();
    let groove_only = raw_args.iter().any(|arg| arg == "--groove-only");
    let no_reuse = raw_args.iter().any(|arg| arg == "--no-reuse");
    let mut args = raw_args
        .into_iter()
        .filter(|arg| arg != "--groove-only" && arg != "--no-reuse");
    let output = args
        .next()
        .map(PathBuf::from)
        .unwrap_or_else(|| env::temp_dir().join("hysteresis-arm.html"));
    let track_url = args
        .next()
        .map(|s| s.to_string_lossy().into_owned())
        .unwrap_or_default();
    let sidecar_json = match args.next() {
        Some(path) => fs::read_to_string(PathBuf::from(path))?,
        None => String::new(),
    };
    let score = if sidecar_json.is_empty() {
        None
    } else {
        Some(
            hyst_compile::compile_sidecar_json_with_config(
                &sidecar_json,
                hyst_compile::CompileConfig {
                    enable_hits: !groove_only,
                    enable_windups: !groove_only,
                    reuse_repeats: !no_reuse,
                },
            )
            .map_err(io::Error::other)?,
        )
    };
    let html = hyst_previz::render_html_with_score(&track_url, &sidecar_json, score.as_ref())
        .map_err(io::Error::other)?;
    if let Some(path) = args.next() {
        let score = score
            .as_ref()
            .ok_or_else(|| io::Error::other("score export requires sidecar"))?;
        fs::write(path, serde_json::to_vec_pretty(score)?)?;
    }
    fs::write(&output, html)?;
    if let Some(score) = score {
        println!(
            "Compiled {:.2}s song: {} cues",
            score.duration,
            score.cues.len()
        );
    }
    println!("Arm preview written to {}", output.display());
    Ok(())
}
