//! hyst-render — wgpu renderer + `.hyst` parsing (R2). See
//! `SINTEZA_IMPLEMENTATION_PLAN.md` §4 (R2) for scope.
//!
//! This session's real slice: the `.hyst` format parser (`hyst_format`).
//! **Deliberately not yet started**, flagged rather than silently absent:
//! `wgpu` setup, the render passes (memory field/persistence/bloom/
//! composite/beam), GLSL-body translation/compilation, and the Julia
//! substrate itself. See `AGENTS.md` §5 for the session record.

pub mod gpu;
pub mod hyst_format;
pub mod isf_translate;
pub mod passes;
pub mod renderer;

pub use gpu::{GpuContext, GpuError, OffscreenTarget};
pub use hyst_format::{parse_hyst, IsfDocument, IsfInput, IsfParseError, IsfPass};
pub use isf_translate::translate_isf_glsl;
pub use renderer::{FrameParams, Renderer};
