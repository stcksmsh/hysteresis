//! Acceptance checks on synthetic full songs: structure-driven decisions,
//! recurrence, section transitions, rests, exact anchors and the full audit.
//! Synthetic fixtures stand in for real audio here; the supplied track is
//! audited separately with `examples/audit_score.rs`.

use hyst_compile::{compile_sidecar_json, Score};
use serde_json::json;

const RATE: f64 = 10.0;
const TEMPO: f64 = 120.0;

/// One section: seconds, loudness 0..1, brightness 0..1 (high vs low bands).
#[derive(Clone, Copy)]
struct Part(f64, f32, f32);

/// Deterministic sidecar with RMS. Ripple depends on time *within* a section,
/// so repeated sections are genuinely repeated material.
fn song(parts: &[Part], accents: &[f64]) -> String {
    let duration: f64 = parts.iter().map(|p| p.0).sum();
    let n = (duration * RATE).ceil() as usize;
    let (mut energy, mut rms, mut low, mut high, mut centroid) =
        (vec![], vec![], vec![], vec![], vec![]);
    for i in 0..n {
        let t = i as f64 / RATE;
        let (mut start, mut part) = (0.0, parts[0]);
        for p in parts {
            if t < start + p.0 {
                part = *p;
                break;
            }
            start += p.0;
        }
        let local = t - start;
        let ripple = if part.1 > 0.0 {
            0.12 * ((local * 0.9).sin() as f32)
        } else {
            0.0
        };
        let level = (part.1 + ripple * part.1).max(0.0);
        energy.push(level);
        rms.push(level * 0.25);
        low.push(level * (1.0 - part.2));
        high.push(level * part.2);
        centroid.push(0.2 + 0.6 * part.2);
    }
    let beats: Vec<f64> = (0..(duration * TEMPO / 60.0) as usize)
        .map(|i| i as f64 * 60.0 / TEMPO)
        .collect();
    // Weak onsets on every loud beat; strong isolated accents where requested.
    let mut onsets: Vec<_> = beats
        .iter()
        .filter(|b| energy[((**b * RATE) as usize).min(n - 1)] > 0.05)
        .map(|b| json!({"t": b, "strength": 0.2, "tone": 0.5, "pan": 0.0}))
        .collect();
    onsets.extend(
        accents
            .iter()
            .map(|t| json!({"t": t, "strength": 1.0, "tone": 0.2, "pan": 0.0})),
    );
    json!({
        "schema": 3, "duration": duration, "tempo": TEMPO, "beats": beats,
        "sections": [], "events": [], "onsets": onsets,
        "energyEnvelope": energy, "rmsEnvelope": rms,
        "bandEnvelope": {"sub": low, "low": low, "mid": energy, "presence": high, "air": high},
        "centroidEnvelope": centroid, "flatnessEnvelope": energy, "envelopeRate": RATE
    })
    .to_string()
}

const INTRO: Part = Part(16.0, 0.25, 0.5);
const VERSE: Part = Part(16.0, 0.55, 0.3);
const CHORUS: Part = Part(16.0, 1.0, 0.7);
const SILENCE: Part = Part(12.0, 0.0, 0.5);

fn pop_song() -> Score {
    compile_sidecar_json(&song(
        &[INTRO, VERSE, CHORUS, VERSE, CHORUS, SILENCE],
        &[],
    ))
    .unwrap()
}

fn cues_in(score: &Score, section: usize) -> Vec<&hyst_compile::Cue> {
    score
        .cues
        .iter()
        .filter(|c| c.section == Some(section))
        .collect()
}

#[test]
fn full_song_passes_audit() {
    let score = pop_song();
    let report = hyst_previz::audit_score(&score).unwrap_or_else(|e| panic!("{e}: {score:#?}"));
    assert!(report["sampledFloorClearanceCm"].as_f64().unwrap() > 10.0);
}

#[test]
fn sections_follow_song_structure_and_recur() {
    let score = pop_song();
    let levels: Vec<_> = score.sections.iter().map(|s| s.level.as_str()).collect();
    assert_eq!(levels, ["quiet", "mid", "peak", "mid", "peak", "rest"], "{:#?}", score.sections);
    let (verse2, chorus2) = (&score.sections[3], &score.sections[4]);
    assert_eq!(verse2.repeat_of, Some(1));
    assert_eq!(chorus2.repeat_of, Some(2));
    assert_eq!((verse2.variation, chorus2.variation), (1, 1));
    assert_ne!(score.sections[1].motif, score.sections[2].motif);
    for (a, b) in [(1, 3), (2, 4)] {
        let first: Vec<_> = cues_in(&score, a).iter().map(|c| c.gesture.clone()).collect();
        let again: Vec<_> = cues_in(&score, b).iter().map(|c| c.gesture.clone()).collect();
        // Same phrase (except the exit cue, which depends on what follows).
        let n = first.len().min(again.len()) - 1;
        assert_eq!(first[..n], again[..n], "section {b} should replay section {a}'s phrase");
        // Variation mirrors the motif rather than copying joint values.
        let excursion = |cs: &[&hyst_compile::Cue]| -> Vec<f64> {
            cs[1..n].iter().map(|c| c.knots[2].joints[0] - c.knots[0].joints[0]).collect()
        };
        let (x, y) = (excursion(&cues_in(&score, a)), excursion(&cues_in(&score, b)));
        assert!(
            x.iter().zip(&y).any(|(p, q)| p * q < 0.0),
            "repeat should mirror shoulder direction: {x:?} vs {y:?}"
        );
    }
}

#[test]
fn section_changes_get_transition_cues_and_postures() {
    let score = pop_song();
    for (i, pair) in score.sections.windows(2).enumerate() {
        let exit = cues_in(&score, i).last().copied().unwrap();
        assert_eq!(exit.end, pair[1].start, "section boundary must be a cue boundary");
        let rank = |l: &str| ["rest", "quiet", "mid", "peak"].iter().position(|x| *x == l);
        let expected = match rank(&pair[1].level).cmp(&rank(&pair[0].level)) {
            std::cmp::Ordering::Greater => "gather",
            std::cmp::Ordering::Less => "settle",
            std::cmp::Ordering::Equal => continue,
        };
        assert_eq!(exit.gesture, expected, "exit of section {i}: {}", exit.reason);
    }
    // Peak register sits more open (shoulder up, elbow extended) than quiet.
    let mean = |i: usize, j: usize| {
        let s = &score.sections[i];
        let n = 200;
        (0..n)
            .map(|k| score.sample(s.start + (s.end - s.start) * k as f64 / n as f64)[j])
            .sum::<f64>()
            / n as f64
    };
    assert!(mean(2, 0) > mean(0, 0) + 4.0, "shoulder {} vs {}", mean(2, 0), mean(0, 0));
    assert!(mean(2, 1) > mean(0, 1) + 8.0, "elbow {} vs {}", mean(2, 1), mean(0, 1));
    // Silence after the last chorus: the arm settles, then holds still.
    assert!(cues_in(&score, 5).iter().all(|c| c.gesture == "hold"));
}

#[test]
fn matched_tempo_different_structure_changes_decisions_not_just_scale() {
    let a = pop_song();
    let b = compile_sidecar_json(&song(
        &[CHORUS, SILENCE, INTRO, CHORUS, VERSE, VERSE],
        &[],
    ))
    .unwrap();
    let gesture_at = |s: &Score, t: f64| {
        s.cues
            .iter()
            .find(|c| t >= c.start && t < c.end)
            .map(|c| c.gesture.clone())
            .unwrap()
    };
    let samples: Vec<f64> = (0..90).map(|i| i as f64).collect();
    let differ = samples
        .iter()
        .filter(|t| gesture_at(&a, **t) != gesture_at(&b, **t))
        .count();
    assert!(differ * 10 >= samples.len() * 4, "only {differ}/90 decisions differ");
    // Structure B rests at 16–28s; structure A is mid-verse there.
    assert_eq!(gesture_at(&b, 20.0), "hold");
    assert_ne!(gesture_at(&a, 20.0), "hold");
    hyst_previz::audit_score(&b).unwrap();
}

#[test]
fn isolated_accents_land_exactly_inside_sections() {
    let accents = [37.3, 70.1];
    let score = compile_sidecar_json(&song(
        &[INTRO, VERSE, CHORUS, VERSE, CHORUS, SILENCE],
        &accents,
    ))
    .unwrap();
    hyst_previz::audit_score(&score).unwrap();
    for t in accents {
        let cue = score
            .cues
            .iter()
            .find(|c| c.start < t && t < c.end)
            .unwrap();
        assert_eq!(cue.arrival_anchor, Some(t), "{cue:#?}");
        let arrival = cue.knots.iter().find(|k| k.phase == "arrival").unwrap();
        assert_eq!(score.sample(t), arrival.joints);
    }
}

#[test]
fn short_clip_without_structure_is_one_section() {
    let score = compile_sidecar_json(&song(&[Part(8.0, 0.5, 0.5)], &[])).unwrap();
    assert_eq!(score.sections.len(), 1);
    assert!(score.cues.iter().all(|c| c.section == Some(0)));
    hyst_previz::audit_score(&score).unwrap();
}

