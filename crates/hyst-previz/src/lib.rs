//! Arm previsualization. Rust compiles song cues and forward kinematics;
//! exported viewer samples absolute audio time. Synthetic studies remain references.

use std::f64::consts::{PI, TAU};
use std::fmt::Write;

pub const LOOP_BEATS: usize = 16;
pub const SAMPLES_PER_BEAT: usize = 64;

#[derive(Clone, Copy, Debug)]
pub struct Point {
    pub x: f64,
    pub y: f64,
}

/// Relative joint angles, radians. Shoulder measured from positive X.
#[derive(Clone, Copy, Debug)]
pub struct Pose(pub [f64; 3]);

#[derive(Clone, Copy, Debug)]
pub struct Arm {
    /// Illustrative link lengths in centimeters, not measured hardware.
    pub lengths: [f64; 3],
}

impl Default for Arm {
    fn default() -> Self {
        Self {
            lengths: [32.0, 26.0, 12.0],
        }
    }
}

impl Arm {
    pub fn joints(&self, pose: Pose) -> [Point; 4] {
        let mut points = [Point { x: 0.0, y: 0.0 }; 4];
        let mut heading = 0.0;
        for (i, angle) in pose.0.iter().enumerate() {
            heading += angle;
            points[i + 1] = Point {
                x: points[i].x + self.lengths[i] * heading.cos(),
                y: points[i].y + self.lengths[i] * heading.sin(),
            };
        }
        points
    }
}

#[derive(Clone, Copy, Debug)]
pub enum Study {
    Pulse,
    Groove,
    Phrase,
}

impl Study {
    pub fn name(self) -> &'static str {
        match self {
            Self::Pulse => "Pulse",
            Self::Groove => "Groove",
            Self::Phrase => "Groove + reach + pause",
        }
    }
}

/// Quintic easing has zero first and second derivatives at either end.
fn smooth(t: f64) -> f64 {
    let t = t.clamp(0.0, 1.0);
    t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
}

fn envelope(b: f64, start: f64, peak: f64, release: f64, end: f64) -> f64 {
    smooth((b - start) / (peak - start)) * (1.0 - smooth((b - release) / (end - release)))
}

/// Cyclic 16-beat study, repeatable and seekable without integration state.
/// Phrase accent peaks at beat 8 (third bar's first beat), after preparation.
pub fn sample(study: Study, beat: f64) -> Pose {
    let b = beat.rem_euclid(LOOP_BEATS as f64);
    let pulse = (TAU * b).cos();
    let mut q = [105.0, -65.0, -20.0];
    if matches!(study, Study::Pulse) {
        q[0] += 4.0 * pulse;
        q[1] -= 9.0 * pulse;
        q[2] += 3.0 * (TAU * b - 0.65).cos();
    } else {
        let pause = if matches!(study, Study::Phrase) {
            envelope(b, 13.0, 14.0, 15.0, 16.0)
        } else {
            0.0
        };
        let reach = if matches!(study, Study::Phrase) {
            envelope(b, 7.0, 8.0, 8.0, 10.0)
        } else {
            0.0
        };
        let prepare = if matches!(study, Study::Phrase) {
            envelope(b, 6.0, 6.8, 6.8, 8.0)
        } else {
            0.0
        };
        let groove = (1.0 - pause) * (1.0 - 0.85 * reach);
        q[0] += groove * (11.0 * (PI * b).sin() + 3.0 * pulse) + 13.0 * prepare - 40.0 * reach;
        q[1] +=
            groove * (-13.0 * (PI * b - 0.45).sin() - 7.0 * pulse) - 14.0 * prepare + 34.0 * reach;
        // Wrist follows shoulder/elbow; its reach peaks slightly later.
        let wrist_reach = if matches!(study, Study::Phrase) {
            envelope(b, 7.2, 8.2, 8.2, 10.2)
        } else {
            0.0
        };
        q[2] += groove * (9.0 * (PI * b - 0.95).sin()) - 7.0 * prepare + 19.0 * wrist_reach;
    }
    Pose(q.map(f64::to_radians))
}

pub fn stage(study: Study, beat: f64) -> &'static str {
    let b = beat.rem_euclid(LOOP_BEATS as f64);
    match study {
        Study::Pulse => "Pulse",
        Study::Groove => "Sway + pulse",
        Study::Phrase => match b {
            b if b < 6.0 => "Sway + pulse",
            b if b < 7.0 => "Prepare",
            b if b < 8.0 => "Reach",
            b if b < 8.3 => "Accent + follow-through",
            b if b < 10.2 => "Recover",
            b if b < 13.0 => "Sway + pulse",
            b if b < 14.0 => "Settle",
            b if b < 15.0 => "Hold",
            _ => "Return",
        },
    }
}

/// Standalone HTML; no server, dependencies, or external resources required.
/// Escape configuration as JSON string, including HTML script delimiters.
fn json_string(value: &str) -> String {
    let mut out = String::with_capacity(value.len() + 2);
    out.push('"');
    for ch in value.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '<' => out.push_str("\\u003c"),
            '>' => out.push_str("\\u003e"),
            '&' => out.push_str("\\u0026"),
            c if c <= '\u{1f}' => write!(out, "\\u{:04x}", c as u32).unwrap(),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

/// Standalone synthetic motion study.
pub fn render_html() -> String {
    render_html_with_music("", "").expect("synthetic preview needs no analysis")
}

/// Optional browser-playable track URL plus raw analysis JSON.
/// Analysis is embedded as an escaped string, then parsed by the viewer.
pub fn render_html_with_music(track_url: &str, sidecar_json: &str) -> Result<String, String> {
    let score = if sidecar_json.is_empty() {
        None
    } else {
        Some(hyst_compile::compile_sidecar_json(sidecar_json)?)
    };
    render_html_with_score(track_url, sidecar_json, score.as_ref())
}

/// Compile once, then export identical score to preview and inspectable JSON.
pub fn render_html_with_score(
    track_url: &str,
    sidecar_json: &str,
    score: Option<&hyst_compile::Score>,
) -> Result<String, String> {
    let mut data = String::new();
    let arm = Arm::default();
    let studies = [Study::Pulse, Study::Groove, Study::Phrase];
    data.push('[');
    for (s, study) in studies.into_iter().enumerate() {
        if s != 0 {
            data.push(',');
        }
        write!(data, "{{\"name\":\"{}\",\"frames\":[", study.name()).unwrap();
        // Include duplicate endpoint for interpolation over loop boundary.
        for i in 0..=LOOP_BEATS * SAMPLES_PER_BEAT {
            if i != 0 {
                data.push(',');
            }
            let b = i as f64 / SAMPLES_PER_BEAT as f64;
            let pose = sample(study, b);
            let points = arm.joints(pose);
            data.push('[');
            for p in &points[1..] {
                write!(data, "{:.5},{:.5},", p.x, p.y).unwrap();
            }
            for angle in pose.0 {
                write!(data, "{:.5},", angle.to_degrees()).unwrap();
            }
            write!(data, "\"{}\"]", stage(study, b)).unwrap();
        }
        data.push_str("]}");
    }
    data.push(']');
    let song = score.map(song_preview_data).transpose()?;
    let song_json = serde_json::to_string(&song)
        .map_err(|e| e.to_string())?
        .replace('<', "\\u003c")
        .replace('>', "\\u003e")
        .replace('&', "\\u0026");
    Ok(include_str!("viewer.html")
        .replace("__ARM_DATA__", &data)
        .replace("__LOOP_BEATS__", &LOOP_BEATS.to_string())
        .replace("__SAMPLES_PER_BEAT__", &SAMPLES_PER_BEAT.to_string())
        .replace("__TRACK_URL_JSON__", &json_string(track_url))
        .replace("__SIDECAR_JSON_STRING__", &json_string(sidecar_json))
        .replace("__SONG_DATA__", &song_json))
}

/// Regular 60 Hz samples plus endpoint, generated from deterministic Rust score.
pub fn song_preview_data(score: &hyst_compile::Score) -> Result<serde_json::Value, String> {
    let fps = 60.0;
    let arm = Arm::default();
    let mut frames = Vec::new();
    for i in 0..=(score.duration * fps).ceil() as usize {
        let time = (i as f64 / fps).min(score.duration);
        let angles = score.sample(time);
        let points = arm.joints(Pose(angles.map(f64::to_radians)));
        let cue = score
            .cues
            .iter()
            .find(|c| time >= c.start && time < c.end)
            .or_else(|| score.cues.last());
        let stage = cue
            .and_then(|c| {
                c.knots
                    .iter()
                    .find(|k| k.time > time)
                    .or_else(|| c.knots.last())
            })
            .map(|k| k.phase.as_str())
            .unwrap_or("hold");
        frames.push(serde_json::json!([
            points[1].x,
            points[1].y,
            points[2].x,
            points[2].y,
            points[3].x,
            points[3].y,
            angles[0],
            angles[1],
            angles[2],
            stage
        ]));
    }
    Ok(
        serde_json::json!({"duration":score.duration,"fps":fps,"frames":frames,"cues":score.cues,"sections":score.sections,"limits":score.limits}),
    )
}

/// Audit a compiled score: coverage, section structure, shared boundary poses,
/// exact arrival knots, joint ranges, analytic quintic speed/acceleration
/// extrema, holds, seek determinism and 120 Hz sampled floor clearance.
/// Returns a JSON summary; floor clearance is sampled, not a collision proof.
pub fn audit_score(score: &hyst_compile::Score) -> Result<serde_json::Value, String> {
    use std::collections::BTreeMap;
    let require = |ok: bool, message: &str| if ok { Ok(()) } else { Err(message.to_string()) };
    require(
        score.duration.is_finite() && score.duration > 0.0,
        "invalid duration",
    )?;
    require(!score.cues.is_empty(), "empty score")?;
    let mut section_end = 0.0;
    for section in &score.sections {
        require(
            section.start == section_end && section.end > section.start,
            "section gap/overlap",
        )?;
        if let Some(j) = section.repeat_of {
            let earlier = score
                .sections
                .get(j)
                .ok_or("repeat_of names missing section")?;
            require(
                earlier.end <= section.start && earlier.motif == section.motif,
                "repeat_of must name earlier section with same motif",
            )?;
        }
        section_end = section.end;
    }
    if !score.sections.is_empty() {
        require(
            (section_end - score.duration).abs() < 1e-9,
            "sections do not cover duration",
        )?;
    }
    let mut end = 0.0;
    let mut previous_pose = None;
    let mut speed = [0.0_f64; 3];
    let mut acceleration = [0.0_f64; 3];
    let mut gestures = BTreeMap::new();
    let mut anchors = 0;
    for cue in &score.cues {
        require(cue.start == end && cue.end > cue.start, "cue gap/overlap")?;
        require(cue.knots.len() >= 2, "cue needs at least two knots")?;
        if let Some(i) = cue.section {
            let section = score.sections.get(i).ok_or("cue names missing section")?;
            require(
                cue.start >= section.start && cue.end <= section.end,
                "cue crosses section boundary",
            )?;
        }
        let first = &cue.knots[0];
        let last = cue.knots.last().unwrap();
        require(
            first.time == cue.start && last.time == cue.end,
            "knot coverage mismatch",
        )?;
        if let Some(pose) = previous_pose {
            require(first.joints == pose, "position discontinuity")?;
        }
        for knot in &cue.knots {
            for (j, q) in knot.joints.iter().enumerate() {
                require(
                    q.is_finite()
                        && *q >= score.limits.min_degrees[j]
                        && *q <= score.limits.max_degrees[j],
                    "joint angle outside limits",
                )?;
            }
        }
        for pair in cue.knots.windows(2) {
            let dt = pair[1].time - pair[0].time;
            require(dt.is_finite() && dt > 0.0, "non-increasing knot times")?;
        }
        if cue.gesture == "hold" {
            require(
                cue.knots.iter().all(|k| k.joints == first.joints),
                "hold moves",
            )?;
        }
        if let Some(anchor) = cue.arrival_anchor {
            require(
                cue.knots
                    .iter()
                    .any(|k| k.phase == "arrival" && k.time == anchor),
                "arrival knot does not match declared anchor",
            )?;
            require(anchor > cue.start && anchor < cue.end, "anchor outside cue")?;
            anchors += 1;
        }
        if matches!(cue.gesture.as_str(), "coil" | "strike-low" | "flick-high") {
            require(
                cue.arrival_anchor.is_some(),
                "accent gesture missing anchor",
            )?;
        }
        *gestures.entry(cue.gesture.clone()).or_insert(0) += 1;
        end = cue.end;
        previous_pose = Some(last.joints);
    }
    require(
        (end - score.duration).abs() < 1e-9,
        "score does not cover duration",
    )?;
    // Knots may carry velocity (Hermite flow) and joints may lag, so check
    // speed/acceleration densely: 1 kHz finite differences, 2% tolerance.
    let h = 0.001;
    let mut prev = (score.sample(0.0), score.sample(h));
    for i in 2..=(score.duration / h) as usize {
        let q = score.sample(i as f64 * h);
        for j in 0..3 {
            let v = (q[j] - prev.1[j]) / h;
            let a = (q[j] - 2.0 * prev.1[j] + prev.0[j]) / (h * h);
            speed[j] = speed[j].max(v.abs());
            acceleration[j] = acceleration[j].max(a.abs());
        }
        prev = (prev.1, q);
    }
    for j in 0..3 {
        require(
            speed[j] <= score.limits.max_speed_degrees_per_second[j] * 1.02,
            "speed limit exceeded",
        )?;
        require(
            acceleration[j] <= score.limits.max_acceleration_degrees_per_second2[j] * 1.02,
            "acceleration limit exceeded",
        )?;
    }
    let mut clearance = f64::INFINITY;
    let arm = Arm::default();
    for i in 0..=(score.duration * 120.0).ceil() as usize {
        let time = (i as f64 / 120.0).min(score.duration);
        let pose = score.sample(time);
        let _unrelated_seek = score.sample(score.duration - time);
        require(pose == score.sample(time), "seek-dependent state")?;
        for point in &arm.joints(Pose(pose.map(f64::to_radians)))[1..] {
            clearance = clearance.min(point.y);
        }
    }
    require(clearance > 0.0, "arm crosses floor")?;
    let sections: Vec<_> = score
        .sections
        .iter()
        .map(|s| serde_json::json!([s.start, s.end, s.level, if s.variation == 0 { s.motif.clone() } else { format!("{}{}", s.motif, s.variation + 1) }]))
        .collect();
    Ok(serde_json::json!({
        "duration":score.duration,"cues":score.cues.len(),"sections":sections,"gestures":gestures,
        "exactArrivalAnchors":anchors,
        "maxSpeedDegreesPerSecond":speed,"maxAccelerationDegreesPerSecond2":acceleration,
        "sampledFloorClearanceCm":clearance,"clearanceSamplingHz":120,
        "continuity":"C2 quintic Hermite; positions/velocities shared across cues; joint lags applied",
        "seek":"deterministic random access"
    }))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn html_export_escapes_configuration_and_rejects_bad_analysis() {
        let html = render_html_with_music("</script><script>alert(1)</script>", "").unwrap();
        assert!(!html.contains("__SONG_DATA__"));
        assert!(!html.contains("</script><script>alert(1)"));
        assert!(html.contains("const song = null;"));
        assert!(render_html_with_music("track.m4a", "invalid json").is_err());
    }

    #[test]
    fn forward_kinematics_preserves_lengths_and_joint_hierarchy() {
        let arm = Arm::default();
        let straight = arm.joints(Pose([0.0; 3]));
        assert!((straight[3].x - 70.0).abs() < 1e-10);
        let bent = arm.joints(Pose([PI / 2.0, -PI / 2.0, 0.0]));
        assert!((bent[3].x - 38.0).abs() < 1e-10);
        assert!((bent[3].y - 32.0).abs() < 1e-10);
        for study in [Study::Pulse, Study::Groove, Study::Phrase] {
            for i in 0..1024 {
                let points = arm.joints(sample(study, i as f64 / 64.0));
                for j in 0..3 {
                    let distance =
                        (points[j + 1].x - points[j].x).hypot(points[j + 1].y - points[j].y);
                    assert!((distance - arm.lengths[j]).abs() < 1e-10);
                    assert!(points[j + 1].y > 0.0, "arm crosses floor");
                }
            }
        }
    }

    #[test]
    fn phrase_holds_and_reaches_beyond_ordinary_groove() {
        assert_eq!(sample(Study::Phrase, 14.2).0, sample(Study::Phrase, 14.8).0);
        let arm = Arm::default();
        assert!(
            arm.joints(sample(Study::Phrase, 8.0))[3].x
                > arm.joints(sample(Study::Groove, 8.0))[3].x + 15.0
        );
    }

    #[test]
    fn loop_and_gesture_joins_preserve_position_and_velocity() {
        let h = 1e-5;
        for study in [Study::Pulse, Study::Groove, Study::Phrase] {
            for b in [
                0.0, 6.0, 6.8, 7.0, 7.2, 8.0, 8.2, 10.0, 10.2, 13.0, 14.0, 15.0, 16.0,
            ] {
                let left = sample(study, b - h).0;
                let at = sample(study, b).0;
                let right = sample(study, b + h).0;
                for j in 0..3 {
                    assert!((left[j] - right[j]).abs() < 0.001);
                    let vl = (at[j] - left[j]) / h;
                    let vr = (right[j] - at[j]) / h;
                    assert!((vl - vr).abs() < 0.002, "velocity jump at {b}");
                }
            }
        }
    }
}
