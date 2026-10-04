//! Offline interpretation → resolved, seekable 3D ensemble score.
//! Example rig geometry is illustrative; physical axes and calibration are site data.

use std::collections::BTreeMap;

use hyst_choreo::{
    effort::Effort,
    formation::{apply_mirror, canon, effective_order, unison, OrderingSource, TimingAnchor},
    moves::{ChannelRole, Duration, Move, PoseRequirement, Provenance, TimescaleRole},
    topology::Topology,
};
use serde::{Deserialize, Serialize};

use crate::{
    director::{IntentCue, Interpretation},
    sample_segment, segment_bounds, Knot,
};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct RigChannel {
    pub name: String,
    /// Unit rotation axis in frame carried by all upstream joints.
    pub axis_local: [f64; 3],
    /// Translation after this joint rotates, metres, in its rotated frame.
    pub link_m: [f64; 3],
    pub neutral_degrees: f64,
    /// Degrees contributed by normalized [sweep, lift, fold] intent.
    pub intent_mix_degrees: [f64; 3],
    pub min_degrees: f64,
    pub max_degrees: f64,
    pub max_speed_degrees_per_second: f64,
    pub max_acceleration_degrees_per_second2: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Rig {
    pub channels: Vec<RigChannel>,
}

impl Rig {
    /// Provisional five-servo arm: base yaw, bend, local yaw, bend, bend.
    /// Z is up; XY is floor. Replace with measured geometry before hardware use.
    pub fn illustrative_five_axis() -> Self {
        let channel =
            |name: &str, axis_local, link_m, neutral_degrees, intent_mix_degrees| RigChannel {
                name: name.into(),
                axis_local,
                link_m,
                neutral_degrees,
                intent_mix_degrees,
                min_degrees: -110.0,
                max_degrees: 110.0,
                max_speed_degrees_per_second: 240.0,
                max_acceleration_degrees_per_second2: 8000.0,
            };
        let mut rig = Self {
            channels: vec![
                channel(
                    "base_yaw",
                    [0.0, 0.0, 1.0],
                    [0.08, 0.0, 0.0],
                    0.0,
                    [70.0, 0.0, 0.0],
                ),
                channel(
                    "shoulder_bend",
                    [0.0, 1.0, 0.0],
                    [0.28, 0.0, 0.0],
                    -55.0,
                    [0.0, -60.0, 6.0],
                ),
                channel(
                    "second_local_yaw",
                    [0.0, 0.0, 1.0],
                    [0.0, 0.0, 0.0],
                    0.0,
                    [20.0, 0.0, -12.0],
                ),
                channel(
                    "elbow_bend",
                    [0.0, 1.0, 0.0],
                    [0.22, 0.0, 0.0],
                    35.0,
                    [0.0, 14.0, -65.0],
                ),
                channel(
                    "wrist_bend",
                    [0.0, 1.0, 0.0],
                    [0.16, 0.0, 0.0],
                    5.0,
                    [-6.0, 20.0, 22.0],
                ),
            ],
        };
        // Base spins freely (continuous rotation) so the hand can circle through
        // the back. A real build needs a slip ring or a servo without end stops.
        (rig.channels[0].min_degrees, rig.channels[0].max_degrees) = (-1e6, 1e6);
        rig
    }

    pub fn validate(&self) -> Result<(), String> {
        if self.channels.is_empty() || self.channels.len() > 32 {
            return Err("rig needs 1..=32 channels".into());
        }
        for (i, c) in self.channels.iter().enumerate() {
            let axis_norm = dot(c.axis_local, c.axis_local).sqrt();
            if !axis_norm.is_finite()
                || (axis_norm - 1.0).abs() > 1e-6
                || !c.link_m.iter().all(|v| v.is_finite())
                || !c.intent_mix_degrees.iter().all(|v| v.is_finite())
                || ![
                    c.neutral_degrees,
                    c.min_degrees,
                    c.max_degrees,
                    c.max_speed_degrees_per_second,
                    c.max_acceleration_degrees_per_second2,
                ]
                .iter()
                .all(|v| v.is_finite())
                || c.min_degrees >= c.max_degrees
                || !(c.min_degrees..=c.max_degrees).contains(&c.neutral_degrees)
                || c.max_speed_degrees_per_second <= 0.0
                || c.max_acceleration_degrees_per_second2 <= 0.0
            {
                return Err(format!("invalid rig channel {i}: {}", c.name));
            }
        }
        Ok(())
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct Placement {
    pub origin_m: [f64; 3],
    pub yaw_degrees: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct JointKnot {
    pub time: f64,
    pub joints_degrees: Vec<f64>,
    /// Shared tangent on both adjacent quintic segments, degrees/second.
    pub velocity_degrees_per_second: Vec<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct AgentTrack {
    pub id: u32,
    pub knots: Vec<JointKnot>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct EnsembleScore {
    pub duration: f64,
    pub rig: Rig,
    pub placements: Vec<Placement>,
    pub cues: Vec<IntentCue>,
    pub tracks: Vec<AgentTrack>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct AgentFrame {
    pub id: u32,
    pub joints_degrees: Vec<f64>,
    /// World-space points, metres: base then one endpoint per channel.
    pub world_points: Vec<[f64; 3]>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct VisualIntent {
    pub character: String,
    pub formation: String,
    pub source_activity: [f64; 4],
    pub confidence: f64,
    pub recall_from: Option<f64>,
    pub anticipation: Option<f64>,
    pub reason: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct EnsembleFrame {
    pub time_seconds: f64,
    pub cue_index: usize,
    pub agents: Vec<AgentFrame>,
    pub visual: VisualIntent,
}

impl EnsembleScore {
    /// Proves continuous position, speed, acceleration via quintic Bezier hulls.
    /// Shared knot velocity and zero acceleration give C2 joins.
    /// Does not prove inter-arm clearance.
    pub fn validate(&self) -> Result<(), String> {
        self.rig.validate()?;
        if !self.duration.is_finite()
            || self.duration <= 0.0
            || self.cues.is_empty()
            || self.tracks.is_empty()
            || self.tracks.len() != self.placements.len()
        {
            return Err("invalid ensemble score dimensions".into());
        }
        let mut end = 0.0;
        for (i, cue) in self.cues.iter().enumerate() {
            if !cue.start.is_finite()
                || !cue.end.is_finite()
                || (cue.start - end).abs() > 1e-6
                || cue.end <= cue.start
                || cue.end > self.duration + 1e-6
            {
                return Err(format!("invalid ensemble cue {i}"));
            }
            end = cue.end;
        }
        if (end - self.duration).abs() > 1e-6 {
            return Err("ensemble cues must cover duration".into());
        }
        for (i, (track, placement)) in self.tracks.iter().zip(&self.placements).enumerate() {
            if track.id as usize != i
                || track.knots.len() < 2
                || !placement.origin_m.iter().all(|v| v.is_finite())
                || !placement.yaw_degrees.is_finite()
                || track.knots[0].time != 0.0
                || (track.knots.last().unwrap().time - self.duration).abs() > 1e-6
            {
                return Err(format!("invalid agent track {i}"));
            }
            for knot in &track.knots {
                if !knot.time.is_finite()
                    || knot.joints_degrees.len() != self.rig.channels.len()
                    || knot.velocity_degrees_per_second.len() != self.rig.channels.len()
                    || !knot
                        .velocity_degrees_per_second
                        .iter()
                        .all(|v| v.is_finite())
                {
                    return Err(format!("invalid knot dimensions for agent {i}"));
                }
                for (q, c) in knot.joints_degrees.iter().zip(&self.rig.channels) {
                    if !q.is_finite() || *q < c.min_degrees - 1e-9 || *q > c.max_degrees + 1e-9 {
                        return Err(format!("joint range exceeded for agent {i}"));
                    }
                }
            }
            for pair in track.knots.windows(2) {
                let dt = pair[1].time - pair[0].time;
                if !dt.is_finite() || dt <= 0.0 {
                    return Err(format!("nonincreasing knot times for agent {i}"));
                }
                for (j, c) in self.rig.channels.iter().enumerate() {
                    let bounds = channel_bounds(&pair[0], &pair[1], j)?;
                    if !within_bounds(&bounds, 0, c) {
                        return Err(format!(
                            "kinematic limit exceeded for agent {i} channel {j}"
                        ));
                    }
                }
            }
        }
        Ok(())
    }

    /// Absolute-time random access. No formation or musical decision runs here.
    pub fn sample(&self, time_seconds: f64) -> Result<EnsembleFrame, String> {
        if !time_seconds.is_finite() {
            return Err("sample time must be finite".into());
        }
        if self.cues.is_empty() || self.tracks.len() != self.placements.len() {
            return Err("invalid ensemble score".into());
        }
        let t = time_seconds.clamp(0.0, self.duration);
        let cue_index = if t >= self.duration {
            self.cues.len() - 1
        } else {
            self.cues
                .partition_point(|cue| cue.end <= t)
                .min(self.cues.len() - 1)
        };
        let cue = &self.cues[cue_index];
        let agents = self
            .tracks
            .iter()
            .zip(&self.placements)
            .map(|(track, placement)| {
                let joints_degrees = sample_track(&track.knots, t)?;
                let world_points = forward_kinematics(&self.rig, placement, &joints_degrees)?;
                Ok(AgentFrame {
                    id: track.id,
                    joints_degrees,
                    world_points,
                })
            })
            .collect::<Result<Vec<_>, String>>()?;
        Ok(EnsembleFrame {
            time_seconds: t,
            cue_index,
            agents,
            visual: VisualIntent {
                character: cue.character.clone(),
                formation: cue.formation.clone(),
                source_activity: cue.source_activity,
                confidence: cue.confidence,
                recall_from: cue.recall_from,
                anticipation: cue.anticipation,
                reason: cue.reason.clone(),
            },
        })
    }
}

pub fn compile_ensemble(
    interpretation: &Interpretation,
    rig: Rig,
    agent_count: usize,
) -> Result<EnsembleScore, String> {
    rig.validate()?;
    if !(1..=256).contains(&agent_count) {
        return Err("agent count needs 1..=256".into());
    }
    if !interpretation.duration.is_finite()
        || interpretation.duration <= 0.0
        || interpretation.cues.is_empty()
    {
        return Err("interpretation duration/cues invalid".into());
    }
    let mut previous_end = 0.0;
    for (i, cue) in interpretation.cues.iter().enumerate() {
        if !cue.start.is_finite()
            || !cue.end.is_finite()
            || (cue.start - previous_end).abs() > 1e-6
            || cue.end <= cue.start
            || cue.end > interpretation.duration + 1e-6
            || cue.profile.len() < 2
            || !cue
                .profile
                .iter()
                .flatten()
                .all(|v| v.is_finite() && (-1.0..=1.0).contains(v))
        {
            return Err(format!("invalid intent cue {i}"));
        }
        previous_end = cue.end;
    }
    if interpretation.cues[0].start > 1e-6 || previous_end < interpretation.duration - 1e-6 {
        return Err("intent cues must cover duration".into());
    }
    let topology = Topology::ring(agent_count as u32);
    let radius = if agent_count < 2 {
        0.0
    } else {
        (0.35 / (std::f64::consts::PI / agent_count as f64).sin()).max(0.6)
    };
    let placements = (0..agent_count)
        .map(|i| {
            let a = std::f64::consts::TAU * i as f64 / agent_count as f64;
            Placement {
                origin_m: [radius * a.cos(), radius * a.sin(), 0.0],
                yaw_degrees: a.to_degrees(),
            }
        })
        .collect::<Vec<_>>();
    let offsets = interpretation
        .cues
        .iter()
        .map(|cue| formation_offsets(cue, &topology))
        .collect::<Vec<_>>();
    // Director samples at sub-beat resolution. Servo travel needs broader knots;
    // retain all cue edges and query continuous intent at each chosen timestamp.
    let knot_spacing = (interpretation.beat_period / 4.0).max(0.1);
    let mut times = interpretation
        .cues
        .iter()
        .flat_map(|cue| {
            (0..cue.profile.len()).map(|i| {
                cue.start + (cue.end - cue.start) * i as f64 / (cue.profile.len() - 1) as f64
            })
        })
        .collect::<Vec<_>>();
    times.push(0.0);
    times.push(interpretation.duration);
    times.sort_by(f64::total_cmp);
    times.dedup_by(|a, b| (*a - *b).abs() < 1e-9);
    let cue_edges = interpretation
        .cues
        .iter()
        .flat_map(|c| [c.start, c.end])
        .collect::<Vec<_>>();
    let mut last_kept = -knot_spacing;
    times.retain(|&time| {
        let edge = cue_edges.iter().any(|&e| (time - e).abs() < 1e-9);
        if edge || time - last_kept >= knot_spacing {
            last_kept = time;
            true
        } else {
            false
        }
    });
    let mut tracks = (0..agent_count)
        .map(|i| AgentTrack {
            id: i as u32,
            knots: Vec::with_capacity(times.len()),
        })
        .collect::<Vec<_>>();
    let mut slopes = vec![vec![0.0; rig.channels.len()]; agent_count];
    for &time in &times {
        let cue_index = if time >= interpretation.duration {
            interpretation.cues.len() - 1
        } else {
            interpretation
                .cues
                .partition_point(|cue| cue.end <= time)
                .min(interpretation.cues.len() - 1)
        };
        let cue = &interpretation.cues[cue_index];
        let mut proposed: Vec<Vec<f64>> = Vec::with_capacity(agent_count);
        for (i, track) in tracks.iter().enumerate() {
            let prior = track.knots.last();
            let target = if let Some(prior) = prior.filter(|_| is_rest(cue)) {
                prior.joints_degrees.clone()
            } else {
                let local_time = (time - offsets[cue_index][i].0).clamp(cue.start, cue.end);
                let mut intent = sample_profile(cue, local_time);
                if offsets[cue_index][i].1 {
                    intent[0] = -intent[0];
                }
                rig.channels
                    .iter()
                    .map(|channel| {
                        (channel.neutral_degrees + dot(intent, channel.intent_mix_degrees))
                            .clamp(channel.min_degrees, channel.max_degrees)
                    })
                    .collect::<Vec<_>>()
            };
            // Second-order follower: bound slope and slope change, so servo
            // limits hold without throttling every step to a rest-to-rest move.
            let joints_degrees = match prior {
                Some(prior) => {
                    let dt = time - prior.time;
                    rig.channels
                        .iter()
                        .enumerate()
                        .map(|(j, channel)| {
                            let v_prev = slopes[i][j];
                            let a = if track.knots.len() < 2 { 0.05 } else { 0.12 }
                                * channel.max_acceleration_degrees_per_second2
                                * dt;
                            let v_max = 0.5 * channel.max_speed_degrees_per_second;
                            let wanted = (target[j] - prior.joints_degrees[j]) / dt;
                            let slope = wanted.clamp(v_prev - a, v_prev + a).clamp(-v_max, v_max);
                            (prior.joints_degrees[j] + slope * dt)
                                .clamp(channel.min_degrees, channel.max_degrees)
                        })
                        .collect()
                }
                None => target,
            };
            let reference = prior.map_or_else(
                || rig.channels.iter().map(|c| c.neutral_degrees).collect(),
                |p| p.joints_degrees.clone(),
            );
            proposed.push(floor_safe(
                &rig,
                &placements[i],
                &reference,
                joints_degrees,
            )?);
        }
        separate_agents(&rig, &placements, &tracks, &mut proposed)?;
        for (i, track) in tracks.iter_mut().enumerate() {
            if let Some(prior) = track.knots.last() {
                let dt = time - prior.time;
                for j in 0..rig.channels.len() {
                    slopes[i][j] = (proposed[i][j] - prior.joints_degrees[j]) / dt;
                }
            }
            track.knots.push(JointKnot {
                time,
                joints_degrees: std::mem::take(&mut proposed[i]),
                velocity_degrees_per_second: slopes[i].clone(),
            });
        }
    }
    for track in &mut tracks {
        fit_tangents(track, &rig)?;
    }
    let score = EnsembleScore {
        duration: interpretation.duration,
        rig,
        placements,
        cues: interpretation.cues.clone(),
        tracks,
    };
    score.validate()?;
    Ok(score)
}

/// Keep every link above the floor. Bisect from a feasible reference pose toward
/// the candidate; margin covers sag between sparse knots. Floor is Z=0 (site data).
fn floor_safe(
    rig: &Rig,
    placement: &Placement,
    reference: &[f64],
    candidate: Vec<f64>,
) -> Result<Vec<f64>, String> {
    const MARGIN_M: f64 = 0.07;
    let ok = |q: &[f64]| -> Result<bool, String> {
        for u in [1.0 / 3.0, 2.0 / 3.0, 1.0] {
            let mid: Vec<f64> = reference
                .iter()
                .zip(q)
                .map(|(r, c)| r + (c - r) * u)
                .collect();
            if !forward_kinematics(rig, placement, &mid)?
                .iter()
                .skip(2)
                .all(|p| p[2] >= MARGIN_M)
            {
                return Ok(false);
            }
        }
        Ok(true)
    };
    if ok(&candidate)? {
        return Ok(candidate);
    }
    let blend = |s: f64| -> Vec<f64> {
        reference
            .iter()
            .zip(&candidate)
            .map(|(r, c)| r + (c - r) * s)
            .collect()
    };
    if !ok(reference)? {
        return Err("reference pose below floor; rig/placement unusable".into());
    }
    let (mut lo, mut hi) = (0.0, 1.0);
    for _ in 0..30 {
        let mid = 0.5 * (lo + hi);
        if ok(&blend(mid))? {
            lo = mid;
        } else {
            hi = mid;
        }
    }
    Ok(blend(lo))
}

/// Minimum distance between any two links of different arms must stay above the
/// clearance. Bisect both arms back toward their prior (feasible) poses.
const ARM_CLEARANCE_M: f64 = 0.14;

fn separate_agents(
    rig: &Rig,
    placements: &[Placement],
    tracks: &[AgentTrack],
    proposed: &mut [Vec<f64>],
) -> Result<(), String> {
    let n = proposed.len();
    if n < 2 {
        return Ok(());
    }
    let prior: Vec<Vec<f64>> = tracks
        .iter()
        .map(|t| {
            t.knots.last().map_or_else(
                || rig.channels.iter().map(|c| c.neutral_degrees).collect(),
                |k| k.joints_degrees.clone(),
            )
        })
        .collect();
    // Check the end pose and two interpolated poses: arms move up to ~0.1 m per knot.
    let pair_ok = |i: usize, j: usize, ci: &[f64], cj: &[f64]| -> Result<bool, String> {
        for u in [1.0 / 3.0, 2.0 / 3.0, 1.0] {
            let mix = |from: &[f64], to: &[f64]| -> Vec<f64> {
                from.iter().zip(to).map(|(f, t)| f + (t - f) * u).collect()
            };
            let a = forward_kinematics(rig, &placements[i], &mix(&prior[i], ci))?;
            let b = forward_kinematics(rig, &placements[j], &mix(&prior[j], cj))?;
            let clear = a.windows(2).all(|x| {
                b.windows(2)
                    .all(|y| segment_distance(x[0], x[1], y[0], y[1]) >= ARM_CLEARANCE_M)
            });
            if !clear {
                return Ok(false);
            }
        }
        Ok(true)
    };
    for _ in 0..n * n {
        let mut hit = None;
        'find: for i in 0..n {
            for j in i + 1..n {
                if !pair_ok(i, j, &proposed[i], &proposed[j])? {
                    hit = Some((i, j));
                    break 'find;
                }
            }
        }
        let Some((i, j)) = hit else {
            return Ok(());
        };
        let (ti, tj) = (proposed[i].clone(), proposed[j].clone());
        let blend = |s: f64| -> (Vec<f64>, Vec<f64>) {
            let mix = |r: &[f64], c: &[f64]| -> Vec<f64> {
                r.iter().zip(c).map(|(r, c)| r + (c - r) * s).collect()
            };
            (mix(&prior[i], &ti), mix(&prior[j], &tj))
        };
        let (mut lo, mut hi) = (0.0, 1.0);
        for _ in 0..24 {
            let mid = 0.5 * (lo + hi);
            let (qi, qj) = blend(mid);
            if pair_ok(i, j, &qi, &qj)? {
                lo = mid;
            } else {
                hi = mid;
            }
        }
        // lo = 0 holds both arms at their prior poses.
        (proposed[i], proposed[j]) = blend(lo);
    }
    Ok(())
}

/// Closest distance between segments p1-q1 and p2-q2 (Ericson, Real-Time Collision Detection).
fn segment_distance(p1: [f64; 3], q1: [f64; 3], p2: [f64; 3], q2: [f64; 3]) -> f64 {
    let sub = |a: [f64; 3], b: [f64; 3]| -> [f64; 3] { std::array::from_fn(|i| a[i] - b[i]) };
    let (d1, d2, r) = (sub(q1, p1), sub(q2, p2), sub(p1, p2));
    let (a, e, f) = (dot(d1, d1), dot(d2, d2), dot(d2, r));
    let (s, t);
    if a <= 1e-12 && e <= 1e-12 {
        (s, t) = (0.0, 0.0);
    } else if a <= 1e-12 {
        (s, t) = (0.0, (f / e).clamp(0.0, 1.0));
    } else {
        let c = dot(d1, r);
        if e <= 1e-12 {
            (s, t) = ((-c / a).clamp(0.0, 1.0), 0.0);
        } else {
            let b = dot(d1, d2);
            let denom = a * e - b * b;
            let mut s0 = if denom > 1e-12 {
                ((b * f - c * e) / denom).clamp(0.0, 1.0)
            } else {
                0.0
            };
            let mut t0 = (b * s0 + f) / e;
            if t0 < 0.0 {
                t0 = 0.0;
                s0 = (-c / a).clamp(0.0, 1.0);
            } else if t0 > 1.0 {
                t0 = 1.0;
                s0 = ((b - c) / a).clamp(0.0, 1.0);
            }
            (s, t) = (s0, t0);
        }
    }
    let c1: [f64; 3] = std::array::from_fn(|i| p1[i] + d1[i] * s);
    let c2: [f64; 3] = std::array::from_fn(|i| p2[i] + d2[i] * t);
    dot(sub(c1, c2), sub(c1, c2)).sqrt()
}

fn formation_offsets(cue: &IntentCue, topology: &Topology) -> Vec<(f64, bool)> {
    let duration = cue.end - cue.start;
    let base = Move {
        channels: BTreeMap::new(),
        duration: Duration::Seconds((duration * 0.3) as f32),
        entry_pose: PoseRequirement::Agnostic,
        exit_pose: PoseRequirement::Agnostic,
        arrival_anchor: None,
        role: TimescaleRole::Groove,
        effort: Effort::NEUTRAL,
        applicability_tags: Vec::new(),
        intensity: 1.0,
        provenance: Provenance::Generated,
    };
    let anchor = TimingAnchor {
        start_time: cue.start,
        seconds_per_beat: 1.0,
    };
    let instructions = match cue.formation.as_str() {
        "canon" | "wave" => canon(topology, &base, anchor, &OrderingSource::Spatial),
        _ => unison(topology, &base, anchor),
    };
    let instructions = if cue.formation == "mirror" {
        apply_mirror(topology, &[ChannelRole::PrimaryElevation], instructions)
    } else {
        instructions
    };
    let order = effective_order(topology, &OrderingSource::Spatial);
    let mut result = vec![(0.0, false); topology.agents.len()];
    for instr in instructions {
        let i = order.iter().position(|id| *id == instr.agent).unwrap();
        let offset = if cue.formation == "scatter" {
            duration * 0.17 * i as f64 / topology.agents.len() as f64
        } else {
            instr.time_offset
        };
        result[i] = (
            offset,
            instr
                .mirror
                .inverted_channels
                .contains(&ChannelRole::PrimaryElevation),
        );
    }
    result
}

fn is_rest(cue: &IntentCue) -> bool {
    cue.character == "silence"
        || cue.character == "rest"
        || cue.character == "hold"
        || cue.profile.iter().all(|v| *v == [0.0; 3])
}

fn sample_profile(cue: &IntentCue, t: f64) -> [f64; 3] {
    let position = ((t - cue.start) / (cue.end - cue.start) * (cue.profile.len() - 1) as f64)
        .clamp(0.0, (cue.profile.len() - 1) as f64);
    let i = (position.floor() as usize).min(cue.profile.len() - 2);
    let u = position - i as f64;
    std::array::from_fn(|j| cue.profile[i][j] * (1.0 - u) + cue.profile[i + 1][j] * u)
}

fn sample_track(knots: &[JointKnot], t: f64) -> Result<Vec<f64>, String> {
    let first = knots.first().ok_or("empty agent track")?;
    if t <= first.time {
        return Ok(first.joints_degrees.clone());
    }
    let last = knots.last().unwrap();
    if t >= last.time {
        return Ok(last.joints_degrees.clone());
    }
    let right = knots.partition_point(|k| k.time < t);
    let a = &knots[right - 1];
    let b = &knots[right];
    let mut out = Vec::with_capacity(a.joints_degrees.len());
    for base in (0..a.joints_degrees.len()).step_by(3) {
        let values = sample_segment(&pack_knot(a, base), &pack_knot(b, base), t);
        out.extend(
            values
                .into_iter()
                .take((a.joints_degrees.len() - base).min(3)),
        );
    }
    Ok(out)
}

fn pack_knot(k: &JointKnot, base: usize) -> Knot {
    Knot {
        time: k.time,
        phase: String::new(),
        joints: std::array::from_fn(|j| k.joints_degrees.get(base + j).copied().unwrap_or(0.0)),
        velocity: std::array::from_fn(|j| {
            k.velocity_degrees_per_second
                .get(base + j)
                .copied()
                .unwrap_or(0.0)
        }),
        acceleration: [0.0; 3],
    }
}

fn within_bounds(bounds: &crate::SegmentBounds, j: usize, c: &RigChannel) -> bool {
    bounds.min_position_degrees[j] >= c.min_degrees - 1e-7
        && bounds.max_position_degrees[j] <= c.max_degrees + 1e-7
        && bounds.max_speed_degrees_per_second[j] <= c.max_speed_degrees_per_second + 1e-7
        && bounds.max_acceleration_degrees_per_second2[j]
            <= c.max_acceleration_degrees_per_second2 + 1e-7
}

fn channel_bounds(a: &JointKnot, b: &JointKnot, j: usize) -> Result<crate::SegmentBounds, String> {
    let single = |k: &JointKnot| Knot {
        time: k.time,
        phase: String::new(),
        joints: [k.joints_degrees[j], 0.0, 0.0],
        velocity: [k.velocity_degrees_per_second[j], 0.0, 0.0],
        acceleration: [0.0; 3],
    };
    let start = single(a);
    let end = single(b);
    if start.velocity == [0.0; 3] && end.velocity == [0.0; 3] {
        return segment_bounds(&start, &end).map_err(|e| e.to_string());
    }
    let dt = end.time - start.time;
    if !dt.is_finite() || dt <= 0.0 {
        return Err("invalid segment duration".into());
    }
    let p0 = start.joints[0];
    let p5 = end.joints[0];
    let v0 = start.velocity[0];
    let v1 = end.velocity[0];
    let p = [
        p0,
        p0 + v0 * dt / 5.0,
        p0 + 2.0 * v0 * dt / 5.0,
        p5 - 2.0 * v1 * dt / 5.0,
        p5 - v1 * dt / 5.0,
        p5,
    ];
    let velocity = std::array::from_fn::<_, 5, _>(|i| 5.0 * (p[i + 1] - p[i]) / dt);
    let acceleration =
        std::array::from_fn::<_, 4, _>(|i| 4.0 * (velocity[i + 1] - velocity[i]) / dt);
    let (min, max) = bezier_extents(p, 6);
    let (min_v, max_v) = bezier_extents(velocity, 6);
    let (min_a, max_a) = bezier_extents(acceleration, 6);
    Ok(crate::SegmentBounds {
        min_position_degrees: [min, 0.0, 0.0],
        max_position_degrees: [max, 0.0, 0.0],
        max_speed_degrees_per_second: [min_v.abs().max(max_v.abs()), 0.0, 0.0],
        max_acceleration_degrees_per_second2: [min_a.abs().max(max_a.abs()), 0.0, 0.0],
    })
}

/// Subdivision tightens Bezier control hulls while retaining continuous guarantees.
fn bezier_extents<const N: usize>(controls: [f64; N], depth: u8) -> (f64, f64) {
    if depth == 0 {
        return (
            controls.iter().copied().fold(f64::INFINITY, f64::min),
            controls.iter().copied().fold(f64::NEG_INFINITY, f64::max),
        );
    }
    let mut work = controls;
    let mut left = [0.0; N];
    let mut right = [0.0; N];
    for i in 0..N {
        left[i] = work[0];
        right[N - 1 - i] = work[N - 1 - i];
        for j in 0..N - 1 - i {
            work[j] = (work[j] + work[j + 1]) * 0.5;
        }
    }
    let a = bezier_extents(left, depth - 1);
    let b = bezier_extents(right, depth - 1);
    (a.0.min(b.0), a.1.max(b.1))
}

pub(crate) fn fit_tangents(track: &mut AgentTrack, rig: &Rig) -> Result<(), String> {
    // Knot velocities come from the second-order follower in compile_ensemble;
    // only shrink them where a segment's continuous bounds still exceed limits.
    let len = track.knots.len();
    for _ in 0..24 {
        let mut changed = false;
        for i in 0..len - 1 {
            for (j, c) in rig.channels.iter().enumerate() {
                let bounds = channel_bounds(&track.knots[i], &track.knots[i + 1], j)?;
                if !within_bounds(&bounds, 0, c) {
                    track.knots[i].velocity_degrees_per_second[j] *= 0.5;
                    track.knots[i + 1].velocity_degrees_per_second[j] *= 0.5;
                    changed = true;
                }
            }
        }
        if !changed {
            return Ok(());
        }
    }
    // Last resort: bring a still-infeasible segment's end tangents to rest
    // (rest-to-rest quintics fit by construction of the follower limits).
    for _ in 0..len {
        let mut changed = false;
        for i in 0..len - 1 {
            for (j, c) in rig.channels.iter().enumerate() {
                let b = channel_bounds(&track.knots[i], &track.knots[i + 1], j)?;
                if !within_bounds(&b, 0, c) {
                    track.knots[i].velocity_degrees_per_second[j] = 0.0;
                    track.knots[i + 1].velocity_degrees_per_second[j] = 0.0;
                    changed = true;
                }
            }
        }
        if !changed {
            return Ok(());
        }
    }
    for i in 0..len - 1 {
        for (j, c) in rig.channels.iter().enumerate() {
            let b = channel_bounds(&track.knots[i], &track.knots[i + 1], j)?;
            if !within_bounds(&b, 0, c) {
                return Err(format!(
                    "cannot fit tangents segment {i} channel {j}: q {:.3}..{:.3}, speed {:.3}/{:.3}, accel {:.3}/{:.3}",
                    b.min_position_degrees[0],
                    b.max_position_degrees[0],
                    b.max_speed_degrees_per_second[0],
                    c.max_speed_degrees_per_second,
                    b.max_acceleration_degrees_per_second2[0],
                    c.max_acceleration_degrees_per_second2
                ));
            }
        }
    }
    Err("cannot fit continuous ensemble tangents within limits".into())
}

/// FK applies each axis in its carried local frame, then advances its link.
pub fn forward_kinematics(
    rig: &Rig,
    placement: &Placement,
    joints_degrees: &[f64],
) -> Result<Vec<[f64; 3]>, String> {
    if joints_degrees.len() != rig.channels.len() || !joints_degrees.iter().all(|v| v.is_finite()) {
        return Err("joint count/value mismatch".into());
    }
    let mut points = vec![placement.origin_m];
    let mut basis = [
        rotate([1.0, 0.0, 0.0], [0.0, 0.0, 1.0], placement.yaw_degrees),
        rotate([0.0, 1.0, 0.0], [0.0, 0.0, 1.0], placement.yaw_degrees),
        [0.0, 0.0, 1.0],
    ];
    let mut p = placement.origin_m;
    for (channel, angle) in rig.channels.iter().zip(joints_degrees) {
        let axis_world = basis_mul(&basis, channel.axis_local);
        for b in &mut basis {
            *b = rotate(*b, axis_world, *angle);
        }
        let link_world = basis_mul(&basis, channel.link_m);
        p = std::array::from_fn(|i| p[i] + link_world[i]);
        points.push(p);
    }
    Ok(points)
}

fn dot(a: [f64; 3], b: [f64; 3]) -> f64 {
    a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
}
fn cross(a: [f64; 3], b: [f64; 3]) -> [f64; 3] {
    [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]
}
fn basis_mul(b: &[[f64; 3]; 3], v: [f64; 3]) -> [f64; 3] {
    std::array::from_fn(|i| b[0][i] * v[0] + b[1][i] * v[1] + b[2][i] * v[2])
}
fn rotate(v: [f64; 3], axis: [f64; 3], degrees: f64) -> [f64; 3] {
    let (sin, cos) = degrees.to_radians().sin_cos();
    let perpendicular = cross(axis, v);
    let parallel = dot(axis, v) * (1.0 - cos);
    std::array::from_fn(|i| v[i] * cos + perpendicular[i] * sin + axis[i] * parallel)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture(formation: &str) -> Interpretation {
        Interpretation {
            duration: 3.0,
            beat_period: 0.5,
            beat_zero: 0.0,
            cues: vec![IntentCue {
                start: 0.0,
                end: 3.0,
                character: "active".into(),
                formation: formation.into(),
                source_activity: [0.8, 0.5, 0.7, 0.2],
                confidence: 0.8,
                recall_from: None,
                anticipation: Some(2.0),
                reason: "measured phrase".into(),
                profile: vec![
                    [0.0, 0.0, 0.0],
                    [1.0, 0.7, -0.7],
                    [-0.8, 0.2, 0.8],
                    [0.0, 0.0, 0.0],
                ],
            }],
        }
    }

    #[test]
    fn n1_and_n6_seek_and_formation() {
        let rig = Rig::illustrative_five_axis();
        for n in [1, 6] {
            let score = compile_ensemble(&fixture("canon"), rig.clone(), n).unwrap();
            assert_eq!(score.sample(1.3).unwrap(), score.sample(1.3).unwrap());
            assert_eq!(score.sample(1.3).unwrap().agents.len(), n);
            assert_eq!(score.sample(1.3).unwrap().agents[0].world_points.len(), 6);
            assert_eq!(score.sample(2.9).unwrap().visual.anticipation, Some(2.0));
            if n == 6 {
                assert_ne!(
                    score.sample(1.3).unwrap().agents[0].joints_degrees,
                    score.sample(1.3).unwrap().agents[5].joints_degrees
                );
            }
        }
        let one = compile_ensemble(&fixture("canon"), rig.clone(), 1).unwrap();
        assert!(
            one.tracks[0].knots[1..one.tracks[0].knots.len() - 1]
                .iter()
                .flat_map(|k| &k.velocity_degrees_per_second)
                .any(|v| v.abs() > 0.01),
            "groove must continue through internal knots"
        );
        let unison = compile_ensemble(&fixture("unison"), rig, 1).unwrap();
        assert_eq!(
            one.sample(1.3).unwrap().agents[0].joints_degrees,
            unison.sample(1.3).unwrap().agents[0].joints_degrees
        );
    }

    #[test]
    fn links_stay_above_floor_under_extreme_intent() {
        let mut interpretation = fixture("canon");
        interpretation.cues[0].profile = (0..31)
            .map(|i| {
                if i % 2 == 0 {
                    [1.0, -1.0, -1.0]
                } else {
                    [-1.0, 1.0, 1.0]
                }
            })
            .collect();
        let score = compile_ensemble(&interpretation, Rig::illustrative_five_axis(), 3).unwrap();
        for k in 0..=300 {
            let frame = score.sample(3.0 * k as f64 / 300.0).unwrap();
            for agent in &frame.agents {
                let low = agent
                    .world_points
                    .iter()
                    .skip(2)
                    .map(|p| p[2])
                    .fold(f64::MAX, f64::min);
                // Knots are floor-checked at 5 cm margin; quintic sag between sparse knots stays small.
                assert!(low >= -0.02, "t={} z={low}", frame.time_seconds);
            }
        }
    }

    #[test]
    fn local_yaw_follows_upstream_bend() {
        let mut rig = Rig::illustrative_five_axis();
        rig.channels = vec![
            RigChannel {
                axis_local: [0.0, 1.0, 0.0],
                link_m: [0.0; 3],
                ..rig.channels[1].clone()
            },
            RigChannel {
                axis_local: [0.0, 0.0, 1.0],
                link_m: [1.0, 0.0, 0.0],
                ..rig.channels[2].clone()
            },
        ];
        let pts = forward_kinematics(
            &rig,
            &Placement {
                origin_m: [0.0; 3],
                yaw_degrees: 0.0,
            },
            &[90.0, 90.0],
        )
        .unwrap();
        assert!(
            pts[2][1] > 0.99,
            "local yaw must rotate link in carried plane: {pts:?}"
        );
        assert!(pts[2][2].abs() < 1e-9);
    }

    #[test]
    fn continuous_segment_limits_and_rest_hold() {
        let mut interpretation = fixture("mirror");
        interpretation.duration = 4.0;
        interpretation.cues[0].end = 3.0;
        interpretation.cues.push(IntentCue {
            start: 3.0,
            end: 4.0,
            character: "silence".into(),
            formation: "breathe".into(),
            source_activity: [0.0; 4],
            confidence: 0.9,
            recall_from: None,
            anticipation: None,
            reason: "silence".into(),
            profile: vec![[0.0; 3]; 2],
        });
        let score = compile_ensemble(&interpretation, Rig::illustrative_five_axis(), 6).unwrap();
        let before_rest = score.sample(3.0).unwrap();
        assert_eq!(
            before_rest.agents[0].joints_degrees,
            score.sample(4.0).unwrap().agents[0].joints_degrees
        );
        let dt = 0.005;
        let mut prev = score.sample(0.0).unwrap();
        let mut last_velocity = vec![vec![0.0; score.rig.channels.len()]; 6];
        for step in 1..=800 {
            let now = score.sample(step as f64 * dt).unwrap();
            for (i, agent) in now.agents.iter().enumerate() {
                for (j, &q) in agent.joints_degrees.iter().enumerate() {
                    let c = &score.rig.channels[j];
                    assert!(q >= c.min_degrees - 1e-8 && q <= c.max_degrees + 1e-8);
                    let v = (q - prev.agents[i].joints_degrees[j]) / dt;
                    assert!(v.abs() <= c.max_speed_degrees_per_second + 0.01);
                    if step > 1 {
                        let a = (v - last_velocity[i][j]) / dt;
                        assert!(a.abs() <= c.max_acceleration_degrees_per_second2 + 2.0);
                    }
                    last_velocity[i][j] = v;
                }
            }
            prev = now;
        }
    }
}
