//! The `mindState` sidecar field (docs/NEXT_DECODER_THEN_BRAIN.md, D1): the only thing the
//! decoder reads, so a later brain replaces its source and never its shape. Written by
//! `scripts/emotion/mindstate.py`. Nothing in the planner reads it yet (D3). A sidecar without
//! the field is `MindState::Off`.

use serde_json::Value;

use crate::body::PARAMS;

pub const VERSION: u64 = 1;
/// Mood lanes are stored on the 0.5 s step grid of the emotion encoding.
pub const HOP_SECONDS: f64 = 0.5;

/// Raw-value range that maps to 0 and 1, fixed per source and stored in the field, never per song.
#[derive(Debug, Clone, PartialEq)]
pub struct Scale {
    pub energy: [f64; 2],
    pub power: [f64; 2],
    pub rest: Vec<[f64; 2]>,
}

/// A per-section bias of the decoded body, −1..1 per body dimension, applied after the decoder.
#[derive(Debug, Clone, PartialEq)]
pub struct Authored {
    pub start: f64,
    pub end: f64,
    pub bias: Vec<(usize, f64)>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Mood {
    pub source: String,
    pub hop_seconds: f64,
    /// Lane values 0..1, one per step.
    pub energy: Vec<f64>,
    pub power: Vec<f64>,
    /// `rest[step][component]`, 0..1.
    pub rest: Vec<Vec<f64>>,
    pub scale: Scale,
    pub authored: Vec<Authored>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum MindState {
    Off,
    On(Mood),
}

const RESERVED: [&str; 4] = ["bands", "pulse", "surprise", "neuromod"];

fn number(v: &Value, what: &str) -> Result<f64, String> {
    v.as_f64()
        .filter(|x| x.is_finite())
        .ok_or_else(|| format!("mindState: {what} is not a finite number"))
}

fn lane(v: &Value, what: &str) -> Result<Vec<f64>, String> {
    let items = v
        .as_array()
        .ok_or_else(|| format!("mindState: {what} is not an array"))?;
    items
        .iter()
        .map(|x| {
            let x = number(x, what)?;
            if (0.0..=1.0).contains(&x) {
                Ok(x)
            } else {
                Err(format!("mindState: {what} value {x} is outside 0..1"))
            }
        })
        .collect()
}

fn pair(v: &Value, what: &str) -> Result<[f64; 2], String> {
    match v.as_array().map(Vec::as_slice) {
        Some([lo, hi]) => {
            let (lo, hi) = (number(lo, what)?, number(hi, what)?);
            if hi > lo {
                Ok([lo, hi])
            } else {
                Err(format!("mindState: {what} needs lo < hi"))
            }
        }
        _ => Err(format!("mindState: {what} is not [lo, hi]")),
    }
}

fn empty(v: &Value, what: &str) -> Result<(), String> {
    match v.as_array() {
        Some(a) if a.is_empty() => Ok(()),
        _ => Err(format!(
            "mindState: {what} must be an empty array in version 1"
        )),
    }
}

fn authored(v: &Value) -> Result<Vec<Authored>, String> {
    let items = v.as_array().ok_or("mindState: authored is not an array")?;
    items
        .iter()
        .map(|s| {
            let (start, end) = (
                number(&s["start"], "authored start")?,
                number(&s["end"], "authored end")?,
            );
            if end <= start {
                return Err("mindState: authored section ends before it starts".to_string());
            }
            let body = s["body"]
                .as_object()
                .ok_or("mindState: authored body is not an object")?;
            let mut bias = Vec::new();
            for (name, value) in body {
                let dim = PARAMS.iter().position(|p| p == name).ok_or_else(|| {
                    format!("mindState: authored names unknown body dimension {name}")
                })?;
                let value = number(value, "authored bias")?;
                if !(-1.0..=1.0).contains(&value) {
                    return Err(format!("mindState: authored bias {value} is outside -1..1"));
                }
                bias.push((dim, value));
            }
            bias.sort_by_key(|b| b.0);
            Ok(Authored { start, end, bias })
        })
        .collect()
}

/// Read the `mindState` field of a parsed sidecar. A missing field is `Off`; a present but
/// malformed one is an error, so a bad file never degrades silently into `Off`.
pub fn read(sidecar: &Value) -> Result<MindState, String> {
    let Some(m) = sidecar.get("mindState") else {
        return Ok(MindState::Off);
    };
    if m["version"].as_u64() != Some(VERSION) {
        return Err(format!("mindState: version is not {VERSION}"));
    }
    let hop_seconds = number(&m["hopSeconds"], "hopSeconds")?;
    if hop_seconds != HOP_SECONDS {
        return Err(format!("mindState: hopSeconds is not {HOP_SECONDS}"));
    }
    let source = m["source"]
        .as_str()
        .filter(|s| !s.is_empty())
        .ok_or("mindState: source is missing")?
        .to_string();
    let mood = &m["mood"];
    let energy = lane(&mood["energy"], "mood.energy")?;
    let power = lane(&mood["power"], "mood.power")?;
    let rest = mood["rest"]
        .as_array()
        .ok_or("mindState: mood.rest is not an array")?
        .iter()
        .map(|row| lane(row, "mood.rest"))
        .collect::<Result<Vec<_>, _>>()?;
    if power.len() != energy.len() || rest.len() != energy.len() {
        return Err("mindState: mood lanes differ in length".into());
    }
    let k = rest.first().map_or(0, Vec::len);
    if rest.iter().any(|row| row.len() != k) {
        return Err("mindState: mood.rest rows differ in width".into());
    }
    let s = &m["scale"];
    let rest_scale = s["rest"]
        .as_array()
        .ok_or("mindState: scale.rest is not an array")?
        .iter()
        .map(|p| pair(p, "scale.rest"))
        .collect::<Result<Vec<_>, _>>()?;
    if !rest.is_empty() && rest_scale.len() != k {
        return Err("mindState: scale.rest and mood.rest differ in width".into());
    }
    let scale = Scale {
        energy: pair(&s["energy"], "scale.energy")?,
        power: pair(&s["power"], "scale.power")?,
        rest: rest_scale,
    };
    empty(&m["events"], "events")?;
    for name in RESERVED {
        empty(&m[name], name)?;
    }
    Ok(MindState::On(Mood {
        source,
        hop_seconds,
        energy,
        power,
        rest,
        scale,
        authored: authored(&m["authored"])?,
    }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn field() -> Value {
        json!({
            "version": 1, "source": "stage1-smooth8", "hopSeconds": 0.5,
            "smoothing": {"tauSeconds": 8.0, "lagSeconds": 0.0},
            "scale": {"energy": [-0.5, 1.5], "power": [0.0, 0.5], "rest": [[-3.0, 3.0], [-1.0, 2.0]]},
            "mood": {"energy": [0.0, 0.25, 1.0], "power": [0.5, 0.5, 0.75],
                     "rest": [[0.1, 0.9], [0.2, 0.8], [0.3, 0.7]]},
            "events": [], "authored": [],
            "bands": [], "pulse": [], "surprise": [], "neuromod": []
        })
    }

    fn sidecar(field: Value) -> Value {
        json!({"duration": 1.5, "mindState": field})
    }

    #[test]
    fn missing_field_is_off() {
        assert_eq!(read(&json!({"duration": 1.5})).unwrap(), MindState::Off);
    }

    #[test]
    fn parses_exact_values() {
        let MindState::On(m) = read(&sidecar(field())).unwrap() else {
            panic!("expected On");
        };
        assert_eq!(m.source, "stage1-smooth8");
        assert_eq!(m.energy, vec![0.0, 0.25, 1.0]);
        assert_eq!(m.power, vec![0.5, 0.5, 0.75]);
        assert_eq!(m.rest[1], vec![0.2, 0.8]);
        assert_eq!(m.scale.energy, [-0.5, 1.5]);
        assert_eq!(m.scale.rest, vec![[-3.0, 3.0], [-1.0, 2.0]]);
        assert!(m.authored.is_empty());
    }

    #[test]
    fn deterministic() {
        assert_eq!(
            read(&sidecar(field())).unwrap(),
            read(&sidecar(field())).unwrap()
        );
    }

    #[test]
    fn scale_is_stored_not_derived_from_the_song() {
        let mut other = field();
        other["mood"]["energy"] = json!([0.4, 0.4, 0.4]);
        let (a, b) = (
            read(&sidecar(field())).unwrap(),
            read(&sidecar(other)).unwrap(),
        );
        let (MindState::On(a), MindState::On(b)) = (a, b) else {
            panic!("expected On");
        };
        assert_ne!(a.energy, b.energy);
        assert_eq!(a.scale, b.scale);
    }

    #[test]
    fn rejects_out_of_range_lane_values() {
        for bad in [1.0001, -0.0001] {
            let mut f = field();
            f["mood"]["power"][1] = json!(bad);
            assert!(read(&sidecar(f)).unwrap_err().contains("outside 0..1"));
        }
        let mut f = field();
        f["mood"]["rest"][2][1] = json!(1.5);
        assert!(read(&sidecar(f)).is_err());
    }

    #[test]
    fn rejects_schema_errors() {
        let cases: [(&str, Value); 8] = [
            ("version", json!(2)),
            ("hopSeconds", json!(1.0)),
            ("source", json!("")),
            (
                "scale",
                json!({"energy": [1.0, 1.0], "power": [0.0, 1.0], "rest": [[0, 1], [0, 1]]}),
            ),
            (
                "scale",
                json!({"energy": [0.0, 1.0], "power": [0.0, 1.0], "rest": [[0, 1]]}),
            ),
            ("events", json!([{"time": 1.0}])),
            ("pulse", json!([1])),
            ("authored", json!([{"start": 2.0, "end": 1.0, "body": {}}])),
        ];
        for (key, value) in cases {
            let mut f = field();
            f[key] = value;
            assert!(read(&sidecar(f)).is_err(), "{key} should be rejected");
        }
    }

    #[test]
    fn rejects_lanes_of_different_length() {
        let mut f = field();
        f["mood"]["power"] = json!([0.5, 0.5]);
        assert!(read(&sidecar(f)).unwrap_err().contains("differ in length"));
        let mut f = field();
        f["mood"]["rest"][1] = json!([0.2]);
        assert!(read(&sidecar(f)).unwrap_err().contains("differ in width"));
    }

    #[test]
    fn a_present_but_broken_field_is_never_off() {
        assert!(read(&json!({"mindState": null})).is_err());
        assert!(read(&json!({"mindState": {}})).is_err());
    }

    #[test]
    fn authored_is_checked_against_the_body_dimensions() {
        let mut f = field();
        f["authored"] =
            json!([{"start": 0.0, "end": 8.0, "body": {"energy": -0.5, "height": 1.0}}]);
        let MindState::On(m) = read(&sidecar(f.clone())).unwrap() else {
            panic!("expected On");
        };
        assert_eq!(
            m.authored,
            vec![Authored {
                start: 0.0,
                end: 8.0,
                bias: vec![(1, 1.0), (13, -0.5)]
            }]
        );
        f["authored"][0]["body"]["energy"] = json!(1.01);
        assert!(read(&sidecar(f.clone())).is_err());
        f["authored"][0]["body"] = json!({"mood": 0.1});
        assert!(read(&sidecar(f))
            .unwrap_err()
            .contains("unknown body dimension"));
    }

    #[test]
    fn reads_what_the_python_writer_makes() {
        let text = include_str!("../tests/fixtures/mindstate_writer.json");
        let MindState::On(m) = read(&serde_json::from_str(text).unwrap()).unwrap() else {
            panic!("expected On");
        };
        assert_eq!(m.source, "stage1-smooth8");
        assert_eq!(
            (m.energy.len(), m.rest[0].len(), m.scale.rest.len()),
            (10, 2, 2)
        );
    }
}
