//! The typed contract between a `HYSTERESIS_SCRIPT` and the engine that hosts it — what a
//! script is allowed to write, and how a malformed value gets coerced back to something safe
//! before it ever reaches a consumer.
//!
//! This mirrors the *shape* of `hyst-render`'s `IsfScriptOutputKind` /
//! `IsfScriptTexturePass` (`crates/hyst-render/src/hyst_format/types.rs`, itself ported from
//! `src/isf/types.ts`) field-for-field, but is deliberately its own, independent type rather than
//! a dependency on `hyst-render` — R2 and R3 are parallel workstreams (plan §3), and the crate
//! boundary is the parallelization seam (rule 4). When `hyst-render`'s `.hyst` parser and this
//! crate's engine are eventually wired together (later workstream, not this one), the glue code
//! translates one shape into the other; neither crate needs to know the other exists today.

use std::collections::HashMap;

/// Mirrors `IsfScriptOutputKind` (`float | bool | point2D | color`). Deliberately not
/// `long`-capable, same "extend when there's a second real case" discipline as the TS/Rust
/// original.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OutputKind {
    Float,
    Bool,
    Point2d,
    Color,
}

/// A concrete value of one of the four `OutputKind`s. Used both for a `scriptOutput`'s declared
/// default and for what a script actually produced this frame (post-coercion).
#[derive(Debug, Clone, PartialEq)]
pub enum OutputValue {
    Float(f64),
    Bool(bool),
    Point2d([f64; 2]),
    Color([f64; 4]),
}

impl OutputValue {
    /// The `OutputKind` this value is shaped as — used to check a script's raw return value
    /// against its declaration before accepting it.
    pub fn kind(&self) -> OutputKind {
        match self {
            OutputValue::Float(_) => OutputKind::Float,
            OutputValue::Bool(_) => OutputKind::Bool,
            OutputValue::Point2d(_) => OutputKind::Point2d,
            OutputValue::Color(_) => OutputKind::Color,
        }
    }

    /// `true` iff every number inside this value is finite — a diverging script computation
    /// (e.g. a runaway spring) must not hand a NaN/Infinity to a downstream consumer. Mirrors
    /// `engine-source.js`'s own finite-checks inside `coerceUniform`.
    fn is_finite(&self) -> bool {
        match self {
            OutputValue::Float(v) => v.is_finite(),
            OutputValue::Bool(_) => true,
            OutputValue::Point2d([x, y]) => x.is_finite() && y.is_finite(),
            OutputValue::Color(c) => c.iter().all(|v| v.is_finite()),
        }
    }
}

/// One declared `scriptOutput` — a scalar/vector value a script writes each frame.
#[derive(Debug, Clone, PartialEq)]
pub struct ScriptOutputDecl {
    pub kind: OutputKind,
    pub default: OutputValue,
}

/// One declared `scriptTexture` source — a named, fixed-length RG32F-shaped buffer (height 1,
/// one texel = one (R, G) pair). `texel_count` matches the TS contract's `length` field's
/// meaning (texel count, NOT float count) — see `float_len()` for the actual `Vec<f32>` length a
/// script must produce.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TextureDecl {
    pub texel_count: usize,
}

impl TextureDecl {
    /// The flat `f32` buffer length a script's texture output is coerced to: `texel_count * 2`
    /// (R, G interleaved per texel) — always even by construction, matching the RG32F shape.
    pub fn float_len(self) -> usize {
        self.texel_count * 2
    }
}

/// The full declared contract for one script: every `scriptOutput` it may write plus every
/// `scriptTexture` source it may fill. Built once (from a `.hyst` document's declared inputs/
/// passes, in whatever later workstream wires `hyst-render` and `hyst-script` together) and
/// never mutated for the life of a `ScriptRuntime`.
#[derive(Debug, Clone, Default)]
pub struct ScriptContract {
    pub uniforms: HashMap<String, ScriptOutputDecl>,
    pub textures: HashMap<String, TextureDecl>,
}

/// A script's actual per-frame output, already coerced against its `ScriptContract` — safe to
/// hand to any consumer (a GPU upload, a patch-graph target, later choreography) without further
/// validation.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct FrameOutput {
    pub uniforms: HashMap<String, OutputValue>,
    pub textures: HashMap<String, Vec<f32>>,
}

impl FrameOutput {
    /// The all-defaults output a contract implies before any script has ever run successfully
    /// (or after a script permanently fails to load) — never a bare zeroed/empty map, always the
    /// author's own declared defaults, same as the TS engine falling back to `decl.default`.
    pub fn defaults(contract: &ScriptContract) -> Self {
        let uniforms = contract
            .uniforms
            .iter()
            .map(|(name, decl)| (name.clone(), decl.default.clone()))
            .collect();
        let textures = contract
            .textures
            .iter()
            .map(|(name, decl)| (name.clone(), vec![0.0; decl.float_len()]))
            .collect();
        FrameOutput { uniforms, textures }
    }
}

/// Coerces one script-returned uniform value against its declaration — wrong-typed, missing, or
/// non-finite values fall back to the declared default rather than reaching a consumer malformed.
/// Ports `engine-source.js`'s `coerceUniform` behavior exactly (including that a *type*
/// mismatch, e.g. a `float` decl but the script returned a bool, is treated the same as
/// "missing": fall back to default, don't try to convert).
pub fn coerce_uniform(decl: &ScriptOutputDecl, raw: Option<&OutputValue>) -> OutputValue {
    match raw {
        Some(value) if value.kind() == decl.kind && value.is_finite() => value.clone(),
        _ => decl.default.clone(),
    }
}

/// Coerces one script-returned texture buffer against its declared texel count. Ports
/// `engine-source.js`'s `coerceTexture` exactly: padded with the last finite value if short,
/// truncated if long, every entry sanitized to a finite number (holding the last finite value
/// across a non-finite one) — mirrors `JuliaScene.ts`'s own reference-orbit handling: once a
/// diverging computation stops being finite, hold rather than propagate NaN/Infinity into a
/// texture upload. This is the validation-before-handoff the task spec calls out: a wrong-length
/// or non-finite buffer is normalized here, inside the sandbox boundary, so it can never reach a
/// hypothetical GPU consumer malformed.
pub fn coerce_texture(decl: TextureDecl, raw: Option<&[f32]>) -> Vec<f32> {
    let want = decl.float_len();
    let mut out = vec![0.0f32; want];
    let Some(raw) = raw else { return out };
    let mut last = 0.0f32;
    for (i, slot) in out.iter_mut().enumerate() {
        let v = raw.get(i).copied().unwrap_or(last);
        let finite = if v.is_finite() { v } else { last };
        *slot = finite;
        last = finite;
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn float_decl(default: f64) -> ScriptOutputDecl {
        ScriptOutputDecl {
            kind: OutputKind::Float,
            default: OutputValue::Float(default),
        }
    }

    #[test]
    fn coerce_uniform_accepts_matching_finite_value() {
        let decl = float_decl(0.0);
        let got = coerce_uniform(&decl, Some(&OutputValue::Float(1.5)));
        assert_eq!(got, OutputValue::Float(1.5));
    }

    #[test]
    fn coerce_uniform_falls_back_on_type_mismatch() {
        let decl = float_decl(9.0);
        let got = coerce_uniform(&decl, Some(&OutputValue::Bool(true)));
        assert_eq!(got, OutputValue::Float(9.0));
    }

    #[test]
    fn coerce_uniform_falls_back_on_non_finite() {
        let decl = float_decl(9.0);
        let got = coerce_uniform(&decl, Some(&OutputValue::Float(f64::NAN)));
        assert_eq!(got, OutputValue::Float(9.0));
    }

    #[test]
    fn coerce_uniform_falls_back_on_missing() {
        let decl = float_decl(9.0);
        let got = coerce_uniform(&decl, None);
        assert_eq!(got, OutputValue::Float(9.0));
    }

    #[test]
    fn coerce_texture_pads_short_buffer_with_last_finite_value() {
        let decl = TextureDecl { texel_count: 3 }; // float_len = 6
        let got = coerce_texture(decl, Some(&[1.0, 2.0, 3.0]));
        assert_eq!(got, vec![1.0, 2.0, 3.0, 3.0, 3.0, 3.0]);
    }

    #[test]
    fn coerce_texture_truncates_long_buffer() {
        let decl = TextureDecl { texel_count: 2 }; // float_len = 4
        let got = coerce_texture(decl, Some(&[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]));
        assert_eq!(got, vec![1.0, 2.0, 3.0, 4.0]);
    }

    #[test]
    fn coerce_texture_holds_last_finite_value_across_nan() {
        let decl = TextureDecl { texel_count: 2 };
        let got = coerce_texture(decl, Some(&[1.0, f32::NAN, f32::INFINITY, 4.0]));
        assert_eq!(got, vec![1.0, 1.0, 1.0, 4.0]);
    }

    #[test]
    fn coerce_texture_defaults_to_zeros_when_missing() {
        let decl = TextureDecl { texel_count: 2 };
        let got = coerce_texture(decl, None);
        assert_eq!(got, vec![0.0, 0.0, 0.0, 0.0]);
    }

    #[test]
    fn declared_float_len_is_always_even() {
        for n in 0..10usize {
            assert_eq!(TextureDecl { texel_count: n }.float_len() % 2, 0);
        }
    }
}
