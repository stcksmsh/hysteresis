//! cargo run -p hyst-previz --example ensemble_preview -- output.html track-url sidecar.json [--score score.json] [--rig rig.json] [--groove-only] [--no-reuse] [--zone x0,y0,z0,x1,y1,z1] [--workspace off|rehearsed|schematic] [--body off|layered]
use std::{env, fs, io, path::PathBuf};

use hyst_compile::director::workspace::{BasinKind, Workspace, WorkspaceMode};

fn clock(t: f64) -> String {
    format!("{}:{:04.1}", t as u32 / 60, t % 60.0)
}

/// Basins, the three highest tension peaks (local maxima at least 8 beats
/// apart) and the two largest surprises, to stderr. Times: seconds into the audio.
fn print_workspace(w: &Workspace) {
    for b in &w.basins {
        let kind = match b.kind {
            BasinKind::Recognition => "recognition",
            BasinKind::Lift => "lift",
            BasinKind::Novelty => "novelty",
        };
        eprintln!("basin {} {kind} {:.2}", clock(b.time), b.strength);
    }
    let at = |n: usize| w.beat_zero + n as f64 * w.beat_period;
    let f = &w.field;
    let mut peaks: Vec<(usize, f64)> = (0..f.len())
        .filter(|&n| {
            let (v, before, after) = (
                f[n].tension,
                n.checked_sub(1).map(|i| f[i].tension),
                f.get(n + 1).map(|x| x.tension),
            );
            v > 0.0 && before.is_none_or(|b| v > b) && after.is_none_or(|a| v >= a)
        })
        .map(|n| (n, f[n].tension))
        .collect();
    peaks.sort_by(|a, b| b.1.total_cmp(&a.1));
    let mut kept: Vec<(usize, f64)> = Vec::new();
    for p in peaks {
        if kept.len() < 3 && kept.iter().all(|k| k.0.abs_diff(p.0) >= 8) {
            kept.push(p);
        }
    }
    for (n, v) in kept {
        eprintln!("tension {} {v:.2}", clock(at(n)));
    }
    let mut surprises: Vec<(usize, f64)> =
        f.iter().enumerate().map(|(n, x)| (n, x.surprise)).collect();
    surprises.sort_by(|a, b| b.1.total_cmp(&a.1));
    for (n, v) in surprises.into_iter().take(2) {
        eprintln!("surprise {} {v:.2}", clock(at(n)));
    }
}

fn count_one(score: &hyst_compile::ensemble::EnsembleScore) -> bool {
    score.tracks.len() == 1
}

/// One arm against the body generator's numbers, and how the figure clock ran, on stderr.
fn print_one_arm(traced: &hyst_compile::director::figures::Traced) {
    use hyst_compile::body::{measure, HAND_MPS, JOINTS, JOLT_MPS2, LIMITS};
    let m = measure(&traced.score, 0);
    let over = |v: f64, limit: f64| if v > limit { " OVER" } else { "" };
    eprintln!(
        "body mode {}, {} pass(es)",
        if traced.layered { "layered" } else { "off" },
        traced.passes
    );
    if traced.layered {
        eprintln!(
            "  worst limit ratio after each pass: {:.3?}, last at {:.1} s",
            traced.worst, traced.worst_at
        );
        eprintln!(
            "  validate against the limits: {}",
            traced.invalid.as_deref().unwrap_or("passes")
        );
    }
    for j in 0..5 {
        eprintln!(
            "  {:<10} max speed {:6.1}/{:.0} deg/s{}, max accel {:7.1}/{:.0} deg/s2{}",
            JOINTS[j],
            m.joint_speed[j],
            LIMITS[j].0,
            over(m.joint_speed[j], LIMITS[j].0),
            m.joint_accel[j],
            LIMITS[j].1,
            over(m.joint_accel[j], LIMITS[j].1)
        );
    }
    eprintln!(
        "  hand max {:.3}/{HAND_MPS} m/s{}, jolt max {:.2}/{JOLT_MPS2} m/s2{}, floor margin {:.4} m{}",
        m.max_hand_mps,
        over(m.max_hand_mps, HAND_MPS),
        m.max_jolt_mps2,
        over(m.max_jolt_mps2, JOLT_MPS2),
        m.min_floor_margin_m,
        if m.min_floor_margin_m < 0.0 { " UNDER" } else { "" }
    );
    let lag = traced.lag();
    let worst: Vec<String> = lag
        .worst
        .iter()
        .map(|(t, g)| format!("{:.0}s +{g:.2}", t))
        .collect();
    eprintln!(
        "  clock lag max {:.2} s at {:.1} s, {:.2} s lost in all; largest gains in ten seconds: {}",
        lag.max,
        lag.at,
        lag.lost,
        worst.join(", ")
    );
}

fn usage() -> &'static str {
    "Usage: ensemble_preview OUTPUT.html AUDIO_URL SIDECAR.json [--score OUT.json] [--rig RIG.json] [--groove-only] [--no-reuse] [--zone BOX] [--workspace MODE]\n\
     AUDIO_URL resolves relative to OUTPUT.html; serve both files with a range-capable local server.\n\
     --score PATH     write resolved 3D score for audit\n\
     --rig PATH       use JSON rig geometry and local axes (default illustrative five-axis)\n\
     --groove-only    disable hit accents\n\
     --no-reuse       disable recalled musical material\n\
     --drag GAIN      wrist trails the hand's rise and fall, degrees per m/s (default 240)\n\
     --implement KIND hand object: ball (default, lumpy mirror ball) or disc; a --rig file may carry any other\n\
     --zone BOX       red zone corners in metres, x0,y0,z0,x1,y1,z1 (repeatable)\n\
     --ring N,R       N arms evenly on a circle of radius R metres, their forward toward its centre (6,1.1 is a hexagon)\n\
     --clearance M    arms keep their checked points this far apart, metres (default 0.1)\n\
     --workspace MODE feeling workspace: off (default), rehearsed or schematic; prints basins, tension peaks and surprises to stderr\n\
     --body MODE      off (default) or layered: body vectors from the sidecar's bodyTrack set the quality; one arm only; prints limits and clock lag to stderr\n\
     --figures        accepted and ignored; the figure planner is the only mode\n\
     Audio starts only after Play. Score and arm trajectories resolve offline for deterministic seek."
}

fn main() -> io::Result<()> {
    let mut args = env::args().skip(1);
    let mut positional = Vec::new();
    let mut score_output = None;
    let mut rig_path = None;
    let mut zones = Vec::new();
    let mut implement = None;
    let (mut ring, mut clearance) = ((1usize, 0.0f64), 0.1f64);
    let mut config = hyst_compile::CompileConfig::default();
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "-h" | "--help" => {
                println!("{}", usage());
                return Ok(());
            }
            "--groove-only" => config.enable_hits = false,
            "--body" => {
                config.body = match args.next().as_deref() {
                    Some("off") => hyst_compile::body_track::BodyMode::Off,
                    Some("layered") => hyst_compile::body_track::BodyMode::Layered,
                    _ => return Err(io::Error::other("--body requires off or layered")),
                }
            }
            "--no-reuse" => config.reuse_repeats = false,
            "--drag" => {
                config.wrist_drag_degrees_per_mps = args
                    .next()
                    .and_then(|v| v.parse().ok())
                    .ok_or_else(|| io::Error::other("--drag requires degrees per m/s"))?
            }
            "--implement" => {
                implement = Some(match args.next().as_deref() {
                    Some("disc") => hyst_compile::ensemble::Implement::disc(),
                    Some("ball") => hyst_compile::ensemble::Implement::mirror_ball(),
                    _ => return Err(io::Error::other("--implement requires disc or ball")),
                })
            }
            "--ring" => {
                let raw = args.next().unwrap_or_default();
                let parsed = raw
                    .split_once(',')
                    .and_then(|(n, r)| Some((n.parse().ok()?, r.parse().ok()?)));
                ring = parsed
                    .filter(|(n, r): &(usize, f64)| {
                        (1..=16).contains(n) && r.is_finite() && *r >= 0.0
                    })
                    .ok_or_else(|| io::Error::other("--ring requires N,RADIUS with 1..=16 arms"))?
            }
            "--clearance" => {
                clearance = args
                    .next()
                    .and_then(|v| v.parse().ok())
                    .ok_or_else(|| io::Error::other("--clearance requires metres"))?
            }
            "--workspace" => {
                config.workspace = match args.next().as_deref() {
                    Some("off") => WorkspaceMode::Off,
                    Some("rehearsed") => WorkspaceMode::Rehearsed,
                    Some("schematic") => WorkspaceMode::Schematic,
                    _ => {
                        return Err(io::Error::other(
                            "--workspace requires off, rehearsed or schematic",
                        ))
                    }
                }
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
    let mut rig: hyst_compile::ensemble::Rig = match rig_path {
        Some(path) => serde_json::from_str(&fs::read_to_string(path)?)?,
        None => hyst_compile::ensemble::Rig::illustrative_five_axis(),
    };
    if let Some(implement) = implement {
        rig.implement = implement;
    }
    let arms: Vec<_> = (0..ring.0)
        .map(|k| {
            let degrees = 360.0 * k as f64 / ring.0 as f64;
            let (sin, cos) = degrees.to_radians().sin_cos();
            hyst_compile::director::figures::ArmPlan {
                placement: hyst_compile::ensemble::Placement {
                    origin_m: [ring.1 * cos, ring.1 * sin, 0.0],
                    // Forward is toward the centre; a lone arm keeps yaw 0.
                    yaw_degrees: if ring.0 > 1 { degrees + 180.0 } else { 0.0 },
                },
                mirrored: false,
            }
        })
        .collect();
    let traced = hyst_compile::director::figures::compile_traced(
        &sidecar, config, rig, &zones, &arms, clearance,
    )
    .map_err(io::Error::other)?;
    if let Some(w) = &traced.workspace {
        print_workspace(w);
    }
    if count_one(&traced.score) {
        print_one_arm(&traced);
    }
    let score = traced.score;
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
