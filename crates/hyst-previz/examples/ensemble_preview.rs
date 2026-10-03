//! cargo run -p hyst-previz --example ensemble_preview -- output.html track-url sidecar.json [--agents N] [--score score.json] [--interpretation interpretation.json] [--rig rig.json] [--groove-only] [--no-reuse]
use std::{env, fs, io, path::PathBuf};

fn usage() -> &'static str {
    "Usage: ensemble_preview OUTPUT.html AUDIO_URL SIDECAR.json [--agents N] [--score OUT.json] [--interpretation OUT.json] [--rig RIG.json] [--groove-only] [--no-reuse]\n\
     AUDIO_URL resolves relative to OUTPUT.html; serve both files with a range-capable local server.\n\
     --agents N       arm count (default 6; 1..=24)\n\
     --score PATH     write resolved 3D ensemble score for audit\n\
     --interpretation PATH  write musical decision cues for audit\n\
     --rig PATH       use JSON rig geometry and local axes (default illustrative five-axis)\n\
     --groove-only    disable hit and windup accents\n\
     --no-reuse       disable recalled musical material\n\
     Audio starts only after Play. Score and arm trajectories resolve offline for deterministic seek."
}

fn main() -> io::Result<()> {
    let mut args = env::args().skip(1);
    let mut positional = Vec::new();
    let mut count = 6_usize;
    let mut score_output = None;
    let mut interpretation_output = None;
    let mut rig_path = None;
    let mut config = hyst_compile::CompileConfig::default();
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "-h" | "--help" => {
                println!("{}", usage());
                return Ok(());
            }
            "--agents" => {
                let raw = args
                    .next()
                    .ok_or_else(|| io::Error::other("--agents requires a count"))?;
                count = raw
                    .parse()
                    .map_err(|_| io::Error::other("invalid --agents count"))?;
                if !(1..=24).contains(&count) {
                    return Err(io::Error::other("--agents must be 1..=24"));
                }
            }
            "--groove-only" => {
                config.enable_hits = false;
                config.enable_windups = false;
            }
            "--no-reuse" => config.reuse_repeats = false,
            "--score" => {
                score_output =
                    Some(PathBuf::from(args.next().ok_or_else(|| {
                        io::Error::other("--score requires a path")
                    })?))
            }
            "--interpretation" => {
                interpretation_output =
                    Some(PathBuf::from(args.next().ok_or_else(|| {
                        io::Error::other("--interpretation requires a path")
                    })?))
            }
            "--rig" => {
                rig_path = Some(PathBuf::from(
                    args.next()
                        .ok_or_else(|| io::Error::other("--rig requires a path"))?,
                ))
            }
            _ if arg.starts_with('-') => {
                return Err(io::Error::other(format!(
                    "unknown option: {arg}\n{}",
                    usage()
                )))
            }
            _ => positional.push(arg),
        }
    }
    if positional.len() != 3 {
        return Err(io::Error::other(usage()));
    }
    let output = PathBuf::from(&positional[0]);
    let track_url = &positional[1];
    let sidecar = fs::read_to_string(&positional[2])?;
    let interpretation = hyst_compile::director::compile_interpretation(&sidecar, config)
        .map_err(io::Error::other)?;
    let rig = match rig_path {
        Some(path) => serde_json::from_str(&fs::read_to_string(path)?)?,
        None => hyst_compile::ensemble::Rig::illustrative_five_axis(),
    };
    let score = hyst_compile::ensemble::compile_ensemble(&interpretation, rig, count)
        .map_err(io::Error::other)?;
    const FPS: f64 = 30.0;
    let mut frames = Vec::with_capacity((score.duration * FPS).ceil() as usize + 1);
    for i in 0..=(score.duration * FPS).ceil() as usize {
        let time = (i as f64 / FPS).min(score.duration);
        let frame = score.sample(time).map_err(io::Error::other)?;
        // Preview geometry only: 0.1 mm precision keeps standalone HTML manageable.
        let points: Vec<_> = frame
            .agents
            .iter()
            .map(|agent| {
                agent
                    .world_points
                    .iter()
                    .map(|point| point.map(|v| (v * 10_000.0).round() / 10_000.0))
                    .collect::<Vec<_>>()
            })
            .collect();
        frames.push(serde_json::json!([points, frame.cue_index]));
    }
    let data = serde_json::json!({
        "duration":score.duration,"fps":FPS,"frames":frames,"cues":interpretation.cues,
        "rig":score.rig,"placements":score.placements
    });
    let data_json = serde_json::to_string(&data)?
        .replace('<', "\\u003c")
        .replace('>', "\\u003e")
        .replace('&', "\\u0026");
    let url_json = serde_json::to_string(track_url)?
        .replace('<', "\\u003c")
        .replace('>', "\\u003e")
        .replace('&', "\\u0026");
    let html = include_str!("../src/ensemble.html")
        .replace("__DURATION__", &score.duration.to_string())
        .replace("__TRACK_URL_JSON__", &url_json)
        .replace("__ENSEMBLE_DATA__", &data_json);
    if let Some(path) = interpretation_output {
        fs::write(path, serde_json::to_vec_pretty(&interpretation)?)?;
    }
    if let Some(path) = score_output {
        fs::write(path, serde_json::to_vec_pretty(&score)?)?;
    }
    fs::write(&output, html)?;
    println!(
        "{} {}, {} cues, {:.2}s → {}",
        count,
        if count == 1 { "arm" } else { "arms" },
        interpretation.cues.len(),
        score.duration,
        output.display()
    );
    Ok(())
}
