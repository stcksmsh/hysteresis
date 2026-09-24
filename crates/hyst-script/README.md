# hyst-script

Lua scripting runtime for `HYSTERESIS_SCRIPT` (plan §4 R3). Hosts a `.hyst` shader's optional
stateful companion script in `mlua` (vendored Lua 5.4) — no system Lua install needed.

## What it does

- Runs 0..N named scripts once per frame, in declared (insertion) order.
- Each script reads the frame's `dt`/`time`/`playback_position`/`idle` plus the full
  `hyst_core::SignalBus`, and returns declared, typed output.
- Enforces a per-frame Lua VM instruction budget (`mlua`'s instruction-count hook) so a runaway
  loop can't hang the process.
- Isolates faults: a throwing or budget-exceeding script never crashes the host. Its exposed
  output freezes at the last successful frame's values until it recovers or is given up on.
- Gives scripts a shared, plain-data `shared` namespace to coordinate through — never a callable
  reference to another script.

This ports the *behavior* of the old browser engine's nested-Worker sandbox
(`src/render/worker/scenes/isf/script-runtime/`) — restart-and-continue-on-fault, an enforced
execution budget, coercion of malformed output to a declared default — not its mechanism (that
was async postMessage/Worker; this is synchronous, in-process, single-threaded).

## The script contract

A script must define a global `update(frame)` function:

```lua
local smoothed = 0.0
function update(frame)
  local alpha = 0.2
  smoothed = smoothed + (frame.bus.energy - smoothed) * alpha
  return { uniforms = { smooth_energy = smoothed } }
end
```

`frame` fields: `dt`, `time`, `playback_position`, `idle` (booleans/numbers), and `bus` — a table
with every `hyst_core::SignalBus` field (snake_case, e.g. `frame.bus.beat_phase`,
`frame.bus.onset_impulse`). Local variables closed over by `update` (upvalues, e.g. `smoothed`
above) persist across every frame call — this is where a script keeps state (springs, decay,
search state), same as the old engine's closure-scoped `update()`.

Return a table with:
- `uniforms = { name = value, ... }` — one entry per declared `scriptOutput` (`float`, `bool`,
  `point2D` as a 2-array, `color` as a 4-array). A missing, wrong-typed, or non-finite value
  falls back to that output's declared default — silently, never a crash or NaN reaching a
  consumer.
- `textures = { name = { ... } }` — one flat array per declared `scriptTexture`, RG32F-shaped
  (pairs of (R, G), height 1). The array is padded (with the last finite value)/truncated to
  exactly `texel_count * 2` floats and every entry sanitized to finite — see `contract.rs`'s
  `coerce_texture`. **This happens before the value ever leaves the engine** — a wrong-length or
  NaN-filled buffer is never handed to a caller malformed.

Declare the contract in Rust (this is what a `.hyst` document's `scriptOutput`/`scriptTexture`
declarations would be translated into, once a later workstream wires `hyst-render` and
`hyst-script` together — not done in this crate, see Deviations below):

```rust
use hyst_script::{ScriptContract, ScriptOutputDecl, OutputKind, OutputValue, TextureDecl};
let mut uniforms = std::collections::HashMap::new();
uniforms.insert("smooth_energy".into(), ScriptOutputDecl { kind: OutputKind::Float, default: OutputValue::Float(0.0) });
let contract = ScriptContract { uniforms, textures: Default::default() };
```

### Shared state (the "ambient conductor" shape)

```lua
-- writer script
function update(frame)
  shared.set("mood", frame.bus.energy)
  return {}
end

-- reader script (runs later in the same frame, per declared order)
function update(frame)
  local mood = shared.get("mood") or 0.0
  return { uniforms = { seen_mood = mood } }
end
```

`shared` holds only plain data (numbers/bools/strings) — a script can never get a callable
reference into another script. One `ScriptEngine` owns one `SharedState`; every script's Lua VM
gets a `shared.get`/`shared.set` global bound to the same handle.

### Running it

```rust
use hyst_script::ScriptEngine;
let mut engine = ScriptEngine::new();
engine.add_script("conductor", source, contract);
engine.tick(dt, time, playback_position, idle, &bus);
let out = engine.slot("conductor").unwrap().output(); // always the last GOOD frame
```

## Fault isolation

- A script that errors (`error(...)`) or exceeds its instruction budget: the current frame's
  output stays exactly what it was last frame (frozen, not zeroed), the script's Lua VM is torn
  down, and a fresh one is spawned (recompiled from the same source) on the *next* tick — matching
  the old engine's "terminate + respawn the Worker" behavior. Its own persistent state (upvalues)
  is lost on respawn; that's the cost of the reset, same tradeoff the browser engine made.
- After 5 consecutive faults (`MAX_CONSECUTIVE_FAULTS`, same threshold as the old
  `script-host.ts`), the engine stops retrying and serves the last-good output forever —
  `ScriptSlot::is_permanently_faulted()` / `last_fault()` report this once.
- A script that never compiles, or never defines `update`, is caught at construction and marked
  permanently faulted immediately — respawning can't fix a syntax error.

## Verifying it works

`cargo test -p hyst-script` — 22 tests:
- `src/contract.rs` — uniform/texture coercion unit tests (type mismatch, non-finite, short/long
  buffers all fall back or normalize correctly).
- `src/shared_state.rs` — writes from one Lua VM are visible to another sharing the same handle.
- `tests/scripts.rs` — end-to-end against real Lua scripts:
  - a smoothed float tracking a computed EMA trajectory exactly (`smoother_script_...`)
  - a script with its own persistent decay state, asserted against the closed-form `0.9^n`
    (`decay_script_state_persists_between_calls_matching_closed_form`) — proves Lua upvalues
    really persist across separate `call()`s, not reset each frame
  - a `scriptTexture` orbit buffer at its declared length (`orbit_script_writes_declared_length...`)
    and a wrong-length variant proving it's coerced, never passed through
    (`wrong_length_texture_is_coerced_before_handoff_never_passed_through`)
  - an infinite `while true do end` loop actually interrupted within its instruction budget,
    asserted via wall-clock bound (`infinite_loop_is_interrupted_within_budget_not_left_running`)
  - a script that succeeds on frames 1-4, throws on frame 5: frame 5's output is asserted equal
    to frame 4's, not zero, not a panic (`faulting_script_freezes_at_last_good_value_not_zero`)
  - an always-broken script giving up permanently after exactly 5 faults, still serving its
    declared defaults (`permanently_gives_up_after_five_consecutive_faults_...`)
  - a writer/reader script pair proving the shared namespace works without either script calling
    into the other (`ambient_conductor_shape_writer_then_reader_same_frame`)

## Current limitations / notes for R6 (the real driver of this contract)

- **No expensive-setup-once escape hatch.** Every script gets exactly one hook: `update(frame)`,
  called every frame. A script that wants to do real one-time setup (e.g. precompute a lookup
  table) has to guard it with an `if not initialized then ... end` inside `update` itself — mildly
  awkward but works (Lua upvalues persist, so a `local initialized = false` closed over by
  `update` is enough). No dedicated `init()` hook was added since nothing here motivates one yet;
  flag if R6 finds it's actually painful.
- **A growing history buffer is possible but not first-class.** A script can accumulate a Lua
  table across frames (an upvalue), but there's no bounded-ring-buffer helper — a script that
  wants "last N samples" has to implement its own ring/eviction logic in Lua. Fine for R6's likely
  needs (a handful of floats), but flag if a much larger history turns out to matter (Lua tables
  aren't the cheapest structure for that).
- **Instruction budget is a blunt, untuned constant** (`DEFAULT_INSTRUCTION_BUDGET` = 2,000,000
  VM instructions/frame, checked every 256 instructions). Never profiled against a real script —
  R6's actual autopilot port is the first real load test; expect to retune.
- **Restart-on-fault loses script state.** A script's upvalues (its persistent state) are wiped
  on every respawn after a fault — matches the old engine's behavior exactly, but means a script
  that faults intermittently effectively resets its own memory each time. If R6's autopilot script
  turns out to fault under real conditions, this is worth revisiting (e.g. a script-managed
  "checkpoint" saved to `shared` before anything risky).
- **`shared` values are scalars only** (number/bool/string) — no point2D/color/table convenience
  there yet; add if a real script needs it.
- **Not wired to `hyst-render`.** This crate defines its own `ScriptContract`/`OutputKind` rather
  than depending on `hyst-render`'s `IsfScriptOutputKind`/`.hyst` parser (R2 and R3 are parallel
  workstreams, plan §3 — the crate boundary is the parallelization seam). Translating a parsed
  `.hyst` document's `scriptOutput`/`scriptTexture` declarations into a `ScriptContract`, and
  wiring a `ScriptEngine`'s output into a real renderer, is future glue code, not this crate's job.
