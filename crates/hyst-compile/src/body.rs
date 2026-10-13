//! Body study generator (`docs/BODY_STUDY.md`): one arm, silent, 8 s, moving in
//! joint space from a body vector. No music, no mind. Rules for check 2a live
//! here so they are in code before any result they score.

use crate::director::IntentCue;
use crate::ensemble::{
    forward_kinematics, AgentTrack, EnsembleScore, Implement, JointKnot, Placement, Rig,
};

pub const PARAMS: [&str; 12] = [
    "curl_extension",
    "height",
    "arch",
    "time",
    "weight",
    "flow",
    "space",
    "succession_direction",
    "succession_delay",
    "initiation",
    "breath_depth",
    "breath_rate",
];
/// Every value 0..1. Order as in `PARAMS`.
pub type Body = [f64; 12];

pub const CLIP_SECONDS: f64 = 8.0;
const KNOT_DT: f64 = 0.05;
pub const FPS: f64 = 60.0;
/// Stretch ladder: 1.1^0 .. 1.1^7 (= 1.95).
pub const STRETCH_STEPS: u32 = 7;

// Check 2a limits (user, 2026-10-13).
pub const SPEED_DPS: f64 = 150.0;
pub const ACCEL_DPS2: f64 = 500.0;
pub const HAND_MPS: f64 = 1.2;
pub const JOLT_MPS2: f64 = 9.0;
pub const FLOOR_M: f64 = 0.05;
pub const DISC_M: f64 = 0.06;
/// Straight reach from the shoulder to the hand point: 0.28 + 0.22 + 0.08 + 0.11.
const REACH_M: f64 = 0.69;

pub fn study_rig() -> Rig {
    let mut rig = Rig::illustrative_five_axis();
    rig.implement = Implement::disc();
    for c in &mut rig.channels {
        c.max_speed_degrees_per_second = SPEED_DPS;
        c.max_acceleration_degrees_per_second2 = ACCEL_DPS2;
    }
    rig
}

struct Rng(u64);
impl Rng {
    fn next(&mut self) -> f64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        ((z ^ (z >> 31)) >> 11) as f64 / (1u64 << 53) as f64
    }
    fn sign(&mut self) -> f64 {
        if self.next() < 0.5 {
            -1.0
        } else {
            1.0
        }
    }
}

/// Attempt `index` of the sampling stream (fixed seed 20261013): a uniform body
/// vector and its content seed.
pub fn draw(index: u64) -> (Body, u64) {
    let mut rng = Rng(20_261_013u64.wrapping_add(index.wrapping_mul(0x2545_F491_4F6C_DD1D)));
    let b = std::array::from_fn(|_| rng.next());
    (b, (rng.next() * (1u64 << 53) as f64) as u64)
}

fn lerp(a: f64, b: f64, x: f64) -> f64 {
    a + (b - a) * x
}
fn minjerk(x: f64) -> f64 {
    let x = x.clamp(0.0, 1.0);
    x * x * x * (10.0 - 15.0 * x + 6.0 * x * x)
}

/// Shoulder, elbow, wrist bend angles for a shape (curl_extension, height, arch).
/// Negative bend lifts the link. Ranges and reasons:
/// - height: shoulder elevation 10..95 degrees (below 10 the straight arm skims
///   the 5 cm floor; above 95 the breath and overshoot would pass the ±110 stop);
/// - curl_extension: elbow bend 95 (curled) .. 5 (straight), but never so far that
///   the forearm points more than 40 degrees below horizontal (the floor);
/// - arch: wrist against elbow (0) or with it (1), up to 0.45 of the elbow bend
///   plus 10 degrees, so arch still reads on a straight arm.
fn posture(extension: f64, height: f64, arch: f64) -> [f64; 3] {
    let e1 = lerp(10.0, 95.0, height);
    let q2 = lerp(95.0, 5.0, extension).min(e1 + 40.0);
    let q3 = ((2.0 * arch - 1.0) * (0.45 * q2 + 10.0)).clamp(-110.0, 110.0);
    [-e1, q2, q3]
}

struct Move {
    start: f64,
    /// Whole transition, seconds (before per-joint delay).
    dur: f64,
    peaks: usize,
    delta: [f64; 5],
    wander_sign: [f64; 2],
}

struct Motion {
    p0: [f64; 5],
    moves: Vec<Move>,
    delay: [f64; 5],
    skew: f64,
    overshoot: f64,
    ring_hz: f64,
    ring_decay: f64,
    wander: [f64; 2],
    breath: [f64; 2],
    breath_hz: f64,
    breath_phase: f64,
}

impl Motion {
    fn new(b: &Body, seed: u64) -> Self {
        let [ext, height, arch, time, weight, flow, space, dir, delay, init, bdepth, brate] = *b;
        let mut rng = Rng(seed ^ 0xA5A5_5A5A_1234_5678);
        // Weight: depth of each move (0.3..1) and the arrival skew. Skew < 1 floats
        // into the end (fast start, soft tail); > 1 is a firm stop (late, brisk end).
        let depth = lerp(0.3, 1.0, weight);
        let skew = lerp(0.75, 1.4, weight);
        let p = posture(ext, height, arch);
        let p0 = [0.0, p[0], p[1], p[2], 0.0];
        // Succession: 0..0.3 s spread along the chain; direction flips at 0.5.
        // Initiation: base, shoulder, elbow or wrist leads (0.12 s ahead, 1.35x depth).
        let lead = ((init * 4.0) as usize).min(3);
        let mut d = [0.0; 5];
        for (j, dj) in d.iter_mut().enumerate() {
            let rank = if dir < 0.5 { j } else { 4 - j } as f64;
            *dj = 0.3 * delay * rank / 4.0 + if j == lead { 0.0 } else { 0.12 };
        }
        let peaks = 1 + (2.0 * time).round() as usize;
        let mut moves = Vec::new();
        let (mut t, mut cur) = (0.2, p0);
        while t < 7.4 {
            let slot = 1.0 + 0.8 * rng.next();
            let dur = slot * lerp(0.95, 0.45, time);
            let clamp01 = |v: f64| v.clamp(0.0, 1.0);
            let q = posture(
                clamp01(ext + depth * 0.4 * (rng.next() - 0.5) * 2.0),
                clamp01(height + depth * 0.35 * (rng.next() - 0.5) * 2.0),
                clamp01(arch + depth * 0.3 * (rng.next() - 0.5) * 2.0),
            );
            let yaw = rng.sign() * (25.0 + 65.0 * rng.next()) * depth;
            let roll = rng.sign() * (30.0 + 120.0 * rng.next()) * lerp(0.3, 1.0, space) * depth;
            let target = [yaw, q[0], q[1], q[2], roll];
            // Authoring budget: a burst of amplitude A over time d peaks near
            // 5.77 A g^2 / d^2 deg/s2 (g = arrival skew, either way), the quintic
            // with zero knot acceleration adds up to 1.5x, so the burst's amplitude
            // is capped at 0.45 of the acceleration limit and 0.8 of the speed limit.
            // A sudden move therefore stays small; that is the arm's range, not a bug.
            let bursts = peaks as f64;
            let d_burst = if peaks > 1 { dur / bursts * 0.7 } else { dur };
            let g2 = skew.max(1.0 / skew).powi(2);
            let cap = bursts
                * (0.45 * ACCEL_DPS2 * d_burst * d_burst / (5.77 * g2))
                    .min(0.8 * SPEED_DPS * d_burst / 1.875);
            let mut delta = [0.0; 5];
            for j in 0..5 {
                let want = (target[j] - cur[j]) * if j == lead { 1.35 } else { 1.0 };
                delta[j] = want.clamp(-cap, cap);
                cur[j] += delta[j];
            }
            moves.push(Move {
                start: t,
                dur,
                peaks,
                delta,
                wander_sign: [rng.sign(), rng.sign()],
            });
            t += slot;
        }
        Self {
            p0,
            moves,
            delay: d,
            skew,
            overshoot: 0.15 * flow,
            ring_hz: lerp(0.8, 1.4, flow),
            ring_decay: lerp(0.15, 0.6, flow),
            // Indirect: yaw wanders ±15 degrees and roll ±30 on the way to each target.
            wander: [15.0 * space, 30.0 * space],
            // Breath: shoulder up to 8 degrees, elbow 12, period 3.3..12 s.
            breath: [8.0 * bdepth, 12.0 * bdepth],
            breath_hz: lerp(0.08, 0.3, brate),
            breath_phase: rng.next() * std::f64::consts::TAU,
        }
    }

    /// Joint angles (yaw, shoulder, elbow, wrist bend, roll), degrees, motion time t.
    fn at(&self, t: f64) -> [f64; 5] {
        let mut q = self.p0;
        #[allow(clippy::needless_range_loop)] // j indexes q, delay and delta together
        for m in &self.moves {
            for j in 0..5 {
                let u = t - m.start - self.delay[j];
                if u <= 0.0 {
                    continue;
                }
                let tau = u / m.dur;
                // `peaks` bursts, each a min-jerk step skewed by `skew`, with rests between.
                let n = m.peaks as f64;
                let x = tau.clamp(0.0, 1.0) * n;
                let k = x.floor().min(n - 1.0);
                let local = x - k;
                let act = if m.peaks > 1 {
                    (local / 0.7).min(1.0)
                } else {
                    local
                };
                q[j] += m.delta[j] * (k + minjerk(act.powf(self.skew))) / n;
                // Free flow: damped follow-through after arrival.
                if tau > 1.0 && self.overshoot > 0.0 {
                    let after = u - m.dur;
                    let ramp = {
                        let r = (after / 0.15).clamp(0.0, 1.0);
                        minjerk(r)
                    };
                    q[j] += m.delta[j]
                        * self.overshoot
                        * ramp
                        * (-after / self.ring_decay).exp()
                        * (std::f64::consts::TAU * self.ring_hz * after).sin();
                }
                // Indirect space: yaw and roll bow off the straight path while moving.
                if (j == 0 || j == 4) && (0.0..1.0).contains(&tau) {
                    // One cycle over the move peaks at 2 pi w / dur; keep it under 0.35 of the speed limit.
                    let w =
                        self.wander[j / 4].min(0.35 * SPEED_DPS * m.dur / std::f64::consts::TAU);
                    q[j] += m.wander_sign[j / 4]
                        * w
                        * (std::f64::consts::TAU * tau).sin()
                        * (std::f64::consts::PI * tau).sin().powi(2);
                }
            }
        }
        let phi = std::f64::consts::TAU * self.breath_hz * t + self.breath_phase;
        q[1] -= self.breath[0] * phi.sin();
        q[2] -= self.breath[1] * phi.sin();
        q
    }
}

/// The 8 s clip for body `b`, content `seed` and stretch `s`: clip time t shows
/// motion time 4 + (t - 4)/s, so s > 1 shows the middle 8/s seconds, slower.
pub fn clip(b: &Body, seed: u64, s: f64) -> EnsembleScore {
    let motion = Motion::new(b, seed);
    let motion_time = |t: f64| 4.0 + (t - 4.0) / s;
    let n = (CLIP_SECONDS / KNOT_DT).round() as usize;
    let knots = (0..=n)
        .map(|i| {
            let t = i as f64 * KNOT_DT;
            let m = motion_time(t);
            let h = 1e-4;
            let (a, c) = (motion.at(m - h), motion.at(m + h));
            JointKnot {
                time: t,
                joints_degrees: motion.at(m).to_vec(),
                velocity_degrees_per_second: (0..5)
                    .map(|j| (c[j] - a[j]) / (2.0 * h) / s)
                    .collect(),
            }
        })
        .collect();
    EnsembleScore {
        duration: CLIP_SECONDS,
        rig: study_rig(),
        placements: vec![Placement {
            origin_m: [0.0; 3],
            yaw_degrees: 0.0,
        }],
        cues: vec![IntentCue {
            start: 0.0,
            end: CLIP_SECONDS,
            character: "study".into(),
            formation: "silent".into(),
            source_activity: [0.0; 4],
            confidence: 1.0,
            recall_from: None,
            anticipation: None,
            reason: "body study".into(),
            profile: vec![[0.0; 3]; 2],
        }],
        tracks: vec![AgentTrack { id: 0, knots }],
        workspace: None,
    }
}

/// Frames at 60 fps: joint angles and the six world points.
pub fn frames(score: &EnsembleScore) -> Vec<([f64; 5], Vec<[f64; 3]>)> {
    let n = (score.duration * FPS).round() as usize;
    (0..=n)
        .map(|i| {
            let f = score.sample(i as f64 / FPS).expect("sample");
            let a = &f.agents[0];
            let q = std::array::from_fn(|j| a.joints_degrees[j]);
            (q, a.world_points.clone())
        })
        .collect()
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Check2a {
    pub max_hand_mps: f64,
    pub max_jolt_mps2: f64,
    /// Smallest margin over the floor rule, metres (negative = violation).
    pub min_floor_margin_m: f64,
}

/// Check 2a on the score as rendered: the score's own proof of joint range, speed
/// and acceleration (the rig carries the study limits), then hand speed, jolt and
/// floor at 60 fps. Err names the first rule broken.
pub fn check_2a(score: &EnsembleScore) -> Result<Check2a, String> {
    score.validate()?;
    let fr = frames(score);
    let hand: Vec<[f64; 3]> = fr.iter().map(|f| f.1[5]).collect();
    let speed: Vec<f64> = hand
        .windows(2)
        .map(|w| {
            (0..3)
                .map(|k| (w[1][k] - w[0][k]).powi(2))
                .sum::<f64>()
                .sqrt()
                * FPS
        })
        .collect();
    let max_hand = speed.iter().copied().fold(0.0, f64::max);
    let max_jolt = speed
        .windows(2)
        .map(|w| (w[1] - w[0]).abs() * FPS)
        .fold(0.0, f64::max);
    let floor = fr
        .iter()
        .map(|f| {
            let z = f.1.iter().map(|p| p[2]);
            let ends = z.clone().skip(1).take(4).fold(f64::MAX, f64::min) - FLOOR_M;
            ends.min(f.1[5][2] - FLOOR_M - DISC_M)
        })
        .fold(f64::MAX, f64::min);
    let report = Check2a {
        max_hand_mps: max_hand,
        max_jolt_mps2: max_jolt,
        min_floor_margin_m: floor,
    };
    if max_hand > HAND_MPS {
        return Err(format!("hand speed {max_hand:.2} m/s"));
    }
    if max_jolt > JOLT_MPS2 {
        return Err(format!("hand jolt {max_jolt:.2} m/s2"));
    }
    if floor < 0.0 {
        return Err(format!("floor margin {floor:.3} m"));
    }
    Ok(report)
}

/// The first clip on the stretch ladder that passes check 2a, with its stretch.
/// None: rejected (stretching beyond 1.95 would show less than half the phrase).
pub fn feasible(b: &Body, seed: u64) -> Option<(f64, EnsembleScore)> {
    (0..=STRETCH_STEPS).find_map(|i| {
        let s = 1.1f64.powi(i as i32);
        let score = clip(b, seed, s);
        check_2a(&score).ok().map(|_| (s, score))
    })
}

pub const DESCRIPTOR_COUNT: usize = 37;

fn mean(v: &[f64]) -> f64 {
    v.iter().sum::<f64>() / v.len() as f64
}
fn p90(v: &[f64]) -> f64 {
    let mut s = v.to_vec();
    s.sort_by(|a, b| a.total_cmp(b));
    s[((s.len() - 1) as f64 * 0.9).round() as usize]
}
/// Best lag, seconds in -0.5..0.5, of the normalised cross-correlation of a and b
/// (positive: b follows a).
fn best_lag(a: &[f64], b: &[f64]) -> f64 {
    let norm = |v: &[f64]| {
        let m = mean(v);
        let sd = (v.iter().map(|x| (x - m).powi(2)).sum::<f64>() / v.len() as f64).sqrt();
        v.iter()
            .map(|x| if sd > 1e-12 { (x - m) / sd } else { 0.0 })
            .collect::<Vec<_>>()
    };
    let (a, b) = (norm(a), norm(b));
    let max_lag = (0.5 * FPS) as isize;
    let corr = |l: isize| {
        let (mut sum, mut n) = (0.0, 0);
        for i in 0..a.len() as isize {
            let k = i + l;
            if (0..b.len() as isize).contains(&k) {
                sum += a[i as usize] * b[k as usize];
                n += 1;
            }
        }
        sum / n as f64
    };
    let best = (-max_lag..=max_lag)
        .max_by(|x, y| corr(*x).total_cmp(&corr(*y)))
        .unwrap();
    best as f64 / FPS
}

/// 37 motion descriptors of the final 8 s at 60 fps (`docs/BODY_STUDY.md`):
/// per channel speed, acceleration and jerk (mean, p90) = 30; posture height,
/// extension, curl = 3; lag base>shoulder, shoulder>elbow, elbow>wrist = 3;
/// hand-speed periodicity = 1.
pub fn descriptors(score: &EnsembleScore) -> Vec<f64> {
    let fr = frames(score);
    let q: Vec<Vec<f64>> = (0..5)
        .map(|j| fr.iter().map(|f| f.0[j]).collect())
        .collect();
    let mut out = Vec::with_capacity(DESCRIPTOR_COUNT);
    let mut speeds = Vec::new();
    for series in &q {
        let d1: Vec<f64> = series
            .windows(2)
            .map(|w| (w[1] - w[0]).abs() * FPS)
            .collect();
        let d2: Vec<f64> = series
            .windows(3)
            .map(|w| (w[2] - 2.0 * w[1] + w[0]).abs() * FPS * FPS)
            .collect();
        let d3: Vec<f64> = series
            .windows(4)
            .map(|w| (w[3] - 3.0 * w[2] + 3.0 * w[1] - w[0]).abs() * FPS * FPS * FPS)
            .collect();
        for d in [&d1, &d2, &d3] {
            out.push(mean(d));
            out.push(p90(d));
        }
        speeds.push(d1);
    }
    out.push(mean(&fr.iter().map(|f| f.1[5][2]).collect::<Vec<_>>()));
    out.push(mean(
        &fr.iter()
            .map(|f| {
                let (s, h) = (f.1[1], f.1[5]);
                (0..3).map(|k| (h[k] - s[k]).powi(2)).sum::<f64>().sqrt() / REACH_M
            })
            .collect::<Vec<_>>(),
    ));
    out.push(mean(
        &fr.iter()
            .map(|f| f.0[2].abs() + f.0[3].abs())
            .collect::<Vec<_>>(),
    ));
    for (a, b) in [(0, 1), (1, 2), (2, 3)] {
        out.push(best_lag(&speeds[a], &speeds[b]));
    }
    let hand: Vec<f64> = fr
        .windows(2)
        .map(|w| {
            (0..3)
                .map(|k| (w[1].1[5][k] - w[0].1[5][k]).powi(2))
                .sum::<f64>()
                .sqrt()
                * FPS
        })
        .collect();
    let m = mean(&hand);
    let var: f64 = hand.iter().map(|x| (x - m).powi(2)).sum();
    let periodicity = ((0.3 * FPS) as usize..=(3.0 * FPS) as usize)
        .map(|l| {
            if var < 1e-12 {
                return 0.0;
            }
            (0..hand.len() - l)
                .map(|i| (hand[i] - m) * (hand[i + l] - m))
                .sum::<f64>()
                / var
        })
        .fold(f64::MIN, f64::max);
    out.push(periodicity);
    debug_assert_eq!(out.len(), DESCRIPTOR_COUNT);
    out
}

/// Hand point at a joint set (for tests and tools).
pub fn hand_at(joints: &[f64; 5]) -> [f64; 3] {
    let p = Placement {
        origin_m: [0.0; 3],
        yaw_degrees: 0.0,
    };
    forward_kinematics(&study_rig(), &p, joints).expect("fk")[5]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn same_inputs_same_clip_and_validates() {
        let b = [0.5; 12];
        let (a, c) = (clip(&b, 7, 1.0), clip(&b, 7, 1.0));
        assert_eq!(a, c);
        assert_ne!(a, clip(&b, 8, 1.0));
        assert_eq!(a.tracks[0].knots.len(), 161);
    }

    #[test]
    fn stretching_slows_motion_and_keeps_the_phrase_centre() {
        let b = [0.5, 0.6, 0.5, 0.5, 0.5, 0.5, 0.5, 0.2, 0.5, 0.3, 0.5, 0.5];
        let (one, two) = (clip(&b, 3, 1.0), clip(&b, 3, 2.0));
        // Centre of the clip is the same pose.
        let mid = |s: &EnsembleScore| s.tracks[0].knots[80].joints_degrees.clone();
        assert_eq!(mid(&one), mid(&two));
        let peak = |s: &EnsembleScore| {
            s.tracks[0]
                .knots
                .iter()
                .flat_map(|k| k.velocity_degrees_per_second.iter().map(|v| v.abs()))
                .fold(0.0, f64::max)
        };
        assert!(peak(&two) < peak(&one) * 0.75);
    }

    #[test]
    fn a_gentle_body_passes_2a_and_a_floor_dive_does_not() {
        let gentle = [0.8, 0.7, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5, 0.0, 0.3, 0.5];
        assert!(feasible(&gentle, 1).is_some());
        assert!(hand_at(&[0.0, 60.0, 80.0, 0.0, 0.0])[2] < FLOOR_M + DISC_M);
    }

    #[test]
    fn descriptor_count_and_finite() {
        let b = [0.4; 12];
        let d = descriptors(&clip(&b, 5, 1.5));
        assert_eq!(d.len(), DESCRIPTOR_COUNT);
        assert!(d.iter().all(|v| v.is_finite()));
    }
}
