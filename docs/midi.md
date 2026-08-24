# MIDI in

Reads real MIDI input — control-change knob/fader movements and clock/beat
sync from a DAW or hardware sequencer — via the browser's
[Web MIDI API](https://developer.mozilla.org/en-US/docs/Web/API/Web_MIDI_API).
Genuinely browser-native, like DMX-serial: no relay process needed, and Web
MIDI has meaningfully broader support than Web Serial (Chrome/Edge on
desktop and Android; Safari added it in 17+).

## Trying it

In the patchbay editor's 🐞 Debug drawer, open **MIDI in**, click **Connect
MIDI** (grants permission and attaches to every currently-connected MIDI
input port), then move a knob/fader or start a DAW's MIDI clock output. You
should see:

- **Recent CC activity** — `CC <channel>:<controller>: <0..1 value>` for
  the last few controls touched.
- **Clock** — a live BPM estimate, "confidence" (ramps up over the first
  beat as timing samples accumulate), and beat/bar phase (0..1), if the
  connected device/DAW sends MIDI clock (0xF8) ticks.

## What's real here

- **Real MIDI 1.0 message parsing** (`src/midi/midi-messages.ts`) — control
  change, note on/off (including the note-on-velocity-0-means-note-off
  running-status convention), and the system realtime messages clock sync
  needs (Clock/Start/Continue/Stop).
- **A real clock tracker** (`src/midi/midi-clock.ts`) — tracks real
  inter-tick timing (24 ticks/quarter-note, per the MIDI spec) into a live
  BPM estimate and beat/bar phase (4/4 assumed — MIDI clock carries no
  time-signature information), with Start resetting phase/tempo and
  Continue resuming without resetting (the same distinction a real DAW's
  transport draws).
- **A real CC input model** (`src/midi/midi-cc-input.ts`) — normalizes
  MIDI's 0..127 to the 0..1 range every other patchable value in this
  codebase uses, plus a "MIDI learn" primitive (`learnNext()`) for the
  standard "click learn, then wiggle the physical knob" UX.
- **Real Web MIDI wiring** (`src/midi/midi-input.ts`) — `navigator.
  requestMIDIAccess()`, attaches to every connected input port, re-attaches
  on device hotplug (`onstatechange`).

## Status today

- **Diagnostic-only, not yet routable.** Unlike ISF inputs or fixture
  channels, a MIDI CC value isn't a patch-graph target you can wire a
  `signal`/`curve`/`threshold` chain into yet — this pass proves the real
  device/parsing/clock-tracking path works end to end first. Turning it
  into a real graph input (most likely a new `midiCc` node kind alongside
  `signal`/`const` in `patchgraph/types.ts`) is real, scoped future work,
  not attempted here — see `AGENTS.md`.
- **Clock sync isn't wired into the Conductor's own tempo tracking** (the
  live-audio `BeatTracker`) — `MidiClockState`'s shape was chosen to be
  compatible with that future integration, but nothing consumes it that way
  yet.
- No SysEx handling, no MIDI output (sending clock/CC back out).
