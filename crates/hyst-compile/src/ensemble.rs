//! Offline interpretation → resolved, seekable 3D ensemble score.
//! Example rig geometry is illustrative; physical axes and calibration are site data.

use serde::{Deserialize, Serialize};

use crate::{director::IntentCue, sample_segment, segment_bounds, Knot};

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
    /// Provisional five-servo arm: base yaw, three bends, wrist roll.
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
                    // Shoulder sits on the yaw axis, up a short column.
                    [0.0, 0.0, 0.08],
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
                    "elbow_bend",
                    [0.0, 1.0, 0.0],
                    [0.22, 0.0, 0.0],
                    35.0,
                    [0.0, 14.0, -65.0],
                ),
                channel(
                    "wrist_bend",
                    [0.0, 1.0, 0.0],
                    [0.08, 0.0, 0.0],
                    5.0,
                    [-6.0, 20.0, 22.0],
                ),
                // Rolls the hand object about the wrist link. Its link is a
                // 5 cm stem plus the 6 cm radius of a disc held by its edge, so
                // it ends at the disc centre; the roll moves no point of the
                // chain and only turns the disc's face.
                channel(
                    "wrist_roll",
                    [1.0, 0.0, 0.0],
                    [0.11, 0.0, 0.0],
                    0.0,
                    [0.0, 0.0, 0.0],
                ),
            ],
        };
        // The roll carries a passive mirror, so it can also spin without end stops.
        (rig.channels[4].min_degrees, rig.channels[4].max_degrees) = (-1e6, 1e6);
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
    // Knot velocities come from the planner;
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
}
