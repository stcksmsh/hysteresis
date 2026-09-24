//! The `.hyst` format (ISF-superset: GLSL + JSON header) — ported from
//! `src/isf/{types,parse-isf}.ts`. See `types.rs`'s module doc for the
//! design; GLSL-body translation/compilation (`translate-isf-glsl.ts`'s
//! counterpart) is NOT ported this session — flagged as R2 follow-up, this
//! slice is parsing only.

pub mod parse;
pub mod types;

pub use parse::parse_hyst;
pub use types::{
    IsfDocument, IsfInput, IsfParseError, IsfPass, IsfScriptOutputKind, ScriptOutputDefault,
};
