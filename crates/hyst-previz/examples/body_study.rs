//! Body study tools (docs/BODY_STUDY.md).
//!   body_study sweep OUT.json [N]            sample feasible body vectors (default 2000)
//!   body_study fill SWEEP.json REGIONS.json OUT.json   fill/replace regions, recheck the rule
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
    let mut reasons1 = std::collections::BTreeMap::<String, u64>::new();
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
                                let (f, fail1) = body::feasible_traced(&b, seed);
                                let r = f.map(|(s, score)| {
                                    // total joint motion per joint, degrees, at 60 fps
                                    let fr = body::frames(&score);
                                    let motion = body::joint_motion(&fr).to_vec();
                                    let mv = body::movement(&fr);
                                    (s, body::descriptors(&score), motion, mv)
                                });
                                // why a rejected vector fails at the top of the ladder
                                let why = r.is_none().then(|| {
                                    let top = body::clip(&b, seed, 1.1f64.powi(7));
                                    body::violations(&top).0
                                });
                                (i, b, seed, r, why, fail1)
                            })
                            .collect::<Vec<_>>()
                    })
                })
                .collect::<Vec<_>>()
                .into_iter()
                .flat_map(|h| h.join().unwrap())
                .collect()
        });
        for (i, b, seed, r, why, fail1) in done {
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
                Some((s, desc, motion, mv)) => {
                    hist[(s.ln() / 1.1f64.ln()).round() as usize] += 1;
                    clips.push(serde_json::json!({"b":b,"seed":seed,"s":s,"desc":desc,"motion":motion,"movement":mv,"fail1":fail1}));
                }
                None => {
                    // first rule broken at the top of the ladder; and every rule at stretch 1
                    let top = why.unwrap_or_default();
                    *reasons
                        .entry(top.first().cloned().unwrap_or_default())
                        .or_default() += 1;
                    for k in &fail1 {
                        *reasons1.entry(k.clone()).or_default() += 1;
                    }
                }
            }
        }
    }
    let data = serde_json::json!({
        "sampleSeed": 20261013u64, "params": body::PARAMS, "attempts": attempts,
        "passed": clips.len(), "stretchHistogram": hist, "attemptedByDecile": seen,
        "rejectedByDecile": lost, "rejectReasonAtTopOfLadder": reasons, "rejectRulesAtStretch1": reasons1, "clips": clips
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
/// A region still short has its centre replaced by the candidate farthest from all
/// kept centres (addendum 2), r held, membership recomputed, and is filled again.
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
    let ids = |v: &serde_json::Value| -> Vec<usize> {
        v.as_array()
            .unwrap()
            .iter()
            .map(|x| x.as_u64().unwrap() as usize)
            .collect()
    };
    // rank-normalise a descriptor vector against the 2,000 sorted columns
    let sorted: Vec<Vec<f64>> = rg["sorted"].as_array().unwrap().iter().map(&vec).collect();
    let r = rg["r"].as_f64().unwrap();
    let z = |d: &[f64]| -> Vec<f64> {
        d.iter()
            .enumerate()
            .map(|(i, v)| {
                let below = sorted[i].partition_point(|x| x < v);
                (below as f64 + 0.5) / sorted[i].len() as f64
            })
            .collect()
    };
    let dist = |a: &[f64], b: &[f64]| {
        a.iter()
            .zip(b)
            .map(|(x, y)| (x - y).powi(2))
            .sum::<f64>()
            .sqrt()
    };
    // pool: (rank vector, body, sweep index or None for a made clip)
    let mut pool: Vec<(Vec<f64>, body::Body, Option<usize>)> = sw["clips"]
        .as_array()
        .unwrap()
        .iter()
        .enumerate()
        .map(|(i, c)| {
            (
                z(&vec(&c["desc"])),
                vec(&c["b"]).try_into().unwrap(),
                Some(i),
            )
        })
        .collect();
    let candidates = ids(&rg["candidates"]);
    let mut centres = ids(&rg["centres"]);
    let mut dropped: Vec<usize> = Vec::new();
    let mut filled = [false; 8];
    let (mut added, mut replacements) = (Vec::new(), Vec::new());
    let mut pass = 0u64;
    let members = |pool: &[(Vec<f64>, body::Body, Option<usize>)], centres: &[usize]| {
        let c: Vec<&Vec<f64>> = centres.iter().map(|&i| &pool[i].0).collect();
        let mut m = vec![Vec::new(); 8];
        for (i, p) in pool.iter().enumerate() {
            let k = (0..8)
                .min_by(|&a, &b| dist(&p.0, c[a]).total_cmp(&dist(&p.0, c[b])))
                .unwrap();
            if dist(&p.0, c[k]) <= r {
                m[k].push(i);
            }
        }
        m
    };
    loop {
        let m = members(&pool, &centres);
        let Some(k) = (0..8).find(|&k| m[k].len() < 9) else {
            break;
        };
        if !filled[k] {
            filled[k] = true;
            pass += 1;
            let (mut have, mut tries) = (m[k].len(), 0);
            let centre = pool[centres[k]].0.clone();
            let others: Vec<Vec<f64>> = centres.iter().map(|&i| pool[i].0.clone()).collect();
            while have < 9 && tries < 200 {
                let b = pool[m[k][tries % m[k].len()]].1;
                let seed = 1_000_000 + pass * 1000 + tries as u64;
                tries += 1;
                if let Some((s, score)) = body::feasible(&b, seed) {
                    let desc = body::descriptors(&score);
                    let d = z(&desc);
                    let near = (0..8)
                        .min_by(|&a, &c| dist(&d, &others[a]).total_cmp(&dist(&d, &others[c])))
                        .unwrap();
                    if near == k && dist(&d, &centre) <= r {
                        added.push(serde_json::json!({"region":k,"centre":centres[k],"b":b,"seed":seed,"s":s,"desc":desc}));
                        pool.push((d, b, None));
                        have += 1;
                    }
                }
            }
            println!(
                "region {k} (centre {}): {} members + {} made in {tries} tries",
                centres[k],
                m[k].len(),
                have - m[k].len()
            );
            continue;
        }
        // Still short after its fill: replace the centre.
        dropped.push(centres[k]);
        let kept: Vec<usize> = (0..8).filter(|&i| i != k).map(|i| centres[i]).collect();
        let next = candidates
            .iter()
            .copied()
            .filter(|c| !centres.contains(c) && !dropped.contains(c))
            .max_by(|&a, &b| {
                let f = |c: usize| {
                    kept.iter()
                        .map(|&o| dist(&pool[c].0, &pool[o].0))
                        .fold(f64::MAX, f64::min)
                };
                f(a).total_cmp(&f(b))
            });
        let Some(next) = next else {
            println!("region {k}: no candidate left; the study stops here");
            break;
        };
        let reason = format!("{} members after fill, under 9", m[k].len());
        println!(
            "region {k}: centre {} replaced by {next} ({reason})",
            centres[k]
        );
        replacements
            .push(serde_json::json!({"region":k,"old":centres[k],"new":next,"reason":reason}));
        centres[k] = next;
        filled[k] = false;
    }
    let m = members(&pool, &centres);
    let sweep_members: Vec<Vec<usize>> = m
        .iter()
        .map(|v| v.iter().filter_map(|&i| pool[i].2).collect())
        .collect();
    for (k, v) in m.iter().enumerate() {
        println!(
            "region {k} (centre {}): {} members after fill",
            centres[k],
            v.len()
        );
    }
    let made_members: Vec<usize> = m
        .iter()
        .map(|v| v.iter().filter(|&&i| pool[i].2.is_none()).count())
        .collect();
    // Addendum 3: the quarter rule and r, rechecked on the final centres and members.
    let cc: Vec<f64> = (0..8)
        .flat_map(|a| (a + 1..8).map(move |b| (a, b)))
        .map(|(a, b)| dist(&pool[centres[a]].0, &pool[centres[b]].0))
        .collect();
    let cc_mean = cc.iter().sum::<f64>() / cc.len() as f64;
    let cc_min = cc.iter().copied().fold(f64::MAX, f64::min);
    let quarter = cc_mean / 4.0;
    let within: Vec<f64> = m
        .iter()
        .map(|v| {
            let d: Vec<f64> = (0..v.len())
                .flat_map(|a| (a + 1..v.len()).map(move |b| (a, b)))
                .map(|(a, b)| dist(&pool[v[a]].0, &pool[v[b]].0))
                .collect();
            if d.is_empty() {
                0.0
            } else {
                d.iter().sum::<f64>() / d.len() as f64
            }
        })
        .collect();
    let rule = within.iter().all(|&w| w < quarter) && r <= cc_min;
    println!(
        "final: centre-to-centre min {cc_min:.3} mean {cc_mean:.3}, quarter {quarter:.3}, r {r:.3}"
    );
    for (k, w) in within.iter().enumerate() {
        println!(
            "  region {k}: within {w:.3} {} quarter",
            if *w < quarter { "<" } else { ">=" }
        );
    }
    println!(
        "final region rule: {}",
        if rule {
            "holds"
        } else {
            "BROKEN: the study stops"
        }
    );
    fs::write(
        out,
        serde_json::to_vec(&serde_json::json!({
            "r": r, "centres": centres, "replacements": replacements, "added": added,
            "sweepMembers": sweep_members, "madeMembers": made_members,
            "membersAfter": m.iter().map(Vec::len).collect::<Vec<_>>(),
            "final": {"minCentreDistance": cc_min, "meanCentreDistance": cc_mean,
                      "quarter": quarter, "meanWithinDistance": within, "ruleHolds": rule},
        }))?,
    )
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
    let rep = body::check_2a(&score).map_err(|e| err(format!("clip fails 2a: {e}")))?;
    // Direction reversals: the hand's velocity points against its velocity at the
    // previous frame where it moved faster than 0.05 m/s (slower frames skipped, so
    // a reversal through a stop counts; a gradual turn does not).
    let fr = body::frames(&score);
    let (mut reversals, mut last) = (0, None::<[f64; 3]>);
    for w in fr.windows(2) {
        let v: [f64; 3] = std::array::from_fn(|k| (w[1].1[5][k] - w[0].1[5][k]) * body::FPS);
        if v.iter().map(|x| x * x).sum::<f64>().sqrt() <= 0.05 {
            continue;
        }
        if last.is_some_and(|l| (0..3).map(|k| l[k] * v[k]).sum::<f64>() < 0.0) {
            reversals += 1;
        }
        last = Some(v);
    }
    let [path, side, turn] = rep.movement;
    println!(
        "hand path {path:.2} m, box {side:.2} m, base turn {turn:.0} deg, top hand speed {:.2} m/s, reversals {reversals}",
        rep.max_hand_mps
    );
    let still = body::longest_still(&fr);
    for (j, name) in body::JOINTS.iter().enumerate() {
        println!(
            "  {name:10} total motion {:5.0} deg (floor {:.0}), longest still {:.2} s",
            rep.joint_motion[j],
            body::MIN_JOINT_DEG[j],
            still[j]
        );
    }
    println!("  frame margin {:.0} px", rep.frame_margin_px);
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
    // The study camera (`body::CAMERA_*`, addendum 3): only this copy changes.
    let template = include_str!("../src/ensemble.html");
    let camera = [
        (
            "const target=solo?[0,0,0.3]:",
            format!("const target=solo?[0,0,{}]:", body::CAMERA_TARGET_Z),
        ),
        (
            "const distance=solo?2.1:",
            format!("const distance=solo?{}:", body::CAMERA_DISTANCE),
        ),
    ];
    let mut template = template.to_string();
    for (from, to) in camera {
        if !template.contains(from) {
            return Err(err(format!("template camera changed: {from}")));
        }
        template = template.replacen(from, &to, 1);
    }
    let html = template
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
