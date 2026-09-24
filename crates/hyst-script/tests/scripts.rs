//! End-to-end tests against real Lua scripts — the "design the contract against a real script"
//! requirement (plan §4 R3). Three realistic scripts stand in for R6's autopilot (not ported
//! yet): a smoothed scalar reading the bus, a script with its own persistent decay state, and a
//! scriptTexture buffer writer. Plus the tests that BITE: instruction-budget enforcement,
//! restart-and-continue-on-fault, permanent-give-up, and texture-length enforcement.

use std::collections::HashMap;
use std::time::{Duration, Instant};

use hyst_core::SignalBus;
use hyst_script::{
    FrameInput, OutputKind, OutputValue, ScriptContract, ScriptEngine, ScriptOutputDecl,
    ScriptSlot, TextureDecl,
};

fn float_contract(name: &str, default: f64) -> ScriptContract {
    let mut uniforms = HashMap::new();
    uniforms.insert(
        name.to_string(),
        ScriptOutputDecl {
            kind: OutputKind::Float,
            default: OutputValue::Float(default),
        },
    );
    ScriptContract {
        uniforms,
        textures: HashMap::new(),
    }
}

fn bus_with_energy(energy: f32) -> SignalBus {
    SignalBus {
        energy,
        ..Default::default()
    }
}

// --- 1. Reads bus signals, writes a smoothed scriptOutput float. ---------------------------

const SMOOTHER: &str = r#"
local smoothed = 0.0
function update(frame)
  local alpha = 0.2
  smoothed = smoothed + (frame.bus.energy - smoothed) * alpha
  return { uniforms = { smooth_energy = smoothed } }
end
"#;

#[test]
fn smoother_script_tracks_expected_ema_trajectory() {
    let mut engine = ScriptEngine::new();
    engine.add_script("smoother", SMOOTHER, float_contract("smooth_energy", 0.0));

    let mut expected = 0.0f64;
    for frame in 0..20 {
        let energy = if frame < 10 { 1.0 } else { 0.0 };
        expected += (energy as f64 - expected) * 0.2;
        engine.tick(
            1.0 / 60.0,
            frame as f32,
            0.0,
            false,
            &bus_with_energy(energy),
        );
    }

    let slot = engine.slot("smoother").unwrap();
    match slot.output().uniforms.get("smooth_energy").unwrap() {
        OutputValue::Float(v) => assert!((v - expected).abs() < 1e-9, "{v} vs {expected}"),
        other => panic!("wrong kind: {other:?}"),
    }
}

// --- 2. Persistent state across frames (decay), not reset each call. -----------------------

const DECAY: &str = r#"
local level = 0.0
function update(frame)
  level = level * 0.9
  if frame.bus.onset_impulse > 0 then
    level = level + frame.bus.onset_impulse
  end
  return { uniforms = { level = level } }
end
"#;

#[test]
fn decay_script_state_persists_between_calls_matching_closed_form() {
    let mut engine = ScriptEngine::new();
    engine.add_script("decay", DECAY, float_contract("level", 0.0));

    // impulse of 1.0 on frame 0 only, then silence — closed form: level_n = 0.9^n.
    for frame in 0..8 {
        let bus = SignalBus {
            onset_impulse: if frame == 0 { 1.0 } else { 0.0 },
            ..Default::default()
        };
        engine.tick(1.0 / 60.0, frame as f32, 0.0, false, &bus);
    }

    let got = match engine
        .slot("decay")
        .unwrap()
        .output()
        .uniforms
        .get("level")
        .unwrap()
    {
        OutputValue::Float(v) => *v,
        other => panic!("wrong kind: {other:?}"),
    };
    // 0.9^7 after the impulse frame — proves the Lua upvalue `level` truly persisted across 8
    // separate `call()`s rather than resetting to 0 each time (a reset would read back as 0).
    assert!((got - 0.9f64.powi(7)).abs() < 1e-9, "{got}");
    assert!(got > 1e-4, "decay should not have reset to zero");
}

// --- 3. Writes a scriptTexture-shaped buffer (small orbit, fixed declared length). ----------

const ORBIT: &str = r#"
function update(frame)
  local out = {}
  local n = 4
  for i = 0, n - 1 do
    local a = (i / n) * 2 * math.pi
    out[i * 2 + 1] = math.cos(a)
    out[i * 2 + 2] = math.sin(a)
  end
  return { textures = { orbit = out } }
end
"#;

fn orbit_contract(texel_count: usize) -> ScriptContract {
    let mut textures = HashMap::new();
    textures.insert("orbit".to_string(), TextureDecl { texel_count });
    ScriptContract {
        uniforms: HashMap::new(),
        textures,
    }
}

#[test]
fn orbit_script_writes_declared_length_rg_pairs() {
    let mut engine = ScriptEngine::new();
    engine.add_script("orbit", ORBIT, orbit_contract(4));
    engine.tick(1.0 / 60.0, 0.0, 0.0, false, &SignalBus::default());

    let buf = engine
        .slot("orbit")
        .unwrap()
        .output()
        .textures
        .get("orbit")
        .unwrap();
    assert_eq!(buf.len(), 8); // texel_count * 2
    assert!((buf[0] - 1.0).abs() < 1e-5); // cos(0), sin(0)
    assert!(buf[1].abs() < 1e-5);
    assert!(buf[2].abs() < 1e-5); // cos(pi/2), sin(pi/2)
    assert!((buf[3] - 1.0).abs() < 1e-5);
}

#[test]
fn wrong_length_texture_is_coerced_before_handoff_never_passed_through() {
    // Contract declares 6 texels (12 floats) but the script only fills 4 slots (8 floats) —
    // must be padded to exactly 12, never handed through at the wrong length.
    let mut engine = ScriptEngine::new();
    engine.add_script("orbit", ORBIT, orbit_contract(6));
    engine.tick(1.0 / 60.0, 0.0, 0.0, false, &SignalBus::default());

    let buf = engine
        .slot("orbit")
        .unwrap()
        .output()
        .textures
        .get("orbit")
        .unwrap();
    assert_eq!(buf.len(), 12);
}

// --- Instruction budget actually fires on an infinite loop. ---------------------------------

const INFINITE_LOOP: &str = r#"
function update(frame)
  while true do end
end
"#;

#[test]
fn infinite_loop_is_interrupted_within_budget_not_left_running() {
    let shared = hyst_script::new_shared_state();
    let mut slot = ScriptSlot::with_budget(
        "hang",
        INFINITE_LOOP,
        float_contract("x", 0.0),
        shared,
        50_000,
    );

    let bus = SignalBus::default();
    let frame = FrameInput {
        dt: 0.016,
        time: 0.0,
        playback_position: 0.0,
        idle: false,
        bus: &bus,
    };

    let started = Instant::now();
    slot.tick(&frame);
    let elapsed = started.elapsed();

    assert!(
        elapsed < Duration::from_secs(2),
        "took {elapsed:?} — instruction hook did not interrupt"
    );
    assert!(slot.last_fault().unwrap().contains("instruction budget"));
    assert!(
        !slot.is_permanently_faulted(),
        "one fault should not be permanent yet"
    );
    // Output must still be the declared default (script never completed a frame) — not garbage.
    assert_eq!(
        *slot.output().uniforms.get("x").unwrap(),
        OutputValue::Float(0.0)
    );
}

// --- Restart-and-continue-on-last-known-values: throws on frame 5, frame-4 value persists. --

const INTERMITTENT: &str = r#"
local frame_count = 0
function update(frame)
  frame_count = frame_count + 1
  if frame_count == 5 then
    error("deliberate fault on frame 5")
  end
  return { uniforms = { x = frame_count * 1.0 } }
end
"#;

#[test]
fn faulting_script_freezes_at_last_good_value_not_zero() {
    let shared = hyst_script::new_shared_state();
    let mut slot = ScriptSlot::new(
        "intermittent",
        INTERMITTENT,
        float_contract("x", -1.0),
        shared,
    );
    let bus = SignalBus::default();

    for f in 1..=4 {
        let frame = FrameInput {
            dt: 0.016,
            time: f as f32,
            playback_position: 0.0,
            idle: false,
            bus: &bus,
        };
        slot.tick(&frame);
        assert_eq!(
            *slot.output().uniforms.get("x").unwrap(),
            OutputValue::Float(f as f64)
        );
    }

    // frame 5: the script errors. Output must still read frame 4's value (4.0), NOT 0/default,
    // and the process must not panic.
    let frame5 = FrameInput {
        dt: 0.016,
        time: 5.0,
        playback_position: 0.0,
        idle: false,
        bus: &bus,
    };
    slot.tick(&frame5);
    assert_eq!(
        *slot.output().uniforms.get("x").unwrap(),
        OutputValue::Float(4.0)
    );
    assert!(slot.last_fault().unwrap().contains("frame 5"));
    assert!(!slot.is_permanently_faulted());

    // A fresh Lua VM was spawned after the fault (restart) — its `frame_count` upvalue is back
    // at 0, so it takes 5 more successful calls before it would fault again; the very next call
    // succeeds and produces a real (not frozen, not zero) new value.
    let frame6 = FrameInput {
        dt: 0.016,
        time: 6.0,
        playback_position: 0.0,
        idle: false,
        bus: &bus,
    };
    slot.tick(&frame6);
    assert_eq!(
        *slot.output().uniforms.get("x").unwrap(),
        OutputValue::Float(1.0)
    );
}

// --- Gives up permanently after MAX_CONSECUTIVE_FAULTS, still serving last-known values. ----

const ALWAYS_ERRORS: &str = r#"
function update(frame)
  error("always broken")
end
"#;

#[test]
fn permanently_gives_up_after_five_consecutive_faults_but_keeps_serving_defaults() {
    let shared = hyst_script::new_shared_state();
    let mut slot = ScriptSlot::new("broken", ALWAYS_ERRORS, float_contract("x", 7.0), shared);
    let bus = SignalBus::default();
    let frame = FrameInput {
        dt: 0.016,
        time: 0.0,
        playback_position: 0.0,
        idle: false,
        bus: &bus,
    };

    for _ in 0..5 {
        slot.tick(&frame);
    }
    assert!(slot.is_permanently_faulted());
    assert!(slot.last_fault().unwrap().contains("5 consecutive faults"));
    assert_eq!(
        *slot.output().uniforms.get("x").unwrap(),
        OutputValue::Float(7.0)
    );

    // Ticking further does nothing — no panic, no retry storm.
    slot.tick(&frame);
    assert!(slot.is_permanently_faulted());
}

// --- A script that never even compiles is caught at construction, not first tick. -----------

#[test]
fn syntax_error_script_is_permanently_faulted_immediately() {
    let shared = hyst_script::new_shared_state();
    let slot = ScriptSlot::new(
        "bad",
        "this is not lua {{{",
        float_contract("x", 0.0),
        shared,
    );
    assert!(slot.is_permanently_faulted());
    assert!(slot.last_fault().unwrap().contains("failed to load"));
}

#[test]
fn missing_update_function_is_permanently_faulted_immediately() {
    let shared = hyst_script::new_shared_state();
    let slot = ScriptSlot::new("no-update", "local x = 1", float_contract("x", 0.0), shared);
    assert!(slot.is_permanently_faulted());
}

// --- Two scripts never call into each other, only through `shared`. ------------------------

const WRITER: &str = r#"
function update(frame)
  shared.set("mood", frame.bus.energy)
  return {}
end
"#;
const READER: &str = r#"
function update(frame)
  local mood = shared.get("mood") or 0.0
  return { uniforms = { seen_mood = mood } }
end
"#;

#[test]
fn ambient_conductor_shape_writer_then_reader_same_frame() {
    let mut engine = ScriptEngine::new();
    engine.add_script("writer", WRITER, ScriptContract::default());
    engine.add_script("reader", READER, float_contract("seen_mood", -1.0));

    engine.tick(1.0 / 60.0, 0.0, 0.0, false, &bus_with_energy(0.42));

    match engine
        .slot("reader")
        .unwrap()
        .output()
        .uniforms
        .get("seen_mood")
        .unwrap()
    {
        OutputValue::Float(v) => assert!((v - 0.42).abs() < 1e-6),
        other => panic!("wrong kind: {other:?}"),
    }
}
