//! Deterministic single-arm offline cue compiler.

use hyst_core::sidecar::{Sidecar, SidecarOnset};
use serde::{Deserialize, Serialize};

const HOME: [f64; 3] = [105.0, -65.0, -20.0];
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
            min_degrees: [45.0, -100.0, -60.0],
            max_degrees: [140.0, -15.0, 40.0],
            max_speed_degrees_per_second: [55.0, 60.0, 70.0],
            max_acceleration_degrees_per_second2: [150.0, 170.0, 200.0],
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
            return HOME;
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

fn compile(s: &Sidecar, rms: Option<&[f32]>, config: CompileConfig) -> Score {
    let limits = JointLimits::default();
    let onset_scale = percentile(
        &s.onsets.iter().map(|o| o.strength).collect::<Vec<_>>(),
        0.82,
    )
    .max(0.05);
    let sections = plan_sections(s, rms);
    let styles: Vec<SectionStyle> = sections.iter().map(|p| section_style(s, p)).collect();
    let section_at = |t: f64| {
        sections
            .iter()
            .position(|p| t >= p.start && t < p.end)
            .unwrap_or(sections.len() - 1)
    };
    let mut bounds = vec![0.0];
    for p in &sections {
        bounds.extend(boundaries(s, rms, p.start, p.end).into_iter().skip(1));
    }
    let mut cues = Vec::new();
    let mut pose = HOME;
    let mut prior = "home";
    let mut step_in_section = 0usize;
    let mut last_section = usize::MAX;
    for w in bounds.windows(2) {
        let (start, end) = (w[0], w[1]);
        let si = section_at(start);
        if si != last_section {
            step_in_section = 0;
            last_section = si;
        }
        let section = &sections[si];
        let style = &styles[si];
        // Recovery aims at the posture of whichever section owns the cue end,
        // so section changes glide across the final cue instead of jumping.
        let target_si = if end >= section.end && si + 1 < sections.len() {
            si + 1
        } else {
            si
        };
        let target = styles[target_si].base;
        let energy = avg(&s.energy_envelope, s.envelope_rate, start, end);
        let absolute = rms.map_or(energy, |v| avg(v, s.envelope_rate, start, end));
        let onset = strongest(&s.onsets, start, end);
        let accent = onset.map_or(0.0, |o| (o.strength / onset_scale).clamp(0.0, 1.0));
        let low = avg(&s.band_envelope.low, s.envelope_rate, start, end)
            + avg(&s.band_envelope.sub, s.envelope_rate, start, end);
        let high = avg(&s.band_envelope.presence, s.envelope_rate, start, end)
            + avg(&s.band_envelope.air, s.envelope_rate, start, end);
        let local_onsets: Vec<_> = s
            .onsets
            .iter()
            .filter(|o| o.t >= start - 2.0 && o.t < end + 2.0)
            .collect();
        let local_mean =
            local_onsets.iter().map(|o| o.strength).sum::<f32>() / local_onsets.len().max(1) as f32;
        let distinct_accent = onset.is_some_and(|o| o.strength > local_mean * 1.45);
        let rest = if rms.is_some() {
            absolute < 0.005
        } else {
            energy < 0.045 && accent < 0.45
        };
        let rising = envelope(s, end) - envelope(s, start) > 0.11;
        let hit_anchor = anchored_onset(&s.onsets, start, end, onset_scale * 0.95);
        let coil_anchor = anchored_onset(&s.onsets, start, end, onset_scale * 0.88);
        let hit_candidate = config.enable_hits && accent >= 0.95 && distinct_accent;
        let coil_candidate = config.enable_windups && rising;
        let next = (target_si != si).then(|| &sections[target_si]);
        let transition = next.and_then(|n| {
            let (from, to) = (level_rank(&section.level), level_rank(&n.level));
            if to > from {
                Some(("gather", format!(
                    "lead-in: {} → {} section {} (motif {})",
                    section.level, n.level, target_si + 1, motif_label(n)
                )))
            } else if to < from {
                Some(("settle", format!(
                    "lead-out: {} → {} section {} (motif {})",
                    section.level, n.level, target_si + 1, motif_label(n)
                )))
            } else {
                None
            }
        });
        let (gesture, reason, arrival_anchor) = if rest {
            ("hold", format!("rest: absolute level {absolute:0.4}"), None)
        } else if let Some(anchor) = hit_candidate.then_some(hit_anchor).flatten() {
            if anchor.tone < 0.46 {
                ("strike-low", format!("low accent {accent:0.2} at {:0.3}s", anchor.t), Some(anchor.t))
            } else {
                ("flick-high", format!("bright accent {accent:0.2} at {:0.3}s", anchor.t), Some(anchor.t))
            }
        } else if let Some((g, why)) = transition {
            (g, why, None)
        } else if let Some(anchor) = coil_candidate.then_some(coil_anchor).flatten() {
            (
                "coil",
                format!("energy rise prepares arrival at {:0.3}s", anchor.t),
                Some(anchor.t),
            )
        } else {
            // Phrase order comes from the section motif: a recurring section
            // replays the same gesture sequence (mirrored on variation).
            let mut g = style.palette[step_in_section % 3];
            if g == prior {
                g = style.palette[(step_in_section + 1) % 3];
            }
            let no_anchor = hit_candidate || coil_candidate;
            let reason = if no_anchor {
                format!(
                    "groove: no onset allows preparation and recovery; motif {} step {}",
                    motif_label(section),
                    step_in_section + 1
                )
            } else {
                format!(
                    "groove: motif {} step {}, energy {energy:0.2}, low/high {low:0.2}/{high:0.2}",
                    motif_label(section),
                    step_in_section + 1
                )
            };
            (g, reason, None)
        };
        let sign = if step_in_section.is_multiple_of(2) != style.mirror {
            1.0
        } else {
            -1.0
        };
        let knots = make_knots(
            Span { start, end, arrival_anchor },
            pose,
            gesture,
            (0.3 + f64::from(energy).clamp(0.0, 1.0) * 0.7) * style.amp_scale,
            sign,
            target,
            &limits,
        );
        pose = knots.last().map_or(pose, |k| k.joints);
        prior = gesture;
        step_in_section += 1;
        cues.push(Cue {
            start,
            end,
            gesture: gesture.into(),
            reason,
            energy: if rest {
                0.0
            } else {
                rms.map_or(energy, |_| (absolute / 0.3).clamp(0.0, 1.0))
            },
            accent: if rest { 0.0 } else { accent },
            arrival_anchor,
            section: Some(si),
            knots,
        });
    }
    Score {
        duration: s.duration,
        sections,
        cues,
        limits,
    }
}

/// `C` for the first statement, `C2`, `C3`... for recurrences.
fn motif_label(p: &SectionPlan) -> String {
    match p.variation {
        0 => p.motif.clone(),
        v => format!("{}{}", p.motif, v + 1),
    }
}

fn level_rank(level: &str) -> u8 {
    match level {
        "rest" => 0,
        "quiet" => 1,
        "mid" => 2,
        _ => 3,
    }
}

/// Raw section character used for gesture family and reasons.
#[derive(Debug, Clone, Copy)]
struct SectionTraits {
    bright: f32,
    centroid: f32,
    density: f32,
}

struct SectionStyle {
    palette: [&'static str; 3],
    base: [f64; 3],
    amp_scale: f64,
    mirror: bool,
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

fn section_style(s: &Sidecar, p: &SectionPlan) -> SectionStyle {
    let t = section_traits(s, p.start, p.end);
    let low_heavy = t.bright < 0.44;
    let bright = t.bright > 0.56 || t.centroid > 0.58;
    let family = if low_heavy {
        ["nod", "sway", "reach"]
    } else if bright {
        ["orbit", "flick", "reach"]
    } else {
        ["sway", "orbit", "nod"]
    };
    // Motif letter rotates phrase order, so two different motifs with the
    // same timbre family still read as different phrases.
    let rot = p.motif.bytes().next().map_or(0, |b| usize::from(b.wrapping_sub(b'A')) % 3);
    let palette = [family[rot], family[(rot + 1) % 3], family[(rot + 2) % 3]];
    let (offset, amp_scale) = match p.level.as_str() {
        "rest" | "quiet" => ([-4.0, -6.0, -6.0], 0.6),
        "mid" => ([0.0; 3], 0.85),
        _ => ([6.0, 8.0, 6.0], 1.0),
    };
    SectionStyle {
        palette,
        base: add(HOME, offset),
        // Variation: later statements mirror, third+ shrink slightly.
        amp_scale: amp_scale * if p.variation >= 2 { 0.85 } else { 1.0 },
        mirror: p.variation % 2 == 1,
    }
}

fn boundaries(s: &Sidecar, rms: Option<&[f32]>, from: f64, to: f64) -> Vec<f64> {
    let source = rms.unwrap_or(&s.energy_envelope);
    let rate = f64::from(s.envelope_rate);
    let rest_level = if rms.is_some() { 0.005 } else { 0.05 };
    let mut candidates = vec![from, to];
    let mut last = from;
    let first = ((from * rate).floor() as usize).min(source.len().saturating_sub(1));
    let mut was_rest = source.get(first).copied().unwrap_or(0.0) < rest_level;
    for (i, &value) in source.iter().enumerate().skip(first + 1) {
        let t = i as f64 / rate;
        if t >= to {
            break;
        }
        let back = i.saturating_sub((rate * 0.8) as usize);
        let delta = (value - source[back]).abs();
        let rest = value < rest_level;
        let threshold = if rms.is_some() { 0.012 } else { 0.17 };
        if t - last >= 0.75 && (delta > threshold || rest != was_rest) {
            candidates.push(t);
            last = t;
        }
        was_rest = rest;
    }
    // Do not cut a cue exactly at each accent. That made every strong onset a
    // boundary, leaving no recovery time and forcing midpoint "arrivals".
    // Onsets remain planner inputs below; boundaries come from sustained content.
    candidates.retain(|t| t.is_finite() && *t >= from && *t <= to);
    candidates.sort_by(f64::total_cmp);
    candidates.dedup_by(|a, b| (*a - *b).abs() < 0.04);
    let mut out = vec![from];
    for target in candidates.into_iter().skip(1) {
        let prev = *out.last().unwrap();
        if target < to && (target - prev < 1.5 || to - target < 1.5) {
            continue;
        }
        let mut cursor = prev;
        while target - cursor > 2.8 {
            let wanted =
                cursor + 1.55 + 0.75 * (1.0 - f64::from(envelope(s, cursor + 1.4)).clamp(0.0, 1.0));
            let snapped = nearest_beat(&s.beats, wanted).unwrap_or(wanted);
            if snapped >= target - 0.72 {
                break;
            }
            out.push(snapped);
            cursor = snapped;
        }
        out.push(target);
    }
    if *out.last().unwrap() < to {
        out.push(to);
    }
    out
}

fn nearest_beat(beats: &[f64], target: f64) -> Option<f64> {
    beats
        .iter()
        .copied()
        .filter(|b| b.is_finite())
        .min_by(|a, b| (a - target).abs().total_cmp(&(b - target).abs()))
        .filter(|b| (b - target).abs() <= 0.22)
}

#[derive(Clone, Copy)]
struct Span {
    start: f64,
    end: f64,
    arrival_anchor: Option<f64>,
}

fn make_knots(
    span: Span,
    from: [f64; 3],
    gesture: &str,
    amp: f64,
    sign: f64,
    target: [f64; 3],
    limits: &JointLimits,
) -> Vec<Knot> {
    let Span { start, end, arrival_anchor } = span;
    if gesture == "hold" {
        return vec![
            Knot {
                time: start,
                phase: "hold".into(),
                joints: from,
            },
            Knot {
                time: end,
                phase: "hold".into(),
                joints: from,
            },
        ];
    }
    let span = end - start;
    let arrival_t = arrival_anchor
        .filter(|t| *t > start && *t < end)
        .unwrap_or(start + span * 0.56);
    let times = [
        start,
        start + (arrival_t - start) * 0.42,
        arrival_t,
        arrival_t + (end - arrival_t) * 0.48,
        end,
    ];
    let deltas = shape(gesture, amp, sign);
    let mut poses = [from; 5];
    for i in 1..5 {
        // Gesture excursions are relative to the incoming pose; recovery lands
        // on the (possibly next) section posture.
        let base = if i == 4 { target } else { from };
        poses[i] = constrain(
            poses[i - 1],
            add(base, deltas[i - 1]),
            times[i] - times[i - 1],
            limits,
        );
    }
    [
        "start",
        "preparation",
        "arrival",
        "followThrough",
        "recovery",
    ]
    .into_iter()
    .enumerate()
    .map(|(i, p)| Knot {
        time: times[i],
        phase: p.into(),
        joints: poses[i],
    })
    .collect()
}

fn shape(g: &str, a: f64, s: f64) -> [[f64; 3]; 4] {
    let z = |v: [f64; 3]| [v[0] * a, v[1] * a, v[2] * a];
    match g {
        "strike-low" => [
            z([-8. * s, -8., -5.]),
            z([24. * s, 18., -34.]),
            z([9. * s, 7., -16.]),
            [0.; 3],
        ],
        "flick-high" | "flick" => [
            z([-10. * s, 2., 8.]),
            z([25. * s, -13., 24.]),
            z([13. * s, 5., 11.]),
            [0.; 3],
        ],
        // Section lead-in: compress, then open toward the louder section.
        "gather" => [
            z([-10. * s, -12., 14.]),
            z([-6. * s, -16., 18.]),
            z([6. * s, 8., -8.]),
            [0.; 3],
        ],
        // Section lead-out: small, decelerating release into lower posture.
        "settle" => [
            z([4. * s, 3., -4.]),
            z([-3. * s, -5., 5.]),
            z([0., -2., 2.]),
            [0.; 3],
        ],
        "coil" => [
            z([-20. * s, -12., 18.]),
            z([10. * s, 14., -18.]),
            z([18. * s, 6., -7.]),
            z([4. * s, 0., 0.]),
        ],
        "orbit" => [
            z([-17. * s, 12., 5.]),
            z([18. * s, 18., -4.]),
            z([22. * s, -9., 8.]),
            z([5. * s, 0., 0.]),
        ],
        "nod" => [
            z([4. * s, -8., 12.]),
            z([-3. * s, 15., -24.]),
            z([5. * s, 5., -11.]),
            [0.; 3],
        ],
        "reach" => [
            z([-8. * s, -5., 4.]),
            z([20. * s, 20., -20.]),
            z([16. * s, 10., -13.]),
            z([4. * s, 0., 0.]),
        ],
        _ => [
            z([-15. * s, -7., 4.]),
            z([19. * s, 10., -10.]),
            z([10. * s, -4., 7.]),
            z([3. * s, 0., 0.]),
        ],
    }
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
fn add(a: [f64; 3], b: [f64; 3]) -> [f64; 3] {
    [a[0] + b[0], a[1] + b[1], a[2] + b[2]]
}
fn sample_knots(k: &[Knot], t: f64) -> [f64; 3] {
    if k.is_empty() {
        return HOME;
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
fn envelope(s: &Sidecar, t: f64) -> f32 {
    let i = (t.max(0.) * f64::from(s.envelope_rate)).floor() as usize;
    s.energy_envelope
        .get(i)
        .copied()
        .or_else(|| s.energy_envelope.last().copied())
        .unwrap_or(0.)
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
fn strongest(v: &[SidecarOnset], a: f64, b: f64) -> Option<&SidecarOnset> {
    v.iter()
        .filter(|o| o.t >= a && o.t < b)
        .max_by(|x, y| x.strength.total_cmp(&y.strength))
}
/// Select only events with enough room for visible preparation and recovery.
/// Boundaries often coincide with onset timestamps; those cannot truthfully be hit cues.
fn anchored_onset(v: &[SidecarOnset], start: f64, end: f64, min_strength: f32) -> Option<&SidecarOnset> {
    const MIN_PREP: f64 = 0.38;
    const MIN_RECOVERY: f64 = 0.30;
    v.iter()
        .filter(|o| {
            o.t >= start + MIN_PREP
                && o.t <= end - MIN_RECOVERY
                && o.strength.is_finite()
                && o.strength >= min_strength
        })
        .max_by(|a, b| a.strength.total_cmp(&b.strength).then_with(|| b.t.total_cmp(&a.t)))
}

#[cfg(test)]
mod tests {
    use super::*;
    fn fixture(e: &[f32], onsets: &str, rms: Option<&[f32]>) -> String {
        let join = |v: &[f32]| {
            v.iter()
                .map(ToString::to_string)
                .collect::<Vec<_>>()
                .join(",")
        };
        let x = join(e);
        let r = rms
            .map(|v| format!(",\"rmsEnvelope\":[{}]", join(v)))
            .unwrap_or_default();
        format!(
            r#"{{"schema":3,"duration":8.0,"tempo":120.0,"beats":[0,0.5,1,1.5,2,2.5,3,3.5,4,4.5,5,5.5,6,6.5,7,7.5],"sections":[],"events":[],"onsets":[{onsets}],"energyEnvelope":[{x}],"bandEnvelope":{{"sub":[{x}],"low":[{x}],"mid":[{x}],"presence":[{x}],"air":[{x}]}},"centroidEnvelope":[{x}],"flatnessEnvelope":[{x}],"envelopeRate":1.0{r}}}"#
        )
    }
    #[test]
    fn content_changes_score() {
        let a = compile_sidecar_json(&fixture(&[0.3; 8], "", None)).unwrap();
        let b = compile_sidecar_json(&fixture(
            &[0.2, 0.9, 0.2, 0.8, 0.2, 0.7, 0.2, 0.6],
            r#"{"t":2.1,"strength":1.0,"tone":0.1,"pan":0.0}"#,
            None,
        ))
        .unwrap();
        assert_ne!(
            a.cues
                .iter()
                .map(|c| (&c.gesture, c.start.to_bits()))
                .collect::<Vec<_>>(),
            b.cues
                .iter()
                .map(|c| (&c.gesture, c.start.to_bits()))
                .collect::<Vec<_>>()
        )
    }
    #[test]
    fn rms_silence_holds() {
        let s = compile_sidecar_json(&fixture(&[0.7; 8], "", Some(&[0.; 8]))).unwrap();
        assert!(s.cues.iter().all(|c| c.gesture == "hold"))
    }
    #[test]
    fn groove_without_specials() {
        let s = compile_sidecar_json_with_config(
            &fixture(
                &[0.3, 0.5, 0.6, 0.4, 0.3, 0.6, 0.5, 0.4],
                r#"{"t":2.1,"strength":1.0,"tone":0.1,"pan":0.0}"#,
                None,
            ),
            CompileConfig {
                enable_hits: false,
                enable_windups: false,
            },
        )
        .unwrap();
        assert!(s
            .cues
            .iter()
            .all(|c| !["strike-low", "flick-high", "coil"].contains(&c.gesture.as_str())));
        assert!((1..80).any(|i| s.sample(i as f64 / 10.) != HOME))
    }
    #[test]
    fn limits_hold_dense() {
        let s = compile_sidecar_json(&fixture(
            &[0.3, 0.9, 0.6, 0.4, 0.8, 0.5, 0.7, 0.4],
            r#"{"t":2.1,"strength":1.0,"tone":0.1,"pan":0.0}"#,
            None,
        ))
        .unwrap();
        let dt = 0.002;
        let mut p = s.sample(0.);
        let mut v = [0.; 3];
        for i in 1..=(s.duration / dt) as usize {
            let q = s.sample(i as f64 * dt);
            for j in 0..3 {
                let nv = (q[j] - p[j]) / dt;
                assert!(nv.abs() <= s.limits.max_speed_degrees_per_second[j] + 0.4);
                if i > 2 {
                    assert!(
                        ((nv - v[j]) / dt).abs()
                            <= s.limits.max_acceleration_degrees_per_second2[j] + 4.
                    )
                }
                v[j] = nv;
            }
            p = q;
        }
    }
    #[test]
    fn hit_arrival_is_exact_anchor_with_continuous_limited_motion() {
        let s = compile_sidecar_json(&fixture(
            &[0.5; 8],
            r#"{"t":1.4,"strength":1.0,"tone":0.1,"pan":0.0},{"t":1.7,"strength":0.1,"tone":0.1,"pan":0.0}"#,
            None,
        ))
        .unwrap();
        let cue = s
            .cues
            .iter()
            .find(|cue| cue.gesture == "strike-low")
            .expect("interior strong onset schedules a hit");
        assert_eq!(cue.arrival_anchor, Some(1.4));
        let encoded = serde_json::to_value(cue).unwrap();
        assert_eq!(encoded["arrivalAnchor"], 1.4);
        let mut legacy = encoded.as_object().unwrap().clone();
        legacy.remove("arrivalAnchor");
        assert_eq!(
            serde_json::from_value::<Cue>(legacy.into()).unwrap().arrival_anchor,
            None
        );
        let arrival = cue.knots.iter().find(|k| k.phase == "arrival").unwrap();
        assert_eq!(arrival.time, cue.arrival_anchor.unwrap());
        assert_eq!(s.sample(1.4), arrival.joints);
        let dt = 0.001;
        let before = s.sample(1.4 - dt);
        let at = s.sample(1.4);
        let after = s.sample(1.4 + dt);
        for j in 0..3 {
            assert!(((at[j] - before[j]) / dt).abs() <= s.limits.max_speed_degrees_per_second[j]);
            assert!(((after[j] - at[j]) / dt).abs() <= s.limits.max_speed_degrees_per_second[j]);
        }
    }
    #[test]
    fn boundary_accent_falls_back_to_truthful_groove() {
        let s = compile_sidecar_json(&fixture(
            &[0.5; 8],
            r#"{"t":2.0,"strength":1.0,"tone":0.1,"pan":0.0},{"t":2.2,"strength":0.1,"tone":0.1,"pan":0.0}"#,
            None,
        ))
        .unwrap();
        let cue = s
            .cues
            .iter()
            .find(|cue| (cue.start - 2.0).abs() < 0.001)
            .unwrap_or_else(|| panic!("expected 2.0s boundary, got {:?}", s.cues));
        assert!(!["strike-low", "flick-high", "coil"].contains(&cue.gesture.as_str()));
        assert_eq!(cue.arrival_anchor, None);
        assert!(cue.reason.contains("no onset allows preparation and recovery"));
    }
    #[test]
    fn coil_uses_exact_lookahead_anchor() {
        let s = compile_sidecar_json_with_config(
            &fixture(
                &[0.1, 0.2, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9],
                r#"{"t":1.4,"strength":0.9,"tone":0.7,"pan":0.0}"#,
                None,
            ),
            CompileConfig {
                enable_hits: false,
                enable_windups: true,
            },
        )
        .unwrap();
        let cue = s.cues.iter().find(|cue| cue.gesture == "coil").unwrap();
        assert_eq!(cue.arrival_anchor, Some(1.4));
        assert_eq!(
            cue.knots.iter().find(|k| k.phase == "arrival").unwrap().time,
            1.4
        );
    }
    #[test]
    fn malformed_rms_is_rejected_without_time_compression() {
        let non_number = fixture(&[0.5; 8], "", Some(&[0.1; 8]))
            .replace("\"rmsEnvelope\":[0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1]", "\"rmsEnvelope\":[0.1,\"bad\",0.1,0.1,0.1,0.1,0.1,0.1]");
        assert!(compile_sidecar_json(&non_number).unwrap_err().contains("rmsEnvelope[1]"));
        let short = fixture(&[0.5; 8], "", Some(&[0.1; 7]));
        assert!(compile_sidecar_json(&short).unwrap_err().contains("needs at least 8"));
    }
}
