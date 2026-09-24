//! `hyst-script` — the Lua scripting runtime (plan §4 R3). `mlua` (vendored Lua 5.4) hosts a
//! `HYSTERESIS_SCRIPT` per shader: reads the signal bus + frame timing, writes named typed
//! output (scalars + fixed-length texture buffers), under an enforced per-frame instruction
//! budget, with fault isolation that freezes output at last-known-good values rather than
//! resetting or crashing. See this crate's README for the full script-author-facing contract.
//!
//! Deliberately **not** a dependency of/on `hyst-render` — R2 and R3 are parallel workstreams
//! (plan §3); `contract.rs` mirrors `hyst-render`'s `IsfScriptOutputKind` shape independently.

pub mod contract;
pub mod engine;
pub mod frame;
pub mod lua_bridge;
pub mod runtime;
pub mod shared_state;

pub use contract::{
    FrameOutput, OutputKind, OutputValue, ScriptContract, ScriptOutputDecl, TextureDecl,
};
pub use engine::{ScriptEngine, ScriptSlot};
pub use frame::FrameInput;
pub use runtime::{ScriptFault, ScriptLoadError, ScriptRuntime};
pub use shared_state::{
    new_handle as new_shared_state, SharedState, SharedStateHandle, SharedValue,
};

#[cfg(test)]
mod smoke {
    use mlua::Lua;

    #[test]
    fn vendored_lua_runs_a_trivial_script() {
        let lua = Lua::new();
        let value: i64 = lua.load("return 1 + 41").eval().unwrap();
        assert_eq!(value, 42);
    }
}
