//! Body study generator (`docs/BODY_STUDY.md`): one arm, silent, 8 s, moving in
//! joint space from a body vector. No music, no mind. Rules for check 2a live
//! here so they are in code before any result they score.

use crate::director::IntentCue;
use crate::ensemble::{
    forward_kinematics, sample_track, AgentTrack, EnsembleScore, Implement, JointKnot, Placement,
    Rig,
};

/// Round 2 (addendum 8) adds size, energy and rhythm: 15 dimensions.
pub const PARAMS: [&str; 15] = [
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
    "size",
    "energy",
    "rhythm",
];
/// Every value 0..1. Order as in `PARAMS`.
pub type Body = [f64; 15];

pub const CLIP_SECONDS: f64 = 8.0;
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
/// Stillness cap (addendum 8): a frame is still when every joint moves under
/// `STILL_DEG_S`; a clip fails with a still run over `STILL_RUN_S` or still frames
/// over `STILL_SHARE` of the clip (60 fps).
pub const STILL_DEG_S: f64 = 2.0;
pub const STILL_RUN_S: f64 = 2.0;
pub const STILL_SHARE: f64 = 0.25;
/// The study camera (addendum 3, in frame): the preview's solo camera (yaw -0.6,
/// pitch 0.35, focal 1800 px, 1280 x 720 canvas, centre at x 640, y 315) moved back
/// from 2.1 m to 3.05 m and aimed at z 0.35 m instead of 0.3 m, the smallest
/// distance (0.05 m steps) at which every point within the arm's reach plus the
/// disc's radius stays 20 px inside the frame. `body_study html` writes these two
/// numbers into its copy of the template; `ensemble.html` itself is unchanged.
pub const CAMERA_TARGET_Z: f64 = 0.35;
pub const CAMERA_DISTANCE: f64 = 3.05;
const CAMERA_YAW: f64 = -0.6;
const CAMERA_PITCH: f64 = 0.35;
pub const FRAME_MARGIN_PX: f64 = 20.0;

/// Pixel position and pixels per metre of a world point, as `ensemble.html`'s
/// `project` draws it with the study camera.
pub fn project(p: [f64; 3]) -> (f64, f64, f64) {
    let t = [0.0, 0.0, CAMERA_TARGET_Z];
    let (cp, sp) = (CAMERA_PITCH.cos(), CAMERA_PITCH.sin());
    let eye = [
        t[0] + CAMERA_DISTANCE * cp * CAMERA_YAW.cos(),
        t[1] + CAMERA_DISTANCE * cp * CAMERA_YAW.sin(),
        t[2] + CAMERA_DISTANCE * sp,
    ];
    let norm = |a: [f64; 3]| {
        let l = (a[0] * a[0] + a[1] * a[1] + a[2] * a[2]).sqrt();
        a.map(|v| v / l)
    };
    let cross = |a: [f64; 3], b: [f64; 3]| {
        [
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        ]
    };
    let dot = |a: [f64; 3], b: [f64; 3]| a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
    let f = norm([t[0] - eye[0], t[1] - eye[1], t[2] - eye[2]]);
    let r = norm(cross(f, [0.0, 0.0, 1.0]));
    let u = cross(r, f);
    let v = [p[0] - eye[0], p[1] - eye[1], p[2] - eye[2]];
    let s = 1800.0 / dot(v, f).max(0.1);
    (640.0 + dot(v, r) * s, 315.0 - dot(v, u) * s, s)
}

/// Smallest distance, pixels, from any world point (and the disc's whole radius
/// round the hand point) to the edge of the 1280 x 720 frame.
pub fn frame_margin(points: &[[f64; 3]]) -> f64 {
    points
        .iter()
        .enumerate()
        .map(|(i, &p)| {
            let (x, y, s) = project(p);
            let r = if i == 5 { DISC_M * s } else { 0.0 };
            (x - r).min(1280.0 - x - r).min(y - r).min(720.0 - y - r)
        })
        .fold(f64::MAX, f64::min)
}

/// Total motion of each joint, sum of |change| per 60 fps frame, degrees.
pub fn joint_motion(fr: &[([f64; 5], Vec<[f64; 3]>)]) -> [f64; 5] {
    std::array::from_fn(|j| fr.windows(2).map(|w| (w[1].0[j] - w[0].0[j]).abs()).sum())
}

/// Longest run, seconds, during which each joint moves slower than 2 deg/s (60 fps).
pub fn longest_still(fr: &[([f64; 5], Vec<[f64; 3]>)]) -> [f64; 5] {
    std::array::from_fn(|j| {
        let (mut run, mut best) = (0usize, 0usize);
        for w in fr.windows(2) {
            if (w[1].0[j] - w[0].0[j]).abs() * FPS < 2.0 {
                run += 1;
                best = best.max(run);
            } else {
                run = 0;
            }
        }
        best as f64 / FPS
    })
}

/// Frames where every joint moves under `STILL_DEG_S` (60 fps): the longest such
/// run, seconds, and their share of all frame steps.
pub fn stillness(fr: &[([f64; 5], Vec<[f64; 3]>)]) -> (f64, f64) {
    let (mut run, mut best, mut total) = (0usize, 0usize, 0usize);
    for w in fr.windows(2) {
        if (0..5).all(|j| (w[1].0[j] - w[0].0[j]).abs() * FPS < STILL_DEG_S) {
            run += 1;
            total += 1;
            best = best.max(run);
        } else {
            run = 0;
        }
    }
    (best as f64 / FPS, total as f64 / (fr.len() - 1) as f64)
}

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
}

/// Attempt `index` of the sampling stream (fixed seed 20261016): a uniform body
/// vector and its content seed.
pub fn draw(index: u64) -> (Body, u64) {
    let mut rng = Rng(20_261_016u64.wrapping_add(index.wrapping_mul(0x2545_F491_4F6C_DD1D)));
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

/// Peak |d/dx| and |d2/dx2| of `profile` (unit move, unit duration), sampled.
fn profile_peaks(ra: f64, rd: f64) -> (f64, f64) {
    let n = 4000;
    let h = 1.0 / n as f64;
    let p: Vec<f64> = (0..=n).map(|i| profile(i as f64 * h, ra, rd)).collect();
    let v = p.windows(2).map(|w| (w[1] - w[0]) / h).fold(0.0, f64::max);
    let a = p
        .windows(3)
        .map(|w| (w[2] - 2.0 * w[1] + w[0]).abs() / (h * h))
        .fold(0.0, f64::max);
    (v, a)
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

const HEAVY: [bool; 5] = [true, true, false, false, false];
/// Seconds per leader move at energy 0 and 1 (geometric between). 0.7 s is under
/// round 1's shortest wrist move, so the fast end meets the joint limits and the
/// hand rules rather than a cap of its own. The slow end 5.0 s and `SIZE_MIN` 0.06
/// are the slowest and smallest of a probe ladder (size scale / pace: 0.12 / 3.2,
/// 0.06 / 4.0, 0.06 / 5.0, 0.04 / 6.0, 0.03 / 8.0) at which at least 90 % of the
/// calmest bodies (size and energy ≤ 0.05, 60 draws) pass the stillness cap:
/// 56 of 60 here, 53 at 0.04 / 6.0, 47 at 0.03 / 8.0.
const PACE_SLOW: f64 = 5.0;
const PACE_FAST: f64 = 0.7;
/// Size scale at size 0 (at 1 it is 1, geometric between); see `PACE_SLOW`.
const SIZE_MIN: f64 = 0.06;
/// Full-size travel per move, degrees: base span between its two sides, shoulder
/// elevation, elbow bend, wrist bend about its centre, roll turn. The base 330 and
/// roll 110 are the old upper ranges; shoulder 85 and elbow 125 are their whole
/// allowed ranges (10..95 and -30..95); the wrist 140 is twice the old 70 per side.
const AMP: [f64; 5] = [330.0, 85.0, 125.0, 140.0, 110.0];
/// Seed variation: each gap ±8 %, each target ±10 % of its joint's travel, and the
/// start phase anywhere in one leader cycle (two moves). Small next to the body's
/// own ranges (pace 7.1x, size 16.7x).
const TIME_JITTER: f64 = 0.08;
const TARGET_JITTER: f64 = 0.1;
/// Moves are generated from `BEGIN` minus the start phase (so every joint is in its
/// pattern, not in its first move from the start pose, when the clip opens: two
/// slowest moves, 5 s each, plus their overlap) to `END` (past the 8 s clip).
const BEGIN: f64 = -12.0;
const END: f64 = 12.0;
/// One move of one joint.
struct Move {
    start: f64,
    dur: f64,
    delta: f64,
    /// Free flow (elbow, wrist bend, roll): the move passes its target by this
    /// much, then settles back once.
    over: f64,
    /// Indirect space (yaw, roll): signed bow amplitude on the way, degrees.
    wander: f64,
}

struct Motion {
    p0: [f64; 5],
    /// Each joint's own moves; moves of one joint overlap and add up.
    moves: [Vec<Move>; 5],
    /// Accelerating and decelerating share of each joint's move.
    ramps: [(f64, f64); 5],
    /// Settle after the overshoot, as a fraction of the move's duration.
    settle: f64,
    breath: [f64; 2],
    breath_hz: f64,
    breath_phase: f64,
}

impl Motion {
    /// Offset of joint j from its start pose for move m, x = time into it / dur.
    fn offset(&self, j: usize, m: &Move, x: f64) -> f64 {
        if x <= 0.0 {
            return 0.0;
        }
        let (ra, rd) = self.ramps[j];
        let mut v = if x < 1.0 {
            (m.delta + m.over) * profile(x, ra, rd)
        } else if x < 1.0 + self.settle {
            m.delta + m.over * (1.0 - minjerk((x - 1.0) / self.settle))
        } else {
            m.delta
        };
        if m.wander != 0.0 && x < 1.0 {
            let (tau, pi) = (std::f64::consts::TAU, std::f64::consts::PI);
            v += m.wander * (tau * x).sin() * (pi * x).sin().powi(2);
        }
        v
    }

    /// Joint j at motion time t, without breath.
    fn joint(&self, j: usize, t: f64) -> f64 {
        self.p0[j]
            + self.moves[j]
                .iter()
                .map(|m| self.offset(j, m, (t - m.start) / m.dur))
                .sum::<f64>()
    }

    fn breath_at(&self, t: f64) -> [f64; 2] {
        let s = (std::f64::consts::TAU * self.breath_hz * t + self.breath_phase).sin();
        [self.breath[0] * s, self.breath[1] * s]
    }

    /// Ranges and why (`docs/BODY_STUDY.md` addendum 8: the body decides, the seed
    /// only varies). Every choice below is a function of the body vector; the seed
    /// draws only the start phase, ±`TIME_JITTER` on each gap, ±`TARGET_JITTER` on
    /// each target, and breath's phase.
    /// - Energy: the leader's move length, `PACE_SLOW` 5.0 s (energy 0) to
    ///   `PACE_FAST` 0.7 s (energy 1), geometric. At the fast end the joint limits
    ///   and the hand rules set the pace (each move lasts at least what its joint's
    ///   limits need; then the whole motion is slowed by one factor, below).
    /// - Size: every joint's travel per move is `AMP` (base 330, shoulder 85, elbow
    ///   125, wrist bend 140, roll 110 degrees) times a scale from `SIZE_MIN` 0.06
    ///   (size 0) to 1 (size 1), geometric. Base and roll scale their wander too.
    /// - Rhythm: base and shoulder move once per pace; the elbow 1 + round(rhythm)
    ///   times, wrist bend and roll 1 + round(2 rhythm) times. Rhythm 0 moves every
    ///   joint together; rhythm 1 has the wrist and roll three moves to the base's
    ///   one.
    /// - Pattern: every joint alternates between two poles, one move each way. Base
    ///   yaw swings between ±span/2 about straight ahead; the roll turns back and
    ///   forth. The shoulder's poles sit about a centre set by height inside 10 +
    ///   breath .. 95 degrees of elevation, the elbow's about a centre set by
    ///   curl_extension inside -30 (bent up) .. its floor cap, the wrist's about the
    ///   arch's centre ((2 arch - 1) x (0.45 elbow + 10)), as in round 1.
    /// - Initiation and succession: the leading joint (base, shoulder, elbow or
    ///   wrist bend) sets the move starts. Each other joint starts at the leader's
    ///   starts plus its delay (0.12 s, plus 0..0.3 s along the chain, base to tip
    ///   below succession_direction 0.5), dividing each leader gap into equal parts
    ///   if it is faster or taking every n-th start if slower.
    /// - No dead stops: each move lasts its gap times 1 + overlap (0.3 sustained ..
    ///   0.12 sudden), so moves of one joint overlap. Only base and shoulder hold,
    ///   and only when sudden: their moves last the gap times 1.3 .. 0.8.
    /// - Time: the accelerating ramp is 50 % (sustained, a bell) to 12 % (sudden,
    ///   a sharp start) of every move.
    /// - Weight: how much of the rest decelerates. Base and shoulder 100 % (light,
    ///   floats in) to 35 % (strong, firm arrival); elbow, wrist and roll 100 % to
    ///   75 %.
    /// - Flow: elbow, wrist bend and roll pass their target by 25 % x flow of their
    ///   move and settle back once over 0.4 x sqrt(flow) of its duration.
    /// - Space: base yaw bows up to 15 and roll 30 degrees (times the size scale)
    ///   on the way, alternating sides.
    /// - Breath: shoulder up to 8 degrees, elbow 12, period 3.3..12 s.
    /// - Floor: a shoulder, elbow or wrist target that puts a point placed by the
    ///   joints drawn so far under the floor (the last of them under the floor plus
    ///   the disc radius; the wrist: the whole floor rule) anywhere along the move,
    ///   breath at either extreme, is lifted in steps (shoulder 8, elbow and wrist
    ///   10 degrees) up to 6 times; if that fails the joint stays for that move.
    ///   Elbow and wrist bends are capped so their link's end stays 5 mm over the
    ///   floor plus the disc radius.
    /// - Limits: each move lasts at least what its joint's own `LIMITS` need (roll
    ///   speed capped at the rig's 240 deg/s envelope; breath's peak taken off
    ///   shoulder and elbow). Elbow, wrist bend and roll moves are sized against 0.6
    ///   of their speed limit, because overlapping moves add up. The base's speed is
    ///   capped so the hand's largest horizontal radius over the move turns at most
    ///   0.75 of the hand speed rule. Then the whole motion (not breath) is slowed
    ///   by one factor, if needed, to keep every joint under 0.98 of its limits and
    ///   the hand under 0.95 of its speed and jolt rules over the clip.
    fn new(b: &Body, seed: u64) -> Self {
        let [ext, height, arch, time, weight, flow, space, dir, delay, init, bdepth, brate, size, energy, rhythm] =
            *b;
        let mut rng = Rng(seed ^ 0xA5A5_5A5A_1234_5678);
        let rig = study_rig();
        let lead = ((init * 4.0) as usize).min(3);
        let d: [f64; 5] = std::array::from_fn(|j| {
            let rank = if dir < 0.5 { j } else { 4 - j } as f64;
            0.3 * delay * rank / 4.0 + if j == lead { 0.0 } else { 0.12 }
        });
        let ra = lerp(0.5, 0.12, time);
        let ramps = std::array::from_fn(|j| {
            let w = if HEAVY[j] {
                lerp(1.0, 0.35, weight)
            } else {
                lerp(1.0, 0.75, weight)
            };
            (ra, (1.0 - ra) * w)
        });
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
        let overlap = lerp(0.3, 0.12, time);
        let settle = 0.4 * flow.sqrt();
        let pace = PACE_SLOW * (PACE_FAST / PACE_SLOW).powf(energy);
        let scale = SIZE_MIN.powf(1.0 - size);
        let per: [f64; 5] = [
            1.0,
            1.0,
            1.0 + rhythm.round(),
            1.0 + (2.0 * rhythm).round(),
            1.0 + (2.0 * rhythm).round(),
        ];
        let mut motion = Self {
            // Start pose, held before the first moves: mid height, elbow half bent.
            p0: [0.0, -lerp(10.0 + breath[0], 95.0, 0.5), 50.0, 0.0, 0.0],
            moves: Default::default(),
            ramps,
            settle,
            breath,
            breath_hz,
            breath_phase: rng.next() * std::f64::consts::TAU,
        };

        // Move starts per joint: the leader's own, then each follower's.
        let jitter = |rng: &mut Rng, x: f64, k: f64| x * (1.0 + k * (2.0 * rng.next() - 1.0));
        let mut starts: [Vec<f64>; 5] = Default::default();
        let lead_gap = pace / per[lead];
        let mut t = BEGIN - 2.0 * lead_gap * rng.next();
        while t < END {
            starts[lead].push(t);
            t += jitter(&mut rng, lead_gap, TIME_JITTER);
        }
        starts[lead].push(t);
        for j in (0..5).filter(|&j| j != lead) {
            let forced: Vec<f64> = starts[lead].iter().map(|s| s + d[j]).collect();
            let ratio = per[j] / per[lead];
            starts[j] = if ratio >= 1.0 {
                let k = ratio.round() as usize;
                let mut out = Vec::new();
                for w in forced.windows(2) {
                    out.push(w[0]);
                    for i in 1..k {
                        let x = jitter(&mut rng, i as f64, TIME_JITTER / i as f64) / k as f64;
                        out.push(lerp(w[0], w[1], x));
                    }
                }
                out.push(*forced.last().unwrap());
                out
            } else {
                forced
                    .iter()
                    .step_by((1.0 / ratio).round() as usize)
                    .copied()
                    .collect()
            };
        }

        // Targets, joint by joint so each floor check sees the joints drawn so far.
        let clear = |m: &Motion, upto: usize, t0: f64, t1: f64| {
            (0..=40).all(|i| {
                let t = lerp(t0, t1, i as f64 / 40.0);
                let mut q: [f64; 5] =
                    std::array::from_fn(|j| if j <= upto { m.joint(j, t) } else { 0.0 });
                q[4] = 0.0;
                [-1.0, 1.0].iter().all(|s| {
                    let mut q = q;
                    q[1] -= breath[0] * s;
                    q[2] -= breath[1] * s;
                    if upto >= 3 {
                        return floor_margin(&rig, &q) >= 0.0;
                    }
                    // Points the joints drawn so far place; the last one also clears
                    // the disc, so a later joint can still point the rest upward.
                    let place = Placement {
                        origin_m: [0.0; 3],
                        yaw_degrees: 0.0,
                    };
                    let w = forward_kinematics(&rig, &place, &q).expect("fk");
                    w[1..=upto + 1].iter().all(|p| p[2] >= FLOOR_M)
                        && w[upto + 1][2] >= FLOOR_M + DISC_M
                })
            })
        };
        let amp: [f64; 5] = std::array::from_fn(|j| AMP[j] * scale);
        let e1_lo = 10.0 + breath[0];
        let peaks: [(f64, f64); 5] = std::array::from_fn(|j| profile_peaks(ramps[j].0, ramps[j].1));
        // Base after the bends: its speed cap needs the hand's radius.
        for j in [1, 2, 3, 0, 4] {
            let st = std::mem::take(&mut starts[j]);
            let mult = if HEAVY[j] {
                lerp(1.0 + overlap, 0.8, time)
            } else {
                1.0 + overlap
            };
            let (mut i, mut k) = (0, 0);
            while i + 1 < st.len() {
                let t0 = st[i];
                let mut next;
                let alt = if k % 2 == 0 { 1.0 } else { -1.0 };
                k += 1;
                let cur = motion.joint(j, t0 + 50.0);
                let gap_dur = (st[i + 1] - t0) * mult;
                // Largest bend (down) of elbow (j 2) or wrist (j 3) over the move that
                // keeps the end of its link above the floor plus the disc radius,
                // breath at its low extreme, 5 mm spare.
                let high = |m: &Motion, j: usize| {
                    let link = if j == 2 { 0.22 } else { 0.19 };
                    (0..=10)
                        .map(|i| {
                            let t = t0 + gap_dur * (1.5 + settle) * i as f64 / 10.0;
                            let mut q: [f64; 5] =
                                std::array::from_fn(|k| if k < j { m.joint(k, t) } else { 0.0 });
                            q[1] += breath[0];
                            q[2] += breath[1];
                            let place = Placement {
                                origin_m: [0.0; 3],
                                yaw_degrees: 0.0,
                            };
                            let z = forward_kinematics(&rig, &place, &q).expect("fk")[j][2];
                            let need = ((FLOOR_M + DISC_M + 0.005 - z) / link)
                                .clamp(-1.0, 1.0)
                                .asin()
                                .to_degrees();
                            -(1..j).map(|k| q[k]).sum::<f64>() - need
                        })
                        .fold(f64::MAX, f64::min)
                        - if j == 2 { breath[1] } else { 0.0 }
                };
                let cap = match j {
                    2 => high(&motion, 2).clamp(5.0, 95.0),
                    3 => high(&motion, 3).clamp(-110.0, 110.0),
                    _ => f64::MAX,
                };
                let jit = TARGET_JITTER * amp[j] * (2.0 * rng.next() - 1.0);
                let half = amp[j] / 2.0;
                let planned = match j {
                    0 => alt * half + jit,
                    1 => {
                        let (lo, hi) = (e1_lo, 95.0);
                        let h = half.min((hi - lo) / 2.0);
                        -(lerp(lo + h, hi - h, height) + alt * h + jit).clamp(lo, hi)
                    }
                    2 => {
                        let (lo, hi) = (-30.0, cap);
                        let h = half.min((hi - lo) / 2.0);
                        (lerp(hi - h, lo + h, ext) + alt * h + jit).clamp(lo, hi)
                    }
                    3 => {
                        let q2 = motion.joint(2, t0 + gap_dur);
                        let c = (2.0 * arch - 1.0) * (0.45 * q2 + 10.0);
                        (c + alt * half + jit).clamp(-110.0, cap)
                    }
                    _ => cur + alt * (2.0 * half) + jit,
                };
                let wander = match j {
                    0 => alt * 15.0 * space * scale,
                    4 => alt * 30.0 * space * scale,
                    _ => 0.0,
                };
                let mut tries = 0;
                loop {
                    // The planned target, then lifted in 6 steps, then no move.
                    let target = match (j, tries) {
                        (_, 0) => planned,
                        (1, 1..=6) => (planned - 8.0 * tries as f64).max(-95.0),
                        (2, 1..=6) => (planned - 10.0 * tries as f64).max(-30.0),
                        (3, 1..=6) => (planned - 10.0 * tries as f64).max(-110.0),
                        _ => cur,
                    };
                    tries += 1;
                    let delta = target - cur;
                    let over = match j {
                        2 => {
                            (target + 0.25 * flow * delta)
                                .clamp(-110.0 + breath[1], cap.max(target))
                                - target
                        }
                        3 => (target + 0.25 * flow * delta).clamp(-110.0, cap.max(target)) - target,
                        4 => 0.25 * flow * delta,
                        _ => 0.0,
                    };
                    // Each joint's own limits set the shortest this move may last.
                    let a = (delta + over).abs();
                    let (pv, pa) = peaks[j];
                    let (vw, aw) = if wander != 0.0 {
                        let tp = std::f64::consts::TAU;
                        (tp * wander.abs(), 3.0 * tp * tp * wander.abs())
                    } else {
                        (0.0, 0.0)
                    };
                    // Light joints' moves overlap their neighbours', which add up:
                    // they are sized against 0.6 of their speed limit. The base keeps
                    // the hand's horizontal speed under 0.75 of the hand rule.
                    let vl = match j {
                        0 => {
                            let r = (0..=10)
                                .map(|i| {
                                    let t = t0 + 1.5 * gap_dur * i as f64 / 10.0;
                                    let q: [f64; 5] = std::array::from_fn(|k| {
                                        if k == 0 {
                                            0.0
                                        } else {
                                            motion.joint(k, t)
                                        }
                                    });
                                    let h = hand_at(&q);
                                    h[0].hypot(h[1])
                                })
                                .fold(0.0, f64::max);
                            lim[0].0.min((0.75 * HAND_MPS / r.max(0.05)).to_degrees())
                        }
                        2..=4 => 0.6 * lim[j].0,
                        _ => lim[j].0,
                    };
                    let dur = gap_dur
                        .max((a * pv + vw) / vl)
                        .max(((a * pa + aw) / lim[j].1).sqrt());
                    // A move longer than its gap takes the following ones too.
                    next = i + 1;
                    while next + 1 < st.len() && (st[next] - t0) * mult < dur {
                        next += 1;
                    }
                    let dur = dur.max((st[next] - t0) * mult);
                    motion.moves[j].push(Move {
                        start: t0,
                        dur,
                        delta,
                        over,
                        wander,
                    });
                    if j == 0 || j == 4 || tries > 7 {
                        break;
                    }
                    if clear(&motion, j, t0, t0 + dur * (1.0 + settle)) {
                        break;
                    }
                    motion.moves[j].pop();
                }
                i = next;
            }
        }
        motion.rescale(&rig, &lim);
        motion
    }

    /// Slow every move (not breath) by one factor so the summed moves keep each
    /// joint's limits and the hand under 0.95 of its rules over the clip.
    fn rescale(&mut self, rig: &Rig, lim: &[(f64, f64); 5]) {
        let hz = 240.0;
        let n = (CLIP_SECONDS * hz) as usize;
        let h = 1.0 / hz;
        let q: Vec<[f64; 5]> = (0..=n + 2)
            .map(|i| std::array::from_fn(|j| self.joint(j, i as f64 * h)))
            .collect();
        let mut k = 1.0f64;
        // 0.98: the 240 Hz samples here can miss the peak the 1 kHz check finds.
        for (j, (lv, la)) in lim.iter().map(|&(v, a)| (0.98 * v, 0.98 * a)).enumerate() {
            for w in q.windows(3) {
                k = k
                    .max((w[1][j] - w[0][j]).abs() / h / lv)
                    .max(((w[2][j] - 2.0 * w[1][j] + w[0][j]).abs() / (h * h) / la).sqrt());
            }
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
                    .map(|i| (w[1][i] - w[0][i]).powi(2))
                    .sum::<f64>()
                    .sqrt()
                    / h
            })
            .collect();
        for w in speed.windows(2) {
            k = k
                .max(w[0] / (0.95 * HAND_MPS))
                .max(((w[1] - w[0]).abs() / h / (0.95 * JOLT_MPS2)).sqrt());
        }
        for ms in &mut self.moves {
            for m in ms {
                m.start *= k;
                m.dur *= k;
            }
        }
    }

    /// Joint angles (yaw, shoulder, elbow, wrist bend, roll), degrees, motion time t.
    fn at(&self, t: f64) -> [f64; 5] {
        let mut q: [f64; 5] = std::array::from_fn(|j| self.joint(j, t));
        let b = self.breath_at(t);
        q[1] -= b[0];
        q[2] -= b[1];
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
    /// Total motion per joint, degrees.
    pub joint_motion: [f64; 5],
    /// Longest still run (s) and still share of the clip (`stillness`).
    pub still: (f64, f64),
    /// Smallest distance to the frame edge, pixels.
    pub frame_margin_px: f64,
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
/// speed, jolt, floor, the stillness cap and the frame at 60 fps.
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
    let jm = joint_motion(&fr);
    let still = stillness(&fr);
    if still.0 > STILL_RUN_S {
        out.push("still run".into());
    }
    if still.1 > STILL_SHARE {
        out.push("still share".into());
    }
    let margin = fr
        .iter()
        .map(|f| frame_margin(&f.1))
        .fold(f64::MAX, f64::min);
    if margin < FRAME_MARGIN_PX {
        out.push("in frame".into());
    }
    (
        out,
        Check2a {
            max_hand_mps: max_hand,
            max_jolt_mps2: max_jolt,
            min_floor_margin_m: floor,
            movement: mv,
            joint_motion: jm,
            still,
            frame_margin_px: margin,
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

/// 37 motion descriptors of the shown 8 s at 60 fps (`docs/BODY_STUDY.md`):
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

    const MID: Body = [0.5; 15];

    fn with(pairs: &[(usize, f64)]) -> Body {
        let mut b = MID;
        for &(k, v) in pairs {
            b[k] = v;
        }
        b
    }

    /// Mean over the five joints of each joint's mean speed, deg/s, on the clip.
    fn mean_speed(c: &EnsembleScore) -> f64 {
        let d = descriptors(c);
        (0..5).map(|j| d[6 * j]).sum::<f64>() / 5.0
    }

    #[test]
    fn same_inputs_same_clip() {
        let (a, c) = (clip(&MID, 7, 1.0), clip(&MID, 7, 1.0));
        assert_eq!(a, c);
        assert_ne!(a, clip(&MID, 8, 1.0));
        assert_eq!(a.tracks[0].knots.len(), 161);
    }

    #[test]
    fn stretching_slows_motion_and_keeps_the_phrase_centre() {
        let (one, two) = (clip(&MID, 3, 1.0), clip(&MID, 3, 2.0));
        let mid = |s: &EnsembleScore| s.tracks[0].knots[80].joints_degrees.clone();
        assert_eq!(mid(&one), mid(&two));
        assert!(mean_speed(&two) < mean_speed(&one) * 0.75);
    }

    #[test]
    fn same_body_different_seeds_stays_close() {
        for b in [
            MID,
            with(&[(12, 0.2), (13, 0.2)]),
            with(&[(12, 0.8), (13, 0.8)]),
        ] {
            let v: Vec<f64> = (1..=6).map(|s| mean_speed(&clip(&b, s, 1.0))).collect();
            let (lo, hi) = (
                v.iter().copied().fold(f64::MAX, f64::min),
                v.iter().copied().fold(0.0, f64::max),
            );
            assert!(hi / lo < 1.35, "{v:?}");
        }
    }

    #[test]
    fn size_and_energy_set_mean_joint_speed() {
        let speed = |size, energy| mean_speed(&clip(&with(&[(12, size), (13, energy)]), 4, 1.0));
        let (calm, big_slow, small_fast, wild) = (
            speed(0.0, 0.0),
            speed(1.0, 0.0),
            speed(0.0, 1.0),
            speed(1.0, 1.0),
        );
        assert!(big_slow > 3.0 * calm, "{calm} {big_slow}");
        assert!(small_fast > 2.0 * calm, "{calm} {small_fast}");
        assert!(wild > 4.0 * calm, "{calm} {wild}");
    }

    #[test]
    fn hardware_limits_hold_on_feasible_clips() {
        for b in [
            MID,
            with(&[(12, 1.0), (13, 1.0), (3, 1.0)]),
            with(&[(12, 0.0), (13, 0.0)]),
        ] {
            let (_, c) = feasible(&b, 2).expect("feasible");
            assert!(violations(&c).0.is_empty());
            c.validate().unwrap();
        }
    }

    #[test]
    fn rendered_curve_check_names_the_joint_and_limit() {
        let (_, mut c) = feasible(&MID, 1).unwrap();
        // 40 degrees of yaw in 0.05 s: 800 deg/s, over the 120 deg/s base limit.
        c.tracks[0].knots[80].joints_degrees[0] += 40.0;
        let v = violations(&c).0;
        assert!(v.contains(&"base_yaw speed".to_string()), "{v:?}");
        assert!(!v.iter().any(|x| x.starts_with("wrist_roll")), "{v:?}");
    }

    #[test]
    fn stillness_cap_is_enforced() {
        let (_, mut c) = feasible(&MID, 1).unwrap();
        assert!(violations(&c).1.still.0 <= STILL_RUN_S);
        // Freeze every joint from 2 s to 4.5 s: a 2.5 s still run.
        let knots = &mut c.tracks[0].knots;
        let hold = knots[40].joints_degrees.clone();
        for k in &mut knots[40..=90] {
            k.joints_degrees = hold.clone();
            k.velocity_degrees_per_second = vec![0.0; 5];
            k.acceleration_degrees_per_second2 = vec![0.0; 5];
        }
        let (v, r) = violations(&c);
        assert!(v.contains(&"still run".to_string()), "{v:?} {:?}", r.still);
        // Short still runs adding up past a quarter of the clip.
        let fr: Vec<([f64; 5], Vec<[f64; 3]>)> = (0..=480)
            .map(|i| {
                let moving = (i / 60) % 2 == 0;
                (
                    [if moving { i as f64 } else { 0.0 }, 0.0, 0.0, 0.0, 0.0],
                    vec![],
                )
            })
            .collect();
        let (run, share) = stillness(&fr);
        assert!(run <= 1.0 && share > STILL_SHARE, "{run} {share}");
    }

    #[test]
    fn a_floor_dive_is_under_the_floor() {
        assert!(hand_at(&[0.0, 60.0, 80.0, 0.0, 0.0])[2] < FLOOR_M + DISC_M);
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
    fn study_camera_matches_the_template_and_catches_a_point_outside() {
        let (x, y, _) = project([0.0, 0.0, CAMERA_TARGET_Z]);
        assert!((x - 640.0).abs() < 1e-9 && (y - 315.0).abs() < 1e-9);
        let (_, mut c) = feasible(&MID, 3).unwrap();
        // A hand 1.5 m up is out of every frame.
        for k in &mut c.tracks[0].knots {
            k.joints_degrees[1] = -90.0;
            k.joints_degrees[2] = 0.0;
            k.joints_degrees[3] = 0.0;
        }
        let mut rig = c.rig.clone();
        rig.channels[1].link_m = [1.5, 0.0, 0.0];
        c.rig = rig;
        assert!(violations(&c).0.contains(&"in frame".to_string()));
    }

    #[test]
    fn rhythm_sets_how_often_distal_joints_move() {
        let count = |rhythm| {
            let m = Motion::new(&with(&[(14, rhythm), (9, 0.0)]), 4);
            (m.moves[0].len(), m.moves[3].len())
        };
        let (_, w0) = count(0.0);
        let (_, w1) = count(1.0);
        assert!(w1 >= 2 * w0, "{w0} {w1}");
    }

    #[test]
    fn free_overshoots_distal_joints_only_and_bound_never() {
        let b = with(&[(5, 1.0)]);
        let m = Motion::new(&b, 6);
        assert!((0..2).all(|j| m.moves[j].iter().all(|x| x.over == 0.0)));
        assert!((2..5).all(|j| m.moves[j].iter().any(|x| x.over != 0.0)));
        let x = &m.moves[4][3];
        let v: Vec<f64> = (0..=50)
            .map(|i| m.offset(4, x, 1.0 + m.settle * i as f64 / 50.0))
            .collect();
        assert!(v.windows(2).all(|w| (w[1] - w[0]) * x.over <= 1e-12));
        let m = Motion::new(&with(&[(5, 0.0)]), 6);
        assert!((0..5).all(|j| m.moves[j].iter().all(|x| x.over == 0.0)));
    }

    #[test]
    fn descriptor_count_and_finite() {
        let d = descriptors(&clip(&[0.4; 15], 5, 1.5));
        assert_eq!(d.len(), DESCRIPTOR_COUNT);
        assert!(d.iter().all(|v| v.is_finite()));
    }
}
