//! The `Move` primitive (`SINTEZA_CHOREOGRAPHY.md` §2): agent-local,
//! count-agnostic. Defined for exactly one agent in normalized local space
//! — no knowledge of how many agents exist. Formations (`crate::formation`)
//! are the only layer that knows agent count.

use std::collections::BTreeMap;

use crate::curve::Curve;
use crate::effort::Effort;

/// A DOF channel role. Common roles are named variants (typo-proof,
/// exhaustive-matchable); `Custom` is the escape hatch for rig-specific or
/// future channels so this enum never needs editing just to add one.
/// Chosen over a bare `String` because the common-path roles (elevation,
/// rotation, light channels) recur across every move and deserve real
/// identifiers; chosen over a closed enum because a rig-specific channel
/// (e.g. a second LED ring) must not require a crate change to express.
#[derive(Debug, Clone, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum ChannelRole {
    PrimaryElevation,
    SecondaryRotation,
    AccentLightIntensity,
    AccentLightHue,
    Custom(String),
}

/// A per-channel normalized value (`0.0..=1.0`), e.g. a required starting
/// or ending pose.
pub type Pose = BTreeMap<ChannelRole, f32>;

/// Outer duration for a move — the curve itself knows nothing about how
/// long it takes (§2's "duration as a separate outer parameter").
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Duration {
    Seconds(f32),
    /// Tempo-locked: resolved to seconds via `seconds_per_beat` at
    /// scheduling time (see `crate::formation::TimingAnchor`).
    Beats(f32),
}

impl Duration {
    pub fn to_seconds(&self, seconds_per_beat: f64) -> f64 {
        match self {
            Duration::Seconds(s) => *s as f64,
            Duration::Beats(b) => *b as f64 * seconds_per_beat,
        }
    }
}

/// Whether a move needs a specific starting/ending pose or blends from/to
/// wherever the agent currently is (§2.2).
#[derive(Debug, Clone, PartialEq)]
pub enum PoseRequirement {
    Required(Pose),
    Agnostic,
}

/// Timescale/role tag (§2.2).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TimescaleRole {
    /// Bounded, keyed to a specific event.
    Hit,
    /// Sustained, looping-but-varied filler.
    Groove,
    /// Spans toward a known future event.
    Windup,
    /// Deliberate stillness — a first-class choice, not an absence of movement.
    Hold,
}

/// Workflow bookkeeping (§2.2) — parallels the taste-gate record used
/// elsewhere in the project.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Provenance {
    Authored,
    Generated,
    GeneratedThenEdited,
}

/// One move: agent-local, count-agnostic (see module docs).
#[derive(Debug, Clone, PartialEq)]
pub struct Move {
    /// Every channel is one of the curves in `crate::curve`, over local
    /// normalized time.
    pub channels: BTreeMap<ChannelRole, Curve>,
    pub duration: Duration,
    pub entry_pose: PoseRequirement,
    pub exit_pose: PoseRequirement,
    /// Future-arrival anchor (§2.2): if set, this move's *end* is pinned to
    /// this absolute timestamp (seconds) rather than a fixed offset from
    /// now — the literal anticipation mechanic, real data on the struct.
    /// Start time is `arrival_anchor - duration_secs`. Back-calculating the
    /// actual start time from this is a scheduling concern (R7), not this
    /// crate's job — this field only carries the data.
    pub arrival_anchor: Option<f64>,
    pub role: TimescaleRole,
    /// Time/Weight/Space only — see `crate::effort`.
    pub effort: Effort,
    /// Descriptive tags only (e.g. "sharp", "floating", "coiled") — never
    /// emotive ("angry", "joyful"). Not enforced by this type (open
    /// vocabulary per §2.2); a closed enum would fight the very
    /// extensibility the tags exist for.
    pub applicability_tags: Vec<String>,
    pub intensity: f32,
    pub provenance: Provenance,
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::curve::Flavor;

    #[test]
    fn move_is_constructible_and_comparable() {
        let mut channels = BTreeMap::new();
        channels.insert(ChannelRole::PrimaryElevation, Curve::Quad(Flavor::Out));
        let mv = Move {
            channels,
            duration: Duration::Seconds(1.0),
            entry_pose: PoseRequirement::Agnostic,
            exit_pose: PoseRequirement::Agnostic,
            arrival_anchor: None,
            role: TimescaleRole::Groove,
            effort: Effort::NEUTRAL,
            applicability_tags: vec!["sharp".into()],
            intensity: 1.0,
            provenance: Provenance::Authored,
        };
        assert_eq!(mv.clone(), mv);
    }

    #[test]
    fn duration_beats_resolves_with_tempo() {
        assert_eq!(Duration::Beats(2.0).to_seconds(0.5), 1.0);
        assert_eq!(Duration::Seconds(3.0).to_seconds(999.0), 3.0);
    }
}
