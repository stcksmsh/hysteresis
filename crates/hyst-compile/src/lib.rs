//! Deterministic single-arm offline cue compiler.

use hyst_core::sidecar::{Sidecar, SidecarOnset, SidecarSectionKind};
use serde::{Deserialize, Serialize};

pub mod director;
pub mod ensemble;
mod memory;

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
    pub knots: Vec<Knot>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Score {
    pub duration: f64,
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
    /// Recall an earlier measured phrase signature; false uses current content.
    pub reuse_repeats: bool,
}
impl Default for CompileConfig {
    fn default() -> Self {
        Self {
            enable_hits: true,
            enable_windups: true,
            reuse_repeats: true,
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
            let values = value.as_array().ok_or("rmsEnvelope must be an array")?;
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
    if let Some(value) = root.get("musicalMemory") {
        let memory = serde_json::from_value(value.clone())
            .map_err(|error| format!("musicalMemory: {error}"))?;
        return memory::compile(&sidecar, rms.as_deref(), memory, config);
    }
    Ok(compile(&sidecar, rms.as_deref(), config))
}

fn compile(s: &Sidecar, rms: Option<&[f32]>, config: CompileConfig) -> Score {
    let limits = JointLimits::default();
    let onset_scale = percentile(
        &s.onsets.iter().map(|o| o.strength).collect::<Vec<_>>(),
        0.82,
    )
    .max(0.05);
    let bounds = boundaries(s, rms);
    let sections = declared_sections(s);
    let mut cues = Vec::new();
    let mut pose = HOME;
    let mut previous_step = [0.0; 3];
    for w in bounds.windows(2) {
        let (start, end) = (w[0], w[1]);
        let energy = avg(&s.energy_envelope, s.envelope_rate, start, end);
        let absolute = rms.map_or(energy, |v| avg(v, s.envelope_rate, start, end));
        let onset = strongest(&s.onsets, start, end);
        let accent = onset.map_or(0.0, |o| (o.strength / onset_scale).clamp(0.0, 1.0));
        let low = avg(&s.band_envelope.low, s.envelope_rate, start, end)
            + avg(&s.band_envelope.sub, s.envelope_rate, start, end);
        let high = avg(&s.band_envelope.presence, s.envelope_rate, start, end)
            + avg(&s.band_envelope.air, s.envelope_rate, start, end);
        let centroid = avg(&s.centroid_envelope, s.envelope_rate, start, end);
        let level = rms.map_or(energy, |_| (absolute / 0.3).clamp(0.0, 1.0));
        let context = phrase_context(s, rms, &sections, start, end);
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
        let (gesture, reason, arrival_anchor) = if rest {
            ("hold", format!("rest: absolute level {absolute:0.4}"), None)
        } else if let Some(anchor) = hit_candidate.then_some(hit_anchor).flatten() {
            if anchor.tone < 0.46 {
                (
                    "strike-low",
                    format!(
                        "{}; low accent {accent:0.2} at {:0.3}s",
                        context.describe(),
                        anchor.t
                    ),
                    Some(anchor.t),
                )
            } else {
                (
                    "flick-high",
                    format!(
                        "{}; bright accent {accent:0.2} at {:0.3}s",
                        context.describe(),
                        anchor.t
                    ),
                    Some(anchor.t),
                )
            }
        } else if let Some(anchor) = coil_candidate.then_some(coil_anchor).flatten() {
            (
                "coil",
                format!(
                    "{}; energy rise prepares arrival at {:0.3}s",
                    context.describe(),
                    anchor.t
                ),
                Some(anchor.t),
            )
        } else {
            // Gesture variation derives from local content relative to phrase
            // baseline. It has no dependence on cue count or earlier cue order.
            let g = context.gesture_for(level, low, high, centroid);
            let no_anchor = hit_candidate || coil_candidate;
            let phrase = context.describe();
            let reason = if no_anchor {
                format!("{phrase}; groove: no onset allows preparation and recovery; energy {energy:0.2}")
            } else {
                format!("{phrase}; groove: energy {energy:0.2}, low/high {low:0.2}/{high:0.2}, centroid {centroid:0.2}")
            };
            (g, reason, None)
        };
        let knots = make_knots(
            start,
            end,
            pose,
            gesture,
            f64::from(level),
            arrival_anchor,
            &limits,
            context.posture,
            f64::from(onset.map_or(0.0, |event| event.pan)),
            f64::from(low - high),
            f64::from(centroid),
            previous_step,
            context.section.is_some_and(|section| {
                sections.iter().any(|candidate| {
                    candidate.kind == section && (candidate.start - start).abs() < 1e-9
                })
            }),
        );
        if knots.len() >= 2 {
            previous_step = sub(knots.last().unwrap().joints, knots[0].joints);
        }
        pose = knots.last().map_or(pose, |k| k.joints);
        cues.push(Cue {
            start,
            end,
            gesture: gesture.into(),
            reason,
            energy: if rest { 0.0 } else { level },
            accent: if rest { 0.0 } else { accent },
            arrival_anchor,
            knots,
        });
    }
    Score {
        duration: s.duration,
        cues,
        limits,
    }
}

#[derive(Debug, Clone, Copy)]
struct DeclaredSection {
    start: f64,
    end: f64,
    kind: SidecarSectionKind,
}

/// Conservative use of producer-provided structure. Labels are deliberately
/// ignored: partial analyses must not be promoted into verse/chorus claims.
fn declared_sections(s: &Sidecar) -> Vec<DeclaredSection> {
    let mut out = s
        .sections
        .iter()
        .filter_map(|section| {
            (section.start.is_finite()
                && section.end.is_finite()
                && section.start >= 0.0
                && section.end <= s.duration
                && section.end - section.start >= 0.75)
                .then_some(DeclaredSection {
                    start: section.start,
                    end: section.end,
                    kind: section.kind,
                })
        })
        .collect::<Vec<_>>();
    out.sort_by(|a, b| {
        a.start
            .total_cmp(&b.start)
            .then_with(|| a.end.total_cmp(&b.end))
    });
    // Sidecar sections are expected to partition time. Keep deterministic
    // non-overlapping evidence only; a malformed overlap cannot safely define
    // mixed phrase context.
    let mut non_overlapping = Vec::with_capacity(out.len());
    let mut last_end = 0.0;
    for section in out {
        if section.start >= last_end {
            last_end = section.end;
            non_overlapping.push(section);
        }
    }
    non_overlapping
}

#[derive(Debug, Clone, Copy)]
enum Motif {
    Grounded,
    Airy,
    Balanced,
}

#[derive(Debug, Clone, Copy)]
struct PhraseContext {
    motif: Motif,
    level: f32,
    low_high: f32,
    centroid: f32,
    section: Option<SidecarSectionKind>,
    posture: [f64; 3],
}

impl PhraseContext {
    fn gesture_for(self, level: f32, low: f32, high: f32, centroid: f32) -> &'static str {
        let level_delta = level - self.level;
        let timbre_delta = (low - high) - self.low_high;
        let brightness_delta = centroid - self.centroid;
        match self.motif {
            Motif::Grounded if level >= 0.72 => "reach",
            Motif::Grounded if level <= 0.32 => "nod",
            Motif::Grounded if level_delta > 0.07 => "reach",
            Motif::Grounded if timbre_delta < -0.12 || brightness_delta > 0.06 => "sway",
            Motif::Grounded => "sway",
            Motif::Airy if level >= 0.68 => "orbit",
            Motif::Airy if level_delta < -0.07 => "flick",
            Motif::Airy if timbre_delta > 0.12 || brightness_delta < -0.06 => "reach",
            Motif::Airy => "flick",
            Motif::Balanced if level <= 0.30 => "nod",
            Motif::Balanced if level >= 0.70 => "reach",
            Motif::Balanced if level_delta.abs() > 0.07 || brightness_delta.abs() > 0.06 => "reach",
            Motif::Balanced => "sway",
        }
    }

    fn describe(self) -> String {
        let motif = match self.motif {
            Motif::Grounded => "grounded motif",
            Motif::Airy => "airy motif",
            Motif::Balanced => "balanced motif",
        };
        match self.section {
            Some(SidecarSectionKind::Build) => format!("declared build transition, {motif}"),
            Some(SidecarSectionKind::Drop) => format!("declared drop transition, {motif}"),
            Some(SidecarSectionKind::Break) => format!("declared break transition, {motif}"),
            Some(SidecarSectionKind::Other) => format!("declared section transition, {motif}"),
            None => format!("content phrase, {motif}"),
        }
    }
}

fn phrase_context(
    s: &Sidecar,
    rms: Option<&[f32]>,
    sections: &[DeclaredSection],
    start: f64,
    end: f64,
) -> PhraseContext {
    let section = sections
        .iter()
        .copied()
        .find(|section| start >= section.start && end <= section.end);
    let prior_edge = sections
        .iter()
        .filter(|candidate| candidate.end <= start)
        .map(|candidate| candidate.end)
        .max_by(f64::total_cmp)
        .unwrap_or(0.0);
    let next_edge = sections
        .iter()
        .filter(|candidate| candidate.start >= end)
        .map(|candidate| candidate.start)
        .min_by(f64::total_cmp)
        .unwrap_or(s.duration);
    // Older sidecars commonly have sparse or partial section coverage. In an
    // unlabeled span, use a bounded temporal phrase window; this is a content
    // baseline, not a claim about verse/chorus structure.
    let (phrase_start, phrase_end) = section.map_or(
        ((start - 4.0).max(prior_edge), (end + 4.0).min(next_edge)),
        |v| (v.start, v.end),
    );
    let spectral_energy = avg(
        &s.energy_envelope,
        s.envelope_rate,
        phrase_start,
        phrase_end,
    );
    let low = avg(
        &s.band_envelope.low,
        s.envelope_rate,
        phrase_start,
        phrase_end,
    ) + avg(
        &s.band_envelope.sub,
        s.envelope_rate,
        phrase_start,
        phrase_end,
    );
    let high = avg(
        &s.band_envelope.presence,
        s.envelope_rate,
        phrase_start,
        phrase_end,
    ) + avg(
        &s.band_envelope.air,
        s.envelope_rate,
        phrase_start,
        phrase_end,
    );
    let centroid = avg(
        &s.centroid_envelope,
        s.envelope_rate,
        phrase_start,
        phrase_end,
    );
    let level = rms.map_or(spectral_energy, |values| {
        (avg(values, s.envelope_rate, phrase_start, phrase_end) / 0.3).clamp(0.0, 1.0)
    });
    let motif = if low > high * 1.12 {
        Motif::Grounded
    } else if high > low * 1.12 || centroid > 0.58 {
        Motif::Airy
    } else {
        Motif::Balanced
    };
    // Sustained absolute level changes silhouette: quiet music folds, loud
    // music extends. Timbre adjusts wrist/height continuously. Declared
    // sections add a small offset instead of replacing content posture.
    let balance = f64::from((low - high).clamp(-1.0, 1.0));
    let mut posture = [
        101.0 + 17.0 * f64::from(level),
        -78.0 + 43.0 * f64::from(level),
        -17.0 - 9.0 * balance + 18.0 * f64::from(centroid.clamp(0.0, 1.0)),
    ];
    let section_offset = match section.map(|v| v.kind) {
        Some(SidecarSectionKind::Build) => [6.0, 5.0, 4.0],
        Some(SidecarSectionKind::Drop) => [-7.0, -7.0, -8.0],
        Some(SidecarSectionKind::Break) => [3.0, -8.0, 3.0],
        _ => [0.0; 3],
    };
    posture = add(posture, section_offset);
    PhraseContext {
        motif,
        level,
        low_high: low - high,
        centroid,
        section: section.map(|v| v.kind),
        posture,
    }
}

fn boundaries(s: &Sidecar, rms: Option<&[f32]>) -> Vec<f64> {
    let source = rms.unwrap_or(&s.energy_envelope);
    let rate = f64::from(s.envelope_rate);
    let mut candidates = vec![(0.0, true), (s.duration, true)];
    // Declared boundaries are stronger evidence than envelope fluctuation, but
    // only use complete, in-range spans. A partial sidecar must not invent a
    // whole-song section map.
    for section in declared_sections(s) {
        candidates.extend([(section.start, true), (section.end, true)]);
    }
    let mut last = 0.0;
    let mut was_rest =
        source.first().copied().unwrap_or(0.0) < if rms.is_some() { 0.005 } else { 0.05 };
    for i in 1..source.len() {
        let t = i as f64 / rate;
        if t >= s.duration {
            break;
        }
        let back = i.saturating_sub((rate * 0.8) as usize);
        let delta = (source[i] - source[back]).abs();
        let rest = source[i] < if rms.is_some() { 0.005 } else { 0.05 };
        let threshold = if rms.is_some() { 0.012 } else { 0.17 };
        if t - last >= 0.75 && (delta > threshold || rest != was_rest) {
            // Rest transitions and declared sections are hard phrase edges.
            // Level fluctuations only cut after enough time for a broad sweep.
            candidates.push((t, rest != was_rest));
            last = t;
        }
        was_rest = rest;
    }
    // Do not cut a cue exactly at each accent. That made every strong onset a
    // boundary, leaving no recovery time and forcing midpoint "arrivals".
    // Onsets remain planner inputs below; boundaries come from sustained content.
    candidates.retain(|(t, _)| t.is_finite() && *t >= 0.0 && *t <= s.duration);
    candidates.sort_by(|a, b| a.0.total_cmp(&b.0).then_with(|| b.1.cmp(&a.1)));
    let mut deduped: Vec<(f64, bool)> = Vec::new();
    for candidate in candidates {
        if let Some(last) = deduped.last_mut() {
            if (last.0 - candidate.0).abs() < 0.04 {
                if candidate.1 && !last.1 {
                    *last = candidate;
                    continue;
                }
                // Two declared edges may legitimately be close to each other
                // (including near song start/end). Preserve both exact times.
                if candidate.1 && last.1 && candidate.0.to_bits() != last.0.to_bits() {
                    deduped.push(candidate);
                    continue;
                }
                continue;
            }
        }
        deduped.push(candidate);
    }
    let mut out = vec![0.0];
    for (target, declared) in deduped.into_iter().skip(1) {
        let prev = *out.last().unwrap();
        if target < s.duration && target - prev < 3.6 && !declared {
            continue;
        }
        let mut cursor = prev;
        while target - cursor > 6.8 {
            let wanted =
                cursor + 4.2 + 1.4 * (1.0 - f64::from(envelope(s, cursor + 3.0)).clamp(0.0, 1.0));
            let snapped = nearest_beat(&s.beats, wanted).unwrap_or(wanted);
            if snapped >= target - 1.8 {
                break;
            }
            out.push(snapped);
            cursor = snapped;
        }
        out.push(target);
    }
    if *out.last().unwrap() < s.duration {
        out.push(s.duration);
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

#[allow(clippy::too_many_arguments)] // Explicit planning inputs keep score generation deterministic.
fn make_knots(
    start: f64,
    end: f64,
    from: [f64; 3],
    gesture: &str,
    energy: f64,
    arrival_anchor: Option<f64>,
    limits: &JointLimits,
    recovery_pose: [f64; 3],
    pan: f64,
    low_high: f64,
    centroid: f64,
    previous_step: [f64; 3],
    section_transition: bool,
) -> Vec<Knot> {
    if gesture == "hold" {
        return vec![
            Knot {
                time: start,
                phase: "hold".into(),
                joints: from,
                velocity: [0.0; 3],
                acceleration: [0.0; 3],
            },
            Knot {
                time: end,
                phase: "hold".into(),
                joints: from,
                velocity: [0.0; 3],
                acceleration: [0.0; 3],
            },
        ];
    }
    let span = end - start;
    let sign = movement_sign(from, previous_step, pan, low_high, limits);
    let level = energy.clamp(0.0, 1.0);
    let deltas = shape(gesture, 0.18 + level * 1.02, sign, centroid);
    let pull = if section_transition { 0.90 } else { 0.72 };
    let target = |index: usize, momentum: f64, terminal: bool| {
        let base = if terminal {
            lerp(from, recovery_pose, pull)
        } else {
            from
        };
        add(
            add(base, deltas[index]),
            previous_step.map(|value| value * momentum * level),
        )
    };
    let plan: Vec<(f64, &str, [f64; 3])> = if let Some(arrival) = arrival_anchor {
        vec![
            (start, "start", from),
            (
                start + (arrival - start) * 0.42,
                "preparation",
                target(0, 0.12, false),
            ),
            (arrival, "arrival", target(1, 0.22, false)),
            (
                arrival + (end - arrival) * 0.48,
                "followThrough",
                target(2, 0.34, false),
            ),
            (end, "recovery", target(3, 0.48, true)),
        ]
    } else {
        // Groove cues use three long quintic legs. Fewer forced zero-velocity
        // knots make a connected sweep instead of five tiny stop-start hops.
        vec![
            (start, "start", from),
            (start + span * 0.30, "preparation", target(0, 0.16, false)),
            (start + span * 0.69, "followThrough", target(1, 0.32, false)),
            (end, "recovery", target(3, 0.52, true)),
        ]
    };
    let mut knots = Vec::with_capacity(plan.len());
    for (time, phase, wanted) in plan {
        let prior = knots.last().map_or(from, |k: &Knot| k.joints);
        let prior_time = knots.last().map_or(start, |k| k.time);
        knots.push(Knot {
            time,
            phase: phase.into(),
            joints: if knots.is_empty() {
                from
            } else {
                constrain(prior, wanted, time - prior_time, limits)
            },
            velocity: [0.0; 3],
            acceleration: [0.0; 3],
        });
    }
    knots
}

fn movement_sign(
    from: [f64; 3],
    previous_step: [f64; 3],
    pan: f64,
    low_high: f64,
    limits: &JointLimits,
) -> f64 {
    let mut sign = if pan.abs() >= 0.18 {
        pan.signum()
    } else if previous_step[0].abs() >= 1.0 {
        previous_step[0].signum()
    } else if low_high >= 0.0 {
        -1.0
    } else {
        1.0
    };
    let margin = if sign > 0.0 {
        limits.max_degrees[0] - from[0]
    } else {
        from[0] - limits.min_degrees[0]
    };
    if margin < 18.0 {
        sign = -sign;
    }
    sign
}

fn shape(g: &str, a: f64, s: f64, centroid: f64) -> [[f64; 3]; 4] {
    let brightness = centroid.clamp(0.0, 1.0);
    let z = |v: [f64; 3]| {
        [
            v[0] * a * (0.85 + 0.25 * brightness),
            v[1] * a,
            v[2] * a * (0.70 + 0.65 * brightness),
        ]
    };
    match g {
        "strike-low" => [
            z([-8. * s, -8., -5.]),
            z([24. * s, 18., -34.]),
            z([9. * s, 7., -16.]),
            z([12. * s, 2., -8.]),
        ],
        "flick-high" | "flick" => [
            z([-10. * s, 2., 8.]),
            z([25. * s, -13., 24.]),
            z([13. * s, 5., 11.]),
            z([10. * s, -2., 8.]),
        ],
        "coil" => [
            z([-20. * s, -12., 18.]),
            z([10. * s, 14., -18.]),
            z([18. * s, 6., -7.]),
            z([12. * s, 4., -6.]),
        ],
        "orbit" => [
            z([-17. * s, 12., 5.]),
            z([18. * s, 18., -4.]),
            z([22. * s, -9., 8.]),
            z([14. * s, 6., 4.]),
        ],
        "nod" => [
            z([-14. * s, -18., 18.]),
            z([18. * s, 25., -30.]),
            z([25. * s, 8., -16.]),
            z([16. * s, -8., 10.]),
        ],
        "reach" => [
            z([-8. * s, -5., 4.]),
            z([20. * s, 20., -20.]),
            z([16. * s, 10., -13.]),
            z([12. * s, 8., -8.]),
        ],
        _ => [
            z([-15. * s, -14., 18.]),
            z([19. * s, 18., -24.]),
            z([10. * s, -9., 16.]),
            z([10. * s, -5., 10.]),
        ],
    }
}

fn constrain(from: [f64; 3], wanted: [f64; 3], dt: f64, l: &JointLimits) -> [f64; 3] {
    const PLANNING_MARGIN: [f64; 3] = [5.0, 7.0, 7.0];
    std::array::from_fn(|j| {
        let travel = (l.max_speed_degrees_per_second[j] * dt / Q_V)
            .min(l.max_acceleration_degrees_per_second2[j] * dt * dt / Q_A)
            .max(0.);
        wanted[j].clamp(from[j] - travel, from[j] + travel).clamp(
            l.min_degrees[j] + PLANNING_MARGIN[j],
            l.max_degrees[j] - PLANNING_MARGIN[j],
        )
    })
}
fn add(a: [f64; 3], b: [f64; 3]) -> [f64; 3] {
    [a[0] + b[0], a[1] + b[1], a[2] + b[2]]
}
fn sub(a: [f64; 3], b: [f64; 3]) -> [f64; 3] {
    [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
}
fn lerp(a: [f64; 3], b: [f64; 3], t: f64) -> [f64; 3] {
    std::array::from_fn(|i| a[i] + (b[i] - a[i]) * t)
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
            return sample_segment(&w[0], &w[1], t);
        }
    }
    k.last().unwrap().joints
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
fn anchored_onset(
    v: &[SidecarOnset],
    start: f64,
    end: f64,
    min_strength: f32,
) -> Option<&SidecarOnset> {
    const MIN_PREP: f64 = 0.38;
    const MIN_RECOVERY: f64 = 0.30;
    v.iter()
        .filter(|o| {
            o.t >= start + MIN_PREP
                && o.t <= end - MIN_RECOVERY
                && o.strength.is_finite()
                && o.strength >= min_strength
        })
        .max_by(|a, b| {
            a.strength
                .total_cmp(&b.strength)
                .then_with(|| b.t.total_cmp(&a.t))
        })
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
    fn fixture_channels(
        energy: &[f32],
        rms: &[f32],
        low: &[f32],
        high: &[f32],
        centroid: &[f32],
    ) -> String {
        let join = |values: &[f32]| {
            values
                .iter()
                .map(ToString::to_string)
                .collect::<Vec<_>>()
                .join(",")
        };
        let duration = energy.len();
        let beats = (0..duration * 2)
            .map(|i| (i as f64 * 0.5).to_string())
            .collect::<Vec<_>>()
            .join(",");
        format!(
            r#"{{"schema":3,"duration":{duration}.0,"tempo":120.0,"beats":[{beats}],"sections":[],"events":[],"onsets":[],"energyEnvelope":[{}],"bandEnvelope":{{"sub":[{}],"low":[{}],"mid":[{}],"presence":[{}],"air":[{}]}},"centroidEnvelope":[{}],"flatnessEnvelope":[{}],"envelopeRate":1.0,"rmsEnvelope":[{}]}}"#,
            join(energy),
            join(low),
            join(low),
            join(energy),
            join(high),
            join(high),
            join(centroid),
            join(energy),
            join(rms),
        )
    }

    fn joint_range(score: &Score, joint: usize) -> f64 {
        let values = score
            .cues
            .iter()
            .flat_map(|cue| cue.knots.iter().map(|knot| knot.joints[joint]));
        let (minimum, maximum) = values.fold(
            (f64::INFINITY, f64::NEG_INFINITY),
            |(minimum, maximum), value| (minimum.min(value), maximum.max(value)),
        );
        maximum - minimum
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
                reuse_repeats: true,
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
    fn sustained_music_makes_broad_connected_sweeps() {
        let score = compile_sidecar_json_with_config(
            &fixture_channels(
                &[0.58; 24],
                &[0.18; 24],
                &[0.72; 24],
                &[0.16; 24],
                &[0.27; 24],
            ),
            CompileConfig {
                enable_hits: false,
                enable_windups: false,
                reuse_repeats: true,
            },
        )
        .unwrap();
        assert!(score.cues.len() <= 6, "short stop-start cues returned");
        assert!(joint_range(&score, 0) > 24.0, "shoulder stays in tiny loop");
        assert!(joint_range(&score, 1) > 22.0, "elbow stays in tiny loop");
        assert!(joint_range(&score, 2) > 22.0, "wrist stays in tiny loop");
        assert!(score
            .cues
            .windows(2)
            .all(|pair| pair[0].knots.last().unwrap().joints == pair[1].knots[0].joints));

        let normalized = score
            .cues
            .iter()
            .map(|cue| {
                let start = cue.knots[0].joints;
                let deltas = cue
                    .knots
                    .iter()
                    .flat_map(|knot| sub(knot.joints, start))
                    .collect::<Vec<_>>();
                let scale = deltas.iter().copied().map(f64::abs).fold(0.0, f64::max);
                deltas
                    .into_iter()
                    .map(|value| (value / scale * 1000.0).round() as i64)
                    .collect::<Vec<_>>()
            })
            .collect::<Vec<_>>();
        assert!(
            normalized
                .windows(3)
                .all(|window| { window[0] != window[1] || window[1] != window[2] }),
            "same normalized trajectory repeats across three cues"
        );
    }

    #[test]
    fn same_tempo_energy_timbre_and_rest_produce_distinct_motion() {
        let grounded = compile_sidecar_json(&fixture_channels(
            &[0.45; 16],
            &[0.08; 16],
            &[0.75; 16],
            &[0.10; 16],
            &[0.22; 16],
        ))
        .unwrap();
        let bright = compile_sidecar_json(&fixture_channels(
            &[0.68; 16],
            &[0.26; 16],
            &[0.10; 16],
            &[0.78; 16],
            &[0.78; 16],
        ))
        .unwrap();
        let loud_grounded = compile_sidecar_json(&fixture_channels(
            &[0.45; 16],
            &[0.26; 16],
            &[0.75; 16],
            &[0.10; 16],
            &[0.22; 16],
        ))
        .unwrap();
        let mut rest_rms = [0.18; 16];
        rest_rms[5..11].fill(0.0);
        let resting = compile_sidecar_json(&fixture_channels(
            &[0.55; 16],
            &rest_rms,
            &[0.45; 16],
            &[0.45; 16],
            &[0.45; 16],
        ))
        .unwrap();

        assert!(grounded.cues.iter().all(|cue| cue.gesture == "nod"));
        assert!(loud_grounded.cues.iter().all(|cue| cue.gesture == "reach"));
        assert!(bright.cues.iter().all(|cue| cue.gesture == "orbit"));
        assert_ne!(grounded.cues[0].knots, bright.cues[0].knots);
        let most_extended_elbow = |score: &Score| {
            score
                .cues
                .iter()
                .flat_map(|cue| cue.knots.iter())
                .map(|knot| knot.joints[1])
                .fold(f64::NEG_INFINITY, f64::max)
        };
        assert!(
            most_extended_elbow(&loud_grounded) > most_extended_elbow(&grounded) + 15.0,
            "absolute RMS must change posture, not only scale same path"
        );
        let holds = resting
            .cues
            .iter()
            .filter(|cue| cue.gesture == "hold")
            .collect::<Vec<_>>();
        assert!(!holds.is_empty());
        assert!(holds.iter().all(|cue| cue
            .knots
            .iter()
            .all(|knot| knot.joints == cue.knots[0].joints)));
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
            serde_json::from_value::<Cue>(legacy.into())
                .unwrap()
                .arrival_anchor,
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
        let json = fixture(
            &[0.5; 8],
            r#"{"t":2.0,"strength":1.0,"tone":0.1,"pan":0.0},{"t":2.2,"strength":0.1,"tone":0.1,"pan":0.0}"#,
            None,
        )
        .replace(
            "\"sections\":[]",
            "\"sections\":[{\"start\":0.0,\"end\":2.0,\"kind\":\"break\"}]",
        );
        let s = compile_sidecar_json(&json).unwrap();
        let cue = s
            .cues
            .iter()
            .find(|cue| (cue.start - 2.0).abs() < 0.001)
            .unwrap_or_else(|| panic!("expected 2.0s boundary, got {:?}", s.cues));
        assert!(!["strike-low", "flick-high", "coil"].contains(&cue.gesture.as_str()));
        assert_eq!(cue.arrival_anchor, None);
        assert!(cue
            .reason
            .contains("no onset allows preparation and recovery"));
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
                reuse_repeats: true,
            },
        )
        .unwrap();
        let cue = s.cues.iter().find(|cue| cue.gesture == "coil").unwrap();
        assert_eq!(cue.arrival_anchor, Some(1.4));
        assert_eq!(
            cue.knots
                .iter()
                .find(|k| k.phase == "arrival")
                .unwrap()
                .time,
            1.4
        );
    }
    #[test]
    fn malformed_rms_is_rejected_without_time_compression() {
        let non_number = fixture(&[0.5; 8], "", Some(&[0.1; 8])).replace(
            "\"rmsEnvelope\":[0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1]",
            "\"rmsEnvelope\":[0.1,\"bad\",0.1,0.1,0.1,0.1,0.1,0.1]",
        );
        assert!(compile_sidecar_json(&non_number)
            .unwrap_err()
            .contains("rmsEnvelope[1]"));
        let short = fixture(&[0.5; 8], "", Some(&[0.1; 7]));
        assert!(compile_sidecar_json(&short)
            .unwrap_err()
            .contains("needs at least 8"));
    }

    fn assert_score_kinematics(score: &Score) {
        let dt = 0.001;
        let mut pose = score.sample(0.0);
        let mut velocity = [0.0; 3];
        for i in 1..=(score.duration / dt) as usize {
            let next = score.sample(i as f64 * dt);
            for joint in 0..3 {
                let next_velocity = (next[joint] - pose[joint]) / dt;
                assert!(
                    next_velocity.abs() <= score.limits.max_speed_degrees_per_second[joint] + 0.5
                );
                if i > 2 {
                    assert!(
                        ((next_velocity - velocity[joint]) / dt).abs()
                            <= score.limits.max_acceleration_degrees_per_second2[joint] + 5.0
                    );
                }
                velocity[joint] = next_velocity;
            }
            pose = next;
        }
        for window in score.cues.windows(2) {
            assert_eq!(
                window[0].knots.last().unwrap().joints,
                window[1].knots[0].joints
            );
        }
    }

    #[test]
    fn declared_sections_change_phrase_posture_without_breaking_arrivals_or_limits() {
        let base = fixture(
            &[0.5; 8],
            r#"{"t":2.0,"strength":1.0,"tone":0.2,"pan":0.0},{"t":3.0,"strength":0.1,"tone":0.8,"pan":0.0}"#,
            None,
        );
        let structured = base.replace(
            "\"sections\":[]",
            "\"sections\":[{\"start\":1.1,\"end\":4.2,\"kind\":\"build\"},{\"start\":4.2,\"end\":8.0,\"kind\":\"drop\"}]",
        );
        let plain = compile_sidecar_json(&base).unwrap();
        let scored = compile_sidecar_json(&structured).unwrap();
        assert!(scored.cues.iter().any(|cue| (cue.start - 1.1).abs() < 1e-9));
        assert!(scored.cues.iter().any(|cue| (cue.start - 4.2).abs() < 1e-9));
        assert!(scored
            .cues
            .iter()
            .any(|cue| cue.reason.contains("declared build transition")));
        assert!(scored
            .cues
            .iter()
            .any(|cue| cue.reason.contains("declared drop transition")));
        assert_ne!(plain.cues, scored.cues);
        assert_ne!(plain.sample(3.5), scored.sample(3.5));
        let hit = scored
            .cues
            .iter()
            .find(|cue| cue.arrival_anchor == Some(2.0))
            .expect("strong interior onset remains an exact arrival");
        assert_eq!(
            hit.knots
                .iter()
                .find(|knot| knot.phase == "arrival")
                .unwrap()
                .time,
            2.0
        );
        assert_score_kinematics(&scored);
    }

    #[test]
    fn weak_unrelated_onset_does_not_rewrite_later_phrase_motif() {
        let base = fixture(&[0.25, 0.26, 0.27, 0.28, 0.72, 0.74, 0.76, 0.78], "", None);
        let inserted = base.replace(
            "\"sections\":[]",
            "\"sections\":[{\"start\":0.8,\"end\":1.6,\"kind\":\"break\"}]",
        );
        let config = CompileConfig {
            enable_hits: false,
            enable_windups: false,
            reuse_repeats: true,
        };
        let a = compile_sidecar_json_with_config(&base, config).unwrap();
        let b = compile_sidecar_json_with_config(&inserted, config).unwrap();
        let later_a = a
            .cues
            .iter()
            .filter(|cue| cue.start >= 6.0)
            .collect::<Vec<_>>();
        let later_b = b
            .cues
            .iter()
            .filter(|cue| cue.start >= 6.0)
            .collect::<Vec<_>>();
        assert_eq!(
            later_a.iter().map(|cue| &cue.gesture).collect::<Vec<_>>(),
            later_b.iter().map(|cue| &cue.gesture).collect::<Vec<_>>()
        );
    }

    #[test]
    fn invalid_or_overlapping_declared_sections_do_not_create_mixed_context() {
        let base = fixture(&[0.3; 8], "", None);
        let invalid = base.replace(
            "\"sections\":[]",
            "\"sections\":[{\"start\":-1.0,\"end\":2.0,\"kind\":\"build\"},{\"start\":1.0,\"end\":1.4,\"kind\":\"drop\"},{\"start\":1.0,\"end\":4.0,\"kind\":\"build\"},{\"start\":3.0,\"end\":6.0,\"kind\":\"drop\"},{\"start\":7.0,\"end\":9.0,\"kind\":\"break\"}]",
        );
        let score = compile_sidecar_json(&invalid).unwrap();
        assert!(score.cues.iter().any(|cue| (cue.start - 1.0).abs() < 1e-9));
        assert!(score
            .cues
            .iter()
            .any(|cue| cue.reason.contains("declared build transition")));
        assert!(!score
            .cues
            .iter()
            .any(|cue| cue.reason.contains("declared drop transition")));
        assert!(!score
            .cues
            .iter()
            .any(|cue| cue.reason.contains("declared break transition")));
        assert_score_kinematics(&score);
    }

    #[test]
    fn declared_edges_near_song_limits_remain_exact() {
        let json = fixture(&[0.3; 8], "", None).replace(
            "\"sections\":[]",
            "\"sections\":[{\"start\":0.02,\"end\":0.80,\"kind\":\"break\"},{\"start\":7.20,\"end\":7.98,\"kind\":\"build\"}]",
        );
        let sidecar = Sidecar::from_json_str(&json).unwrap();
        let edges = boundaries(&sidecar, None);
        for expected in [0.0, 0.02, 0.80, 7.20, 7.98, 8.0] {
            assert!(edges.iter().any(|edge| (*edge - expected).abs() < 1e-12));
        }
    }
}
