//! Deterministic single-arm offline cue compiler.

use hyst_core::sidecar::{Sidecar, SidecarOnset};
use serde::{Deserialize, Serialize};

const Q_V: f64 = 1.875; // max derivative of 6t^5-15t^4+10t^3
const Q_A: f64 = 5.773_502_691_896_258;

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct JointLimits {
    pub min_degrees: [f64; 3],
    pub max_degrees: [f64; 3],
    pub max_speed_degrees_per_second: [f64; 3],
    pub max_acceleration_degrees_per_second2: [f64; 3],
}
impl Default for JointLimits {
    fn default() -> Self {
        Self {
            // Assumed hobby/serial-servo class (~0.15 s/60° unloaded),
            // derated. Not measured hardware; revisit once actuators exist.
            min_degrees: [15.0, -150.0, -90.0],
            max_degrees: [165.0, 150.0, 90.0],
            max_speed_degrees_per_second: [240.0, 300.0, 360.0],
            max_acceleration_degrees_per_second2: [1500.0, 1800.0, 2400.0],
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Knot {
    pub time: f64,
    pub phase: String,
    pub joints: [f64; 3],
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Cue {
    pub start: f64,
    pub end: f64,
    pub gesture: String,
    pub reason: String,
    pub energy: f32,
    pub accent: f32,
    /// Exact timestamp of a content event this hit/windup was planned to reach.
    #[serde(rename = "arrivalAnchor", default)]
    pub arrival_anchor: Option<f64>,
    /// Index into `Score::sections`; absent in scores compiled before sections existed.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub section: Option<usize>,
    pub knots: Vec<Knot>,
}

/// Coarse song section: sustained level/timbre regime, not verified verse/chorus.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct SectionPlan {
    pub start: f64,
    pub end: f64,
    /// `rest`, `quiet`, `mid` or `peak`.
    pub level: String,
    /// Motif label shared by sections judged to recur (`A`, `B`, ...).
    pub motif: String,
    /// 0 for first statement; later statements mirror/scale the motif.
    pub variation: u32,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub repeat_of: Option<usize>,
    pub reason: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Score {
    pub duration: f64,
    #[serde(default)]
    pub sections: Vec<SectionPlan>,
    pub cues: Vec<Cue>,
    pub limits: JointLimits,
}

impl Score {
    /// Sample simulated joint angles in degrees at absolute audio time.
    pub fn sample(&self, time: f64) -> [f64; 3] {
        if self.cues.is_empty() {
            return REST_POSE;
        }
        let t = time.clamp(0.0, self.duration);
        let i = self
            .cues
            .partition_point(|c| c.end < t)
            .min(self.cues.len() - 1);
        sample_knots(&self.cues[i].knots, t)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct CompileConfig {
    pub enable_hits: bool,
    pub enable_windups: bool,
}
impl Default for CompileConfig {
    fn default() -> Self {
        Self {
            enable_hits: true,
            enable_windups: true,
        }
    }
}

pub fn compile_sidecar_json(json: &str) -> Result<Score, String> {
    compile_sidecar_json_with_config(json, CompileConfig::default())
}

pub fn compile_sidecar_json_with_config(
    json: &str,
    config: CompileConfig,
) -> Result<Score, String> {
    let root: serde_json::Value = serde_json::from_str(json).map_err(|e| e.to_string())?;
    let sidecar = Sidecar::from_json_str(json).map_err(|e| e.to_string())?;
    if !sidecar.duration.is_finite()
        || !(0.0..=21_600.0).contains(&sidecar.duration)
        || sidecar.duration == 0.0
    {
        return Err("duration must be finite, positive, and <= 6 hours".into());
    }
    if !sidecar.envelope_rate.is_finite()
        || sidecar.envelope_rate <= 0.0
        || sidecar.energy_envelope.is_empty()
    {
        return Err("envelopeRate and energyEnvelope must be valid".into());
    }
    let rms = match root.get("rmsEnvelope") {
        None => None,
        Some(value) => {
            let values = value
                .as_array()
                .ok_or("rmsEnvelope must be an array")?;
            let required = (sidecar.duration * f64::from(sidecar.envelope_rate)).ceil() as usize;
            if values.len() < required {
                return Err(format!(
                    "rmsEnvelope has {} samples; needs at least {required} for duration and envelopeRate",
                    values.len()
                ));
            }
            let mut parsed = Vec::with_capacity(values.len());
            for (i, value) in values.iter().enumerate() {
                let sample = value
                    .as_f64()
                    .ok_or_else(|| format!("rmsEnvelope[{i}] must be a number"))?;
                if !sample.is_finite() || sample < 0.0 || sample > f64::from(f32::MAX) {
                    return Err(format!("rmsEnvelope[{i}] must be finite and nonnegative"));
                }
                parsed.push(sample as f32);
            }
            Some(parsed)
        }
    };
    Ok(compile(&sidecar, rms.as_deref(), config))
}

/// Named key pose: shoulder/elbow/wrist degrees, relative planar joints.
/// Right-side versions; `mirror` gives the left-side counterpart.
/// All keep the tip >= ~10 cm above the floor with 32/26/12 cm links.
const POSES: [(&str, [f64; 3]); 8] = [
    ("rise", [90.0, 0.0, 0.0]),
    ("reach", [55.0, 15.0, 10.0]),
    ("arc", [120.0, -60.0, -40.0]),
    ("fold", [105.0, -130.0, -30.0]),
    ("sweep", [30.0, -20.0, -10.0]),
    ("hook", [70.0, 70.0, 50.0]),
    ("coil", [115.0, -100.0, 60.0]),
    ("open", [40.0, 40.0, -20.0]),
];
const REST_POSE: [f64; 3] = [105.0, -110.0, -40.0];
const NEUTRAL: [f64; 3] = [95.0, -35.0, -10.0];

fn pose(name: &str) -> [f64; 3] {
    POSES.iter().find(|p| p.0 == name).map_or(NEUTRAL, |p| p.1)
}
/// Left/right mirror about the vertical through the base.
fn mirror(q: [f64; 3]) -> [f64; 3] {
    [180.0 - q[0], -q[1], -q[2]]
}
fn lerp(a: [f64; 3], b: [f64; 3], x: f64) -> [f64; 3] {
    std::array::from_fn(|j| a[j] + (b[j] - a[j]) * x)
}

/// Per-level phrasing: bars per phrase, move lead, settle time, amplitude,
/// overshoot, beat-bounce depth. Loud = short phrases, fast committed moves,
/// bounces on every beat; quiet = long phrases, slow sweeps, breathing only.
struct Feel {
    bars: usize,
    lead: f64,
    settle: f64,
    amp: f64,
    overshoot: f64,
    bounce: f64,
}
fn feel(level: &str) -> Feel {
    match level {
        "peak" => Feel { bars: 1, lead: 0.45, settle: 0.22, amp: 1.0, overshoot: 0.1, bounce: 1.0 },
        "mid" => Feel { bars: 2, lead: 0.8, settle: 0.35, amp: 0.85, overshoot: 0.07, bounce: 0.55 },
        _ => Feel { bars: 4, lead: 1.8, settle: 0.7, amp: 0.6, overshoot: 0.0, bounce: 0.0 },
    }
}

/// Section motif: four key poses from a timbre family, alternating sides so
/// consecutive phrases travel across the body. Recurrences replay it mirrored.
fn motif_poses(s: &Sidecar, p: &SectionPlan) -> Vec<(String, [f64; 3])> {
    if p.level == "rest" {
        return vec![("rest".into(), REST_POSE)];
    }
    let t = section_traits(s, p.start, p.end);
    let family: &[&str] = if t.bright < 0.44 {
        &["fold", "sweep", "coil", "arc", "reach"]
    } else if t.bright > 0.56 || t.centroid > 0.58 {
        &["rise", "sweep", "hook", "open", "reach", "arc"]
    } else {
        &["reach", "fold", "open", "coil", "arc", "rise"]
    };
    let rot = p.motif.bytes().next().map_or(0, |b| usize::from(b.wrapping_sub(b'A')));
    let flip = p.variation % 2 == 1;
    (0..4)
        .map(|k| {
            let name = family[(rot + k * 2 + k / 2) % family.len()];
            let side = (k % 2 == 1) != flip;
            let q = if side { mirror(pose(name)) } else { pose(name) };
            let label = format!("{name} {}", if side { "L" } else { "R" });
            (label, lerp(NEUTRAL, q, feel(&p.level).amp))
        })
        .collect()
}

/// Bar lines from the detected grid: downbeat phase = beat parity (mod 4)
/// carrying most onset strength. Provisional, like the grid itself.
fn bar_lines(s: &Sidecar) -> Vec<f64> {
    let mut beats: Vec<f64> = s.beats.iter().copied().filter(|b| b.is_finite()).collect();
    beats.sort_by(f64::total_cmp);
    beats.dedup();
    if beats.len() < 8 {
        let period = 60.0 / f64::from(if s.tempo > 20.0 { s.tempo } else { 120.0 });
        beats = (0..)
            .map(|i| i as f64 * period)
            .take_while(|t| *t < s.duration)
            .collect();
    }
    let weight = |b: f64| {
        s.onsets
            .iter()
            .filter(|o| (o.t - b).abs() < 0.07)
            .map(|o| o.strength)
            .sum::<f32>()
    };
    let phase = (0..4)
        .max_by(|a, b| {
            let score = |p: usize| beats.iter().skip(p).step_by(4).map(|b| weight(*b)).sum::<f32>();
            score(*a).total_cmp(&score(*b)).then(b.cmp(a))
        })
        .unwrap_or(0);
    beats.into_iter().skip(phase).step_by(4).collect()
}

struct Arrival {
    time: f64,
    section: usize,
    step: usize,
}

fn compile(s: &Sidecar, rms: Option<&[f32]>, config: CompileConfig) -> Score {
    let limits = JointLimits::default();
    let sections = plan_sections(s, rms);
    let motifs: Vec<_> = sections.iter().map(|p| motif_poses(s, p)).collect();
    let bars = bar_lines(s);
    let beat = {
        let mut b: Vec<f64> = s.beats.iter().copied().filter(|b| b.is_finite()).collect();
        b.sort_by(f64::total_cmp);
        b
    };
    let strengths: Vec<f32> = s.onsets.iter().map(|o| o.strength).collect();
    let onset_scale = percentile(&strengths, 0.9).max(0.05);
    // A hit must stand out: top decile and well above the typical onset.
    let hit_floor = onset_scale.max(percentile(&strengths, 0.5) * 1.8);

    // Phrase arrivals: section entry downbeat, then every `bars` bar lines.
    let mut arrivals: Vec<Arrival> = Vec::new();
    for (si, p) in sections.iter().enumerate() {
        let f = feel(&p.level);
        let lines: Vec<f64> = bars
            .iter()
            .copied()
            .filter(|t| *t >= p.start - 0.3 && *t < p.end - 0.5 && *t > 0.2)
            .collect();
        let entry = lines.first().copied().unwrap_or(p.start + 0.5);
        let every = if p.level == "rest" { usize::MAX } else { f.bars };
        let mut step = 0;
        for (k, t) in std::iter::once(entry)
            .chain(lines.iter().copied().skip(1))
            .enumerate()
        {
            if k % every.max(1) == 0 && t < s.duration - 0.3 {
                // A strong onset near the bar line wins: land exactly on it.
                let t = s
                    .onsets
                    .iter()
                    .filter(|o| (o.t - t).abs() <= 0.3 && o.strength >= hit_floor && o.t > 0.2)
                    .max_by(|a, b| a.strength.total_cmp(&b.strength))
                    .map_or(t, |o| o.t);
                arrivals.push(Arrival { time: t, section: si, step });
                step += 1;
            }
        }
    }
    arrivals.dedup_by(|b, a| b.time - a.time < 0.6);

    let section_at = |t: f64| sections.iter().position(|p| t >= p.start && t < p.end).unwrap_or(sections.len() - 1);
    let mut cues = Vec::new();
    let mut q = REST_POSE;
    let mut t0 = 0.0;
    for (i, a) in arrivals.iter().enumerate() {
        let sec = &sections[a.section];
        let f = feel(&sec.level);
        let (name, wanted) = motifs[a.section][a.step % motifs[a.section].len()].clone();
        let wanted = floor_safe(wanted);
        // Lead = time the move needs at full size (speed/accel limits, with
        // anticipation + overshoot headroom). If the bar is too short, the
        // move shrinks so it still *arrives on the beat*; it never smears
        // past the arrival into the following beats.
        let available = a.time - t0;
        let target = if move_time(q, wanted, f.overshoot, &limits) <= available {
            wanted
        } else {
            let mut x = 1.0;
            while x > 0.05 && move_time(q, lerp(q, wanted, x), f.overshoot, &limits) > available {
                x -= 0.05;
            }
            lerp(q, wanted, x)
        };
        let lead = f.lead.max(move_time(q, target, f.overshoot, &limits)).min(available).max(0.12);
        // Absorb slivers of stillness shorter than 0.25 s into the move.
        let start = if a.time - lead - t0 < 0.25 { t0 } else { a.time - lead };
        if start > t0 + 1e-6 {
            cues.push(hold_cue(t0, start, q, section_at(t0), "stillness before next phrase"));
        }
        let next_start = arrivals.get(i + 1).map_or(s.duration, |n| {
            let nf = feel(&sections[n.section].level);
            let next = floor_safe(motifs[n.section][n.step % motifs[n.section].len()].1);
            let next_lead = nf.lead.max(move_time(target, next, nf.overshoot, &limits));
            (n.time - next_lead).max(a.time + f.settle + 0.1)
        });
        let end = next_start.min(s.duration).max(a.time + 0.05);
        let mut knots: Vec<(f64, &'static str, [f64; 3])> = vec![(start, "start", q)];
        if config.enable_windups && f.overshoot > 0.0 && lead > 0.3 {
            // Anticipation: brief counter-move before committing.
            knots.push((start + lead * 0.35, "preparation", lerp(q, target, -0.12)));
        }
        knots.push((a.time, "arrival", lerp(q, target, 1.0 + f.overshoot)));
        let settle_t = (a.time + f.settle).min(end);
        if settle_t < end - 0.05 && f.overshoot > 0.0 {
            knots.push((settle_t, "followThrough", target));
        }
        let sign = if name.ends_with('L') { -1.0 } else { 1.0 };
        let hits: Vec<&SidecarOnset> = if config.enable_hits {
            s.onsets
                .iter()
                .filter(|o| o.t > settle_t + 0.25 && o.t < end - 0.15 && o.strength >= hit_floor)
                .collect()
        } else {
            Vec::new()
        };
        let mut sustain: Vec<(f64, &'static str, [f64; 3])> = Vec::new();
        for o in &hits {
            let d = [4.0 * sign, 16.0 * sign, 30.0 * sign];
            let lo = if o.tone < 0.46 { -1.0 } else { 1.0 };
            sustain.push((o.t - 0.22, "hit", target));
            sustain.push((o.t, "hit", std::array::from_fn(|j| target[j] + d[j] * lo * f.amp)));
            if o.t + 0.35 < end - 0.05 {
                sustain.push((o.t + 0.35, "hit", target));
            }
        }
        if f.bounce > 0.0 {
            // Groove: dip on each beat, lift on the off-beat.
            for w in beat.windows(2).filter(|w| w[0] > settle_t + 0.1 && w[0] < end - 0.2) {
                let b = f.bounce * f.amp;
                sustain.push((w[0], "beat", [target[0] - 2.0 * b * sign, target[1] - 7.0 * b * sign, target[2] - 12.0 * b * sign]));
                let off = (w[0] + w[1]) / 2.0;
                if off < end - 0.12 {
                    sustain.push((off, "offbeat", [target[0] + 1.0 * b * sign, target[1] + 3.0 * b * sign, target[2] + 6.0 * b * sign]));
                }
            }
        } else if sec.level != "rest" && end - settle_t > 2.0 {
            // Quiet: one slow breath across the held pose.
            let mid = (settle_t + end) / 2.0;
            sustain.push((mid, "breath", [target[0] + 4.0 * sign, target[1] - 6.0, target[2] + 10.0 * sign]));
        }
        sustain.sort_by(|a, b| a.0.total_cmp(&b.0));
        // Hits win over nearby beat knots.
        let hit_times: Vec<f64> = hits.iter().map(|o| o.t).collect();
        sustain.retain(|k| k.1 == "hit" || hit_times.iter().all(|h| (k.0 - h).abs() > 0.35));
        knots.extend(sustain);
        knots.push((end, "recovery", target));
        knots.sort_by(|a, b| a.0.total_cmp(&b.0));
        let mut cleaned: Vec<(f64, &'static str, [f64; 3])> = Vec::new();
        for k in knots {
            match cleaned.last() {
                Some(l) if k.0 - l.0 < 0.08 && k.1 != "arrival" && k.1 != "recovery" && k.1 != "hit" => {}
                Some(l) if k.0 - l.0 < 0.02 => {}
                _ => cleaned.push(k),
            }
        }
        let mut out = Vec::with_capacity(cleaned.len());
        let mut prev = (start, q);
        for (i, (t, phase, want)) in cleaned.into_iter().enumerate() {
            let joints = if i == 0 { q } else { constrain(prev.1, floor_safe(want), t - prev.0, &limits) };
            out.push(Knot { time: t, phase: phase.into(), joints });
            prev = (t, joints);
        }
        q = prev.1;
        let accent = s
            .onsets
            .iter()
            .filter(|o| (o.t - a.time).abs() < 0.08)
            .map(|o| (o.strength / onset_scale).clamp(0.0, 1.0))
            .fold(0.0_f32, f32::max);
        let energy = rms.map_or_else(
            || avg(&s.energy_envelope, s.envelope_rate, start, end),
            |r| (avg(r, s.envelope_rate, start, end) / 0.3).clamp(0.0, 1.0),
        );
        cues.push(Cue {
            start,
            end,
            gesture: name.clone(),
            reason: format!(
                "{} section {} motif {} step {}: {} lands on bar {:.2}s{}{}",
                sec.level,
                a.section + 1,
                motif_label(sec),
                a.step + 1,
                if f.bars == 1 { "1-bar phrase" } else if f.bars == 2 { "2-bar phrase" } else { "4-bar phrase" },
                a.time,
                if hits.is_empty() { String::new() } else { format!(", {} onset hit(s)", hits.len()) },
                if f.bounce > 0.0 { ", beat bounce" } else { "" }
            ),
            energy: if sec.level == "rest" { 0.0 } else { energy },
            accent: accent.max(if sec.level == "peak" { 0.8 } else { 0.4 }),
            arrival_anchor: Some(a.time).filter(|t| *t > start && *t < end),
            section: Some(a.section),
            knots: out,
        });
        t0 = end;
    }
    if t0 < s.duration - 1e-9 || cues.is_empty() {
        cues.push(hold_cue(t0, s.duration, q, section_at(t0), "hold to end"));
    }
    // Section tags must not straddle: re-tag each cue by where it starts, and
    // split any cue that crosses a section edge only in metadata terms.
    for c in &mut cues {
        let si = section_at(c.start);
        if c.end <= sections[si].end + 1e-9 {
            c.section = Some(si);
        } else {
            c.section = None;
        }
    }
    Score { duration: s.duration, sections, cues, limits }
}

/// Lowest joint/tip height (cm) for the assumed 32/26/12 cm planar links.
fn lowest_point(q: [f64; 3]) -> f64 {
    let (mut h, mut y, mut low) = (0.0_f64, 0.0_f64, f64::INFINITY);
    for (len, a) in [32.0, 26.0, 12.0].into_iter().zip(q) {
        h += a.to_radians();
        y += len * h.sin();
        low = low.min(y);
    }
    low
}

/// Pull a wanted pose toward neutral until it keeps >= 8 cm floor clearance.
fn floor_safe(q: [f64; 3]) -> [f64; 3] {
    const MIN_CLEARANCE: f64 = 8.0;
    if lowest_point(q) >= MIN_CLEARANCE {
        return q;
    }
    (1..=20)
        .map(|k| lerp(q, NEUTRAL, f64::from(k) / 20.0))
        .find(|p| lowest_point(*p) >= MIN_CLEARANCE)
        .unwrap_or(NEUTRAL)
}

/// Seconds a quintic move needs within joint speed/acceleration limits,
/// including overshoot and anticipation headroom.
fn move_time(from: [f64; 3], to: [f64; 3], overshoot: f64, l: &JointLimits) -> f64 {
    (0..3)
        .map(|j| {
            let d = (to[j] - from[j]).abs() * (1.0 + overshoot) * 1.3;
            (Q_V * d / l.max_speed_degrees_per_second[j])
                .max((Q_A * d / l.max_acceleration_degrees_per_second2[j]).sqrt())
        })
        .fold(0.0, f64::max)
}

fn hold_cue(start: f64, end: f64, q: [f64; 3], section: usize, why: &str) -> Cue {
    Cue {
        start,
        end,
        gesture: "hold".into(),
        reason: why.into(),
        energy: 0.0,
        accent: 0.0,
        arrival_anchor: None,
        section: Some(section),
        knots: vec![
            Knot { time: start, phase: "hold".into(), joints: q },
            Knot { time: end, phase: "hold".into(), joints: q },
        ],
    }
}

/// `C` for the first statement, `C2`, `C3`... for recurrences.
fn motif_label(p: &SectionPlan) -> String {
    match p.variation {
        0 => p.motif.clone(),
        v => format!("{}{}", p.motif, v + 1),
    }
}

/// Raw section character used for gesture family and reasons.
#[derive(Debug, Clone, Copy)]
struct SectionTraits {
    bright: f32,
    centroid: f32,
    density: f32,
}

const FEATURE_DIMS: usize = 8;

/// Per-frame z-scored features (loudness, five bands, centroid, flatness)
/// with prefix sums, so any window mean is O(1).
struct Features {
    rate: f64,
    prefix: Vec<[f64; FEATURE_DIMS]>,
}

impl Features {
    fn new(s: &Sidecar, rms: Option<&[f32]>) -> Self {
        let b = &s.band_envelope;
        let dims: [&[f32]; FEATURE_DIMS] = [
            rms.unwrap_or(&s.energy_envelope),
            &b.sub,
            &b.low,
            &b.mid,
            &b.presence,
            &b.air,
            &s.centroid_envelope,
            &s.flatness_envelope,
        ];
        let rate = f64::from(s.envelope_rate);
        let n = dims
            .iter()
            .map(|d| d.len())
            .min()
            .unwrap_or(0)
            .min((s.duration * rate).ceil() as usize);
        let stats: Vec<(f64, f64)> = dims
            .iter()
            .map(|d| {
                let v = &d[..n];
                let mean = v.iter().map(|x| f64::from(*x)).sum::<f64>() / n.max(1) as f64;
                let var = v.iter().map(|x| (f64::from(*x) - mean).powi(2)).sum::<f64>()
                    / n.max(1) as f64;
                (mean, if var > 1e-12 { var.sqrt() } else { 1.0 })
            })
            .collect();
        let mut prefix = vec![[0.0; FEATURE_DIMS]];
        for i in 0..n {
            let mut next = *prefix.last().unwrap();
            for (k, d) in dims.iter().enumerate() {
                let x = f64::from(d[i]);
                next[k] += if x.is_finite() { (x - stats[k].0) / stats[k].1 } else { 0.0 };
            }
            prefix.push(next);
        }
        Self { rate, prefix }
    }
    fn len(&self) -> usize {
        self.prefix.len() - 1
    }
    fn mean_idx(&self, a: usize, b: usize) -> [f64; FEATURE_DIMS] {
        let (a, b) = (a.min(self.len()), b.min(self.len()));
        if b <= a {
            return [0.0; FEATURE_DIMS];
        }
        std::array::from_fn(|k| (self.prefix[b][k] - self.prefix[a][k]) / (b - a) as f64)
    }
    fn mean(&self, start: f64, end: f64) -> [f64; FEATURE_DIMS] {
        let a = (start * self.rate).floor() as usize;
        let b = ((end * self.rate).ceil() as usize).max(a + 1);
        self.mean_idx(a, b)
    }
}

fn distance(a: &[f64; FEATURE_DIMS], b: &[f64; FEATURE_DIMS]) -> f64 {
    (a.iter().zip(b).map(|(x, y)| (x - y).powi(2)).sum::<f64>() / FEATURE_DIMS as f64).sqrt()
}

fn section_traits(s: &Sidecar, start: f64, end: f64) -> SectionTraits {
    let low = avg(&s.band_envelope.low, s.envelope_rate, start, end)
        + avg(&s.band_envelope.sub, s.envelope_rate, start, end);
    let high = avg(&s.band_envelope.presence, s.envelope_rate, start, end)
        + avg(&s.band_envelope.air, s.envelope_rate, start, end);
    let count = s.onsets.iter().filter(|o| o.t >= start && o.t < end).count();
    SectionTraits {
        bright: high / (low + high).max(1e-6),
        centroid: avg(&s.centroid_envelope, s.envelope_rate, start, end),
        density: count as f32 / (end - start).max(1e-6) as f32,
    }
}

/// Section cuts from multi-feature novelty: distance between 4s window means
/// before/after each frame, peaks above median + 2·MAD, >=8s apart. Tuned on
/// the supplied track (19 sections, 9–37s); heuristic, not verse/chorus labels.
fn novelty_cuts(features: &Features, duration: f64) -> Vec<f64> {
    const MIN_SECTION: f64 = 8.0;
    let win = (4.0 * features.rate).round().max(1.0) as usize;
    let n = features.len();
    if n <= 2 * win {
        return Vec::new();
    }
    let novelty: Vec<f64> = (0..n)
        .map(|i| {
            if i < win || i + win > n {
                0.0
            } else {
                distance(&features.mean_idx(i - win, i), &features.mean_idx(i, i + win))
            }
        })
        .collect();
    let mut active: Vec<f64> = novelty.iter().copied().filter(|x| *x > 0.0).collect();
    if active.is_empty() {
        return Vec::new();
    }
    let median = |v: &mut Vec<f64>| {
        v.sort_by(f64::total_cmp);
        v[v.len() / 2]
    };
    let med = median(&mut active);
    let mad = median(&mut active.iter().map(|x| (x - med).abs()).collect());
    // Absolute floor keeps ripple inside homogeneous material from cutting.
    let threshold = (med + 2.0 * mad).max(0.3);
    let mut peaks: Vec<usize> = (win..=n - win)
        .filter(|&i| {
            novelty[i] > threshold
                && novelty[i.saturating_sub(win)..(i + win + 1).min(n)]
                    .iter()
                    .all(|x| *x <= novelty[i])
        })
        .collect();
    peaks.sort_by(|a, b| novelty[*b].total_cmp(&novelty[*a]));
    let mut cuts: Vec<f64> = Vec::new();
    for i in peaks {
        let t = i as f64 / features.rate;
        if t >= MIN_SECTION * 0.75
            && t <= duration - MIN_SECTION * 0.75
            && cuts.iter().all(|c| (c - t).abs() >= MIN_SECTION)
        {
            cuts.push(t);
        }
    }
    cuts
}

/// Split the song into sustained regimes, then label recurrences.
/// Uses sidecar sections only when they describe real structure (>=2 long
/// sections); otherwise multi-feature novelty (see `novelty_cuts`).
fn plan_sections(s: &Sidecar, rms: Option<&[f32]>) -> Vec<SectionPlan> {
    const MIN_SECTION: f64 = 8.0;
    let features = Features::new(s, rms);
    let usable: Vec<_> = s
        .sections
        .iter()
        .filter(|x| x.end - x.start >= MIN_SECTION)
        .collect();
    let cuts = if usable.len() >= 2 {
        usable.iter().map(|x| x.start).collect()
    } else {
        novelty_cuts(&features, s.duration)
    };
    let mut cuts: Vec<f64> = cuts
        .into_iter()
        .map(|t| nearest_beat(&s.beats, t).unwrap_or(t))
        .filter(|t| *t >= MIN_SECTION * 0.75 && *t <= s.duration - MIN_SECTION * 0.75)
        .collect();
    cuts.sort_by(f64::total_cmp);
    cuts.dedup_by(|a, b| *a - *b < MIN_SECTION * 0.75);
    let mut edges = vec![0.0];
    edges.extend(cuts);
    edges.push(s.duration);

    let mut plans: Vec<SectionPlan> = Vec::new();
    let mut vectors: Vec<[f64; FEATURE_DIMS]> = Vec::new();
    let mut motifs = 0u8;
    for w in edges.windows(2) {
        let (start, end) = (w[0], w[1]);
        let v = features.mean(start, end);
        let t = section_traits(s, start, end);
        // Loudness relative to this song (z-score), absolute RMS only for rest.
        let silent = rms.map_or_else(
            || avg(&s.energy_envelope, s.envelope_rate, start, end) < 0.045,
            |r| avg(r, s.envelope_rate, start, end) < 0.005,
        );
        let class = if silent {
            "rest"
        } else if v[0] < -0.6 {
            "quiet"
        } else if v[0] > 0.35 {
            "peak"
        } else {
            "mid"
        };
        let overlap = |a0: f64, a1: f64, b0: f64, b1: f64| (a1.min(b1) - a0.max(b0)).max(0.0);
        let sidecar_repeat = s.repeats.iter().flatten().filter(|r| r.similarity >= 0.5).find_map(|r| {
            (overlap(r.b_start, r.b_end, start, end) >= 0.5 * (end - start)).then(|| {
                plans.iter().position(|p| {
                    p.level == class
                        && overlap(r.a_start, r.a_end, p.start, p.end) >= 0.5 * (p.end - p.start)
                })
            })?
        });
        let similar = plans
            .iter()
            .zip(&vectors)
            .enumerate()
            .filter(|(_, (p, _))| p.level == class && class != "rest")
            .map(|(j, (_, u))| (j, distance(&v, u)))
            .filter(|(_, d)| *d < 0.3)
            .min_by(|a, b| a.1.total_cmp(&b.1));
        let (repeat_of, why) = match (sidecar_repeat, similar) {
            (Some(j), _) => (Some(j), format!("sidecar repeat of section {}", j + 1)),
            (None, Some((j, d))) => (Some(j), format!("feature match section {} (d {d:.2})", j + 1)),
            (None, None) => (None, "new material".to_string()),
        };
        let (motif, variation) = match repeat_of {
            Some(j) => {
                let m = plans[j].motif.clone();
                let n = plans.iter().filter(|p| p.motif == m).count() as u32;
                (m, n)
            }
            None if class == "rest" => ("rest".to_string(), 0),
            None => {
                let m = char::from(b'A' + motifs % 26).to_string();
                motifs += 1;
                (m, 0)
            }
        };
        plans.push(SectionPlan {
            start,
            end,
            level: class.into(),
            motif,
            variation,
            repeat_of,
            reason: format!(
                "{why}; loudness z {:+.2}, bright {:.2}, onsets {:.1}/s",
                v[0], t.bright, t.density
            ),
        });
        vectors.push(v);
    }
    plans
}

fn nearest_beat(beats: &[f64], target: f64) -> Option<f64> {
    beats
        .iter()
        .copied()
        .filter(|b| b.is_finite())
        .min_by(|a, b| (a - target).abs().total_cmp(&(b - target).abs()))
        .filter(|b| (b - target).abs() <= 0.22)
}

fn constrain(from: [f64; 3], wanted: [f64; 3], dt: f64, l: &JointLimits) -> [f64; 3] {
    std::array::from_fn(|j| {
        let travel = (l.max_speed_degrees_per_second[j] * dt / Q_V)
            .min(l.max_acceleration_degrees_per_second2[j] * dt * dt / Q_A)
            .max(0.);
        wanted[j]
            .clamp(from[j] - travel, from[j] + travel)
            .clamp(l.min_degrees[j], l.max_degrees[j])
    })
}
fn sample_knots(k: &[Knot], t: f64) -> [f64; 3] {
    if k.is_empty() {
        return REST_POSE;
    }
    if t <= k[0].time {
        return k[0].joints;
    }
    for w in k.windows(2) {
        if t <= w[1].time {
            let x = ((t - w[0].time) / (w[1].time - w[0].time)).clamp(0., 1.);
            let q = x * x * x * (10. + x * (-15. + 6. * x));
            return std::array::from_fn(|j| w[0].joints[j] + (w[1].joints[j] - w[0].joints[j]) * q);
        }
    }
    k.last().unwrap().joints
}
fn percentile(v: &[f32], q: f64) -> f32 {
    let mut x = v
        .iter()
        .copied()
        .filter(|v| v.is_finite())
        .collect::<Vec<_>>();
    if x.is_empty() {
        return 1.;
    }
    x.sort_by(f32::total_cmp);
    x[((x.len() - 1) as f64 * q).round() as usize]
}
fn avg(v: &[f32], rate: f32, start: f64, end: f64) -> f32 {
    if v.is_empty() {
        return 0.;
    }
    let a = ((start * f64::from(rate)).floor() as usize).min(v.len() - 1);
    let b = ((end * f64::from(rate)).ceil() as usize)
        .min(v.len())
        .max(a + 1);
    v[a..b].iter().sum::<f32>() / (b - a) as f32
}

#[cfg(test)]
mod tests {
    use super::*;

    /// `secs` seconds at 10 Hz, 120 BPM, constant level and brightness.
    fn fixture(secs: usize, level: f32, rms: Option<f32>, onsets: &str) -> String {
        let n = secs * 10;
        let v = |x: f32| vec![x.to_string(); n].join(",");
        let beats: Vec<String> = (0..secs * 2).map(|i| (i as f64 * 0.5).to_string()).collect();
        let r = rms.map(|x| format!(",\"rmsEnvelope\":[{}]", v(x))).unwrap_or_default();
        format!(
            r#"{{"schema":3,"duration":{secs}.0,"tempo":120.0,"beats":[{}],"sections":[],"events":[],"onsets":[{onsets}],"energyEnvelope":[{e}],"bandEnvelope":{{"sub":[{e}],"low":[{e}],"mid":[{e}],"presence":[{e}],"air":[{e}]}},"centroidEnvelope":[{e}],"flatnessEnvelope":[{e}],"envelopeRate":10.0{r}}}"#,
            beats.join(","),
            e = v(level)
        )
    }

    #[test]
    fn vocabulary_and_mirrors_clear_floor_and_limits() {
        let l = JointLimits::default();
        for (name, q) in POSES.iter().map(|p| (p.0, p.1)).chain([("rest", REST_POSE)]) {
            for p in [q, mirror(q)] {
                assert!(lowest_point(p) >= 8.0, "{name} {p:?} low {}", lowest_point(p));
                assert!((0..3).all(|j| p[j] >= l.min_degrees[j] && p[j] <= l.max_degrees[j]), "{name}");
            }
        }
        assert_eq!(mirror(mirror([30.0, -20.0, 5.0])), [30.0, -20.0, 5.0]);
    }

    #[test]
    fn silence_is_stillness() {
        let s = compile_sidecar_json(&fixture(12, 0.7, Some(0.0), "")).unwrap();
        let q = s.sample(0.0);
        assert!((0..120).all(|i| s.sample(i as f64 / 10.0) == q));
    }

    #[test]
    fn moves_arrive_on_the_bar_not_after_it() {
        let s = compile_sidecar_json(&fixture(24, 0.8, None, "")).unwrap();
        let moves: Vec<_> = s.cues.iter().filter(|c| c.arrival_anchor.is_some()).collect();
        assert!(moves.len() >= 4, "{}", moves.len());
        for c in moves {
            let k = |p: &str| c.knots.iter().find(|k| k.phase == p).unwrap().joints;
            let travel = (0..3).map(|j| (k("arrival")[j] - k("start")[j]).abs()).fold(0.0, f64::max);
            let drift = (0..3).map(|j| (k("recovery")[j] - k("arrival")[j]).abs()).fold(0.0, f64::max);
            // Regression: truncated leads once smeared the move across the bar.
            assert!(drift < 0.35 * travel.max(20.0), "{}: travel {travel:.1} drift {drift:.1}", c.gesture);
        }
    }

    #[test]
    fn dense_sampling_respects_limits() {
        let s = compile_sidecar_json(&fixture(16, 0.9, None, r#"{"t":5.3,"strength":1.0,"tone":0.2,"pan":0.0}"#)).unwrap();
        let dt = 0.001;
        let (mut p, mut v) = (s.sample(0.0), [0.0; 3]);
        for i in 1..=(s.duration / dt) as usize {
            let q = s.sample(i as f64 * dt);
            for j in 0..3 {
                let nv = (q[j] - p[j]) / dt;
                assert!(nv.abs() <= s.limits.max_speed_degrees_per_second[j] * 1.01);
                if i > 2 {
                    assert!(((nv - v[j]) / dt).abs() <= s.limits.max_acceleration_degrees_per_second2[j] * 1.02);
                }
                v[j] = nv;
            }
            p = q;
        }
    }

    #[test]
    fn malformed_rms_is_rejected_without_time_compression() {
        let bad = fixture(8, 0.5, Some(0.1), "").replacen("\"rmsEnvelope\":[0.1,", "\"rmsEnvelope\":[\"bad\",", 1);
        assert!(compile_sidecar_json(&bad).unwrap_err().contains("rmsEnvelope[0]"));
        let short = fixture(8, 0.5, None, "").replace("\"envelopeRate\":10.0", "\"envelopeRate\":10.0,\"rmsEnvelope\":[0.1,0.1]");
        assert!(compile_sidecar_json(&short).unwrap_err().contains("needs at least 80"));
    }
}
