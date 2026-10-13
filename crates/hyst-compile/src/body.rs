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
/// Per-joint motion floors (addendum 3): total |change| per 16 s, degrees, at the
/// 10th percentile of version 47's 16 s windows on arm 0, in `JOINTS` order.
pub const MIN_JOINT_DEG: [f64; 5] = [386.0, 148.0, 299.0, 454.0, 370.0];
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
/// Each joint's own pace: the range its move lengths are drawn from, seconds.
/// Base and shoulder carry the arm and take long moves; the elbow, wrist bend and
/// roll carry little and take short, frequent ones.
const PACE: [(f64, f64); 5] = [(1.8, 3.0), (1.5, 2.6), (0.8, 1.3), (0.6, 1.1), (0.7, 1.3)];
/// Moves are generated from this time (so the clip opens mid-motion) to `END`.
const BEGIN: f64 = -3.0;
const END: f64 = 24.0;

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

    /// Ranges and why (`docs/BODY_STUDY.md` addendum 3: every joint dances).
    /// - Pace: each joint has its own move lengths (`PACE`): base 1.8..3.0 s,
    ///   shoulder 1.5..2.6, elbow 0.8..1.3, wrist bend 0.6..1.1, roll 0.7..1.3.
    ///   No duration is shared across joints. A move that its joint's limits make
    ///   longer than its gap takes the following gaps too, so it reaches its target.
    /// - Initiation and succession: the leading joint (base, shoulder, elbow or
    ///   wrist bend) runs its own stream of moves. Every other joint starts a move
    ///   at one of the leader's move starts plus its delay (0.12 s, plus 0..0.3 s
    ///   along the chain, base to tip below 0.5): it picks the leader's starts
    ///   nearest its own pace and, if it is faster, splits the gap into its own
    ///   shorter moves (lengths 0.75..1.25 of an equal split).
    /// - No dead stops: each move lasts its gap times 1 + overlap (0.3 sustained ..
    ///   0.12 sudden), so the next move of the same joint starts before it ends and
    ///   the two add up. Only base and shoulder hold, and only when sudden: their
    ///   moves last the gap times 1.3 .. 0.8, the lighter joints keep moving
    ///   through it, and breath never stops.
    /// - Time: the accelerating ramp is 50 % (sustained, a bell with the
    ///   decelerating one) to 12 % (sudden, a sharp start) of every move.
    /// - Weight: how much of the rest decelerates. Base and shoulder 100 % (light,
    ///   floats in) to 35 % (strong, cruise then a firm arrival); elbow, wrist and
    ///   roll 100 % to 75 %, so they keep settling when the heavy joints arrive.
    /// - Flow: elbow, wrist bend and roll pass their target by 25 % x flow of their
    ///   move and settle back once over 0.4 x sqrt(flow) of its duration. Base and
    ///   shoulder never overshoot.
    /// - Travel and shape: base yaw alternates sides of a span of 240..330 degrees
    ///   (each target in the outer 25 % of its side, so two targets are at least 180
    ///   degrees apart). Shoulder elevation alternates between the lowest and
    ///   highest 35 % of 10 + breath .. 95 degrees, elbow bend between the most
    ///   curled and most straight 35 % of -30 (bent up) .. 95 degrees, wrist
    ///   bend alternates sides by 20..70 degrees about the arch's centre
    ///   ((2 arch - 1) x (0.45 elbow + 10)). Elbow and wrist never bend down so far that their
    ///   link's end comes under the floor plus the disc radius (+5 mm) over the move.
    ///   height and curl_extension set 0.25 of the shoulder and elbow draws, so they
    ///   bias where the targets fall, never whether they move. Sizes were set so the
    ///   joints' shares of motion come near version 47's.
    /// - Space: the roll turns 30..110 x 0.6..1 degrees per move; yaw bows up to 15
    ///   degrees and roll 30 on the way.
    /// - Breath: shoulder up to 8 degrees, elbow 12, period 3.3..12 s.
    /// - Floor: shoulder, elbow and wrist targets are drawn again (up to 30 times)
    ///   if, anywhere along the move with breath at either extreme, a point placed
    ///   by the joints drawn so far is under the floor, or the last of them under
    ///   the floor plus the disc radius (the wrist: the whole floor rule). A draw
    ///   under 15 degrees from where the joint is counts as failed. After 30 the
    ///   joint lifts 25 degrees (shoulder 15) if that passes, else stays for that
    ///   move.
    /// - Limits: each move lasts at least what its joint's own `LIMITS` need (roll
    ///   speed capped at the rig's 240 deg/s envelope; breath's peak taken off
    ///   shoulder and elbow). Elbow, wrist bend and roll moves are sized against 0.6
    ///   of their speed limit, because overlapping moves (a settle and the next
    ///   move) add up. The base is drawn last of the four and its speed is capped
    ///   so that the hand's largest horizontal radius over the move turns at most
    ///   0.75 of the hand speed rule. Then the whole motion (not breath) is slowed by one
    ///   factor, if needed, so that the summed moves keep every joint under 0.98 of
    ///   its limits and the hand under 0.95 of its speed and jolt rules over the clip.
    fn new(b: &Body, seed: u64) -> Self {
        let [ext, height, arch, time, weight, flow, space, dir, delay, init, bdepth, brate] = *b;
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
        let mut starts: [Vec<f64>; 5] = Default::default();
        let (lo, hi) = PACE[lead];
        let mut t = BEGIN;
        while t < END {
            starts[lead].push(t);
            t += lerp(lo, hi, rng.next());
        }
        starts[lead].push(t);
        for j in (0..5).filter(|&j| j != lead) {
            let forced: Vec<f64> = starts[lead].iter().map(|s| s + d[j]).collect();
            let (lo, hi) = PACE[j];
            let mut cur = forced[0];
            let mut out = vec![cur];
            while cur < END {
                let want = cur + lerp(lo, hi, rng.next());
                let Some(next) = forced
                    .iter()
                    .copied()
                    .filter(|&f| f > cur + 0.5 * lo)
                    .min_by(|a, b| (a - want).abs().total_cmp(&(b - want).abs()))
                else {
                    break;
                };
                let n = ((next - cur) / (0.5 * (lo + hi))).round().max(1.0) as usize;
                let w: Vec<f64> = (0..n).map(|_| lerp(0.75, 1.25, rng.next())).collect();
                let sum: f64 = w.iter().sum();
                let mut acc = cur;
                for wi in &w[..n - 1] {
                    acc += (next - cur) * wi / sum;
                    out.push(acc);
                }
                out.push(next);
                cur = next;
            }
            starts[j] = out;
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
        let span = lerp(240.0, 330.0, rng.next());
        let e1_lo = 10.0 + breath[0];
        let peaks: [(f64, f64); 5] = std::array::from_fn(|j| profile_peaks(ramps[j].0, ramps[j].1));
        // Base after the bends: its speed cap needs the hand's radius.
        for j in [1, 2, 3, 0, 4] {
            let flip = rng.sign();
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
                let alt = if k % 2 == 0 { flip } else { -flip };
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
                let draw = |rng: &mut Rng, m: &Motion| -> f64 {
                    let band = 0.35 * rng.next() + if alt > 0.0 { 0.65 } else { 0.0 };
                    match j {
                        0 => alt * (span / 2.0 - 0.25 * span / 2.0 * rng.next()),
                        1 => -lerp(e1_lo, 95.0, 0.75 * band + 0.25 * height),
                        2 => lerp(cap, -30.0, 0.75 * band + 0.25 * ext),
                        3 => {
                            let q2 = m.joint(2, t0 + gap_dur);
                            let c = (2.0 * arch - 1.0) * (0.45 * q2 + 10.0);
                            (c + alt * lerp(20.0, 70.0, rng.next())).clamp(-110.0, cap)
                        }
                        _ => {
                            cur + rng.sign() * lerp(30.0, 110.0, rng.next()) * lerp(0.6, 1.0, space)
                        }
                    }
                };
                let wander = match j {
                    0 => rng.sign() * 15.0 * space,
                    4 => rng.sign() * 30.0 * space,
                    _ => 0.0,
                };
                let mut tries = 0;
                loop {
                    // 30 draws, then a 25 degree lift (shoulder 15), then no move.
                    let target = match tries {
                        0..30 => draw(&mut rng, &motion),
                        30 => match j {
                            1 => (cur - 15.0).max(-95.0),
                            2 => (cur - 25.0).max(-30.0),
                            3 => (cur - 25.0).max(-110.0),
                            _ => cur,
                        },
                        _ => cur,
                    };
                    tries += 1;
                    let delta = target - cur;
                    if (1..4).contains(&j) && tries <= 30 && delta.abs() < 15.0 {
                        continue;
                    }
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
                    if j == 0 || j == 4 || tries > 31 {
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
    /// Total motion per joint, degrees.
    pub joint_motion: [f64; 5],
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
/// speed, jolt, floor, the minimum movement, the per-joint motion floors and the
/// frame at 60 fps.
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
    let jm = joint_motion(&fr);
    for j in 0..5 {
        if jm[j] < MIN_JOINT_DEG[j] {
            out.push(format!("{} motion", JOINTS[j]));
        }
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
    fn a_typical_clip_travels_past_the_floors_in_frame() {
        let b = [0.5; 12];
        let (_, c) = feasible(&b, 3).unwrap();
        let fr = frames(&c);
        let mv = movement(&fr);
        assert!(
            mv[0] >= MIN_PATH_M && mv[1] >= MIN_BOX_M && mv[2] >= MIN_TURN_DEG,
            "{mv:?}"
        );
        let jm = joint_motion(&fr);
        assert!((0..5).all(|j| jm[j] >= MIN_JOINT_DEG[j]), "{jm:?}");
        let (_, r) = violations(&c);
        assert!(r.frame_margin_px >= FRAME_MARGIN_PX);
    }

    #[test]
    fn study_camera_matches_the_template_and_catches_a_point_outside() {
        let (x, y, _) = project([0.0, 0.0, CAMERA_TARGET_Z]);
        assert!((x - 640.0).abs() < 1e-9 && (y - 315.0).abs() < 1e-9);
        let b = [0.5; 12];
        let (_, mut c) = feasible(&b, 3).unwrap();
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
    fn joints_keep_their_own_pace_and_light_joints_move_more_often() {
        let m = Motion::new(&[0.5; 12], 4);
        let median = |j: usize| {
            let mut d: Vec<f64> = m.moves[j].iter().map(|x| x.dur).collect();
            d.sort_by(|a, b| a.total_cmp(b));
            d[d.len() / 2]
        };
        assert!(
            median(2) < median(0) && median(3) < median(1),
            "elbow/wrist slower"
        );
        assert!(m.moves[3].len() > m.moves[0].len() + 3);
        // Not one shared duration: the base and the wrist start at different times.
        let s0: Vec<f64> = m.moves[0].iter().map(|x| x.start).collect();
        assert!(m.moves[3].iter().filter(|x| !s0.contains(&x.start)).count() > 3);
    }

    #[test]
    fn something_always_moves_sudden_or_sustained() {
        for time in [0.0, 1.0] {
            let mut b = [0.5; 12];
            (b[3], b[4]) = (time, 1.0);
            let (_, c) = feasible(&b, 5).unwrap();
            let fr = frames(&c);
            let all_still = fr
                .windows(2)
                .filter(|w| (0..5).all(|j| (w[1].0[j] - w[0].0[j]).abs() * FPS < 2.0));
            assert_eq!(all_still.count(), 0, "time {time}");
            let still = longest_still(&fr);
            assert!(
                still[2..].iter().all(|&s| s < 0.5),
                "time {time}: {still:?}"
            );
        }
    }

    #[test]
    fn free_overshoots_distal_joints_only_and_bound_never() {
        let mut b = [0.5; 12];
        b[5] = 1.0;
        let m = Motion::new(&b, 6);
        assert!((0..2).all(|j| m.moves[j].iter().all(|x| x.over == 0.0)));
        assert!((2..5).all(|j| m.moves[j].iter().any(|x| x.over != 0.0)));
        // One overshoot: it settles once, monotonically, to the target.
        let x = &m.moves[4][3];
        let v: Vec<f64> = (0..=50)
            .map(|i| m.offset(4, x, 1.0 + m.settle * i as f64 / 50.0))
            .collect();
        assert!(v.windows(2).all(|w| (w[1] - w[0]) * x.over <= 1e-12));
        b[5] = 0.0;
        let m = Motion::new(&b, 6);
        assert!((0..5).all(|j| m.moves[j].iter().all(|x| x.over == 0.0)));
    }

    #[test]
    fn sudden_starts_sharp_and_strong_heavy_joints_arrive_firm() {
        let mut b = [0.5; 12];
        (b[3], b[4]) = (1.0, 1.0);
        let m = Motion::new(&b, 7);
        let (ra, rd0) = m.ramps[0];
        let (_, rd3) = m.ramps[3];
        assert!(ra < 0.15 && rd0 < 0.35 && rd3 > 0.6, "{:?}", m.ramps);
    }

    #[test]
    fn descriptor_count_and_finite() {
        let b = [0.4; 12];
        let d = descriptors(&clip(&b, 5, 1.5));
        assert_eq!(d.len(), DESCRIPTOR_COUNT);
        assert!(d.iter().all(|v| v.is_finite()));
    }
}
