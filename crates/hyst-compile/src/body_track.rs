//! The `bodyTrack` sidecar field (docs/NEXT_DECODER_THEN_BRAIN.md, D3): for each of the planner's
//! phrases (`musicalMemory.phrases`) one 15-value body vector (0..1, `body::PARAMS` order), written
//! by `scripts/emotion/bodytrack.py` from a `mindState` and a fitted decoder map. The planner reads
//! only this field, so it does not care which encoding or map made the vectors. A sidecar without
//! the field is `None`, and `BodyMode::Layered` then compiles exactly as `Off` does.

use serde_json::Value;

use crate::body::{Body, PARAMS};

pub const VERSION: u64 = 1;

/// `Off` is version 47 with its own limits. `Layered` lets a body vector set the quality of the
/// same dance (docs/ARCHITECTURE.md §3.4, the knob table in docs/DANCE_HANDOFF.md) and holds it to
/// `body::LIMITS`; it needs one arm and a `bodyTrack`, without which it equals `Off`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum BodyMode {
    #[default]
    Off,
    Layered,
}

#[derive(Debug, Clone, PartialEq)]
pub struct PhraseBody {
    pub start: f64,
    pub end: f64,
    pub body: Body,
}

#[derive(Debug, Clone, PartialEq)]
pub struct BodyTrack {
    /// The mood source the vectors came from, e.g. `stage1-smooth8`.
    pub source: String,
    /// Which fitted map made them.
    pub map: String,
    pub phrases: Vec<PhraseBody>,
}

fn number(v: &Value, what: &str) -> Result<f64, String> {
    v.as_f64()
        .filter(|x| x.is_finite())
        .ok_or_else(|| format!("bodyTrack: {what} is not a finite number"))
}

fn text(v: &Value, what: &str) -> Result<String, String> {
    match v.as_str() {
        Some(s) if !s.is_empty() => Ok(s.to_string()),
        _ => Err(format!("bodyTrack: {what} is missing")),
    }
}

/// Read the `bodyTrack` field of a parsed sidecar. A missing field is `None`; a present but
/// malformed one is an error, so a bad file never degrades silently into `Off`.
pub fn read(sidecar: &Value) -> Result<Option<BodyTrack>, String> {
    sidecar.get("bodyTrack").map(parse).transpose()
}

/// The `bodyTrack` object itself.
pub fn parse(t: &Value) -> Result<BodyTrack, String> {
    if t["version"].as_u64() != Some(VERSION) {
        return Err(format!("bodyTrack: version is not {VERSION}"));
    }
    let dims: Vec<&str> = t["dims"]
        .as_array()
        .ok_or("bodyTrack: dims is not an array")?
        .iter()
        .map(|d| d.as_str().unwrap_or(""))
        .collect();
    if dims != PARAMS {
        return Err("bodyTrack: dims are not the body generator's PARAMS in order".into());
    }
    match t["authored"].as_array() {
        Some(a) if a.is_empty() => {}
        _ => return Err("bodyTrack: authored must be an empty array in version 1".into()),
    }
    let mut phrases: Vec<PhraseBody> = Vec::new();
    for p in t["phrases"]
        .as_array()
        .ok_or("bodyTrack: phrases is not an array")?
    {
        let (start, end) = (
            number(&p["start"], "phrase start")?,
            number(&p["end"], "phrase end")?,
        );
        if end <= start || phrases.last().is_some_and(|q| start < q.end - 1e-6) {
            return Err("bodyTrack: phrases must be in order, each ending after it starts".into());
        }
        let values = p["body"]
            .as_array()
            .ok_or("bodyTrack: body is not an array")?;
        if values.len() != PARAMS.len() {
            return Err(format!("bodyTrack: body needs {} values", PARAMS.len()));
        }
        let mut body = [0.0; 15];
        for (slot, v) in body.iter_mut().zip(values) {
            *slot = number(v, "body value")?;
            if !(0.0..=1.0).contains(slot) {
                return Err(format!("bodyTrack: body value {slot} is outside 0..1"));
            }
        }
        phrases.push(PhraseBody { start, end, body });
    }
    if phrases.is_empty() {
        return Err("bodyTrack: no phrases".into());
    }
    Ok(BodyTrack {
        source: text(&t["source"], "source")?,
        map: text(&t["map"], "map")?,
        phrases,
    })
}

fn smooth(u: f64) -> f64 {
    let u = u.clamp(0.0, 1.0);
    u * u * (3.0 - 2.0 * u)
}

impl BodyTrack {
    /// The body at time `t`: the phrase's own vector, moving to the next phrase's over the last
    /// `beat` seconds before that phrase starts (no change inside a phrase). Before the first
    /// phrase and after the last, the nearest one holds.
    pub fn at(&self, t: f64, beat: f64) -> Body {
        let next = self.phrases.partition_point(|p| p.start <= t);
        let Some(this) = next.checked_sub(1) else {
            return self.phrases[0].body;
        };
        let body = self.phrases[this].body;
        let Some(after) = self.phrases.get(next) else {
            return body;
        };
        let u = smooth((t - (after.start - beat)) / beat);
        std::array::from_fn(|k| body[k] + (after.body[k] - body[k]) * u)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn field() -> Value {
        json!({"bodyTrack": {
        "version": 1, "source": "stage1-smooth8", "map": "test",
        "dims": PARAMS, "authored": [],
        "phrases": [
            {"start": 0.0, "end": 8.0, "body": vec![0.0; 15]},
            {"start": 8.0, "end": 16.0, "body": vec![1.0; 15]},
        ]}})
    }

    #[test]
    fn missing_field_is_none() {
        assert_eq!(read(&json!({"duration": 1.0})).unwrap(), None);
    }

    #[test]
    fn parses_and_holds_inside_a_phrase() {
        let t = read(&field()).unwrap().unwrap();
        assert_eq!((t.source.as_str(), t.phrases.len()), ("stage1-smooth8", 2));
        for time in [-5.0, 0.0, 6.9, 8.0, 12.0, 100.0] {
            let b = t.at(time, 1.0);
            assert_eq!(
                b,
                if time < 7.0 { [0.0; 15] } else { [1.0; 15] },
                "t {time}"
            );
        }
    }

    #[test]
    fn changes_only_over_the_last_beat_before_a_phrase_starts() {
        let t = read(&field()).unwrap().unwrap();
        assert_eq!(t.at(7.0, 1.0), [0.0; 15]);
        let mid = t.at(7.5, 1.0)[3];
        assert!((mid - 0.5).abs() < 1e-12, "{mid}");
        let a = t.at(7.25, 1.0)[0];
        let b = t.at(7.75, 1.0)[0];
        assert!(0.0 < a && a < mid && mid < b && b < 1.0);
        assert_eq!(t.at(8.0, 1.0), [1.0; 15]);
    }

    #[test]
    fn rejects_schema_errors() {
        let mut cases: Vec<(&str, Value)> = vec![
            ("version", json!(2)),
            ("source", json!("")),
            ("map", json!(null)),
            ("dims", json!(["size"])),
            ("authored", json!([{"start": 0.0, "end": 1.0, "body": {}}])),
            ("phrases", json!([])),
            (
                "phrases",
                json!([{"start": 2.0, "end": 1.0, "body": vec![0.5; 15]}]),
            ),
            (
                "phrases",
                json!([{"start": 0.0, "end": 1.0, "body": vec![0.5; 14]}]),
            ),
            (
                "phrases",
                json!([{"start": 0.0, "end": 1.0, "body": vec![1.5; 15]}]),
            ),
            (
                "phrases",
                json!([
                    {"start": 0.0, "end": 2.0, "body": vec![0.5; 15]},
                    {"start": 1.0, "end": 3.0, "body": vec![0.5; 15]},
                ]),
            ),
        ];
        let mut swapped: Vec<&str> = PARAMS.to_vec();
        swapped.swap(0, 1);
        cases.push(("dims", json!(swapped)));
        for (key, value) in cases {
            let mut f = field();
            f["bodyTrack"][key] = value;
            assert!(read(&f).is_err(), "{key} should be rejected");
        }
        assert!(read(&json!({"bodyTrack": null})).is_err());
    }

    #[test]
    fn reads_what_the_python_writer_makes() {
        let text = include_str!("../tests/fixtures/bodytrack_writer.json");
        let t = read(&serde_json::from_str(text).unwrap()).unwrap().unwrap();
        assert_eq!((t.phrases.len(), t.source.as_str()), (2, "stage1-smooth8"));
    }
}
