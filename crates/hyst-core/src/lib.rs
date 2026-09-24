//! hyst-core — foundation crate (R0). Signal bus types + timescale tags,
//! sidecar deserialization, project loading, the `VizOutput` trait, and
//! error conventions shared by every other crate in the workspace.
//!
//! See `SINTEZA_IMPLEMENTATION_PLAN.md` §4 (R0) for scope, and the TS tree
//! (`src/render/conductor/types.ts`, `src/shared/sidecar.ts`) for what this
//! ports from — read freely, never edited, per plan §1.2.

pub mod error;
pub mod project;
pub mod sidecar;
pub mod signal;

pub use error::{HystError, Result};
pub use project::{Project, ProjectManifest, PROJECT_FORMAT_VERSION};
pub use sidecar::{Sidecar, SidecarSchemaVersion, SIDECAR_SCHEMA_VERSION};
pub use signal::{
    signal_tag, ResolvedTargetValue, ResolvedTargets, SignalBus, TargetDecl, TimescaleTag,
    VizOutput, ROUTABLE_SIGNAL_NAMES,
};
