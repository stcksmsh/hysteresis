//! `hyst-output` — physical-output plumbing: `VizOutput`-based dense fields plus direct-clock
//! compiled-score playback. See README.md and `SINTEZA_CHOREOGRAPHY.md` §0/§5.2/§5.3/§7.

pub mod array_topology;
pub mod cadence;
pub mod choreography_output;
pub mod diff;
pub mod ensemble;
pub mod failure;
pub mod field;
pub mod field_output;

pub use array_topology::{ArrayTopology, ElementSlot};
pub use cadence::TickAccumulator;
pub use choreography_output::{ChoreographyFrame, ChoreographyOutput, ClockPosition};
pub use diff::DiffTracker;
pub use failure::FailureMask;
pub use field::{BilinearGradient, Checkerboard, FieldSource, FieldValue, MovingGaussianBlob};
pub use field_output::{ElementMapping, ElementUpdate, FieldOutput};
