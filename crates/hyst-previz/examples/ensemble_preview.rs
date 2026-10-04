//! cargo run -p hyst-previz --example ensemble_preview -- output.html track-url sidecar.json [--score score.json] [--rig rig.json] [--groove-only] [--no-reuse] [--zone x0,y0,z0,x1,y1,z1]
use std::{env, fs, io, path::PathBuf};

fn usage() -> &'static str {
    "Usage: ensemble_preview OUTPUT.html AUDIO_URL SIDECAR.json [--score OUT.json] [--rig RIG.json] [--groove-only] [--no-reuse] [--zone BOX]\n\
     AUDIO_URL resolves relative to OUTPUT.html; serve both files with a range-capable local server.\n\
     --score PATH     write resolved 3D score for audit\n\
     --rig PATH       use JSON rig geometry and local axes (default illustrative five-axis)\n\
     --groove-only    disable hit accents\n\
     --no-reuse       disable recalled musical material\n\
     --drag GAIN      wrist trails the hand's rise and fall, degrees per m/s (default 240)\n\
     --zone BOX       red zone corners in metres, x0,y0,z0,x1,y1,z1 (repeatable)\n\
     --figures        accepted and ignored; the figure planner is the only mode\n\
     Audio starts only after Play. Score and arm trajectories resolve offline for deterministic seek."
}

fn main() -> io::Result<()> {
    let mut args = env::args().skip(1);
    let mut positional = Vec::new();
    let mut score_output = None;
    let mut rig_path = None;
    let mut zones = Vec::new();
    let mut config = hyst_compile::CompileConfig::default();
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "-h" | "--help" => {
                println!("{}", usage());
                return Ok(());
            }
            "--groove-only" => config.enable_hits = false,
            "--no-reuse" => config.reuse_repeats = false,
            "--drag" => {
                config.wrist_drag_degrees_per_mps = args
                    .next()
                    .and_then(|v| v.parse().ok())
                    .ok_or_else(|| io::Error::other("--drag requires degrees per m/s"))?
            }
            "--dejitter" => {
                config.dejitter = args
                    .next()
                    .and_then(|v| v.parse().ok())
                    .ok_or_else(|| io::Error::other("--dejitter requires 0, 1 or 2"))?
            }
            "--flourish" => {
                config.flourish = args
                    .next()
                    .and_then(|v| v.parse().ok())
                    .ok_or_else(|| io::Error::other("--flourish requires 0, 1 or 2"))?
            }
            "--figures" => {}
            "--zone" => {
                let raw = args
                    .next()
                    .ok_or_else(|| io::Error::other("--zone requires x0,y0,z0,x1,y1,z1"))?;
                let v = raw
                    .split(',')
                    .map(str::parse::<f64>)
                    .collect::<Result<Vec<_>, _>>()
                    .map_err(|_| io::Error::other("invalid --zone number"))?;
                if v.len() != 6 {
                    return Err(io::Error::other("--zone requires six numbers"));
                }
                zones.push(hyst_compile::director::figures::Zone {
                    min: [v[0], v[1], v[2]],
                    max: [v[3], v[4], v[5]],
                });
            }
            "--score" => {
                score_output =
                    Some(PathBuf::from(args.next().ok_or_else(|| {
                        io::Error::other("--score requires a path")
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
    let rig = match rig_path {
        Some(path) => serde_json::from_str(&fs::read_to_string(path)?)?,
        None => hyst_compile::ensemble::Rig::illustrative_five_axis(),
    };
    let score = hyst_compile::director::figures::compile_figures(&sidecar, config, rig, &zones)
        .map_err(io::Error::other)?;
    let cues = &score.cues;
    let count = score.tracks.len();
    // One arm stays small at 60 fps and removes visible frame stepping.
    let fps: f64 = 60.0;
    let mut frames = Vec::with_capacity((score.duration * fps).ceil() as usize + 1);
    for i in 0..=(score.duration * fps).ceil() as usize {
        let time = (i as f64 / fps).min(score.duration);
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
        // First and last joint angle per arm: the preview turns the base marks
        // and rolls the hand disc with them.
        let turns: Vec<[f64; 2]> = frame
            .agents
            .iter()
            .map(|agent| {
                let q = &agent.joints_degrees;
                [q[0], q[q.len() - 1]].map(|v| (v * 100.0).round() / 100.0)
            })
            .collect();
        frames.push(serde_json::json!([points, frame.cue_index, turns]));
    }
    let data = serde_json::json!({
        "duration":score.duration,"fps":fps,"frames":frames,"cues":cues,"zones":zones,
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
    if let Some(path) = score_output {
        fs::write(path, serde_json::to_vec_pretty(&score)?)?;
    }
    fs::write(&output, html)?;
    println!(
        "{} {}, {} cues, {:.2}s → {}",
        count,
        if count == 1 { "arm" } else { "arms" },
        cues.len(),
        score.duration,
        output.display()
    );
    Ok(())
}
