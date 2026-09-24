//! One script's own Lua VM: load, an enforced per-frame instruction budget, and the frame
//! in/frame out call. No fault-isolation/restart logic here — that's `engine.rs`'s job, layered
//! on top; this module either returns a result or an error, once, and does not itself retry.

use std::cell::Cell;
use std::collections::HashMap;
use std::rc::Rc;

use mlua::{Function, HookTriggers, Lua, RegistryKey, Table, Value, VmState};

use crate::contract::{coerce_texture, coerce_uniform, FrameOutput, ScriptContract};
use crate::frame::FrameInput;
use crate::lua_bridge::{lua_table_as_f32_vec, lua_value_as_output, push_signal_bus};
use crate::shared_state::{bind_shared_global, SharedStateHandle};

/// How often (in VM instructions) the budget hook fires. Lower = finer-grained interruption but
/// higher overhead per mlua's own `HookTriggers::every_nth_instruction` doc; 256 is a reasonable
/// middle ground never profiled against a real script yet (R6 will be the first real load test).
const HOOK_INSTRUCTION_INTERVAL: u32 = 256;

/// Default per-frame VM-instruction ceiling. Generous for real per-frame work (a spring update,
/// a small orbit buffer fill) while still bounding a runaway loop to a fraction of a second of
/// wall time — see `tests/instruction_budget.rs` for the "infinite loop actually gets stopped"
/// proof.
pub const DEFAULT_INSTRUCTION_BUDGET: u64 = 2_000_000;

#[derive(Debug, thiserror::Error)]
pub enum ScriptLoadError {
    #[error("script does not compile or errored during top-level load: {0}")]
    Compile(String),
    #[error("HYSTERESIS_SCRIPT must define an update(frame) function")]
    MissingUpdate,
}

#[derive(Debug, thiserror::Error)]
#[error("{0}")]
pub struct ScriptFault(pub String);

pub struct ScriptRuntime {
    lua: Lua,
    update_key: RegistryKey,
    instruction_count: Rc<Cell<u64>>,
}

impl ScriptRuntime {
    pub fn new(source: &str, shared: SharedStateHandle) -> Result<Self, ScriptLoadError> {
        Self::with_budget(source, shared, DEFAULT_INSTRUCTION_BUDGET)
    }

    pub fn with_budget(
        source: &str,
        shared: SharedStateHandle,
        instruction_budget: u64,
    ) -> Result<Self, ScriptLoadError> {
        let lua = Lua::new();
        bind_shared_global(&lua, shared).map_err(|e| ScriptLoadError::Compile(e.to_string()))?;

        let instruction_count = Rc::new(Cell::new(0u64));
        let counter = instruction_count.clone();
        lua.set_hook(
            HookTriggers::new().every_nth_instruction(HOOK_INSTRUCTION_INTERVAL),
            move |_, _| {
                let n = counter.get() + HOOK_INSTRUCTION_INTERVAL as u64;
                counter.set(n);
                if n > instruction_budget {
                    return Err(mlua::Error::RuntimeError(
                        "script exceeded its per-frame instruction budget".into(),
                    ));
                }
                Ok(VmState::Continue)
            },
        )
        .map_err(|e| ScriptLoadError::Compile(e.to_string()))?;

        lua.load(source)
            .exec()
            .map_err(|e| ScriptLoadError::Compile(e.to_string()))?;

        let update: Function = lua
            .globals()
            .get("update")
            .map_err(|_| ScriptLoadError::MissingUpdate)?;
        let update_key = lua
            .create_registry_value(update)
            .map_err(|e| ScriptLoadError::Compile(e.to_string()))?;

        Ok(ScriptRuntime {
            lua,
            update_key,
            instruction_count,
        })
    }

    /// Runs one frame. Persistent script-side state (upvalues closed over `update`, e.g. a
    /// spring's velocity) lives in `self.lua` across calls — nothing here resets it; only a
    /// fresh `ScriptRuntime` (a full respawn, `engine.rs`'s job on fault) does.
    pub fn call(
        &self,
        frame: &FrameInput,
        contract: &ScriptContract,
    ) -> Result<FrameOutput, ScriptFault> {
        self.instruction_count.set(0); // budget is per-frame, not cumulative for the VM's life

        let update: Function = self
            .lua
            .registry_value(&self.update_key)
            .map_err(|e| ScriptFault(e.to_string()))?;

        let frame_table = self
            .lua
            .create_table()
            .map_err(|e| ScriptFault(e.to_string()))?;
        frame_table
            .set("dt", frame.dt)
            .map_err(|e| ScriptFault(e.to_string()))?;
        frame_table
            .set("time", frame.time)
            .map_err(|e| ScriptFault(e.to_string()))?;
        frame_table
            .set("playback_position", frame.playback_position)
            .map_err(|e| ScriptFault(e.to_string()))?;
        frame_table
            .set("idle", frame.idle)
            .map_err(|e| ScriptFault(e.to_string()))?;
        let bus_table =
            push_signal_bus(&self.lua, frame.bus).map_err(|e| ScriptFault(e.to_string()))?;
        frame_table
            .set("bus", bus_table)
            .map_err(|e| ScriptFault(e.to_string()))?;

        let result: Table = update
            .call(frame_table)
            .map_err(|e| ScriptFault(e.to_string()))?;

        let raw_uniforms: Option<Table> = result.get("uniforms").unwrap_or(None);
        let raw_textures: Option<Table> = result.get("textures").unwrap_or(None);

        let mut uniforms = HashMap::new();
        for (name, decl) in &contract.uniforms {
            let raw: Value = raw_uniforms
                .as_ref()
                .and_then(|t| t.get(name.as_str()).ok())
                .unwrap_or(Value::Nil);
            let candidate = lua_value_as_output(decl.kind, &raw);
            uniforms.insert(name.clone(), coerce_uniform(decl, candidate.as_ref()));
        }

        let mut textures = HashMap::new();
        for (name, decl) in &contract.textures {
            let raw: Value = raw_textures
                .as_ref()
                .and_then(|t| t.get(name.as_str()).ok())
                .unwrap_or(Value::Nil);
            let candidate = lua_table_as_f32_vec(&raw);
            textures.insert(name.clone(), coerce_texture(*decl, candidate.as_deref()));
        }

        Ok(FrameOutput { uniforms, textures })
    }
}
