//! The `mindState` sidecar field (docs/NEXT_DECODER_THEN_BRAIN.md, D1): the only thing the
//! decoder reads, so a later brain replaces its source and never its shape. Written by
//! `scripts/emotion/mindstate.py`. Nothing in the planner reads it yet (D3). A sidecar without
//! the field is `MindState::Off`.

use std::collections::BTreeMap;

use serde_json::Value;

use crate::body::PARAMS;

pub const VERSION: u64 = 1;
/// Version 2: the reserved `bands` / `surprise` / `neuromod` arrays carry the B7 lanes (`scripts/brain/brain_mindstate.py`, `to_v2`).
pub const VERSION_2: u64 = 2;
/// B7 lanes are stored on 0.1 s bins (`brainHopSeconds`), bin k stamped 0.1 (k + 1) s; `None` = undefined there.
pub const BRAIN_HOP_SECONDS: f64 = 0.1;
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

/// Named lanes of one reserved group, all the same length. Mechanism names only.
pub type Lanes = BTreeMap<String, Vec<Option<f64>>>;

/// The B7 lanes of a version-2 field: `bands` (band power, phase order parameter, self-similarity),
/// `surprise` (prediction error per layer), `neuromod` (arousal signal, gain, exponent).
#[derive(Debug, Clone, PartialEq)]
pub struct Brain {
    pub hop_seconds: f64,
    pub bands: Lanes,
    pub surprise: Lanes,
    pub neuromod: Lanes,
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
    /// `None` for version 1.
    pub brain: Option<Box<Brain>>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum MindState {
    Off,
    On(Mood),
}

const RESERVED: [&str; 4] = ["bands", "pulse", "surprise", "neuromod"];
const BRAIN_GROUPS: [&str; 3] = ["bands", "surprise", "neuromod"];

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

fn lanes(v: &Value, what: &str, len: &mut Option<usize>) -> Result<Lanes, String> {
    let obj = v
        .as_object()
        .ok_or_else(|| format!("mindState: {what} is not an object in version 2"))?;
    let mut out = Lanes::new();
    for (name, lane) in obj {
        let items = lane
            .as_array()
            .ok_or_else(|| format!("mindState: {what}.{name} is not an array"))?;
        let lane = items
            .iter()
            .map(|x| {
                if x.is_null() {
                    Ok(None)
                } else {
                    number(x, &format!("{what}.{name}")).map(Some)
                }
            })
            .collect::<Result<Vec<_>, _>>()?;
        if *len.get_or_insert(lane.len()) != lane.len() {
            return Err(format!("mindState: {what}.{name} differs in length"));
        }
        out.insert(name.clone(), lane);
    }
    Ok(out)
}

fn brain(m: &Value) -> Result<Brain, String> {
    let hop_seconds = number(&m["brainHopSeconds"], "brainHopSeconds")?;
    if hop_seconds != BRAIN_HOP_SECONDS {
        return Err(format!(
            "mindState: brainHopSeconds is not {BRAIN_HOP_SECONDS}"
        ));
    }
    let mut len = None;
    let [bands, surprise, neuromod] = BRAIN_GROUPS.map(|g| lanes(&m[g], g, &mut len));
    Ok(Brain {
        hop_seconds,
        bands: bands?,
        surprise: surprise?,
        neuromod: neuromod?,
    })
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
    let version = m["version"]
        .as_u64()
        .filter(|v| [VERSION, VERSION_2].contains(v));
    let Some(version) = version else {
        return Err(format!(
            "mindState: version is not {VERSION} or {VERSION_2}"
        ));
    };
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
    empty(&m["pulse"], "pulse")?;
    let brain = if version == VERSION_2 {
        Some(Box::new(brain(m)?))
    } else {
        for name in RESERVED {
            empty(&m[name], name)?;
        }
        None
    };
    Ok(MindState::On(Mood {
        source,
        hop_seconds,
        energy,
        power,
        rest,
        scale,
        authored: authored(&m["authored"])?,
        brain,
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
            ("version", json!(3)),
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
    fn a_brain_object_beside_the_reserved_arrays_changes_nothing() {
        // scripts/brain/brain_mindstate.py adds `brain` inside mindState; version 1 ignores it
        let mut f = field();
        f["brain"] =
            json!({"source": "b7-epoch6", "hopSeconds": 0.1, "smoothedSurprisal": [0.1, null]});
        assert_eq!(read(&sidecar(f)).unwrap(), read(&sidecar(field())).unwrap());
    }

    fn field_v2() -> Value {
        let mut f = field();
        f["version"] = json!(2);
        f["brainHopSeconds"] = json!(0.1);
        f["bands"] = json!({"power.L1": [0.5, null, 0.25], "coherence.L1": [null, null, 0.75]});
        f["surprise"] = json!({"L1": [null, 1.5, 2.0], "total": [null, 1.5, 2.5]});
        f["neuromod"] = json!({"arousalSignal": [0.0, 0.5, 1.0]});
        f
    }

    #[test]
    fn version_2_reads_the_lanes_and_keeps_mood() {
        let (MindState::On(v1), MindState::On(v2)) = (
            read(&sidecar(field())).unwrap(),
            read(&sidecar(field_v2())).unwrap(),
        ) else {
            panic!("expected On");
        };
        assert_eq!(v1.brain, None);
        assert_eq!(
            (&v2.energy, &v2.power, &v2.rest, &v2.scale),
            (&v1.energy, &v1.power, &v1.rest, &v1.scale)
        );
        let b = v2.brain.unwrap();
        assert_eq!(b.hop_seconds, 0.1);
        assert_eq!(b.bands["power.L1"], vec![Some(0.5), None, Some(0.25)]);
        assert_eq!(b.surprise["total"], vec![None, Some(1.5), Some(2.5)]);
        assert_eq!(
            b.neuromod["arousalSignal"],
            vec![Some(0.0), Some(0.5), Some(1.0)]
        );
    }

    #[test]
    fn version_2_rejects_bad_lanes() {
        let cases: [(&str, Value); 6] = [
            ("brainHopSeconds", json!(0.5)),
            ("bands", json!([])),
            ("surprise", json!({"L1": [0.0, "x", 1.0]})),
            ("neuromod", json!({"a": [0.0, 1.0]})),
            ("bands", json!({"a": 3})),
            ("pulse", json!([1])),
        ];
        for (key, value) in cases {
            let mut f = field_v2();
            f[key] = value;
            assert!(read(&sidecar(f)).is_err(), "{key} should be rejected");
        }
        let mut f = field_v2();
        f.as_object_mut().unwrap().remove("brainHopSeconds");
        assert!(read(&sidecar(f)).is_err());
    }

    #[test]
    fn version_1_still_wants_the_reserved_arrays_empty() {
        let mut f = field();
        f["surprise"] = json!({"L1": [0.0]});
        assert!(read(&sidecar(f)).is_err());
    }

    #[test]
    fn reads_what_the_python_writer_makes_in_version_2() {
        let text = include_str!("../tests/fixtures/mindstate_v2_writer.json");
        let MindState::On(m) = read(&serde_json::from_str(text).unwrap()).unwrap() else {
            panic!("expected On");
        };
        let b = m.brain.unwrap();
        assert_eq!(
            (b.bands.len(), b.surprise.len(), b.neuromod.len()),
            (9, 8, 9)
        );
        assert_eq!(b.bands["coherence.L1"][8], None);
        assert!(b.bands["coherence.L1"][9].is_some());
        assert_eq!(m.energy.len(), 4);
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
