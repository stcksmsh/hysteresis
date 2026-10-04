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
/// Solver keeps this clearance; the hard check enforces 60% of it.
const MARGIN_M: f64 = 0.05;

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

/// Figure sequence per musical class and an overall size. The sequence runs
/// for as long as the class lasts, mirrored on every repeat.
fn motif(class: &str) -> (&'static [Step], f64) {
    const FULL: &[Step] = &[
        ("gather", gather, 8.0, 1.0),
        ("rise", rise, 4.0, 1.0),
        ("open", open, 4.0, 1.0),
        ("arc", arc, 8.0, 1.0),
        ("arc", arc, 8.0, -1.0),
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
        "interlocked" => (FULL, 0.9),
        "bass-led" => (BASS, 0.85),
        "vocal-led" => (VOCAL, 0.7),
        "percussive-open" => (PERC, 0.6),
        "textural" => (CALM, 0.5),
        "silence" => (STILL, 1.0),
        _ => (CALM, 0.35),
    }
}

struct Instance {
    start: f64,
    end: f64,
    shape: Shape,
    dir: f64,
    scale: f64,
    pulse: f64,
    /// Scaled shell position where the previous figure ended.
    entry: [f64; 3],
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
    let beat_zero = data.musical_memory.beat_zero;
    let rate = data.stem_interpretation.envelope_rate;
    let sources: [&Source; 4] =
        std::array::from_fn(|i| &data.stem_interpretation.sources[SOURCES[i]]);

    // Spans: phrase edges and measured transitions; drop edges under four beats apart.
    let mut edges: Vec<f64> = Vec::new();
    for edge in boundaries(&data, &transitions(&data, &sources)) {
        if edges.last().is_none_or(|last| edge - last >= 4.0 * beat) {
            edges.push(edge);
        }
    }
    if edges.len() > 1 && data.duration - edges[edges.len() - 1] > 1e-9 {
        edges.pop();
    }
    if edges.len() < 2 || edges[edges.len() - 1] < data.duration {
        edges.push(data.duration);
    }
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

    // (run start, direction, class) for recall lookups.
    let mut chosen: Vec<(f64, f64, &str)> = Vec::new();
    let mut occurrences: HashMap<&str, usize> = HashMap::new();
    let mut instances: Vec<Instance> = Vec::new();
    let mut cues: Vec<IntentCue> = Vec::new();
    let mut entry = still(0.0, 1.0);
    for &(start, end, class) in &runs {
        let activity = classify(start, end).1;
        let (sequence, size) = motif(class);
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
        let pulse = activity[1].clamp(0.0, 0.3);
        let mut t = start;
        for (k, &(name, shape, beats, step_dir)) in sequence.iter().cycle().enumerate() {
            let mut stop = t + beats * beat;
            if stop > end - 2.0 * beat {
                stop = end;
            }
            let repeat = k / sequence.len();
            let dir = first_dir * step_dir * if repeat % 2 == 1 { -1.0 } else { 1.0 };
            instances.push(Instance {
                start: t,
                end: stop,
                shape,
                dir,
                scale,
                pulse,
                entry,
            });
            entry = scaled(shape(1.0, dir), scale);
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
                ),
                profile: Vec::new(),
            });
            t = stop;
            if t >= end {
                break;
            }
        }
    }

    // Drums set the floor: motion eases into each beat by `pulse`.
    let warped = |t: f64, pulse: f64| {
        let b = (t - beat_zero) / beat;
        beat_zero + beat * (b.floor() + lerp(b.fract(), smooth(b.fract()), pulse))
    };
    // The melodic stem sets the pace: a figure advances faster through its
    // flourishes (high spectral flux) and lingers while it sustains.
    let flux = &sources[3].spectral_flux;
    let mut pace = vec![0.0; flux.len() + 1];
    for i in 0..flux.len() {
        let t = i as f64 / rate;
        pace[i + 1] = pace[i] + 0.35 + mean(flux, rate, t - 0.3, t + 0.3);
    }
    let paced = |t: f64| {
        let x = (t * rate).clamp(0.0, flux.len() as f64);
        let i = (x.floor() as usize).min(flux.len() - 1);
        lerp(pace[i], pace[i + 1], x - i as f64)
    };
    let contour = |name: &str, t: f64| -> (f64, f64) {
        data.melody_contour
            .as_ref()
            .and_then(|m| Some((m.envelope_rate, m.sources.get(name)?)))
            .filter(|(_, c)| !c.height.is_empty() && c.height.len() == c.salience.len())
            .map_or((0.5, 0.0), |(rate, c)| {
                let i = ((t * rate).max(0.0) as usize).min(c.height.len() - 1);
                (c.height[i], c.salience[i])
            })
    };
    let shell = |t: f64| -> [f64; 3] {
        let i = instances
            .partition_point(|x| x.end <= t)
            .min(instances.len() - 1);
        let x = &instances[i];
        let at = |t: f64| paced(warped(t, x.pulse));
        let u = ((at(t) - at(x.start)) / (at(x.end) - at(x.start)).max(1e-9)).clamp(0.0, 1.0);
        let here = scaled((x.shape)(u, x.dir), x.scale);
        let first = scaled((x.shape)(0.0, x.dir), x.scale);
        // Carry the previous figure's end into this one over its first half.
        let carry = 1.0 - smooth(u / 0.5);
        let mut p: [f64; 3] = std::array::from_fn(|k| here[k] + (x.entry[k] - first[k]) * carry);
        // Lead melody lifts and lowers the hand; the voice opens the arm.
        let (lead_height, lead_salience) = contour("other", t);
        let (voice_height, voice_salience) = contour("vocals", t);
        p[1] += 0.3 * (lead_height - 0.5) * lead_salience;
        p[2] += 0.2 * (voice_height - 0.4) * voice_salience;
        p
    };
    let step = beat / 4.0;
    let count = (data.duration / step).ceil() as usize;
    let times: Vec<f64> = (0..=count)
        .map(|i| (i as f64 * step).min(data.duration))
        .collect();
    // This song has no sharp passages: low-pass the hand path (sigma 0.3 s).
    let raw: Vec<[f64; 3]> = times.iter().map(|&t| shell(t)).collect();
    let sigma = 0.3 / step;
    let radius = (3.0 * sigma).ceil() as isize;
    let reach_m: f64 = rig
        .channels
        .iter()
        .map(|c| c.link_m.iter().map(|v| v * v).sum::<f64>().sqrt())
        .sum();
    let targets: Vec<[f64; 3]> = (0..raw.len() as isize)
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
            let p = sum.map(|v| v / total);
            // 340 of 360 degrees in the floor plane; the 20 degree gap straight back
            // is the base-yaw seam, which the hand never crosses.
            let azimuth = (p[0].clamp(-1.0, 1.0) * 170.0_f64).to_radians();
            let elevation = (10.0 + 70.0 * p[1].clamp(0.0, 1.0)).to_radians();
            let distance = reach_m * (0.38 + 0.54 * p[2].clamp(0.0, 1.0));
            [
                distance * elevation.cos() * azimuth.cos(),
                distance * elevation.cos() * azimuth.sin(),
                distance * elevation.sin(),
            ]
        })
        .collect();

    let placement = Placement {
        origin_m: [0.0; 3],
        yaw_degrees: 0.0,
    };
    let neutral: Vec<f64> = rig.channels.iter().map(|c| c.neutral_degrees).collect();
    if !clear(&rig, &placement, &zones, &neutral, &neutral)? {
        return Err("rig neutral pose intersects a zone".into());
    }
    let mut knots: Vec<JointKnot> = Vec::with_capacity(times.len());
    for (&time, &target) in times.iter().zip(&targets) {
        if knots.last().is_some_and(|k| time - k.time < 1e-9) {
            continue;
        }
        let (prior, dt) = knots.last().map_or((neutral.clone(), f64::INFINITY), |k| {
            (k.joints_degrees.clone(), time - k.time)
        });
        let mut q = solve(&rig, &placement, &zones, target, &prior)?;
        for (j, c) in rig.channels.iter().enumerate() {
            // Largest step a rest-to-rest quintic can make inside both limits,
            // so tangent fitting always has a feasible fallback.
            let travel = (c.max_speed_degrees_per_second * dt / 1.875)
                .min(c.max_acceleration_degrees_per_second2 * dt * dt / 5.7736);
            q[j] = q[j].clamp(prior[j] - travel, prior[j] + travel);
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
        knots.push(JointKnot {
            time,
            velocity_degrees_per_second: vec![0.0; q.len()],
            joints_degrees: q,
        });
    }
    for i in 1..knots.len() - 1 {
        let span = knots[i + 1].time - knots[i - 1].time;
        knots[i].velocity_degrees_per_second = (0..rig.channels.len())
            .map(|j| (knots[i + 1].joints_degrees[j] - knots[i - 1].joints_degrees[j]) / span)
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
// ponytail: checks 3 linear blends, not the exact quintic; margin covers the gap.
fn clear(
    rig: &Rig,
    placement: &Placement,
    zones: &[Zone],
    from: &[f64],
    to: &[f64],
) -> Result<bool, String> {
    for u in [1.0 / 3.0, 2.0 / 3.0, 1.0] {
        let q: Vec<f64> = (0..to.len()).map(|j| lerp(from[j], to[j], u)).collect();
        let points = forward_kinematics(rig, placement, &q)?;
        if link_samples(&points)
            .into_iter()
            .any(|p| penetration(p, zones, 0.6 * MARGIN_M) > 0.0)
        {
            return Ok(false);
        }
    }
    Ok(true)
}

/// Damped least squares: hand to target, stay near the prior pose (fluid
/// joints), drift toward neutral, push every link sample out of zones.
fn solve(
    rig: &Rig,
    placement: &Placement,
    zones: &[Zone],
    target: [f64; 3],
    prior: &[f64],
) -> Result<Vec<f64>, String> {
    let n = rig.channels.len();
    let residual = |q: &[f64]| -> Result<Vec<f64>, String> {
        let points = forward_kinematics(rig, placement, q)?;
        let mut r: Vec<f64> = (0..3).map(|i| points[n][i] - target[i]).collect();
        for j in 0..n {
            r.push(4e-4 * (q[j] - prior[j]));
            r.push(1e-4 * (q[j] - rig.channels[j].neutral_degrees));
        }
        r.extend(
            link_samples(&points)
                .into_iter()
                .map(|p| 3.0 * penetration(p, zones, MARGIN_M)),
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
        // Zone sits in the hand's unobstructed path.
        let zone = Zone {
            min: [0.15, 0.25, 0.25],
            max: [0.6, 0.5, 0.6],
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
}
