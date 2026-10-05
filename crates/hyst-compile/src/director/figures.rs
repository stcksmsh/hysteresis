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

/// How the arms of an ensemble share one dance.
#[derive(Debug, Clone, Copy, PartialEq)]
enum Formation {
    /// All together.
    Unison,
    /// Every second arm dances the mirror image.
    Mirrored,
    /// Each move starts on one arm and passes round the ring (1-2-3-4-5-6 and
    /// on to 1 with the next move): each arm starts it a fraction of the
    /// move's own length after the last.
    Canon,
    /// Each move starts on one arm and spreads both ways round the ring to the
    /// arm opposite (1, then 2 and 6, then 3 and 5, then 4); the next move
    /// starts there and comes back.
    Ripple,
    /// Opposite arms pair up; the pairs take turns of eight beats.
    Pairs,
    /// Every second arm sits out.
    DropOut,
}

impl Formation {
    /// For arm `a` of `count`, `beats` into the run, during the song's
    /// `index`-th move, which lasts `length` beats: (side: 1 as planned, -1
    /// mirrored; delay in beats; 1 dancing or 0 resting).
    fn part(
        self,
        a: usize,
        count: usize,
        beats: f64,
        index: usize,
        length: f64,
    ) -> (f64, f64, f64) {
        // About a sixth of the move per step (the user: half a second to a
        // second for a move of three), less where more arms would overrun
        // the move; in whole beats, so a late arm still lands on the beat.
        let step = (length / (count as f64).max(6.0)).round().max(1.0);
        let odd = a % 2 == 1;
        let turn = |every: f64, groups: usize| (beats / every) as usize % groups.max(1);
        let on = |dancing: bool| if dancing { 1.0 } else { 0.0 };
        match self {
            Self::Unison => (1.0, 0.0, 1.0),
            Self::Mirrored => (if odd { -1.0 } else { 1.0 }, 0.0, 1.0),
            Self::Canon => (1.0, a as f64 * step, 1.0),
            Self::Ripple => {
                let (out, far) = (a.min(count - a), count / 2);
                let rank = if index % 2 == 1 { far - out } else { out };
                // Half a beat per step, less than the canon's: reversing
                // the order makes the end arms play alternate moves slower
                // and faster, and at the canon's step that was by half, which
                // doubled every accent's acceleration and read as a stutter.
                (1.0, rank as f64 * 0.5, 1.0)
            }
            Self::Pairs => {
                let groups = (count / 2).max(1);
                (1.0, 0.0, on(a % groups == turn(8.0, groups)))
            }
            Self::DropOut => (1.0, 0.0, on(!odd)),
        }
    }
}

/// One arm of an ensemble: where it stands (its forward is its placement's
/// yaw), and whether it always dances the left-right mirror image.
#[derive(Debug, Clone, PartialEq)]
pub struct ArmPlan {
    pub placement: Placement,
    pub mirrored: bool,
}

/// One arm at the origin.
pub fn compile_figures(
    json: &str,
    config: CompileConfig,
    rig: Rig,
    zones: &[Zone],
) -> Result<EnsembleScore, String> {
    let alone = ArmPlan {
        placement: Placement {
            origin_m: [0.0; 3],
            yaw_degrees: 0.0,
        },
        mirrored: false,
    };
    compile_ensemble(json, config, rig, zones, &[alone], 0.0)
}

/// Every arm dances the same figures in its own frame. Each arm treats the
/// others as moving red zones: no checked point of one arm comes within
/// `clearance_m` of a checked point of another (plus the implements' radii).
/// Arms are solved in order at each knot, so earlier arms have right of way.
pub fn compile_ensemble(
    json: &str,
    config: CompileConfig,
    rig: Rig,
    zones: &[Zone],
    arms: &[ArmPlan],
    clearance_m: f64,
) -> Result<EnsembleScore, String> {
    if arms.is_empty() || !(clearance_m.is_finite() && clearance_m >= 0.0) {
        return Err("ensemble needs an arm and a finite clearance >= 0".into());
    }
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
    if (0..lanes.len()).all(|l| bright(l).len() >= ranks.len()) {
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
    // Voice: how far above its usual pitch it sings on each beat, 0..1 (two
    // semitones above the song's median note start it, eight are full). The
    // lane's rough pitch is enough to tell a lifted passage from the rest.
    let mut voice: Vec<f64> = Vec::new();
    if let Some(lane) = data.note_track.as_ref().and_then(|n| n.lanes.get("vocals")) {
        let median = |mut pitches: Vec<f64>| {
            pitches.sort_by(f64::total_cmp);
            pitches.get(pitches.len() / 2).copied()
        };
        if let Some(usual) = median(lane.notes.iter().map(|n| n[1]).collect()) {
            voice = (0..lane.level_per_beat.len())
                .map(|i| {
                    let from = data.musical_memory.beat_zero + i as f64 * beat;
                    let here = lane
                        .notes
                        .iter()
                        .filter(|n| (from..from + beat).contains(&n[0]));
                    median(here.map(|n| n[1]).collect())
                        .map_or(0.0, |p| ((p - usual - 2.0) / 6.0).clamp(0.0, 1.0))
                })
                .collect();
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
    // A figure grows and shrinks with the leader's loudness. The user chose
    // this strength (with the height below) over half of it and over none, on
    // the break's solo and on a strummed verse.
    let sized = |scale: f64, t: f64| (scale * (1.0 + 0.35 * swell_at(t)[0])).min(1.0);

    // (run start, direction, class) for recall lookups.
    let mut chosen: Vec<(f64, f64, &str)> = Vec::new();
    let mut occurrences: HashMap<&str, usize> = HashMap::new();
    let mut instances: Vec<Instance> = Vec::new();
    let mut cues: Vec<IntentCue> = Vec::new();
    // Scaled shell azimuth where the previous figure ended.
    let mut entry = still(0.0, 1.0)[0];
    let mut way = -1.0;
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
        // Each section travels round the base the opposite way to the last
        // (the figures keep their own side). All one way, the base netted 12.5
        // turns over the song: "mostly one direction" (user). Mirroring the
        // figures too was the other extreme; the user asked for the middle.
        if travel > 0.0 {
            way = -way;
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
            let turn = way * travel * 2.0 * (stop - t) / (32.0 * beat);
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
            // Among stabs a flourish lands on a hit that stands out. In a
            // steady stream it lands on an arbitrary note, so there it is slow
            // and soft (blind side-by-side: the sharp one was "too much", and
            // the user picked soft over none).
            let index = ((time - data.musical_memory.beat_zero) / beat).max(0.0) as usize;
            let soft = !stabs.is_empty() && stabs[index.min(stabs.len() - 1)] < 0.5;
            if inside && !clash {
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
    // Ensemble formation of each run, chosen from its class and how often that
    // class has come round. The user: all together looks best, the mirror
    // image is liked too, and a canon or ripple is a flourish, not a way to
    // dance a section. A run shorter than eight beats keeps the formation
    // before it.
    let mut formations: Vec<(f64, Formation)> = Vec::new();
    let mut seen: HashMap<&str, usize> = HashMap::new();
    for &(start, end, class) in &runs {
        let n = *seen.entry(class).and_modify(|n| *n += 1).or_insert(0);
        // Everyone dances nearly all the time (the user found resting arms
        // low in energy and not synchronized enough).
        let formation = match class {
            // Verses in step: mirrored verses stood idle longest and the user
            // found them the worst of mirrored, ripple and unison.
            "interlocked" | "bass-led" | "silence" | "vocal-led" => Formation::Unison,
            "percussive-open" => [Formation::Mirrored, Formation::Unison][n % 2],
            "sparse" => Formation::DropOut,
            _ => Formation::Pairs,
        };
        let short = end - start < 8.0 * beat && !formations.is_empty();
        let formation = if short {
            formations[formations.len() - 1].1
        } else {
            formation
        };
        formations.push((start, formation));
        if arms.len() > 1 {
            for cue in cues
                .iter_mut()
                .filter(|c| c.start >= start && c.start < end)
            {
                cue.reason.push_str(&format!(" · ensemble {formation:?}"));
            }
        }
    }
    // Per move: the move that holds a melodic flourish passes round the ring,
    // as a ripple and a canon in turn. Only its timing changes; the arms keep
    // the sides of the run's formation. Moves under six beats stay together.
    let mut accents: Vec<Option<Formation>> = vec![None; instances.len()];
    if arms.len() > 1 {
        let flourishes = moments.iter().filter(|m| m.label == "flourish");
        for (n, m) in flourishes.enumerate() {
            let i = instances
                .partition_point(|x| x.end <= m.time)
                .min(instances.len() - 1);
            // Only a move that sweeps under 120 degrees round the base. The
            // wide circles and arcs belong to the choruses, which stay in
            // step (the user: all together looks best).
            let x = &instances[i];
            let sweep = (0..=16).map(|k| {
                let u = k as f64 / 16.0;
                scaled((x.shape)(u, x.dir), x.scale)[0] + x.turn * u
            });
            let (low, high) = sweep.fold((f64::INFINITY, f64::NEG_INFINITY), |(low, high), v| {
                (low.min(v), high.max(v))
            });
            let narrow = 180.0 * (high - low) < 120.0;
            if narrow && x.end - x.start >= 6.0 * beat && accents[i].is_none() {
                let accent = [Formation::Ripple, Formation::Canon][n % 2];
                accents[i] = Some(accent);
                cues[i]
                    .reason
                    .push_str(&format!(" · passed round as {accent:?}"));
            }
        }
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
    let mut clock: Vec<f64> = Vec::with_capacity(grid.len());
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
    // Smooth the clock (bell of two knots). Quick notes of the leader retrigger
    // the surge every second knot, which made the hand's pace, the base and the
    // disc alternate knot by knot. The hand stays within 1 cm of the unsmoothed
    // path; hand acceleration outside moments falls from 5.8 to 1.8 m/s² p95.
    // The user saw no difference by eye: kept for the hardware.
    let clock: Vec<f64> = (0..clock.len())
        .map(|i| bell(&clock, i as f64, 2.0))
        .collect();
    let waited = |t: f64| -> [f64; 3] {
        let x = (t / step).clamp(0.0, (clock.len() - 1) as f64);
        let i = (x.floor() as usize).min(clock.len() - 2);
        let mut p = flow(lerp(clock[i], clock[i + 1], x - i as f64));
        // The hand rises while the voice sings well above its usual pitch.
        let sung = (t - data.musical_memory.beat_zero) / beat - 0.5;
        // 0.65: the user put it between 0.45 and 0.9 in a blind side-by-side.
        let lift = 0.65 * bell(&voice, sung, 2.0);
        (p[1], p[2]) = (p[1] + lift, p[2] + lift);
        // The hand rides higher as the leader's line brightens.
        p[1] += 0.3 * swell_at(t)[1];
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

    let neutral: Vec<f64> = rig.channels.iter().map(|c| c.neutral_degrees).collect();
    let held = rig.implement.radius_m;
    // A last joint that turns about its own link is a tool roll: it moves no
    // point of the chain, so it is driven here, not by the position solver.
    let roll_joint = rig.channels.last().and_then(|c| {
        let along: f64 = (0..3).map(|k| c.axis_local[k] * c.link_m[k]).sum();
        let length = c.link_m.iter().map(|v| v * v).sum::<f64>().sqrt();
        (length > 0.0 && (along.abs() - length).abs() < 1e-9).then_some(rig.channels.len() - 1)
    });
    struct Arm<'a> {
        placement: &'a Placement,
        /// (hand target in the world, base facing in the arm's own frame).
        targets: Vec<([f64; 3], f64)>,
        knots: Vec<JointKnot>,
        held_target: Option<[f64; 3]>,
        wanted: Vec<f64>,
        speed: Vec<f64>,
        turned: f64,
    }
    // Each arm's own hand path. Alone, an arm dances the figures as planned.
    // In an ensemble the formation gives each arm a side (mirror image about
    // its forward line), a delay and whether it dances or rests; bearings are
    // in the arm's frame, where 0 is its forward. A resting arm draws in low
    // and turns forward. Changes of formation are eased, never cut.
    let count = arms.len();
    let rest = place(still(0.0, 1.0)).0;
    let (rest_out, rest_up) = (rest[0].hypot(rest[1]), rest[2]);
    let mut locals: Vec<Vec<([f64; 3], f64)>> = Vec::with_capacity(count);
    // Centre of the layout.
    let middle: [f64; 2] = std::array::from_fn(|k| {
        arms.iter()
            .map(|arm| arm.placement.origin_m[k])
            .sum::<f64>()
            / count as f64
    });
    for (a, plan) in arms.iter().enumerate() {
        let flip = if plan.mirrored { -1.0 } else { 1.0 };
        let local: Vec<([f64; 3], f64)> = if count == 1 {
            let flipped =
                |&(p, facing): &([f64; 3], f64)| ([p[0], flip * p[1], p[2]], flip * facing);
            targets.iter().map(flipped).collect()
        } else {
            // This arm's part at the start of move `index`, as seen at time `t`.
            let at_move = |index: usize, t: f64| {
                let run = formations.partition_point(|f| f.0 <= t).saturating_sub(1);
                let (start, formation) = formations[run];
                let length = (instances[index].end - instances[index].start) / beat;
                let (side, delay, on) =
                    formation.part(a, count, ((t - start) / beat).max(0.0), index, length);
                let delay =
                    accents[index].map_or(delay, |f| f.part(a, count, 0.0, index, length).1);
                (side, delay, on)
            };
            let part = |t: f64| {
                let index = instances
                    .partition_point(|x| x.end <= t)
                    .min(instances.len() - 1);
                let (side, delay, on) = at_move(index, t);
                // The delay runs evenly from this move's to the next one's
                // across the move: the arm starts each move on its turn and
                // plays it a little faster or slower. (A delay that jumped at
                // each move made the end arms of a ripple stall, then race:
                // the user saw it as a stutter.)
                let x = &instances[index];
                let next = (index + 1).min(instances.len() - 1);
                let then = at_move(next, instances[next].start).1;
                let along = ((t - x.start) / (x.end - x.start).max(1e-9)).clamp(0.0, 1.0);
                (side, lerp(delay, then, along), on)
            };
            let parts: Vec<(f64, f64, f64)> = times.iter().map(|&t| part(t)).collect();
            let column =
                |pick: fn(&(f64, f64, f64)) -> f64| parts.iter().map(pick).collect::<Vec<f64>>();
            let (delays, dancing) = (column(|p| p.1), column(|p| p.2));
            let mut bearings: Vec<f64> = Vec::with_capacity(times.len());
            let mut reach: Vec<[f64; 2]> = Vec::with_capacity(times.len());
            let placed: Vec<([f64; 3], f64)> = (0..times.len())
                .map(|i| {
                    let late = beat * bell(&delays, i as f64, 12.0);
                    let (p, bearing) = place(hand((times[i] - late).max(0.0)));
                    (p, flip * parts[i].0 * bearing)
                })
                .collect();
            for (i, &(p, want)) in placed.iter().enumerate() {
                let on = bell(&dancing, i as f64, 6.0);
                let aimed = lerp(360.0 * (want / 360.0).round(), want, on);
                // Turns are counted from the last bearing, so a change of side
                // swings the nearer way round and not back through every turn.
                let last = bearings.last().copied().unwrap_or(aimed);
                bearings.push(last + (aimed - last + 180.0).rem_euclid(360.0) - 180.0);
                reach.push([
                    lerp(rest_out, p[0].hypot(p[1]), on),
                    lerp(rest_up, p[2], on),
                ]);
            }
            (0..times.len())
                .map(|i| {
                    let bearing = bell(&bearings, i as f64, 5.0);
                    let (sin, cos) = bearing.to_radians().sin_cos();
                    ([reach[i][0] * cos, reach[i][0] * sin, reach[i][1]], bearing)
                })
                .collect()
        };
        locals.push(local);
    }
    let alone = Obstacles {
        zones: &zones,
        others: &[],
        radius: 0.0,
    };
    let wrist = roll_joint.map_or(rig.channels.len() - 1, |r| r - 1);
    // Arms share the floor: their reaches overlap and they pass through
    // each other's space. Two limits keep a formation from asking for a
    // collision, both the same for every arm so the picture stays
    // symmetric (the cross-check alone would stop arms by their order):
    // no hand enters the circle at the ring's centre where all the hands
    // would meet; and, where arms out of step would meet (`apart` below),
    // each hand stays on its own side of the line half way to its
    // neighbours. `limit` is how far that second limit applies, 0..1.
    let around = PI / count as f64;
    // Half the clearance and the implement. In the middle 2 cm more is
    // enough: in unison the hands arrive together. At the line between
    // neighbours it is 12 cm: out of step, an elbow reaches past its hand,
    // and with less the cross-check stopped arms dead there.
    let ball = 0.5 * clearance_m + held;
    let keep_out = (ball + 0.02) / around.sin();
    let shared = |plan: &ArmPlan, p: [f64; 3], limit: f64| -> [f64; 3] {
        let (sin, cos) = plan.placement.yaw_degrees.to_radians().sin_cos();
        let o = plan.placement.origin_m;
        let world = [
            o[0] + cos * p[0] - sin * p[1],
            o[1] + sin * p[0] + cos * p[1],
        ];
        if count == 1 {
            return [world[0], world[1], o[2] + p[2]];
        }
        let own = (o[1] - middle[1]).atan2(o[0] - middle[0]);
        let (x, y) = (world[0] - middle[0], world[1] - middle[1]);
        // Eases out to the circle's edge over the last fifth of it.
        let out = x.hypot(y);
        let out = out.max(keep_out)
            + 0.2 * keep_out * (-(out - keep_out).max(0.0) / (0.2 * keep_out)).exp();
        let off = (y.atan2(x) - own + PI).rem_euclid(TAU) - PI;
        let half = (around - ((ball + 0.12) / out).min(1.0).asin()).max(0.0);
        // Untouched over the inner 70 % of the sector, eased into its
        // edge beyond. (Squeezing the whole sector bent the hand's path
        // over its own base, into a joint limit and out with a kick.)
        let (knee, edge) = (0.7 * half, (0.3 * half).max(1e-9));
        let inside = if off.abs() <= knee {
            off
        } else {
            off.signum() * (knee + edge * ((off.abs() - knee) / edge).tanh())
        };
        let angle = own + lerp(off, inside, limit);
        [
            middle[0] + out * angle.cos(),
            middle[1] + out * angle.sin(),
            o[2] + p[2],
        ]
    };
    // Where arms out of step would meet. Each arm is posed on its own along
    // its unlimited path, at every second knot; wherever two of them come
    // within the clearance, every hand keeps to its own sector from half a
    // beat before to half a beat after. Elsewhere out-of-step arms work
    // inside each other's reach. Arms moving as one (unison) pass through
    // the space a neighbour has just left and need no limit. Measured on one
    // song: a wider margin or window gave less shared space and no fewer
    // stalls; a narrower margin left the cross-check to stop arms.
    let mut apart = vec![0.0; times.len()];
    if count > 1 {
        let mut poses = vec![neutral.clone(); count];
        let mut meets = vec![false; times.len()];
        for i in (0..times.len()).step_by(2) {
            let mut bodies = Vec::with_capacity(count);
            for (a, plan) in arms.iter().enumerate() {
                let (p, facing) = locals[a][i];
                let target = shared(plan, p, 0.0);
                poses[a] = solve(
                    &rig,
                    &plan.placement,
                    &alone,
                    target,
                    facing,
                    &poses[a],
                    (wrist, 0.0),
                )?;
                bodies.push(body_samples(
                    &forward_kinematics(&rig, &plan.placement, &poses[a])?,
                    held,
                ));
            }
            meets[i] = (0..count).any(|a| {
                let others = Obstacles {
                    zones: &[],
                    others: &bodies[(a + 1)..].concat(),
                    radius: clearance_m,
                };
                bodies[a]
                    .iter()
                    .any(|(p, extra)| others.depth(*p, *extra, 1.0) > 0.0)
            });
        }
        for (i, weight) in apart.iter_mut().enumerate() {
            let around = &meets[i.saturating_sub(4)..(i + 5).min(meets.len())];
            *weight = f64::from(around.iter().any(|m| *m));
        }
    }
    let mut dancers: Vec<Arm> = Vec::with_capacity(count);
    for (plan, local) in arms.iter().zip(locals) {
        dancers.push(Arm {
            placement: &plan.placement,
            targets: local
                .into_iter()
                .enumerate()
                .map(|(i, (p, facing))| (shared(plan, p, bell(&apart, i as f64, 6.0)), facing))
                .collect(),
            knots: Vec::with_capacity(times.len()),
            held_target: None,
            wanted: Vec::new(),
            speed: vec![0.0; rig.channels.len()],
            turned: 0.0,
        });
    }
    // Where each arm starts. Alone: the rig's neutral pose. In an ensemble the
    // neutral poses may meet in the middle, so each arm starts at its first
    // target, solved on its own.
    let mut starts: Vec<Vec<f64>> = Vec::with_capacity(count);
    for arm in &dancers {
        if !clear(&rig, arm.placement, &alone, &neutral, &neutral)? {
            return Err("rig neutral pose intersects a zone".into());
        }
        let (target, facing) = arm.targets[0];
        starts.push(if count == 1 {
            neutral.clone()
        } else {
            solve(
                &rig,
                arm.placement,
                &alone,
                target,
                facing,
                &neutral,
                (wrist, 0.0),
            )?
        });
    }
    // Where each arm is now, as points the other arms must keep away from.
    let mut bodies: Vec<Vec<([f64; 3], f64)>> = Vec::new();
    for (arm, start) in dancers.iter().zip(&starts) {
        bodies.push(body_samples(
            &forward_kinematics(&rig, arm.placement, start)?,
            held,
        ));
    }
    let others_of = |bodies: &[Vec<([f64; 3], f64)>], a: usize| -> Vec<([f64; 3], f64)> {
        let rest = bodies.iter().enumerate().filter(|(b, _)| *b != a);
        rest.flat_map(|(_, body)| body.iter().copied()).collect()
    };
    for (a, (arm, start)) in dancers.iter().zip(&starts).enumerate() {
        let others = others_of(&bodies, a);
        let world = Obstacles {
            zones: &zones,
            others: &others,
            radius: clearance_m,
        };
        if !clear(&rig, arm.placement, &world, start, start)? {
            return Err("arms start inside a zone or each other: move them apart".into());
        }
    }
    for (i, &time) in times.iter().enumerate() {
        if i > 0 && time - times[i - 1] < 1e-9 {
            continue;
        }
        for (a, arm) in dancers.iter_mut().enumerate() {
            let others = others_of(&bodies, a);
            let world = Obstacles {
                zones: &zones,
                others: &others,
                radius: clearance_m,
            };
            let (placement, targets) = (arm.placement, &arm.targets);
            let (target, facing) = targets[i];
            let (prior, dt) = arm
                .knots
                .last()
                .map_or((starts[a].clone(), f64::INFINITY), |k| {
                    (k.joints_degrees.clone(), time - k.time)
                });
            // A held hand keeps its solved pose: no settling toward neutral.
            let holding = arm.held_target == Some(target);
            arm.held_target = Some(target);
            if !holding || arm.wanted.is_empty() {
                // Body: the wrist trails the hand's rise and fall like a brush
                // (bends back as the hand rises, forward as it falls). It is only a
                // posture preference, so the other joints make up for it and the
                // hand still reaches its target.
                let (lo, hi) = (i.saturating_sub(4), (i + 4).min(targets.len() - 1));
                let rise =
                    (targets[hi].0[2] - targets[lo].0[2]) / (times[hi] - times[lo]).max(1e-9);
                let lean = (config.wrist_drag_degrees_per_mps * rise).clamp(-45.0, 45.0);
                let wrist = roll_joint.map_or(rig.channels.len() - 1, |r| r - 1);
                arm.wanted = solve(
                    &rig,
                    placement,
                    &world,
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
                    arm.turned += SPIN_DEGREES_PER_METRE * travel * fast * way;
                }
                arm.wanted[r] = flips + arm.turned;
            }
            // Hardware follower: each joint chases its solved angle at a design
            // acceleration and speed a hobby-class servo arm could plausibly follow,
            // braking early enough to stop on target (trapezoid profile). The rig's
            // own limits are the hard validation envelope, reached only when a zone
            // forces an abrupt stop. Both are assumptions until measured on hardware.
            let wanted = &arm.wanted;
            let speed = &mut arm.speed;
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
                    let v =
                        (gap.signum() * brake).clamp(speed[j] - accel * dt, speed[j] + accel * dt);
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
                let before = link_samples(&forward_kinematics(&rig, placement, &prior)?, held);
                let after = link_samples(&forward_kinematics(&rig, placement, &q)?, held);
                let brake = (0.1 * rig.channels[0].max_acceleration_degrees_per_second2)
                    .to_radians()
                    * reach_m;
                let mut scale: f64 = 1.0;
                for (a, b) in before.iter().zip(&after) {
                    let travel = (0..3)
                        .map(|k| (b.0[k] - a.0[k]).powi(2))
                        .sum::<f64>()
                        .sqrt();
                    // Toward another arm it brakes as toward a zone; moving
                    // apart is free, or two arms that met would hardly part.
                    let (near, then) = (world.arm_room(a.0, a.1), world.arm_room(b.0, b.1));
                    let zone = world.zone_room(a.0, a.1);
                    let room = if then < near { zone.min(near) } else { zone };
                    let limit = (2.0 * brake * (room + 0.005)).sqrt() * dt;
                    if travel > limit {
                        scale = scale.min(limit / travel);
                    }
                }
                for j in 0..q.len() {
                    q[j] = lerp(prior[j], q[j], scale);
                }
            }
            // Hard guarantee: bisect back toward the prior clear pose.
            if !clear(&rig, placement, &world, &prior, &q)? {
                let (mut lo, mut hi) = (0.0, 1.0);
                for _ in 0..24 {
                    let mid = 0.5 * (lo + hi);
                    let trial: Vec<f64> = (0..q.len()).map(|j| lerp(prior[j], q[j], mid)).collect();
                    if clear(&rig, placement, &world, &prior, &trial)? {
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
            bodies[a] = body_samples(&forward_kinematics(&rig, placement, &q)?, held);
            arm.knots.push(JointKnot {
                time,
                velocity_degrees_per_second: vec![0.0; q.len()],
                joints_degrees: q,
            });
        }
    }
    let mut tracks = Vec::with_capacity(dancers.len());
    for (id, arm) in dancers.into_iter().enumerate() {
        let mut knots = arm.knots;
        for i in 1..knots.len() - 1 {
            let span = knots[i + 1].time - knots[i - 1].time;
            // An arrival stops dead: no tangent into a held pose.
            let holds = (0..rig.channels.len()).all(|j| {
                (knots[i + 1].joints_degrees[j] - knots[i].joints_degrees[j]).abs() < 0.05
            });
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
        let mut track = AgentTrack {
            id: id as u32,
            knots,
        };
        fit_tangents(&mut track, &rig)?;
        tracks.push(track);
    }
    let score = EnsembleScore {
        duration: data.duration,
        rig,
        placements: arms.iter().map(|arm| arm.placement.clone()).collect(),
        cues,
        tracks,
    };
    score.validate()?;
    Ok(score)
}

/// `series` at fractional index `x`, averaged under a bell `sigma` samples
/// wide; the ends repeat. 0 for an empty series.
fn bell(series: &[f64], x: f64, sigma: f64) -> f64 {
    if series.is_empty() {
        return 0.0;
    }
    let (mut sum, mut total) = (0.0, 0.0);
    let reach = (3.0 * sigma).ceil() as isize;
    for i in x.round() as isize - reach..=x.round() as isize + reach {
        let w = (-0.5 * ((i as f64 - x) / sigma).powi(2)).exp();
        sum += w * series[i.clamp(0, series.len() as isize - 1) as usize];
        total += w;
    }
    sum / total
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

/// What an arm must stay out of: fixed zones, and the other arms as they
/// stand now (points with their own extra room), `radius` apart.
struct Obstacles<'a> {
    zones: &'a [Zone],
    others: &'a [([f64; 3], f64)],
    radius: f64,
}

impl Obstacles<'_> {
    fn gap(&self, p: [f64; 3], extra: f64) -> f64 {
        self.others
            .iter()
            .map(|(q, more)| {
                (0..3).map(|k| (p[k] - q[k]).powi(2)).sum::<f64>().sqrt() - extra - more
            })
            .fold(f64::INFINITY, f64::min)
    }
    /// How deep `p` (needing `extra` room) is inside something; 0 when clear.
    /// `slack` widens every margin: the solver aims for more than the check.
    fn depth(&self, p: [f64; 3], extra: f64, slack: f64) -> f64 {
        penetration(p, self.zones, slack * MARGIN_M + extra)
            // The same extra width as for zones, whatever the radius, so the
            // solver steers away before the hard check has to stop the arm.
            .max(self.radius + (slack - 1.0) * MARGIN_M - self.gap(p, extra))
            .max(0.0)
    }
    /// Free distance from `p` to the nearest zone; 0 when inside one.
    fn zone_room(&self, p: [f64; 3], extra: f64) -> f64 {
        clearance(p, self.zones, MARGIN_M + extra)
    }
    /// Free distance from `p` to the nearest other arm, halved: that arm may
    /// be closing in at the same rate. 0 when inside its clearance.
    fn arm_room(&self, p: [f64; 3], extra: f64) -> f64 {
        (0.5 * (self.gap(p, extra) - self.radius)).max(0.0)
    }
}

/// Points of a whole arm that other arms keep away from: the checked points
/// plus the base column, which never meets a zone but can meet a neighbour.
fn body_samples(points: &[[f64; 3]], held: f64) -> Vec<([f64; 3], f64)> {
    let mut out = link_samples(points, held);
    out.extend([(points[0], 0.0), (points[1], 0.0)]);
    out.push((
        std::array::from_fn(|i| lerp(points[1][i], points[2][i], 0.25)),
        0.0,
    ));
    out
}

/// Points checked against zones, each with the extra room it needs. The base
/// and its first link sit on the mount surface, so checks start halfway up the
/// second link. The last point is the hand: it carries the implement, which
/// reaches `held` metres from it in any direction.
fn link_samples(points: &[[f64; 3]], held: f64) -> Vec<([f64; 3], f64)> {
    let mut out = Vec::new();
    for k in 1..points.len() - 1 {
        for f in [0.25, 0.5, 0.75, 1.0] {
            if k > 1 || f >= 0.5 {
                out.push((
                    std::array::from_fn(|i| lerp(points[k][i], points[k + 1][i], f)),
                    0.0,
                ));
            }
        }
    }
    if let Some(hand) = out.last_mut() {
        hand.1 = held;
    }
    out
}

/// True when the straight joint-space move `from` → `to` stays out of all zones.
// ponytail: checks 6 linear blends, not the exact quintic; margin covers the gap.
fn clear(
    rig: &Rig,
    placement: &Placement,
    world: &Obstacles,
    from: &[f64],
    to: &[f64],
) -> Result<bool, String> {
    for u in [1.0 / 6.0, 2.0 / 6.0, 0.5, 4.0 / 6.0, 5.0 / 6.0, 1.0] {
        let q: Vec<f64> = (0..to.len()).map(|j| lerp(from[j], to[j], u)).collect();
        let points = forward_kinematics(rig, placement, &q)?;
        if link_samples(&points, rig.implement.radius_m)
            .into_iter()
            .any(|(p, extra)| world.depth(p, extra, 1.0) > 0.0)
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
    world: &Obstacles,
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
            link_samples(&points, rig.implement.radius_m)
                .into_iter()
                .map(|(p, extra)| 3.0 * world.depth(p, extra, 1.6)),
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
                // The implement too: nothing within its radius of the hand.
                link_samples(
                    &score.sample(t).unwrap().agents[0].world_points,
                    score.rig.implement.radius_m,
                )
                .into_iter()
                .any(|(p, extra)| penetration(p, &[zone, FLOOR], extra) > 0.0)
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
    fn hand_rides_higher_as_a_flowing_leader_brightens() {
        let mut value: serde_json::Value =
            serde_json::from_str(&super::super::tests::fixture(0.7, 0.7)).unwrap();
        // The leader plays a steady stream (no stabs): dull for eight beats,
        // then bright. A quieter lane keeps it company.
        let steady: Vec<[f64; 3]> = (0..16).map(|i| [0.5 * i as f64, 60.0, 1.0]).collect();
        let mut climb = |step: f64| {
            let brightness: Vec<f64> = (0..16)
                .map(|i| if i < 8 { 72.0 - step } else { 72.0 })
                .collect();
            value["noteTrack"] = serde_json::json!({"lanes": {
                "lead": {"notes": steady, "levelPerBeat": vec![-10.0; 16], "brightnessPerBeat": brightness},
                "bass": {"notes": steady, "levelPerBeat": vec![-30.0; 16], "brightnessPerBeat": vec![40.0; 16]},
            }});
            let config = CompileConfig {
                enable_hits: false,
                ..CompileConfig::default()
            };
            let rig = Rig::illustrative_five_axis();
            let score = compile_figures(&value.to_string(), config, rig, &[]).unwrap();
            let height = |from: f64| {
                (0..20)
                    .map(|i| {
                        let t = from + 0.1 * i as f64;
                        score.sample(t).unwrap().agents[0]
                            .world_points
                            .last()
                            .unwrap()[2]
                    })
                    .sum::<f64>()
                    / 20.0
            };
            height(5.5) - height(1.5)
        };
        let (with, without) = (climb(12.0), climb(0.0));
        assert!(
            with > without + 0.05,
            "climb with a brightening leader {with:.3} m, with a flat one {without:.3} m"
        );
    }

    #[test]
    fn hand_rises_while_the_voice_sings_high() {
        let mut value: serde_json::Value =
            serde_json::from_str(&super::super::tests::fixture(0.7, 0.7)).unwrap();
        let config = CompileConfig {
            enable_hits: false,
            ..CompileConfig::default()
        };
        let mut climb = |high: f64| {
            // Two notes a beat at its usual pitch, then one a beat higher up.
            let low = (0..16).map(|i| [0.25 * i as f64, 60.0, 1.0]);
            let notes: Vec<[f64; 3]> = low
                .chain((8..16).map(|i| [0.5 * i as f64, high, 1.0]))
                .collect();
            value["noteTrack"] = serde_json::json!({"lanes": {
                "vocals": {"notes": notes, "levelPerBeat": vec![-20.0; 16]},
            }});
            let rig = Rig::illustrative_five_axis();
            let score = compile_figures(&value.to_string(), config, rig, &[]).unwrap();
            let height = |from: f64| {
                (0..20)
                    .map(|i| {
                        let t = from + 0.1 * i as f64;
                        score.sample(t).unwrap().agents[0]
                            .world_points
                            .last()
                            .unwrap()[2]
                    })
                    .sum::<f64>()
                    / 20.0
            };
            height(5.5) - height(1.5)
        };
        let (with, without) = (climb(72.0), climb(60.0));
        assert!(
            with > without + 0.1,
            "climb with a high voice {with:.3} m, with a level one {without:.3} m"
        );
    }

    #[test]
    fn another_arm_is_a_red_zone() {
        // One point of another arm, carrying 0.08 m of implement, 1 m away.
        let other = [([1.0, 0.0, 0.5], 0.08)];
        let world = Obstacles {
            zones: &[],
            others: &other,
            radius: 0.1,
        };
        // 0.3 m apart: 0.22 m of free gap, clear. 0.15 m apart: inside.
        assert_eq!(world.depth([0.7, 0.0, 0.5], 0.0, 1.0), 0.0);
        assert!((world.depth([0.85, 0.0, 0.5], 0.0, 1.0) - 0.03).abs() < 1e-9);
        // The arm's own extra room counts too, and it brakes within half the gap.
        assert!(world.depth([0.7, 0.0, 0.5], 0.13, 1.0) > 0.0);
        assert!((world.arm_room([0.7, 0.0, 0.5], 0.0) - 0.06).abs() < 1e-9);
    }

    #[test]
    fn six_arms_share_the_dance_and_keep_apart() {
        let json = super::super::tests::fixture(0.7, 0.7);
        let rig = Rig::illustrative_five_axis();
        let ring: Vec<ArmPlan> = (0..6)
            .map(|k| {
                let degrees = 60.0 * k as f64;
                let (sin, cos) = degrees.to_radians().sin_cos();
                ArmPlan {
                    placement: Placement {
                        origin_m: [0.8 * cos, 0.8 * sin, 0.0],
                        yaw_degrees: degrees + 180.0,
                    },
                    mirrored: false,
                }
            })
            .collect();
        let config = CompileConfig::default();
        let score = compile_ensemble(&json, config, rig, &[], &ring, 0.1).unwrap();
        assert_eq!(score.tracks.len(), 6);
        assert!(score.cues[0].reason.contains("ensemble Unison"));
        let held = score.rig.implement.radius_m;
        let (mut closest, mut middle, mut moved) = (f64::INFINITY, f64::INFINITY, [0.0f64; 6]);
        let mut across = false;
        for i in 0..=480 {
            let frame = score.sample(8.0 * i as f64 / 480.0).unwrap();
            let bodies: Vec<_> = frame
                .agents
                .iter()
                .map(|agent| body_samples(&agent.world_points, held))
                .collect();
            for a in 0..6 {
                let hand = frame.agents[a].world_points.last().unwrap();
                let origin = ring[a].placement.origin_m;
                moved[a] = moved[a].max((hand[0] - origin[0]).hypot(hand[1] - origin[1]));
                let to = |b: &ArmPlan| {
                    (hand[0] - b.placement.origin_m[0]).hypot(hand[1] - b.placement.origin_m[1])
                };
                across |= ring.iter().any(|b| to(b) < to(&ring[a]) - 1e-9);
                middle = middle.min(hand[0].hypot(hand[1]));
                for b in a + 1..6 {
                    for (p, extra) in &bodies[a] {
                        for (q, more) in &bodies[b] {
                            let apart = (0..3).map(|k| (p[k] - q[k]).powi(2)).sum::<f64>().sqrt();
                            closest = closest.min(apart - extra - more);
                        }
                    }
                }
            }
        }
        assert!(
            closest > 0.08,
            "arms came within {closest:.3} m, clearance 0.1 m"
        );
        // They share the floor: hands go well past half way to a neighbour
        // (0.4 m), yet none enters the circle in the middle where all six
        // would meet.
        assert!(moved.iter().all(|m| *m > 0.5), "reach {moved:?}");
        // Nearer a neighbour's base than its own: no sector limit applies
        // while the arms, posed alone, would not meet.
        assert!(across, "no hand went past half way to a neighbour");
        assert!(middle > 0.27, "a hand came {middle:.3} m from the centre");
    }

    #[test]
    fn mirrored_arms_keep_apart_without_stopping() {
        // Drums without voice or bass: every second arm dances the mirror image.
        let json = super::super::tests::fixture(0.1, 0.2);
        let ring: Vec<ArmPlan> = (0..6)
            .map(|k| {
                let degrees = 60.0 * k as f64;
                let (sin, cos) = degrees.to_radians().sin_cos();
                ArmPlan {
                    placement: Placement {
                        origin_m: [0.8 * cos, 0.8 * sin, 0.0],
                        yaw_degrees: degrees + 180.0,
                    },
                    mirrored: false,
                }
            })
            .collect();
        let rig = Rig::illustrative_five_axis();
        let score =
            compile_ensemble(&json, CompileConfig::default(), rig, &[], &ring, 0.1).unwrap();
        assert!(score.cues[0].reason.contains("ensemble Mirrored"));
        let held = score.rig.implement.radius_m;
        let hands = |t: f64| -> Vec<[f64; 3]> {
            let frame = score.sample(t).unwrap();
            let last = |agent: &crate::ensemble::AgentFrame| *agent.world_points.last().unwrap();
            frame.agents.iter().map(last).collect()
        };
        let apart = |p: [f64; 3], q: [f64; 3]| (p[0] - q[0]).hypot(p[1] - q[1]);
        let (mut closest, mut still) = (f64::INFINITY, [0; 6]);
        for i in 40..=440 {
            let (now, soon) = (
                hands(8.0 * i as f64 / 480.0),
                hands(8.0 * (i + 1) as f64 / 480.0),
            );
            for a in 0..6 {
                still[a] += usize::from(apart(now[a], soon[a]) * 60.0 < 0.02);
                for b in a + 1..6 {
                    let gap = (0..3)
                        .map(|k| (now[a][k] - now[b][k]).powi(2))
                        .sum::<f64>()
                        .sqrt();
                    closest = closest.min(gap - 2.0 * held);
                }
            }
        }
        assert!(closest > 0.08, "implements came within {closest:.3} m");
        // No arm stands for a third of a second in all.
        assert!(
            still.iter().all(|n| *n < 20),
            "frames standing still {still:?}"
        );
    }

    #[test]
    fn every_arm_of_an_ensemble_stays_out_of_a_red_zone() {
        let json = super::super::tests::fixture(0.7, 0.7);
        let rig = Rig::illustrative_five_axis();
        // Two arms 1.6 m apart, facing each other.
        let pair: Vec<ArmPlan> = [(-0.8, 0.0), (0.8, 180.0)]
            .map(|(x, yaw_degrees)| ArmPlan {
                placement: Placement {
                    origin_m: [x, 0.0, 0.0],
                    yaw_degrees,
                },
                mirrored: false,
            })
            .to_vec();
        let plan = |zones: &[Zone]| {
            compile_ensemble(
                &json,
                CompileConfig::default(),
                rig.clone(),
                zones,
                &pair,
                0.1,
            )
            .unwrap()
        };
        let free = plan(&[]);
        // A box of equipment where the second arm's hand is furthest out.
        let far = (0..=960)
            .map(|i| {
                *free.sample(8.0 * i as f64 / 960.0).unwrap().agents[1]
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
        let blocked = plan(&[zone]);
        let entered = |score: &EnsembleScore, t: f64| {
            let held = score.rig.implement.radius_m;
            score.sample(t).unwrap().agents.iter().any(|agent| {
                link_samples(&agent.world_points, held)
                    .into_iter()
                    .any(|(p, extra)| penetration(p, &[zone, FLOOR], extra) > 0.0)
            })
        };
        let times = (0..=960).map(|i| 8.0 * i as f64 / 960.0);
        assert!(
            times.clone().any(|t| entered(&free, t)),
            "fixture zone must obstruct the free path"
        );
        for t in times {
            assert!(!entered(&blocked, t), "an arm is inside the zone at {t}");
        }
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
