//! What a script reads per frame (plan §4 R3): bus signals, `dt`, `time`, playback position, an
//! `idle` flag. Borrowed, not owned — `ScriptEngine::tick` builds one of these per frame and
//! hands it to every declared script in order.

use hyst_core::SignalBus;

pub struct FrameInput<'a> {
    pub dt: f32,
    pub time: f32,
    pub playback_position: f32,
    pub idle: bool,
    pub bus: &'a SignalBus,
}
