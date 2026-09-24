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
    // Loud: a new home pose every 2 bars. Quiet: every 4 bars.
    assert!(moves_in(&score, 2).len() >= 3, "{}", moves_in(&score, 2).len());
    assert!(moves_in(&score, 0).len() <= 2, "{}", moves_in(&score, 0).len());
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
    for k in 0..20 {
        let q = score.sample(r0 + 3.0 + (r1 - r0 - 3.0) * k as f64 / 20.0);
        assert!((0..3).all(|j| (q[j] - held[j]).abs() < 1e-9), "{q:?} vs {held:?}");
    }
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

/// Add synthetic `elements`: vocals lead 0..24 s with a melody rising then
/// falling (8 s cycle), bass leads 24..48 s.
fn with_elements(json: &str) -> String {
    let mut v: serde_json::Value = serde_json::from_str(json).unwrap();
    let n = (v["duration"].as_f64().unwrap() * RATE).ceil() as usize;
    let t = |i: usize| i as f64 / RATE;
    let vocals: Vec<f64> = (0..n).map(|i| if t(i) < 24.0 { 0.9 } else { 0.2 }).collect();
    let bass: Vec<f64> = (0..n).map(|i| if t(i) < 24.0 { 0.2 } else { 0.9 }).collect();
    let melody: Vec<f64> = (0..n)
        .map(|i| if t(i) < 24.0 { 0.5 - 0.5 * (std::f64::consts::TAU * t(i) / 8.0).cos() } else { -1.0 })
        .collect();
    v["elements"] = json!({"drums": vec![0.1; n], "bass": bass, "vocals": vocals,
        "synth": vec![0.1; n], "melody": melody, "melodyOnsets": []});
    v.to_string()
}

#[test]
fn arm_follows_the_dominant_element() {
    let score = compile_sidecar_json(&with_elements(&song(&[Part(48.0, 0.6, 0.5)], &[]))).unwrap();
    hyst_previz::audit_score(&score).unwrap();
    let lead = |a: f64, b: f64, name: &str| {
        let ks: Vec<_> = score.cues.iter().flat_map(|c| &c.knots).filter(|k| k.time >= a && k.time < b).collect();
        ks.iter().filter(|k| k.phase == name).count() as f64 / ks.len() as f64
    };
    assert!(lead(4.0, 22.0, "vocals") > 0.8, "{}", lead(4.0, 22.0, "vocals"));
    assert!(lead(27.0, 46.0, "bass") > 0.8, "{}", lead(27.0, 46.0, "bass"));
    // Melody high (t = 12, 20) lifts the tip above melody low (t = 8, 16).
    let y = |t: f64| tip(score.sample(t)).1;
    let (high, low) = ((y(12.0) + y(20.0)) / 2.0, (y(8.0) + y(16.0)) / 2.0);
    assert!(high > low + 4.0, "tip height high-melody {high:.1} vs low {low:.1}");
}

#[test]
fn short_clip_without_structure_is_one_section() {
    let score = compile_sidecar_json(&song(&[Part(8.0, 0.5, 0.5)], &[])).unwrap();
    assert_eq!(score.sections.len(), 1);
    assert!(score.cues.iter().all(|c| c.section == Some(0)));
    hyst_previz::audit_score(&score).unwrap();
}

