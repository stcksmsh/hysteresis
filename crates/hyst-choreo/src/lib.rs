//! `hyst-choreo` — choreography primitives (`SINTEZA_IMPLEMENTATION_PLAN.md`
//! R4): the curve corpus, the `Move` type, the procedural move generator,
//! ensemble `Topology`, and formation modes. Pure math/data only — no
//! runtime sequencing (R7), no hardware, no rendering. See the crate
//! README for the full data model and what's deliberately not here yet.

pub mod curve;
pub mod effort;
pub mod formation;
pub mod generator;
pub mod moves;
pub mod topology;
