//! Offline, rig-independent musical interpretation. All decisions use measured
//! source, structure, and phrase evidence; playback only samples resolved intent.

use crate::CompileConfig;
use serde::{Deserialize, Serialize};

pub mod figures;

const SOURCES: [&str; 4] = ["bass", "drums", "vocals", "other"];

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
    /// Onsets and phrases per instrument lane (`scripts/dance_notes.py`).
    #[serde(default)]
    note_track: Option<NoteTrack>,
}

#[derive(Deserialize)]
struct NoteTrack {
    lanes: std::collections::HashMap<String, Lane>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Lane {
    /// [time, rough MIDI pitch, strength 0..1]
    #[serde(default)]
    notes: Vec<[f64; 3]>,
    /// A-weighted level in dB for each beat of the grid.
    #[serde(default)]
    level_per_beat: Vec<f64>,
    /// A-weighted spectral centroid as a MIDI pitch for each beat; 0 if silent.
    #[serde(default)]
    brightness_per_beat: Vec<f64>,
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
    novelty_candidates: Vec<Novelty>,
    repeated_material: Vec<Repeat>,
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

fn phrase_at(phrases: &[Phrase], time: f64) -> &Phrase {
    let i = phrases
        .partition_point(|p| p.end <= time)
        .min(phrases.len() - 1);
    &phrases[i]
}

/// `a`: each stem's level against its own loudest. `share`: each stem's share
/// of the sound's power. `loudness`: the level against the song's loud
/// passages. By `a` alone a voice that ranges from soft to screaming reads as
/// absent while it carries the verse, and the near-empty voice stem of an
/// instrumental reads as singing; and a climax whose bass is buried is still
/// the song at full strength.
fn character(
    a: [f64; 4],
    rms: f64,
    share: [f64; 4],
    loudness: f64,
) -> (&'static str, &'static str) {
    // An active voice stem counts only with a sixth of the power of the
    // melodic instruments beside it.
    let sung = a[2] > 0.3 && share[2] > 0.15 * share[3] || share[2] > 0.14;
    if rms < 0.005 {
        ("silence", "breathe")
    } else if a[0] > 0.43 && a[2] > 0.35 || sung && loudness > 0.7 {
        ("interlocked", "mirror")
    } else if sung {
        ("vocal-led", "canon")
    } else if a[0] > 0.43 {
        // Same dance; the name says what the user hears in front.
        if share[3] > 1.5 * share[0] {
            ("melody-led", "unison")
        } else {
            ("bass-led", "unison")
        }
    } else if a[1] > 0.17 && (a[2] < 0.15 || share[2] < 0.04) {
        ("percussive-open", "wave")
    } else if share[1] > 0.4 && (a[2] < 0.15 || share[2] < 0.04) {
        // Same dance. A sparse kick carries the power (drums are spikes)
        // without being a percussion passage to the ear.
        ("kick-led", "wave")
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
    use serde_json::json;

    #[test]
    fn a_soft_voice_leads_and_a_loud_sung_passage_is_the_song_at_full() {
        // "Five Years": steady bass, a voice far below its own loudest.
        let verse = [0.7, 0.15, 0.25, 0.1];
        let voice = |v: f64| [0.5 - v, 0.2, v, 0.3];
        assert_eq!(super::character(verse, 0.1, voice(0.05), 0.4).0, "bass-led");
        assert_eq!(
            super::character(verse, 0.1, voice(0.45), 0.4).0,
            "vocal-led"
        );
        // Its climax: the bass buried, everything loud.
        let climax = [0.3, 0.25, 0.55, 0.8];
        assert_eq!(
            super::character(climax, 0.2, voice(0.3), 0.6).0,
            "vocal-led"
        );
        assert_eq!(
            super::character(climax, 0.2, voice(0.3), 0.9).0,
            "interlocked"
        );
        // "Presence", an instrumental: the voice stem is nearly empty but
        // peaks against itself; a lone kick carries the intro; and keys in
        // front of an active bass lead.
        let intro = [0.0, 0.16, 0.75, 0.5];
        let class = super::character(intro, 0.1, [0.0, 0.6, 0.01, 0.39], 0.4).0;
        assert_eq!(class, "kick-led");
        let drop = [0.7, 0.19, 0.1, 0.7];
        let class = super::character(drop, 0.2, [0.23, 0.3, 0.0, 0.47], 0.9).0;
        assert_eq!(class, "melody-led");
    }

    pub(super) fn fixture(vocal: f64, bass: f64) -> String {
        let source = |activity: f64| json!({"absoluteRms":vec![0.2*activity;160],"wholeTrackActivity":vec![activity;160],"spectralFlux":vec![0.55;160],"transientDensity":vec![0.4;160],"candidates":[]});
        json!({"duration":8.0,"envelopeRate":20.0,"rmsEnvelope":vec![0.2;160],
            "musicalMemory":{"version":1,"beatPeriod":0.5,"beatZero":0.0,"phrases":[{"start":0.0,"end":8.0,"rhythm":vec![0.5;32],"lowRhythm":vec![0.5;32],"highRhythm":vec![0.5;32],"similarity":0.0}]},
            "stemInterpretation":{"version":1,"duration":8.0,"envelopeRate":20.0,"sources":{"bass":source(bass),"drums":source(0.3),"vocals":source(vocal),"other":source(0.4)}},
            "musicalStructure":{"version":1,"beatGrid":{"fitReliable":false},"noveltyCandidates":[],"repeatedMaterial":[]}
        }).to_string()
    }
}
