//! Signal Bus + timescale tags, ported from `src/render/conductor/types.ts`.
//!
//! The Signal Bus is the cross-boundary contract between the Conductor and
//! every output. `TimescaleTag` is load-bearing for physical-output safety —
//! a servo output can refuse a signal tagged faster than it can physically
//! follow — so it must exist even before any output enforces it.

use std::collections::HashMap;

/// How fast a routable signal is allowed to move. See SIGNAL_TAGS below for
/// which tag applies to which field.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum TimescaleTag {
    Transient,
    Beat,
    Bar,
    Section,
    Continuous,
}

/// Discrete companion to `dropImpulse` — kept for the same "escape hatch"
/// reason as the TS original: the exact strength/age shape, not just a
/// re-derived edge.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct DropTrigger {
    pub active: bool,
    pub strength: f32,
    pub age: f32,
}

/// The Signal Bus: a flat, named record produced fresh every frame by the
/// Conductor. `scope`/`chroma` are pass-through (not curve/timescale-tagged);
/// `idle`/`tempo_bpm`/`tempo_confidence` are meta.
///
/// `Default` (every field zeroed / `None` / `false`) is what a consumer that only populates a subset
/// of fields — e.g. `hyst-audio`'s live feature extractor, before Layer 2's
/// build/drop/break detectors exist in Rust — starts from.
#[derive(Debug, Clone, Default)]
pub struct SignalBus {
    // continuous — alive every frame for a track's entire runtime.
    pub energy: f32,
    pub sub: f32,
    pub low: f32,
    pub mid: f32,
    pub presence: f32,
    pub air: f32,
    pub band_tilt: f32, // bipolar -1..1
    pub centroid: f32,
    pub flatness: f32,
    pub pan: f32, // bipolar -1..1
    pub familiarity: f32,
    pub novelty_local: f32,
    pub novelty_section: f32,
    pub fullness: f32,
    pub onset_density: f32,
    pub harmonic_novelty: f32,
    pub chroma_root_hue: f32,
    // sidecar-only (schema-3 stemPresence); 0.0 with no sidecar.
    pub vocal_presence: f32,
    pub drums_presence: f32,
    pub bass_presence: f32,
    pub other_presence: f32,
    pub lead_presence: f32,
    pub hue_drift: f32,

    // beat
    pub beat_phase: f32,
    pub beat_pulse: f32,

    // bar
    pub bar_phase: f32,
    pub downbeat_pulse: f32,

    // section — sparse, dramatic
    pub build_windup: f32,
    pub build_progress: f32,
    pub tension: f32,
    pub suspension: f32,

    // transient — event-derived, never routable to slow/physical outputs
    pub drop_impulse: f32,
    pub onset_impulse: f32,
    pub drop_trigger: Option<DropTrigger>,

    // pass-through
    pub scope: Option<Vec<f32>>,
    pub chroma: Option<Vec<f32>>,

    // meta
    pub idle: bool,
    pub tempo_bpm: f32,
    pub tempo_confidence: f32,
}

/// Every routable signal name, for a consumer that needs to enumerate or
/// validate against the full set (e.g. hyst-render's `.hyst` parser
/// checking a `hysteresisSignal` input's declared `SIGNAL` name) rather than
/// just test one name via `signal_tag`.
pub const ROUTABLE_SIGNAL_NAMES: &[&str] = &[
    "energy",
    "sub",
    "low",
    "mid",
    "presence",
    "air",
    "bandTilt",
    "centroid",
    "flatness",
    "pan",
    "familiarity",
    "noveltyLocal",
    "noveltySection",
    "fullness",
    "onsetDensity",
    "harmonicNovelty",
    "chromaRootHue",
    "vocalPresence",
    "drumsPresence",
    "bassPresence",
    "otherPresence",
    "leadPresence",
    "hueDrift",
    "tempoBpm",
    "tempoConfidence",
    "beatPhase",
    "beatPulse",
    "barPhase",
    "downbeatPulse",
    "buildWindup",
    "buildProgress",
    "tension",
    "suspension",
    "dropImpulse",
    "onsetImpulse",
];

/// Every *routable* scalar signal's timescale tag. `scope`/`chroma`/`idle`
/// are deliberately absent (pass-through/meta, not curve-routable).
pub fn signal_tag(name: &str) -> Option<TimescaleTag> {
    use TimescaleTag::*;
    Some(match name {
        "energy" | "sub" | "low" | "mid" | "presence" | "air" | "bandTilt" | "centroid"
        | "flatness" | "pan" | "familiarity" | "noveltyLocal" | "noveltySection" | "fullness"
        | "onsetDensity" | "harmonicNovelty" | "chromaRootHue" | "vocalPresence"
        | "drumsPresence" | "bassPresence" | "otherPresence" | "leadPresence" | "hueDrift"
        | "tempoBpm" | "tempoConfidence" => Continuous,

        "beatPhase" | "beatPulse" => Beat,
        "barPhase" | "downbeatPulse" => Bar,
        "buildWindup" | "buildProgress" | "tension" | "suspension" => Section,
        "dropImpulse" | "onsetImpulse" => Transient,

        _ => return None,
    })
}

/// A target an output exposes for routing into. `accepts_tags` is what makes
/// servo-safety structural rather than a comment someone has to remember.
#[derive(Debug, Clone)]
pub struct TargetDecl {
    pub id: String,
    pub accepts_tags: Vec<TimescaleTag>,
    pub default_value: f32,
    pub range: (f32, f32),
    /// Bypasses curve/smoothing/range/clamp entirely — the resolved value is
    /// the named bus field copied verbatim (`scope`, `chroma`, `idle`).
    /// Exempt from timescale-tag validation too.
    pub pass_through: bool,
}

#[derive(Debug, Clone)]
pub enum ResolvedTargetValue {
    Number(f32),
    Vector(Vec<f32>),
    DropTrigger(Option<DropTrigger>),
    Bool(bool),
    None,
}

pub type ResolvedTargets = HashMap<String, ResolvedTargetValue>;

/// Every output implements this. Pull-model: the frame loop resolves the bus
/// through the patch graph per output, then hands each output only its own
/// resolved targets — the output never sees the raw bus itself.
pub trait VizOutput {
    fn id(&self) -> &str;
    fn targets(&self) -> &[TargetDecl];
    fn update(&mut self, dt: f32, resolved_targets: &ResolvedTargets);
    fn dispose(&mut self);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tags_cover_every_routable_field_and_only_those() {
        for &name in ROUTABLE_SIGNAL_NAMES {
            assert!(signal_tag(name).is_some(), "{name} should have a tag");
        }
        for name in ["scope", "chroma", "idle", "dropTrigger", "nonsense"] {
            assert!(signal_tag(name).is_none(), "{name} should NOT have a tag");
        }
    }
}
