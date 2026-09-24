//! Fault isolation + orchestration. Ports `script-host.ts`'s *behavior* (not its mechanism — that
//! was a sandboxed nested-Worker with async postMessage; `mlua` is in-process and synchronous, so
//! there's no message-passing/timeout-polling layer to port, just the fault-handling shape):
//! a throwing/hanging script never takes the process down, and its exposed output freezes at the
//! last good frame rather than resetting to zero until the script recovers.

use hyst_core::SignalBus;

use crate::contract::{FrameOutput, ScriptContract};
use crate::frame::FrameInput;
use crate::runtime::{ScriptFault, ScriptLoadError, ScriptRuntime, DEFAULT_INSTRUCTION_BUDGET};
use crate::shared_state::{new_handle, SharedStateHandle};

/// Same threshold as `script-host.ts`'s `MAX_CONSECUTIVE_FAULTS` — after this many faults in a
/// row, stop retrying (a fundamentally broken script thrashing a respawn every frame helps no
/// one) and give up permanently, still serving the last good output forever after.
const MAX_CONSECUTIVE_FAULTS: u32 = 5;

/// One named script, restart-and-continue-on-last-known-values.
pub struct ScriptSlot {
    name: String,
    source: String,
    contract: ScriptContract,
    shared: SharedStateHandle,
    instruction_budget: u64,
    runtime: Option<ScriptRuntime>,
    last_good: FrameOutput,
    consecutive_faults: u32,
    permanently_faulted: bool,
    last_fault: Option<String>,
}

impl ScriptSlot {
    pub fn new(
        name: impl Into<String>,
        source: impl Into<String>,
        contract: ScriptContract,
        shared: SharedStateHandle,
    ) -> Self {
        Self::with_budget(name, source, contract, shared, DEFAULT_INSTRUCTION_BUDGET)
    }

    pub fn with_budget(
        name: impl Into<String>,
        source: impl Into<String>,
        contract: ScriptContract,
        shared: SharedStateHandle,
        instruction_budget: u64,
    ) -> Self {
        let source = source.into();
        let last_good = FrameOutput::defaults(&contract);
        let mut slot = ScriptSlot {
            name: name.into(),
            source,
            contract,
            shared,
            instruction_budget,
            runtime: None,
            last_good,
            consecutive_faults: 0,
            permanently_faulted: false,
            last_fault: None,
        };
        slot.try_spawn();
        slot
    }

    pub fn name(&self) -> &str {
        &self.name
    }

    pub fn output(&self) -> &FrameOutput {
        &self.last_good
    }

    pub fn last_fault(&self) -> Option<&str> {
        self.last_fault.as_deref()
    }

    pub fn is_permanently_faulted(&self) -> bool {
        self.permanently_faulted
    }

    /// A syntax error / missing `update` fn is NOT retried — respawning a script whose source
    /// never parsed can't fix it (matches TS's `loadError` -> permanent, reported once).
    fn try_spawn(&mut self) {
        match ScriptRuntime::with_budget(&self.source, self.shared.clone(), self.instruction_budget)
        {
            Ok(rt) => self.runtime = Some(rt),
            Err(e) => {
                self.permanently_faulted = true;
                self.last_fault = Some(format_load_error(&e));
            }
        }
    }

    fn record_fault(&mut self, message: String) {
        self.consecutive_faults += 1;
        self.runtime = None; // force a respawn attempt next tick
        if self.consecutive_faults >= MAX_CONSECUTIVE_FAULTS {
            self.permanently_faulted = true;
            self.last_fault = Some(format!(
                "{message} ({} consecutive faults — giving up, output frozen at last-known values)",
                self.consecutive_faults
            ));
        } else {
            self.last_fault = Some(message);
        }
    }

    /// Runs one frame. `self.output()` always reflects the last frame the script actually
    /// completed successfully — a fault this call leaves it untouched, never zeroed/reset.
    pub fn tick(&mut self, frame: &FrameInput) {
        if self.permanently_faulted {
            return;
        }
        if self.runtime.is_none() {
            self.try_spawn();
            if self.permanently_faulted || self.runtime.is_none() {
                return;
            }
        }
        let rt = self.runtime.as_ref().expect("just ensured present");
        match rt.call(frame, &self.contract) {
            Ok(output) => {
                self.consecutive_faults = 0;
                self.last_good = output;
            }
            Err(ScriptFault(message)) => self.record_fault(message),
        }
    }
}

fn format_load_error(e: &ScriptLoadError) -> String {
    format!("HYSTERESIS_SCRIPT failed to load: {e}")
}

/// Runs a declared, ordered set of scripts once per frame, each in its own `ScriptSlot`, sharing
/// one `SharedState` namespace. **No script gets a reference to another** — the only channel
/// between them is `shared` (plain data, plan §4 R3's "no script-to-script calls").
pub struct ScriptEngine {
    shared: SharedStateHandle,
    slots: Vec<ScriptSlot>,
}

impl ScriptEngine {
    pub fn new() -> Self {
        ScriptEngine {
            shared: new_handle(),
            slots: Vec::new(),
        }
    }

    /// Scripts run in the order they're added — deterministic, per plan §4 R3 ("when it runs:
    /// once per frame, in a declared, deterministic order").
    pub fn add_script(
        &mut self,
        name: impl Into<String>,
        source: impl Into<String>,
        contract: ScriptContract,
    ) {
        self.slots
            .push(ScriptSlot::new(name, source, contract, self.shared.clone()));
    }

    pub fn add_script_with_budget(
        &mut self,
        name: impl Into<String>,
        source: impl Into<String>,
        contract: ScriptContract,
        instruction_budget: u64,
    ) {
        self.slots.push(ScriptSlot::with_budget(
            name,
            source,
            contract,
            self.shared.clone(),
            instruction_budget,
        ));
    }

    pub fn tick(
        &mut self,
        dt: f32,
        time: f32,
        playback_position: f32,
        idle: bool,
        bus: &SignalBus,
    ) {
        let frame = FrameInput {
            dt,
            time,
            playback_position,
            idle,
            bus,
        };
        for slot in &mut self.slots {
            slot.tick(&frame);
        }
    }

    pub fn slot(&self, name: &str) -> Option<&ScriptSlot> {
        self.slots.iter().find(|s| s.name() == name)
    }
}

impl Default for ScriptEngine {
    fn default() -> Self {
        Self::new()
    }
}
