# Hysteresis — Master Project Prompt

## 0. What this document is
A single reference for scope, architecture, and priorities for Hysteresis, an
audio-reactive patchbay for driving screen visuals, LEDs, DMX lighting, and
lasers from music. Use this to brief contributors, scope milestones, or
re-anchor a design conversation that's drifted.

## 1. Positioning (one paragraph)
Hysteresis is a patch-based instrument that turns music into a rich,
named stream of signals — spectral, structural, and temporal-memory — and
lets users wire those signals to *anything*: a built-in fractal renderer,
a user-written shader, a strip of LEDs, a DMX rig, or a laser. It is not
trying to out-feature TouchDesigner as a general compositor, and not trying
to out-feature QLC+ as a lighting console. Its wedge is being the one tool
where the *same graph* drives screen and physical light together, informed
by audio understanding richer than raw FFT bins.

## 2. Non-goals (say these out loud so scope doesn't creep)
- Not a general-purpose node-based compositor (not competing with TD/Notch on generality).
- Not a full lighting console (not replacing GrandMA/Chamsys for complex theatrical rigs).
- Not a DAW. Audio is input, not something authored inside the tool.
- Not trying to replace ISF/Shadertoy as shader ecosystems — adopt and extend them, don't reinvent.

## 3. Architecture decision: stay web, add a native bridge (do not fully port)

**Verdict: keep the webapp as the core. Ship a small local "Bridge" companion
process for hardware I/O that the browser cannot reach directly.** Rationale:

- WebGPU now has broad support across Chrome/Edge/Firefox/Safari, so
  GPU-bound rendering (fractals, shaders, kaleidoscope effects) is not a
  reason to leave the browser.
- The real gap is hardware: there is no browser API for Art-Net/sACN (raw
  UDP), and the closest fits — Web Serial (USB-DMX dongles) and Web MIDI —
  are Chromium-desktop-leaning; Safari has an explicit opposed position on
  Web Serial over fingerprinting concerns, and neither has real mobile
  support. This is a protocol problem, not a "browser is too weak" problem.
- Every native lighting tool solves this the same way: an external
  interface/bridge process (Enttec dongle drivers, Art-Net nodes,
  ILDA DACs). Nothing is "natively" in-app even in TouchDesigner or QLC+.
  So the standard-practice answer is: **webapp UI/engine + a tiny local
  Hysteresis Bridge daemon** that:
  - Speaks Art-Net, sACN, raw DMX (via USB-serial dongles), and ILDA/laser
    protocols on the hardware side.
  - Speaks WebSocket + OSC to the webapp on the other side.
  - Runs as a lightweight local service (installable via npm/cargo, or as
    a signed background app) — the browser connects to `localhost` like
    talking to a local dev server.
- This preserves 100% of the existing web codebase, keeps the update/deploy
  story simple (still a webapp for the 95% of usage that's screen-only),
  and isolates the "needs native/OS access" surface to one small,
  replaceable component.
- Revisit full native (Tauri-wrapping the existing web code is the cheap
  upgrade path, not a rewrite) only if: (a) WebGPU ceiling is genuinely hit
  for the heaviest patches, or (b) offline/installer distribution and
  OS-level low-latency audio device access become recurring user
  complaints. Neither is true today — don't pre-optimize for it.

## 4. Core pipeline (target shape)

```
[Audio Source] → [Feature Engine] → [Signal Bus] → [Patchbay Graph] → [Output Adapters]
     ↑                  ↓
  (sidecar          (memory/state:
   import/export)    novelty, similarity,
                      section tracking)
```

### 4.1 Audio Source
- Live input (mic/line/device) and file playback, at minimum.
- **Sidecar format**: a portable, versioned JSON/binary artifact that stores
  precomputed per-frame features + detected structure for a given audio
  file, keyed by a content hash (not filename) so it survives renames.
  Should be tool-agnostic enough that someone could generate one with
  Python/librosa offline and hand it to Hysteresis.
- Sidecar should be diffable/inspectable (don't make it an opaque blob) —
  helps debugging and lets advanced users hand-edit or augment it.

### 4.2 Feature Engine
Two tiers of signal, both first-class and patchable:

- **Instantaneous features** (per-frame, no memory needed): RMS/loudness,
  spectral centroid, spectral bands (configurable N-band split, not fixed
  low/mid/high), spectral flux, onset strength, pitch/key estimate where
  applicable, stereo width/pan.
- **Temporal/structural features** (this is the differentiator — protect
  it from being an afterthought): 
  - Novelty curve (how different is "now" from the recent past)
  - Self-similarity against a rolling window (for phrase/loop detection)
  - Section-change / boundary detection (verse/chorus/drop-style shifts)
  - "Build" and "drop" heuristics as derived, tunable signals — not magic
    booleans, but continuous confidence values the user can threshold
    themselves in the patchbay
  - Tempo/beat phase, bar position when derivable
- Feature Engine should be swappable/extensible — expose a plugin
  interface so power users can add custom analyzers (steal TouchDesigner's
  VST-hosting pattern: treat an analyzer like a pluggable unit with typed
  outputs, not a hardcoded internal).

### 4.3 Signal Bus
- Every feature is a named, typed, timestamped stream (float, vector,
  event/trigger, or boolean-with-confidence).
- Bus should support recording/scrubbing for offline editing against a
  sidecar (author your patch against a fixed timeline, not just live).
- OSC-compatible addressing scheme for signal names, so external tools
  (Ableton, TouchDesigner, VCV Rack) can send/receive against the same bus
  without a translation layer.

### 4.4 Patchbay Graph
- Node-graph UI, live state visible on every node (inline value/waveform,
  not just on click — this is the VDMX-style bar to hit).
- Nodes are typed by signal kind; connections type-check visually.
- Support for macro/grouped nodes (save a sub-patch as a single reusable
  block — this is what turns "patch spaghetti" into a shareable prefab).
- Undo/redo and versioning on the graph itself, not just the project file.

### 4.5 Output Adapters — the "drive anything" layer
This is where ISF adoption matters most.

- **Screen/shader outputs**: adopt **ISF (Interactive Shader Format)** as
  the primary scripting surface for visuals, not a bespoke format.
  - ISF = GLSL fragment shader + JSON header declaring typed inputs.
    Hosts auto-generate UI controls from the header — steal this pattern
    directly for how the patchbay auto-exposes a script's parameters as
    patchable nodes.
  - Ship compatible with the existing ISF ecosystem (hundreds of
    free generators/effects, plus Shadertoy→ISF conversion tooling) so
    users get a prefab library on day one instead of you hand-authoring
    dozens of visual effects from scratch.
  - Extend ISF's input types with your own: expose Feature Engine outputs
    (novelty, similarity, section-confidence) as first-class typed inputs
    a shader can declare it wants — this is the part no existing ISF host
    does, and it's your actual novelty.
  - Built-in prefabs (Julia fractal w/ zoom/rotation/C automation,
    oscilloscope, kaleidoscope) should themselves be written *as* ISF (or
    your ISF-superset) scripts, not special-cased native code — dogfood
    the extensibility layer so it's provably not a second-class citizen.
- **Physical outputs** (LEDs/strips/servos/DMX/lasers): unify under one
  adapter interface (`OutputAdapter.write(frame_of_typed_values)`), with
  protocol-specific adapters underneath:
  - DMX via USB dongle (through the Bridge)
  - Art-Net / sACN over network (through the Bridge, or directly if
    running on a platform with raw UDP access)
  - ILDA/laser via a DAC (Bridge-mediated; this is the underserved
    protocol — no current tool cleanly unifies laser + DMX + shader under
    one graph)
  - Generic addressable LED strip protocols (WLED/E1.31 is a reasonable
    first target since it rides on sACN and has a large hobbyist install
    base)
- Fixture/profile system for physical devices, borrowing QLC+'s model:
  reusable fixture definitions (channel counts, pan/tilt ranges, color
  models) rather than raw channel-number patching every time.

### 4.6 Export / Presentation Mode
- A distinct, stripped-down runtime target: given a finished project +
  audio (or sidecar), play it back reliably without the authoring UI
  overhead. This is your "burn to a show file" step.
- Should support: fixed showfile playback (offline-rendered timeline) and
  live-reactive playback (same patch, live audio in) as two distinct
  export modes — don't conflate them.

## 5. Protocols to explicitly support (priority order)
1. **ISF** (visual scripting/prefab compatibility) — highest leverage, do first. ✅ done (§6).
2. **OSC** (signal bus interop with the wider creative-coding world). ✅ done, both directions (§6).
3. **Art-Net / sACN** (network DMX — most common in modern lighting rigs). ✅ done (§6) — now has a real production fixture pipeline (`FixtureOutput` in the render worker); USB/Web Serial stays editor-tool-only (see §6).
4. **DMX512 via USB-serial** (Bridge-mediated; covers dongle-based setups). ✅ done (§6) — NOT Bridge-mediated after all, turned out to be the one protocol Web Serial reaches directly.
5. **MIDI** (both control input — mapping a knob to a patch parameter —
   and MIDI clock/beat sync from a DAW). ✅ control input done and routable
   via a `midiCc` patch-graph node (§6); clock/beat sync still not wired
   into the Conductor's own tempo tracking.
6. **ILDA / laser DAC support** (Bridge-mediated; smaller user base but a
   real differentiator since nothing unifies this with the rest cleanly).
   ✅ protocol layer done (§6) — real ILDA file format + Ether Dream
   codecs, researched and cross-checked against real implementations (not
   guessed); no patch-graph laser point source or live client yet.
7. **WLED/E1.31** as a friendly on-ramp for hobbyist LED strip users
   before they touch raw DMX. ✅ done (§6) — WLED's own native realtime
   UDP protocol, reusing the same sACN/Art-Net universe rendering.

## 6. Concrete feature backlog (pulled from competitive research)

- [ ] Sidecar format spec (versioned schema, content-hash keyed). Partial:
      the schema-2 sidecar (`src/shared/sidecar.ts`) exists and is
      versioned, but it's filename/URL-keyed (a track's `sidecar` field),
      not content-hash-keyed yet.
- [ ] Feature Engine plugin interface (custom analyzer support).
- [x] ISF import + auto-generated patchbay node UI from ISF JSON header —
      real single-pass subset (float/bool/long/color/point2D inputs;
      multi-pass/PERSISTENT/image/audio inputs explicitly rejected with a
      clear error, not silently mis-rendered). Loadable both from the
      patchbay editor tool AND as real public API
      (`VizInstance.loadIsfShader()`/`clearIsfShader()`, see
      `docs/isf-shaders.md`) — opt-in, so the production site's background
      still ships the built-in Julia scene unless a host explicitly calls
      it. Whether the real site itself should ever do so is a separate,
      not-yet-made product decision (see AGENTS.md).
- [ ] ISF superset spec: additional input types for temporal/memory signals
      (novelty, similarity, section-confidence) a shader could declare it
      wants — not started; this session's ISF work is spec-compliant
      single-pass ISF only, no Hysteresis-specific extension yet.
- [ ] Shadertoy → ISF import helper (mind licensing/attribution on ported shaders).
- [ ] Live inline node state visualization (waveform/value preview per node).
- [ ] Macro/sub-patch save-as-reusable-block.
- [~] Hysteresis Bridge daemon: Art-Net/sACN/DMX-serial/ILDA ↔ WebSocket+OSC.
      Partial, narrower than originally scoped: `scripts/udp-relay.ts` is a
      real, working WebSocket↔UDP forwarder covering OSC/Art-Net/sACN, NOT
      a full daemon speaking every protocol itself — it does no protocol
      encoding at all, just moves bytes. DMX-serial turned out not to need
      a bridge/daemon at all (Web Serial reaches USB-DMX dongles directly
      from the browser — see `docs/dmx-out.md`). ILDA still unaddressed.
- [ ] Fixture profile system for physical devices (QLC+-style reusable definitions).
- [ ] Presentation/export mode: fixed showfile vs. live-reactive export paths.
- [x] Art-Net / sACN output. Real spec-shaped packet encoders
      (`src/dmx/artnet.ts`/`sacn.ts`), fixture→universe rendering
      (`src/dmx/render-dmx-universe.ts`), sent via the same relay OSC uses
      (`scripts/udp-relay.ts`, generalized this session to carry a
      per-message JSON envelope alongside OSC's raw passthrough) — see
      `docs/dmx-out.md`. **Now wired into production**: `FixtureOutput`
      (`src/render/conductor/outputs/FixtureOutput.ts`) runs a real fixture
      `PatchGraphEvaluator` inside the shipped render worker, driven by
      `VizInstance.setFixtureDocument()`/`setFixtureGraph()`/
      `setFixtureOut()` — a host embedding this package can now drive real
      Art-Net/sACN/WLED fixtures, not just the patchbay editor. No
      16-bit/fine-channel support, no fixture-profile import (GDTF/QLC+).
- [~] DMX512 via USB-serial. Real Enttec DMX USB PRO Widget API framing
      (`src/dmx/enttec-usb-pro.ts`) sent via genuine Web Serial
      (`src/dmx/dmx-serial-output.ts`) — the one §5 protocol that reaches
      real hardware straight from the browser, no relay/Bridge daemon
      needed, because the dongle's own firmware generates the actual DMX
      signal/break. Chromium-desktop-only (Web Serial isn't implemented
      elsewhere); a raw "Open DMX USB"-style dongle (host generates the
      break itself) isn't reachable this way at all — see `docs/dmx-out.md`.
      **Still editor-tool-only, deliberately**, unlike Art-Net/sACN/WLED
      above: Web Serial's `requestPort()` needs a main-thread user gesture,
      which a background render worker can never trigger — there's no
      obvious production wiring for this leg without a different mechanism
      (e.g. the host page obtaining the port and transferring it in).
- [~] MIDI: control input + clock/beat sync. Real MIDI 1.0 message parsing,
      a clock tracker (24-tick/quarter-note timing → live BPM + beat/bar
      phase, shape-compatible with the live-audio `BeatTracker` for a
      future Conductor integration that hasn't happened), a CC input model
      with 0..1 normalization and a "MIDI learn" primitive, and real Web
      MIDI wiring (`src/midi/`) — see `docs/midi.md`. **Now routable**: a
      `midiCc` patch-graph node kind (`patchgraph/types.ts`) reads a live
      CC value the same way a `signal` node reads a bus field, and
      `VizInstance.connectMidiIn()` forwards every real CC message to the
      render worker for it to read from. Real Web MIDI, meaningfully
      broader browser support than Web Serial (desktop + Android
      Chrome/Edge, Safari 17+). Clock sync into the Conductor's own tempo
      tracking is still not wired (see the MIDI clock sync backlog item
      below).
- [x] WLED/E1.31 on-ramp. Real WLED "DRGB"/"WARLS" UDP realtime protocol
      encoders (`src/dmx/wled.ts`), reusing the exact same universe
      rendering and relay Art-Net/sACN use — a patched `rgb` fixture run
      IS a plain sequential pixel stream once addressed contiguously from
      1, so no separate LED-strip fixture model was needed. Also reachable
      today by just pointing a WLED device at sACN directly (WLED speaks
      it natively) — this mode is specifically for not needing to think
      about sACN/universes at all, which is the actual "friendly on-ramp"
      ask. See `docs/dmx-out.md`. **Now wired into production** the same
      way as Art-Net/sACN above — `FixtureOutput`'s `setFixtureOut()`
      accepts `wled-drgb` as a protocol like any other.
- [~] ILDA / laser DAC protocol layer. Real ILDA file-format codec
      (`src/ilda/ilda-format.ts`) and real Ether Dream live-DAC protocol
      codec (`src/ilda/ether-dream.ts`) — both researched via WebSearch/
      real reference implementations rather than guessed, per an explicit
      earlier decision not to fabricate a binary spec (see `docs/ilda.md`
      for the exact sources and a real error the cross-check against two
      independent implementations caught). A TCP↔WebSocket relay
      (`scripts/tcp-relay.ts`, Ether Dream's TCP session needs a different
      relay shape than Art-Net/sACN/OSC/WLED's UDP `udp-relay.ts`) is real
      and end-to-end tested. **Not done**: no browser-side client driving
      the actual prepare/data/begin command sequence, and no patch-graph
      concept of "a stream of laser points" at all yet (no fixture/target
      exists for it, unlike DMX's dimmer/RGB/servo types) — this is real,
      separate design work, not started.
- [x] OSC in/out on the signal bus for external tool interop. OSC **out**:
      a real OSC 1.0 codec (`src/osc/`), every routable bus signal
      streamed as `/hysteresis/bus/<name>` at 20Hz over a WebSocket, real
      public API (`VizInstance.setOscOut()`), plus a local relay
      (`npm run udp-relay`, browsers have no raw UDP) — see `docs/osc.md`.
      OSC **in**: an `oscIn` patch-graph node kind reads a live incoming
      message's value by OSC address, fed by `OscInBridge`
      (`src/osc/osc-in-bridge.ts`) decoding real packets the relay forwards
      from an `--osc-in-port` inbound UDP listener — real public API
      (`VizInstance.setOscIn()`). No address pattern matching (exact match
      only) and no live-value-log UI in the editor yet.
- [x] MIDI CC mapping to patch parameters — see the MIDI entry above (§5).
      MIDI clock sync into the Conductor's own tempo tracking is still not
      wired (`MidiClockState`'s shape was chosen to be compatible with a
      future integration, but nothing consumes it that way yet).
- [ ] Graph versioning/undo distinct from project-file save.

## 7. Design principles to hold onto
- **Signals are typed and named, never magic.** "Drop detected" should be
  a thresholded view of a continuous, inspectable confidence signal, not
  an opaque boolean the user can't tune or distrust.
- **Prefabs are real citizens of the scripting layer, not hardcoded
  exceptions.** If the built-in Julia fractal can't be forked/edited the
  same way a user's custom ISF script can, the extensibility story is fake.
- **Don't reinvent formats the ecosystem already agreed on.** ISF for
  shaders, OSC for signal interop, Art-Net/sACN for networked lighting —
  adopt these so users bring existing assets/rigs instead of starting over.
- **Physical and screen output are peers, not a bolted-on afterthought
  to a video tool.** This is the actual competitive gap — protect it in
  every architecture decision (e.g., don't let the Output Adapter
  interface silently assume "frame = image").

## 8. Open questions worth resolving early
- Licensing stance on imported/ported ISF and Shadertoy content (CC
  variants differ; needs a clear policy before the prefab library ships).
- How much of the Bridge daemon needs code-signing/notarization for
  smooth install on macOS/Windows given it's doing raw serial/network I/O.
- Whether sidecar generation should ever require server-side compute
  (heavier MIR models) or must remain fully client-side/offline-capable.
