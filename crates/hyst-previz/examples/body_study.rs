//! Body study tools (docs/BODY_STUDY.md).
//!   body_study sweep OUT.json [N]            sample feasible body vectors (default 2000)
//!   body_study regions SWEEP.json REGIONS.json OUT.json   regions under addendum 4
//!   body_study ladder b0,..,b14 SEED S       fail unless S is the clip's stretch-ladder value
//!   body_study html OUT.html AUDIO_URL b0,..,b14 SEED S [--score OUT.json]   one clip
use std::{env, fs, io, path::PathBuf};

use hyst_compile::body;
use hyst_compile::body_regions as br;
use hyst_compile::ensemble::EnsembleScore;

fn err(m: impl Into<String>) -> io::Error {
    io::Error::other(m.into())
}

fn sweep(out: PathBuf, want: usize) -> io::Result<()> {
    let threads = std::thread::available_parallelism().map_or(4, |n| n.get());
    let mut clips = Vec::new();
    let (mut attempts, mut next) = (0u64, 0u64);
    // attempted / rejected per parameter decile
    let mut seen = [[0u64; 10]; body::PARAMS.len()];
    let mut lost = [[0u64; 10]; body::PARAMS.len()];
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
                                    let still = body::stillness(&fr);
                                    (s, body::descriptors(&score), motion, mv, still)
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
                Some((s, desc, motion, mv, still)) => {
                    hist[(s.ln() / 1.1f64.ln()).round() as usize] += 1;
                    clips.push(serde_json::json!({"b":b,"seed":seed,"s":s,"desc":desc,"motion":motion,"movement":mv,
                        "stillRun":still.0,"stillShare":still.1,"fail1":fail1}));
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
        "sampleSeed": 20261016u64, "params": body::PARAMS, "attempts": attempts,
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

/// Addendum 4: a region is one body vector (centre sweep clip + 8 clips with fresh
/// seeds passing check 2a), regions separated by 1.5 x their seed spread.
fn regions(sweep: PathBuf, regions: PathBuf, out: PathBuf) -> io::Result<()> {
    use serde_json::{json, Value};
    let sw: Value = serde_json::from_slice(&fs::read(sweep)?)?;
    let rg: Value = serde_json::from_slice(&fs::read(regions)?)?;
    let vec = |v: &Value| -> Vec<f64> {
        v.as_array()
            .unwrap()
            .iter()
            .map(|x| x.as_f64().unwrap())
            .collect()
    };
    let ids = |v: &Value| -> Vec<usize> {
        v.as_array()
            .unwrap()
            .iter()
            .map(|x| x.as_u64().unwrap() as usize)
            .collect()
    };
    let sorted: Vec<Vec<f64>> = rg["sorted"].as_array().unwrap().iter().map(&vec).collect();
    let clips = sw["clips"].as_array().unwrap();
    let points: Vec<Vec<f64>> = clips
        .iter()
        .map(|c| br::rank(&sorted, &vec(&c["desc"])))
        .collect();
    let n = points.len() as f64;
    let mean: Vec<f64> = (0..points[0].len())
        .map(|k| points.iter().map(|p| p[k]).sum::<f64>() / n)
        .collect();
    let candidates = ids(&rg["candidates"]);
    let first = br::initial_centres(&points, &candidates, &mean, 8);
    if first != ids(&rg["centres"]) {
        return Err(err(format!(
            "initial centres {first:?} differ from REGIONS.json"
        )));
    }
    let threads = std::thread::available_parallelism().map_or(4, |n| n.get());
    let build = |c: usize| {
        let b: body::Body = vec(&clips[c]["b"]).try_into().unwrap();
        let seeds: Vec<u64> = br::made_seeds(c).collect();
        let mut made = Vec::new();
        let mut skipped = std::collections::BTreeMap::<String, u64>::new();
        let mut tried = 0usize;
        'outer: for batch in seeds.chunks(threads) {
            let res: Vec<_> = std::thread::scope(|sc| {
                batch
                    .iter()
                    .map(|&seed| {
                        sc.spawn(move || match body::feasible(&b, seed) {
                            Some((s, score)) => Ok((seed, s, body::descriptors(&score))),
                            None => {
                                let top =
                                    body::clip(&b, seed, 1.1f64.powi(body::STRETCH_STEPS as i32));
                                Err(body::violations(&top)
                                    .0
                                    .first()
                                    .cloned()
                                    .unwrap_or_default())
                            }
                        })
                    })
                    .collect::<Vec<_>>()
                    .into_iter()
                    .map(|h| h.join().unwrap())
                    .collect()
            });
            for r in res {
                tried += 1;
                match r {
                    Ok(x) => made.push(x),
                    Err(why) => *skipped.entry(why).or_default() += 1,
                }
                if made.len() == br::CLIPS_PER_REGION - 1 {
                    break 'outer;
                }
            }
        }
        let mut ranks = vec![points[c].clone()];
        let mut list = vec![
            json!({"sweep": c, "b": b, "seed": clips[c]["seed"], "s": clips[c]["s"], "rank": points[c]}),
        ];
        for (seed, s, desc) in made {
            let r = br::rank(&sorted, &desc);
            list.push(
                json!({"sweep": null, "b": b, "seed": seed, "s": s, "desc": desc, "rank": r}),
            );
            ranks.push(r);
        }
        println!(
            "centre {c}: {} clips, w {:.3}, {tried} seeds tried, skipped {skipped:?}",
            ranks.len(),
            br::spread(&ranks)
        );
        let payload = json!({"centre": c, "clips": list, "seedsTried": tried, "skipped": skipped, "w": br::spread(&ranks)});
        (ranks, payload)
    };
    let o = br::select(&points, &candidates, &mean, 8, build);
    let events: Vec<Value> = o
        .events
        .iter()
        .map(|e| match e {
            br::Event::Built { slot, centre, clips } => json!({"built": {"slot": slot, "centre": centre, "clips": clips}}),
            br::Event::Replaced { slot, old, new, pair, ratio } => json!({"replaced": {"slot": slot, "old": old, "new": new,
                "pair": pair, "ratio": ratio,
                "reason": if pair.is_some() { "separation rule broken (worst pair, later-chosen centre)" } else { "under 9 clips after 200 seeds" }}}),
            br::Event::Exhausted { slot } => json!({"exhausted": {"slot": slot}}),
        })
        .collect();
    for e in &events {
        if e.get("built").is_none() {
            println!("{e}");
        }
    }
    let reps = events
        .iter()
        .filter(|e| e.get("replaced").is_some())
        .count();
    let mut result = json!({"factor": br::FACTOR, "seedOrder": br::SEED_ORDER, "initialCentres": first,
        "centres": o.centres, "events": events, "replacements": reps, "holds": o.holds});
    if o.regions.len() == 8 {
        let ranks: Vec<Vec<Vec<f64>>> = o
            .regions
            .iter()
            .map(|r| {
                r["clips"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .map(|c| vec(&c["rank"]))
                    .collect()
            })
            .collect();
        let w: Vec<f64> = ranks.iter().map(|r| br::spread(r)).collect();
        let m: Vec<Vec<f64>> = ranks.iter().map(|r| br::position(r)).collect();
        let pairs: Vec<Value> = br::pairs(&m, &w)
            .into_iter()
            .map(|(i, j, d, r)| json!({"i": i, "j": j, "distance": d, "ratio": r}))
            .collect();
        let smallest = br::pairs(&m, &w)
            .into_iter()
            .map(|p| p.3)
            .fold(f64::MAX, f64::min);
        println!(
            "seed spread w: {}",
            w.iter()
                .map(|x| format!("{x:.3}"))
                .collect::<Vec<_>>()
                .join(" ")
        );
        println!("smallest ratio {smallest:.3} (rule >= {})", br::FACTOR);
        result["w"] = json!(w);
        result["m"] = json!(m);
        result["pairs"] = json!(pairs);
        result["smallestRatio"] = json!(smallest);
    }
    result["regions"] = json!(o.regions);
    println!(
        "{} replacements; separation rule {}",
        reps,
        if o.holds {
            "holds"
        } else {
            "BROKEN: candidates ran out, the study stops"
        }
    );
    fs::write(out, serde_json::to_vec(&result)?)
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
    let b: body::Body = b.try_into().map_err(|_| err("b needs 15 values"))?;
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
    let d = body::descriptors(&score);
    for (j, name) in body::JOINTS.iter().enumerate() {
        println!(
            "  {name:10} mean speed {:5.1} deg/s, total motion {:5.0} deg, longest still {:.2} s",
            d[6 * j],
            rep.joint_motion[j],
            still[j]
        );
    }
    println!(
        "  all joints still: longest {:.2} s, share {:.3}",
        rep.still.0, rep.still.1
    );
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

/// Fails unless `s` is the first stretch on the ladder at which the clip passes 2a.
fn ladder(b: &str, seed: u64, s: f64) -> io::Result<()> {
    let b: Vec<f64> = b
        .split(',')
        .map(|v| v.parse().map_err(|_| err("bad b")))
        .collect::<Result<_, _>>()?;
    let b: body::Body = b.try_into().map_err(|_| err("b needs 15 values"))?;
    match body::feasible(&b, seed) {
        Some((l, _)) if l == s => {
            println!("stretch {s} matches the ladder");
            Ok(())
        }
        Some((l, _)) => Err(err(format!("ladder gives stretch {l}, stored {s}"))),
        None => Err(err("rejected on the ladder")),
    }
}

fn main() -> io::Result<()> {
    let a: Vec<String> = env::args().skip(1).collect();
    match a.iter().map(String::as_str).collect::<Vec<_>>().as_slice() {
        ["sweep", out] => sweep(out.into(), 2000),
        ["sweep", out, n] => sweep(out.into(), n.parse().map_err(|_| err("bad N"))?),
        ["regions", sweep, rg, out] => regions(sweep.into(), rg.into(), out.into()),
        ["ladder", b, seed, s] => ladder(
            b,
            seed.parse().map_err(|_| err("bad seed"))?,
            s.parse().map_err(|_| err("bad s"))?,
        ),
        ["html", out, url, b, seed, s, rest @ ..] => html(
            out.into(), url, b,
            seed.parse().map_err(|_| err("bad seed"))?,
            s.parse().map_err(|_| err("bad s"))?,
            match rest { ["--score", p] => Some(p.into()), [] => None, _ => return Err(err("usage")) },
        ),
        _ => Err(err("usage: body_study sweep OUT.json [N] | html OUT.html AUDIO_URL b0,..,b14 SEED S [--score P]")),
    }
}
