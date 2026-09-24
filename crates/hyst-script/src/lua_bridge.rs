//! Lua <-> Rust value plumbing: `SignalBus` -> a read-only Lua table, and a script's raw
//! returned Lua value -> a typed `OutputValue`/texture buffer (pre-coercion — `contract.rs`
//! does the actual coercion once this module has produced a type-matched candidate or `None`).

use hyst_core::SignalBus;
use mlua::{Lua, Table, Value};

use crate::contract::OutputKind;

/// Builds a read-only-by-convention Lua table exposing every `SignalBus` field a script might
/// want to read. Full bus, not a patch-graph-filtered subset — per plan §4 R3 ("what a script
/// reads: bus signals (reuse `hyst_core::SignalBus`)"), unlike the TS engine which only saw
/// whatever the patch graph had already routed to it.
pub fn push_signal_bus(lua: &Lua, bus: &SignalBus) -> mlua::Result<Table> {
    let t = lua.create_table()?;
    macro_rules! f {
        ($name:ident) => {
            t.set(stringify!($name), bus.$name)?
        };
    }
    f!(energy);
    f!(sub);
    f!(low);
    f!(mid);
    f!(presence);
    f!(air);
    f!(band_tilt);
    f!(centroid);
    f!(flatness);
    f!(pan);
    f!(familiarity);
    f!(novelty_local);
    f!(novelty_section);
    f!(fullness);
    f!(onset_density);
    f!(harmonic_novelty);
    f!(chroma_root_hue);
    f!(vocal_presence);
    f!(drums_presence);
    f!(bass_presence);
    f!(other_presence);
    f!(lead_presence);
    f!(hue_drift);
    f!(beat_phase);
    f!(beat_pulse);
    f!(bar_phase);
    f!(downbeat_pulse);
    f!(build_windup);
    f!(build_progress);
    f!(tension);
    f!(suspension);
    f!(drop_impulse);
    f!(onset_impulse);
    f!(idle);
    f!(tempo_bpm);
    f!(tempo_confidence);
    // scope/chroma/drop_trigger are Option — nil when absent, matching how the rest of the bus's
    // "no data yet" state already reads (e.g. idle's zeroed neighbors) rather than a sentinel.
    match &bus.scope {
        Some(v) => t.set("scope", v.clone())?,
        None => t.set("scope", Value::Nil)?,
    }
    match &bus.chroma {
        Some(v) => t.set("chroma", v.clone())?,
        None => t.set("chroma", Value::Nil)?,
    }
    Ok(t)
}

/// Reads a Lua sequence table into a fixed-size `[f64; N]`, requiring exactly `N` numeric
/// entries — used for `point2D`/`color` uniforms, which TS's `coerceUniform` treats as
/// all-or-nothing (any wrong length/type is "malformed", not partially accepted).
fn fixed_number_array<const N: usize>(t: &Table) -> Option<[f64; N]> {
    if t.raw_len() != N {
        return None;
    }
    let mut out = [0.0f64; N];
    for (i, slot) in out.iter_mut().enumerate() {
        let v: Value = t.get(i + 1).ok()?;
        *slot = match v {
            Value::Number(n) => n,
            Value::Integer(n) => n as f64,
            _ => return None,
        };
    }
    Some(out)
}

/// Interprets a raw Lua value as an `OutputValue` of exactly `kind`, or `None` if it doesn't
/// match that kind's shape — mirrors `engine-source.js`'s `coerceUniform` type checks, just
/// split out so `contract::coerce_uniform` stays Lua-agnostic and independently testable.
pub fn lua_value_as_output(
    kind: OutputKind,
    value: &Value,
) -> Option<crate::contract::OutputValue> {
    use crate::contract::OutputValue as OV;
    match (kind, value) {
        (OutputKind::Float, Value::Number(n)) => Some(OV::Float(*n)),
        (OutputKind::Float, Value::Integer(n)) => Some(OV::Float(*n as f64)),
        (OutputKind::Bool, Value::Boolean(b)) => Some(OV::Bool(*b)),
        (OutputKind::Point2d, Value::Table(t)) => fixed_number_array::<2>(t).map(OV::Point2d),
        (OutputKind::Color, Value::Table(t)) => fixed_number_array::<4>(t).map(OV::Color),
        _ => None,
    }
}

/// Reads a Lua sequence table of numbers into `Vec<f32>` — used for a script's raw
/// `textures[name]` return value before `contract::coerce_texture` pads/truncates/sanitizes it.
/// Non-array-like or non-numeric-entry values yield `None` (treated as "missing" downstream,
/// same as TS's `coerceTexture` falling back to all-zeros for a non-array-like value).
pub fn lua_table_as_f32_vec(value: &Value) -> Option<Vec<f32>> {
    let Value::Table(t) = value else { return None };
    let len = t.raw_len();
    let mut out = Vec::with_capacity(len);
    for i in 1..=len {
        let v: Value = t.get(i).ok()?;
        let n = match v {
            Value::Number(n) => n as f32,
            Value::Integer(n) => n as f32,
            _ => f32::NAN, // let coerce_texture's finite-check hold-last-value handle it
        };
        out.push(n);
    }
    Some(out)
}
