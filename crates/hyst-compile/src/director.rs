//! Offline, rig-independent musical interpretation. All decisions use measured
//! source, structure, and phrase evidence; playback only samples resolved intent.

use crate::CompileConfig;
use serde::{Deserialize, Serialize};

pub mod figures;

const SOURCES: [&str; 4] = ["bass", "drums", "vocals", "other"];

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct Interpretation {
    pub duration: f64,
    pub beat_period: f64,
    pub beat_zero: f64,
    pub cues: Vec<IntentCue>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct IntentCue {
    pub start: f64,
    pub end: f64,
    pub character: String,
    pub formation: String,
    /// Whole-track calibrated source activity: bass, drums, vocals, other.
    pub source_activity: [f64; 4],
    pub confidence: f64,
    /// Earlier audio time mapped onto this cue when related material returns.
    pub recall_from: Option<f64>,
    /// Future measured arrival time; profiles begin preparing before it.
    pub anticipation: Option<f64>,
    pub reason: String,
    /// Uniform inclusive samples over [start,end]. Coordinates: sweep/lift/fold.
    pub profile: Vec<[f64; 3]>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Evidence {
    duration: f64,
    envelope_rate: f64,
    #[serde(default)]
    rms_envelope: Vec<f64>,
    musical_memory: Memory,
    stem_interpretation: Stems,
    musical_structure: Structure,
    /// Optional estimated melodic height per pitched stem (dance_melody.py).
    #[serde(default)]
    melody_contour: Option<Melody>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Melody {
    envelope_rate: f64,
    sources: std::collections::HashMap<String, Contour>,
}

#[derive(Deserialize)]
struct Contour {
    height: Vec<f64>,
    salience: Vec<f64>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Memory {
    version: u8,
    beat_period: f64,
    beat_zero: f64,
    phrases: Vec<Phrase>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Phrase {
    start: f64,
    end: f64,
    rhythm: Vec<f64>,
    low_rhythm: Vec<f64>,
    high_rhythm: Vec<f64>,
    #[serde(default)]
    repeat_of: Option<usize>,
    similarity: f64,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Stems {
    version: u8,
    duration: f64,
    envelope_rate: f64,
    sources: std::collections::HashMap<String, Source>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Source {
    absolute_rms: Vec<f64>,
    whole_track_activity: Vec<f64>,
    spectral_flux: Vec<f64>,
    transient_density: Vec<f64>,
    candidates: Vec<SourceCandidate>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct SourceCandidate {
    kind: String,
    time: f64,
    confidence: f64,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Structure {
    version: u8,
    beat_grid: BeatGrid,
    novelty_candidates: Vec<Novelty>,
    repeated_material: Vec<Repeat>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct BeatGrid {
    #[serde(default)]
    fit_reliable: bool,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Novelty {
    time: f64,
    scale_beats: u32,
    score_percentile: f64,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Repeat {
    start: f64,
    end: f64,
    repeat_start: f64,
    repeat_end: f64,
    similarity: f64,
}

pub fn compile_interpretation(json: &str, config: CompileConfig) -> Result<Interpretation, String> {
    let data: Evidence = serde_json::from_str(json).map_err(|error| error.to_string())?;
    validate(&data)?;
    let beat = data.musical_memory.beat_period;
    let sources: [&Source; 4] =
        std::array::from_fn(|i| &data.stem_interpretation.sources[SOURCES[i]]);
    let transitions = transitions(&data, &sources);
    let boundaries = boundaries(&data, &transitions);

    // One continuous source-driven timeline prevents phrase/cue joins from
    // resetting position. Cue profiles sample it at identical absolute times.
    // Motion is event-driven: each source gesture is a physical impulse (windup
    // before the measured onset, accent at it, follow-through after), not a level.
    let step = beat / 4.0;
    let count = (data.duration / step).ceil() as usize + 1;
    let rate = data.stem_interpretation.envelope_rate;
    let drum_hits = spaced(onsets(sources[1], rate, 0.3), beat * 0.9);
    let bass_hits = spaced(onsets(sources[0], rate, 0.25), beat * 0.9);
    let vocal_hits = spaced(onsets(sources[2], rate, 0.25), beat * 0.45);
    let mut motion = Vec::with_capacity(count);
    for i in 0..count {
        let time = (i as f64 * step).min(data.duration);
        let activity = activities(&sources, rate, time, beat * 0.45);
        let vocal = mean(
            &sources[2].whole_track_activity,
            rate,
            time - 0.5,
            time + 0.5,
        );
        let other = activity[3];
        let total = |t: f64| activities(&sources, rate, t, beat).iter().sum::<f64>();
        // Whole-song lookahead: rising material builds tension, falling releases.
        let trend = (total(time + beat * 6.0) - total(time - beat * 2.0)).clamp(-1.5, 1.5) / 1.5;
        let gain = 0.55 + 0.45 * (total(time) / 2.0).clamp(0.0, 1.0);
        let bar = 8.0 * beat;
        let sway = (std::f64::consts::TAU * (time - data.musical_memory.beat_zero) / bar).sin();
        let mut sweep = 0.4 * other * sway;
        let mut lift = -0.1 + 0.3 * trend.max(0.0) + 0.9 * vocal;
        let mut fold = 0.25 * other * (std::f64::consts::TAU * time / (4.0 * beat)).cos()
            - 0.5 * vocal
            - 0.25 * trend.min(0.0).abs();
        for (n, hit) in drum_hits.iter().enumerate() {
            let k = windup_kernel(time - hit.0, 0.28, 0.22);
            let side = if n % 2 == 0 { 1.0 } else { -1.0 };
            sweep += side * 0.85 * hit.1 * k;
            fold += 0.5 * hit.1 * k;
        }
        for hit in &bass_hits {
            let k = windup_kernel(time - hit.0, 0.3, 0.45);
            lift -= 0.7 * hit.1 * k;
            fold += 0.55 * hit.1 * k;
        }
        for hit in &vocal_hits {
            lift += 0.35 * hit.1 * windup_kernel(time - hit.0, 0.15, 0.3);
        }
        let mut vector = [sweep * gain, lift * gain, fold * gain];
        // Forward-looking preparation uses only strong measured source/structure
        // transitions. Specials switch controls preparation, never core groove.
        if config.enable_windups {
            if let Some((arrival, source, _)) = transitions
                .iter()
                .find(|(arrival, _, _)| *arrival > time && *arrival - time <= beat * 1.5)
            {
                let gain = (1.0 - (arrival - time) / (beat * 1.5)).powi(2);
                vector[1] += gain * if *source == 2 { 0.24 } else { 0.12 };
                vector[2] -= gain * 0.12;
            }
        }
        let rms = if data.rms_envelope.is_empty() {
            sources
                .iter()
                .map(|source| mean(&source.absolute_rms, rate, time - 0.2, time + 0.2))
                .sum::<f64>()
        } else {
            mean(
                &data.rms_envelope,
                data.envelope_rate,
                time - 0.2,
                time + 0.2,
            )
        };
        let silence = ((rms - 0.003) / 0.007).clamp(0.0, 1.0);
        motion.push(vector.map(|value| (value * silence).clamp(-1.0, 1.0)));
    }

    let mut cues = Vec::new();
    for pair in boundaries.windows(2) {
        let (start, end) = (pair[0], pair[1]);
        if end - start < 1e-6 {
            continue;
        }
        let activity = activities(
            &sources,
            data.stem_interpretation.envelope_rate,
            (start + end) * 0.5,
            (end - start) * 0.5,
        );
        let rms = if data.rms_envelope.is_empty() {
            sources
                .iter()
                .map(|source| {
                    mean(
                        &source.absolute_rms,
                        data.stem_interpretation.envelope_rate,
                        start,
                        end,
                    )
                })
                .sum()
        } else {
            mean(&data.rms_envelope, data.envelope_rate, start, end)
        };
        let (character, formation) = character(activity, rms);
        let recall_from = if config.reuse_repeats {
            recall_at(&data, (start + end) * 0.5).map(|(old, _)| old - (end - start) * 0.5)
        } else {
            None
        };
        let anticipation = if config.enable_windups {
            transitions
                .iter()
                .find(|(time, _, _)| *time >= start && *time <= end + beat * 1.5)
                .map(|item| item.0)
        } else {
            None
        };
        let count = ((end - start) / step).ceil().max(2.0) as usize + 1;
        let mut profile = Vec::with_capacity(count);
        for i in 0..count {
            let time = start + (end - start) * i as f64 / (count - 1) as f64;
            let mut value = sample_motion(&motion, step, time);
            if config.reuse_repeats {
                if let Some((earlier, edge_distance)) = recall_at(&data, time) {
                    let old = sample_motion(&motion, step, earlier);
                    let fade = (edge_distance / beat).clamp(0.0, 1.0);
                    let weight = 0.55 * fade * fade * (3.0 - 2.0 * fade);
                    for axis in 0..3 {
                        value[axis] =
                            (weight * old[axis] + (1.0 - weight) * value[axis]).clamp(-1.0, 1.0);
                    }
                }
            }
            profile.push(value);
        }
        // Conservative evidence score, not calibrated semantic probability.
        let contrast = activity.iter().copied().fold(0.0, f64::max)
            - activity.iter().copied().fold(1.0, f64::min);
        let confidence =
            0.38 + if data.musical_structure.beat_grid.fit_reliable {
                0.16
            } else {
                0.0
            } + 0.16 * contrast
                + if recall_from.is_some() { 0.06 } else { 0.0 };
        let reason = format!(
            "estimated source activity bass {:.2}, drums {:.2}, vocals {:.2}, other {:.2}; {}{}; beat grid {}",
            activity[0], activity[1], activity[2], activity[3],
            if recall_from.is_some() { "related material recalled" } else { "current ordered source rhythm" },
            if anticipation.is_some() { "; preparing measured transition" } else { "" },
            if data.musical_structure.beat_grid.fit_reliable { "fit" } else { "provisional" },
        );
        cues.push(IntentCue {
            start,
            end,
            character: character.into(),
            formation: formation.into(),
            source_activity: activity,
            confidence,
            recall_from,
            anticipation,
            reason,
            profile,
        });
    }
    Ok(Interpretation {
        duration: data.duration,
        beat_period: beat,
        beat_zero: data.musical_memory.beat_zero,
        cues,
    })
}

/// Phrase edges plus strong measured source/structure transitions, sorted.
fn boundaries(data: &Evidence, transitions: &[(f64, usize, f64)]) -> Vec<f64> {
    let mut boundaries = vec![0.0, data.duration];
    for phrase in &data.musical_memory.phrases {
        boundaries.extend([phrase.start, phrase.end]);
    }
    boundaries.extend(transitions.iter().map(|(time, _, _)| *time));
    boundaries.sort_by(f64::total_cmp);
    boundaries.dedup_by(|a, b| (*a - *b).abs() < 0.08);
    boundaries
}

fn validate(data: &Evidence) -> Result<(), String> {
    if !data.duration.is_finite()
        || !(0.0..=21_600.0).contains(&data.duration)
        || data.duration == 0.0
    {
        return Err("duration must be finite, positive, and <= 6 hours".into());
    }
    if data.musical_memory.version != 1
        || data.stem_interpretation.version != 1
        || data.musical_structure.version != 1
    {
        return Err(
            "musicalMemory, stemInterpretation and musicalStructure version must be 1".into(),
        );
    }
    let beat = data.musical_memory.beat_period;
    if !beat.is_finite()
        || !(0.2..=3.0).contains(&beat)
        || !data.musical_memory.beat_zero.is_finite()
        || !data.envelope_rate.is_finite()
        || data.envelope_rate <= 0.0
        || !data.stem_interpretation.envelope_rate.is_finite()
        || data.stem_interpretation.envelope_rate <= 0.0
        || (data.duration - data.stem_interpretation.duration).abs() > 0.001
    {
        return Err("invalid beat grid, envelope rate or stem duration".into());
    }
    if data.musical_memory.phrases.is_empty() {
        return Err("musicalMemory needs phrases".into());
    }
    let mut expected = 0.0;
    for (i, phrase) in data.musical_memory.phrases.iter().enumerate() {
        if phrase.start != expected
            || !phrase.end.is_finite()
            || phrase.end <= phrase.start
            || phrase.rhythm.len() != 32
            || phrase.low_rhythm.len() != 32
            || phrase.high_rhythm.len() != 32
            || !phrase.similarity.is_finite()
            || !(0.0..=1.0).contains(&phrase.similarity)
            || phrase
                .rhythm
                .iter()
                .chain(&phrase.low_rhythm)
                .chain(&phrase.high_rhythm)
                .any(|v| !v.is_finite() || !(0.0..=1.0).contains(v))
            || phrase.repeat_of.is_some_and(|source| source >= i)
        {
            return Err(format!("invalid musicalMemory phrase {i}"));
        }
        expected = phrase.end;
    }
    if expected != data.duration {
        return Err("musicalMemory phrases must cover duration".into());
    }
    for name in SOURCES {
        let source = data
            .stem_interpretation
            .sources
            .get(name)
            .ok_or_else(|| format!("missing source {name}"))?;
        for (label, series) in [
            ("absoluteRms", &source.absolute_rms),
            ("wholeTrackActivity", &source.whole_track_activity),
            ("spectralFlux", &source.spectral_flux),
            ("transientDensity", &source.transient_density),
        ] {
            if series.len()
                < (data.duration * data.stem_interpretation.envelope_rate).ceil() as usize
                || series
                    .iter()
                    .any(|v| !v.is_finite() || *v < 0.0 || (label != "absoluteRms" && *v > 1.0))
            {
                return Err(format!("invalid {name}.{label}"));
            }
        }
        if source.candidates.iter().any(|c| {
            !c.time.is_finite()
                || c.time < 0.0
                || c.time > data.duration
                || !c.confidence.is_finite()
                || !(0.0..=1.0).contains(&c.confidence)
        }) {
            return Err(format!("invalid {name}.candidates"));
        }
    }
    if !data.rms_envelope.is_empty()
        && (data.rms_envelope.len() < (data.duration * data.envelope_rate).ceil() as usize
            || data.rms_envelope.iter().any(|v| !v.is_finite() || *v < 0.0))
    {
        return Err("invalid rmsEnvelope".into());
    }
    if data.musical_structure.repeated_material.iter().any(|r| {
        !r.start.is_finite()
            || !r.end.is_finite()
            || !r.repeat_start.is_finite()
            || !r.repeat_end.is_finite()
            || !r.similarity.is_finite()
            || r.start < 0.0
            || r.end <= r.start
            || r.repeat_start <= r.start
            || r.repeat_end <= r.repeat_start
            || r.repeat_end > data.duration
            || !(0.0..=1.0).contains(&r.similarity)
    }) {
        return Err("invalid repeatedMaterial".into());
    }
    Ok(())
}

fn mean(values: &[f64], rate: f64, start: f64, end: f64) -> f64 {
    let a = ((start.max(0.0) * rate).floor() as usize).min(values.len() - 1);
    let b = (((end.max(start + 1.0 / rate)) * rate).ceil() as usize)
        .min(values.len())
        .max(a + 1);
    let slice = &values[a..b];
    slice.iter().sum::<f64>() / slice.len() as f64
}

fn activities(sources: &[&Source; 4], rate: f64, time: f64, half: f64) -> [f64; 4] {
    std::array::from_fn(|i| {
        mean(
            &sources[i].whole_track_activity,
            rate,
            time - half,
            time + half,
        )
        .clamp(0.0, 1.0)
    })
}

/// Local-maximum flux peaks above an adaptive floor: (time, strength 0..1).
fn onsets(source: &Source, rate: f64, floor: f64) -> Vec<(f64, f64)> {
    let v = &source.spectral_flux;
    let w = rate as usize;
    (1..v.len().saturating_sub(1))
        .filter_map(|i| {
            let lo = i.saturating_sub(w);
            let hi = (i + w).min(v.len());
            let local = v[lo..hi].iter().sum::<f64>() / (hi - lo) as f64;
            (v[i] > v[i - 1] && v[i] >= v[i + 1] && v[i] > floor && v[i] > 1.5 * local)
                .then(|| (i as f64 / rate, v[i].clamp(0.0, 1.0)))
        })
        .collect()
}

/// Keep the stronger of any two events closer than `gap`.
fn spaced(events: Vec<(f64, f64)>, gap: f64) -> Vec<(f64, f64)> {
    let mut out: Vec<(f64, f64)> = Vec::new();
    for e in events {
        match out.last_mut() {
            Some(last) if e.0 - last.0 < gap => {
                if e.1 > last.1 {
                    *last = e;
                }
            }
            _ => out.push(e),
        }
    }
    out
}

/// Impulse response around an event at d=0: opposite-direction windup over
/// `before` seconds (peak -0.25), accent 1.0 at the event, exponential follow-through.
fn windup_kernel(d: f64, before: f64, after: f64) -> f64 {
    if d < -before {
        0.0
    } else if d < 0.0 {
        let u = (d + before) / before;
        -0.25 * (std::f64::consts::PI * u).sin().max(0.0) * (1.0 - u) + u.powi(3)
    } else {
        (-d / after).exp()
    }
}

fn phrase_at(phrases: &[Phrase], time: f64) -> &Phrase {
    let i = phrases
        .partition_point(|p| p.end <= time)
        .min(phrases.len() - 1);
    &phrases[i]
}

fn sample_motion(motion: &[[f64; 3]], step: f64, time: f64) -> [f64; 3] {
    let index = (time.max(0.0) / step).min((motion.len() - 1) as f64);
    let a = index.floor() as usize;
    let b = (a + 1).min(motion.len() - 1);
    let f = index - a as f64;
    std::array::from_fn(|axis| motion[a][axis] * (1.0 - f) + motion[b][axis] * f)
}

fn character(a: [f64; 4], rms: f64) -> (&'static str, &'static str) {
    if rms < 0.005 {
        ("silence", "breathe")
    } else if a[0] > 0.43 && a[2] > 0.35 {
        ("interlocked", "mirror")
    } else if a[2] > 0.3 {
        ("vocal-led", "canon")
    } else if a[0] > 0.43 {
        ("bass-led", "unison")
    } else if a[1] > 0.17 && a[2] < 0.15 {
        ("percussive-open", "wave")
    } else if a[3] > 0.3 {
        ("textural", "scatter")
    } else {
        ("sparse", "breathe")
    }
}

fn transitions(data: &Evidence, sources: &[&Source; 4]) -> Vec<(f64, usize, f64)> {
    let beat = data.musical_memory.beat_period;
    let rate = data.stem_interpretation.envelope_rate;
    let mut events = Vec::new();
    for (source_index, source) in sources.iter().enumerate() {
        if source_index == 1 {
            continue;
        } // drum onsets are beat events, not section transitions
        for candidate in &source.candidates {
            if candidate.confidence < 0.5
                || !matches!(candidate.kind.as_str(), "activity_entry" | "activity_exit")
                || candidate.time < beat * 2.0
                || candidate.time > data.duration - beat * 2.0
            {
                continue;
            }
            let before = mean(
                &source.whole_track_activity,
                rate,
                candidate.time - beat * 4.0,
                candidate.time - beat * 0.5,
            );
            let after = mean(
                &source.whole_track_activity,
                rate,
                candidate.time + beat * 0.5,
                candidate.time + beat * 4.0,
            );
            let change = (after - before).abs();
            if change >= if source_index == 2 { 0.23 } else { 0.29 } {
                events.push((
                    candidate.time,
                    source_index,
                    (candidate.confidence * change).min(1.0),
                ));
            }
        }
    }
    for novelty in &data.musical_structure.novelty_candidates {
        if novelty.scale_beats >= 8
            && novelty.score_percentile >= 0.94
            && novelty.time > beat * 2.0
            && novelty.time < data.duration - beat * 2.0
        {
            let before = activities(sources, rate, novelty.time - beat * 2.0, beat);
            let after = activities(sources, rate, novelty.time + beat * 2.0, beat);
            let (source, change) = (0..4)
                .map(|i| (i, (after[i] - before[i]).abs()))
                .max_by(|a, b| a.1.total_cmp(&b.1))
                .unwrap();
            if change > 0.3 {
                events.push((
                    novelty.time,
                    source,
                    (novelty.score_percentile * change).min(1.0),
                ));
            }
        }
    }
    events.sort_by(|a, b| a.0.total_cmp(&b.0));
    let mut selected: Vec<(f64, usize, f64)> = Vec::new();
    for event in events {
        if let Some(last) = selected.last_mut() {
            if event.0 - last.0 < beat * 1.5 {
                if event.2 > last.2 {
                    *last = event;
                }
                continue;
            }
        }
        selected.push(event);
    }
    selected
}

fn recall_at(data: &Evidence, time: f64) -> Option<(f64, f64)> {
    let structure = data
        .musical_structure
        .repeated_material
        .iter()
        .filter(|r| {
            r.similarity >= 0.9
                && time >= r.repeat_start
                && time <= r.repeat_end
                && (r.end - r.start - (r.repeat_end - r.repeat_start)).abs()
                    < data.musical_memory.beat_period
        })
        .max_by(|a, b| a.similarity.total_cmp(&b.similarity));
    if let Some(r) = structure {
        let earlier = r.start + time - r.repeat_start;
        let distance = source_distance(data, time, earlier);
        if distance < 0.28 {
            let similarity_edge = data.musical_memory.beat_period * (1.0 - distance / 0.28);
            return Some((
                earlier,
                (time - r.repeat_start)
                    .min(r.repeat_end - time)
                    .min(similarity_edge),
            ));
        }
    }
    let phrase = phrase_at(&data.musical_memory.phrases, time);
    let earlier = phrase.repeat_of?;
    if phrase.similarity < 0.85 {
        return None;
    }
    let original = &data.musical_memory.phrases[earlier];
    if (original.end - original.start - (phrase.end - phrase.start)).abs() > 1e-4 {
        return None;
    }
    let earlier = original.start + time - phrase.start;
    let distance = source_distance(data, time, earlier);
    let similarity_edge = data.musical_memory.beat_period * (1.0 - distance / 0.28);
    (distance < 0.28).then_some((
        earlier,
        (time - phrase.start)
            .min(phrase.end - time)
            .min(similarity_edge),
    ))
}

fn source_distance(data: &Evidence, now: f64, earlier: f64) -> f64 {
    SOURCES
        .iter()
        .map(|name| {
            let source = &data.stem_interpretation.sources[*name];
            let rate = data.stem_interpretation.envelope_rate;
            let half = data.musical_memory.beat_period * 0.5;
            (mean(&source.whole_track_activity, rate, now - half, now + half)
                - mean(
                    &source.whole_track_activity,
                    rate,
                    earlier - half,
                    earlier + half,
                ))
            .abs()
        })
        .sum::<f64>()
        / 4.0
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    pub(super) fn fixture(vocal: f64, bass: f64) -> String {
        let source = |activity: f64| json!({"absoluteRms":vec![0.1;160],"wholeTrackActivity":vec![activity;160],"spectralFlux":vec![0.55;160],"transientDensity":vec![0.4;160],"candidates":[]});
        json!({"duration":8.0,"envelopeRate":20.0,"rmsEnvelope":vec![0.2;160],
            "musicalMemory":{"version":1,"beatPeriod":0.5,"beatZero":0.0,"phrases":[{"start":0.0,"end":8.0,"rhythm":vec![0.5;32],"lowRhythm":vec![0.5;32],"highRhythm":vec![0.5;32],"similarity":0.0}]},
            "stemInterpretation":{"version":1,"duration":8.0,"envelopeRate":20.0,"sources":{"bass":source(bass),"drums":source(0.3),"vocals":source(vocal),"other":source(0.4)}},
            "musicalStructure":{"version":1,"beatGrid":{"fitReliable":false},"noveltyCandidates":[],"repeatedMaterial":[]}
        }).to_string()
    }

    #[test]
    fn same_tempo_different_sources_change_character_and_motion() {
        let full = compile_interpretation(&fixture(0.7, 0.7), CompileConfig::default()).unwrap();
        let break_like =
            compile_interpretation(&fixture(0.02, 0.1), CompileConfig::default()).unwrap();
        assert_eq!(full.beat_period, break_like.beat_period);
        assert_ne!(full.cues[0].character, break_like.cues[0].character);
        assert_ne!(full.cues[0].profile, break_like.cues[0].profile);
    }

    #[test]
    fn bad_source_contract_fails() {
        let mut value: serde_json::Value = serde_json::from_str(&fixture(0.7, 0.7)).unwrap();
        value["stemInterpretation"]["sources"]["bass"]["wholeTrackActivity"] = json!([0.3]);
        assert!(compile_interpretation(&value.to_string(), CompileConfig::default()).is_err());
    }

    #[test]
    fn recurrence_and_rest_follow_evidence_with_specials_off() {
        let mut value: serde_json::Value = serde_json::from_str(&fixture(0.7, 0.7)).unwrap();
        value["duration"] = json!(16.0);
        value["rmsEnvelope"] = json!([vec![0.2; 160], vec![0.2; 120], vec![0.0; 40]].concat());
        value["musicalMemory"]["phrases"] = json!([
            {"start":0.0,"end":8.0,"rhythm":vec![0.5;32],"lowRhythm":vec![0.5;32],"highRhythm":vec![0.5;32],"similarity":0.0},
            {"start":8.0,"end":16.0,"rhythm":vec![0.7;32],"lowRhythm":vec![0.3;32],"highRhythm":vec![0.6;32],"similarity":0.95,"repeatOf":0}
        ]);
        value["stemInterpretation"]["duration"] = json!(16.0);
        for name in SOURCES {
            for field in [
                "absoluteRms",
                "wholeTrackActivity",
                "spectralFlux",
                "transientDensity",
            ] {
                let first = value["stemInterpretation"]["sources"][name][field]
                    .as_array()
                    .unwrap()
                    .clone();
                value["stemInterpretation"]["sources"][name][field] =
                    json!([first.clone(), first].concat());
            }
        }
        value["musicalStructure"]["repeatedMaterial"] =
            json!([{"start":0.0,"end":8.0,"repeatStart":8.0,"repeatEnd":16.0,"similarity":0.96}]);
        let config = CompileConfig {
            enable_hits: false,
            enable_windups: false,
            reuse_repeats: true,
        };
        let reused = compile_interpretation(&value.to_string(), config).unwrap();
        let varied = compile_interpretation(
            &value.to_string(),
            CompileConfig {
                reuse_repeats: false,
                ..config
            },
        )
        .unwrap();
        assert_eq!(reused.cues.len(), 2);
        assert_eq!(reused.cues[1].recall_from, Some(0.0));
        assert_eq!(varied.cues[1].recall_from, None);
        assert_ne!(reused.cues[1].profile[16], varied.cues[1].profile[16]);
        assert_eq!(
            reused.cues[0].profile.last(),
            reused.cues[1].profile.first()
        );
        assert_eq!(reused.cues[1].profile.last(), Some(&[0.0; 3]));
        assert!(reused.cues.iter().all(|cue| cue.anticipation.is_none()));

        for name in ["bass", "vocals"] {
            let activity = value["stemInterpretation"]["sources"][name]["wholeTrackActivity"]
                .as_array_mut()
                .unwrap();
            activity[160..].fill(json!(0.0));
        }
        let changed = compile_interpretation(&value.to_string(), config).unwrap();
        assert_eq!(changed.cues[1].recall_from, None);
    }

    #[test]
    fn measured_future_entry_prepares_before_arrival() {
        let mut value: serde_json::Value = serde_json::from_str(&fixture(0.05, 0.1)).unwrap();
        let mut vocal = vec![0.05; 80];
        vocal.extend(vec![0.7; 80]);
        value["stemInterpretation"]["sources"]["vocals"]["wholeTrackActivity"] = json!(vocal);
        value["stemInterpretation"]["sources"]["vocals"]["candidates"] =
            json!([{"kind":"activity_entry","time":4.0,"confidence":0.8}]);
        let enabled = compile_interpretation(&value.to_string(), CompileConfig::default()).unwrap();
        let disabled = compile_interpretation(
            &value.to_string(),
            CompileConfig {
                enable_windups: false,
                ..CompileConfig::default()
            },
        )
        .unwrap();
        assert!(enabled.cues.iter().any(|cue| cue.anticipation == Some(4.0)));
        assert!(disabled.cues.iter().all(|cue| cue.anticipation.is_none()));
        assert_ne!(enabled.cues[0].profile, disabled.cues[0].profile);
    }
}
