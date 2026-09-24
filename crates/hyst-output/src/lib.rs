//! `hyst-output` — `VizOutput` implementations. This session: shared cadence/diff/failure
//! plumbing, and `FieldOutput` (dense physical arrays). See README.md and
//! `SINTEZA_CHOREOGRAPHY.md` §0/§5.3/§7.

pub mod array_topology;
pub mod cadence;
pub mod diff;
pub mod failure;
pub mod field;
pub mod field_output;

pub use array_topology::{ArrayTopology, ElementSlot};
pub use cadence::TickAccumulator;
pub use diff::DiffTracker;
pub use failure::FailureMask;
pub use field::{BilinearGradient, Checkerboard, FieldSource, FieldValue, MovingGaussianBlob};
pub use field_output::{ElementMapping, ElementUpdate, FieldOutput};
