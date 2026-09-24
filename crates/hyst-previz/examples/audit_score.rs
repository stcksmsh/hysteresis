//! Audit exported score, including exact quintic extrema and sampled clearance.
//! cargo run -p hyst-previz --example audit_score -- score.json
use hyst_compile::Score;
use hyst_previz::{Arm, Pose};
use std::{collections::BTreeMap, env, fs, io};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let path = env::args().nth(1).ok_or("usage: audit_score score.json")?;
    let score: Score = serde_json::from_str(&fs::read_to_string(path)?)?;
    let require = |ok: bool, message: &str| -> io::Result<()> {
        if ok {
            Ok(())
        } else {
            Err(io::Error::other(message))
        }
    };
    require(
        score.duration.is_finite() && score.duration > 0.0,
        "invalid duration",
    )?;
    require(!score.cues.is_empty(), "empty score")?;
    let mut end = 0.0;
    let mut previous_pose = None;
    let mut speed = [0.0_f64; 3];
    let mut acceleration = [0.0_f64; 3];
    let mut gestures = BTreeMap::new();
    let mut anchors = 0;
    for cue in &score.cues {
        require(cue.start == end && cue.end > cue.start, "cue gap/overlap")?;
        require(cue.knots.len() >= 2, "cue needs at least two knots")?;
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
            for j in 0..3 {
                let distance = (pair[1].joints[j] - pair[0].joints[j]).abs();
                speed[j] = speed[j].max(distance * 1.875 / dt);
                acceleration[j] =
                    acceleration[j].max(distance * (10.0 / 3.0_f64.sqrt()) / dt.powi(2));
                require(
                    speed[j] <= score.limits.max_speed_degrees_per_second[j] + 1e-7,
                    "speed limit exceeded",
                )?;
                require(
                    acceleration[j] <= score.limits.max_acceleration_degrees_per_second2[j] + 1e-7,
                    "acceleration limit exceeded",
                )?;
            }
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
        *gestures.entry(cue.gesture.as_str()).or_insert(0) += 1;
        end = cue.end;
        previous_pose = Some(last.joints);
    }
    require(
        (end - score.duration).abs() < 1e-9,
        "score does not cover duration",
    )?;
    let mut clearance = f64::INFINITY;
    let arm = Arm::default();
    // Bounds proven per segment above; floor clearance sampled, not a collision proof.
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
    println!(
        "{}",
        serde_json::to_string_pretty(&serde_json::json!({
        "duration":score.duration,"cues":score.cues.len(),"gestures":gestures,"exactArrivalAnchors":anchors,
            "maxSpeedDegreesPerSecond":speed,"maxAccelerationDegreesPerSecond2":acceleration,
            "sampledFloorClearanceCm":clearance,"clearanceSamplingHz":120,
            "continuity":"C2 at quintic knots; positions shared across cues",
            "seek":"deterministic random access"
        }))?
    );
    Ok(())
}
