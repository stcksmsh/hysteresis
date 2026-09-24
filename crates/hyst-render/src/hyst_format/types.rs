//! `.hyst` document types, ported from `src/isf/types.ts`. An ISF-superset
//! format: a `/*{ ... }*/` JSON header immediately followed by GLSL. See
//! that file's own extensive header comments for the design rationale
//! (`hysteresisSignal`/`resource`/`scriptOutput` inputs, the
//! fullscreen/lineTrace/scriptTexture multi-pass model) — not restated here,
//! ported field-for-field instead.

#[derive(Debug, Clone, PartialEq)]
pub enum IsfInput {
    Float {
        name: String,
        label: Option<String>,
        default: f64,
        min: f64,
        max: f64,
    },
    Bool {
        name: String,
        label: Option<String>,
        default: bool,
    },
    Long {
        name: String,
        label: Option<String>,
        default: f64,
        values: Vec<f64>,
        labels: Vec<String>,
    },
    Color {
        name: String,
        label: Option<String>,
        default: [f64; 4],
    },
    Point2d {
        name: String,
        label: Option<String>,
        default: [f64; 2],
        min: [f64; 2],
        max: [f64; 2],
    },
    /// This format's own extension: a shader declares it wants a specific
    /// live Feature Engine signal by name instead of an anonymous float a
    /// user has to know to route by hand.
    HysteresisSignal {
        name: String,
        label: Option<String>,
        signal: String,
        default: f64,
    },
    /// A live, non-scalar system resource (today just `scope`) — not a
    /// routable patch-graph target, bound automatically by name.
    Resource {
        name: String,
        label: Option<String>,
        resource: String,
    },
    /// The `HYSTERESIS_SCRIPT` engine's per-frame stateful output — never a
    /// routable target either, a shader author picks script-driven OR
    /// patch-routed per input, not both.
    ScriptOutput {
        name: String,
        label: Option<String>,
        kind: IsfScriptOutputKind,
        default: ScriptOutputDefault,
    },
}

impl IsfInput {
    pub fn name(&self) -> &str {
        match self {
            IsfInput::Float { name, .. }
            | IsfInput::Bool { name, .. }
            | IsfInput::Long { name, .. }
            | IsfInput::Color { name, .. }
            | IsfInput::Point2d { name, .. }
            | IsfInput::HysteresisSignal { name, .. }
            | IsfInput::Resource { name, .. }
            | IsfInput::ScriptOutput { name, .. } => name,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IsfScriptOutputKind {
    Float,
    Bool,
    Point2d,
    Color,
}

#[derive(Debug, Clone, PartialEq)]
pub enum ScriptOutputDefault {
    Float(f64),
    Bool(bool),
    Point2d([f64; 2]),
    Color([f64; 4]),
}

/// Real ISF features this subset does not implement — detected and rejected
/// at parse time with a clear message rather than silently mis-rendering.
pub const UNSUPPORTED_INPUT_TYPES: [&str; 4] = ["image", "audio", "audioFFT", "event"];

#[derive(Debug, Clone, PartialEq)]
pub enum IsfPass {
    /// `''` target = the scene's real output framebuffer.
    Fullscreen { target: String },
    /// Draws an open polyline from a named `resource` input via GPU-
    /// instanced-quad rasterization — no shader-author GLSL body.
    LineTrace {
        target: String,
        points: String,
        width: Option<String>,
    },
    /// The `HYSTERESIS_SCRIPT` engine's non-scalar output channel: a named
    /// field of the script's per-frame `textures` output becomes a
    /// `uniform sampler2D <target>`. RG32F-only, height 1.
    ScriptTexture {
        target: String,
        source: String,
        length: u32,
    },
}

#[derive(Debug, Clone, PartialEq)]
pub struct IsfDocument {
    pub description: Option<String>,
    pub credit: Option<String>,
    pub categories: Vec<String>,
    pub inputs: Vec<IsfInput>,
    /// `None` = a plain stock-ISF-compatible file. Only version 1 is
    /// currently recognized.
    pub hysteresis_version: Option<f64>,
    /// Always at least one entry — a document with no `HYSTERESIS_VERSION`/
    /// `PASSES` gets the implicit single fullscreen pass.
    pub passes: Vec<IsfPass>,
    /// The optional per-file stateful JS companion, raw source inline.
    /// `None` = no script.
    pub hysteresis_script: Option<String>,
    /// The GLSL source after the JSON header comment — untranslated, still
    /// written against ISF's built-ins, not valid standalone GLSL on its
    /// own (see `translate-isf-glsl.ts`'s TS counterpart — not ported this
    /// session, flagged as R2 follow-up work).
    pub body: String,
}

#[derive(Debug, Clone, thiserror::Error)]
pub enum IsfParseError {
    #[error("{0}")]
    Parse(String),
    #[error("{0}")]
    UnsupportedFeature(String),
}
