//! Body study tools (docs/BODY_STUDY.md).
//!   body_study sweep OUT.json [N]            sample feasible body vectors (default 2000)
//!   body_study html OUT.html AUDIO_URL b0,..,b11 SEED S [--score OUT.json]   one clip
use std::{env, fs, io, path::PathBuf};

use hyst_compile::body;
use hyst_compile::ensemble::EnsembleScore;

fn err(m: impl Into<String>) -> io::Error {
    io::Error::other(m.into())
}

fn sweep(out: PathBuf, want: usize) -> io::Result<()> {
    let threads = std::thread::available_parallelism().map_or(4, |n| n.get());
    let mut clips = Vec::new();
    let (mut attempts, mut next) = (0u64, 0u64);
    // attempted / rejected per parameter decile
    let mut seen = [[0u64; 10]; 12];
    let mut lost = [[0u64; 10]; 12];
    let mut hist = [0u64; 8];
    let mut reasons = std::collections::BTreeMap::<String, u64>::new();
    while clips.len() < want {
        let batch: Vec<u64> = (next..next + 64 * threads as u64).collect();
        next += batch.len() as u64;
        let done: Vec<_> = std::thread::scope(|sc| {
            batch
                .chunks(64)
                .map(|ch| {
                    sc.spawn(move || {
                        ch.iter()
                            .map(|&i| {
                                let (b, seed) = body::draw(i);
                                let r = body::feasible(&b, seed)
                                    .map(|(s, score)| (s, body::descriptors(&score)));
                                // why a rejected vector fails at the top of the ladder
                                let why = r.is_none().then(|| {
                                    let top = body::clip(&b, seed, 1.1f64.powi(7));
                                    body::check_2a(&top).err().unwrap_or_default()
                                });
                                (i, b, seed, r, why)
                            })
                            .collect::<Vec<_>>()
                    })
                })
                .collect::<Vec<_>>()
                .into_iter()
                .flat_map(|h| h.join().unwrap())
                .collect()
        });
        for (i, b, seed, r, why) in done {
            if clips.len() >= want {
                break;
            }
            attempts = i + 1;
            for (p, v) in b.iter().enumerate() {
                let d = ((v * 10.0) as usize).min(9);
                seen[p][d] += 1;
                if r.is_none() {
                    lost[p][d] += 1;
                }
            }
            match r {
                Some((s, desc)) => {
                    hist[(s.ln() / 1.1f64.ln()).round() as usize] += 1;
                    clips.push(serde_json::json!({"b":b,"seed":seed,"s":s,"desc":desc}));
                }
                None => {
                    let key = why.unwrap_or_default();
                    let key = key.split_whitespace().take(2).collect::<Vec<_>>().join(" ");
                    *reasons.entry(key).or_default() += 1;
                }
            }
        }
    }
    let data = serde_json::json!({
        "sampleSeed": 20261013u64, "params": body::PARAMS, "attempts": attempts,
        "passed": clips.len(), "stretchHistogram": hist, "attemptedByDecile": seen,
        "rejectedByDecile": lost, "rejectReasonAtTopOfLadder": reasons, "clips": clips
    });
    fs::write(&out, serde_json::to_vec(&data)?)?;
    println!(
        "{} passed of {attempts} attempts → {}",
        clips.len(),
        out.display()
    );
    Ok(())
}

/// Regions short of 9 members get clips made from their members' body vectors with
/// fresh seeds, kept if they fall inside the region's ball (up to 200 tries each).
fn fill(sweep: PathBuf, regions: PathBuf, out: PathBuf) -> io::Result<()> {
    let sw: serde_json::Value = serde_json::from_slice(&fs::read(sweep)?)?;
    let rg: serde_json::Value = serde_json::from_slice(&fs::read(regions)?)?;
    let vec = |v: &serde_json::Value| -> Vec<f64> {
        v.as_array()
            .unwrap()
            .iter()
            .map(|x| x.as_f64().unwrap())
            .collect()
    };
    let (mu, sd) = (vec(&rg["mean"]), vec(&rg["std"]));
    let r = rg["r"].as_f64().unwrap();
    let clips = sw["clips"].as_array().unwrap();
    let z = |d: &[f64]| -> Vec<f64> {
        d.iter()
            .enumerate()
            .map(|(i, v)| (v - mu[i]) / sd[i])
            .collect()
    };
    let centres: Vec<Vec<f64>> = rg["centres"]
        .as_array()
        .unwrap()
        .iter()
        .map(|c| z(&vec(&clips[c.as_u64().unwrap() as usize]["desc"])))
        .collect();
    let dist = |a: &[f64], b: &[f64]| {
        a.iter()
            .zip(b)
            .map(|(x, y)| (x - y).powi(2))
            .sum::<f64>()
            .sqrt()
    };
    let mut added = Vec::new();
    for (k, reg) in rg["regions"].as_array().unwrap().iter().enumerate() {
        let members: Vec<usize> = reg["members"]
            .as_array()
            .unwrap()
            .iter()
            .map(|m| m.as_u64().unwrap() as usize)
            .collect();
        let mut have = members.len();
        let mut tries = 0;
        while have < 9 && tries < 200 && !members.is_empty() {
            let m = &clips[members[tries % members.len()]];
            let b: body::Body = vec(&m["b"]).try_into().unwrap();
            let seed = 1_000_000 + (k * 1000 + tries) as u64;
            tries += 1;
            if let Some((s, score)) = body::feasible(&b, seed) {
                let d = z(&body::descriptors(&score));
                let near = (0..8)
                    .min_by(|&a, &c| dist(&d, &centres[a]).total_cmp(&dist(&d, &centres[c])))
                    .unwrap();
                if near == k && dist(&d, &centres[k]) <= r {
                    added.push(serde_json::json!({"region":k,"b":b,"seed":seed,"s":s,"desc":body::descriptors(&score)}));
                    have += 1;
                }
            }
        }
        println!(
            "region {k}: {} members + {} made in {tries} tries",
            members.len(),
            have - members.len()
        );
    }
    fs::write(out, serde_json::to_vec(&added)?)
}

fn html(
    out: PathBuf,
    url: &str,
    b: &str,
    seed: u64,
    s: f64,
    score_out: Option<PathBuf>,
) -> io::Result<()> {
    let b: Vec<f64> = b
        .split(',')
        .map(|v| v.parse().map_err(|_| err("bad b")))
        .collect::<Result<_, _>>()?;
    let b: body::Body = b.try_into().map_err(|_| err("b needs 12 values"))?;
    let score: EnsembleScore = body::clip(&b, seed, s);
    body::check_2a(&score).map_err(|e| err(format!("clip fails 2a: {e}")))?;
    let fps = body::FPS;
    let frames: Vec<_> = (0..=(score.duration * fps).round() as usize)
        .map(|i| {
            let f = score.sample(i as f64 / fps).unwrap();
            let a = &f.agents[0];
            let pts: Vec<_> = a
                .world_points
                .iter()
                .map(|p| p.map(|v| (v * 10_000.0).round() / 10_000.0))
                .collect();
            let q = &a.joints_degrees;
            let turns = [q[0], q[q.len() - 1]].map(|v| (v * 100.0).round() / 100.0);
            serde_json::json!([[pts], f.cue_index, [turns]])
        })
        .collect();
    let data = serde_json::json!({
        "duration":score.duration,"fps":fps,"frames":frames,"cues":score.cues,"zones":Vec::<u8>::new(),
        "rig":score.rig,"placements":score.placements
    });
    let esc = |s: String| {
        s.replace('<', "\\u003c")
            .replace('>', "\\u003e")
            .replace('&', "\\u0026")
    };
    let html = include_str!("../src/ensemble.html")
        .replace("__DURATION__", &score.duration.to_string())
        .replace("__TRACK_URL_JSON__", &esc(serde_json::to_string(url)?))
        .replace("__ENSEMBLE_DATA__", &esc(serde_json::to_string(&data)?));
    if let Some(p) = score_out {
        fs::write(p, serde_json::to_vec_pretty(&score)?)?;
    }
    fs::write(&out, html)?;
    println!("1 arm, {:.2}s → {}", score.duration, out.display());
    Ok(())
}

fn main() -> io::Result<()> {
    let a: Vec<String> = env::args().skip(1).collect();
    match a.iter().map(String::as_str).collect::<Vec<_>>().as_slice() {
        ["sweep", out] => sweep(out.into(), 2000),
        ["sweep", out, n] => sweep(out.into(), n.parse().map_err(|_| err("bad N"))?),
        ["fill", sweep, regions, out] => fill(sweep.into(), regions.into(), out.into()),
        ["html", out, url, b, seed, s, rest @ ..] => html(
            out.into(), url, b,
            seed.parse().map_err(|_| err("bad seed"))?,
            s.parse().map_err(|_| err("bad s"))?,
            match rest { ["--score", p] => Some(p.into()), [] => None, _ => return Err(err("usage")) },
        ),
        _ => Err(err("usage: body_study sweep OUT.json [N] | html OUT.html AUDIO_URL b0,..,b11 SEED S [--score P]")),
    }
}
