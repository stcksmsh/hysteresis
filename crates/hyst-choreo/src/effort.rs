//! The Effort vector (`SINTEZA_CHOREOGRAPHY.md` §2.2): Time/Weight/Space
//! only. **Flow is deliberately excluded** — the LMA robotics source this
//! is based on drops it because it has no spatial correlate on low-DOF
//! platforms. Do not add it, even as a stub field.

/// A three-scalar modifier layered over any [`crate::move_::Move`], not a
/// separate move. Each axis is `0.0..=1.0` along its named polarity.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Effort {
    /// Sudden (1.0) vs sustained (0.0) — modeled as extrema count in the
    /// velocity profile per §2.2; stored here as the already-normalized
    /// scalar, not the raw extrema count.
    pub time: f32,
    /// Strong (1.0) vs light (0.0) — path displacement/amplitude bias.
    pub weight: f32,
    /// Indirect (1.0) vs direct (0.0) — heading variation en route.
    pub space: f32,
}

impl Effort {
    pub const NEUTRAL: Effort = Effort {
        time: 0.5,
        weight: 0.5,
        space: 0.5,
    };

    pub fn in_range(&self) -> bool {
        (0.0..=1.0).contains(&self.time)
            && (0.0..=1.0).contains(&self.weight)
            && (0.0..=1.0).contains(&self.space)
    }
}

impl Default for Effort {
    fn default() -> Self {
        Effort::NEUTRAL
    }
}
