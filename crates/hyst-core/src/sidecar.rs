//! The precomputed sidecar format, ported from `src/shared/sidecar.ts`.
//!
//! Schema 2/3 are real and match the TS tree exactly (verified against
//! `src/shared/sidecar.ts`, read in full before writing this). Schema 4
//! (`repeats`/`noveltyLocalEnvelope`/`noveltySectionEnvelope`/
//! `boundaryConfidence`) is ported from `SINTEZA_OFFLINE_SSM.md` §2, which is
//! an older, unverified design spec — nothing in the current tools/ pipeline
//! emits schema 4 yet. Treated here as directional: the shape is plausible
//! and additive (matches the project's own "never break the live production
//! path" schema precedent), but flag before anything downstream relies on
//! its specifics.
//!
//! Additive-only across all three versions: every schema-2 field is
//! required and unchanged; schema-3/4 fields are `Option`, so a schema-2
//! sidecar (or a schema-3 one, once schema 4 exists for real) keeps
//! deserializing.

use serde::{Deserialize, Serialize};

use crate::error::{HystError, Result};

pub const SIDECAR_SCHEMA_VERSION: u8 = 3;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize)]
#[serde(try_from = "u8", into = "u8")]
pub enum SidecarSchemaVersion {
    V2,
    V3,
    /// Directional per SINTEZA_OFFLINE_SSM.md — not yet produced by the real
    /// offline pipeline. See module doc comment.
    V4,
}

impl TryFrom<u8> for SidecarSchemaVersion {
    type Error = String;
    fn try_from(value: u8) -> std::result::Result<Self, Self::Error> {
        match value {
            2 => Ok(Self::V2),
            3 => Ok(Self::V3),
            4 => Ok(Self::V4),
            other => Err(format!("unknown sidecar schema version {other}")),
        }
    }
}

impl From<SidecarSchemaVersion> for u8 {
    fn from(value: SidecarSchemaVersion) -> u8 {
        match value {
            SidecarSchemaVersion::V2 => 2,
            SidecarSchemaVersion::V3 => 3,
            SidecarSchemaVersion::V4 => 4,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub enum SidecarSectionKind {
    Build,
    Drop,
    Break,
    Other,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct SidecarSection {
    pub start: f64,
    pub end: f64,
    pub kind: SidecarSectionKind,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub label: Option<String>,
    /// Schema-4, directional (SINTEZA_OFFLINE_SSM.md §2) — the novelty
    /// peak's own magnitude at this boundary, 0..1.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub boundary_confidence: Option<f32>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub enum SidecarEventType {
    Drop,
    BreakStart,
    BreakEnd,
    Downbeat,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct SidecarEvent {
    #[serde(rename = "type")]
    pub kind: SidecarEventType,
    pub t: f64,
    pub strength: f32,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct SidecarOnset {
    pub t: f64,
    pub strength: f32,
    /// 0 = sub, 1 = air — dominant band at this onset.
    pub tone: f32,
    /// -1..1, synthetic (see TS doc comment — no real stereo source survives
    /// mono downmix; this is a deterministic placement aid, not a
    /// measurement).
    pub pan: f32,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SidecarBandEnvelope {
    pub sub: Vec<f32>,
    pub low: Vec<f32>,
    pub mid: Vec<f32>,
    pub presence: Vec<f32>,
    pub air: Vec<f32>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SidecarStemPresence {
    pub vocals: Vec<f32>,
    pub drums: Vec<f32>,
    pub bass: Vec<f32>,
    pub other: Vec<f32>,
    pub lead_presence: Vec<f32>,
}

/// Schema-4, directional (SINTEZA_OFFLINE_SSM.md §1.5) — an off-diagonal
/// region of sustained SSM similarity: "this section is a repeat of that
/// earlier section." Nothing in the real pipeline produces this yet.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SidecarRepeat {
    pub a_start: f64,
    pub a_end: f64,
    pub b_start: f64,
    pub b_end: f64,
    pub similarity: f32,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Sidecar {
    pub schema: SidecarSchemaVersion,
    pub duration: f64,
    pub tempo: f32,
    pub beats: Vec<f64>,
    pub sections: Vec<SidecarSection>,
    pub events: Vec<SidecarEvent>,
    pub onsets: Vec<SidecarOnset>,
    /// 0..1, sampled at envelope_rate Hz.
    pub energy_envelope: Vec<f32>,
    pub band_envelope: SidecarBandEnvelope,
    pub centroid_envelope: Vec<f32>,
    pub flatness_envelope: Vec<f32>,
    pub envelope_rate: f32,
    /// schema-3, optional.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub stem_presence: Option<SidecarStemPresence>,
    /// schema-4, directional/optional — see module doc comment.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub repeats: Option<Vec<SidecarRepeat>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub novelty_local_envelope: Option<Vec<f32>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub novelty_section_envelope: Option<Vec<f32>>,
}

impl Sidecar {
    /// Parse and structurally validate, matching `isSidecar()`'s checks
    /// (schema in range, beats/onsets are arrays, bandEnvelope present) plus
    /// whatever serde's own type-checking adds for free.
    pub fn from_json_str(s: &str) -> Result<Self> {
        serde_json::from_str(s).map_err(|source| HystError::Json {
            path: "<sidecar string>".into(),
            source,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn minimal_schema2_json() -> &'static str {
        r#"{
            "schema": 2,
            "duration": 180.0,
            "tempo": 128.0,
            "beats": [0.0, 0.5, 1.0],
            "sections": [{"start": 0.0, "end": 10.0, "kind": "build"}],
            "events": [{"type": "drop", "t": 10.0, "strength": 0.9}],
            "onsets": [{"t": 0.1, "strength": 0.5, "tone": 0.2, "pan": 0.0}],
            "energyEnvelope": [0.1, 0.2],
            "bandEnvelope": {"sub": [0.1], "low": [0.1], "mid": [0.1], "presence": [0.1], "air": [0.1]},
            "centroidEnvelope": [0.5],
            "flatnessEnvelope": [0.3],
            "envelopeRate": 20.0
        }"#
    }

    #[test]
    fn schema2_round_trips() {
        let sidecar = Sidecar::from_json_str(minimal_schema2_json()).expect("parses");
        assert_eq!(sidecar.schema, SidecarSchemaVersion::V2);
        assert!(sidecar.stem_presence.is_none());
        assert!(sidecar.repeats.is_none());

        let reserialized = serde_json::to_string(&sidecar).expect("serializes");
        let reparsed = Sidecar::from_json_str(&reserialized).expect("reparses");
        assert_eq!(sidecar.beats, reparsed.beats);
        assert_eq!(sidecar.duration, reparsed.duration);
    }

    #[test]
    fn schema4_optional_fields_round_trip() {
        let mut sidecar = Sidecar::from_json_str(minimal_schema2_json()).unwrap();
        sidecar.schema = SidecarSchemaVersion::V4;
        sidecar.repeats = Some(vec![SidecarRepeat {
            a_start: 0.0,
            a_end: 8.0,
            b_start: 32.0,
            b_end: 40.0,
            similarity: 0.92,
        }]);
        sidecar.novelty_local_envelope = Some(vec![0.1, 0.2, 0.3]);
        sidecar.novelty_section_envelope = Some(vec![0.05, 0.1]);
        sidecar.sections[0].boundary_confidence = Some(0.8);

        let json = serde_json::to_string(&sidecar).unwrap();
        let reparsed = Sidecar::from_json_str(&json).unwrap();
        assert_eq!(reparsed.schema, SidecarSchemaVersion::V4);
        assert_eq!(reparsed.repeats.unwrap().len(), 1);
        assert_eq!(reparsed.sections[0].boundary_confidence, Some(0.8));
    }

    #[test]
    fn schema3_with_stem_presence_round_trips() {
        let mut sidecar = Sidecar::from_json_str(minimal_schema2_json()).unwrap();
        sidecar.schema = SidecarSchemaVersion::V3;
        sidecar.stem_presence = Some(SidecarStemPresence {
            vocals: vec![0.1],
            drums: vec![0.2],
            bass: vec![0.3],
            other: vec![0.4],
            lead_presence: vec![0.15],
        });
        let json = serde_json::to_string(&sidecar).unwrap();
        let reparsed = Sidecar::from_json_str(&json).unwrap();
        assert_eq!(reparsed.stem_presence.unwrap().vocals, vec![0.1]);
    }

    #[test]
    fn rejects_unknown_schema_version() {
        let bad = minimal_schema2_json().replacen("\"schema\": 2", "\"schema\": 99", 1);
        assert!(Sidecar::from_json_str(&bad).is_err());
    }
}
