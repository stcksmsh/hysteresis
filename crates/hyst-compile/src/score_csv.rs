//! Step H, the builder's part (docs/NEXT_DECODER_THEN_BRAIN.md §5): one arm's joint angles as a CSV
//! for a person to play on real servos, and a checker that refuses a file that breaks the Layered
//! limits. Nothing here sends anything anywhere.
//!
//! Export: the score is sampled with `EnsembleScore::sample`, the sampler the previz uses, at `hz`
//! from 0 while the time is within the score.
//!
//! Check, the same for every file, no filtering: speed is the absolute difference of two
//! neighbouring rows times `hz`, acceleration the absolute second difference times `hz^2`, each
//! per joint against `body::LIMITS`; the hand point is the forward kinematics of the header's rig,
//! its speed and jolt (difference of neighbouring speeds times `hz`) are taken the same way against
//! `HAND_MPS` and `JOLT_MPS2`; every row's joints must lie in the rig's position limits; the floor
//! rule is `body::measure`'s (points 1 to 4 clear it by `FLOOR_M`, the hand by `FLOOR_M + DISC_M`).
//! Also refused: a non-finite cell, a row of the wrong width, a time that is not `1/hz` after the
//! one before (a gap, a repeat or going back), a wrong column header or a missing header line.

use crate::body::{DISC_M, FLOOR_M, HAND_MPS, JOINTS, JOLT_MPS2, LIMITS};
use crate::ensemble::{forward_kinematics, EnsembleScore, Placement, Rig};

pub const COLUMNS: &str = "time_s,base_yaw,shoulder,elbow,wrist_bend,wrist_roll";
/// Most breaches the checker names.
pub const SHOWN: usize = 10;

/// What the header says about the file beyond what the checker needs.
pub struct Meta<'a> {
    pub source_score: &'a str,
    pub mode: &'a str,
    pub body_source: &'a str,
}

/// The file's text for the first arm of `score`.
pub fn export(score: &EnsembleScore, hz: f64, meta: &Meta) -> Result<String, String> {
    if !(hz.is_finite() && hz > 0.0) || score.tracks.is_empty() || score.rig.channels.len() != 5 {
        return Err("score-csv needs hz > 0 and a five-axis score with an arm".into());
    }
    let mut out =
        String::from("# hyst score-csv v1; angles in degrees, time in audio seconds from 0\n");
    out += &format!(
        "# source_score: {}\n# mode: {}\n# body_source: {}\n# hz: {hz}\n",
        meta.source_score, meta.mode, meta.body_source
    );
    out += "# limits_used (speed deg/s, accel deg/s2):";
    for (name, (v, a)) in JOINTS.iter().zip(LIMITS) {
        out += &format!(" {name} {v} {a};");
    }
    out += &format!("\n# limits_used hand: speed {HAND_MPS} m/s, jolt {JOLT_MPS2} m/s2, floor margin {FLOOR_M} m, hand disc {DISC_M} m\n");
    out += &format!(
        "# rig_json: {}\n",
        serde_json::to_string(&score.rig).map_err(|e| e.to_string())?
    );
    out += &format!(
        "# placement_json: {}\n{COLUMNS}\n",
        serde_json::to_string(&score.placements[0]).map_err(|e| e.to_string())?
    );
    let rows = (score.duration * hz + 1e-9).floor() as usize;
    for i in 0..=rows {
        let t = i as f64 / hz;
        let q = &score.sample(t)?.agents[0].joints_degrees;
        out += &format!("{t:.6}");
        for v in q {
            out += &format!(",{v:.6}");
        }
        out.push('\n');
    }
    Ok(out)
}

/// One refusal: where, what, the value and the limit.
#[derive(Debug, Clone, PartialEq)]
pub struct Breach {
    pub time: f64,
    pub what: String,
    pub value: f64,
    pub limit: f64,
}

impl std::fmt::Display for Breach {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "t = {:.3} s: {} {:.3} against limit {:.3}",
            self.time, self.what, self.value, self.limit
        )
    }
}

/// The result of checking a file: a format error, or the breaches in time order (empty: accepted).
pub fn check(text: &str) -> Result<Vec<Breach>, String> {
    let (mut hz, mut rig, mut placement, mut header_done) = (None, None, None, false);
    let mut rows: Vec<(f64, [f64; 5])> = Vec::new();
    let mut breaches: Vec<Breach> = Vec::new();
    for (n, line) in text.lines().enumerate() {
        let n = n + 1;
        if let Some(rest) = line.strip_prefix('#') {
            let rest = rest.trim();
            if let Some(v) = rest.strip_prefix("hz:") {
                hz = Some(
                    v.trim()
                        .parse::<f64>()
                        .map_err(|_| format!("line {n}: bad hz"))?,
                );
            } else if let Some(v) = rest.strip_prefix("rig_json:") {
                rig = Some(
                    serde_json::from_str::<Rig>(v.trim())
                        .map_err(|e| format!("line {n}: bad rig: {e}"))?,
                );
            } else if let Some(v) = rest.strip_prefix("placement_json:") {
                placement = Some(
                    serde_json::from_str::<Placement>(v.trim())
                        .map_err(|e| format!("line {n}: bad placement: {e}"))?,
                );
            }
            continue;
        }
        if !header_done {
            if line != COLUMNS {
                return Err(format!("line {n}: expected the column header {COLUMNS}"));
            }
            header_done = true;
            continue;
        }
        let cells: Vec<&str> = line.split(',').collect();
        if cells.len() != 6 {
            return Err(format!("line {n}: {} cells, expected 6", cells.len()));
        }
        let mut v = [0.0; 6];
        for (slot, cell) in v.iter_mut().zip(&cells) {
            *slot = cell
                .trim()
                .parse::<f64>()
                .map_err(|_| format!("line {n}: '{cell}' is not a number"))?;
            if !slot.is_finite() {
                return Err(format!("line {n}: non-finite value '{cell}'"));
            }
        }
        rows.push((v[0], [v[1], v[2], v[3], v[4], v[5]]));
    }
    let (hz, rig, placement) = (
        hz.ok_or("missing '# hz:' header line")?,
        rig.ok_or("missing '# rig_json:' header line")?,
        placement.ok_or("missing '# placement_json:' header line")?,
    );
    if !(hz.is_finite() && hz > 0.0) || rig.channels.len() != 5 || rows.len() < 3 {
        return Err("hz must be > 0, the rig five-axis, and the file at least 3 rows".into());
    }
    let mut add = |time: f64, what: String, value: f64, limit: f64| {
        breaches.push(Breach {
            time,
            what,
            value,
            limit,
        })
    };
    if rows[0].0.abs() > 1e-9 {
        add(rows[0].0, "first time is not 0".into(), rows[0].0, 0.0);
    }
    for w in rows.windows(2) {
        let dt = w[1].0 - w[0].0;
        if (dt - 1.0 / hz).abs() > 1e-5 {
            let what = if dt <= 0.0 {
                "time does not increase, step"
            } else {
                "time step (gap or repeat)"
            };
            add(w[1].0, what.into(), dt, 1.0 / hz);
        }
    }
    let q = |i: usize| rows[i].1;
    for (i, (t, joints)) in rows.iter().enumerate() {
        for (j, c) in rig.channels.iter().enumerate() {
            if joints[j] < c.min_degrees || joints[j] > c.max_degrees {
                let limit = if joints[j] < c.min_degrees {
                    c.min_degrees
                } else {
                    c.max_degrees
                };
                add(*t, format!("{} position", JOINTS[j]), joints[j], limit);
            }
        }
        if i + 1 < rows.len() {
            for (j, (v_lim, _)) in LIMITS.iter().enumerate() {
                let v = (q(i + 1)[j] - q(i)[j]).abs() * hz;
                if v > *v_lim {
                    add(*t, format!("{} speed", JOINTS[j]), v, *v_lim);
                }
            }
        }
        if i > 0 && i + 1 < rows.len() {
            for (j, (_, a_lim)) in LIMITS.iter().enumerate() {
                let a = (q(i + 1)[j] - 2.0 * q(i)[j] + q(i - 1)[j]).abs() * hz * hz;
                if a > *a_lim {
                    add(*t, format!("{} acceleration", JOINTS[j]), a, *a_lim);
                }
            }
        }
    }
    let mut points: Vec<[[f64; 3]; 6]> = Vec::with_capacity(rows.len());
    for (t, joints) in &rows {
        let p =
            forward_kinematics(&rig, &placement, joints).map_err(|e| format!("t = {t:.3}: {e}"))?;
        let p: [[f64; 3]; 6] = p
            .try_into()
            .map_err(|_| "rig does not give six points".to_string())?;
        let ends = p[1..5].iter().map(|p| p[2]).fold(f64::MAX, f64::min) - FLOOR_M;
        let margin = ends.min(p[5][2] - FLOOR_M - DISC_M);
        if margin < 0.0 {
            add(*t, "floor margin (m)".into(), margin, 0.0);
        }
        points.push(p);
    }
    let speed: Vec<f64> = points
        .windows(2)
        .map(|w| {
            (0..3)
                .map(|k| (w[1][5][k] - w[0][5][k]).powi(2))
                .sum::<f64>()
                .sqrt()
                * hz
        })
        .collect();
    for (i, v) in speed.iter().enumerate() {
        if *v > HAND_MPS {
            add(rows[i].0, "hand speed (m/s)".into(), *v, HAND_MPS);
        }
        if i > 0 && (v - speed[i - 1]).abs() * hz > JOLT_MPS2 {
            add(
                rows[i].0,
                "hand jolt (m/s2)".into(),
                (v - speed[i - 1]).abs() * hz,
                JOLT_MPS2,
            );
        }
    }
    breaches.sort_by(|a, b| a.time.total_cmp(&b.time));
    Ok(breaches)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn meta() -> Meta<'static> {
        Meta {
            source_score: "test",
            mode: "layered",
            body_source: "none",
        }
    }

    fn clip_csv() -> String {
        let (_, clip) = crate::body::feasible(&[0.5; 15], 1).expect("feasible clip");
        export(&clip, 50.0, &meta()).unwrap()
    }

    /// Row `i` (0 is the first data row) of the file as cells.
    fn edit(text: &str, row: usize, f: impl Fn(&mut Vec<String>)) -> String {
        let mut seen = 0;
        text.lines()
            .map(|l| {
                if l.starts_with('#') || l == COLUMNS {
                    return l.to_string();
                }
                seen += 1;
                if seen - 1 != row {
                    return l.to_string();
                }
                let mut cells: Vec<String> = l.split(',').map(String::from).collect();
                f(&mut cells);
                cells.join(",")
            })
            .collect::<Vec<_>>()
            .join("\n")
            + "\n"
    }

    #[test]
    fn a_feasible_clip_round_trips_and_is_accepted() {
        let text = clip_csv();
        assert!(text.starts_with("# hyst score-csv v1"));
        assert!(text.contains("# mode: layered") && text.contains("# rig_json: {"));
        assert_eq!(check(&text).unwrap(), vec![]);
        let rows = text.lines().filter(|l| !l.starts_with('#')).count() - 1;
        assert_eq!(rows, 8 * 50 + 1);
    }

    #[test]
    fn rows_are_the_previz_sampler() {
        let (_, clip) = crate::body::feasible(&[0.5; 15], 1).unwrap();
        let text = export(&clip, 50.0, &meta()).unwrap();
        let row = text
            .lines()
            .filter(|l| !l.starts_with('#'))
            .nth(1 + 133)
            .unwrap();
        let cells: Vec<f64> = row.split(',').map(|c| c.parse().unwrap()).collect();
        let want = clip.sample(cells[0]).unwrap().agents[0]
            .joints_degrees
            .clone();
        for j in 0..5 {
            assert!((cells[1 + j] - want[j]).abs() < 1e-6);
        }
    }

    #[test]
    fn an_over_speed_sample_is_named() {
        let text = edit(&clip_csv(), 100, |c| {
            c[1] = format!("{}", c[1].parse::<f64>().unwrap() + 40.0)
        });
        let b = check(&text).unwrap();
        assert!(
            b.iter()
                .any(|b| b.what == "base_yaw speed" && b.value > 120.0 && b.limit == 120.0),
            "{b:?}"
        );
    }

    #[test]
    fn an_over_acceleration_sample_is_named_without_a_speed_breach() {
        // 2 degrees of roll for one sample: 100 deg/s (limit 250) but 10,000 deg/s2 (limit 3,000).
        let text = edit(&clip_csv(), 100, |c| {
            c[5] = format!("{}", c[5].parse::<f64>().unwrap() + 2.0)
        });
        let b = check(&text).unwrap();
        assert!(
            b.iter()
                .any(|b| b.what == "wrist_roll acceleration" && b.limit == 3000.0),
            "{b:?}"
        );
        assert!(!b.iter().any(|b| b.what == "wrist_roll speed"), "{b:?}");
    }

    #[test]
    fn a_nan_a_gap_and_a_repeat_are_refused() {
        let nan = edit(&clip_csv(), 10, |c| c[2] = "NaN".into());
        assert!(check(&nan).unwrap_err().contains("non-finite"));
        let text = clip_csv();
        let mut kept: Vec<&str> = text.lines().collect();
        let first_row = kept.iter().position(|l| *l == COLUMNS).unwrap() + 1;
        kept.remove(first_row + 50);
        let gap = kept.join("\n") + "\n";
        let b = check(&gap).unwrap();
        assert!(
            b.iter()
                .any(|b| b.what.contains("time step") && (b.time - 1.02).abs() < 1e-6),
            "{b:?}"
        );
        let repeat = edit(&text, 20, |c| c[0] = "0.380000".into());
        let b = check(&repeat).unwrap();
        assert!(
            b.iter()
                .any(|b| b.what.contains("time does not increase") || b.what.contains("time step")),
            "{b:?}"
        );
    }

    #[test]
    fn position_floor_hand_and_header_errors_are_refused() {
        let text = clip_csv();
        // The base and the roll turn without end; the shoulder stops at 110.
        let b = check(&edit(&text, 5, |c| c[2] = "150".into())).unwrap();
        assert!(
            b.iter()
                .any(|b| b.what == "shoulder position" && b.limit == 110.0),
            "{b:?}"
        );
        // The shoulder dived with the elbow bent: below the floor.
        let down = edit(&text, 30, |c| {
            c[2] = "-60".into();
            c[3] = "80".into();
        });
        assert!(check(&down)
            .unwrap()
            .iter()
            .any(|b| b.what.starts_with("floor") || b.what.contains("speed")));
        assert!(check(&text.replace("# hz: 50\n", ""))
            .unwrap_err()
            .contains("hz"));
        assert!(check(&text.replace(COLUMNS, "t,a,b,c,d,e"))
            .unwrap_err()
            .contains("column header"));
    }
}
