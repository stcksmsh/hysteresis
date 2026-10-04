//! Single-arm figure planner. The hand traces phrase-length spatial figures;
//! joints are solved to follow it while every link stays out of red zones.
//!
//! Figure shapes, motif sequences and the class-to-motif table are prototype
//! assumptions awaiting human review, not an approved vocabulary.

use std::collections::HashMap;
use std::f64::consts::{PI, TAU};

use super::*;
use crate::ensemble::{
    fit_tangents, forward_kinematics, AgentTrack, EnsembleScore, JointKnot, Placement, Rig,
};

/// Axis-aligned red zone, metres, world frame. No link may enter it.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub struct Zone {
    pub min: [f64; 3],
    pub max: [f64; 3],
}

const FLOOR: Zone = Zone {
    min: [-1e3; 3],
    max: [1e3, 1e3, 0.0],
};
/// Hard check enforces this clearance; the solver aims for 1.6 times it.
const MARGIN_M: f64 = 0.05;
/// Beats the hand disc takes to turn over at a moment.
const FLIP_BEATS: f64 = 3.0;
/// Hand disc turn per metre of fast hand travel. The user leaned to 280 over
/// 150 and 80 in a blind side-by-side.
const SPIN_DEGREES_PER_METRE: f64 = 280.0;
/// Fastest the figure path carries the hand, m/s. A guess, tuned by eye on one
/// song; moments may exceed it briefly.
const HAND_SPEED_CAP: f64 = 0.8;

/// Hand position in arm-relative shell coordinates:
/// [azimuth -1..1, elevation 0..1, extension 0..1]. `dir` mirrors left/right.
type Shape = fn(f64, f64) -> [f64; 3];
const CENTRE: [f64; 3] = [0.0, 0.45, 0.55];

fn smooth(u: f64) -> f64 {
    let u = u.clamp(0.0, 1.0);
    u * u * (3.0 - 2.0 * u)
}
fn lerp(a: f64, b: f64, u: f64) -> f64 {
    a + (b - a) * u
}

/// Wide circle spiralling inward while the hand pulls in toward the body.
fn gather(u: f64, dir: f64) -> [f64; 3] {
    let s = smooth(u);
    let rho = lerp(1.0, 0.15, s);
    let phi = PI + dir * TAU * u;
    [
        0.9 * rho * phi.cos(),
        0.5 + 0.45 * rho * phi.sin(),
        lerp(0.95, 0.25, s),
    ]
}
fn rise(u: f64, dir: f64) -> [f64; 3] {
    let s = smooth(u);
    [
        0.15 * dir * (PI * u).sin(),
        lerp(0.5, 1.0, s),
        lerp(0.25, 0.7, s),
    ]
}
fn open(u: f64, dir: f64) -> [f64; 3] {
    let s = smooth(u);
    [dir * 0.95 * s, lerp(1.0, 0.45, s), lerp(0.7, 1.0, s)]
}
/// Full-reach overhead arc from the `dir` side to the other.
fn arc(u: f64, dir: f64) -> [f64; 3] {
    [
        dir * 0.95 * (PI * u).cos(),
        0.4 + 0.35 * (PI * u).sin(),
        0.95,
    ]
}
/// Slightly more than a full circle in the floor plane (so it closes even when
/// scaled down), starting at the `dir` side, hand rising and
/// falling twice. Azimuth runs past the back; the base keeps turning.
fn circle(u: f64, dir: f64) -> [f64; 3] {
    [dir * (0.95 - 2.3 * u), 0.45 + 0.3 * (TAU * u).sin(), 0.95]
}
fn sway(u: f64, dir: f64) -> [f64; 3] {
    [
        0.45 * dir * (TAU * u).sin(),
        0.35 + 0.08 * (2.0 * TAU * u).sin(),
        0.6,
    ]
}
fn reach(u: f64, dir: f64) -> [f64; 3] {
    let bell = (PI * u).sin();
    [
        dir * 0.5 * smooth(u),
        lerp(0.3, 0.7, bell),
        0.5 + 0.4 * bell,
    ]
}
fn eight(u: f64, dir: f64) -> [f64; 3] {
    [
        0.7 * dir * (TAU * u).sin(),
        0.5 + 0.3 * (2.0 * TAU * u).sin(),
        0.75,
    ]
}
fn still(_: f64, _: f64) -> [f64; 3] {
    [0.0, 0.25, 0.3]
}

/// (name, shape, beats, direction multiplier)
type Step = (&'static str, Shape, f64, f64);

/// Figure sequence per musical class, an overall size, and how many full turns
/// the whole figure travels around the base per 32 beats. The sequence runs for
/// as long as the class lasts, mirrored on every repeat.
fn motif(class: &str) -> (&'static [Step], f64, f64) {
    const FULL: &[Step] = &[
        ("gather", gather, 6.0, 1.0),
        ("rise", rise, 3.0, 1.0),
        ("open", open, 3.0, 1.0),
        ("circle", circle, 12.0, 1.0),
    ];
    const BASS: &[Step] = &[
        ("arc", arc, 8.0, 1.0),
        ("arc", arc, 8.0, -1.0),
        ("gather", gather, 8.0, 1.0),
        ("rise", rise, 8.0, 1.0),
    ];
    const VOCAL: &[Step] = &[("reach", reach, 8.0, 1.0), ("sway", sway, 8.0, 1.0)];
    const PERC: &[Step] = &[("eight", eight, 8.0, 1.0), ("sway", sway, 8.0, 1.0)];
    const CALM: &[Step] = &[("sway", sway, 16.0, 1.0)];
    const STILL: &[Step] = &[("still", still, 1e9, 1.0)];
    match class {
        "interlocked" => (FULL, 0.9, 0.5),
        "bass-led" => (BASS, 0.85, 1.0),
        "vocal-led" => (VOCAL, 0.7, 0.5),
        "percussive-open" => (PERC, 0.6, 1.0),
        "textural" => (CALM, 0.5, 0.25),
        "silence" => (STILL, 1.0, 0.0),
        _ => (CALM, 0.35, 0.25),
    }
}

struct Instance {
    start: f64,
    end: f64,
    shape: Shape,
    dir: f64,
    scale: f64,
    /// Azimuth offset (1.0 = 180 degrees) that makes this figure start where
    /// the last one ended. Figures are relative to the current facing: no front.
    heading: f64,
    /// Azimuth travelled steadily over the figure, same units.
    turn: f64,
}

pub fn compile_figures(
    json: &str,
    config: CompileConfig,
    rig: Rig,
    zones: &[Zone],
) -> Result<EnsembleScore, String> {
    let data: Evidence = serde_json::from_str(json).map_err(|error| error.to_string())?;
    validate(&data)?;
    rig.validate()?;
    if zones.iter().any(|z| {
        !z.min.iter().chain(&z.max).all(|v| v.is_finite()) || (0..3).any(|i| z.min[i] >= z.max[i])
    }) {
        return Err("zone needs finite min < max".into());
    }
    let zones: Vec<Zone> = zones.iter().copied().chain([FLOOR]).collect();
    let beat = data.musical_memory.beat_period;
    let rate = data.stem_interpretation.envelope_rate;
    let sources: [&Source; 4] =
        std::array::from_fn(|i| &data.stem_interpretation.sources[SOURCES[i]]);

    // Measured transitions, strongest first, at least eight beats apart.
    let mut arrivals: Vec<(f64, f64)> = Vec::new();
    let mut ranked = transitions(&data, &sources);
    ranked.sort_by(|a, b| b.2.total_cmp(&a.2));
    for (time, _, strength) in ranked {
        if arrivals.iter().all(|a| (a.0 - time).abs() >= 8.0 * beat) {
            arrivals.push((time, strength));
        }
    }
    // Spans: those transitions, then phrase edges at least four beats from any edge.
    let mut edges: Vec<f64> = vec![0.0, data.duration];
    edges.extend(arrivals.iter().map(|a| a.0));
    for edge in boundaries(&data, &[]) {
        if edges.iter().all(|e| (e - edge).abs() >= 4.0 * beat) {
            edges.push(edge);
        }
    }
    edges.sort_by(f64::total_cmp);
    let classify = |start: f64, end: f64| {
        let activity = activities(&sources, rate, (start + end) * 0.5, (end - start) * 0.5);
        let rms = if data.rms_envelope.is_empty() {
            sources
                .iter()
                .map(|s| mean(&s.absolute_rms, rate, start, end))
                .sum()
        } else {
            mean(&data.rms_envelope, data.envelope_rate, start, end)
        };
        (character(activity, rms).0, activity)
    };
    // Runs: neighbouring spans of one class dance one continuous sequence.
    let mut runs: Vec<(f64, f64, &str)> = Vec::new();
    for pair in edges.windows(2) {
        let class = classify(pair[0], pair[1]).0;
        match runs.last_mut() {
            Some(run) if run.2 == class => run.1 = pair[1],
            _ => runs.push((pair[0], pair[1], class)),
        }
    }

    // Leader and second: the loudest and next loudest instrument lane on each
    // beat (voice and drums do not compete). A challenger takes over once it
    // has led by 3 dB for four beats, counted from the first of them.
    let mut lanes: Vec<(&str, &Lane)> = data.note_track.as_ref().map_or(Vec::new(), |n| {
        n.lanes
            .iter()
            .filter(|(name, lane)| {
                !matches!(name.as_str(), "vocals" | "drums") && !lane.level_per_beat.is_empty()
            })
            .map(|(name, lane)| (name.as_str(), lane))
            .collect()
    });
    lanes.sort_by_key(|lane| lane.0);
    let mut ranks: Vec<[usize; 2]> = Vec::new();
    if lanes.len() >= 2 {
        let count = lanes
            .iter()
            .map(|l| l.1.level_per_beat.len())
            .min()
            .unwrap();
        let level = |lane: usize, i: usize| {
            let v = &lanes[lane].1.level_per_beat[i.saturating_sub(2)..(i + 3).min(count)];
            v.iter().sum::<f64>() / v.len() as f64
        };
        let best = |i: usize, skip: usize| {
            (0..lanes.len())
                .filter(|l| *l != skip)
                .max_by(|a, b| level(*a, i).total_cmp(&level(*b, i)))
                .unwrap()
        };
        let (mut leader, mut challenger, mut streak) = (best(0, usize::MAX), usize::MAX, 0);
        for i in 0..count {
            let top = best(i, usize::MAX);
            if top != leader && level(top, i) - level(leader, i) > 3.0 {
                streak = if challenger == top { streak + 1 } else { 1 };
                challenger = top;
                if streak >= 4 {
                    leader = top;
                    for (j, rank) in ranks.iter_mut().enumerate().skip(i + 1 - streak) {
                        *rank = [leader, best(j, leader)];
                    }
                    streak = 0;
                }
            } else {
                streak = 0;
            }
            ranks.push([leader, best(i, leader)]);
        }
    }
    let rank_at = |t: f64| {
        let i = ((t - data.musical_memory.beat_zero) / beat).max(0.0) as usize;
        ranks[i.min(ranks.len() - 1)]
    };
    // The leader's note starts, and how much it plays in stabs (separate
    // hits with empty beats between) rather than as a steady stream, 0..1.
    let mut hits: Vec<f64> = Vec::new();
    let mut stabs: Vec<f64> = Vec::new();
    if !ranks.is_empty() {
        let beat_of = |t: f64| ((t - data.musical_memory.beat_zero) / beat).max(0.0) as usize;
        let mut played = vec![vec![false; ranks.len()]; lanes.len()];
        for (index, (_, lane)) in lanes.iter().enumerate() {
            for note in &lane.notes {
                if let Some(cell) = played[index].get_mut(beat_of(note[0])) {
                    *cell = true;
                }
                if rank_at(note[0])[0] == index {
                    hits.push(note[0]);
                }
            }
        }
        hits.sort_by(f64::total_cmp);
        stabs = (0..ranks.len())
            .map(|i| {
                let around = &played[ranks[i][0]][i.saturating_sub(8)..(i + 9).min(ranks.len())];
                let empty = around.iter().filter(|p| !**p).count() as f64 / around.len() as f64;
                ((empty - 0.1) / 0.2).clamp(0.0, 1.0)
            })
            .collect();
    }

    // Swell of the leading lane per beat, [loudness, brightness], each -1..1
    // about its median over the stretch that lane leads (3 dB and 4 semitones
    // are full scale), fading out where it plays stabs. Brightness stands in
    // for the pitch of a flowing line, which cannot be read reliably.
    let mut swell: Vec<[f64; 2]> = Vec::new();
    let bright = |lane: usize| &lanes[lane].1.brightness_per_beat;
    if config.swell > 0.0 && (0..lanes.len()).all(|l| bright(l).len() >= ranks.len()) {
        let mut from = 0;
        while from < ranks.len() {
            let lead = ranks[from][0];
            let to = (from..ranks.len())
                .find(|i| ranks[*i][0] != lead)
                .unwrap_or(ranks.len());
            let part = |series: &[f64], full: f64| -> Vec<f64> {
                let mut sorted = series[from..to].to_vec();
                sorted.sort_by(f64::total_cmp);
                let median = sorted[sorted.len() / 2];
                (from..to)
                    .map(|i| ((series[i] - median) / full).clamp(-1.0, 1.0) * (1.0 - stabs[i]))
                    .collect()
            };
            let loud = part(&lanes[lead].1.level_per_beat, 3.0);
            swell.extend(
                loud.into_iter()
                    .zip(part(bright(lead), 4.0))
                    .map(<[f64; 2]>::from),
            );
            from = to;
        }
    }
    // Smooth in time: beats weighted by a bell one beat wide.
    let swell_at = |t: f64| -> [f64; 2] {
        let x = (t - data.musical_memory.beat_zero) / beat - 0.5;
        let (mut sum, mut total) = ([0.0; 2], 0.0);
        let (first, last) = ((x - 3.0).max(0.0) as usize, (x + 4.0).max(0.0) as usize);
        for (i, at) in swell.iter().enumerate().take(last).skip(first) {
            let w = (-0.5 * (i as f64 - x).powi(2)).exp();
            sum = [sum[0] + w * at[0], sum[1] + w * at[1]];
            total += w;
        }
        sum.map(|v| if total > 0.0 { v / total } else { 0.0 })
    };
    // A figure grows and shrinks with the leader's loudness.
    let sized =
        |scale: f64, t: f64| (scale * (1.0 + 0.35 * config.swell * swell_at(t)[0])).min(1.0);

    // (run start, direction, class) for recall lookups.
    let mut chosen: Vec<(f64, f64, &str)> = Vec::new();
    let mut occurrences: HashMap<&str, usize> = HashMap::new();
    let mut instances: Vec<Instance> = Vec::new();
    let mut cues: Vec<IntentCue> = Vec::new();
    // Scaled shell azimuth where the previous figure ended.
    let mut entry = still(0.0, 1.0)[0];
    for &(start, end, class) in &runs {
        let activity = classify(start, end).1;
        let (sequence, size, travel) = motif(class);
        let n = *occurrences
            .entry(class)
            .and_modify(|n| *n += 1)
            .or_insert(0);
        let (mut first_dir, mut scale) = (if n % 2 == 1 { -1.0 } else { 1.0 }, size);
        let mut recall_from = None;
        if config.reuse_repeats {
            let probe = start + (0.5 * (end - start)).min(8.0 * beat);
            if let Some((earlier, _)) = recall_at(&data, probe) {
                let source = chosen.partition_point(|c| c.0 <= earlier).checked_sub(1);
                if let Some(&(source_start, dir, source_class)) = source.map(|i| &chosen[i]) {
                    if source_class == class {
                        // Returning material: same figures, same side, larger.
                        (first_dir, scale) = (dir, (size * 1.12).min(1.0));
                        recall_from = Some(source_start);
                    }
                }
            }
        }
        chosen.push((start, first_dir, class));
        let mut t = start;
        for (k, &(name, shape, beats, step_dir)) in sequence.iter().cycle().enumerate() {
            let mut stop = t + beats * beat;
            if stop > end - 2.0 * beat {
                stop = end;
            }
            let repeat = k / sequence.len();
            let dir = first_dir * step_dir * if repeat % 2 == 1 { -1.0 } else { 1.0 };
            let heading = entry - scaled(shape(0.0, dir), sized(scale, t))[0];
            let turn = first_dir * travel * 2.0 * (stop - t) / (32.0 * beat);
            instances.push(Instance {
                start: t,
                end: stop,
                shape,
                dir,
                scale,
                heading,
                turn,
            });
            entry = scaled(shape(1.0, dir), sized(scale, stop))[0] + heading + turn;
            cues.push(IntentCue {
                start: t,
                end: stop,
                character: name.into(),
                formation: class.into(),
                source_activity: activity,
                confidence: 0.5,
                recall_from,
                anticipation: None,
                reason: format!(
                    "figure {name} {} · class {class} occurrence {} repeat {} size {scale:.2}{} · stems bass {:.2}, drums {:.2}, vocals {:.2}, other {:.2}",
                    if dir > 0.0 { "right-first" } else { "left-first" },
                    n + 1,
                    repeat + 1,
                    recall_from.map_or(String::new(), |t| format!(" · returns from {t:.1}s")),
                    activity[0], activity[1], activity[2], activity[3],
                ) + &if !ranks.is_empty() {
                    let [lead, second] = rank_at(t);
                    format!(" · leads {}, second {}", lanes[lead].0, lanes[second].0)
                } else {
                    String::new()
                },
                profile: Vec::new(),
            });
            t = stop;
            if t >= end {
                break;
            }
        }
    }

    let shell = |t: f64| -> [f64; 3] {
        let i = instances
            .partition_point(|x| x.end <= t)
            .min(instances.len() - 1);
        let x = &instances[i];
        let u = ((t - x.start) / (x.end - x.start).max(1e-9)).clamp(0.0, 1.0);
        let mut p = scaled((x.shape)(u, x.dir), sized(x.scale, t));
        p[0] += x.heading + x.turn * u;
        p
    };
    let step = beat / 8.0;
    let count = (data.duration / step).ceil() as usize;
    let grid: Vec<f64> = (0..=count)
        .map(|i| (i as f64 * step).min(data.duration))
        .collect();
    // Low-pass the hand path (sigma 0.3 s). This also joins one figure's end
    // to the next one's start. Without it the arm jitters badly (user-verified).
    let raw: Vec<[f64; 3]> = grid.iter().map(|&t| shell(t)).collect();
    let sigma = 0.3 / step;
    let radius = (3.0 * sigma).ceil() as isize;
    let flowing: Vec<[f64; 3]> = (0..raw.len() as isize)
        .map(|i| {
            let (mut sum, mut total) = ([0.0; 3], 0.0);
            for d in -radius..=radius {
                let w = (-0.5 * (d as f64 / sigma).powi(2)).exp();
                let sample = raw[(i + d).clamp(0, raw.len() as isize - 1) as usize];
                for k in 0..3 {
                    sum[k] += w * sample[k];
                }
                total += w;
            }
            sum.map(|v| v / total)
        })
        .collect();
    let flow = |t: f64| -> [f64; 3] {
        let x = (t / step).clamp(0.0, (flowing.len() - 1) as f64);
        let i = (x.floor() as usize).min(flowing.len() - 2);
        std::array::from_fn(|k| lerp(flowing[i][k], flowing[i + 1][k], x - i as f64))
    };

    // Moments: a few measured events the arm prepares for and arrives at
    // exactly. Only section arrivals stop and hold, briefly; melodic flourishes
    // are reached and passed through. Energetic classes use shorter windows.
    struct Moment {
        time: f64,
        /// [elevation, extension]
        pose: [f64; 2],
        strength: f64,
        label: &'static str,
        hold_beats: f64,
        /// Beats to prepare, to arrive, and to release (each).
        span: f64,
        /// True freeze. Only for a cut: dense music, near nothing, dense again.
        /// Every other hold stays alive with small slow movement.
        frozen: bool,
    }
    let mut moments: Vec<Moment> = Vec::new();
    if config.enable_hits {
        let class_at = |t: f64| {
            runs.iter()
                .find(|r| t >= r.0 && t < r.1)
                .map_or("silence", |r| r.2)
        };
        let span_for = |class: &str| {
            if matches!(class, "interlocked" | "bass-led") {
                1.5
            } else {
                2.0
            }
        };
        for &(time, strength) in &arrivals {
            if time > 4.0 * beat && class_at(time + beat) != "silence" {
                moments.push(Moment {
                    time,
                    pose: [0.72, 1.0],
                    strength: 0.7 + 0.3 * strength,
                    label: "arrival",
                    hold_beats: 1.5,
                    span: span_for(class_at(time + beat)),
                    frozen: false,
                });
            }
        }
        // Strongest melodic-stem onset in each stretch of about sixteen beats.
        let flourishes = spaced(onsets(sources[3], rate, 0.25), 16.0 * beat);
        for (n, (time, strength)) in flourishes.into_iter().enumerate() {
            let clash = moments.iter().any(|m| (m.time - time).abs() < 8.0 * beat);
            let inside = class_at(time - 3.0 * beat) != "silence"
                && class_at(time + 3.0 * beat) != "silence";
            if inside && !clash && config.flourish != 1 {
                let soft = config.flourish == 2;
                let pose = if n % 2 == 0 { [0.8, 0.95] } else { [0.15, 1.0] };
                moments.push(Moment {
                    time,
                    pose,
                    strength: (0.5 + 0.5 * strength) * if soft { 0.5 } else { 1.0 },
                    label: "flourish",
                    hold_beats: 0.0,
                    span: if soft { 1.5 } else { 0.75 } * span_for(class_at(time)),
                    frozen: false,
                });
            }
        }
        // Cuts: the mix drops to near nothing for half a beat to four beats
        // between two dense stretches. The arm freezes where it is.
        let level = &data.rms_envelope;
        if !level.is_empty() {
            let frame = data.envelope_rate;
            let mut sorted = level.clone();
            sorted.sort_by(f64::total_cmp);
            let dense = 0.6 * sorted[sorted.len() * 3 / 4];
            let mut i = 0;
            while i < level.len() {
                let around = mean(
                    level,
                    frame,
                    i as f64 / frame - 4.0 * beat,
                    i as f64 / frame,
                );
                if level[i] >= 0.2 * around || around < dense {
                    i += 1;
                    continue;
                }
                let start = i;
                while i < level.len() && level[i] < 0.2 * around {
                    i += 1;
                }
                let (from, to) = (start as f64 / frame, i as f64 / frame);
                let after = mean(level, frame, to, to + 2.0 * beat);
                if (0.5 * beat..=4.0 * beat).contains(&(to - from)) && after >= dense {
                    moments.retain(|m| (m.time - from).abs() >= 6.0 * beat);
                    moments.push(Moment {
                        time: from,
                        pose: [0.0, 0.0],
                        strength: 0.0,
                        label: "cut",
                        hold_beats: (to - from) / beat,
                        span: 0.5,
                        frozen: true,
                    });
                }
            }
        }
        moments.sort_by(|a, b| a.time.total_cmp(&b.time));
    }
    for &Moment { time, label, .. } in &moments {
        let i = cues.partition_point(|c| c.end <= time).min(cues.len() - 1);
        cues[i].anticipation = Some(time);
        cues[i]
            .reason
            .push_str(&format!(" · {label} moment at {time:.2}s"));
    }
    let reach_m: f64 = rig
        .channels
        .iter()
        .map(|c| c.link_m.iter().map(|v| v * v).sum::<f64>().sqrt())
        .sum();
    // Shell coordinates to (hand position in metres, unwrapped azimuth in degrees).
    let place = |p: [f64; 3]| -> ([f64; 3], f64) {
        // Azimuth is unbounded: 1.0 = 180 degrees, turns accumulate.
        let azimuth = (p[0] * 180.0_f64).to_radians();
        let elevation = (10.0 + 70.0 * p[1].clamp(0.0, 1.0)).to_radians();
        let distance = reach_m * (0.38 + 0.54 * p[2].clamp(0.0, 1.0));
        (
            [
                distance * elevation.cos() * azimuth.cos(),
                distance * elevation.cos() * azimuth.sin(),
                distance * elevation.sin(),
            ],
            p[0] * 180.0,
        )
    };
    // Figure clock. Figures wait out a hold instead of running on underneath it
    // (the release then had to chase a path that kept moving), and never carry
    // the hand faster than HAND_SPEED_CAP; lost time is made up at 15% extra pace.
    let mut clock = Vec::with_capacity(grid.len());
    let mut s = 0.0;
    for &t in &grid {
        clock.push(s);
        let held = moments
            .iter()
            .any(|m| (m.time..m.time + m.hold_beats * beat).contains(&t));
        let (from, to) = (place(flow(s)).0, place(flow(s + step)).0);
        let pace = (0..3)
            .map(|k| (to[k] - from[k]).powi(2))
            .sum::<f64>()
            .sqrt()
            / step;
        // While the leader plays stabs the hand travels in pulses along its
        // path: it surges just after each stab and eases between (the user
        // chose this in a blind side-by-side over even travel and over
        // arriving on the stab). A steady leader keeps the even pace.
        let pulse = if stabs.is_empty() {
            1.0
        } else {
            let index = ((t - data.musical_memory.beat_zero) / beat).max(0.0) as usize;
            let since = hits
                .partition_point(|h| *h <= t)
                .checked_sub(1)
                .map(|i| t - hits[i]);
            let bump = since.map_or(0.0, |g| (-g / (0.35 * beat)).exp());
            lerp(1.0, 0.3 + 1.9 * bump, stabs[index.min(stabs.len() - 1)])
        };
        let rate = if held {
            0.0
        } else {
            f64::min(
                pulse * if s < t { 1.15 } else { 1.0 },
                // A pulse may exceed the cap by as much as it exceeds even pace.
                HAND_SPEED_CAP * pulse.clamp(1.0, 1.5) / pace.max(1e-9),
            )
        };
        s = (s + rate * step).min(t + step);
    }
    let waited = |t: f64| -> [f64; 3] {
        let x = (t / step).clamp(0.0, (clock.len() - 1) as f64);
        let i = (x.floor() as usize).min(clock.len() - 2);
        let mut p = flow(lerp(clock[i], clock[i + 1], x - i as f64));
        // The hand rides higher as the leader's line brightens.
        p[1] += 0.3 * config.swell * swell_at(t)[1];
        p
    };
    let hand = |t: f64| -> [f64; 3] {
        let mut p = waited(t);
        for m in &moments {
            let (time, pose, strength, hold, span) =
                (m.time, m.pose, m.strength, m.hold_beats, m.span);
            let tau = (t - time) / beat;
            if !(-2.0 * span..hold + span).contains(&tau) {
                continue;
            }
            // Arrive smoothly, hold (or pass through), release.
            let blend = if tau < -span {
                0.0
            } else if tau < 0.0 {
                smooth((tau + span) / span)
            } else if tau < hold {
                1.0
            } else {
                1.0 - smooth((tau - hold) / span)
            };
            // Prepare by sinking and pulling in, opposite to the arrival.
            let prepare = strength
                * if tau < -span {
                    smooth((tau + 2.0 * span) / span)
                } else {
                    1.0 - blend
                }
                * f64::from(tau < 0.0);
            p[1] -= 0.2 * prepare;
            p[2] -= 0.35 * prepare;
            // A flourish passes through and keeps travelling. An arrival hold
            // stays alive: its pose drifts steadily (slow turn, slow rise, slight
            // give) from before the arrival until after the release, so the hand
            // never comes to rest. Only a cut truly freezes.
            // Strength sets how far the pose departs from the flowing path.
            let base = waited(time);
            let alive = f64::from(hold > 0.0 && !m.frozen);
            let turn = (waited(time + beat)[0] - base[0]).signum();
            let held = [
                if hold > 0.0 {
                    base[0] + alive * (0.2 * (p[0] - base[0]) + 0.06 * turn * tau)
                } else {
                    p[0]
                },
                lerp(base[1], pose[0], strength) + alive * 0.04 * tau,
                lerp(base[2], pose[1], strength) - alive * 0.04 * tau,
            ];
            for k in 0..3 {
                p[k] = lerp(p[k], held[k], blend);
            }
        }
        p
    };
    // Uniform knots keep the quintic well-conditioned; a moment lands within
    // half a knot (about 34 ms at this tempo) of its measured time.
    let times = grid.clone();
    let targets: Vec<([f64; 3], f64)> = times.iter().map(|&t| place(hand(t))).collect();

    let placement = Placement {
        origin_m: [0.0; 3],
        yaw_degrees: 0.0,
    };
    let neutral: Vec<f64> = rig.channels.iter().map(|c| c.neutral_degrees).collect();
    if !clear(&rig, &placement, &zones, &neutral, &neutral)? {
        return Err("rig neutral pose intersects a zone".into());
    }
    let mut knots: Vec<JointKnot> = Vec::with_capacity(times.len());
    let mut held_target: Option<[f64; 3]> = None;
    let mut wanted: Vec<f64> = Vec::new();
    let mut speed = vec![0.0; rig.channels.len()];
    // A last joint that turns about its own link is a tool roll: it moves no
    // point of the chain, so it is driven here, not by the position solver.
    let roll_joint = rig.channels.last().and_then(|c| {
        let along: f64 = (0..3).map(|k| c.axis_local[k] * c.link_m[k]).sum();
        let length = c.link_m.iter().map(|v| v * v).sum::<f64>().sqrt();
        (length > 0.0 && (along.abs() - length).abs() < 1e-9).then_some(rig.channels.len() - 1)
    });
    let mut turned = 0.0;
    for (i, (&time, &(target, facing))) in times.iter().zip(&targets).enumerate() {
        if knots.last().is_some_and(|k| time - k.time < 1e-9) {
            continue;
        }
        let (prior, dt) = knots.last().map_or((neutral.clone(), f64::INFINITY), |k| {
            (k.joints_degrees.clone(), time - k.time)
        });
        // A held hand keeps its solved pose: no settling toward neutral.
        let holding = held_target == Some(target);
        held_target = Some(target);
        if !holding || wanted.is_empty() {
            // Body: the wrist trails the hand's rise and fall like a brush
            // (bends back as the hand rises, forward as it falls). It is only a
            // posture preference, so the other joints make up for it and the
            // hand still reaches its target.
            let (lo, hi) = (i.saturating_sub(4), (i + 4).min(targets.len() - 1));
            let rise = (targets[hi].0[2] - targets[lo].0[2]) / (times[hi] - times[lo]).max(1e-9);
            let lean = (config.wrist_drag_degrees_per_mps * rise).clamp(-45.0, 45.0);
            let wrist = roll_joint.map_or(rig.channels.len() - 1, |r| r - 1);
            wanted = solve(
                &rig,
                &placement,
                &zones,
                target,
                facing,
                &prior,
                (wrist, lean),
            )?;
        }
        if let Some(r) = roll_joint {
            // Flips: the disc turns to show its other face across each moment,
            // in alternating directions.
            let flips = 180.0
                * moments
                    .iter()
                    .enumerate()
                    .map(|(n, m)| {
                        let way = if n % 2 == 0 { 1.0 } else { -1.0 };
                        way * smooth((time - m.time) / (FLIP_BEATS * beat) + 0.5)
                    })
                    .sum::<f64>();
            // Travel: in a fast sweep the disc turns with the distance the hand
            // covers; it rests when the hand is slow. Its direction is the
            // hand's sweep round the base relative to the figure's steady
            // travel over the surrounding four beats, so left and right sweeps
            // turn it opposite ways. (Turning with all travel, one way, read
            // as constant purposeless rotation: user.)
            if i > 0 && dt.is_finite() {
                let (before, bearing) = targets[i - 1];
                let travel = (0..3)
                    .map(|k| (target[k] - before[k]).powi(2))
                    .sum::<f64>()
                    .sqrt();
                let fast = smooth((travel / dt - 0.25) / 0.35);
                let (lo, hi) = (i.saturating_sub(16), (i + 16).min(targets.len() - 1));
                let steady = (targets[hi].1 - targets[lo].1) / (times[hi] - times[lo]);
                let way = (((facing - bearing) / dt - steady) / 30.0).tanh();
                turned += SPIN_DEGREES_PER_METRE * travel * fast * way;
            }
            wanted[r] = flips + turned;
        }
        // Hardware follower: each joint chases its solved angle at a design
        // acceleration and speed a hobby-class servo arm could plausibly follow,
        // braking early enough to stop on target (trapezoid profile). The rig's
        // own limits are the hard validation envelope, reached only when a zone
        // forces an abrupt stop. Both are assumptions until measured on hardware.
        let mut q = wanted.clone();
        if dt.is_finite() {
            for (j, c) in rig.channels.iter().enumerate() {
                let top = 0.75 * c.max_speed_degrees_per_second;
                let accel = 0.1 * c.max_acceleration_degrees_per_second2;
                let gap = wanted[j] - prior[j];
                let brake = (2.0 * accel * gap.abs())
                    .sqrt()
                    .min(top)
                    .min(gap.abs() / dt);
                let v = (gap.signum() * brake).clamp(speed[j] - accel * dt, speed[j] + accel * dt);
                // Never approach a joint end stop faster than it can brake.
                let room = |d: f64| (2.0 * accel * (d - 1.0).max(0.0)).sqrt();
                let v = v.clamp(
                    -room(prior[j] - c.min_degrees),
                    room(c.max_degrees - prior[j]),
                );
                q[j] = (prior[j] + v * dt).clamp(c.min_degrees + 0.5, c.max_degrees - 0.5);
            }
        }
        // The roll moves no link, so zone braking below must not disturb it.
        let rolled = roll_joint.map(|r| (r, q[r]));
        // Zone-aware: a link near a zone moves only as fast as it could brake
        // within its remaining clearance (as for joint end stops above), so the
        // hard check below never has to stop the arm abruptly.
        if dt.is_finite() {
            let before = link_samples(&forward_kinematics(&rig, &placement, &prior)?);
            let after = link_samples(&forward_kinematics(&rig, &placement, &q)?);
            let brake =
                (0.1 * rig.channels[0].max_acceleration_degrees_per_second2).to_radians() * reach_m;
            let mut scale: f64 = 1.0;
            for (a, b) in before.iter().zip(&after) {
                let travel = (0..3).map(|k| (b[k] - a[k]).powi(2)).sum::<f64>().sqrt();
                let limit = (2.0 * brake * (clearance(*a, &zones, MARGIN_M) + 0.005)).sqrt() * dt;
                if travel > limit {
                    scale = scale.min(limit / travel);
                }
            }
            for j in 0..q.len() {
                q[j] = lerp(prior[j], q[j], scale);
            }
        }
        // Hard guarantee: bisect back toward the prior clear pose.
        if !clear(&rig, &placement, &zones, &prior, &q)? {
            let (mut lo, mut hi) = (0.0, 1.0);
            for _ in 0..24 {
                let mid = 0.5 * (lo + hi);
                let trial: Vec<f64> = (0..q.len()).map(|j| lerp(prior[j], q[j], mid)).collect();
                if clear(&rig, &placement, &zones, &prior, &trial)? {
                    lo = mid;
                } else {
                    hi = mid;
                }
            }
            q = (0..q.len()).map(|j| lerp(prior[j], q[j], lo)).collect();
        }
        if let Some((r, angle)) = rolled {
            q[r] = angle;
        }
        if dt.is_finite() {
            for j in 0..q.len() {
                speed[j] = (q[j] - prior[j]) / dt;
            }
        }
        knots.push(JointKnot {
            time,
            velocity_degrees_per_second: vec![0.0; q.len()],
            joints_degrees: q,
        });
    }
    for i in 1..knots.len() - 1 {
        let span = knots[i + 1].time - knots[i - 1].time;
        // An arrival stops dead: no tangent into a held pose.
        let holds = (0..rig.channels.len())
            .all(|j| (knots[i + 1].joints_degrees[j] - knots[i].joints_degrees[j]).abs() < 0.05);
        knots[i].velocity_degrees_per_second = (0..rig.channels.len())
            .map(|j| {
                if holds {
                    0.0
                } else {
                    (knots[i + 1].joints_degrees[j] - knots[i - 1].joints_degrees[j]) / span
                }
            })
            .collect();
    }
    // A score that ends mid-motion keeps its last slope; zero there would ask
    // a moving joint to stop within one knot.
    if let [.., before, last] = &mut knots[..] {
        let dt = last.time - before.time;
        last.velocity_degrees_per_second = (0..rig.channels.len())
            .map(|j| (last.joints_degrees[j] - before.joints_degrees[j]) / dt)
            .collect();
    }
    let mut track = AgentTrack { id: 0, knots };
    fit_tangents(&mut track, &rig)?;
    let score = EnsembleScore {
        duration: data.duration,
        rig,
        placements: vec![placement],
        cues,
        tracks: vec![track],
    };
    score.validate()?;
    Ok(score)
}

fn scaled(p: [f64; 3], scale: f64) -> [f64; 3] {
    std::array::from_fn(|k| CENTRE[k] + (p[k] - CENTRE[k]) * scale)
}

/// Depth of `p` inside the deepest zone grown by `margin`; 0 when outside all.
fn penetration(p: [f64; 3], zones: &[Zone], margin: f64) -> f64 {
    zones
        .iter()
        .map(|z| {
            (0..3)
                .map(|i| (p[i] - z.min[i] + margin).min(z.max[i] + margin - p[i]))
                .fold(f64::INFINITY, f64::min)
        })
        .fold(0.0, f64::max)
}

/// Distance from `p` to the nearest zone grown by `margin`; 0 when inside one.
fn clearance(p: [f64; 3], zones: &[Zone], margin: f64) -> f64 {
    zones
        .iter()
        .map(|z| {
            (0..3)
                .map(|i| {
                    (z.min[i] - margin - p[i])
                        .max(p[i] - z.max[i] - margin)
                        .max(0.0)
                        .powi(2)
                })
                .sum::<f64>()
                .sqrt()
        })
        .fold(f64::INFINITY, f64::min)
}

/// Points checked against zones. The base and its first link sit on the mount
/// surface, so checks start halfway up the second link.
fn link_samples(points: &[[f64; 3]]) -> Vec<[f64; 3]> {
    let mut out = Vec::new();
    for k in 1..points.len() - 1 {
        for f in [0.25, 0.5, 0.75, 1.0] {
            if k > 1 || f >= 0.5 {
                out.push(std::array::from_fn(|i| {
                    lerp(points[k][i], points[k + 1][i], f)
                }));
            }
        }
    }
    out
}

/// True when the straight joint-space move `from` → `to` stays out of all zones.
// ponytail: checks 6 linear blends, not the exact quintic; margin covers the gap.
fn clear(
    rig: &Rig,
    placement: &Placement,
    zones: &[Zone],
    from: &[f64],
    to: &[f64],
) -> Result<bool, String> {
    for u in [1.0 / 6.0, 2.0 / 6.0, 0.5, 4.0 / 6.0, 5.0 / 6.0, 1.0] {
        let q: Vec<f64> = (0..to.len()).map(|j| lerp(from[j], to[j], u)).collect();
        let points = forward_kinematics(rig, placement, &q)?;
        if link_samples(&points)
            .into_iter()
            .any(|p| penetration(p, zones, MARGIN_M) > 0.0)
        {
            return Ok(false);
        }
    }
    Ok(true)
}

/// Damped least squares: hand to target, stay near the prior pose (fluid
/// joints), base facing the hand, others drifting toward neutral, every link
/// sample pushed out of zones.
fn solve(
    rig: &Rig,
    placement: &Placement,
    zones: &[Zone],
    target: [f64; 3],
    facing_degrees: f64,
    prior: &[f64],
    // (joint, degrees): shifts that joint's home angle for this pose.
    lean: (usize, f64),
) -> Result<Vec<f64>, String> {
    let n = rig.channels.len();
    let residual = |q: &[f64]| -> Result<Vec<f64>, String> {
        let points = forward_kinematics(rig, placement, q)?;
        let mut r: Vec<f64> = (0..3).map(|i| points[n][i] - target[i]).collect();
        for j in 0..n {
            r.push(4e-4 * (q[j] - prior[j]));
            // A freely spinning joint has no home angle; it faces the hand, which
            // keeps the arm from flipping over backwards or twisting sideways.
            let c = &rig.channels[j];
            let free = c.max_degrees - c.min_degrees >= 720.0;
            r.push(if free {
                6e-4 * (q[j] - facing_degrees)
            } else {
                3e-4 * (q[j] - c.neutral_degrees - if j == lean.0 { lean.1 } else { 0.0 })
            });
        }
        r.extend(
            link_samples(&points)
                .into_iter()
                .map(|p| 3.0 * penetration(p, zones, 1.6 * MARGIN_M)),
        );
        Ok(r)
    };
    let mut q = prior.to_vec();
    for _ in 0..30 {
        let r0 = residual(&q)?;
        let mut jacobian = vec![vec![0.0; n]; r0.len()];
        for j in 0..n {
            let mut bumped = q.clone();
            bumped[j] += 0.05;
            for (row, r1) in residual(&bumped)?.into_iter().enumerate() {
                jacobian[row][j] = (r1 - r0[row]) / 0.05;
            }
        }
        // Normal equations (JᵀJ + λI) dq = -Jᵀr, Gaussian elimination.
        let mut a = vec![vec![0.0; n + 1]; n];
        for i in 0..n {
            for j in 0..n {
                a[i][j] = jacobian.iter().map(|row| row[i] * row[j]).sum::<f64>();
            }
            a[i][i] += 1e-6;
            a[i][n] = -jacobian
                .iter()
                .zip(&r0)
                .map(|(row, r)| row[i] * r)
                .sum::<f64>();
        }
        for col in 0..n {
            let pivot = (col..n)
                .max_by(|x, y| a[*x][col].abs().total_cmp(&a[*y][col].abs()))
                .unwrap();
            a.swap(col, pivot);
            for row in 0..n {
                if row != col {
                    let f = a[row][col] / a[col][col];
                    let pivot_row = a[col].clone();
                    for (cell, p) in a[row].iter_mut().zip(&pivot_row).skip(col) {
                        *cell -= f * p;
                    }
                }
            }
        }
        let mut moved: f64 = 0.0;
        for (j, c) in rig.channels.iter().enumerate() {
            let dq = (a[j][n] / a[j][j]).clamp(-15.0, 15.0);
            let next = (q[j] + dq).clamp(c.min_degrees, c.max_degrees);
            moved = moved.max((next - q[j]).abs());
            q[j] = next;
        }
        if moved < 1e-3 {
            break;
        }
    }
    Ok(q)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hand_travels_and_no_link_enters_a_red_zone() {
        let json = super::super::tests::fixture(0.7, 0.7);
        let rig = Rig::illustrative_five_axis();
        let free = compile_figures(&json, CompileConfig::default(), rig.clone(), &[]).unwrap();
        // Zone surrounds where the unobstructed hand is furthest to one side.
        let far = (0..=960)
            .map(|i| {
                *free.sample(8.0 * i as f64 / 960.0).unwrap().agents[0]
                    .world_points
                    .last()
                    .unwrap()
            })
            .max_by(|a, b| a[1].abs().total_cmp(&b[1].abs()))
            .unwrap();
        let zone = Zone {
            min: far.map(|v| v - 0.1),
            max: far.map(|v| v + 0.1),
        };
        let blocked = compile_figures(&json, CompileConfig::default(), rig, &[zone]).unwrap();
        let (mut entered_free, mut low, mut high) = (false, f64::INFINITY, f64::NEG_INFINITY);
        for i in 0..=960 {
            let t = 8.0 * i as f64 / 960.0;
            let inside = |score: &EnsembleScore| {
                link_samples(&score.sample(t).unwrap().agents[0].world_points)
                    .into_iter()
                    .any(|p| penetration(p, &[zone, FLOOR], 0.0) > 0.0)
            };
            entered_free |= inside(&free);
            assert!(!inside(&blocked), "link inside zone or floor at {t}");
            let tip = *free.sample(t).unwrap().agents[0]
                .world_points
                .last()
                .unwrap();
            low = low.min(tip[1]);
            high = high.max(tip[1]);
        }
        assert!(entered_free, "fixture zone must obstruct the free path");
        assert!(high - low > 0.4, "hand lateral travel {:.3} m", high - low);
        assert_eq!(free.cues[0].character, "gather");
    }

    #[test]
    fn hand_surges_after_each_stab_of_the_leading_lane() {
        let mut value: serde_json::Value =
            serde_json::from_str(&super::super::tests::fixture(0.7, 0.7)).unwrap();
        // Leader hits every second beat (stabs); a quieter lane plays steadily.
        let stabs: Vec<[f64; 3]> = (0..8).map(|i| [i as f64, 60.0, 1.0]).collect();
        let steady: Vec<[f64; 3]> = (0..16).map(|i| [0.5 * i as f64, 40.0, 1.0]).collect();
        value["noteTrack"] = serde_json::json!({"lanes": {
            "keys": {"notes": stabs, "levelPerBeat": vec![-10.0; 16]},
            "bass": {"notes": steady, "levelPerBeat": vec![-30.0; 16]},
        }});
        let config = CompileConfig {
            enable_hits: false,
            ..CompileConfig::default()
        };
        let rig = Rig::illustrative_five_axis();
        let score = compile_figures(&value.to_string(), config, rig, &[]).unwrap();
        let tip = |t: f64| {
            *score.sample(t).unwrap().agents[0]
                .world_points
                .last()
                .unwrap()
        };
        let travel = |a: f64, b: f64| {
            let (p, q) = (tip(a), tip(b));
            (0..3).map(|k| (p[k] - q[k]).powi(2)).sum::<f64>().sqrt()
        };
        let (mut after, mut before) = (0.0, 0.0);
        for hit in [2.0, 3.0, 4.0, 5.0, 6.0] {
            after += travel(hit + 0.05, hit + 0.3);
            before += travel(hit - 0.3, hit - 0.05);
        }
        assert!(
            after > 1.3 * before,
            "after {after:.3} m, before {before:.3} m"
        );
        assert!(score.cues[0].reason.contains("leads keys"));
    }

    #[test]
    fn only_a_cut_freezes_the_arm() {
        let mut value: serde_json::Value =
            serde_json::from_str(&super::super::tests::fixture(0.7, 0.7)).unwrap();
        // Dense, half a second of nothing, dense again.
        for frame in 80..90 {
            value["rmsEnvelope"][frame] = serde_json::json!(0.0);
        }
        let rig = Rig::illustrative_five_axis();
        let score =
            compile_figures(&value.to_string(), CompileConfig::default(), rig, &[]).unwrap();
        assert!(score.cues.iter().any(|c| c.reason.contains("cut moment")));
        let tip = |t: f64| {
            *score.sample(t).unwrap().agents[0]
                .world_points
                .last()
                .unwrap()
        };
        let moved = |a: f64, b: f64| {
            let (p, q) = (tip(a), tip(b));
            (0..3).map(|k| (p[k] - q[k]).powi(2)).sum::<f64>().sqrt()
        };
        assert!(
            moved(4.25, 4.45) < 0.01,
            "cut moved {:.3} m",
            moved(4.25, 4.45)
        );
        assert!(
            moved(2.25, 2.45) > 0.02,
            "flow moved {:.3} m",
            moved(2.25, 2.45)
        );
    }
}
