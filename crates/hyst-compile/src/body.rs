//! Body study generator (`docs/BODY_STUDY.md`): one arm, silent, 16 s, moving in
//! joint space from a body vector. No music, no mind. Rules for check 2a live
//! here so they are in code before any result they score.

use crate::director::IntentCue;
use crate::ensemble::{
    forward_kinematics, sample_track, AgentTrack, EnsembleScore, Implement, JointKnot, Placement,
    Rig,
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

pub const CLIP_SECONDS: f64 = 16.0;
const KNOT_DT: f64 = 0.05;
pub const FPS: f64 = 60.0;
/// Stretch ladder: 1.1^0 .. 1.1^7 (= 1.95).
pub const STRETCH_STEPS: u32 = 7;

/// Joint names, in channel order.
pub const JOINTS: [&str; 5] = ["base_yaw", "shoulder", "elbow", "wrist_bend", "wrist_roll"];
/// Check 2a per-joint limits for cheap servos (`docs/BODY_STUDY.md` addendum
/// 2026-10-13): speed degrees/s, acceleration degrees/s2. The one place they live.
pub const LIMITS: [(f64, f64); 5] = [
    (120.0, 600.0),
    (90.0, 300.0),
    (150.0, 1000.0),
    (200.0, 2000.0),
    (250.0, 3000.0),
];
/// Sampling rate of the rendered-curve joint check.
const CHECK_HZ: f64 = 1000.0;
pub const HAND_MPS: f64 = 1.2;
pub const JOLT_MPS2: f64 = 9.0;
pub const FLOOR_M: f64 = 0.05;
pub const DISC_M: f64 = 0.06;
/// Minimum movement over the clip (addendum 2): the 10th percentile of version 47's
/// 16 s windows on arm 0 over the three songs.
pub const MIN_PATH_M: f64 = 3.67;
pub const MIN_BOX_M: f64 = 0.74;
pub const MIN_TURN_DEG: f64 = 161.0;
/// Straight reach from the shoulder to the hand point: 0.28 + 0.22 + 0.08 + 0.11.
const REACH_M: f64 = 0.69;

pub fn study_rig() -> Rig {
    // The rig keeps its own envelope (240 deg/s, 8000 deg/s2): `validate` must still
    // pass on it. The study limits are checked on the rendered curve instead.
    let mut rig = Rig::illustrative_five_axis();
    rig.implement = Implement::disc();
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

/// Position 0..1 of a move at x in 0..1: accelerate over the first `ra` of it,
/// decelerate over the last `rd`, cruise between. Each ramp is a smootherstep in
/// velocity, so acceleration and jerk stay continuous.
fn profile(x: f64, ra: f64, rd: f64) -> f64 {
    // integral of the smootherstep 6y^5 - 15y^4 + 10y^3
    let s = |y: f64| y.powi(6) - 3.0 * y.powi(5) + 2.5 * y.powi(4);
    let x = x.clamp(0.0, 1.0);
    let i = if x < ra {
        ra * s(x / ra)
    } else if x <= 1.0 - rd {
        ra / 2.0 + (x - ra)
    } else {
        ra / 2.0 + (1.0 - rd - ra) + rd * (0.5 - s((1.0 - x) / rd))
    };
    i / (1.0 - (ra + rd) / 2.0)
}

/// Smallest margin over the floor rule, metres, at joint set `q`.
fn floor_margin(rig: &Rig, q: &[f64; 5]) -> f64 {
    let p = Placement {
        origin_m: [0.0; 3],
        yaw_degrees: 0.0,
    };
    let w = forward_kinematics(rig, &p, q).expect("fk");
    let ends = w[1..5].iter().map(|p| p[2]).fold(f64::MAX, f64::min) - FLOOR_M;
    ends.min(w[5][2] - FLOOR_M - DISC_M)
}

struct Move {
    start: f64,
    /// The transition, seconds (before per-joint delay); the settle follows it.
    dur: f64,
    delta: [f64; 5],
    /// Free flow: elbow and wrist bend pass the target by this much, then settle.
    over: [f64; 5],
    /// Indirect space: signed bow amplitude on yaw and roll, degrees.
    wander: [f64; 2],
}

struct Motion {
    p0: [f64; 5],
    moves: Vec<Move>,
    delay: [f64; 5],
    ra: f64,
    rd: f64,
    /// Settle after the overshoot, as a fraction of the move's duration.
    settle: f64,
    breath: [f64; 2],
    breath_hz: f64,
    breath_phase: f64,
}

impl Motion {
    /// Offset of joint j from the move's start pose, x = time into the move / dur.
    fn offset(&self, m: &Move, j: usize, x: f64) -> f64 {
        if x <= 0.0 {
            return 0.0;
        }
        let mut v = if x < 1.0 {
            (m.delta[j] + m.over[j]) * profile(x, self.ra, self.rd)
        } else if x < 1.0 + self.settle {
            m.delta[j] + m.over[j] * (1.0 - minjerk((x - 1.0) / self.settle))
        } else {
            m.delta[j]
        };
        if (j == 0 || j == 4) && x < 1.0 {
            let (tau, pi) = (std::f64::consts::TAU, std::f64::consts::PI);
            v += m.wander[j / 4] * (tau * x).sin() * (pi * x).sin().powi(2);
        }
        v
    }

    /// Shortest duration at which move `m` from pose `from` keeps every joint inside
    /// its own limits `lim` and the hand inside its speed and jolt rules. Speeds scale
    /// as 1/T and accelerations (and jolt) as 1/T^2, so one pass at T = 1 gives it.
    /// Joint delays and breath are not in this pass; the stretch ladder covers them.
    fn min_dur(&self, m: &Move, from: &[f64; 5], rig: &Rig, lim: &[(f64, f64); 5]) -> f64 {
        let n = 2000;
        let h = (1.0 + self.settle) / n as f64;
        let q: Vec<[f64; 5]> = (0..=n)
            .map(|i| std::array::from_fn(|j| from[j] + self.offset(m, j, i as f64 * h)))
            .collect();
        let mut t = 0.0f64;
        for (j, &(lv, la)) in lim.iter().enumerate() {
            let v = q.windows(2).map(|w| (w[1][j] - w[0][j]).abs() / h);
            let a = q
                .windows(3)
                .map(|w| (w[2][j] - 2.0 * w[1][j] + w[0][j]).abs() / (h * h));
            t = t
                .max(v.fold(0.0, f64::max) / lv)
                .max((a.fold(0.0, f64::max) / la).sqrt());
        }
        let p = Placement {
            origin_m: [0.0; 3],
            yaw_degrees: 0.0,
        };
        let hand: Vec<[f64; 3]> = q
            .iter()
            .map(|q| forward_kinematics(rig, &p, q).expect("fk")[5])
            .collect();
        let speed: Vec<f64> = hand
            .windows(2)
            .map(|w| {
                (0..3)
                    .map(|k| (w[1][k] - w[0][k]).powi(2))
                    .sum::<f64>()
                    .sqrt()
                    / h
            })
            .collect();
        let jolt = speed
            .windows(2)
            .map(|w| (w[1] - w[0]).abs() / h)
            .fold(0.0, f64::max);
        t.max(speed.iter().copied().fold(0.0, f64::max) / HAND_MPS)
            .max((jolt / JOLT_MPS2).sqrt())
    }

    /// Ranges and why (`docs/BODY_STUDY.md` addendum 2: travel like the dance).
    /// - Travel: every phrase goes between postures spread over the reachable space.
    ///   Base yaw alternates sides of a span of 220..320 degrees (each target in the
    ///   outer 35 % of its side), so the hand crosses sides on every move; the shoulder
    ///   alternates between the lowest and highest 35 % of its draw, so the hand
    ///   crosses heights. Shape (curl_extension, height, arch) biases where in the
    ///   space the targets fall (0.25 of the draw), never whether they spread.
    ///   A target whose path or pose (breath at either extreme) breaks the floor is
    ///   drawn again, up to 30 times.
    /// - Time: velocity ramps cover 100 % (sustained, a bell) to 45 % (sudden, a
    ///   quick cruise) of the move. Each move takes its shortest legal duration times
    ///   1.7 (sustained, no hold) to 1.0 (sudden), then holds still for
    ///   time x 0.6..1.4 s while the breath runs.
    /// - Weight: the deceleration ramp's share of the ramps, 65 % (light, floats into
    ///   the end) to 30 % (strong, firm stop).
    /// - Flow: elbow and wrist bend pass their target by 25 % x flow of their move and
    ///   settle back over 0.4 x sqrt(flow) of the move's duration: one overshoot, no ring.
    /// - Space: yaw bows up to 15 degrees and roll 30 on the way; the roll's own turn
    ///   per move is 30..150 degrees x 0.3..1.
    /// - Succession and initiation: 0..0.3 s along the chain, base to tip below 0.5;
    ///   the leading joint starts 0.12 s ahead of the rest.
    /// - Breath: shoulder up to 8 degrees, elbow 12, period 3.3..12 s.
    ///
    /// Limits: each joint's own (`LIMITS`, roll speed capped at the rig's 240 deg/s
    /// envelope so `validate` can pass), less the breath's exact peak on shoulder and
    /// elbow. No other margin.
    fn new(b: &Body, seed: u64) -> Self {
        let [ext, height, arch, time, weight, flow, space, dir, delay, init, bdepth, brate] = *b;
        let mut rng = Rng(seed ^ 0xA5A5_5A5A_1234_5678);
        let rig = study_rig();
        let lead = ((init * 4.0) as usize).min(3);
        let mut d = [0.0; 5];
        for (j, dj) in d.iter_mut().enumerate() {
            let rank = if dir < 0.5 { j } else { 4 - j } as f64;
            *dj = 0.3 * delay * rank / 4.0 + if j == lead { 0.0 } else { 0.12 };
        }
        let ramps = lerp(1.0, 0.45, time);
        let rd = ramps * lerp(0.65, 0.3, weight);
        let breath = [8.0 * bdepth, 12.0 * bdepth];
        let breath_hz = lerp(0.08, 0.3, brate);
        let mut lim = LIMITS;
        for (j, l) in lim.iter_mut().enumerate() {
            l.0 = l.0.min(rig.channels[j].max_speed_degrees_per_second);
            if j == 1 || j == 2 {
                let w = std::f64::consts::TAU * breath_hz;
                l.0 -= breath[j - 1] * w;
                l.1 -= breath[j - 1] * w * w;
            }
        }
        let mut motion = Self {
            p0: [0.0; 5],
            moves: Vec::new(),
            delay: d,
            ra: ramps - rd,
            rd,
            settle: 0.4 * flow.sqrt(),
            breath,
            breath_hz,
            breath_phase: 0.0,
        };
        // Floor margin along a path, breath at either extreme.
        let clear = |q: &[f64; 5]| {
            [-1.0, 1.0].iter().all(|s| {
                let mut q = *q;
                q[1] -= breath[0] * s;
                q[2] -= breath[1] * s;
                floor_margin(&rig, &q) >= 0.0
            })
        };
        let span = lerp(220.0, 320.0, rng.next());
        let side0 = rng.sign();
        let high0 = rng.next() < 0.5;
        let (mut t, mut cur, mut k) = (0.2, [0.0; 5], 0usize);
        while t < CLIP_SECONDS {
            let side = if k % 2 == 0 { side0 } else { -side0 };
            let yaw = side * (span / 2.0 - 0.35 * span / 2.0 * rng.next());
            let high = (k % 2 == 0) == high0;
            let roll = cur[4] + rng.sign() * lerp(30.0, 150.0, rng.next()) * lerp(0.3, 1.0, space);
            let wander = [rng.sign() * 15.0 * space, rng.sign() * 30.0 * space];
            let mut m = None;
            for _ in 0..30 {
                let hu = 0.35 * rng.next() + if high { 0.65 } else { 0.0 };
                let q = posture(
                    0.75 * rng.next() + 0.25 * ext,
                    0.75 * hu + 0.25 * height,
                    0.75 * rng.next() + 0.25 * arch,
                );
                let target = [yaw, q[0], q[1], q[2], roll];
                let delta: [f64; 5] = std::array::from_fn(|j| target[j] - cur[j]);
                let mut over = [0.0; 5];
                for (j, room) in [(2, 110.0 - breath[1]), (3, 110.0)] {
                    over[j] = (target[j] + 0.25 * flow * delta[j]).clamp(-room, room) - target[j];
                }
                let mv = Move {
                    start: t,
                    dur: 1.0,
                    delta,
                    over,
                    wander,
                };
                let ok = if k == 0 {
                    clear(&target)
                } else {
                    (0..=60).all(|i| {
                        let x = i as f64 / 60.0 * (1.0 + motion.settle);
                        clear(&std::array::from_fn(|j| cur[j] + motion.offset(&mv, j, x)))
                    })
                };
                m = Some(mv);
                if ok {
                    break;
                }
            }
            let mut m = m.unwrap();
            if k == 0 {
                cur = std::array::from_fn(|j| cur[j] + m.delta[j]);
                motion.p0 = cur;
                k += 1;
                continue;
            }
            m.dur = motion.min_dur(&m, &cur, &rig, &lim) * lerp(1.7, 1.0, time);
            t += m.dur * (1.0 + motion.settle) + time * lerp(0.6, 1.4, rng.next());
            cur = std::array::from_fn(|j| cur[j] + m.delta[j]);
            motion.moves.push(m);
            k += 1;
        }
        motion.breath_phase = rng.next() * std::f64::consts::TAU;
        motion
    }

    /// Joint angles (yaw, shoulder, elbow, wrist bend, roll), degrees, motion time t.
    fn at(&self, t: f64) -> [f64; 5] {
        let mut q = self.p0;
        for m in &self.moves {
            for (j, qj) in q.iter_mut().enumerate() {
                *qj += self.offset(m, j, (t - m.start - self.delay[j]) / m.dur);
            }
        }
        let phi = std::f64::consts::TAU * self.breath_hz * t + self.breath_phase;
        q[1] -= self.breath[0] * phi.sin();
        q[2] -= self.breath[1] * phi.sin();
        q
    }
}

/// The 16 s clip for body `b`, content `seed` and stretch `s`: clip time t shows
/// motion time 8 + (t - 8)/s, so s > 1 shows the middle 16/s seconds, slower.
pub fn clip(b: &Body, seed: u64, s: f64) -> EnsembleScore {
    let motion = Motion::new(b, seed);
    let motion_time = |t: f64| 8.0 + (t - 8.0) / s;
    let n = (CLIP_SECONDS / KNOT_DT).round() as usize;
    let knots = (0..=n)
        .map(|i| {
            let t = i as f64 * KNOT_DT;
            let m = motion_time(t);
            let h = 1e-4;
            let (a, c) = (motion.at(m - h), motion.at(m + h));
            let g = 2e-3;
            let (lo, mid, hi) = (motion.at(m - g), motion.at(m), motion.at(m + g));
            JointKnot {
                acceleration_degrees_per_second2: (0..5)
                    .map(|j| (hi[j] - 2.0 * mid[j] + lo[j]) / (g * g) / (s * s))
                    .collect(),
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
    /// Hand path length (m), largest side of the hand's box (m), base turn range (deg).
    pub movement: [f64; 3],
}

/// Hand path length (m), largest side of the box the hand covers (m) and base yaw
/// range max - min (degrees), on 60 fps frames.
pub fn movement(fr: &[([f64; 5], Vec<[f64; 3]>)]) -> [f64; 3] {
    let path = fr
        .windows(2)
        .map(|w| {
            (0..3)
                .map(|k| (w[1].1[5][k] - w[0].1[5][k]).powi(2))
                .sum::<f64>()
                .sqrt()
        })
        .sum();
    let side = (0..3)
        .map(|k| {
            let v = fr.iter().map(|f| f.1[5][k]);
            v.clone().fold(f64::MIN, f64::max) - v.fold(f64::MAX, f64::min)
        })
        .fold(0.0, f64::max);
    let yaw = fr.iter().map(|f| f.0[0]);
    let turn = yaw.clone().fold(f64::MIN, f64::max) - yaw.fold(f64::MAX, f64::min);
    [path, side, turn]
}

/// Every check 2a rule the score breaks, each named (empty = feasible). Joint speed
/// and acceleration are measured on the rendered curve at 1 kHz (acceleration by
/// second difference); `validate` (the rig's own envelope) must also pass; hand
/// speed, jolt, floor and the minimum movement at 60 fps.
pub fn violations(score: &EnsembleScore) -> (Vec<String>, Check2a) {
    let mut out = Vec::new();
    if let Err(e) = score.validate() {
        out.push(format!("validate: {e}"));
    }
    let dt = 1.0 / CHECK_HZ;
    let n = (score.duration * CHECK_HZ).round() as usize;
    let q: Vec<Vec<f64>> = (0..=n)
        .map(|i| sample_track(&score.tracks[0].knots, i as f64 * dt).expect("sample"))
        .collect();
    for (j, &(v_lim, a_lim)) in LIMITS.iter().enumerate() {
        let v = q.windows(2).map(|w| (w[1][j] - w[0][j]).abs() / dt);
        let a = q
            .windows(3)
            .map(|w| (w[2][j] - 2.0 * w[1][j] + w[0][j]).abs() / (dt * dt));
        let (v, a) = (v.fold(0.0, f64::max), a.fold(0.0, f64::max));
        if v > v_lim {
            out.push(format!("{} speed", JOINTS[j]));
        }
        if a > a_lim {
            out.push(format!("{} accel", JOINTS[j]));
        }
    }
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
    if max_hand > HAND_MPS {
        out.push("hand speed".into());
    }
    if max_jolt > JOLT_MPS2 {
        out.push("hand jolt".into());
    }
    if floor < 0.0 {
        out.push("floor".into());
    }
    let mv = movement(&fr);
    for (k, (v, min)) in mv
        .iter()
        .zip([MIN_PATH_M, MIN_BOX_M, MIN_TURN_DEG])
        .enumerate()
    {
        if *v < min {
            out.push(["hand path", "hand box", "base turn"][k].into());
        }
    }
    (
        out,
        Check2a {
            max_hand_mps: max_hand,
            max_jolt_mps2: max_jolt,
            min_floor_margin_m: floor,
            movement: mv,
        },
    )
}

/// Check 2a: Err names the first rule broken.
pub fn check_2a(score: &EnsembleScore) -> Result<Check2a, String> {
    let (v, report) = violations(score);
    v.into_iter().next().map_or(Ok(report), Err)
}

/// The first clip on the stretch ladder that passes check 2a, with its stretch, and
/// the rules broken at stretch 1. None: rejected (stretching beyond 1.95 would show
/// less than half the phrase).
pub fn feasible_traced(b: &Body, seed: u64) -> (Option<(f64, EnsembleScore)>, Vec<String>) {
    let mut first = Vec::new();
    for i in 0..=STRETCH_STEPS {
        let s = 1.1f64.powi(i as i32);
        let score = clip(b, seed, s);
        let (v, _) = violations(&score);
        if i == 0 {
            first = v.clone();
        }
        if v.is_empty() {
            return (Some((s, score)), first);
        }
    }
    (None, first)
}

pub fn feasible(b: &Body, seed: u64) -> Option<(f64, EnsembleScore)> {
    feasible_traced(b, seed).0
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
        assert_eq!(a.tracks[0].knots.len(), 321);
    }

    #[test]
    fn stretching_slows_motion_and_keeps_the_phrase_centre() {
        let b = [0.5, 0.6, 0.5, 0.5, 0.5, 0.5, 0.5, 0.2, 0.5, 0.3, 0.5, 0.5];
        let (one, two) = (clip(&b, 3, 1.0), clip(&b, 3, 2.0));
        // Centre of the clip is the same pose.
        let mid = |s: &EnsembleScore| s.tracks[0].knots[160].joints_degrees.clone();
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
    fn rendered_curve_check_names_the_joint_and_limit() {
        let b = [0.8, 0.7, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5, 0.0, 0.3, 0.5];
        let (_, mut c) = feasible(&b, 1).unwrap();
        assert!(violations(&c).0.is_empty());
        // 40 degrees of yaw in 0.05 s: 800 deg/s, over the 120 deg/s base limit.
        c.tracks[0].knots[80].joints_degrees[0] += 40.0;
        let v = violations(&c).0;
        assert!(v.contains(&"base_yaw speed".to_string()), "{v:?}");
        assert!(!v.iter().any(|x| x.starts_with("wrist_roll")), "{v:?}");
    }

    #[test]
    fn sudden_is_one_move_then_a_hold_and_free_overshoots_elbow_and_wrist_only() {
        let mut b = [0.5; 12];
        (b[3], b[5]) = (1.0, 1.0);
        let m = Motion::new(&b, 11);
        assert!(m.moves.len() >= 3);
        for w in m.moves.windows(2) {
            let end = w[0].start + w[0].dur * (1.0 + m.settle);
            assert!(w[1].start - end >= 0.6 - 1e-9, "no hold");
        }
        for mv in &m.moves {
            assert!([0, 1, 4].iter().all(|&j| mv.over[j] == 0.0));
            assert!(mv.over[2].signum() == mv.delta[2].signum() || mv.over[2] == 0.0);
        }
        assert!(m.moves.iter().any(|mv| mv.over[2] != 0.0));
        // Sustained and bound: no hold, no overshoot.
        (b[3], b[5]) = (0.0, 0.0);
        let m = Motion::new(&b, 11);
        for w in m.moves.windows(2) {
            assert!((w[1].start - (w[0].start + w[0].dur)).abs() < 1e-9);
        }
        assert!(m.moves.iter().all(|mv| mv.over == [0.0; 5]));
    }

    #[test]
    fn profile_runs_zero_to_one_monotonically() {
        for (ra, rd) in [(0.5, 0.5), (0.3, 0.15), (0.1, 0.35)] {
            let v: Vec<f64> = (0..=100)
                .map(|i| profile(i as f64 / 100.0, ra, rd))
                .collect();
            assert!(v[0].abs() < 1e-12 && (v[100] - 1.0).abs() < 1e-12);
            assert!(v.windows(2).all(|w| w[1] >= w[0]));
        }
    }

    #[test]
    fn a_typical_clip_travels_past_the_floors() {
        let b = [0.5; 12];
        let (_, c) = feasible(&b, 3).unwrap();
        let mv = movement(&frames(&c));
        assert!(
            mv[0] >= MIN_PATH_M && mv[1] >= MIN_BOX_M && mv[2] >= MIN_TURN_DEG,
            "{mv:?}"
        );
    }

    #[test]
    fn descriptor_count_and_finite() {
        let b = [0.4; 12];
        let d = descriptors(&clip(&b, 5, 1.5));
        assert_eq!(d.len(), DESCRIPTOR_COUNT);
        assert!(d.iter().all(|v| v.is_finite()));
    }
}
