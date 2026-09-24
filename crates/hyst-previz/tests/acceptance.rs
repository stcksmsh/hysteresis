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

#[test]
fn full_song_passes_audit() {
    let score = pop_song();
    let report = hyst_previz::audit_score(&score).unwrap_or_else(|e| panic!("{e}: {score:#?}"));
    assert!(report["sampledFloorClearanceCm"].as_f64().unwrap() > 10.0);
}

/// Phrase moves whose downbeat arrival lies inside section `i`.
fn moves_in(score: &Score, i: usize) -> Vec<&hyst_compile::Cue> {
    let s = &score.sections[i];
    score
        .cues
        .iter()
        .filter(|c| c.arrival_anchor.is_some_and(|t| t >= s.start && t < s.end))
        .collect()
}

fn tip(q: [f64; 3]) -> (f64, f64) {
    let p = hyst_previz::Arm::default().joints(hyst_previz::Pose(q.map(f64::to_radians)));
    (p[3].x, p[3].y)
}

/// Bounding-box diagonal (cm) of tip positions sampled across [a, b).
fn tip_travel(score: &Score, a: f64, b: f64) -> f64 {
    let pts: Vec<_> = (0..400).map(|k| tip(score.sample(a + (b - a) * k as f64 / 400.0))).collect();
    let (x0, x1) = pts.iter().fold((f64::MAX, f64::MIN), |m, p| (m.0.min(p.0), m.1.max(p.0)));
    let (y0, y1) = pts.iter().fold((f64::MAX, f64::MIN), |m, p| (m.0.min(p.1), m.1.max(p.1)));
    (x1 - x0).hypot(y1 - y0)
}

#[test]
fn sections_follow_song_structure_and_recur_mirrored() {
    let score = pop_song();
    let levels: Vec<_> = score.sections.iter().map(|s| s.level.as_str()).collect();
    assert_eq!(levels, ["quiet", "mid", "peak", "mid", "peak", "rest"], "{:#?}", score.sections);
    let (verse2, chorus2) = (&score.sections[3], &score.sections[4]);
    assert_eq!(verse2.repeat_of, Some(1));
    assert_eq!(chorus2.repeat_of, Some(2));
    assert_eq!((verse2.variation, chorus2.variation), (1, 1));
    assert_ne!(score.sections[1].motif, score.sections[2].motif);
    let swap = |g: &str| match g.rsplit_once(' ') {
        Some((n, "L")) => format!("{n} R"),
        Some((n, "R")) => format!("{n} L"),
        _ => g.to_string(),
    };
    for (a, b) in [(1, 3), (2, 4)] {
        let first: Vec<_> = moves_in(&score, a).iter().map(|c| swap(&c.gesture)).collect();
        let again: Vec<_> = moves_in(&score, b).iter().map(|c| c.gesture.clone()).collect();
        assert!(first.len() >= 2, "{first:?}");
        assert_eq!(first, again, "section {b} should replay section {a} mirrored");
    }
}

#[test]
fn loud_sections_dance_big_quiet_sections_breathe_rest_is_still() {
    let score = pop_song();
    let span = |i: usize| (score.sections[i].start, score.sections[i].end);
    let (q0, q1) = span(0);
    let (p0, p1) = span(2);
    let (quiet, peak) = (tip_travel(&score, q0 + 2.0, q1), tip_travel(&score, p0 + 1.0, p1));
    // The complaint this guards: tiny twitching around one home pose.
    assert!(peak > 60.0, "peak tip travel only {peak:.1} cm");
    assert!(peak > quiet * 1.3, "peak {peak:.1} vs quiet {quiet:.1}");
    // Loud: a new pose every bar with beat bounces. Quiet: few phrases, no bounces.
    let bounces = |i: usize| {
        moves_in(&score, i)
            .iter()
            .flat_map(|c| &c.knots)
            .filter(|k| k.phase == "beat")
            .count()
    };
    assert!(moves_in(&score, 2).len() >= 6, "{}", moves_in(&score, 2).len());
    assert!(moves_in(&score, 0).len() <= 3);
    assert!(bounces(2) >= 10 && bounces(0) == 0);
    // Arrivals land on the beat grid.
    let beats: Vec<f64> = (0..200).map(|i| i as f64 * 0.5).collect();
    for c in &score.cues {
        if let Some(t) = c.arrival_anchor {
            assert!(beats.iter().any(|b| (b - t).abs() < 1e-9), "arrival {t} off grid");
        }
    }
    // Silence: after arriving at rest, the pose is frozen.
    let (r0, r1) = span(5);
    let held = score.sample(r0 + 3.0);
    assert!((0..20).all(|k| score.sample(r0 + 3.0 + (r1 - r0 - 3.0) * k as f64 / 20.0) == held));
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
    // Structure B is silent at 16–28s (still once rested, before the next
    // section's wind-up); structure A is mid-verse there (moving).
    assert!(tip_travel(&b, 18.0, 25.0) < 1e-9);
    assert!(tip_travel(&a, 18.0, 25.0) > 20.0);
    hyst_previz::audit_score(&b).unwrap();
}

#[test]
fn strong_onsets_become_exact_hits() {
    // 36.6: inside a held bar (hit). 70.1: 0.1 s after a bar line (arrival snaps).
    // Accents inside a big move's wind-up are not separately hit (documented).
    let accents = [36.6, 70.1];
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
            .find(|c| c.knots.iter().any(|k| (k.phase == "hit" || k.phase == "arrival") && k.time == t))
            .unwrap_or_else(|| panic!("no hit/arrival knot at {t}"));
        let knot = cue.knots.iter().find(|k| k.time == t).unwrap();
        let at = score.sample(t);
        assert!((0..3).all(|j| (at[j] - knot.joints[j]).abs() < 1e-9), "{at:?} vs {:?}", knot.joints);
        // Accent is a real move: from the hit's wind-up, or from the phrase start.
        let before = if knot.phase == "hit" { score.sample(t - 0.22) } else { cue.knots[0].joints };
        assert!((0..3).any(|j| (knot.joints[j] - before[j]).abs() > 10.0), "{t}: {} {:?} vs {before:?}", knot.phase, knot.joints);
    }
}

#[test]
fn short_clip_without_structure_is_one_section() {
    let score = compile_sidecar_json(&song(&[Part(8.0, 0.5, 0.5)], &[])).unwrap();
    assert_eq!(score.sections.len(), 1);
    assert!(score.cues.iter().all(|c| c.section == Some(0)));
    hyst_previz::audit_score(&score).unwrap();
}

