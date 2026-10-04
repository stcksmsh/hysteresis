//! Offline dance compiler: shared quintic segment maths plus the figure planner.

use serde::{Deserialize, Serialize};

pub mod director;
pub mod ensemble;

const Q_V: f64 = 1.875; // max derivative of 6t^5-15t^4+10t^3
const Q_A: f64 = 5.773_502_691_896_258;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Knot {
    pub time: f64,
    pub phase: String,
    pub joints: [f64; 3],
    /// Joint velocity in degrees/second. Missing legacy fields deserialize as rest.
    #[serde(default, skip_serializing_if = "is_zero_derivative")]
    pub velocity: [f64; 3],
    /// Joint acceleration in degrees/second². Missing legacy fields deserialize as rest.
    #[serde(default, skip_serializing_if = "is_zero_derivative")]
    pub acceleration: [f64; 3],
}

fn is_zero_derivative(value: &[f64; 3]) -> bool {
    *value == [0.0; 3]
}

/// Conservative continuous bounds for one quintic-Hermite score segment.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct SegmentBounds {
    pub min_position_degrees: [f64; 3],
    pub max_position_degrees: [f64; 3],
    pub max_speed_degrees_per_second: [f64; 3],
    pub max_acceleration_degrees_per_second2: [f64; 3],
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct CompileConfig {
    pub enable_hits: bool,
    /// Recall an earlier measured phrase signature; false uses current content.
    pub reuse_repeats: bool,
    /// Body: how far the wrist's preferred bend trails the hand's vertical
    /// speed, degrees per m/s. 0 turns it off. 240 chosen by the user in a
    /// blind side-by-side over 0 and 120; it about triples wrist travel, so
    /// lower it if real wrist or elbow servos cannot keep up.
    pub wrist_drag_degrees_per_mps: f64,
    /// Temporary review knob: 0 flourishes as before, 1 none, 2 slow and soft.
    pub flourish: u8,
    /// Temporary review knob: how far hand size and height follow the leading
    /// lane's swell. 0 off.
    pub swell: f64,
}
impl Default for CompileConfig {
    fn default() -> Self {
        Self {
            enable_hits: true,
            reuse_repeats: true,
            wrist_drag_degrees_per_mps: 240.0,
            flourish: 0,
            swell: 0.0,
        }
    }
}

/// Sample one segment using endpoint position, velocity, and acceleration.
///
/// Zero derivatives preserve legacy `6t⁵ - 15t⁴ + 10t³` interpolation exactly.
pub fn sample_segment(start: &Knot, end: &Knot, time: f64) -> [f64; 3] {
    let dt = end.time - start.time;
    let x = ((time - start.time) / dt).clamp(0.0, 1.0);
    if segment_has_zero_derivatives(start, end) {
        let q = x * x * x * (10.0 + x * (-15.0 + 6.0 * x));
        return std::array::from_fn(|j| start.joints[j] + (end.joints[j] - start.joints[j]) * q);
    }
    std::array::from_fn(|joint| {
        let mut points = bezier_controls(start, end, joint);
        for width in (1..points.len()).rev() {
            for i in 0..width {
                points[i] += (points[i + 1] - points[i]) * x;
            }
        }
        points[0]
    })
}

/// Prove range, speed, and acceleration bounds for one score segment.
///
/// Derivative-bearing segments use degree-5 Bezier control hulls. Bounds are
/// conservative: every continuous value lies inside its corresponding hull.
/// Legacy zero-derivative segments retain exact quintic speed/acceleration extrema.
pub fn segment_bounds(start: &Knot, end: &Knot) -> Result<SegmentBounds, &'static str> {
    let dt = end.time - start.time;
    if !dt.is_finite() || dt <= 0.0 {
        return Err("segment duration must be finite and positive");
    }
    for joint in 0..3 {
        for value in [
            start.joints[joint],
            end.joints[joint],
            start.velocity[joint],
            end.velocity[joint],
            start.acceleration[joint],
            end.acceleration[joint],
        ] {
            if !value.is_finite() {
                return Err("segment position and derivatives must be finite");
            }
        }
    }

    let mut bounds = SegmentBounds {
        min_position_degrees: [0.0; 3],
        max_position_degrees: [0.0; 3],
        max_speed_degrees_per_second: [0.0; 3],
        max_acceleration_degrees_per_second2: [0.0; 3],
    };
    for joint in 0..3 {
        if segment_has_zero_derivatives(start, end) {
            let distance = (end.joints[joint] - start.joints[joint]).abs();
            bounds.min_position_degrees[joint] = start.joints[joint].min(end.joints[joint]);
            bounds.max_position_degrees[joint] = start.joints[joint].max(end.joints[joint]);
            bounds.max_speed_degrees_per_second[joint] = distance * Q_V / dt;
            bounds.max_acceleration_degrees_per_second2[joint] = distance * Q_A / dt.powi(2);
            continue;
        }

        let points = bezier_controls(start, end, joint);
        bounds.min_position_degrees[joint] = points.iter().copied().fold(f64::INFINITY, f64::min);
        bounds.max_position_degrees[joint] =
            points.iter().copied().fold(f64::NEG_INFINITY, f64::max);
        bounds.max_speed_degrees_per_second[joint] = points
            .windows(2)
            .map(|pair| (5.0 * (pair[1] - pair[0]) / dt).abs())
            .fold(0.0, f64::max);
        bounds.max_acceleration_degrees_per_second2[joint] = points
            .windows(3)
            .map(|triple| (20.0 * (triple[2] - 2.0 * triple[1] + triple[0]) / dt.powi(2)).abs())
            .fold(0.0, f64::max);
    }
    Ok(bounds)
}

fn segment_has_zero_derivatives(start: &Knot, end: &Knot) -> bool {
    is_zero_derivative(&start.velocity)
        && is_zero_derivative(&end.velocity)
        && is_zero_derivative(&start.acceleration)
        && is_zero_derivative(&end.acceleration)
}

fn bezier_controls(start: &Knot, end: &Knot, joint: usize) -> [f64; 6] {
    let dt = end.time - start.time;
    let dt2 = dt * dt;
    let p0 = start.joints[joint];
    let p5 = end.joints[joint];
    let v0 = start.velocity[joint];
    let v1 = end.velocity[joint];
    let a0 = start.acceleration[joint];
    let a1 = end.acceleration[joint];
    [
        p0,
        p0 + v0 * dt / 5.0,
        p0 + 2.0 * v0 * dt / 5.0 + a0 * dt2 / 20.0,
        p5 - 2.0 * v1 * dt / 5.0 + a1 * dt2 / 20.0,
        p5 - v1 * dt / 5.0,
        p5,
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn legacy_knots_default_to_rest_derivatives_and_keep_exact_quintic() {
        let start: Knot =
            serde_json::from_str(r#"{"time":0.0,"phase":"start","joints":[100.0,-65.0,-20.0]}"#)
                .unwrap();
        let end: Knot =
            serde_json::from_str(r#"{"time":1.0,"phase":"end","joints":[110.0,-65.0,-20.0]}"#)
                .unwrap();
        assert_eq!(start.velocity, [0.0; 3]);
        assert_eq!(start.acceleration, [0.0; 3]);
        assert_eq!(sample_segment(&start, &end, 0.5)[0], 105.0);
        let bounds = segment_bounds(&start, &end).unwrap();
        assert_eq!(bounds.min_position_degrees[0], 100.0);
        assert_eq!(bounds.max_position_degrees[0], 110.0);
        assert_eq!(bounds.max_speed_degrees_per_second[0], 18.75);
        assert_eq!(bounds.max_acceleration_degrees_per_second2[0], 10.0 * Q_A);
        let encoded = serde_json::to_value(start).unwrap();
        assert!(encoded.get("velocity").is_none());
        assert!(encoded.get("acceleration").is_none());
    }

    #[test]
    fn quintic_hermite_samples_endpoint_derivatives_and_has_proven_hulls() {
        let start = Knot {
            time: 2.0,
            phase: "start".into(),
            joints: [100.0, -65.0, -20.0],
            velocity: [4.0, -2.0, 1.0],
            acceleration: [1.0, 0.5, -0.25],
        };
        let end = Knot {
            time: 4.0,
            phase: "end".into(),
            joints: [110.0, -70.0, -18.0],
            velocity: [-3.0, 1.0, 0.5],
            acceleration: [0.5, -0.5, 0.25],
        };
        assert_eq!(sample_segment(&start, &end, start.time), start.joints);
        assert_eq!(sample_segment(&start, &end, end.time), end.joints);
        let h = 1e-4;
        for joint in 0..3 {
            let p0 = sample_segment(&start, &end, start.time)[joint];
            let p1 = sample_segment(&start, &end, start.time + h)[joint];
            let p2 = sample_segment(&start, &end, start.time + 2.0 * h)[joint];
            assert!(((p1 - p0) / h - start.velocity[joint]).abs() < 0.001);
            assert!(((p2 - 2.0 * p1 + p0) / h.powi(2) - start.acceleration[joint]).abs() < 0.01);
        }
        let bounds = segment_bounds(&start, &end).unwrap();
        for i in 0..=1_000 {
            let pose = sample_segment(&start, &end, 2.0 + 2.0 * i as f64 / 1_000.0);
            for (joint, position) in pose.iter().enumerate() {
                assert!(*position >= bounds.min_position_degrees[joint]);
                assert!(*position <= bounds.max_position_degrees[joint]);
            }
        }
    }
}
