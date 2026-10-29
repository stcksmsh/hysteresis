//! D3: a body vector sets the quality of the version-47 dance, and the dance is held to the body
//! generator's hardware numbers (`body::LIMITS`, `HAND_MPS`, `JOLT_MPS2`). The knob table is in
//! docs/DANCE_HANDOFF.md. `figures.rs` reads a `Layer` at each knob; with none, it is version 47.

use std::f64::consts::TAU;

use crate::body::{HAND_MPS, JOLT_MPS2, LIMITS};
use crate::body_track::BodyTrack;
use crate::ensemble::{hull_ratios, sample_track, EnsembleScore};

pub(super) struct Layer<'a> {
    pub track: &'a BodyTrack,
    /// Per grid knot: 1, or less where the figure clock runs slower to keep a limit.
    pub rate_scale: &'a [f64],
    /// Per moment: 1, or more where a moment takes a longer approach and release.
    pub span_scale: &'a [f64],
}

/// 1 at x = 0.5, `lo` at 0 and `hi` at 1, geometric between.
pub(super) fn geo(x: f64, lo: f64, hi: f64) -> f64 {
    if x < 0.5 {
        lo.powf(1.0 - 2.0 * x)
    } else {
        hi.powf(2.0 * x - 1.0)
    }
}

/// 0 up to 0.5, then 0 to 1 at 1.
pub(super) fn upper(x: f64) -> f64 {
    (2.0 * x - 1.0).max(0.0)
}

/// Figure size factor range (size 0 .. 1); the planner's own cap of 1 still applies.
pub(super) const SIZE: (f64, f64) = (0.55, 1.25);
/// Roll spin per metre of hand travel, energy 0 .. 1.
pub(super) const SPIN: (f64, f64) = (0.35, 1.8);
/// Depth of the stab surge, energy 0 .. 1.
pub(super) const SURGE: (f64, f64) = (0.5, 1.5);
/// Approach and release length of a moment, weight 0 (light) .. 1 (strong), and its hold.
pub(super) const SPAN: (f64, f64) = (1.5, 0.7);
pub(super) const HOLD: (f64, f64) = (0.7, 1.4);
/// Wrist trail, flow 0 (bound) .. 1 (free).
pub(super) const DRAG: (f64, f64) = (0.4, 1.5);
/// Overshoot of an arrival at flow 1, as a share of its travel.
pub(super) const OVERSHOOT: f64 = 0.25;
/// Shell units of hand elevation and extension at height 1 / curl_extension 1 (±, about 0.5).
pub(super) const HEIGHT: f64 = 0.5;
pub(super) const EXTENSION: f64 = 0.5;
/// Shell units of breath at depth 1: elevation, extension; and its rate in Hz at rate 0 / 1.
pub(super) const BREATH: (f64, f64) = (0.10, 0.06);
pub(super) const BREATH_HZ: (f64, f64) = (0.08, 0.3);
/// Joint lag: half of body.rs's succession numbers (0.3 s along the chain, 0.12 s off the leader).
pub(super) const LAG_CHAIN: f64 = 0.15;
pub(super) const LAG_OFF_LEADER: f64 = 0.06;
/// Peak beat kick of the figure clock at time 1 (a smooth bump peaking on the beat).
pub(super) const KICK: f64 = 1.2;
/// Follower acceleration share of a joint's limit (version 47: 0.1 of 8,000 deg/s2).
pub(super) const FOLLOW_ACCEL: f64 = 0.3;

/// The clock speed factor on beat phase `phase` (beats): 1 on average over a beat, peaking on the
/// beat when `time` is above 0.5 (sudden), 1 below.
pub(super) fn kick(time: f64, phase: f64) -> f64 {
    const POWER: i32 = 3;
    const MEAN: f64 = 20.0 / 64.0; // mean of ((1 + cos 2 pi x) / 2)^3 over a beat
    let bump = (0.5 * (1.0 + (TAU * phase).cos())).powi(POWER);
    1.0 + KICK * upper(time) * (bump - MEAN)
}

/// Seconds each joint's command trails the planner's, for body `b`: base to tip below
/// succession_direction 0.5, tip to base above; the initiating joint (base, shoulder, elbow or
/// wrist bend) is not held back the extra `LAG_OFF_LEADER`.
pub(super) fn lags(b: &[f64; 15]) -> [f64; 5] {
    let lead = ((b[9] * 4.0) as usize).min(3);
    std::array::from_fn(|j| {
        let rank = if b[7] < 0.5 { j } else { 4 - j } as f64;
        LAG_CHAIN * b[8] * rank / 4.0 + if j == lead { 0.0 } else { LAG_OFF_LEADER }
    })
}

/// Velocity and acceleration at every knot from the natural cubic spline through the knots (one
/// joint, `q` at `t`). The quintic Hermite between knots carrying these is that spline exactly, so
/// its speed and acceleration are the spline's: no stop forced at a held knot, and no start from rest
/// that the follower never made.
pub(super) fn spline_derivatives(t: &[f64], q: &[f64]) -> (Vec<f64>, Vec<f64>) {
    let n = t.len();
    let h: Vec<f64> = t.windows(2).map(|w| w[1] - w[0]).collect();
    // Second derivatives m: natural ends, tridiagonal interior (Thomas algorithm).
    let mut m = vec![0.0; n];
    if n > 2 {
        let (mut diag, mut rhs) = (vec![0.0; n], vec![0.0; n]);
        for i in 1..n - 1 {
            diag[i] = 2.0 * (h[i - 1] + h[i]);
            rhs[i] = 6.0 * ((q[i + 1] - q[i]) / h[i] - (q[i] - q[i - 1]) / h[i - 1]);
        }
        for i in 2..n - 1 {
            let w = h[i - 1] / diag[i - 1];
            diag[i] -= w * h[i - 1];
            rhs[i] -= w * rhs[i - 1];
        }
        for i in (1..n - 1).rev() {
            let above = if i + 1 < n - 1 { h[i] * m[i + 1] } else { 0.0 };
            m[i] = (rhs[i] - above) / diag[i];
        }
    }
    let v = (0..n)
        .map(|i| {
            if i + 1 < n {
                (q[i + 1] - q[i]) / h[i] - h[i] * (2.0 * m[i] + m[i + 1]) / 6.0
            } else {
                (q[i] - q[i - 1]) / h[i - 1] + h[i - 1] * (2.0 * m[i] + m[i - 1]) / 6.0
            }
        })
        .collect();
    (v, m)
}

/// How far over a limit the first arm is, per grid knot: 1 is at a limit. Joint speed and the
/// square root of joint acceleration on the rendered curve at 1 kHz, hand speed and the square
/// root of its jolt at 60 fps, each over its `body.rs` limit; the largest in each knot's step.
pub(super) fn demand(score: &EnsembleScore, grid: &[f64]) -> Vec<f64> {
    let step = grid[1] - grid[0];
    let mut need = vec![0.0f64; grid.len()];
    let bucket = |t: f64| ((t / step) as usize).min(grid.len() - 1);
    let dt = 1e-3;
    let n = (score.duration / dt).round() as usize;
    let q: Vec<Vec<f64>> = (0..=n)
        .map(|i| sample_track(&score.tracks[0].knots, i as f64 * dt).expect("sample"))
        .collect();
    for i in 1..n {
        let r = (0..5)
            .map(|j| {
                let v = (q[i + 1][j] - q[i - 1][j]).abs() / (2.0 * dt) / LIMITS[j].0;
                let a = (q[i + 1][j] - 2.0 * q[i][j] + q[i - 1][j]).abs() / (dt * dt) / LIMITS[j].1;
                v.max(a.sqrt())
            })
            .fold(0.0, f64::max);
        let b = bucket(i as f64 * dt);
        need[b] = need[b].max(r);
    }
    // The continuous bounds `validate` proves, which are looser than the samples above.
    let hull = hull_ratios(&score.tracks[0], &score.rig).expect("bounds");
    for (i, r) in hull.iter().enumerate() {
        let b = bucket(score.tracks[0].knots[i].time);
        need[b] = need[b].max(*r);
    }
    let fps = crate::body::FPS;
    let m = (score.duration * fps).round() as usize;
    let hand: Vec<[f64; 3]> = (0..=m)
        .map(|i| {
            *score.sample(i as f64 / fps).expect("sample").agents[0]
                .world_points
                .last()
                .unwrap()
        })
        .collect();
    let speed: Vec<f64> = hand
        .windows(2)
        .map(|w| {
            (0..3)
                .map(|k| (w[1][k] - w[0][k]).powi(2))
                .sum::<f64>()
                .sqrt()
                * fps
        })
        .collect();
    for (i, v) in speed.iter().enumerate() {
        let jolt = if i > 0 {
            (v - speed[i - 1]).abs() * fps
        } else {
            0.0
        };
        let b = bucket((i as f64 + 0.5) / fps);
        need[b] = need[b].max((v / HAND_MPS).max((jolt / JOLT_MPS2).sqrt()));
    }
    need
}

/// The next clock scale: where `need` is over `target`, slow the clock by the share it is over
/// (speed and the root of acceleration both scale with the clock), spread over `reach` knots each
/// way and smoothed, never below `floor`.
pub(super) fn slower(
    scale: &[f64],
    need: &[f64],
    target: f64,
    reach: usize,
    floor: f64,
) -> Vec<f64> {
    let n = scale.len();
    let want: Vec<f64> = need
        .iter()
        .map(|r| (target / r.max(1e-9)).min(1.0))
        .collect();
    let low: Vec<f64> = (0..n)
        .map(|i| {
            let (a, b) = (i.saturating_sub(reach), (i + reach + 1).min(n));
            want[a..b].iter().copied().fold(1.0, f64::min)
        })
        .collect();
    let sigma = 0.5 * reach as f64;
    (0..n)
        .map(|i| {
            let (mut sum, mut total) = (0.0, 0.0);
            let r = (3.0 * sigma).ceil() as isize;
            for d in -r..=r {
                let w = (-0.5 * (d as f64 / sigma).powi(2)).exp();
                sum += w * low[(i as isize + d).clamp(0, n as isize - 1) as usize];
                total += w;
            }
            // The smoothed dip is shallower than the dip: never above what the knot itself needs.
            (scale[i] * (sum / total).min(want[i])).max(floor)
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_spline_derivatives_match_a_cubic_exactly() {
        let t: Vec<f64> = (0..12)
            .map(|i| 0.07 * i as f64 + if i > 6 { 0.01 } else { 0.0 })
            .collect();
        // Natural ends only hold for a function with zero second derivative there; use a line plus
        // a bump that is flat at both ends.
        let q: Vec<f64> = t.iter().map(|x| 3.0 + 2.0 * x).collect();
        let (v, a) = spline_derivatives(&t, &q);
        assert!(v.iter().all(|v| (v - 2.0).abs() < 1e-9) && a.iter().all(|a| a.abs() < 1e-9));
        let held = vec![5.0; 12];
        let (v, a) = spline_derivatives(&t, &held);
        assert!(v.iter().chain(&a).all(|x| *x == 0.0));
    }

    #[test]
    fn geo_is_one_at_the_middle_and_hits_both_ends() {
        assert_eq!(geo(0.5, 0.3, 2.0), 1.0);
        assert!((geo(0.0, 0.3, 2.0) - 0.3).abs() < 1e-12);
        assert!((geo(1.0, 0.3, 2.0) - 2.0).abs() < 1e-12);
        assert!(geo(0.25, 0.3, 2.0) < 1.0 && geo(0.75, 0.3, 2.0) > 1.0);
        assert_eq!((upper(0.3), upper(0.5), upper(1.0)), (0.0, 0.0, 1.0));
    }

    #[test]
    fn the_kick_averages_one_over_a_beat_and_is_flat_below_a_half() {
        for time in [0.0, 0.5] {
            assert_eq!(kick(time, 0.37), 1.0);
        }
        let n = 10_000;
        let mean = (0..n).map(|i| kick(1.0, i as f64 / n as f64)).sum::<f64>() / n as f64;
        assert!((mean - 1.0).abs() < 1e-3, "{mean}");
        assert!(kick(1.0, 0.0) > 1.5 && kick(1.0, 0.5) < 1.0);
    }

    #[test]
    fn lags_follow_direction_delay_and_the_initiating_joint() {
        let mut b = [0.5; 15];
        (b[7], b[8], b[9]) = (0.0, 1.0, 0.0);
        let l = lags(&b);
        assert_eq!(l[0], 0.0);
        assert!(l.windows(2).all(|w| w[1] > w[0]));
        b[7] = 1.0;
        let l = lags(&b);
        assert!(l[4] < l[1] && l[0] > l[4]);
        b[8] = 0.0;
        assert_eq!(
            lags(&b),
            [
                0.0,
                LAG_OFF_LEADER,
                LAG_OFF_LEADER,
                LAG_OFF_LEADER,
                LAG_OFF_LEADER
            ]
        );
        b[9] = 0.3; // the shoulder initiates
        assert_eq!(lags(&b)[1], 0.0);
    }

    #[test]
    fn slower_cuts_the_clock_where_a_limit_is_over_and_keeps_it_elsewhere() {
        let scale = vec![1.0; 100];
        let mut need = vec![0.5; 100];
        need[50] = 2.0;
        let next = slower(&scale, &need, 1.0, 6, 0.2);
        assert!(next[50] <= 0.5 + 1e-9, "{}", next[50]);
        assert!(next[44] < 1.0 && next[0] == 1.0 && next[99] == 1.0);
        assert!(next.iter().all(|s| *s >= 0.2));
        assert_eq!(slower(&scale, &vec![0.9; 100], 1.0, 6, 0.2), scale);
    }
}
