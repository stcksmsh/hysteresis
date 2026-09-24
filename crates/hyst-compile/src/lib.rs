//! Deterministic single-arm offline cue compiler.

use hyst_core::sidecar::Sidecar;
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
    /// Joint velocity (deg/s) passing through this knot. Absent = full stop.
    /// Segments are quintic Hermite: C2, zero acceleration at knots.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub velocity: Option<[f64; 3]>,
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
    /// Overlapping action: joint j samples the knot curve at `t - lag[j]`,
    /// so elbow and wrist trail the shoulder. Zero in older scores.
    #[serde(default, rename = "jointLagSeconds")]
    pub joint_lag_seconds: [f64; 3],
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
        std::array::from_fn(|j| {
            let t = (time - self.joint_lag_seconds[j]).clamp(0.0, self.duration);
            let i = self
                .cues
                .partition_point(|c| c.end < t)
                .min(self.cues.len() - 1);
            sample_knots(&self.cues[i].knots, t)[j]
        })
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
    let elements = match root.get("elements") {
        None => None,
        Some(v) => Some(parse_elements(v, (sidecar.duration * f64::from(sidecar.envelope_rate)).ceil() as usize)?),
    };
    Ok(compile(&sidecar, rms.as_deref(), elements.as_ref(), config))
}

fn parse_elements(v: &serde_json::Value, required: usize) -> Result<Elements, String> {
    let series = |name: &str, lo: f64| -> Result<Vec<f32>, String> {
        let a = v.get(name).and_then(|x| x.as_array()).ok_or(format!("elements.{name} must be an array"))?;
        if a.len() < required {
            return Err(format!("elements.{name} has {} samples; needs {required}", a.len()));
        }
        a.iter()
            .enumerate()
            .map(|(i, x)| {
                x.as_f64()
                    .filter(|x| x.is_finite() && *x >= lo && *x <= 10.0)
                    .map(|x| x as f32)
                    .ok_or(format!("elements.{name}[{i}] out of range"))
            })
            .collect()
    };
    let onsets = v
        .get("melodyOnsets")
        .and_then(|x| x.as_array())
        .map(|a| a.iter().filter_map(|x| x.as_f64()).filter(|x| x.is_finite()).collect())
        .unwrap_or_default();
    Ok(Elements {
        drums: series("drums", 0.0)?,
        bass: series("bass", 0.0)?,
        vocals: series("vocals", 0.0)?,
        synth: series("synth", 0.0)?,
        melody: series("melody", -1.0)?,
        melody_onsets: onsets,
        groove: v
            .get("grooveSlots")
            .and_then(|x| x.as_array())
            .map(|a| {
                a.iter()
                    .filter_map(|r| {
                        let r = r.as_array()?;
                        let g: Vec<f64> = r.iter().filter_map(|x| x.as_f64()).collect();
                        (g.len() == 3 && g.iter().all(|x| x.is_finite())).then(|| [g[0], g[1].clamp(0.0, 1.0), g[2].clamp(0.0, 1.0)])
                    })
                    .collect()
            })
            .unwrap_or_default(),
    })
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

/// Per-level phrasing: bars per home move, pose amplitude, voice-layer gain.
/// Loud = pose changes every 2 bars and a strong voice; quiet = every 4 bars,
/// small voice (mostly breathing with the dominant element).
struct Feel {
    bars: usize,
    amp: f64,
    layer: f64,
}
fn feel(level: &str) -> Feel {
    match level {
        "peak" => Feel { bars: 2, amp: 1.0, layer: 1.0 },
        "mid" => Feel { bars: 4, amp: 0.85, layer: 0.8 },
        _ => Feel { bars: 4, amp: 0.6, layer: 0.5 },
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
    // Candidates: each family pose on both sides. Start from the motif's own
    // pose, then always take the unused candidate farthest from the last one,
    // so consecutive phrases contrast instead of nudging.
    let mut pool: Vec<(String, [f64; 3])> = family
        .iter()
        .flat_map(|n| [(format!("{n} R"), pose(n)), (format!("{n} L"), mirror(pose(n)))])
        .collect();
    let first = pool.remove((rot * 2) % pool.len());
    let mut chosen = vec![first];
    while chosen.len() < 4 && !pool.is_empty() {
        let last = chosen.last().unwrap().1;
        let far = |q: &[f64; 3]| (0..3).map(|j| (q[j] - last[j]).abs()).sum::<f64>();
        let i = (0..pool.len())
            .max_by(|a, b| far(&pool[*a].1).total_cmp(&far(&pool[*b].1)).then(b.cmp(a)))
            .unwrap();
        chosen.push(pool.remove(i));
    }
    // Recurrence variation: mirror the whole motif (L <-> R).
    let amp = feel(&p.level).amp;
    chosen
        .into_iter()
        .map(|(name, q)| {
            let (name, q) = if flip {
                let swapped = match name.rsplit_once(' ') {
                    Some((n, "R")) => format!("{n} L"),
                    Some((n, _)) => format!("{n} R"),
                    None => name,
                };
                (swapped, mirror(q))
            } else {
                (name, q)
            };
            (name, lerp(NEUTRAL, q, amp))
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

/// Per-element activity from `scripts/arm_elements.py` (0..~1 each, own
/// range), sampled at `envelopeRate`. `melody` is 0..1 height or -1.
#[derive(Debug, Clone, Default)]
pub struct Elements {
    pub drums: Vec<f32>,
    pub bass: Vec<f32>,
    pub vocals: Vec<f32>,
    pub synth: Vec<f32>,
    pub melody: Vec<f32>,
    pub melody_onsets: Vec<f64>,
    /// `[t, kick, snare]` per 8th-note slot (0..1 relative strengths).
    pub groove: Vec<[f64; 3]>,
}

const ELEMENTS: [&str; 4] = ["vocals", "synth", "bass", "drums"];

struct Phrase {
    time: f64,
    section: usize,
    step: usize,
}

/// Choreography = slow *home path* between key poses (one move per phrase:
/// 4 bars, 2 in loud sections) + a *voice* layer that moves to whichever
/// musical element dominates right now, blended by dominance:
///   vocals: height follows the melody, wrist articulates sung notes
///   synth:  slow flowing orbit (one loop per 2 bars)
///   bass:   weighted side-to-side sway, one swing per bar
///   drums:  bounce on each beat
/// Knots every half beat, then flow tangents: continuous, no stop-go.
fn compile(s: &Sidecar, rms: Option<&[f32]>, el: Option<&Elements>, config: CompileConfig) -> Score {
    let limits = JointLimits::default();
    let sections = plan_sections(s, rms);
    let motifs: Vec<_> = sections.iter().map(|p| motif_poses(s, p)).collect();
    let bars = bar_lines(s);
    let mut beats: Vec<f64> = s.beats.iter().copied().filter(|b| b.is_finite()).collect();
    beats.sort_by(f64::total_cmp);
    let mut gaps: Vec<f64> = bars.windows(2).map(|w| w[1] - w[0]).collect();
    gaps.sort_by(f64::total_cmp);
    let bar_len = gaps.get(gaps.len() / 2).copied().unwrap_or(2.0);
    let rate = f64::from(s.envelope_rate);
    let at = |v: &[f32], t: f64| -> f64 {
        v.get(((t * rate).max(0.0) as usize).min(v.len().saturating_sub(1)))
            .map_or(0.0, |x| f64::from(*x))
    };
    let window = |v: &[f32], t: f64, half: f64| -> f64 {
        let n = 9;
        (0..n).map(|k| at(v, t - half + 2.0 * half * k as f64 / (n - 1) as f64)).sum::<f64>() / n as f64
    };
    let section_at = |t: f64| sections.iter().position(|p| t >= p.start && t < p.end).unwrap_or(sections.len() - 1);

    // Phrase downbeats: each section's first bar, then every `bars` bars.
    let mut phrases: Vec<Phrase> = Vec::new();
    for (si, p) in sections.iter().enumerate() {
        let f = feel(&p.level);
        let lines: Vec<f64> = bars.iter().copied().filter(|t| *t >= p.start - 0.05 && *t < p.end - 0.5 && *t > 0.2).collect();
        let every = if p.level == "rest" { usize::MAX } else { f.bars };
        let mut step = 0;
        let entry = lines.first().copied().unwrap_or(p.start.max(0.3));
        for (k, t) in std::iter::once(entry).chain(lines.iter().copied().skip(1)).enumerate() {
            if k % every.max(1) == 0 && t < s.duration - 0.3 {
                phrases.push(Phrase { time: t, section: si, step });
                step += 1;
            }
        }
    }
    phrases.dedup_by(|b, a| b.time - a.time < 0.6);
    let planned = |a: &Phrase| -> [f64; 3] {
        let m = &motifs[a.section];
        let base = m[a.step % m.len()].1;
        let c = (a.step / m.len()) as i64;
        let off = if c == 0 || sections[a.section].level == "rest" {
            [0.0; 3]
        } else {
            [((c * 37) % 21 - 10) as f64, ((c * 53) % 31 - 15) as f64, ((c * 71) % 41 - 20) as f64]
        };
        floor_safe(std::array::from_fn(|j| base[j] + off[j]))
    };
    let targets: Vec<[f64; 3]> = phrases.iter().map(planned).collect();
    // Home path: glide into each phrase pose over up to one bar, landing on
    // the phrase downbeat; hold it otherwise (the voice layer keeps moving).
    let glide: Vec<f64> = (0..phrases.len())
        .map(|i| {
            let from = if i == 0 { REST_POSE } else { targets[i - 1] };
            let room = phrases[i].time - if i == 0 { 0.0 } else { phrases[i - 1].time + 0.3 };
            bar_len.max(move_time(from, targets[i], 0.0, &limits) * 1.2).min(room.max(0.3))
        })
        .collect();
    let home = |t: f64| -> [f64; 3] {
        let i = phrases.partition_point(|p| p.time <= t);
        let prev = if i == 0 { REST_POSE } else { targets[i - 1] };
        match phrases.get(i) {
            Some(p) if t > p.time - glide[i] => {
                let x = (t - (p.time - glide[i])) / glide[i];
                lerp(prev, targets[i], x * x * x * (10.0 + x * (-15.0 + 6.0 * x)))
            }
            _ => prev,
        }
    };
    let zeros = [0.0_f32; 1];
    let (drums, bass, vocals, synth, melody) = match el {
        Some(e) => (&e.drums[..], &e.bass[..], &e.vocals[..], &e.synth[..], &e.melody[..]),
        None => (&s.energy_envelope[..], &zeros[..], &zeros[..], &zeros[..], &zeros[..]),
    };
    // Dominance weights over ±1.5 s: phrase-scale, so the lead element does
    // not flicker between beats and styles cross-fade.
    let weights = |t: f64| -> [f64; 4] {
        let voiced = {
            let n = 9;
            (0..n).filter(|k| at(melody, t - 1.5 + 3.0 * *k as f64 / (n - 1) as f64) >= 0.0).count() as f64 / n as f64
        };
        let score = [
            window(vocals, t, 1.5) + 0.15 * voiced,
            window(synth, t, 1.5),
            window(bass, t, 1.5),
            window(drums, t, 1.5),
        ];
        let e: Vec<f64> = score.iter().map(|x| (x / 0.08).exp()).collect();
        let sum: f64 = e.iter().sum::<f64>().max(1e-12);
        std::array::from_fn(|k| e[k] / sum)
    };
    let bar_phase = |t: f64| -> f64 {
        let i = bars.partition_point(|b| *b <= t);
        if i == 0 || i >= bars.len() {
            return ((t / bar_len).fract() + 1.0).fract();
        }
        (t - bars[i - 1]) / (bars[i] - bars[i - 1]) + (i % 2) as f64
    };
    let tau = std::f64::consts::TAU;
    let voice = |t: f64, gain: f64, side: f64, home: [f64; 3]| -> ([f64; 3], [f64; 4]) {
        let w = weights(t);
        let mut d = [0.0; 3];
        // vocals: melody height -> shoulder lift + elbow opening; notes flick wrist.
        let m = window(melody, t, 0.15);
        let lvl = window(vocals, t, 0.3);
        if m >= 0.0 {
            let h = (m - 0.5) * 2.0;
            let note = el.map_or(0.0, |e| {
                e.melody_onsets.iter().map(|o| (-((t - o) / 0.12).powi(2)).exp()).fold(0.0, f64::max)
            });
            // Pull toward a raised pose when the melody is high, a lowered
            // one when low (pose space, so "up" means up for any home pose).
            let (goal, k) = if h >= 0.0 { ([90.0, -10.0, 10.0], 0.55 * h) } else { ([100.0, -115.0, -35.0], -0.45 * h) };
            let k = k * lvl.max(0.5);
            let v = [
                (goal[0] - home[0]) * k + side * 8.0,
                (goal[1] - home[1]) * k,
                (goal[2] - home[2]) * k + 22.0 * note * side,
            ];
            (0..3).for_each(|j| d[j] += w[0] * v[j]);
        }
        // synth: orbit, two bars per loop; radius with synth level.
        let ph = tau * bar_phase(t) / 2.0;
        let r = 10.0 + 14.0 * window(synth, t, 0.5);
        let v = [r * ph.sin() * side, r * 1.4 * ph.cos(), r * 1.2 * (ph + 1.2).sin()];
        (0..3).for_each(|j| d[j] += w[1] * v[j]);
        // bass: one heavy swing per bar, arm sinks.
        let b = (tau * bar_phase(t) / 2.0).sin();
        let lvl = window(bass, t, 0.5);
        let v = [28.0 * b * lvl.max(0.5), -16.0 - 10.0 * lvl, 14.0 * b];
        (0..3).for_each(|j| d[j] += w[2] * v[j]);
        // Drums are not an expression style: the groove layer carries them
        // under everything. When drums dominate, expression eases back.
        (d.map(|x| x * gain * (1.0 - 0.5 * w[3])), w)
    };

    // Groove slots: detected kick/snare strengths per 8th note, or (without
    // elements) a steady on-beat pulse.
    let slots: Vec<[f64; 3]> = match el.map(|e| &e.groove) {
        Some(g) if !g.is_empty() => g.clone(),
        _ => beats
            .windows(2)
            .flat_map(|w| [[w[0], 0.7, 0.0], [(w[0] + w[1]) / 2.0, 0.1, 0.0]])
            .collect(),
    };
    // Groove: the body keeps time under every style. Dip lands on the kick,
    // the wrist snaps on the snare, sized by how hard the drums play.
    let groove_at = |slot: &[f64; 3], side: f64, level_gain: f64| -> [f64; 3] {
        let lvl = window(drums, slot[0], 0.3);
        if lvl < 0.1 {
            return [0.0; 3];
        }
        let g = level_gain * (0.35 + 0.65 * lvl.min(1.0));
        let (k, n) = (slot[1], slot[2] * (1.0 - 0.5 * slot[1]));
        [
            // Sized to the acceleration budget at 8th-note spacing (~0.27 s).
            g * (-6.0 * k + 3.0 * n) * side,
            g * (-20.0 * k + 6.0 * n),
            g * (-20.0 * k + 16.0 * n) * side,
        ]
    };
    let mut cues = Vec::new();
    let first = phrases.first().map_or(s.duration, |p| (p.time - glide[0]).max(0.0));
    if first > 0.0 {
        cues.push(hold_cue(0.0, first, REST_POSE, 0, "stillness before first phrase"));
    }
    let mut q = REST_POSE;
    let mut current_lead = 0usize;
    for (i, p) in phrases.iter().enumerate() {
        let sec = &sections[p.section];
        let f = feel(&sec.level);
        let start = if i == 0 { first } else { cues.last().map_or(0.0, |c: &Cue| c.end) };
        let end = phrases.get(i + 1).map_or(s.duration, |n| n.time - glide[i + 1]).max(p.time + 0.1);
        let side = if motifs[p.section][p.step % motifs[p.section].len()].0.ends_with('L') { -1.0 } else { 1.0 };
        // Knots: every 8th-note groove slot, plus the phrase arrival; home +
        // expression + groove are sampled at each. (A 16th-note rebound was
        // tried: bouncing at that rate exceeds joint acceleration limits.)
        let mut times: Vec<f64> = vec![start];
        let mut hits: Vec<(f64, [f64; 3])> = Vec::new();
        let level_gain = if sec.level == "peak" { 1.0 } else { 0.9 };
        for w in slots.windows(2).filter(|w| w[0][0] > start + 0.05 && w[0][0] < end - 0.05) {
            times.push(w[0][0]);
            hits.push((w[0][0], groove_at(&w[0], side, level_gain)));
        }
        if times.len() == 1 {
            // No drums in this span: keep a half-second sampling for expression.
            let mut t = start + 0.5;
            while t < end - 0.08 {
                times.push(t);
                t += 0.5;
            }
        }
        times.push(end);
        // The phrase arrival is exact; drop grid knots crowding it.
        let arrival = p.time;
        if arrival > start + 0.02 && arrival < end - 0.02 {
            times.retain(|t| (t - arrival).abs() >= 0.08 || *t == start || *t == end);
            times.push(arrival);
        }
        times.sort_by(f64::total_cmp);
        times.dedup_by(|b, a| *b - *a < 1e-9);
        let mut knots = Vec::with_capacity(times.len());
        let mut lead_votes = [0.0; 4];
        let mut prev = (start, q);
        for (k, &t) in times.iter().enumerate() {
            let gain = if sec.level == "rest" { 0.0 } else { f.layer * if config.enable_hits { 1.0 } else { 0.8 } };
            let h = home(t);
            let (d, w) = voice(t, gain, side, h);
            (0..4).for_each(|j| lead_votes[j] += w[j]);
            // Label hysteresis: switch only when another element clearly leads.
            let top = (0..4).max_by(|a, b| w[*a].total_cmp(&w[*b])).unwrap();
            if w[top] > w[current_lead] + 0.25 {
                current_lead = top;
            }
            let lead = current_lead;
            let g = if sec.level == "rest" {
                [0.0; 3]
            } else {
                hits.iter().find(|x| (x.0 - t).abs() < 1e-9).map_or([0.0; 3], |x| x.1)
            };
            let want = floor_safe(std::array::from_fn(|j| h[j] + d[j] + g[j]));
            let joints = if k == 0 { q } else { constrain(prev.1, want, t - prev.0, &limits) };
            let phase = if (t - p.time).abs() < 1e-9 { "arrival".to_string() } else if sec.level == "rest" { "hold".to_string() } else { ELEMENTS[lead].to_string() };
            knots.push(Knot { time: t, phase, joints, velocity: None });
            prev = (t, joints);
        }
        q = prev.1;
        let lead = (0..4).max_by(|a, b| lead_votes[*a].total_cmp(&lead_votes[*b])).unwrap();
        let energy = rms.map_or_else(
            || avg(&s.energy_envelope, s.envelope_rate, start, end),
            |r| (avg(r, s.envelope_rate, start, end) / 0.3).clamp(0.0, 1.0),
        );
        let name = motifs[p.section][p.step % motifs[p.section].len()].0.clone();
        cues.push(Cue {
            start,
            end,
            gesture: name,
            reason: format!(
                "{} section {} motif {} phrase {}: lands {:.2}s, following {}",
                sec.level,
                p.section + 1,
                motif_label(sec),
                p.step + 1,
                p.time,
                if sec.level == "rest" { "silence" } else { ELEMENTS[lead] }
            ),
            energy: if sec.level == "rest" { 0.0 } else { energy },
            accent: if sec.level == "peak" { 0.8 } else { 0.4 },
            arrival_anchor: Some(p.time).filter(|t| *t > start && *t < end),
            section: Some(p.section),
            knots,
        });
    }
    if cues.last().is_none_or(|c| c.end < s.duration - 1e-9) {
        let t0 = cues.last().map_or(0.0, |c| c.end);
        cues.push(hold_cue(t0, s.duration, q, section_at(t0), "hold to end"));
    }
    for c in &mut cues {
        let si = section_at(c.start);
        c.section = (c.end <= sections[si].end + 1e-9).then_some(si);
    }
    add_flow(&mut cues, &limits, 0.9);
    Score {
        duration: s.duration,
        joint_lag_seconds: [0.0, 0.05, 0.11],
        sections,
        cues,
        limits,
    }
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
            Knot { time: start, phase: "hold".into(), joints: q, velocity: None },
            Knot { time: end, phase: "hold".into(), joints: q, velocity: None },
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

/// Novelty peaks sit where *all* features changed most, which on the supplied
/// track landed 6–9 s after the audible loudness change. Move each cut to the
/// earliest strong loudness step on a bar line within ±9 s, in the direction of the
/// overall change: a rise when entering louder material, a fall when leaving.
fn refine_cut(features: &Features, bars: &[f64], prev: f64, cut: f64, next: f64) -> f64 {
    let loud = |a: f64, b: f64| features.mean(a.max(0.0), b)[0];
    // Direction from whole neighbouring sections, so a short dip or push
    // right at the edge cannot flip it.
    let dir = (loud(cut, next) - loud(prev, cut)).signum();
    // Sections start on downbeats: score bar lines within ±6 s with 4 s
    // windows (loudness pumps per beat, shorter windows are noise).
    // Novelty cuts were measured up to ~9 s off; stay between neighbours.
    let lo = (cut - 9.0).max((prev + cut) / 2.0);
    let hi = (cut + 9.0).min((cut + next) / 2.0);
    let near: Vec<f64> = bars.iter().copied().filter(|b| *b >= lo && *b <= hi).collect();
    let candidates: Vec<f64> = if near.is_empty() {
        (-60..=60).map(|k| cut + f64::from(k) * 0.1).collect()
    } else {
        near
    };
    let scored: Vec<(f64, f64)> = candidates
        .into_iter()
        .map(|t| (dir * (loud(t, t + 4.0) - loud(t - 4.0, t)), t))
        .collect();
    // A change is heard where it *starts*: the earliest bar reaching 70% of
    // the strongest step, not the bar where the ramp is steepest.
    let best = scored.iter().map(|x| x.0).fold(f64::MIN, f64::max);
    scored
        .iter()
        .filter(|x| x.0 >= 0.7 * best)
        .map(|x| x.1)
        .fold(None, |acc: Option<f64>, t| Some(acc.map_or(t, |a| a.min(t))))
        .unwrap_or(cut)
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
    let mut cuts: Vec<f64> = cuts;
    cuts.sort_by(f64::total_cmp);
    let rough = cuts.clone();
    let bars = bar_lines(s);
    let mut cuts: Vec<f64> = (0..rough.len())
        .map(|i| {
            let prev = if i == 0 { 0.0 } else { rough[i - 1] };
            let next = rough.get(i + 1).copied().unwrap_or(s.duration);
            refine_cut(&features, &bars, prev, rough[i], next)
        })
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
            let span = w[1].time - w[0].time;
            let x = ((t - w[0].time) / span).clamp(0., 1.);
            return hermite(&w[0], &w[1], span, x).0;
        }
    }
    k.last().unwrap().joints
}
/// Quintic Hermite (position, velocity, zero acceleration at both ends):
/// returns position, velocity, acceleration at normalized `x`.
/// With no velocities this is exactly the classic 10-15-6 smoothstep.
fn hermite(a: &Knot, b: &Knot, span: f64, x: f64) -> ([f64; 3], [f64; 3], [f64; 3]) {
    let (x2, x3, x4, x5) = (x * x, x * x * x, x.powi(4), x.powi(5));
    let h0 = 1.0 - 10.0 * x3 + 15.0 * x4 - 6.0 * x5;
    let h0d = -30.0 * x2 + 60.0 * x3 - 30.0 * x4;
    let h0dd = -60.0 * x + 180.0 * x2 - 120.0 * x3;
    let h1 = x - 6.0 * x3 + 8.0 * x4 - 3.0 * x5;
    let h1d = 1.0 - 18.0 * x2 + 32.0 * x3 - 15.0 * x4;
    let h1dd = -36.0 * x + 96.0 * x2 - 60.0 * x3;
    let h4 = -4.0 * x3 + 7.0 * x4 - 3.0 * x5;
    let h4d = -12.0 * x2 + 28.0 * x3 - 15.0 * x4;
    let h4dd = -24.0 * x + 84.0 * x2 - 60.0 * x3;
    let va = a.velocity.unwrap_or([0.0; 3]);
    let vb = b.velocity.unwrap_or([0.0; 3]);
    let mut out = ([0.0; 3], [0.0; 3], [0.0; 3]);
    for j in 0..3 {
        let (p0, p1) = (a.joints[j], b.joints[j]);
        out.0[j] = p0 * h0 + p1 * (1.0 - h0) + span * (va[j] * h1 + vb[j] * h4);
        out.1[j] = (p0 - p1) * h0d / span + va[j] * h1d + vb[j] * h4d;
        out.2[j] = (p0 - p1) * h0dd / (span * span) + (va[j] * h1dd + vb[j] * h4dd) / span;
    }
    out
}

/// Give knots velocity where motion continues through them (monotone,
/// harmonic-mean tangents; zero at reversals and holds), then shrink any
/// velocity whose adjacent segments would break speed/acceleration limits.
fn add_flow(cues: &mut [Cue], limits: &JointLimits, flow: f64) {
    // Flatten; a cue's first knot duplicates the previous cue's last one.
    let mut refs: Vec<(usize, usize)> = Vec::new();
    for (c, cue) in cues.iter().enumerate() {
        for k in 0..cue.knots.len() {
            if c > 0 && k == 0 {
                continue;
            }
            refs.push((c, k));
        }
    }
    let knot = |cues: &[Cue], r: (usize, usize)| cues[r.0].knots[r.1].clone();
    let mut vel = vec![[0.0; 3]; refs.len()];
    for i in 1..refs.len().saturating_sub(1) {
        let (a, b, c) = (knot(cues, refs[i - 1]), knot(cues, refs[i]), knot(cues, refs[i + 1]));
        if b.phase == "hold" || b.phase == "hit" {
            continue;
        }
        vel[i] = std::array::from_fn(|j| {
            let d1 = (b.joints[j] - a.joints[j]) / (b.time - a.time);
            let d2 = (c.joints[j] - b.joints[j]) / (c.time - b.time);
            if d1 * d2 > 0.0 {
                flow * 2.0 / (1.0 / d1 + 1.0 / d2)
            } else {
                0.0
            }
        });
    }
    let ok = |a: &Knot, b: &Knot| {
        let span = b.time - a.time;
        (0..=24).all(|k| {
            let (_, v, acc) = hermite(a, b, span, f64::from(k) / 24.0);
            (0..3).all(|j| {
                v[j].abs() <= limits.max_speed_degrees_per_second[j]
                    && acc[j].abs() <= limits.max_acceleration_degrees_per_second2[j]
            })
        })
    };
    for _ in 0..12 {
        for (i, r) in refs.iter().enumerate() {
            cues[r.0].knots[r.1].velocity = (vel[i] != [0.0; 3]).then_some(vel[i]);
        }
        let mut changed = false;
        for i in 1..refs.len() {
            if !ok(&knot(cues, refs[i - 1]), &knot(cues, refs[i])) {
                for k in [i - 1, i] {
                    vel[k] = vel[k].map(|v| v * 0.7);
                }
                changed = true;
            }
        }
        if !changed {
            break;
        }
    }
    // Anything still over the limit falls back to full stops (known safe).
    for i in 1..refs.len() {
        if !ok(&knot(cues, refs[i - 1]), &knot(cues, refs[i])) {
            vel[i - 1] = [0.0; 3];
            vel[i] = [0.0; 3];
        }
    }
    for (i, r) in refs.iter().enumerate() {
        cues[r.0].knots[r.1].velocity = (vel[i] != [0.0; 3]).then_some(vel[i]);
    }
    // Keep the duplicated cue-boundary knots identical.
    for c in 1..cues.len() {
        let last = cues[c - 1].knots.last().unwrap().velocity;
        cues[c].knots[0].velocity = last;
    }
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
    fn phrase_moves_land_exactly_on_bar_lines() {
        let s = compile_sidecar_json(&fixture(40, 0.8, None, "")).unwrap();
        let moves: Vec<_> = s.cues.iter().filter(|c| c.arrival_anchor.is_some()).collect();
        assert!(moves.len() >= 3, "{}", moves.len());
        for c in moves {
            let t = c.arrival_anchor.unwrap();
            assert!(c.knots.iter().any(|k| k.phase == "arrival" && k.time == t));
            assert!((t / 0.5 - (t / 0.5).round()).abs() < 1e-9, "arrival {t} off beat grid");
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
