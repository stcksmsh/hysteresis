//! Whole-song musical-memory planner.
//!
//! `rhythm`, `lowRhythm`, and `highRhythm` remain ordered here. Fourier pairs at
//! phrase, four-beat, and two-beat periods shape joint heading, phase, and
//! internal accents on one continuous 16-beat clock. Repeated phrases reuse coefficients
//! while current absolute level still controls scale. This is deterministic
//! musical evidence, not instrument classification.

use crate::{segment_bounds, CompileConfig, Cue, JointLimits, Knot, Score};
use hyst_core::sidecar::Sidecar;
use serde::Deserialize;
use std::f64::consts::TAU;

const HOME: [f64; 3] = [105.0, -65.0, -20.0];
const KNOT_PERIOD: f64 = 0.21;
const REST_THRESHOLD: f32 = 0.005;
const MIN_REST_SECONDS: f64 = 0.7;
const REST_RAMP_SECONDS: f64 = 1.2;
const EVENT_LEAD_SECONDS: f64 = 0.9;
const EVENT_TAIL_SECONDS: f64 = 0.9;
const LIMIT_TOLERANCE: f64 = 1e-7;
const PROFILE_HARMONICS: [usize; 3] = [1, 4, 8];

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub(super) struct Memory {
    version: u8,
    method: String,
    beat_period: f64,
    beat_zero: f64,
    phrases: Vec<Phrase>,
    #[serde(default)]
    events: Vec<MemoryEvent>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
struct Phrase {
    start: f64,
    end: f64,
    level: f32,
    low_ratio: f32,
    brightness: f32,
    rhythm: [f32; 32],
    low_rhythm: [f32; 32],
    high_rhythm: [f32; 32],
    #[serde(default)]
    repeat_of: Option<usize>,
    similarity: f32,
    complete: bool,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
struct MemoryEvent {
    time: f64,
    kind: String,
    source: String,
    strength: f32,
}

#[derive(Debug, Clone, Copy)]
struct Interval {
    start: f64,
    end: f64,
}

#[derive(Debug, Clone)]
struct PlannedEvent {
    event: MemoryEvent,
    window: Interval,
}

#[derive(Debug, Clone, Copy)]
struct Motif {
    // Per joint, per harmonic: sine and cosine weights.
    sin: [[f64; 3]; 3],
    cos: [[f64; 3]; 3],
    posture: [f64; 3],
}

#[derive(Debug, Clone, Copy)]
struct DescriptorCalibration {
    low_center: f64,
    low_span: f64,
    brightness_center: f64,
    brightness_span: f64,
    harmonic_gain: [f64; 3],
}

impl Motif {
    fn blend(self, other: Self, amount: f64) -> Self {
        Self {
            sin: std::array::from_fn(|joint| {
                std::array::from_fn(|harmonic| {
                    mix(
                        self.sin[joint][harmonic],
                        other.sin[joint][harmonic],
                        amount,
                    )
                })
            }),
            cos: std::array::from_fn(|joint| {
                std::array::from_fn(|harmonic| {
                    mix(
                        self.cos[joint][harmonic],
                        other.cos[joint][harmonic],
                        amount,
                    )
                })
            }),
            posture: std::array::from_fn(|joint| {
                mix(self.posture[joint], other.posture[joint], amount)
            }),
        }
    }
}

pub(super) fn compile(
    sidecar: &Sidecar,
    rms: Option<&[f32]>,
    memory: Memory,
    config: CompileConfig,
) -> Result<Score, String> {
    validate(sidecar, rms, &memory)?;
    let limits = JointLimits::default();
    let rests = rest_intervals(sidecar.duration, sidecar.envelope_rate, rms);
    // Keep event windows in both feature modes. Identical knot grids make base
    // groove comparisons meaningful; disabled specials remove only overlay and metadata.
    let events = planned_events(sidecar.duration, &memory.events, &rests);
    let event_overlay = config.enable_hits || config.enable_windups;
    let spans = cue_spans(sidecar.duration, &memory, &rests, &events);
    let calibration = descriptor_calibration(&memory);
    let motifs = memory
        .phrases
        .iter()
        .map(|phrase| motif_from_phrase(phrase, calibration))
        .collect::<Vec<_>>();

    let mut knots = knot_timeline(&spans, &events);
    let knot_times = knots.iter().map(|knot| knot.time).collect::<Vec<_>>();
    for knot in &mut knots {
        let time = knot.time;
        if interval_at(&rests, time).is_some() {
            knot.joints = HOME;
            knot.velocity = [0.0; 3];
            knot.acceleration = [0.0; 3];
            knot.phase = "hold".into();
            continue;
        }
        knot.joints = trajectory(&memory, &motifs, &rests, config.reuse_repeats, time);
        let h = derivative_step(&knot_times, time);
        let before = trajectory(
            &memory,
            &motifs,
            &rests,
            config.reuse_repeats,
            (time - h).max(0.0),
        );
        let after = trajectory(
            &memory,
            &motifs,
            &rests,
            config.reuse_repeats,
            (time + h).min(sidecar.duration),
        );
        if time > 0.0 && time < sidecar.duration {
            knot.velocity = std::array::from_fn(|joint| (after[joint] - before[joint]) / (2.0 * h));
            knot.acceleration = std::array::from_fn(|joint| {
                (after[joint] - 2.0 * knot.joints[joint] + before[joint]) / (h * h)
            });
        } else {
            knot.velocity = [0.0; 3];
            knot.acceleration = [0.0; 3];
        }
    }
    enforce_base_limits(&mut knots, &limits)?;
    if event_overlay {
        apply_event_overlay(&mut knots, &rests, &events, &limits)?;
    }
    mark_phases(
        &mut knots,
        &rests,
        if event_overlay { &events } else { &[] },
    );

    let cues = spans
        .iter()
        .map(|span| make_cue(span, &knots, &memory, &rests, &events, config))
        .collect::<Result<Vec<_>, _>>()?;
    Ok(Score {
        duration: sidecar.duration,
        cues,
        limits,
    })
}

fn validate(sidecar: &Sidecar, rms: Option<&[f32]>, memory: &Memory) -> Result<(), String> {
    if memory.version != 1 {
        return Err("musicalMemory version must be 1".into());
    }
    if memory.method.trim().is_empty() {
        return Err("musicalMemory method must not be empty".into());
    }
    if !memory.beat_period.is_finite() || memory.beat_period <= 0.0 {
        return Err("musicalMemory beatPeriod must be finite and positive".into());
    }
    if !memory.beat_zero.is_finite() {
        return Err("musicalMemory beatZero must be finite".into());
    }
    if memory.phrases.is_empty() {
        return Err("musicalMemory needs phrases".into());
    }
    let mut expected_start = 0.0;
    for (index, phrase) in memory.phrases.iter().enumerate() {
        if !phrase.start.is_finite()
            || !phrase.end.is_finite()
            || phrase.start != expected_start
            || phrase.end <= phrase.start
        {
            return Err(format!(
                "musicalMemory phrase {index} must provide exact contiguous positive coverage"
            ));
        }
        for (name, value) in [
            ("level", phrase.level),
            ("lowRatio", phrase.low_ratio),
            ("brightness", phrase.brightness),
            ("similarity", phrase.similarity),
        ] {
            if !value.is_finite() || !(0.0..=1.0).contains(&value) {
                return Err(format!(
                    "musicalMemory phrase {index} {name} must be finite in 0..1"
                ));
            }
        }
        for (name, profile) in [
            ("rhythm", &phrase.rhythm),
            ("lowRhythm", &phrase.low_rhythm),
            ("highRhythm", &phrase.high_rhythm),
        ] {
            if profile
                .iter()
                .any(|value| !value.is_finite() || !(0.0..=1.0).contains(value))
            {
                return Err(format!(
                    "musicalMemory phrase {index} {name} must contain finite 0..1 values"
                ));
            }
        }
        if phrase.complete {
            let expected = 16.0 * memory.beat_period;
            let tolerance = (expected * 0.002).max(1e-6);
            if (phrase_duration(phrase) - expected).abs() > tolerance {
                return Err(format!(
                    "musicalMemory complete phrase {index} must span 16 beats"
                ));
            }
        }
        if let Some(source) = phrase.repeat_of {
            if source >= index.saturating_sub(1) {
                return Err(format!(
                    "musicalMemory phrase {index} repeatOf must name an earlier nonadjacent phrase"
                ));
            }
            let source_phrase = &memory.phrases[source];
            if !source_phrase.complete
                || !phrase.complete
                || phrase.similarity < 0.85
                || (phrase_duration(source_phrase) - phrase_duration(phrase)).abs() > 1e-6
            {
                return Err(format!(
                    "musicalMemory phrase {index} repeat must be complete, equal-duration, and >= 0.85 similarity"
                ));
            }
        }
        expected_start = phrase.end;
    }
    if expected_start != sidecar.duration {
        return Err("musicalMemory phrases must cover exact track duration".into());
    }
    for (index, event) in memory.events.iter().enumerate() {
        if !event.time.is_finite()
            || event.time < 0.0
            || event.time > sidecar.duration
            || !event.strength.is_finite()
            || !(0.0..=1.0).contains(&event.strength)
            || event.kind.trim().is_empty()
            || event.source.trim().is_empty()
        {
            return Err(format!(
                "musicalMemory event {index} needs finite in-range time/strength and nonempty kind/source"
            ));
        }
    }
    if let Some(samples) = rms {
        let required = (sidecar.duration * f64::from(sidecar.envelope_rate)).ceil() as usize;
        if samples.len() < required
            || samples
                .iter()
                .any(|value| !value.is_finite() || *value < 0.0)
        {
            return Err("rmsEnvelope must cover duration with finite nonnegative values".into());
        }
    }
    Ok(())
}

fn phrase_duration(phrase: &Phrase) -> f64 {
    phrase.end - phrase.start
}

fn descriptor_calibration(memory: &Memory) -> DescriptorCalibration {
    let low = memory
        .phrases
        .iter()
        .map(|phrase| f64::from(phrase.low_ratio))
        .collect::<Vec<_>>();
    let brightness = memory
        .phrases
        .iter()
        .map(|phrase| f64::from(phrase.brightness))
        .collect::<Vec<_>>();
    let (low_center, low_span) = robust_center_span(low, 0.02);
    let (brightness_center, brightness_span) = robust_center_span(brightness, 0.004);
    DescriptorCalibration {
        low_center,
        low_span,
        brightness_center,
        brightness_span,
        harmonic_gain: harmonic_gain(memory),
    }
}

fn harmonic_gain(memory: &Memory) -> [f64; 3] {
    let mut magnitudes: [Vec<f64>; 3] = std::array::from_fn(|_| Vec::new());
    for phrase in &memory.phrases {
        for profile in [&phrase.rhythm, &phrase.low_rhythm, &phrase.high_rhythm] {
            for (index, (sine, cosine)) in harmonics(profile).into_iter().enumerate() {
                magnitudes[index].push(sine.hypot(cosine));
            }
        }
    }
    // Phrase and four-beat bands carry body-scale travel. Two-beat band stays
    // smaller because acceleration rises with frequency squared.
    let target = [2.80, 1.10, 0.14];
    std::array::from_fn(|index| {
        magnitudes[index].sort_by(f64::total_cmp);
        let p90 = percentile(&magnitudes[index], 0.9).max(0.025);
        (target[index] / p90).min(24.0)
    })
}

fn robust_center_span(mut values: Vec<f64>, minimum_span: f64) -> (f64, f64) {
    values.sort_by(f64::total_cmp);
    let center = percentile(&values, 0.5);
    let span = (percentile(&values, 0.9) - percentile(&values, 0.1)).max(minimum_span);
    (center, span)
}

fn percentile(values: &[f64], fraction: f64) -> f64 {
    let position = fraction * (values.len() - 1) as f64;
    let lower = position.floor() as usize;
    let upper = position.ceil() as usize;
    mix(values[lower], values[upper], position - lower as f64)
}

fn calibrated(value: f64, center: f64, span: f64) -> f64 {
    ((value - center) * 2.0 / span).clamp(-1.0, 1.0)
}

fn motif_from_phrase(phrase: &Phrase, calibration: DescriptorCalibration) -> Motif {
    let rhythm = harmonics(&phrase.rhythm);
    let low = harmonics(&phrase.low_rhythm);
    let high = harmonics(&phrase.high_rhythm);
    let low_character = calibrated(
        f64::from(phrase.low_ratio),
        calibration.low_center,
        calibration.low_span,
    );
    let bright_character = calibrated(
        f64::from(phrase.brightness),
        calibration.brightness_center,
        calibration.brightness_span,
    );
    let mut motif = Motif {
        sin: [[0.0; 3]; 3],
        cos: [[0.0; 3]; 3],
        posture: [
            5.0 * low_character,
            -4.0 * bright_character,
            5.0 * bright_character - 2.0 * low_character,
        ],
    };
    for harmonic in 0..3 {
        // Track-relative P90 gain makes tight descriptor ranges perceptible.
        // Lower two-beat target keeps physical acceleration bounded.
        let gain = calibration.harmonic_gain[harmonic];
        motif.sin[0][harmonic] = gain * (0.72 * low[harmonic].0 + 0.28 * rhythm[harmonic].0);
        motif.cos[0][harmonic] = gain * (0.72 * low[harmonic].1 + 0.28 * rhythm[harmonic].1);
        motif.sin[1][harmonic] = gain * (0.62 * rhythm[harmonic].0 - 0.38 * high[harmonic].1);
        motif.cos[1][harmonic] = gain * (0.62 * rhythm[harmonic].1 + 0.38 * high[harmonic].0);
        motif.sin[2][harmonic] = gain * (0.72 * high[harmonic].0 + 0.28 * rhythm[harmonic].1);
        motif.cos[2][harmonic] = gain * (0.72 * high[harmonic].1 - 0.28 * rhythm[harmonic].0);
    }
    // Coherent four-beat carrier remains for sparse profiles. Relative timbre
    // rotates its direction/phase; profile coefficients retain phrase shape.
    motif.sin[0][1] += 0.11 + 0.04 * low_character;
    motif.cos[0][1] += 0.035 * bright_character;
    motif.cos[1][1] += 0.10;
    motif.sin[1][1] -= 0.04 * bright_character;
    motif.sin[2][1] += 0.09 + 0.04 * bright_character;
    motif.cos[2][1] -= 0.035 * low_character;
    motif
}

fn harmonics(profile: &[f32; 32]) -> [(f64, f64); 3] {
    let mean = profile.iter().map(|value| f64::from(*value)).sum::<f64>() / 32.0;
    std::array::from_fn(|harmonic| {
        let frequency = PROFILE_HARMONICS[harmonic] as f64;
        let mut sine = 0.0;
        let mut cosine = 0.0;
        for (index, value) in profile.iter().enumerate() {
            let angle = TAU * frequency * index as f64 / 32.0;
            let centered = f64::from(*value) - mean;
            sine += centered * angle.sin();
            cosine += centered * angle.cos();
        }
        (2.0 * sine / 32.0, 2.0 * cosine / 32.0)
    })
}

fn motif_at(memory: &Memory, motifs: &[Motif], reuse_repeats: bool, time: f64) -> Motif {
    let index = phrase_index(memory, time);
    let motif_index = |phrase_index: usize| {
        if reuse_repeats {
            memory.phrases[phrase_index]
                .repeat_of
                .unwrap_or(phrase_index)
        } else {
            phrase_index
        }
    };
    let phrase = &memory.phrases[index];
    if index > 0 {
        let width = boundary_half_width(memory, index - 1);
        if time < phrase.start + width {
            let amount = smooth5((time - phrase.start + width) / (2.0 * width));
            return motifs[motif_index(index - 1)].blend(motifs[motif_index(index)], amount);
        }
    }
    if index + 1 < memory.phrases.len() {
        let width = boundary_half_width(memory, index);
        if time > phrase.end - width {
            let amount = smooth5((time - (phrase.end - width)) / (2.0 * width));
            return motifs[motif_index(index)].blend(motifs[motif_index(index + 1)], amount);
        }
    }
    motifs[motif_index(index)]
}

fn boundary_half_width(memory: &Memory, left_index: usize) -> f64 {
    let left = phrase_duration(&memory.phrases[left_index]);
    let right = phrase_duration(&memory.phrases[left_index + 1]);
    left.min(right).min(2.0 * memory.beat_period)
}

fn trajectory(
    memory: &Memory,
    motifs: &[Motif],
    rests: &[Interval],
    reuse_repeats: bool,
    time: f64,
) -> [f64; 3] {
    if interval_at(rests, time).is_some() {
        return HOME;
    }
    let motif = motif_at(memory, motifs, reuse_repeats, time);
    let loudness = loudness_at(phrase_level_at(memory, time));
    let duration = memory.phrases.last().map_or(0.0, |phrase| phrase.end);
    let activation =
        rest_activation(rests, time) * track_activation(duration, memory.beat_period, time);
    let theta = TAU * (time - memory.beat_zero) / (16.0 * memory.beat_period);
    let amplitude = [11.0, 10.0, 12.0];
    let mut pose = HOME;
    for joint in 0..3 {
        let mut wave = 0.0;
        for (harmonic, frequency) in PROFILE_HARMONICS.into_iter().enumerate() {
            let angle = theta * frequency as f64;
            wave +=
                motif.sin[joint][harmonic] * angle.sin() + motif.cos[joint][harmonic] * angle.cos();
        }
        pose[joint] += activation
            * (motif.posture[joint] * (0.18 + 0.82 * loudness)
                + amplitude[joint] * (0.14 + 0.86 * loudness) * wave);
    }
    pose
}

fn event_offset(rests: &[Interval], events: &[PlannedEvent], time: f64) -> [f64; 3] {
    let activation = rest_activation(rests, time);
    let mut offset = [0.0; 3];
    for planned in events {
        if time >= planned.window.start && time <= planned.window.end {
            let shape = event_shape(time, planned.event.time);
            let strength = f64::from(planned.event.strength);
            // Sparse event overlay stays inside residual travel budget. Safety
            // scaling below touches this offset only, never base groove.
            let accent = [5.0, 6.0, -7.0];
            for joint in 0..3 {
                offset[joint] += activation * strength * accent[joint] * shape;
            }
        }
    }
    offset
}

fn event_shape(time: f64, arrival: f64) -> f64 {
    let prep = arrival - EVENT_LEAD_SECONDS;
    let coil = arrival - 0.55;
    let follow = arrival + 0.55;
    let end = arrival + EVENT_TAIL_SECONDS;
    if time <= coil {
        -0.42 * smooth5((time - prep) / (coil - prep))
    } else if time <= arrival {
        mix(-0.42, 1.0, smooth5((time - coil) / (arrival - coil)))
    } else if time <= follow {
        mix(1.0, 0.32, smooth5((time - arrival) / (follow - arrival)))
    } else {
        0.32 * (1.0 - smooth5((time - follow) / (end - follow)))
    }
}

fn loudness_at(phrase_level: f64) -> f64 {
    phrase_level.clamp(0.0, 1.0).powf(1.35)
}

fn phrase_level_at(memory: &Memory, time: f64) -> f64 {
    let index = phrase_index(memory, time);
    let phrase = &memory.phrases[index];
    if index > 0 {
        let width = boundary_half_width(memory, index - 1);
        if time < phrase.start + width {
            let amount = smooth5((time - phrase.start + width) / (2.0 * width));
            return mix(
                f64::from(memory.phrases[index - 1].level),
                f64::from(phrase.level),
                amount,
            );
        }
    }
    if index + 1 < memory.phrases.len() {
        let width = boundary_half_width(memory, index);
        if time > phrase.end - width {
            let amount = smooth5((time - (phrase.end - width)) / (2.0 * width));
            return mix(
                f64::from(phrase.level),
                f64::from(memory.phrases[index + 1].level),
                amount,
            );
        }
    }
    f64::from(phrase.level)
}

fn rest_intervals(duration: f64, rate: f32, rms: Option<&[f32]>) -> Vec<Interval> {
    let Some(samples) = rms else {
        return Vec::new();
    };
    let rate = f64::from(rate);
    let mut intervals = Vec::new();
    let mut start = None;
    let sample_count = (duration * rate).ceil() as usize;
    for index in 0..=sample_count {
        let quiet = index < sample_count
            && samples
                .get(index)
                .is_some_and(|value| *value < REST_THRESHOLD);
        if quiet && start.is_none() {
            start = Some(index);
        } else if !quiet {
            if let Some(first) = start.take() {
                let interval = Interval {
                    start: first as f64 / rate,
                    end: (index as f64 / rate).min(duration),
                };
                if interval.end - interval.start >= MIN_REST_SECONDS {
                    intervals.push(interval);
                }
            }
        }
    }
    intervals
}

fn rest_activation(rests: &[Interval], time: f64) -> f64 {
    let mut activation: f64 = 1.0;
    for rest in rests {
        if time >= rest.start && time <= rest.end {
            return 0.0;
        }
        if time < rest.start && time > rest.start - REST_RAMP_SECONDS {
            activation = activation.min(smooth5((rest.start - time) / REST_RAMP_SECONDS));
        }
        if time > rest.end && time < rest.end + REST_RAMP_SECONDS {
            activation = activation.min(smooth5((time - rest.end) / REST_RAMP_SECONDS));
        }
    }
    activation
}

fn track_activation(duration: f64, beat_period: f64, time: f64) -> f64 {
    let ramp = (2.0 * beat_period).min(duration * 0.5);
    if ramp <= 0.0 {
        return 0.0;
    }
    smooth5(time / ramp).min(smooth5((duration - time) / ramp))
}

fn planned_events(duration: f64, events: &[MemoryEvent], rests: &[Interval]) -> Vec<PlannedEvent> {
    let mut candidates = events
        .iter()
        .filter(|event| {
            event.time >= EVENT_LEAD_SECONDS
                && event.time <= duration - EVENT_TAIL_SECONDS
                && !rests.iter().any(|rest| {
                    event.time - EVENT_LEAD_SECONDS < rest.end
                        && event.time + EVENT_TAIL_SECONDS > rest.start
                })
        })
        .cloned()
        .collect::<Vec<_>>();
    candidates.sort_by(|a, b| a.time.total_cmp(&b.time));
    let mut planned: Vec<PlannedEvent> = Vec::new();
    for event in candidates {
        let window = Interval {
            start: event.time - EVENT_LEAD_SECONDS,
            end: event.time + EVENT_TAIL_SECONDS,
        };
        if planned
            .last()
            .is_none_or(|previous| window.start >= previous.window.end)
        {
            planned.push(PlannedEvent { event, window });
        }
    }
    planned
}

fn cue_spans(
    duration: f64,
    memory: &Memory,
    rests: &[Interval],
    events: &[PlannedEvent],
) -> Vec<Interval> {
    let specials = rests
        .iter()
        .copied()
        .chain(events.iter().map(|event| event.window))
        .collect::<Vec<_>>();
    let mut boundaries = vec![0.0, duration];
    for interval in &specials {
        boundaries.extend([interval.start, interval.end]);
    }
    for phrase in &memory.phrases {
        if !specials
            .iter()
            .any(|interval| phrase.end > interval.start && phrase.end < interval.end)
        {
            boundaries.push(phrase.end);
        }
    }
    boundaries.sort_by(f64::total_cmp);
    boundaries.dedup();
    boundaries
        .windows(2)
        .filter(|window| window[1] > window[0])
        .map(|window| Interval {
            start: window[0],
            end: window[1],
        })
        .collect()
}

fn knot_timeline(spans: &[Interval], events: &[PlannedEvent]) -> Vec<Knot> {
    let mut times = Vec::new();
    for span in spans {
        let pieces = ((span.end - span.start) / KNOT_PERIOD).ceil().max(1.0) as usize;
        times.push(span.start);
        for index in 1..pieces {
            times.push(mix(span.start, span.end, index as f64 / pieces as f64));
        }
        times.push(span.end);
    }
    times.extend(events.iter().map(|event| event.event.time));
    times.sort_by(f64::total_cmp);
    times.dedup();
    times
        .into_iter()
        .map(|time| Knot {
            time,
            phase: "groove".into(),
            joints: HOME,
            velocity: [0.0; 3],
            acceleration: [0.0; 3],
        })
        .collect()
}

fn derivative_step(times: &[f64], time: f64) -> f64 {
    let index = times.partition_point(|candidate| *candidate < time);
    let before = index
        .checked_sub(1)
        .and_then(|index| times.get(index))
        .map_or(0.01, |candidate| (time - candidate) * 0.2);
    let after = times
        .get(index + usize::from(index < times.len() && times[index] == time))
        .map_or(0.01, |candidate| (candidate - time) * 0.2);
    before.min(after).clamp(0.001, 0.01)
}

fn mark_phases(knots: &mut [Knot], rests: &[Interval], events: &[PlannedEvent]) {
    for knot in knots {
        if interval_at(rests, knot.time).is_some() {
            knot.phase = "hold".into();
        }
        for event in events {
            if knot.time == event.event.time {
                knot.phase = "arrival".into();
            } else if knot.time >= event.window.start && knot.time < event.event.time {
                knot.phase = "preparation".into();
            } else if knot.time > event.event.time && knot.time <= event.window.end {
                knot.phase = "followThrough".into();
            }
        }
    }
}

fn enforce_base_limits(knots: &mut [Knot], limits: &JointLimits) -> Result<(), String> {
    let mut scale = [1.0_f64; 3];
    for pair in knots.windows(2) {
        let bounds = segment_bounds(&pair[0], &pair[1]).map_err(str::to_owned)?;
        for joint in 0..3 {
            scale[joint] = scale[joint]
                .min(limit_ratio(
                    bounds.max_speed_degrees_per_second[joint],
                    limits.max_speed_degrees_per_second[joint],
                ))
                .min(limit_ratio(
                    bounds.max_acceleration_degrees_per_second2[joint],
                    limits.max_acceleration_degrees_per_second2[joint],
                ));
            let low_offset = HOME[joint] - bounds.min_position_degrees[joint];
            if low_offset > 0.0 {
                scale[joint] =
                    scale[joint].min((HOME[joint] - limits.min_degrees[joint]) / low_offset);
            }
            let high_offset = bounds.max_position_degrees[joint] - HOME[joint];
            if high_offset > 0.0 {
                scale[joint] =
                    scale[joint].min((limits.max_degrees[joint] - HOME[joint]) / high_offset);
            }
        }
    }
    for factor in &mut scale {
        // Reserve acceleration headroom for sparse independently-scaled events.
        *factor = (*factor * 0.90).min(0.90);
        if *factor < 0.25 {
            return Err(format!(
                "musicalMemory base trajectory needs excessive global scale {factor:.3}"
            ));
        }
    }
    for knot in knots {
        for joint in 0..3 {
            knot.joints[joint] = HOME[joint] + (knot.joints[joint] - HOME[joint]) * scale[joint];
            knot.velocity[joint] *= scale[joint];
            knot.acceleration[joint] *= scale[joint];
        }
    }
    Ok(())
}

fn limit_ratio(measured: f64, limit: f64) -> f64 {
    if measured <= limit || measured == 0.0 {
        1.0
    } else {
        limit / measured
    }
}

fn apply_event_overlay(
    base: &mut [Knot],
    rests: &[Interval],
    events: &[PlannedEvent],
    limits: &JointLimits,
) -> Result<(), String> {
    let times = base.iter().map(|knot| knot.time).collect::<Vec<_>>();
    let mut overlay = base
        .iter()
        .map(|knot| {
            let time = knot.time;
            let h = derivative_step(&times, time);
            let joints = event_offset(rests, events, time);
            let edge = events
                .iter()
                .any(|event| time == event.window.start || time == event.window.end);
            let (velocity, acceleration) = if edge || interval_at(rests, time).is_some() {
                ([0.0; 3], [0.0; 3])
            } else {
                let before = event_offset(rests, events, (time - h).max(0.0));
                let after = event_offset(rests, events, time + h);
                (
                    std::array::from_fn(|joint| (after[joint] - before[joint]) / (2.0 * h)),
                    std::array::from_fn(|joint| {
                        (after[joint] - 2.0 * joints[joint] + before[joint]) / (h * h)
                    }),
                )
            };
            Knot {
                time,
                phase: String::new(),
                joints,
                velocity,
                acceleration,
            }
        })
        .collect::<Vec<_>>();

    for _ in 0..160 {
        let mut reductions = vec![[1.0_f64; 3]; base.len()];
        let mut safe = true;
        for index in 0..base.len().saturating_sub(1) {
            let start = combined_knot(&base[index], &overlay[index]);
            let end = combined_knot(&base[index + 1], &overlay[index + 1]);
            let bounds = segment_bounds(&start, &end).map_err(str::to_owned)?;
            for (joint, minimum) in bounds.min_position_degrees.iter().enumerate() {
                let valid = *minimum >= limits.min_degrees[joint] - LIMIT_TOLERANCE
                    && bounds.max_position_degrees[joint]
                        <= limits.max_degrees[joint] + LIMIT_TOLERANCE
                    && bounds.max_speed_degrees_per_second[joint]
                        <= limits.max_speed_degrees_per_second[joint] + LIMIT_TOLERANCE
                    && bounds.max_acceleration_degrees_per_second2[joint]
                        <= limits.max_acceleration_degrees_per_second2[joint] + LIMIT_TOLERANCE;
                if !valid {
                    safe = false;
                    reductions[index][joint] = 0.82;
                    reductions[index + 1][joint] = 0.82;
                }
            }
        }
        if safe {
            for (base, overlay) in base.iter_mut().zip(overlay) {
                for joint in 0..3 {
                    base.joints[joint] += overlay.joints[joint];
                    base.velocity[joint] += overlay.velocity[joint];
                    base.acceleration[joint] += overlay.acceleration[joint];
                }
            }
            return Ok(());
        }
        for (overlay, scale) in overlay.iter_mut().zip(reductions) {
            for (joint, factor) in scale.into_iter().enumerate() {
                overlay.joints[joint] *= factor;
                overlay.velocity[joint] *= factor;
                overlay.acceleration[joint] *= factor;
            }
        }
    }
    Err("musicalMemory event overlay could not satisfy residual joint limits".into())
}

fn combined_knot(base: &Knot, overlay: &Knot) -> Knot {
    Knot {
        time: base.time,
        phase: base.phase.clone(),
        joints: std::array::from_fn(|joint| base.joints[joint] + overlay.joints[joint]),
        velocity: std::array::from_fn(|joint| base.velocity[joint] + overlay.velocity[joint]),
        acceleration: std::array::from_fn(|joint| {
            base.acceleration[joint] + overlay.acceleration[joint]
        }),
    }
}

#[allow(clippy::too_many_arguments)]
fn make_cue(
    span: &Interval,
    knots: &[Knot],
    memory: &Memory,
    rests: &[Interval],
    events: &[PlannedEvent],
    config: CompileConfig,
) -> Result<Cue, String> {
    let cue_knots = knots
        .iter()
        .filter(|knot| knot.time >= span.start && knot.time <= span.end)
        .cloned()
        .collect::<Vec<_>>();
    if cue_knots.len() < 2 {
        return Err("musicalMemory cue needs two knots".into());
    }
    let middle = (span.start + span.end) * 0.5;
    let phrase_index = phrase_index(memory, middle);
    let phrase = &memory.phrases[phrase_index];
    let source_index = if config.reuse_repeats {
        phrase.repeat_of.unwrap_or(phrase_index)
    } else {
        phrase_index
    };
    let rest = interval_at(rests, middle).is_some();
    let event = (config.enable_hits || config.enable_windups)
        .then(|| {
            events
                .iter()
                .find(|event| event.window.start == span.start && event.window.end == span.end)
        })
        .flatten();
    let (gesture, reason, arrival_anchor, accent) = if rest {
        (
            "hold".to_owned(),
            "verified sustained absolute RMS rest".to_owned(),
            None,
            0.0,
        )
    } else if let Some(event) = event {
        (
            "annotated-event".to_owned(),
            format!(
                "annotated {} from {}; phrase motif {} source {} confidence {:.2}",
                event.event.kind, event.event.source, phrase_index, source_index, phrase.similarity
            ),
            Some(event.event.time),
            event.event.strength,
        )
    } else {
        (
            "memory-groove".to_owned(),
            format!(
                "phrase motif {} source {} confidence {:.2}; ordered rhythm/timbre harmonics",
                phrase_index, source_index, phrase.similarity
            ),
            None,
            0.0,
        )
    };
    let energy = if rest {
        0.0
    } else {
        loudness_at(phrase_level_at(memory, middle)) as f32
    };
    Ok(Cue {
        start: span.start,
        end: span.end,
        gesture,
        reason,
        energy,
        accent,
        arrival_anchor,
        knots: cue_knots,
    })
}

fn phrase_index(memory: &Memory, time: f64) -> usize {
    memory
        .phrases
        .partition_point(|phrase| phrase.end <= time)
        .min(memory.phrases.len() - 1)
}

fn interval_at(intervals: &[Interval], time: f64) -> Option<&Interval> {
    intervals
        .iter()
        .find(|interval| time >= interval.start && time <= interval.end)
}

fn smooth5(value: f64) -> f64 {
    let value = value.clamp(0.0, 1.0);
    value * value * value * (10.0 + value * (-15.0 + 6.0 * value))
}

fn mix(start: f64, end: f64, amount: f64) -> f64 {
    start + (end - start) * amount
}

#[cfg(test)]
mod tests {
    use super::*;
    use hyst_core::sidecar::{SidecarBandEnvelope, SidecarSchemaVersion};

    fn profile(phase: usize) -> [f32; 32] {
        std::array::from_fn(|index| {
            let angle = TAU * ((index + phase) % 32) as f64 / 32.0;
            (0.5 + 0.45 * angle.sin()) as f32
        })
    }

    fn phrase(start: f64, end: f64, phase: usize, level: f32) -> Phrase {
        Phrase {
            start,
            end,
            level,
            low_ratio: 0.62,
            brightness: 0.38,
            rhythm: profile(phase),
            low_rhythm: profile(phase + 3),
            high_rhythm: profile(phase + 9),
            repeat_of: None,
            similarity: 0.9,
            complete: true,
        }
    }

    fn memory() -> Memory {
        let mut repeat = phrase(16.0, 24.0, 17, 0.55);
        repeat.repeat_of = Some(0);
        Memory {
            version: 1,
            method: "fixture".into(),
            beat_period: 0.5,
            beat_zero: 0.0,
            phrases: vec![
                phrase(0.0, 8.0, 0, 0.55),
                phrase(8.0, 16.0, 7, 0.55),
                repeat,
            ],
            events: Vec::new(),
        }
    }

    fn sidecar() -> Sidecar {
        let values = vec![0.4; 240];
        Sidecar {
            schema: SidecarSchemaVersion::V3,
            duration: 24.0,
            tempo: 120.0,
            beats: (0..48).map(|index| index as f64 * 0.5).collect(),
            sections: Vec::new(),
            events: Vec::new(),
            onsets: Vec::new(),
            energy_envelope: values.clone(),
            band_envelope: SidecarBandEnvelope {
                sub: values.clone(),
                low: values.clone(),
                mid: values.clone(),
                presence: values.clone(),
                air: values.clone(),
            },
            centroid_envelope: values.clone(),
            flatness_envelope: values,
            envelope_rate: 10.0,
            stem_presence: None,
            repeats: None,
            novelty_local_envelope: None,
            novelty_section_envelope: None,
        }
    }

    fn config(reuse_repeats: bool) -> CompileConfig {
        CompileConfig {
            enable_hits: false,
            enable_windups: false,
            reuse_repeats,
        }
    }

    #[test]
    fn rejects_bad_contracts() {
        let sidecar = sidecar();
        let mut bad = memory();
        bad.version = 2;
        assert!(compile(&sidecar, None, bad, config(true)).is_err());
        let mut bad = memory();
        bad.phrases[1].start += 0.1;
        assert!(compile(&sidecar, None, bad, config(true)).is_err());
        let mut bad = memory();
        bad.phrases[2].similarity = 0.84;
        assert!(compile(&sidecar, None, bad, config(true)).is_err());
        let mut bad = memory();
        bad.phrases[2].repeat_of = Some(usize::MAX);
        assert!(compile(&sidecar, None, bad, config(true)).is_err());
        let mut bad = memory();
        bad.phrases[0].rhythm[3] = f32::NAN;
        assert!(compile(&sidecar, None, bad, config(true)).is_err());
    }

    #[test]
    fn ordered_rhythm_and_repeat_policy_change_motion() {
        let sidecar = sidecar();
        let reused = compile(&sidecar, None, memory(), config(true)).unwrap();
        let varied = compile(&sidecar, None, memory(), config(false)).unwrap();
        let repeated = reused.sample(17.1);
        let source = reused.sample(1.1);
        let variant = varied.sample(17.1);
        assert!(distance(repeated, source) < distance(variant, source));

        let mut other = memory();
        other.phrases[1].rhythm = profile(19);
        let changed = compile(&sidecar, None, other, config(false)).unwrap();
        assert_ne!(varied.sample(10.3), changed.sample(10.3));
        let ranges = joint_ranges(&varied, 8.0, 16.0);
        assert!(
            ranges.iter().filter(|range| **range >= 5.0).count() >= 2,
            "profile-driven complete phrase must use body-scale travel: {ranges:?}"
        );
    }

    #[test]
    fn louder_music_moves_farther_and_active_knots_keep_velocity() {
        let sidecar = sidecar();
        let rms = vec![0.12; 240];
        let mut quiet = memory();
        let mut loud = memory();
        for phrase in &mut quiet.phrases {
            phrase.level = 0.2;
        }
        for phrase in &mut loud.phrases {
            phrase.level = 0.9;
        }
        let quiet_score = compile(&sidecar, Some(&rms), quiet, config(true)).unwrap();
        let loud_score = compile(&sidecar, Some(&rms), loud, config(true)).unwrap();
        assert!(excursion(&loud_score) > excursion(&quiet_score) * 1.2);
        let active = loud_score
            .cues
            .iter()
            .flat_map(|cue| &cue.knots)
            .filter(|knot| knot.time > 1.0 && knot.time < 23.0)
            .collect::<Vec<_>>();
        assert!(
            active
                .iter()
                .filter(|knot| knot.velocity != [0.0; 3])
                .count()
                * 4
                > active.len() * 3
        );
    }

    #[test]
    fn annotated_event_has_lookahead_exact_arrival_and_feature_switch() {
        let sidecar = sidecar();
        let mut memory = memory();
        memory.events.push(MemoryEvent {
            time: 12.0,
            kind: "mix_onset".into(),
            source: "manual-marker".into(),
            strength: 0.9,
        });
        let enabled = compile(
            &sidecar,
            None,
            memory.clone(),
            CompileConfig {
                enable_hits: true,
                enable_windups: true,
                reuse_repeats: true,
            },
        )
        .unwrap();
        let cue = enabled
            .cues
            .iter()
            .find(|cue| cue.arrival_anchor == Some(12.0))
            .unwrap();
        assert!(cue.start <= 11.1 && cue.end >= 12.9);
        assert!(cue
            .knots
            .iter()
            .any(|knot| knot.time == 12.0 && knot.phase == "arrival"));
        assert!(cue.reason.contains("mix_onset from manual-marker"));
        let disabled = compile(&sidecar, None, memory, config(true)).unwrap();
        assert!(disabled.cues.iter().all(|cue| cue.arrival_anchor.is_none()));
        assert_eq!(enabled.sample(10.5), disabled.sample(10.5));
        assert_eq!(enabled.sample(13.5), disabled.sample(13.5));
        assert_ne!(enabled.sample(11.7), disabled.sample(11.7));
    }

    #[test]
    fn sustained_rest_is_home_and_every_segment_has_proven_limits() {
        let sidecar = sidecar();
        let mut rms = vec![0.18; 240];
        rms[80..100].fill(0.0);
        let score = compile(&sidecar, Some(&rms), memory(), config(true)).unwrap();
        let hold = score.cues.iter().find(|cue| cue.gesture == "hold").unwrap();
        assert!(hold.end - hold.start >= 1.9);
        assert!(hold.knots.iter().all(|knot| {
            knot.joints == HOME && knot.velocity == [0.0; 3] && knot.acceleration == [0.0; 3]
        }));
        for cue in &score.cues {
            for pair in cue.knots.windows(2) {
                let bounds = segment_bounds(&pair[0], &pair[1]).unwrap();
                for (joint, minimum) in bounds.min_position_degrees.iter().enumerate() {
                    assert!(*minimum >= score.limits.min_degrees[joint] - LIMIT_TOLERANCE);
                    assert!(
                        bounds.max_position_degrees[joint]
                            <= score.limits.max_degrees[joint] + LIMIT_TOLERANCE
                    );
                    assert!(
                        bounds.max_speed_degrees_per_second[joint]
                            <= score.limits.max_speed_degrees_per_second[joint] + LIMIT_TOLERANCE
                    );
                    assert!(
                        bounds.max_acceleration_degrees_per_second2[joint]
                            <= score.limits.max_acceleration_degrees_per_second2[joint]
                                + LIMIT_TOLERANCE
                    );
                }
            }
        }
        let first_seek = score.sample(14.345);
        let _unrelated_seek = score.sample(2.125);
        assert_eq!(first_seek, score.sample(14.345));
    }

    #[test]
    fn partial_edge_phrases_crossfade_with_finite_derivatives() {
        let mut sidecar = sidecar();
        sidecar.duration = 12.0;
        sidecar.beats.truncate(24);
        let mut first = phrase(0.0, 2.0, 0, 0.35);
        first.complete = false;
        let middle = phrase(2.0, 10.0, 7, 0.65);
        let mut last = phrase(10.0, 12.0, 13, 0.45);
        last.complete = false;
        let memory = Memory {
            version: 1,
            method: "partial-fixture".into(),
            beat_period: 0.5,
            beat_zero: 0.0,
            phrases: vec![first, middle, last],
            events: Vec::new(),
        };
        let score = compile(&sidecar, None, memory, config(true)).unwrap();
        assert!(score.cues.iter().flat_map(|cue| &cue.knots).all(|knot| knot
            .joints
            .iter()
            .chain(&knot.velocity)
            .chain(&knot.acceleration)
            .all(|value| value.is_finite())));
    }

    fn distance(a: [f64; 3], b: [f64; 3]) -> f64 {
        a.into_iter()
            .zip(b)
            .map(|(a, b)| (a - b).powi(2))
            .sum::<f64>()
            .sqrt()
    }

    fn excursion(score: &Score) -> f64 {
        score
            .cues
            .iter()
            .flat_map(|cue| &cue.knots)
            .map(|knot| distance(knot.joints, HOME))
            .fold(0.0, f64::max)
    }

    fn joint_ranges(score: &Score, start: f64, end: f64) -> [f64; 3] {
        let samples = (0..=800)
            .map(|index| score.sample(mix(start, end, index as f64 / 800.0)))
            .collect::<Vec<_>>();
        std::array::from_fn(|joint| {
            let minimum = samples
                .iter()
                .map(|sample| sample[joint])
                .fold(f64::INFINITY, f64::min);
            let maximum = samples
                .iter()
                .map(|sample| sample[joint])
                .fold(f64::NEG_INFINITY, f64::max);
            maximum - minimum
        })
    }
}
