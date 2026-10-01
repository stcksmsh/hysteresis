//! Absolute-time playback for a compiled single-arm [`hyst_compile::Score`].
//!
//! This path bypasses `VizOutput` and patchgraph: compiler already resolved every cue.  Logical
//! clock time intentionally leads audible time by configured output latency; choose [`ClockPosition`]
//! explicitly for each downstream consumer.  This validates score artifact consistency, not
//! hardware safety, calibration, torque, or collision clearance.

use hyst_audio::AudioClock;
use hyst_compile::{Cue, Score};
use serde::Serialize;

const MAX_DURATION_SECS: f64 = 21_600.0;
const QUINTIC_MAX_SPEED: f64 = 1.875;
// Same analytic extrema used by `hyst-previz`'s `audit_score`.
const QUINTIC_MAX_ACCELERATION: f64 = 5.773_502_691_896_258;
const LIMIT_TOLERANCE: f64 = 1e-7;

/// Which playback clock domain should drive score sampling.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ClockPosition {
    /// Source position. Use for outputs which need configured latency lead.
    Logical,
    /// Heard position, delayed by `AudioClock` output latency.
    Audible,
}

/// Borrowed score state at one absolute timestamp. Field names serialize as snake_case.
#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct ChoreographyFrame<'a> {
    pub time_seconds: f64,
    pub joints_degrees: [f64; 3],
    pub cue_index: usize,
    pub gesture: &'a str,
    pub phase: &'a str,
    pub energy: f32,
    pub accent: f32,
    pub arrival_anchor: Option<f64>,
}

/// Validated compiled-score sampler. Sampling is deterministic random access; no `dt` state.
pub struct ChoreographyOutput {
    score: Score,
}

impl ChoreographyOutput {
    pub fn new(score: Score) -> Result<Self, String> {
        validate_score(&score)?;
        Ok(Self { score })
    }

    pub fn duration(&self) -> f64 {
        self.score.duration
    }

    /// Samples finite absolute seconds; values outside score range clamp to its endpoints.
    /// Cue metadata is right-continuous: a shared boundary selects next cue, except final endpoint.
    pub fn sample_at(&self, time_seconds: f64) -> Result<ChoreographyFrame<'_>, String> {
        if !time_seconds.is_finite() {
            return Err("sample time must be finite".into());
        }
        let time_seconds = time_seconds.clamp(0.0, self.score.duration);
        let cue_index = if time_seconds >= self.score.duration {
            self.score.cues.len() - 1
        } else {
            self.score
                .cues
                .partition_point(|cue| cue.end <= time_seconds)
        };
        let cue = &self.score.cues[cue_index];
        let phase = cue
            .knots
            .iter()
            .find(|knot| knot.time >= time_seconds)
            .unwrap_or_else(|| cue.knots.last().expect("validated knots"));
        Ok(ChoreographyFrame {
            time_seconds,
            joints_degrees: self.score.sample(time_seconds),
            cue_index,
            gesture: &cue.gesture,
            phase: &phase.phase,
            energy: cue.energy,
            accent: cue.accent,
            arrival_anchor: cue.arrival_anchor,
        })
    }

    /// Samples selected audio clock domain. A zero-rate clock has no valid seconds domain.
    pub fn sample_clock(
        &self,
        clock: &AudioClock,
        position: ClockPosition,
    ) -> Result<ChoreographyFrame<'_>, String> {
        if clock.sample_rate() == 0 {
            return Err("audio clock sample rate must be nonzero".into());
        }
        let time = match position {
            ClockPosition::Logical => clock.logical_position_secs(),
            ClockPosition::Audible => clock.audible_position_secs(),
        };
        self.sample_at(time)
    }
}

fn validate_score(score: &Score) -> Result<(), String> {
    require(
        score.duration.is_finite() && score.duration > 0.0 && score.duration <= MAX_DURATION_SECS,
        "duration must be finite, positive, and <= 6 hours",
    )?;
    require(!score.cues.is_empty(), "score must contain cues")?;
    for joint in 0..3 {
        require(
            score.limits.min_degrees[joint].is_finite()
                && score.limits.max_degrees[joint].is_finite()
                && score.limits.min_degrees[joint] < score.limits.max_degrees[joint],
            "joint limits must be finite increasing ranges",
        )?;
        require(
            score.limits.max_speed_degrees_per_second[joint].is_finite()
                && score.limits.max_speed_degrees_per_second[joint] > 0.0
                && score.limits.max_acceleration_degrees_per_second2[joint].is_finite()
                && score.limits.max_acceleration_degrees_per_second2[joint] > 0.0,
            "speed and acceleration limits must be finite positive",
        )?;
    }

    let mut expected_start = 0.0;
    let mut previous_pose = None;
    for cue in &score.cues {
        validate_cue(score, cue, expected_start, previous_pose)?;
        expected_start = cue.end;
        previous_pose = Some(cue.knots.last().expect("validated knots").joints);
    }
    require(
        expected_start == score.duration,
        "cues must cover score duration",
    )
}

fn validate_cue(
    score: &Score,
    cue: &Cue,
    expected_start: f64,
    previous_pose: Option<[f64; 3]>,
) -> Result<(), String> {
    require(
        cue.start.is_finite() && cue.end.is_finite() && cue.end > cue.start,
        "cue range must be finite and positive",
    )?;
    require(cue.start == expected_start, "cues must be contiguous")?;
    require(
        cue.start >= 0.0 && cue.end <= score.duration,
        "cue range outside score duration",
    )?;
    require(
        cue.energy.is_finite() && cue.accent.is_finite(),
        "cue energy and accent must be finite",
    )?;
    require(!cue.gesture.is_empty(), "cue gesture must not be empty")?;
    require(cue.knots.len() >= 2, "cue needs at least two knots")?;
    require(cue.knots[0].time == cue.start, "first knot must begin cue")?;
    require(
        cue.knots.last().expect("nonempty").time == cue.end,
        "last knot must end cue",
    )?;
    if let Some(previous) = previous_pose {
        require(
            cue.knots[0].joints == previous,
            "cue boundary poses must match",
        )?;
    }
    for knot in &cue.knots {
        require(
            knot.time.is_finite() && knot.time >= cue.start && knot.time <= cue.end,
            "knot time outside cue",
        )?;
        require(!knot.phase.is_empty(), "knot phase must not be empty")?;
        for joint in 0..3 {
            require(knot.joints[joint].is_finite(), "joint angle must be finite")?;
            require(
                knot.joints[joint] >= score.limits.min_degrees[joint]
                    && knot.joints[joint] <= score.limits.max_degrees[joint],
                "joint angle outside limits",
            )?;
        }
    }
    for pair in cue.knots.windows(2) {
        let dt = pair[1].time - pair[0].time;
        require(dt.is_finite() && dt > 0.0, "knot times must increase")?;
        for joint in 0..3 {
            let distance = (pair[1].joints[joint] - pair[0].joints[joint]).abs();
            require(
                distance * QUINTIC_MAX_SPEED / dt
                    <= score.limits.max_speed_degrees_per_second[joint] + LIMIT_TOLERANCE,
                "quintic speed limit exceeded",
            )?;
            require(
                distance * QUINTIC_MAX_ACCELERATION / dt.powi(2)
                    <= score.limits.max_acceleration_degrees_per_second2[joint] + LIMIT_TOLERANCE,
                "quintic acceleration limit exceeded",
            )?;
        }
    }
    if cue.gesture == "hold" {
        require(
            cue.knots
                .iter()
                .all(|knot| knot.joints == cue.knots[0].joints),
            "hold cue must remain still",
        )?;
    }
    if let Some(anchor) = cue.arrival_anchor {
        require(
            anchor.is_finite() && anchor > cue.start && anchor < cue.end,
            "arrival anchor must be inside cue",
        )?;
        require(
            cue.knots
                .iter()
                .any(|knot| knot.phase == "arrival" && knot.time == anchor),
            "arrival anchor must match arrival knot",
        )?;
    }
    if matches!(cue.gesture.as_str(), "coil" | "strike-low" | "flick-high") {
        require(
            cue.arrival_anchor.is_some(),
            "accent gesture requires arrival anchor",
        )?;
    }
    Ok(())
}

fn require(condition: bool, message: &'static str) -> Result<(), String> {
    condition.then_some(()).ok_or_else(|| message.into())
}

#[cfg(test)]
mod tests {
    use super::*;
    use hyst_compile::{JointLimits, Knot};

    fn score() -> Score {
        let limits = JointLimits::default();
        let a = [105.0, -65.0, -20.0];
        let b = [110.0, -60.0, -15.0];
        Score {
            duration: 4.0,
            limits,
            cues: vec![
                Cue {
                    start: 0.0,
                    end: 2.0,
                    gesture: "sway".into(),
                    reason: "fixture".into(),
                    energy: 0.2,
                    accent: 0.1,
                    arrival_anchor: None,
                    knots: vec![
                        Knot {
                            time: 0.0,
                            phase: "start".into(),
                            joints: a,
                        },
                        Knot {
                            time: 2.0,
                            phase: "recovery".into(),
                            joints: b,
                        },
                    ],
                },
                Cue {
                    start: 2.0,
                    end: 4.0,
                    gesture: "hold".into(),
                    reason: "fixture".into(),
                    energy: 0.0,
                    accent: 0.0,
                    arrival_anchor: None,
                    knots: vec![
                        Knot {
                            time: 2.0,
                            phase: "start".into(),
                            joints: b,
                        },
                        Knot {
                            time: 4.0,
                            phase: "recovery".into(),
                            joints: b,
                        },
                    ],
                },
            ],
        }
    }

    fn anchored_score() -> Score {
        let mut score = score();
        score.cues[0].gesture = "strike-low".into();
        score.cues[0].arrival_anchor = Some(1.0);
        score.cues[0].knots.insert(
            1,
            Knot {
                time: 1.0,
                phase: "arrival".into(),
                joints: [110.0, -60.0, -15.0],
            },
        );
        score
    }

    #[test]
    fn deterministic_seek_clamp_and_right_continuous_metadata() {
        let output = ChoreographyOutput::new(score()).unwrap();
        assert_eq!(output.sample_at(-4.0).unwrap().time_seconds, 0.0);
        assert_eq!(output.sample_at(99.0).unwrap().time_seconds, 4.0);
        let join = output.sample_at(2.0).unwrap();
        assert_eq!(
            (join.cue_index, join.gesture, join.phase),
            (1, "hold", "start")
        );
        let first = output.sample_at(1.37).unwrap();
        let unrelated = output.sample_at(3.8).unwrap();
        let again = output.sample_at(1.37).unwrap();
        assert_eq!(first, again);
        assert_eq!(unrelated.gesture, "hold");
        assert!(output.sample_at(f64::NAN).is_err());
    }

    #[test]
    fn clock_sampling_has_no_frame_increment_or_pause_drift() {
        let output = ChoreographyOutput::new(score()).unwrap();
        let clock = AudioClock::new(1_000);
        clock.advance(1_234);
        let one = output.sample_clock(&clock, ClockPosition::Logical).unwrap();
        let two = output.sample_clock(&clock, ClockPosition::Logical).unwrap();
        assert_eq!(one, two); // paused: no advance, no motion.
        clock.advance(1);
        let three = output.sample_clock(&clock, ClockPosition::Logical).unwrap();
        assert_eq!(
            three.joints_degrees,
            output.sample_at(1.235).unwrap().joints_degrees
        );

        let once = AudioClock::new(1_000);
        once.advance(1_234);
        let irregular = AudioClock::new(1_000);
        for frames in [7, 91, 1, 400, 735] {
            irregular.advance(frames);
        }
        assert_eq!(
            output.sample_clock(&once, ClockPosition::Logical).unwrap(),
            output
                .sample_clock(&irregular, ClockPosition::Logical)
                .unwrap()
        );
    }

    #[test]
    fn clock_domain_makes_latency_choice_visible() {
        let output = ChoreographyOutput::new(score()).unwrap();
        let clock = AudioClock::new(1_000);
        clock.set_output_latency_frames(250);
        clock.advance(1_500);
        assert_eq!(
            output
                .sample_clock(&clock, ClockPosition::Logical)
                .unwrap()
                .time_seconds,
            1.5
        );
        assert_eq!(
            output
                .sample_clock(&clock, ClockPosition::Audible)
                .unwrap()
                .time_seconds,
            1.25
        );
        assert!(output
            .sample_clock(&AudioClock::new(0), ClockPosition::Logical)
            .is_err());
    }

    #[test]
    fn malformed_scores_rejected() {
        let mut invalid = score();
        invalid.limits.max_speed_degrees_per_second[0] = f64::NAN;
        assert!(ChoreographyOutput::new(invalid).is_err());
        let mut invalid = score();
        invalid.cues[1].knots[1].joints[0] += 1.0;
        assert!(ChoreographyOutput::new(invalid).is_err());
        let mut invalid = score();
        invalid.duration = 0.4;
        invalid.cues[0].end = 0.2;
        invalid.cues[0].knots[1].time = 0.2;
        invalid.cues[1].start = 0.2;
        invalid.cues[1].end = 0.4;
        invalid.cues[1].knots[0].time = 0.2;
        invalid.cues[1].knots[1].time = 0.4;
        invalid.cues[0].knots[1].joints[0] = 140.0;
        invalid.cues[1].knots[0].joints[0] = 140.0;
        invalid.cues[1].knots[1].joints[0] = 140.0;
        assert!(ChoreographyOutput::new(invalid).is_err()); // quintic acceleration limit

        let mut invalid = score();
        invalid.cues[1].end -= 5e-8;
        invalid.cues[1].knots[1].time -= 5e-8;
        assert!(ChoreographyOutput::new(invalid).is_err()); // no gap accepted near final endpoint

        let mut invalid = anchored_score();
        invalid.cues[0].arrival_anchor = Some(1.1);
        assert!(ChoreographyOutput::new(invalid).is_err());
    }

    #[test]
    fn arrival_anchor_samples_exact_arrival_pose_and_phase() {
        let output = ChoreographyOutput::new(anchored_score()).unwrap();
        let frame = output.sample_at(1.0).unwrap();
        assert_eq!(frame.phase, "arrival");
        assert_eq!(frame.joints_degrees, [110.0, -60.0, -15.0]);
        assert_eq!(frame.arrival_anchor, Some(1.0));
    }
}
