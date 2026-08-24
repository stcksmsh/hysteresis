# AGENTS.md — sinteza-viz (published as `hysteresis` on GitHub, pending rename)

The single AI-facing reference for this repo: what it is, how it's built today, where it's
going, and the full session-by-session history. This file absorbs what used to be five separate
docs (`SINTEZA_VIZ.md`, `SINTEZA_SIGNAL_BUS.md`, `hysteresis-master-prompt.md`,
`NEXT_SESSION_PROMPT.md`, and this file's own prior self) — they drifted from each other (most
visibly: `SINTEZA_SIGNAL_BUS.md`'s original spec described a flat Patchbay/Route model a later
addendum in the same file said was retired) and are gone now, folded in below. `docs/*.md`
(`isf-shaders.md`, `dmx-out.md`, `midi.md`, `osc.md`, `ilda.md`, `patchbay-editor.md`) are
**not** part of this merge — those are real per-protocol reference docs meant for human users
too, kept separate on purpose.

Read in this order: §1 (what this is) → §2 (current architecture) → §3 (target architecture &
backlog) → §4 (Layer 2 understanding spec) → §5 (resume / operating mode) → §6 (session history,
the detailed "how we got here" appendix — long, chronological, trust it over any summary above
when they conflict).

---

## 1. What this is

A WebGL2 music visualizer package (`the СИНТЕЗА visualizer` / "sinteza-viz") consumed by
`stcksmsh/stcksmsh.github.io` as a persistent site-wide background, and — per §3's broader
target — the seed of a general audio-reactive patchbay instrument ("Hysteresis") that can drive
screen visuals, LEDs, DMX lighting, and lasers from the same signal graph.

**Naming.** *The СИНТЕЗА visualizer* is the signature audio-reactive surface of the СИНТЕЗА
design system, not a separately-branded product. **HYSTERESIS is the internal technical
principle** driving the core layer: a system whose visible output depends on its whole history,
not just the current input — the feedback memory field literally renders this. "Hysteresis" is
also the working name of the broader patchbay-instrument project this package is growing into
(§3).

**The thesis (why the memory field is the whole point).** Almost every audio visualizer is
memoryless: this frame reacts to this instant, then forgets. The СИНТЕЗА visualizer is built on
the opposite principle — the image itself accumulates history. A feedback field continuously
smears, flows, and decays past states into the present, so the screen is a slowly-evolving
record of the last few seconds of the song, not a snapshot. The emotional arc this produces maps
onto electronic music structure and is the spine of all choreography: **MEMORY → PROCESSING →
RESOLUTION** — the field accumulates (energy loads into the feedback buffer over a build), the
flow reorganizes what it holds (domain-warp churns and densifies), an event resolves it into a
single gesture (the drop discharges the field). Maximalism is on-brand but *earned by the
memory*, never piled on: if a visual element isn't wired to memory/energy/event state, it doesn't
ship.

**Also part of the thesis (§4 below): musical *understanding* is the actual moat, not the
renderer.** Anyone can render a Julia set and send Art-Net. Almost nobody exposes musical
understanding with memory and structure — beat phase that survives silence, novelty against the
recent past, section structure, salience of prominent elements. Everything visual is a consumer
of that understanding, not the product itself.

---

## 2. Current architecture

Framework-agnostic package the host mounts once via `init(canvas, opts)` (`src/index.ts`,
`VizOpts`/`VizInstance` — see `README.md` for the real call signature). No DOM ownership beyond
the canvas, no routing, no player, no knowledge of the site.

```
[Audio Source: live worklet | sidecar]
        │
        ▼
Layer 1 — the ear (src/audio/worklet/)         AudioWorklet, audio thread
   FFT, perceptual bands, centroid, flatness, spectral flux/onsets, waveform ring buffer
        │
        ▼
Layer 2 — the sense (src/audio/worklet/brain/, src/audio/StructureSource.ts)
   beat/bar tracking, build/drop/break detectors, sidecar fusion (structure prefers
   sidecar when loaded; detail is always live)
        │
        ▼
Conductor (src/render/conductor/Conductor.ts)   → produces the Signal Bus, output-blind
        │
        ▼
Signal Bus (src/render/conductor/types.ts)      flat, named, timescale-tagged signals — THE
        │                                        cross-boundary contract
        ▼
PatchGraph (src/render/conductor/patchgraph/)   node-graph engine: signal/const/threshold/
        │                                        envelope/logic/combine/curve/map/target/
        │                                        midiCc/oscIn nodes, topologically evaluated
        ▼
VizOutput[] (src/render/conductor/outputs/)     peers behind one interface, pull model:
                                                  ScreenOutput (production), FixtureOutput
                                                  (Art-Net/sACN/WLED, production)
```

**Layer 1 — the ear** (`src/audio/worklet/`): `feature-worklet.ts` (`FeatureProcessor extends
AudioWorkletProcessor`, registered `'feature-processor'`) runs a windowed FFT (`fft.ts`,
`WindowedFFT`) per hop, perceptual band split sub/low/mid/presence/air (`bands.ts`, each band
smoothed by an `EnvelopeFollower` + `AdaptiveNormalizer`), spectral centroid/flatness
(`spectral.ts`), spectral-flux onset novelty (`onset.ts`, `SpectralFlux`), stereo pan, and emits
a `StateFrame` (`src/shared/types.ts`) every hop via `postMessage`.

**Layer 2 — the sense** (`src/audio/worklet/brain/`): `beat-tracker.ts` (`BeatTracker`/
`BarTracker` — tempo + a phase-locked oscillator that free-runs through silence/breaks),
`build-detector.ts`, `break-detector.ts`, `drop-detector.ts` (`DropDetector` — fires on a
conjunction of **fullness** — multi-second sustained low-band energy, crest-factor-penalized so a
pulsing reverb tail doesn't read as full — **onset-density jump**, and **novelty contrast**
against a 4s window, OR the same fullness+novelty pair alone for rhythm-free "soft" drops;
`getDebug()` exposes the three raw values). `novelty.ts` is the shared primitive
(`cosineSimilarity`, `NoveltyRingBuffer`) both `DropDetector` and the render-side
`familiarity.ts` build on, as two separate instances (different threads/cadences). Detectors are
gated by a runtime `debugSetDetectorsEnabled` toggle for the groove-reactivity acceptance test
(§3's history has the details).

`src/audio/StructureSource.ts` fuses a precomputed sidecar (`src/shared/sidecar.ts`, schema
2 today — see §4 for the schema-3 work landing alongside it) with live Layer 1/2 output:
`fuse(frame, positionSec)` overlays sidecar structure (tempo, beat/bar phase, buildProgress,
tension, structural events) onto an otherwise-live `StateFrame`; `synthesize(positionSec)` builds
a **complete** `StateFrame` from the sidecar alone with no live audio at all (the SoundCloud/
cross-origin-embed case — `idle: true` is set deliberately here so the beam plays its idle
Lissajous instead of a fake trace, everything else is genuine track structure). Both self-heal a
backward position jump (`healPositionRegression()`) since an external widget's position feed
isn't guaranteed monotonic.

**Conductor → Signal Bus** (`src/render/conductor/Conductor.ts`, `types.ts`): the (renamed,
widened) former `Choreographer`. Output-blind by construction (no WebGL/canvas/Scene/serial
imports — a grep test). Produces a `SignalBus` every frame: `TimescaleTag = 'transient' | 'beat'
| 'bar' | 'section' | 'continuous'`, `SIGNAL_TAGS` maps every routable field to its tag.
Continuous group (alive every frame — the fix for the old "amplitude follower" failure mode):
`energy, sub, low, mid, presence, air, bandTilt, centroid, flatness, pan, familiarity, hueDrift`.
Beat: `beatPhase, beatPulse`. Bar: `barPhase, downbeatPulse`. Section (sparse, dramatic):
`buildWindup, buildProgress, tension, suspension`. Transient: `dropImpulse, onsetImpulse` (+
internal-only `dropTrigger`). Pass-through (raw, exempt from scalar/tag rules): `scope`. Meta:
`idle, tempoBpm, tempoConfidence`. `familiarity` (`familiarity.ts`, `FamiliarityTracker`) is a
time-bucketed ring buffer (~12s window) of `[sub,low,mid,presence,air,centroid,flatness]`
vectors; each frame, cosine-similarity the current vector against a strided sample of the buffer
→ 0..1 "how much does now resemble the recent past."

**PatchGraph** (`src/render/conductor/patchgraph/`): the *only* live routing engine —
`PatchGraph`/`PatchGraphEvaluator`, a small operator graph (`signal`, `const`, `threshold`
w/hysteresis, `envelope`, `logic` and/or/not, `combine`, `curve`, `map`, `target`, `midiCc`,
`oscIn` node kinds), topologically evaluated with per-node persistent state, construction-time
validated (throws on error-severity `validatePatchGraph` issues — a hot-swap handler rejects a
bad edit and keeps the previous graph running). `ScreenOutput` consumes `configs/screen-graph.ts`
(migrated from an earlier flat `Patchbay`/`Route` model — that model and its `screen-only.ts`
config are still in the tree, still tested, kept only as the migration's numerically-verified
oracle, not live). Three nonlinear screen composites (`flowStrength`, `symmetry`, `fieldDecay` —
spring/damper + edge-triggered impulse dynamics, `patchbay/screen-composites.ts`) are
deliberately hand-written outside the graph, not generic nodes — considered and rejected as a
graph rewrite, no browser access to re-verify hand-tuned motion math from scratch.

**Outputs** (`src/render/conductor/outputs/`): `ScreenOutput` wraps the existing WebGL2 render
pipeline (Julia substrate, curl-noise memory field, oscilloscope beam, bloom, ISF-shader hot-swap
support) — unchanged internals, just fed by patch-graph-resolved targets instead of a
conductor-produced `ParamBus` directly. `FixtureOutput` is the worker-resident production
counterpart for physical fixtures: renders DMX universes (`src/dmx/render-dmx-universe.ts`) from
a `FixtureDocument` + its own `PatchGraphEvaluator`, sent over a WebSocket relay
(`DmxOutBridge`) to Art-Net/sACN/WLED. Real public API on `VizInstance`: `loadIsfShader()`/
`clearIsfShader()`, `setOscOut()`/`setOscIn()`, `setFixtureDocument()`/`setFixtureGraph()`/
`setFixtureOut()`, `connectMidiIn()`/`disconnectMidiIn()` — all opt-in/additive, no existing
integration calls any of them by default.

**Visual composition** (`src/render/worker/scenes/julia/`, `src/render/worker/passes/`): Julia
substrate (2D escape-time, XaoS-style continuous autopilot — `c` sweeps the Mandelbrot cardioid
boundary, a distance-estimator autopilot pans/zooms toward genuine detail, `JuliaScene.ts`) +
oscilloscope beam (Woscope-style glowing vector, trigger-locked when live audio is attached, idle
Lissajous otherwise) composited into a ping-pong feedback buffer, advected through a shared
curl-noise flow field, decayed by a factor tied to `tension`/section — **this ping-pong buffer is
the signature layer**, the hysteresis principle rendered as an image. Earned symmetry (kaleidoscope
fold-count/mirror-strength) modulates the *sampling coordinate* the memory field reads its own
previous frame through, never the final composited frame, and is always a response (rises with
tension/buildProgress, snaps to full symmetry for ~1 bar on a drop) — never a constant filter.
Bloom + color-grade composite to screen. Onset-particles (a 4th layer) shipped once and was
removed — see §6 for why; don't re-add something similar without addressing why it read as
distracting.

**Idle & power tiers**: no audio → the Julia autopilot keeps running, the beam draws idle
Lissajous, the field keeps flowing/decaying gently — never frozen (except `prefers-reduced-motion`,
which the host handles by disabling the canvas). Tiers `full`/`cheap`/`idle-only` per
`setTier()`.

**Two run modes**: live (mic/line-in → worklet → Conductor → bus, the opening-party case) and
unattended looped playback with precomputed sidecars (best case — look-ahead anticipation via
`StructureSource`) or ambient mic — most of the exhibition's actual runtime, must auto-start and
survive a crash with no keyboard (host/IO-page concern, noted here so it isn't forgotten).

**Offline analysis** (`scripts/analyze.ts`/`scripts/structure.ts`, this repo, not the host):
ingests a WAV master, reuses the *exact* browser worklet modules (FFT/bands/spectral/onset/
beat-tracker/detectors — no reimplementation, no Python/ONNX dependency for the schema-2 path)
in a manual hop loop, downsamples envelopes to 20Hz, emits a schema-2 `<slug>.sidecar.json`:
`{schema:2, tempo, beats[], sections[], events[], onsets[], energyEnvelope[], bandEnvelope,
centroidEnvelope[], flatnessEnvelope[], envelopeRate}`. Produced here, served by the host as a
static asset. §4 below adds a schema-3 path (stem presence) that *does* need an external
dependency (Python + Demucs), scoped narrowly to stay opt-in.

---

## 3. Target architecture & backlog

*(This section is `hysteresis-master-prompt.md` §1–§8, carried over close to verbatim as the spec
of record — it describes where the whole "Hysteresis" project is going, one level broader than
just this package's current state in §2 above.)*

### 3.1 Positioning

Hysteresis is a patch-based instrument that turns music into a rich, named stream of signals —
spectral, structural, and temporal-memory — and lets users wire those signals to *anything*: a
built-in fractal renderer, a user-written shader, a strip of LEDs, a DMX rig, or a laser. It is
not trying to out-feature TouchDesigner as a general compositor, and not trying to out-feature
QLC+ as a lighting console. Its wedge is being the one tool where the *same graph* drives screen
and physical light together, informed by audio understanding richer than raw FFT bins.

### 3.2 Non-goals (say these out loud so scope doesn't creep)

- Not a general-purpose node-based compositor (not competing with TD/Notch on generality).
- Not a full lighting console (not replacing GrandMA/Chamsys for complex theatrical rigs).
- Not a DAW. Audio is input, not something authored inside the tool.
- Not trying to replace ISF/Shadertoy as shader ecosystems — adopt and extend them, don't reinvent.

### 3.3 Architecture decision: stay web, add a native bridge (do not fully port)

**Verdict: keep the webapp as the core. Ship a small local "Bridge" companion process for
hardware I/O the browser cannot reach directly.** Rationale:

- WebGPU has broad support across Chrome/Edge/Firefox/Safari, so GPU-bound rendering is not a
  reason to leave the browser.
- The real gap is hardware: no browser API for Art-Net/sACN (raw UDP); Web Serial (USB-DMX) and
  Web MIDI are Chromium-desktop-leaning, Safari opposes Web Serial over fingerprinting, neither
  has real mobile support. A protocol problem, not a "browser is too weak" problem.
- Every native lighting tool solves this the same way (an external interface/bridge process) — so
  the standard-practice answer is a tiny local **Hysteresis Bridge daemon**: speaks Art-Net/sACN/
  raw DMX (USB-serial)/ILDA on the hardware side, WebSocket+OSC to the webapp on the other.
  Preserves the whole existing web codebase, isolates the "needs native/OS access" surface to one
  small, replaceable component.
- Revisit full native (Tauri-wrapping, not a rewrite) only if the WebGPU ceiling is genuinely hit,
  or offline/installer distribution + OS-level low-latency audio access become recurring user
  complaints. Neither is true today.
- **Status**: `scripts/udp-relay.ts`/`scripts/tcp-relay.ts` are real, working, narrowly-scoped
  seeds of this (byte-forwarding only, no protocol encoding) — not the full daemon. DMX-serial and
  MIDI turned out not to need a bridge at all (Web Serial/Web MIDI reach hardware directly).

### 3.4 Core pipeline (target shape)

```
[Audio Source] → [Feature Engine] → [Signal Bus] → [Patchbay Graph] → [Output Adapters]
     ↑                  ↓
  (sidecar          (memory/state:
   import/export)    novelty, similarity,
                      section tracking)
```

**Audio Source**: live input and file playback, at minimum. Sidecar format: portable, versioned
JSON/binary, per-frame features + detected structure, ideally content-hash-keyed (not filename)
so it survives renames — **not yet true**, today's schema-2/3 sidecar is filename/URL-keyed via
a track's `sidecar` content field (§3.7's backlog). Should be tool-agnostic enough someone could
generate one with Python/librosa and hand it to Hysteresis; diffable/inspectable, not opaque.

**Feature Engine** — two tiers, both first-class and patchable:
- *Instantaneous* (no memory): RMS/loudness, spectral centroid, N-band split, spectral flux,
  onset strength, pitch/key estimate, stereo width/pan. — largely built (§2), chroma/harmonic
  added in §4.
- *Temporal/structural* (the differentiator, protect it from being an afterthought): novelty
  curve, self-similarity against a rolling window, section-change/boundary detection, "build"/
  "drop" as continuous tunable confidence values (not magic booleans), tempo/beat/bar phase. —
  §4 below is the concrete build-out of this tier.
- Should be swappable/extensible: a plugin interface so power users can add custom analyzers
  (TouchDesigner's VST-hosting pattern — an analyzer as a pluggable typed-output unit, not a
  hardcoded internal). **Not started.**

**Signal Bus**: every feature a named/typed/timestamped stream (float, vector, event/trigger, or
boolean-with-confidence). Should support recording/scrubbing for offline patch-authoring against
a fixed sidecar timeline (**not started**). OSC-compatible addressing so external tools
(Ableton, TouchDesigner, VCV Rack) can send/receive against the same bus with no translation layer
— **done**, `/hysteresis/bus/<name>`.

**Patchbay Graph**: node-graph UI, live state visible on every node inline (VDMX-style bar —
**not started**, the editor currently has no per-node live value/waveform preview). Nodes typed
by signal kind, connections type-check visually — **done** (timescale-tag validation). Macro/
grouped nodes (save a sub-patch as a reusable block) — **not started**. Undo/redo and versioning
on the graph itself — **not started**.

**Output Adapters — "drive anything"**: ISF as the primary screen-scripting surface — **done**
(§3.7). Extend ISF's input types with Feature Engine outputs (novelty/similarity/
section-confidence as first-class typed shader inputs) — **not started**, the real differentiator
no existing ISF host has; §4's new signals are what this would expose once built. Physical
outputs unified under one adapter interface, protocol-specific underneath — **done** for DMX/
Art-Net/sACN/WLED/USB-serial (§3.7), ILDA protocol-layer-only. Fixture/profile system (QLC+-style
reusable definitions, not raw channel patching) — **not started**.

**Export/Presentation Mode**: a stripped-down runtime target — fixed showfile playback and
live-reactive playback as two distinct export modes. **Not started.**

### 3.5 Protocols (priority order — all 7 now have real, tested work landed)

1. **ISF** ✅ done.
2. **OSC** ✅ done, both directions.
3. **Art-Net/sACN** ✅ done, real production fixture pipeline (`FixtureOutput`); USB/Web Serial
   stays editor-tool-only (needs a main-thread user gesture a worker can't trigger).
4. **DMX512 via USB-serial** ✅ done — turned out reachable directly via Web Serial, no Bridge
   needed.
5. **MIDI** ✅ control input done, routable via a `midiCc` patch-graph node; clock/beat sync not
   wired into the Conductor's own tempo tracking yet.
6. **ILDA/laser DAC** ✅ protocol layer done (real ILDA file format + Ether Dream codecs,
   cross-checked against real implementations); no patch-graph laser point source or live client
   yet.
7. **WLED/E1.31** ✅ done, reuses the Art-Net/sACN universe rendering.

### 3.6 Design principles to hold onto

- **Signals are typed and named, never magic.** "Drop detected" is a thresholded view of a
  continuous, inspectable confidence signal, not an opaque boolean the user can't tune or
  distrust.
- **Prefabs are real citizens of the scripting layer, not hardcoded exceptions.** If the built-in
  Julia fractal can't be forked/edited the same way a user's custom ISF script can, the
  extensibility story is fake.
- **Don't reinvent formats the ecosystem already agreed on.** ISF for shaders, OSC for signal
  interop, Art-Net/sACN for networked lighting.
- **Physical and screen output are peers, not a bolted-on afterthought to a video tool.** Protect
  this in every architecture decision — don't let the Output Adapter interface silently assume
  "frame = image".

### 3.7 Concrete feature backlog

- [ ] Sidecar format spec: versioned ✅, content-hash-keyed ❌ (still filename/URL-keyed).
- [ ] Feature Engine plugin interface (custom analyzer support) — not started.
- [x] ISF import + auto-generated patchbay node UI — real single-pass subset (float/bool/long/
      color/point2D inputs; multi-pass/PERSISTENT/image/audio inputs rejected with a clear
      error). Loadable from the editor AND as real public API (`loadIsfShader()`/
      `clearIsfShader()`, `docs/isf-shaders.md`) — opt-in, production still ships Julia by
      default.
- [~] ISF superset spec ("the Hysteresis format") — the `hysteresisSignal` input type is real and
      shipped (`src/isf/`, `docs/isf-shaders.md`): a shader can declare it wants any real bus
      signal by name (`noveltyLocal`, `familiarity`, `harmonicNovelty`, per-band energies, the
      sidecar-only presence signals, ...), validated at load time. `HYSTERESIS_SCRIPT` (an
      optional per-file stateful JS companion — needed for anything a single GLSL fragment
      shader can't express, e.g. Julia's own autopilot navigation) is reserved in the parser
      (rejected with a clear error) but its execution engine is not built — real, separate,
      later work, planned as the next phase before porting Julia itself onto this format.
- [ ] Shadertoy → ISF import helper (mind licensing/attribution on ported shaders).
- [ ] Live inline node state visualization (waveform/value preview per node).
- [ ] Macro/sub-patch save-as-reusable-block.
- [~] Hysteresis Bridge daemon — partial (`udp-relay.ts`/`tcp-relay.ts`, byte-forwarding only).
- [ ] Fixture profile system (QLC+-style reusable definitions).
- [ ] Presentation/export mode (fixed showfile vs. live-reactive).
- [x] Art-Net/sACN output — production (`FixtureOutput`), no 16-bit/fine-channel, no
      fixture-profile import.
- [~] DMX512 via USB-serial — real, editor-tool-only (Web Serial's `requestPort()` needs a
      main-thread gesture).
- [~] MIDI: control input + clock/beat sync — CC input real and routable (`midiCc` node); clock
      sync into Conductor tempo tracking not wired.
- [x] WLED/E1.31 on-ramp — production, reuses Art-Net/sACN universe rendering.
- [~] ILDA/laser DAC protocol layer — real codecs, no live client, no patch-graph laser concept.
- [x] OSC in/out on the signal bus — both directions real, no address-pattern matching (exact
      match only) for OSC-in.
- [x] MIDI CC mapping to patch parameters.
- [ ] Graph versioning/undo distinct from project-file save.
- [x] **Online multi-scale novelty (`noveltyLocal`/`noveltySection`) + beat-synchronous feature
      aggregation** — §4 below. `noveltyLocal`/`noveltySection` real bus signals, both pushed
      only on beat-boundary edges (`Conductor.ts`).
- [x] **`onsetDensity`/`fullness` as real, generally-routable bus signals** — extracted from
      `DropDetector`'s internals into `src/audio/worklet/brain/activity.ts`
      (`FullnessTracker`/`OnsetDensityTracker`), now always-alive (not detector-gated) and on
      the bus.
- [x] **Chromagram + `harmonicNovelty`** — `src/audio/worklet/chroma.ts`, `chromaRootHue`
      too. First harmonic sense this pipeline has ever had.
- [x] **Schema-3 sidecar: per-stem presence via offline Demucs separation**
      (`vocalPresence`/`drumsPresence`/`bassPresence`/`otherPresence`) — `scripts/analyze.ts
      --stems`, shells out to the real Python Demucs CLI. **Verified end-to-end against a real
      track** (Daft Punk — Instant Crush, 5:40) in a follow-up session, see its own §6 entry.
- [x] **Heuristic sidecar section labeling** (intro/build/breakdown/outro — deterministic rules,
      not ML) — `scripts/structure.ts`'s `labelSections()`.
- [x] **Lead-salience tracking within the separated `other` stem** (approximate) —
      `leadPresence`, a per-hop sustained-spectral-peak tracker, part of the same `--stems` pass.

### 3.8 Open questions worth resolving early

- Licensing stance on imported/ported ISF and Shadertoy content (CC variants differ).
- How much of the Bridge daemon needs code-signing/notarization for smooth install on macOS/
  Windows given it does raw serial/network I/O.
- Whether sidecar generation should ever require server-side compute (heavier MIR models) or must
  remain fully client-side/offline-capable. **§4's Demucs stem-presence step is a real instance
  of this question**: it requires a local Python + `demucs` install to run `scripts/analyze.ts
  --stems` — deliberately kept an opt-in, manual, per-track offline step (not a build/CI/hosted
  dependency), consistent with "must remain offline-capable" until this question gets a real
  answer.

---

## 4. Layer 2 musical understanding (СИНТЕЗА) — the moat, in detail

*(This section is `SINTEZA_UNDERSTANDING.md`, folded in near-verbatim as the detailed spec behind
§3.7's new backlog items above. It assumes §2's current architecture — Layer 1 worklet, Layer 2
brain/`StructureSource` sidecar fusion — already exists; it does not re-describe them.)*

### 4.0 The thesis (why this layer is the whole product)

Anyone can render a Julia set and send Art-Net. Almost nobody exposes *musical understanding*
with memory and structure — beat phase that survives silence, novelty against the recent past,
section structure, salience of prominent elements. That understanding is the differentiator (the
"moat"). So this layer is not plumbing for the renderer; it is the thing worth building, and
everything visual is a *consumer* of it.

The organizing principle, because it decides what is buildable:

> **Structure & novelty are cheap, robust, and can run live. Source identity ("that's the vocal
> / the lead synth") is expensive and is only tractable the way this project actually needs it:
> OFFLINE, in the sidecar, for your own tracks.**

This is the same live-vs-sidecar split already adopted for drops (§2's `DropDetector` vs.
sidecar-primary drop gating), pushed one level deeper. Every ambition below is sorted into
**LIVE-CAPABLE** (runs in the worklet, works on unknown audio at the party) or **SIDECAR-ONLY**
(precomputed, look-ahead, own-tracks, hand-correctable). Do not try to make a sidecar-only
capability run live.

### 4.1 What the field actually does (grounded)

**Structure = novelty, homogeneity, repetition, read off a Self-Similarity Matrix (SSM)**: a
feature per time-unit, compared to every other unit (cosine/centered-cosine/RBF) — structure
appears as blocks (homogeneous sections) and diagonal paths (repetitions). The Foote (2000)
lineage, still the backbone of state-of-the-art unsupervised methods.

**Boundaries = checkerboard-kernel novelty.** Correlate a checkerboard kernel along the SSM
diagonal; peaks = section boundaries. Kernel size sets the timescale — small kernel → phrase-
level ("a fill happened"), large kernel → section-level ("the chorus started"). Expose both
scales, not one.

**Beat-synchronous features are the pro move.** Aggregate to the beat grid before building the
SSM — tempo-invariance, denoises everything.

**EDM-specific, a studied problem.** DJ-mix cue-point/switch-point detection research finds the
most predictive features for a structural transition are: novelty in signal energy, novelty in
timbre, number of drum onsets, and harmony — drum-onset-density called out explicitly. This
independently validates §2's fullness/onset-density-jump drop-detector redesign, and that padding
loudness novelty with zeros at the track start (vs. the no-data value) is what makes intros
behave.

**Modern (optional, heavy) ceiling.** SOTA MSA uses learned SSM features, demixed-audio structure
models, LLM/embedding zero-shot labeling. Flagged as the ceiling for the sidecar path, not
required — none of this repo's ML-free heuristics attempt to reach it.

### 4.2 LIVE-CAPABLE understanding

Everything here is cheap enough for realtime, correct-enough causally. Runs at the party and on
ambient/line-in input.

- **Already built** (§2): bands, centroid, flatness, spectral-flux novelty, beat/tempo PLL,
  build/break/tension, `familiarity`.
- **Online SSM + multi-scale novelty** (new, §3.7): a ring buffer of beat-synchronous feature
  vectors over the last N beats; each new beat, similarity of the current vector against the
  buffer → a running novelty curve at **two timescales** — `noveltyLocal` (small kernel,
  phrase-scale: a fill, a new element entering) and `noveltySection` (large kernel, section-scale:
  breakdown→drop, verse→chorus). `familiarity` is the same computation read the other way — high
  familiarity = low novelty = a loop repeating. Cost: a bounded ring buffer, a few dot products
  per beat — trivially realtime, and the single highest-value live addition.
- **Drum-onset density & fullness, exposed as real bus signals** (new, §3.7): onset events/sec +
  a fullness signal (energy sustained continuously over a multi-second window, crest-factor-
  penalized) — both already computed inside `DropDetector` but never exposed generally. A drop =
  onset-density AND fullness jump together after a span low on both = a large `noveltySection`
  spike.
- **Chroma/harmonic signals** (new, §3.7): a chromagram (12-bin pitch-class energy) — cheap,
  standard, currently entirely missing from the pipeline. Enables harmonic novelty (key/chord
  changes as a boundary cue, one of the EDM switch-point predictors), a "harmonic tension" proxy,
  and a genuinely new visual driver (pitch-class → hue/rotation). Bass-band chroma alone
  approximates root/bassline movement.
- **NOT live-capable, don't attempt online**: naming sections (needs the whole track), tracking a
  *specific* source (needs separation, §4.3), anything needing real look-ahead (a drop is defined
  by contrast with the build *before* it — live gets a fallback, sidecar gets it right).

### 4.3 "Track prominent elements" — honestly scoped

The want: track the vocal, the main synth, per-section prominent elements. This is source
separation + salience, heavier than structure.

**Feasibility.** Offline separation (HTDemucs v4, ~9dB SDR on 4 stems: drums/bass/vocals/other) is
solved and excellent, runs in Python, is a solved dependency, not research. Real-time low-latency
separation exists but is research-grade and weak (HS-TasNet ~4.6-5.6dB SDR at 23ms — far below
offline quality, nothing drop-in for a web app today). **Conclusion: do not attempt live stem
separation.** "other" is a bucket, not an instrument — even offline, "the main synth" specifically
is approximate (it's whatever's loudest/most sustained inside `other`, alongside pads/FX).

**The design that delivers it: SIDECAR-ONLY, stem-wise structure.** For your own tracks: (1)
offline, in `scripts/analyze.ts`'s pipeline, run separation once (Demucs, shelled out to the
Python CLI — see §3.8's open question on this) → stems vocals/drums/bass/other; (2) per stem,
compute a presence/energy envelope across the whole track — not "what note is the vocal" but "is
the vocal present, and how prominent, right now," which is exactly what "track the prominent
element" visually needs; (3) bake it into the sidecar as new signal lanes
(`vocalPresence`/`drumsPresence`/`bassPresence`/`otherPresence`), schema bump; (4) at playback,
`StructureSource` exposes these as bus signals exactly like existing structure — "vocal enters →
this element blooms," "bass drops out → the field thins," without any live separation.

**Salience within a stem** (optional, harder): a per-section peak-tracker on the `other` stem's
spectrum — the loudest *sustained* band-limited component per section approximates "the lead."
Approximate, a refinement to attempt after stem-presence works.

**Explicit non-goals**: no live vocal/lead tracking (sidecar-only); no pitch-accurate
transcription/MIDI extraction (presence/salience envelopes, not notes); no lyric alignment/word
tracking.

### 4.4 The signal taxonomy this layer adds to the bus

Time/pulse, energy/timbre (LIVE, mostly already have) — unchanged, see §2.

**Rhythmic activity (LIVE, new):** `onsetDensity`, `fullness`.

**Harmony (LIVE, new):** `chroma` (pass-through 12-vector, like `scope`), `harmonicNovelty`,
`chromaRootHue`.

**Structure/memory:** `noveltyLocal`, `noveltySection` — LIVE, new. Section boundaries (precise),
labels — SIDECAR (heuristic labeler, new). Repetition map ("this section = that earlier one") —
SIDECAR, not attempted (needs a full offline SSM this plan doesn't build).

**Source presence (SIDECAR-ONLY, new):** `vocalPresence`, `drumsPresence`, `bassPresence`,
`otherPresence`, `leadPresence` (approximate, within `other`).

### 4.5 Build order (as actually executed this session)

1. Online SSM + multi-scale novelty + beat-synchronous aggregation (one implementation slice —
   the beat-sync push is the same call site the multi-scale trackers use).
2. `onsetDensity`/`fullness` exposed as real, generally-routable bus signals.
3. Chromagram + harmonic novelty.
4. Schema-3 sidecar: stem-presence via offline Demucs (Python CLI subprocess).
5. Heuristic sidecar section labeling (deterministic rules, not ML — no LLM/embedding infra
   exists in this repo and the doc itself flags learned labeling as an optional heavy ceiling).
6. Lead salience within `other` (approximate, rides on step 4's separated stems).

### 4.6 Feasibility summary (the one-screen answer to "can we track the vocal")

| Ambition | Live? | Sidecar? | Verdict |
|---|---|---|---|
| Beat/tempo, phase through silence | ✅ have | ✅ | done |
| Novelty / self-similarity / familiarity | ✅ cheap | ✅ better | build first |
| Section *boundaries* | ⚠️ causal, approx | ✅ precise | live-approx + sidecar-exact |
| Section *labels* (verse/chorus/drop) | ❌ | ✅ heuristic | sidecar only, deterministic |
| Drop/build/break | ⚠️ fallback only | ✅ primary | existing §2 design |
| Harmony/chroma | ✅ cheap | ✅ | build (new sense) |
| Vocal present & how prominent | ❌ | ✅ Demucs offline | sidecar only, viable |
| Drums/bass presence | ❌ live | ✅ | sidecar, clean |
| "The main synth" specifically | ❌ | ⚠️ approx | sidecar, approximate |
| Note-level transcription | ❌ | ❌ | out of scope |
| Live stem separation | ❌ research-grade, weak | n/a | do not attempt |

---

## 5. Resume / operating mode

Non-negotiable constraints, in priority order:

1. **Never break the live production path.** The renderer runs 24/7 unattended on a real site.
   Every commit leaves `npm run typecheck`, `npm test`, `npm run build`, and `npm run build:lib`
   green. If a feature can't be added without regressing this, stop and say so.
2. **Legibility over feature count.** Every UI surface touched must be as usable/readable as the
   patchbay editor's current state — dark theme, clear hierarchy, no dead/hidden controls, real
   labels not ids.
3. **Ship working slices, not partial scaffolding.** Definition of done: does the real thing
   end-to-end, is tested, and is verified (real browser check when visual/interactive — flag
   clearly when browser access isn't available, per §6's many "not verified in a browser" notes).
4. **Protect extensibility.** Prefabs/built-ins must be built *through* the same extension
   mechanism a user would use, never a hardcoded special case beside a thinner "real" API. Ask:
   could a user replace/extend this the same way I just built it?

**Where things stand**: all 7 §3.5 protocols have real landed work; the two biggest recurring
gaps (physical fixtures editor-tool-only, MIDI/OSC not routable in the graph) are closed —
`FixtureOutput` runs in production, `midiCc`/`oscIn` are real graph node kinds, the editor
dogfoods the production fixture API. §4's Layer 2 understanding build order (all 6 steps) also
landed — the Signal Bus now carries `noveltyLocal`/`noveltySection`/`fullness`/`onsetDensity`/
`harmonicNovelty`/`chromaRootHue`/`chroma`/the 5 sidecar-only presence signals — and every one of
those (including the `--stems` Demucs path) has now been verified against a real 5:40 track, not
just synthetic fixtures (see the "headless real-audio test run" §6 entry). **None of these new
signals are wired into any default screen/fixture route yet**, though — deliberately out of
scope for both sessions, still real follow-up work. §3.7's checklist is the source of truth for
what's next — don't assume any older list (§3.5's protocol order) still dictates priority, it's
exhausted.

**Standing caveat across almost everything in §6**: most of it has never been verified against
real hardware or a real browser (no MIDI controller, no external OSC sender, no Art-Net/sACN
receiver, no laser DAC, no browser access in most of these sessions) — typechecked and
unit-tested at the logic layer only. Closing that loop for any one protocol, when real
hardware/browser access is available, is higher-value than starting new scope.

**Operating mode**:
- Gap-analysis first, every time you resume — diff §3.7's checklist against what's actually in
  the repo, don't assume where the last session left off.
- One coherent slice per session; update §3.7's checkboxes as items land.
- Append a dated/titled §6 entry per session — what changed, what's verified vs. not, what's
  explicitly deferred. This is how continuity survives repeated context clears.
- Respect §3.2's non-goals as hard scope boundaries.
- If a decision genuinely needs the user's input (§3.8's open questions, or anything expensive to
  reverse), ask; don't guess and proceed.

---

## 6. Session history (appendix — chronological, detailed, trust this over any summary above)

## Signal bus / patchbay / output refactor (this session, per the then-separate `SINTEZA_SIGNAL_BUS.md`)

`Choreographer`→`ParamBus`→`Scene` (one hardwired consumer) is now `Conductor`→`SignalBus`→`Patchbay`→`VizOutput[]` (peers behind an interface, pull model). Implemented all 6 build-order steps from the spec in one pass:

- **New layout**: `src/render/conductor/` — `Conductor.ts` (widened Choreographer, output-blind — grep-checkable per R1), `types.ts` (`SignalBus`/`TimescaleTag`/`SIGNAL_TAGS`/`VizOutput`), `familiarity.ts` (the online self-similarity signal), `patchbay/` (`Patchbay.ts` evaluator + `curves.ts` + `configs/screen-only.ts` default config + `configs/servo-targets.ts` SPEC ONLY), `outputs/ScreenOutput.ts` (owns the render pipeline moved in from `render-worker.ts` — Scene, memory field/persistence/bloom/composite passes; `Scene`/`SceneContext` themselves are unchanged). `src/render/choreography/` now holds only `spring-damper.ts` (still used standalone by `JuliaScene` for its own `c`-position spring — untouched).
- **Nonlinear composites** (`flowStrength`, `symmetry`, `fieldDecay` — each a `max()`/multi-signal formula, not a 1:1 route): deliberately computed in `patchbay/screen-composites.ts`'s `ScreenParamAssembler` (pure, GL-free, unit-tested directly in `tests/unit/conductor.spec.ts`) rather than forced into the patchbay's 1-signal-in/1-target-out route model. Documented as an intentional deviation from "patchbay owns all routing logic," not an oversight — see that file's header comment.
- **New continuous/beat/bar bus signals**: `bandTilt`, `beatPulse`, `downbeatPulse`, `dropImpulse`, `onsetImpulse`, `familiarity` — `dropImpulse` in particular replaces the old one-frame-true `DropTrigger` push for routing purposes (ScreenOutput edge-detects a rise in it to reconstruct the same one-shot spring-impulse/symmetry-hold behavior, staying pull-model/R2-compliant); the discrete `DropTrigger` still exists as Conductor-internal state per the spec's explicit allowance.
- **Groove reactivity** (step 3): bands/`bandTilt` bias the memory field's curl-noise drift axis (`MemoryFieldParams.flowDirection`, new optional field, no shader/GLSL changes needed — just a JS-side drift-ratio bias), `beatPulse` adds a modest throb into `flowStrength`, `barPhase` adds a subtle sinusoidal "breathing" into `fieldDecay`. Detector-disable acceptance test: new `MainToWorklet` message `debugSetDetectorsEnabled` (main thread → live AudioWorklet, a channel that didn't exist before — `AudioEngine.setDetectorsEnabled()`), gates `feature-worklet.ts`'s build/drop/break detector calls. **Not automated** — verify by hand via `npm run dev` + the debug toggle; screen should stay visibly reactive with detectors off.
- **`familiarity`**: time-bucketed (not fixed-count — frame rate varies under adaptive quality) buffer of `[sub,low,mid,presence,air,centroid,flatness]` vectors, cosine similarity against ~16-32 recent samples. Routed into `symmetry`'s composite as a gentle organization gain, distinct from the drop's snap.
- **Drop detector fix** (`drop-detector.ts`): replaced the fast-minus-slow-energy-jump primitive (conflated "louder" with "sparse→full", false-positived on pulsing reverb-tail sparse intros, missed drops after already-loud builds) with a conjunction of **fullness** (multi-second sustained energy, crest-factor-penalized), **onset-density jump**, and **novelty contrast** (own `src/audio/worklet/brain/novelty.ts` — `cosineSimilarity`/`NoveltyRingBuffer`, the same algorithm `familiarity.ts` reuses, but a *separate instance* since they run on different threads/cadences: audio worklet hop-rate vs. render-frame-rate). Removed the never-resetting cumulative `grooveSec` leak entirely. Confirmation/refractory/startup-grace/beat-snap-lookahead mechanics unchanged. `tests/unit/drop-detector.spec.ts` rewritten for the new primitive (5 tests, same behavioral intents as before — see file for the exact synthetic feature-vector fixtures; tuning these constants (`FULLNESS_THRESHOLD`, `ONSET_JUMP_MIN`, `NOVELTY_WINDOW_SEC`=4 (short, on purpose — independent of familiarity's own ~12s window), `NOVELTY_HOLD_SEC`) against **real audio** hasn't happened yet, only synthetic fixtures — flag as the next thing to sanity-check against real tracks).
- **Sidecar-primary drop gating** (partial): the "true offline whole-track segmentation" half of this was **not** built — `scripts/structure.ts` still replays the (now-fixed) causal `DropDetector` hop-by-hop offline rather than doing genuine look-ahead segmentation; that's real remaining work if the fixed causal primitive isn't good enough replayed offline. What *was* wired: `src/index.ts` now calls `engine.setDetectorsEnabled(false)` whenever a sidecar loads (reusing the same toggle groove-reactivity needed) and `true` on `trackchange`'s clear — since `StructureSource.fuse()` already discards live build/drop/break detector output wholesale whenever a sidecar is active, this stops that output from being computed and thrown away every hop, and removes the live drop detector's false-positive/miss risk for own tracks entirely (sidecar timeline is authoritative).
- **Patchbay test coverage**: `tests/unit/patchbay.spec.ts` — curves, gain/offset/invert, sum-then-clamp multi-route combine, passThrough, and the timescale-tag rejection path validated against `servo-targets.ts`'s declarations (screen accepts every tag, so rejection can't be exercised against it — this is the concrete proof the interface generalizes to a second, physically-constrained output without building one).
- **Explicitly not built**: no `ServoOutput` runtime code, no serial/GPIO transport, no patchbay editor UI, no device manager beyond the literal `const outputs: VizOutput[] = [screenOutput]` array, no `full-physical`/`calm`/`idle` patchbay config variants (only `screen-only` exists).
- **Not covered by a test**: the sidecar→`setDetectorsEnabled(false)` wiring itself lives in `src/index.ts`, which is DOM/Worker-dependent and outside this repo's existing (Node-environment, DOM-free) vitest conventions — no test harness for `index.ts` exists at all, before or after this session. Verify by hand if this specific wiring is ever suspected of a regression.

## Fold seam / Julia zoom follow-up (this session, after the signal-bus refactor above)

User feedback on the live render after the refactor, addressed in three iterations — recorded in full because the first two attempts were each visibly wrong in a way worth not repeating:

- **Kaleidoscope fold seam** (`memory-field.frag.glsl`): reported as a bad-looking horizontal line through the center plus a ~30° wedge that never "smeared." Root cause: the textbook `abs(mod(theta,wedge)-wedge/2)` fold is a 2-to-1 map — exactly half of every wedge sits in the canonical half and maps to itself (`folded(theta) == theta`) *regardless of `uMirrorStrength`*, so that whole half never organizes while its mirrored twin does. First attempt (smoothing the triangle wave into a cosine tent + a quarter-wedge phase offset) only softened the derivative kink; it didn't touch this deeper asymmetry, and the user saw the seam persist (especially on the left, where the wide-aspect canvas stretches that ray across most of the screen). **Actual fix**: sample `uPrev` twice — once raw, once fully folded — and cross-fade the two *colors* by `uMirrorStrength`, uniformly across the whole screen, instead of blending the angle before a single sample. No privileged always-identity region, no seam from the blend itself, and every wedge keeps a real share of its own history even at high symmetry. **Not yet verified in a browser** — reasoned through and typechecked/tested (no GL test coverage exists), but this file has already needed two follow-up passes based on live feedback, so don't assume the third is necessarily right either.
- **Julia zoom rate** (`JuliaScene.ts`): reported as imperceptible — "just changing colors in the center." First attempt 3x'd `ZOOM_RATE_BASE` (0.018→0.054) and *loosened* `ZOOM_SEEK_MIN_FACTOR` (0.6→0.75); that made the zoom visible but broke the balance between how fast the view narrows and how much real wall-clock time `updateNavigation` gets to steer pan toward genuine boundary detail at its own unchanged speed (`NAV_PAN_SPEED`) — reported back as the dive drifting past/outside the fractal's detail, exactly the "zoom outracing navigation" failure `ZOOM_SEEK_MIN_FACTOR` exists to prevent. **Landed at**: 2x instead of 3x (`ZOOM_RATE_BASE` = 0.036, ~6.4min idle dive vs. the original ~13min) and `ZOOM_SEEK_MIN_FACTOR` restored to its original 0.6. `ZOOM_RATE_WINDUP_GAIN`/`ZOOM_RATE_ENERGY_GAIN` scaled by the same 2x to keep their relative contribution unchanged. This also roughly doubles the `ZOOM_MIN` reset frequency vs. the original estimate below (was ~13-22min idle, now ~6.5-11min idle) — still infrequent, not disruptive. (An independent review of this session's commits caught the comments in `JuliaScene.ts` itself understating these dive-duration figures by ~30% — `ln(ZOOM_START_MAX/ZOOM_MIN)/rate` is the actual formula, fixed in-code; the "13-22min"/"6.5-11min" figures here and below were already right.)
- **"Not enough variety, just looks psychedelic"** — flagged by the user as a real, unresolved complaint, explicitly *not* something to keep guessing at with more constant tweaks. The color cross-fade above should help some (real per-wedge history now survives even under high symmetry, instead of everything-but-one-wedge becoming a pure copy of its neighbor), but whether that's enough, or whether the actual issue is palette/hue range, the Julia `c`-parameter's motion (dives looking similar to each other), or the symmetry effect being overused generally, is an open design question — ask before further tuning here rather than assuming which one it is.
- **Julia dive "missing the fractal completely, going into mostly void"** — reported again after the zoom-rate walk-back above, so the zoom-vs-navigation balance wasn't the whole story. Root cause found: `c` (`thetaSweep` via `cardioidPoint`) drifts at a fixed **real-time** rate (`THETA_SPEED_BASE` etc.), completely independent of the current zoom depth — "θ only ever advances, there is no reset" is deliberate (the "never repeats" guarantee) but means over one ~6.4min dive `c` can traverse ~3 radians of the cardioid boundary, a huge parameter-space move. At normal zoom that's a gentle morph; deep in a dive (zoom shrunk many orders of magnitude), the visible field is so narrow that this same absolute drift relocates or destroys the fine structure navigation is aimed at, faster than local re-probing (`updateNavigation`'s periodic 8-direction check) can recover from — the view ends up staring at now-unrelated/empty structure. Fixed by scaling both `thetaSweep`'s and `radialPhase`'s per-frame advance by `max(THETA_ZOOM_FLOOR=0.03, min(1, zoom))` — full speed at normal/wide zoom, nearly frozen once genuinely deep, back to full speed the instant a new dive resets zoom near 1-2. **Not yet verified in a browser** — same caveat as the fold/zoom items above.

## Patchbay/patch-graph editor tool + a real bug-fixing pass (this session, later)

Built a dev-only editor tool per user request, then spent most of the rest of the session chasing real bugs the user found while testing against it and the real site. Recording all of it since several fixes only worked on the second or third try.

**The editor** (`tools/patchbay-editor/`, `npm run patchbay`, own Vite config/tsconfig, React as a devDependency scoped to this tool only — never touches the shipped package): drives a **real** render-worker instance (not a mock), lets you live-edit the screen's `Patchbay` config (hot-swapped via new dev-only `debugSetPatchbayConfig`/`debugSetSignalBusStream` worker messages, inert unless this tool sends them) and see the change immediately. Data model: `patchbay/editor/patch-document.ts` (pure add/update/remove/reorder ops over routes, stable ids) is deliberately separate from a **second, new system**, `render/conductor/patchgraph/` — a small operator graph (signal/const/threshold-with-hysteresis/envelope/logic-and-or-not/combine/curve/map/target nodes, topologically evaluated with per-node persistent state) built specifically for physical outputs (servos/LEDs/lasers), since the screen's flat 1-signal-in/1-target-out route model can't express "LED on only when energy is high AND the low end is present" — deliberately NOT unifying this with the screen's `Patchbay`, which stays untouched/working. `patchgraph/fixture-document.ts` lets a user add/name/remove fixture instances (dimmer/RGB/servo/mover types), each instance's channels becoming real routable targets live, no code change. Only a vertical slice of UI exists (one route, one demo fixture, live debug readouts) — the full route table and a graph-building canvas are still unbuilt (see "Outstanding" below).

**Real bugs found and fixed, in the order they surfaced** (several are `JuliaScene.ts`/`memory-field.frag.glsl` fixes affecting the real site, not just the editor tool):

- **Canvas double-transfer crash**: React 18 StrictMode's dev-mode double-invoke of effects (mount→cleanup→mount) collided with `canvas.transferControlToOffscreen()`, a genuine one-shot browser API with no undo. Removed StrictMode from the editor's `main.tsx`; also cached `RuntimeBridge` instances by canvas element (a `WeakMap`) so Vite Fast Refresh reuses the existing bridge instead of re-transferring.
- **View "vanishes"/goes dark, heals briefly on resize, non-deterministic**: several real, independent gaps found in sequence — (1) the editor's own resize handling had no debounce (the exact bug already fixed in `src/index.ts`'s `RESIZE_DEBOUNCE_MS`, just never carried over when building this tool's resize handling from scratch — fixed); (2) **no WebGL context-loss handling existed anywhere in this codebase** — without a `webglcontextlost` listener calling `preventDefault()`, the browser won't even attempt to restore a lost context, so `powerPreference: 'high-performance'` (a real trigger on hybrid-graphics laptops) could kill the canvas permanently — added both listeners to `render-worker.ts`'s `init` handler, reusing the still-valid `caps.gl` reference to re-run `screenOutput.init()` on restore; (3) **no error handling existed anywhere in the render loop** — any uncaught exception meant the recursive `requestAnimationFrame` call never happened and the loop died silently forever, freezing on whatever was last drawn (plausible if that landed mid-flash during the — now more frequent, post zoom-speedup — zoom-floor reset) — split `loop()` into an outer try/catch wrapper (always reschedules regardless) and `tick()` (the actual per-frame work); added `console.log` around the zoom-floor reset trigger and context-restore for next time. **The actual root cause turned out to be none of these** — see next item.
- **"Black shaders growing... like the GPU is dying"** (the real root cause of the above): a NaN/Infinity value entering `MemoryFieldPass`'s ping-pong buffer, which is a **float** FBO and does NOT clamp on write (unlike an 8-bit texture) — once one bad pixel exists, every subsequent frame's advection sampling spreads it to neighboring pixels, visually reading as corruption growing across the screen; a resize reallocates that exact buffer from scratch, which is why that "healed" it. **Confirmed fixed** (user-verified) by sanitizing in `memory-field.frag.glsl`'s `main()`: `isnan()`/`isinf()` fall back to the current frame's fresh content, plus a generous finite clamp (64). The upstream source of the bad value was never identified — this stops it from persisting/spreading regardless of cause, which turned out to be sufficient.
- **Drop detection never fires on a softer ambient "drop"**: confirmed in code — the rewrite earlier this session requires `fullness AND onsetJump AND noveltyPeak`, all three, so a pad/drone swelling into fullness with no percussion structurally could never qualify (no rhythm to jump). Added a second qualifying path (fullness + novelty, no onset requirement) in `drop-detector.ts` — safe against the original false-positive case since that's rejected by fullness's own crest-factor penalty independent of onset activity. First attempt used a *stricter* novelty threshold for this path; measured that this can't work (fullness ramps up over ~1.3s, by which point novelty has typically already decayed most of the way from its post-transition peak — true for the *existing* rhythmic path too, which passes with novelty barely above 0.3 at the moment fullness clears) — landed on reusing the same `NOVELTY_THRESHOLD` instead.
- **Julia "spins/moves too fast," worst near max zoom before reset**: `THETA_SPEED_WINDUP_GAIN`/`THETA_SPEED_ENERGY_GAIN` (c's sweep-speed build/energy gains) key off the same signals as the zoom rate's own build/energy gains AND screen-composites.ts's flowStrength/symmetry build/tension gains — a build moment accelerated the shape morph, the zoom, the turbulence, and the kaleidoscope fold all at once. The zoom-freeze fix from earlier this session only meaningfully damps this once zoom is already fairly deep, so a build early/mid-dive got the full unthrottled morph speed regardless. Halved both gains.
- **"Too psychedelic/bright/illegible sometimes"**: root-caused but **not yet fixed**, still an open plan the user hasn't signed off on implementing — see "Outstanding" below.
- **`tension`/`buildProgress`/`suspension` "make no sense"**: not a bug — explained to the user (`tension`/`suspension` are the same raw `BreakDetector` "is the mix thin/collapsed" signal at two different smoothing time-constants, not independent concepts; `buildProgress` only tracks a *rising trend* in centroid/sub, not general energy). All three were designed around dynamic build→drop→break song structure and are expected to sit near-inert on continuous ambient material — that's the gap `energy`/`familiarity` exist to cover. User left the naming as-is for now ("I don't know your choice") — worth a rename for clarity if it comes up again, not urgent.
- Also fixed during an independent code review of the day's earlier commits (before this bug-hunting pass): a dead `windupSpring.setTarget(0)` call in `Conductor.ts` that never did anything, a misleading comment in `types.ts` about `dropTrigger` being consumed downstream (it isn't), a Patchbay type-safety gap where a typo'd route `from` silently produced `NaN` every frame instead of failing at construction, and ~30%-understated dive-duration figures in `JuliaScene.ts`'s own comments.

## Repo rename status

Not yet renamed on GitHub — still `stcksmsh/hysteresis`. The site's `projects.manifest.json` and this package's own `io-page` branch `meta.json` already declare the eventual slug `sinteza-viz`; the manifest's fetch-source `repo` field is deliberately still pointed at `stcksmsh/hysteresis` (the real, reachable name) until the actual rename happens. **When the rename happens: flip that one line back in the site repo, nothing else needs to change** (the resulting page path stays `/projects/sinteza-viz` either way, since that comes from `meta.json`'s `slug`, not the manifest's `repo` field).

## Position-only sync mode (the site's actual integration)

The site embeds SoundCloud via iframe — cross-origin, no AnalyserNode reachable, ever. `StructureSource.synthesize(positionSec)` builds a complete `StateFrame` purely from a schema-2 sidecar (`src/shared/sidecar.ts`), driven by an rAF loop in `src/index.ts` whenever a sidecar is loaded and no live audio has attached. `idle: true` is set *deliberately* in this mode even though music is genuinely playing — it's the existing lever (`JuliaScene.idleClockSec`) that keeps the beam animating its idle Lissajous figure, since there's no real waveform to trace offline. Every other field (`buildProgress`, `tension`, bands, onsets, energy, centroid, flatness) carries real per-track structure.

**Generating a sidecar**: `npm run analyze -- /path/to/master.wav output.sidecar.json` (wraps `scripts/analyze.ts`, needs the *original* WAV — the hand-rolled `scripts/wav.ts` reader only handles RIFF/WAVE PCM 16/24/32-bit or 32-bit float, no compressed formats). Output is schema-2 JSON: `bandEnvelope` (5 bands × ~20Hz samples), `centroidEnvelope`/`flatnessEnvelope`/`energyEnvelope`, `beats[]`, `sections[]` (build/break spans only — everything outside a matched section defaults to `buildProgress`/`tension` = 0), `events[]`, `onsets[]`. Runs fine on the *original* full-fidelity WAV directly — no need to downsample for this script's sake (downsampling only matters if you need to physically transfer the file somewhere with a size limit).

**Currently wired up** (as of this session): SIGSEGV, 0xC000021A, Hysteresis, Sampling Drift, Triple Pendulum — all five real tracks on the site now have real sidecars driving the visualizer (published to the site repo's `public/sidecars/`, referenced via each track's `sidecar` content field). Confirmed empirically (simulated `player:transport` sequences, diffed rendered output at a detected build-section position vs. a plain groove position) that this actually changes what renders, not placebo.

## Known/accepted limitations (don't "fix" these without reason to)

- The beam never shows a real waveform in position-only mode — always the idle Lissajous figure. Sidecar section detection is currently sparse for most tracks (e.g., SIGSEGV: 2 sections across ~6 minutes) — `buildProgress`/`tension` default to 0 for a large majority of most tracks' runtime. `energy` (see below) now fills most of that gap for the continuous/ambient motion; buildProgress/tension are still what drives the big, rare, structural reactions (drops, builds) specifically. **The new §4 signals (`noveltyLocal`/`noveltySection`/`fullness`/`onsetDensity`/chroma) are the real, live-capable fix for this same gap going forward** — they're alive every frame, not section-gated.
- `ZOOM_MIN` (JuliaScene) is deliberately capped — going deeper needs actual perturbation-orbit rebasing (not implemented), and past attempts at a lower floor introduced visible blocky artifacts. Don't lower it without implementing rebasing.
- The Julia scene's perpetual zoom dive periodically resets when it hits `ZOOM_MIN` (a designed, not-a-bug beat, now with a slower/smoother 1.6s reveal — see below). Cadence is now somewhat shorter than the original idle-only ~13-22min estimate since `ZOOM_RATE_ENERGY_GAIN` also feeds it, but was kept conservative specifically to avoid pushing this too far — if it's ever reported as "too frequent" again, check real `energy`/`windup` values before assuming the rate math is wrong.
- Onset particles were removed (this session, user's explicit call after being asked to choose between toning down / repositioning / removing). Don't re-add a similar effect without addressing *why* it was disliked: it wasn't "a transient/granular layer is bad", it was specifically that particles spawned in a way that visually read as erupting from the fractal shape's own position.

## Fixes landed this session

- **Flash pacing** (`JuliaScene.ts`, `POST_FLASH_SEC`): was 0.28s, now 1.6s. The zoom-floor reset's fade-to-black (`PRE_FLASH_LOG_WINDOW`) takes ~28s at idle rate — a near-instant 0.28s fade back in was a ~100x pacing mismatch that read as a stutter/glitch regardless of how rare the actual reset event is.
- **Energy coupling** (`Choreographer.ts`, `JuliaScene.ts`): `frame.energy` (RMS loudness, continuously available for a track's *entire* runtime, unlike section-gated `buildProgress`/`tension`) was computed and threaded through `ParamBus` but never consumed by anything — dead data. Now smoothed (`DtSmoother`, 0.25s) and fed as an *additional* term into flow strength, theta-sweep speed, and zoom rate, gains kept modest relative to the existing build/drop dynamics. This is the real fix for "doesn't work with the music enough" — verified visually, same track/accent, two positions with very different energy (0.96 vs 0.21) both outside any structural section, clearly different field turbulence/beam character.
- **Resize debounce** (`src/index.ts`, `RESIZE_DEBOUNCE_MS = 150`): the canvas's `ResizeObserver` had zero debouncing. On mobile, a scroll gesture crossing the point where the browser's address bar finishes collapsing changes the *dynamic* viewport height mid-gesture, firing the observer repeatedly — each firing was a full pipeline reallocation, and `MemoryFieldPass.resize()` specifically deletes+recreates its ping-pong buffers from scratch, wiping all accumulated trail history. This was the actual "stutter when scrolling past half the screen" bug — not a JS scroll listener (there isn't one), a resize side-effect of mobile browser chrome. Debounced so rapid-fire observations coalesce into one reallocation.
- **Onset particles removed**: see the limitations note above. Also removed `ParamBus.onsetPulses`/`OnsetPulse` and Choreographer's `spectralHits`→pulses conversion (existed solely to feed particles); `StateFrame.spectralHits`/`SpectralHit` itself was left alone as general Layer-2 data.

**Process note for any future fix here**: this package is consumed by the site via `github:stcksmsh/hysteresis#master`, but `stcksmsh.github.io`'s `package-lock.json` pins a *resolved commit SHA*, not just the branch. Merging a fix to this repo's `master` does **not** automatically reach the deployed site — you also need to go into the site repo and run `npm install sinteza-viz@github:stcksmsh/hysteresis#master` to re-resolve the lockfile, then commit that lockfile change. Every fix above required this as a separate, necessary follow-up step.

## Sandbox/environment notes (for whoever's running this next in a similar constrained environment)

- `w.soundcloud.com` and generic Google/Drive domains are blocked by egress policy in Claude Code's sandboxed sessions — can't test real SoundCloud playback or fetch from Drive links there. `raw.githubusercontent.com` and normal git push/fetch against `github.com` do work.
- `api.github.com` (plain REST, e.g. the `contents` listing endpoint the site's `federate.ts` script calls) also 403s in that sandbox even though `raw.githubusercontent.com` doesn't — this is a real, pre-existing limitation of `federate.ts`'s GitHub-API dependency in that specific sandbox, not a bug in the script; it works fine in real CI (GitHub Actions) which isn't behind the same egress policy.

## The "step back and fix everything" pass (this session, later still)

User feedback after the fixes above: drop detection *still* never fires (`dropImpulse` reads a flat 0 on real audio), Julia navigation has been retuned across many sessions and still doesn't reliably find interesting structure, and — the important reframe — the psychedelic-ness is fine *if* it's controllable/automatable (palette control in the patchbay), and responsiveness is present but shallow (wants specific salient elements followed, not just overall energy). Explicit instruction: stop patching reactively, take a real step back.

- **Drop detector internals exposed live**, not tuned blind again: `DropDetector.getDebug()` (fullness/onsetJump/noveltyPeak/armed) threaded through as an optional `StateFrame.dropDebug` field and the patchbay editor's signalBus stream, shown in a new "drop detector internals" panel. Next real-track test through the editor shows directly which condition is failing, instead of guessing at thresholds again.
- **Julia vortex-search extracted into its own tested module** (`vortex-search.ts`) — `sampleOrbit`/`clusterScore`/`findVortexTarget` had ZERO test coverage before, across all the prior sessions' worth of hand-tuning against live feedback alone. Investigated one concrete, mathematically-grounded hypothesis with real data instead of another guess: `c` always sits on the Mandelbrot cardioid's boundary, which has parabolic (neutral) dynamics that converge polynomially, not geometrically — the existing iteration caps (60/90) seemed like a plausible source of systematic blindness near real boundary detail. Empirically measured this is a real but MODEST effect (raising the cap does change which candidate gets picked, sometimes substantially, and finds a few more genuinely diverse candidates — but the search already found *something* even at the old cap, it wasn't dramatically blind). Raised the caps anyway (90→400, 60→200 — both cheap, one runs once per dive) since it's a real, verified, zero-risk improvement, but this is honestly NOT confirmed as THE fix for "misses every iteration" — the deeper issue is more likely in the ongoing pan/zoom convergence behavior, which needs actual visual iteration to diagnose properly (10 new tests, all passed first write).
- **Palette is now genuinely routable** — checked, and there was previously no way to control/automate it at all: `hueShift`/`paletteMix` were hardcoded formulas inside `ScreenParamAssembler`, never a bus signal or a target. Moved hue auto-drift onto the bus as `hueDrift` (computed in Conductor.ts), added `screen.hueShift`/`screen.paletteMix` targets, and the default `screen-only.ts` config now reproduces the old formulas as real routes (`hueDrift` + `centroid`\*0.1 summed into `screen.hueShift` — the patchbay's existing sum-then-clamp combine mode, no new mechanism needed; `buildWindup` → `screen.paletteMix` passthrough). New conductor.spec.ts tests cover both (neither had any test before, hardcoded or otherwise).
- **Built the real route table UI** (`tools/patchbay-editor/src/RouteTable.tsx`) replacing the single hardcoded energy-gain slider — every non-passthrough route in the live screen config is now editable in place (from/to/curve/gain/offset/invert), with add/remove and live inline validation. This is what makes the palette routing above actually *usable* right now, not just wired at the data layer.
- **Finished in a follow-up pass, same session**: the physical patch-graph builder UI (`GraphEditor.tsx` — structured, every node kind's fields inline, `graph-draft.ts` is the seam that keeps a future node-graph canvas additive rather than a rewrite), fixture instance management (`FixtureManager.tsx`), simulated fixture visuals (`FixtureVisuals.tsx` — dimmer glow/RGB swatch/servo needle/mover crosshair), save-to-file (`serialize-config.ts` + a small Vite dev-middleware in `vite.patchbay-editor.config.ts`, restricted to one directory, filename-validated, live-verified including two rejected path-traversal attempts), and a visual-polish pass (real CSS classes replacing scattered inline styles — see `styles.css`). The patchbay editor's original task list is now fully built.
- **Still not done, deliberately** — the "follow salient/singled-out elements" responsiveness idea was explicitly flagged back to the user as a hard, real DSP problem needing its own design conversation, not something to build blind. **This is what §4 above is the actual answer to.**
- **Patchbay editor layout overhaul** (after user feedback: "clunky, difficult (ugly, bad UX, and barely legible, need a fullscreen option or move it below the demo or something)"): the original layout was a fixed 520px sidebar of tiny (11-12px) panels squeezed next to the canvas regardless of window size — that was the actual problem, not colors. Replaced with: canvas as a top preview strip (`min(46vh, 520px)` tall) with a fullscreen toggle button (Escape also exits) that switches it to `position:fixed; inset:0` without recreating the canvas DOM node — important because `transferControlToOffscreen()` is one-shot, so the existing per-canvas `RuntimeBridge` cache in `App.tsx` had to keep working across the fullscreen state change, not just across Fast Refresh; editor panels moved into a full-width responsive grid below (`repeat(auto-fit, minmax(360px, 1fr))`, the patch-graph panel spans full width via `.panel-section-wide`) instead of one narrow vertical stack. Base font bumped 13px→14px, most panel-internal text 11-12px→12-13px. Verified: typecheck clean, dev server serves/transforms all changed modules with no console errors, full test suite (107 tests) passes. Not yet verified in an actual browser click-through — no browser access in this session.
- **Fixed a real bug from that overhaul**: the fullscreen toggle broke the sim entirely (stayed black forever), and the canvas preview also read as too squeezed. Root cause of the black-screen bug — the JSX rendered `canvasBlock` (the `<canvas>` element) at two DIFFERENT tree positions depending on `canvasFullscreen` (`{!canvasFullscreen && canvasBlock}` inside `.app-body`, `{canvasFullscreen && canvasBlock}` after it). React sees that as a different element identity at each position, so toggling fullscreen unmounted the old canvas and mounted a brand-new one — fatal here because `transferControlToOffscreen()` is one-shot per canvas and the effect that calls it has no unmount cleanup, so the old worker/offscreen-canvas pairing was orphaned mid-render while a new bridge tried to start fresh, leaving it black. Fixed by rendering the canvas block exactly once, at a single fixed JSX position, and doing fullscreen purely via CSS class toggle (`.canvas-block-fullscreen` → `position:fixed;inset:0`) — same DOM node the whole time, no remount. Also bumped the default preview height `min(46vh,520px)` → `min(72vh,900px)` per the "squeezed" complaint. Typecheck + full test suite (107) verified again after this fix; still no real browser click-through.
- **Panels below the sim are now reorderable and resizable** (user's next ask after the layout overhaul: "the individual windows should take up the space better and fill it up better, many things should be reorderable/resizable"). Switched the panel area from a uniform CSS grid to `display:flex; flex-wrap:wrap` (`.panel-flow`) so panels pack against their own natural sizes instead of forcing every panel into the same column width — a route table and a 3-line debug readout no longer waste the same footprint. Each panel got: (1) a real per-panel resize handle via the browser's native `resize: both` (deliberately not a JS resize library — free, familiar, zero new dependency for a dev-only tool); (2) drag-to-reorder via native HTML5 drag-and-drop (`Panel.tsx`'s draggable header, no library) — order is tracked as a plain id array in `use-panel-order.ts` and persisted to `localStorage` so a customized layout survives a reload, merging in any new panel ids that get added later rather than resetting. `App.tsx`'s 8 panels are now data (`{id, title, hint, wide, width, height, content}`) mapped over the persisted order, instead of hardcoded JSX `<section>`s in a fixed sequence — same content as before, just re-arrangeable. Verified: typecheck clean, dev server transforms the two new modules with no errors, full suite (107) passes. Still not verified in a real browser — in particular the actual drag feel and whether native `resize` interacts oddly with the `RouteTable`'s internal horizontal scroll container need an eyes-on check.
- **Seeded all 4 fixture types by default**, not just the dimmer: `App.tsx`'s initial `fixtureDoc` now adds "Demo Dimmer" / "Demo RGB" / "Demo Servo" / "Demo Laser" (`mover` type — there's no separate "laser" fixture type, `mover`'s pan/tilt/intensity channels are what a laser/moving-light needs) up front, so opening the editor immediately shows every `FixtureVisuals` widget kind and gives the graph editor's target dropdown a channel from each type to route to, without the user needing to know to add them manually first.
- **Caught immediately by the user: the new demo fixtures "were not wired up in a working way."** Correct — the original `seedNodes` only ever wired the FIRST target in the catalog (energy→threshold→target), so the 7 other new demo channels sat at their default value with nothing driving them. Fixed properly, not just patched: extracted the seeding logic out of `App.tsx` into its own pure module (`tools/patchbay-editor/src/seed-graph.ts`, no React/RuntimeBridge imports, so it's cheap to unit test) and rewrote it to wire EVERY target in the catalog — the first keeps the original threshold-gated chain (still the clearest single demo of a threshold node), every other channel gets a signal picked from a rotating list of continuous-tagged signals (`energy/low/mid/presence/air/centroid/pan/familiarity` — continuous-only deliberately, since validate.ts's servo-safety warning flags a transient signal fed straight into a servo/mover with no smoothing). Also fixed a second, subtler instance of the SAME bug class the rewrite would otherwise still have: `evaluateNode`'s `target` case is a pure passthrough (nothing auto-scales a 0-1 signal into a target's real range), so a servo (range `[0,180]`) or any non-[0,1]-range target getting a raw signal would visually barely move at all even though it "has wiring" — every chain now inserts a `map` node into the target's real range when it isn't already [0,1], including the first/threshold chain (a servo landing in the "first" slot was still stuck in 0-1 space before this second fix). New tests (`tests/unit/seed-graph.spec.ts`): one builds all 4 demo fixture types and asserts `validatePatchGraph` returns zero issues and every target resolves to a finite value; the other specifically catches the range-mapping regression (a lone servo target must resolve well above 1, not just 0 or 1). Full suite now 109 tests, all passing; dev-server transform check clean.

## Outstanding (as of the session before the docs merge)

- **The "too psychedelic/bright/illegible sometimes" fix — implemented, not yet verified in a browser.** User confirmed both complaints were real. Mechanism: the composite pass already Reinhard-tonemaps (`c/(1+c)`), so nothing literally clips to white, but once the memory field's accumulated brightness gets large, Reinhard's compression crushes local contrast so everything reads as a washed-out bright mush — and `symmetry` (kaleidoscope strength) and `decay` (memory-field persistence, hence brightness) both scale up off the *same* `tension`/`buildProgress`/`suspension` signals, so a build/break moment got simultaneously more mirrored and more washed-out at once, for as long as that section ran. Landed: (1) `uCurGain` in `memory-field.frag.glsl`/`memory-field-pass.ts` scales the fresh-frame contribution by `(1-decay)/(1-DECAY_REFERENCE)` so steady-state brightness (`cur/(1-decay)`) stays constant regardless of decay — `DECAY_REFERENCE` matches today's resting decay (`FIELD_DECAY_GROOVE`=0.86) so the look at rest is unchanged, every higher decay tier now holds the same brightness longer instead of a brighter one; (2) `SYMMETRY_AMBIENT_CEILING`=0.72 in `screen-composites.ts` caps ambient (tension/build/flatness/familiarity-driven) symmetry below full mirror — the drop's brief snap-to-1 hold is untouched, since that's a deliberate earned punch, not the thing reported as overused. Did NOT lower `FIELD_DECAY_BREAK_MAX` as a separate backstop — (1) already fully decouples brightness from decay mathematically, so that would only be a persistence-*duration* tuning choice now, not a brightness fix, and wasn't asked for.
- **Patchbay/patch-graph editor tool is now feature-complete** including a real visual node-graph canvas (see "Visual node-graph canvas + 24/7 reliability audit" below) — the old "vertical slice only" note is stale.
- Needs a real-browser check still, in priority order: (1) the still-unverified-by-eye items from earlier in this session (the fold cross-fade, zoom-rate change) — GL/shader behavior has zero automated coverage in this repo, though several rounds of real bug reports since then didn't surface anything wrong with these two specifically; (2) the detector-disable acceptance test and the drop-detector constants (`FULLNESS_THRESHOLD`/`ONSET_JUMP_MIN`/`NOVELTY_WINDOW_SEC`/`NOVELTY_HOLD_SEC`, now also the soft-drop path) — still only checked against synthetic fixtures + this session's live spot-testing via the patchbay editor, never a systematic pass against multiple real tracks.
- `tension`/`buildProgress`/`suspension`'s confusing naming (see above) — left alone, revisit if it comes up again.
- Position-only sync is real end-to-end for all 5 live tracks, flash pacing and resize-triggered stutter/reset are fixed, energy actually drives the visual, onset particles are gone per user request — none of that has regressed across this session's changes (verified by the full test suite passing throughout, and no reports pointing at any of it).
- Still real remaining work, not urgent: `scripts/structure.ts`'s offline sidecar path still replays the causal drop detector hop-by-hop rather than true look-ahead segmentation — only matters if the fixed causal primitive (including tonight's soft-drop path) proves insufficient replayed offline. Also still worth a real mobile-device check of the resize-debounce fix and real SoundCloud playback generally — both were only reasoned/simulated, never literally exercised (sandboxed sessions can't reach `w.soundcloud.com` or trigger a real mobile address-bar collapse).

## Visual node-graph canvas + 24/7 reliability audit (this session)

User asked for a "beautiful and intuitive graph based UI for the patchbay" and for the production visualizer to be crash-proof for unattended 24/7 operation. Scoped via explicit questions first: the graph UI meant a real drag/wire node canvas (not more form polish), and the reliability ask was about the production renderer (the site-wide background), not the dev editor tool.

**Visual node-graph canvas** (`tools/patchbay-editor/src/PatchGraphCanvas.tsx`, replaces the old form-only `GraphEditor.tsx`, which is deleted): drag a node's header to reposition it, drag from a node's output circle to another node's input circle to wire them, click a filled input circle to disconnect (also picks the wire back up for immediate rewiring — same gesture as a fresh connection, just pre-detached), click a node to select it and edit its typed params in a side inspector (`node-fields.tsx`'s `NodeFields`, extracted out of the old `GraphEditor.tsx` so both a future alternate view and this canvas can share it without duplication), Delete/Backspace removes the selected node (guarded against firing while a form field has focus — Backspace while editing a number must edit the number). No pan/zoom yet — the canvas is a large fixed-coordinate-space div inside a scrolling container (plain addition for every position calculation, no transform-matrix math), which trades "scroll to reach far-apart nodes" for real implementation simplicity; add zoom later if graphs outgrow this — `graph-draft.ts`'s `x`/`y` fields don't need to change for that. `layout.ts`'s `computeAutoLayout`/`withAutoLayout` seed positions (topological-depth columns, left-to-right following actual evaluation order) for any node that doesn't have one yet — freshly seeded nodes, a loaded file, or a just-added node — without disturbing nodes the user already dragged. Verified: typecheck clean, full suite (109 tests) still passes, dev server transforms all new/changed modules with no errors (checked via direct HTTP fetch of each module's Vite-transformed output, grepped for real thrown errors vs. React's compiler-inserted exhaustive-switch guards — no real errors). **Not verified in an actual browser** — no browser access this session, so the drag/wire feel itself is unconfirmed, same caveat as several earlier layout passes.

**24/7 reliability audit of the production renderer** (not the editor tool) found and fixed three real gaps, all confirmed by reading the actual code paths rather than guessing:

- **`visibilitychange` was never wired up.** `render-worker.ts` already has a `'visibility'` message that calls `stop()`/`start()` on the render loop — built, tested by nothing sending it, ever. `src/index.ts` now listens for `document.visibilitychange` and forwards it (plus an initial check in case the page starts out already backgrounded), cleaned up in `destroy()`. Without this, a backgrounded/minimized tab kept rendering at full tilt indefinitely — not something to depend on browser rAF throttling to fix uniformly, and directly relevant to "24/7 unattended, must be fast" since sustained unnecessary GPU load is exactly the kind of thing that compounds into driver instability over a long unattended run.
- **`loadSidecar`'s `fetch`/`res.json()` had no error handling**, called as `void loadSidecar(...)` from `onTransport` (can't await a DOM event handler) — any network hiccup or malformed response was an unhandled promise rejection, silently leaving that one track without sidecar-driven structure with zero visible symptom. Now wrapped in try/catch (`res.ok` also checked explicitly), logs and falls back cleanly.
- **The real one**: `tryAttachAudio()` called `engine.attach(ctx, workletUrl, analyser)` (async — `addModule()` fetches+compiles the worklet script) as fire-and-forget, then *unconditionally* stopped the synth/idle fallback loop and cleared the audio poll interval on the very next line — regardless of whether `attach()` actually succeeded. A transient failure (script fetch hiccup, or `ctx` closed between the poll's check and the call) meant: no live audio attached, AND the poll that would've retried was already cleared, AND the fallback loop that would've kept the visual moving was already stopped. Permanently silent and dead for the rest of that page load — exactly the kind of failure a 24/7-unattended requirement can't tolerate. Fixed by only clearing the poll / stopping the fallback inside `attach()`'s `.then()` (confirmed success), with a `.catch()` that just logs — the still-running poll interval naturally retries on failure instead of being told to stop early.

Verified: typecheck clean, full suite (109 tests, unaffected — `index.ts` has no test harness per the existing DOM/Worker-dependent note above) still passes after these changes.

**Not done, out of scope for this pass**: no pan/zoom on the canvas, no browser click-through verification of either the canvas or the reliability fixes (no browser access this session — same standing caveat as prior sessions' GL/layout work), no deeper audit of the audio-worklet/detector internals beyond the three items above (they were the concrete, verified gaps found; didn't go looking for hypothetical ones beyond that).

## Unify screen + physical patch graphs (this session, after the canvas above)

User's ask, scoped via a planning pass first (since "the screen is going to be used as a projector too... total control, shared behavior for screen and outside stuff, driven by same signal" plus "elevate to production level" touches the live 24/7 render path, not just the dev tool): replace the screen's flat `Patchbay`/`Route` engine with the same `PatchGraph` node-graph engine physical fixtures already use, so one authored graph can drive both — plus give nodes real renameable names instead of `n1, n2, ...`. Summary:

- **Safety net built before touching production**: `migrateRouteConfigToGraph()` (`patchgraph/migrate-route-config.ts`) converts any `Route[]`-based `PatchbayConfig` into an equivalent `PatchGraph`, and `tests/unit/migrate-route-config.spec.ts` proves it numerically matches `Patchbay.resolve()` across 200 random synthetic bus states/dt values plus dedicated edge-case tests (gain+offset, invert, invert+gain/offset, non-linear curve, multi-route summing, passThrough separation, unknown-signal rejection) — this is what made swapping the live engine defensible without a browser to eyeball the result against.
- **Production swap**: `render-worker.ts` now runs `PatchGraphEvaluator` against `configs/screen-graph.ts` (the migrated default graph) instead of `Patchbay` against `screen-only.ts`. `resolve-screen-targets.ts` is the direct successor to `Patchbay.resolve()`'s contract (default-fills unrouted targets, copies `idle`/`scope` straight from the bus since those can't be graph nodes at all — scalar-only node type). The hot-swap message is now `debugSetScreenGraph` (was `debugSetPatchbayConfig`), same reject-bad-edit-keep-previous behavior, just on the new engine's construction-time validation.
- **A real, independent bug found and fixed along the way**: `PatchGraphEvaluator`'s `target` node case never clamped to the target's declared range at all (unlike `Patchbay.resolve()`, which always did) — a genuine safety gap affecting fixture targets too, not something this migration introduced. Fixed in `PatchGraphEvaluator.evaluate()`.
- **Deliberately NOT touched**: the three nonlinear screen composites (`flowStrength`/`symmetry`/`fieldDecay`, spring/damper + edge-triggered impulse dynamics, `patchbay/screen-composites.ts`) stay exactly as hand-written — reimplementing hand-tuned, multi-session-tuned motion math as generic graph nodes with no browser access to re-verify it was judged too risky for this pass. `Patchbay`/`Route`/`screen-only.ts` are kept in the tree (still tested) as the migration's source of truth and reference oracle, just no longer wired into the live render path.
- **Editor tool**: one unified `DraftNode[]` graph now, seeded from both `screen-graph.ts`'s default and the fixture demo chains, validated against a merged catalog (`SCREEN_TARGETS` ∪ live fixture catalog) — a target node can point at either domain in the same canvas, which is the concrete "one signal drives both a screen effect and a servo" the user asked for. Sent to the live worker only after pruning to the screen-relevant subgraph (new `patchgraph/prune.ts`'s `pruneGraphToTargets`, cycle-safe upstream-closure trim) so the worker never has to know a fixture half exists. `RouteTable.tsx`/`patchbay/editor/patch-document.ts` (the old flat route-table UI) are **deleted**, not deprecated — the node canvas supersedes them outright, and `patch-document.ts` had zero remaining callers once `RouteTable.tsx` was gone.
- **Node naming**: `label?: string` added to the real `PatchGraphNode` (`patchgraph/types.ts`) and the editor's `DraftNode`, separate from each node's stable wiring `id`. Canvas: double-click a node's header to rename inline; inspector has the same field; a toolbar "find a node" input with a native `<datalist>` autocompletes by label and scrolls/selects on Enter. `PatchTargetDecl.label` had to become optional (was required) so the screen's plain `TargetDecl` — which never had a display label — stays structurally assignable where a `PatchTargetDecl[]` is expected; display code falls back to `.id` when absent.
- **Verification**: typecheck clean, full suite (112 tests — net down from before this session's earlier work because `patch-document.spec.ts` was deleted along with its now-dead subject, but up overall from the 12 new tests this pass added), `npm run build` and `npm run build:lib` (what the site actually consumes) both succeed, dev server transforms every changed/new module with no errors (checked via direct HTTP fetch + grep, same method as the canvas work earlier this session).
- **Not done / explicitly out of scope this pass**: no real browser verification that the screen still looks the same post-migration — this is the biggest remaining risk. The equivalence tests prove the *routing* math is identical; they can't prove a visual regression didn't sneak in through something the tests don't cover. **Do a real-browser side-by-side check (or at minimum `npm run patchbay` and eyeball it) before treating this migration as fully proven** — same standing caveat this file has carried for GL/layout changes across several prior sessions.

## Patchbay editor UI overhaul, round 2 (this session, after the demo/edit split above)

User feedback on the demo/edit split from the previous pass: the patch graph is "the main thing" and wasn't reading as central, Fixtures/Fixture Visuals needed to be visually secondary (a side rail), debug panels should be an overlay rather than more inline panels, and the graph itself needed to "take up space while keeping legibility" — plus a general high-bar visual pass ("supposed to be a project I'm proud to present"). Planned explicitly before implementing (two concrete UX questions asked and answered: rail on the right, debug as a slide-in panel over the canvas, not a full modal).

- **Workspace hierarchy, not a flat panel flow**: `App.tsx`'s old `panel-flow` (every panel equal-weight, drag-to-reorder) is gone. New `.workspace` is two zones — `.workspace-main` (the patch graph, full height, dominant) and a fixed `.workspace-rail` (320px, Fixtures + Fixture Visuals, right side) — with a real background-depth difference (`--bg-0` vs `--bg-1`, 1px divider) so "primary vs. supporting" reads at a glance, not just from relative size. Drag-reorder/native-resize (`Panel.tsx`, `use-panel-order.ts`) is **deleted**, not kept dormant — it existed for a loose list of equal-weight windows, which the new hierarchy doesn't have anymore (only ever 2 items in the rail).
- **Debug panels are now a real overlay**: `SectionCard.tsx` replaces `Panel.tsx` for static chrome (title/hint/content, no drag/resize). The 🐞 Debug button opens a right-edge slide-in drawer (`.debug-drawer`, backdrop, Escape/backdrop-click/toggle-again to close) containing all 4 diagnostic panels — never inline in the main flow.
- **The graph canvas got real pan/zoom** (`PatchGraphCanvas.tsx`): mouse-wheel zoom-to-cursor (native non-passive `wheel` listener — React's synthetic `onWheel` is passive by default, so `preventDefault()` there is silently ignored, a real gotcha worth remembering next time), drag-empty-background to pan, a "⊡ Fit" button plus auto-fit-once-on-load (frames every node with padding). Switched from native-scroll positioning to a CSS `transform: translate() scale()` on the content layer — node positions (`DraftNode.x/y`) still live in the same plain "canvas space" they always did; only the render/hit-test math changed. Wire-drop hit-testing (`document.elementFromPoint`) needed no changes at all since it already worked in real screen coordinates, transform-agnostic by construction.
- **Auto-layout got measurably denser** (`layout.ts`): previously packed rows into a fixed-height slot regardless of a node's actual size, wasting space in mixed graphs. Now accumulates real per-node height per column (via the new shared `node-box.ts`). Column width is also now the actual max node width in that column, not a fixed pitch.
- **Node width now flexes with label length** (`node-box.ts`'s `nodeBoxWidth`, clamped 150-260px) instead of a fixed 190px that truncated longer descriptive names — directly addresses the "should be smarter, same for names" ask, since renaming (added earlier this session) is pointless if the result just gets ellipsis-truncated.
- **A real layout bug caught and fixed before it shipped**: the fixed-position corner preview (screen demo PiP, edit mode) was originally still bottom-right, same corner as the new rail — since the rail scrolls and the preview is `position: fixed`, any rail content scrolled up would render *underneath* the preview, permanently obscured. Moved the preview to the *top* of the rail instead and gave `.workspace-rail` real reserved top padding (270px) for it, rather than just visually avoiding the overlap — content can never scroll under a fixed overlay if space for it is reserved in the flow.
- Verification: typecheck clean, full suite (112 tests, none of this touches production code so the count is unchanged from the previous pass), dev server transforms every new/changed module with no errors (same HTTP-fetch-and-grep method as prior passes). **Not verified in an actual browser** — no browser access this session — same standing caveat as everything else UI-shaped in this file. The pan/zoom feel, the corner-preview reserved-space fix, and the debug drawer's animation are the highest-value things to eyeball first if picking this up.

## ISF import (this session — first slice under the then-separate `hysteresis-master-prompt.md`)

First session working from the new `hysteresis-master-prompt.md`/`NEXT_SESSION_PROMPT.md` docs (both new at the time, now merged into this file) rather than the (then-separate) signal-bus/viz docs directly — those two describe a broader "drive anything" instrument the current signal-bus/patchgraph/canvas work is a real foundation for, not yet a superset of. Gap analysis found: the signal bus, unified patchgraph, and node canvas (all prior sessions above) satisfy the master-prompt's pipeline-target reasonably well; **zero** protocol work from the priority order (ISF, OSC, Art-Net/sACN, DMX-serial, MIDI, ILDA, WLED/E1.31) existed anywhere in the repo. Picked ISF (priority #1, first unchecked backlog item).

**Real architectural constraint found before writing code**: the visualizer's own package-shape section and `scenes/registry.ts`'s own comment both state "one fixed visual identity, no scene picker in the package API" — the production site is deliberately not scene-pluggable. The master prompt's "wire signals to anything: a built-in fractal renderer, a user-written shader" is a real identity shift from that. Rather than guess which way to resolve this, scoped ISF import to the **patchbay editor tool only** (a sandbox/authoring environment) — a real, working, end-to-end capability that doesn't touch constraint #1 (never break the live production path), while deliberately leaving "should the real site ever be scene-pluggable" as an open decision for the user, not decided unilaterally. Confirmed with the user up front that docs should live in an in-repo `docs/` folder, not a separate GitHub Wiki repo (avoids a second push target this session had no need to touch).

- **`src/isf/`** (new, framework-agnostic — no render-worker/React imports): `types.ts` (`IsfDocument`/`IsfInput` variants, `IsfParseError`/`IsfUnsupportedFeatureError`), `parse-isf.ts` (real subset parser: float/bool/long/color/point2D inputs; rejects multi-pass, `PERSISTENT` buffers, `IMPORTED` images, and `image`/`audio`/`audioFFT`/`event` inputs with a specific message naming exactly what's unsupported — not a stub, everything accepted renders for real), `translate-isf-glsl.ts` (textual translation from ISF's GLSL ES 1.00-style built-ins to this repo's GLSL ES 300/WebGL2 convention: `gl_FragColor`→a real `out vec4`, `texture2D`/`textureCube`→`texture`, `isf_FragNormCoord` injected as a local inside `main()` since GLSL forbids a non-constant global initializer referencing `gl_FragCoord`), `isf-targets.ts` (`isfInputsToTargets`/`resolvedTargetsToIsfUniforms` — the two-way bridge between a shader's declared inputs and the patch graph's scalar-only node model; color/point2D expand into r/g/b/a or x/y scalar targets, `isf.`-prefixed to avoid catalog collisions).
- **`IsfScene`** (`src/render/worker/scenes/isf/IsfScene.ts`): implements the existing `Scene` interface (same one `JuliaScene`/`MandelbulbScene` implement — not a special-cased second render path) by compiling the translated shader against the existing `fullscreen.vert.glsl`. Deliberately does NOT read `ParamBus` for its inputs — `ParamBus` is a fixed, Julia-shaped struct (`screen-composites.ts`'s `ScreenParamAssembler`); an arbitrary shader's inputs have arbitrary names, so a new optional `Scene.setInputValues?()` hook (added to `Scene.ts`, harmless no-op for every existing scene) is what `ScreenOutput.update()` calls with typed uniform values reassembled from that frame's raw resolved targets, bypassing the Julia-specific assembler for this scene only.
- **`ScreenOutput.setIsfScene(doc)`/`resetToDefaultScene()`** (new): hot-swaps the active scene and widens/restores `targets` (now a mutable field, was `readonly` — the `VizOutput` interface's own `readonly` only restricts the *interface* view, so this is safe) to include/exclude the loaded shader's own generated targets. Both are purely additive — production's `init()` path never calls either, so the default-scene behavior byte-for-byte matches before this session.
- **Wire-up**: new `debugSetIsfShader`/`isfShaderResult` message pair (`shared/types.ts`, mirrors `debugSetScreenGraph`/`patchbayConfigResult`'s existing shape), handled in `render-worker.ts` via a new `rebuildScreenGraphEvaluator()` helper — tracks `currentScreenGraph` separately from the hardcoded default `screenGraph` specifically so loading/clearing a shader reconstructs the evaluator against the editor's *actual* authored graph, not silently resetting it to the default.
- **Editor UI**: `IsfPanel.tsx` (load-by-file-picker or drag-and-drop, status readout, "Revert to Julia") in a new rail `SectionCard`; `App.tsx`'s `mergedCatalog`/`screenTargetIds` now include the loaded shader's targets; `runtime-bridge.ts` gets `setIsfShader()`/`onIsfResult`.
- **Tests**: `tests/unit/parse-isf.spec.ts`, `tests/unit/isf-targets.spec.ts`, `tests/unit/translate-isf-glsl.spec.ts`. 25 new tests, all passing; full suite now 137.
- **Verified**: typecheck clean (all 4 tsconfigs), full suite passes, `npm run build`/`build:lib` both succeed, dev server (`npm run patchbay`) transforms every new/changed module with no errors.
- **Not verified in a browser**: whether a real ISF file from the wild ecosystem actually loads/renders correctly end-to-end (no browser access this session) — GLSL compilation itself has zero automated coverage in this repo. **Test against a handful of real downloaded `.fs` files from the ISF ecosystem before trusting this beyond the fixture shapes here.**
- **Explicitly deferred, not started**: the ISF superset (exposing `novelty`/`familiarity`/section-confidence as inputs a shader could declare it wants — see §4 above for the underlying signals this now needs); making ISF a swappable scene on the live production site; Shadertoy→ISF import helper; every other protocol (OSC next per priority order, then Art-Net/sACN, DMX-serial, MIDI, ILDA, WLED/E1.31) — none started.

## ISF as real public API (same session, immediate follow-up)

User feedback on the slice above: wanted ISF "runnable" beyond the editor tool, and floated (explicitly "perhaps eventually," not now) converting Julia itself to run through the ISF pipeline. Confirmed scope before coding: (1) add a real, opt-in method to the shipped `VizInstance` — not just the editor's dev-only channel — so any embedding host *could* use it; (2) leave the Julia→ISF dogfood conversion for a later, dedicated session. User also explicitly authorized continuing autonomously through the rest of the master-plan roadmap step by step after this, stopping only when everything's done or the session runs out of budget — so if you're reading this mid-roadmap, that's why work kept going past one slice.

- **Renamed** the render-worker message from `debugSetIsfShader` to `setIsfShader` — it's no longer editor-only, so the `debug` prefix would have been actively misleading.
- **`src/index.ts`**: new `VizInstance.loadIsfShader(source, onResult?)`/`clearIsfShader()`, plus an exported `IsfShaderResult` type. Purely additive — no existing call site calls either method, so nothing about current behavior changes; a host has to opt in.
- **Dev harness** (`src/main.ts`, `npm run dev`): added a file input + "Clear ISF" button proving the real public API path end-to-end through `init()`, not through the editor's separate `RuntimeBridge`.
- **Verified**: typecheck clean, full suite (137, unchanged) passes, `npm run build`/`build:lib` both succeed, `dist/index.d.ts` confirmed to actually contain `loadIsfShader`/`clearIsfShader`/`IsfShaderResult` after the lib build.
- **Not verified in a browser**: no browser access this session, so `npm run dev`'s new file input hasn't actually been clicked.

## OSC out (same session, next priority slice — user authorized continuing through the roadmap autonomously)

Second protocol slice, per priority order (ISF done above, OSC next). Real OSC almost always rides UDP, which browsers categorically cannot do — so this is genuinely a two-half feature: a browser-side WebSocket sender (real code, ships today) plus a tiny local relay process that actually reaches UDP (a real, working, narrowly-scoped seed of the Hysteresis Bridge daemon — OSC only).

- **`src/osc/`** (new, framework-agnostic): `osc-codec.ts` — a real OSC 1.0 wire-format codec, supporting float/int/string/bool args and bundles (fixed `1n` "immediate" time tag). `bus-to-osc.ts` — `signalBusToOscMessages()` maps every `SIGNAL_TAGS`-routable bus signal to one `/hysteresis/bus/<name>` float message; `scope`/`idle`/`dropTrigger` excluded. `osc-out-bridge.ts` — `OscOutBridge`, wraps the Worker-global `WebSocket`, sends an encoded bundle per call, reports connect/disconnect/error via a status callback.
- **Wire-up**: new (real feature, not `debug`-prefixed) message pair `setOscOut`/`oscOutStatus`, handled in `render-worker.ts` (throttled to 20Hz). `oscOutStatus` is NOT one-shot — `src/index.ts` keeps a persistent `oscOutStatusCallback` rather than a fire-once one.
- **Real public API**: `VizInstance.setOscOut(wsUrl, onStatus?)`.
- **`scripts/osc-relay.ts`** (new, Node-only, `ws`/`@types/ws` devDependencies): `createOscRelay({wsPort, udpHost, udpPort})` forwards each WebSocket message byte-for-byte to one UDP datagram via `dgram`. New `npm run osc-relay` script.
- **Tests**: `tests/unit/osc-codec.spec.ts`, `tests/unit/bus-to-osc.spec.ts`, and **`tests/unit/osc-relay.spec.ts`: a real integration test** — a real `ws` WebSocket client sends real OSC bytes to a real relay instance, a real loopback UDP socket asserts the same bytes arrive. First thing in this whole arc that's actually end-to-end verified rather than typechecked+unit-tested-in-isolation-unverified-live.
- **Dev harness**: OSC URL input + connect/disconnect buttons.
- **Verified**: typecheck clean, full suite (150, up from 137) passes, `npm run build`/`build:lib` both succeed (`ws`/`@types/ws` confirmed NOT pulled into `dist/render-worker.js`).
- **Not verified in a browser**: the WebSocket-in-a-Worker path itself — the relay integration test proves the *relay* half works for real, but nothing has actually opened a real browser tab and watched real UDP packets land in TouchDesigner/VCV Rack.
- **Explicitly deferred, not started**: OSC in; every remaining protocol (Art-Net/sACN next, then DMX-serial, MIDI, ILDA, WLED/E1.31).

## Art-Net / sACN out (same session, third priority slice)

Immediately resolved the open question the OSC slice raised ("one growing relay vs. separate processes per protocol") in favor of one generic relay: `scripts/osc-relay.ts` **renamed to `scripts/udp-relay.ts`** and generalized to carry two message shapes on the same WebSocket server — binary frames forward verbatim to the relay's fixed default UDP target (OSC's need), text frames are parsed as a `{host,port,bytes}` JSON envelope and forwarded to *that* per-message destination instead (Art-Net/sACN's need, since both address by universe — broadcast/multicast, a different target per universe). `npm run osc-relay` renamed to `npm run udp-relay`.

A real architectural finding drove scope here: **there is no production fixture patch graph anywhere in the shipped render worker** — `fixtureEvaluator.evaluate(bus, dt)` (App.tsx) had always been ephemeral browser-side React state, evaluated only for the editor's own simulated `FixtureVisuals`. So unlike ISF/OSC, Art-Net/sACN output had nothing real to feed it in production yet. Scoped this slice to the **patchbay editor tool**, same proportional-scope precedent the ISF slice set, and flagged the production `DmxOutput` VizOutput as real, separate, larger future work — not decided here (closed in a later session, see "Wire the fixture patch graph into production" below).

- **`src/dmx/`** (new, framework-agnostic): `artnet.ts` — real Art-Net 4 ArtDMX packet encoding. `sacn.ts` — real ANSI E1.31 Data Packet encoding. `render-dmx-universe.ts` — `renderDmxUniverses()` scales each DMX-patched fixture's resolved channel value onto a real 0..255 DMX byte at its patched address. `dmx-out-bridge.ts` — `DmxOutBridge`, sends one packet per universe over a WebSocket to the relay's JSON-envelope path.
- **`fixture-document.ts`**: new optional `FixtureInstance.dmxPatch?: {universe, startAddress}` + `setFixtureDmxPatch()` mutator.
- **Editor UI**: `FixtureManager.tsx` gained a `DMX: [universe] @ [address]` field per fixture row. New `DmxOutPanel.tsx`.
- **Tests**: `tests/unit/artnet.spec.ts`, `tests/unit/sacn.spec.ts`, `tests/unit/render-dmx-universe.spec.ts`, and — replacing the deleted `osc-relay.spec.ts` — **`tests/unit/udp-relay.spec.ts`: real end-to-end integration tests** for both relay paths. Full suite now 178 (was 150).
- **Verified**: typecheck clean, full suite passes, `npm run build`/`build:lib` both succeed and are byte-identical in size to before this slice (confirming `src/dmx/`/`ws` are genuinely not reachable from the production bundle).
- **Not verified**: no real Art-Net/sACN receiver has actually confirmed these packets — spot-checkable against a known-good tool's own output if this is ever suspected of being subtly wrong.
- **Explicitly deferred, not started**: production `DmxOutput` VizOutput; OSC in; 16-bit/fine-channel DMX support; fixture-profile import; DMX-serial, MIDI, ILDA, WLED/E1.31.

## DMX512 via USB-serial (same session, fourth priority slice)

The one protocol in this whole arc that turned out NOT to need a relay/Bridge daemon at all: Web Serial gives the browser real, direct serial-port access, and Enttec's DMX USB PRO "Widget API" puts the actual DMX signal/break generation inside the *dongle's own firmware* — the host only ever sends an ordinary framed serial write at a fixed baud rate.

- **`src/dmx/enttec-usb-pro.ts`**: `encodeEnttecDmxPacket()` — real Widget API "Output Only Send DMX Packet" (Label 6) framing.
- **`src/dmx/dmx-serial-output.ts`**: `DmxSerialOutput` wraps a real `navigator.serial` `SerialPort` — `connect()` calls `requestPort()` (must run inside a user-gesture handler) then `open({baudRate: 250000})`; `isWebSerialSupported()` feature-detects.
- **A real type-availability snag, found and fixed properly**: `SerialPort`/`navigator.serial` aren't part of TypeScript's bundled `lib.dom.d.ts`. Added `@types/w3c-web-serial` — but this repo's tsconfigs pin an explicit `"types": [...]` allowlist, which disables automatic `@types/*` inclusion entirely, so `"w3c-web-serial"` had to be added to that allowlist too, in both `tsconfig.json` and `tsconfig.patchbay-editor.json`. Worth remembering for any future `@types/*` addition in this repo.
- **Editor UI**: `DmxOutPanel.tsx`'s mode select gained "USB (Enttec-protocol dongle)".
- **Tests**: `tests/unit/enttec-usb-pro.spec.ts`. The `DmxSerialOutput`/Web Serial path itself has **zero automated coverage** — no fake/mock serial port available, and `requestPort()` requires a real user gesture by design — genuinely unverifiable here at any level beyond typecheck.
- **Verified**: typecheck (after the allowlist fix) clean, full suite (183) passes, `npm run build`/`build:lib` both succeed and remain byte-identical in size.
- **Explicitly deferred, not started**: MIDI, ILDA, WLED/E1.31; DMX-serial as a production feature; anything for the raw "Open DMX USB" dongle family (structurally unreachable from Web Serial).

## MIDI in (same session, fifth priority slice)

Another genuinely browser-native leg (Web MIDI), same story as DMX-serial's Web Serial: no relay/Bridge daemon needed, and no new `@types/*` package needed either — Web MIDI's types are already part of TypeScript's bundled `lib.dom.d.ts`.

Scoped deliberately narrower than a full "MIDI routes into the patch graph" feature, said so up front: wiring a CC into the patch graph would mean adding a new node kind to `patchgraph/types.ts` with no real MIDI consumer to justify touching it yet at the time. Built the real parsing/tracking/mapping logic fully, end-to-end, proved it via a live diagnostic panel — the patch-graph integration (`midiCc` node kind) landed in a later session (see "MIDI CC + OSC-in" below).

- **`src/midi/`** (new, framework-agnostic): `midi-messages.ts` — real MIDI 1.0 parsing. `midi-clock.ts` — `MidiClockTracker`, 24-tick/quarter-note timing → live BPM + beat/bar phase; Start resets phase/tempo, Continue resumes without resetting. `midi-cc-input.ts` — `MidiCcInput`, normalizes 0..127 to 0..1, plus `learnNext()`/`cancelLearn()`. `midi-input.ts` — `MidiInput`, real Web MIDI wiring, attaches to every connected input port, re-attaches on hotplug.
- **Editor UI**: `MidiPanel.tsx` — Connect/Disconnect, live clock readout, a rolling log of the last 8 distinct CCs touched.
- **Tests**: `tests/unit/midi-messages.spec.ts`, `tests/unit/midi-clock.spec.ts`, `tests/unit/midi-cc-input.spec.ts`. 18 new tests; full suite now 201.
- **Verified**: typecheck clean, full suite passes, `npm run build`/`build:lib` both succeed and remain byte-identical in size.
- **Not verified**: the real `MidiInput`/Web MIDI wiring itself — no real browser + real MIDI device available.
- **Explicitly deferred, not started** (at the time): a `midiCc` patch-graph node kind; wiring `MidiClockState` into the Conductor's own tempo tracking; SysEx; MIDI output; ILDA, WLED/E1.31.

## WLED/E1.31 on-ramp (same session, sixth priority slice)

The fastest slice of this whole arc: WLED devices already speak real sACN/Art-Net natively, so the Art-Net/sACN work earlier this session already reaches them. What was actually missing was the "friendly" half — a hobbyist point at their WLED device without thinking about universes/sACN at all. WLED's own native realtime UDP protocol is that on-ramp.

- **`src/dmx/wled.ts`** (new): `encodeWledDrgb()` — WLED's "DRGB" protocol. `encodeWledWarls()` — the "WARLS" variant, spec-completeness even though nothing currently produces sparse LED data.
- **The actual reuse, not just "another encoder"**: `DmxOutBridge.send()` gained a `'wled-drgb'` protocol option that takes the SAME per-universe `Uint8Array(512)` buffer `render-dmx-universe.ts` already produces from DMX-patched `rgb`-type fixtures and feeds it straight into `encodeWledDrgb()` — no new fixture/pixel model needed.
- **Editor UI**: `DmxOutPanel.tsx` mode select gained "WLED (UDP realtime)".
- **Tests**: `tests/unit/wled.spec.ts`. 3 new tests; full suite now 204.
- **Verified**: typecheck clean, full suite passes, `npm run build`/`build:lib` both succeed and remain byte-identical in size.
- **Status after this slice**: 6 of 7 protocols real — only **ILDA** remained, flagged as needing real laser-DAC protocol research.

## ILDA / laser DAC protocol layer (same session, seventh and final priority slice this pass)

Explicitly the one protocol flagged to the user as needing real research rather than a from-memory guess, since a wrong binary laser format looks done but silently fails to load — the user confirmed: research it properly, then implement. Used WebSearch + direct `raw.githubusercontent.com` fetches of real reference implementations — this caught a real error before it shipped: an AI-summarized read of the official Ether Dream protocol page said the `DacStatus` struct was 18 bytes; cross-checking against two independent real implementations (`tgreiser/etherdream` Go, `echelon/etherdream.rs` Rust) showed it's actually 20 bytes (response/broadcast packets 22/36 bytes, not 20/34) — both agreed with each other and disagreed with the summarized page text.

- **`src/ilda/ilda-format.ts`**: the real ILDA Image Data Transfer Format (`.ild` files) — sourced from the ILDA Technical Committee's own IDTF spec, cross-checked against `nannou-org/ilda-idtf`. `encodeIldaHeader`/`decodeIldaHeader`, `encodeIldaPoints`/`decodeIldaPoints` for all defined point formats (0/1/4/5) plus format 2's palette, `encodeIldaFile`/`decodeIldaFile` for a complete multi-frame file. **A real bug caught by the tests, not shipped**: format 5's point-record size was written as 7 bytes; the actual layout is 8 — a round-trip test caught the silent corruption.
- **`src/ilda/ether-dream.ts`**: the real Ether Dream live-streaming DAC protocol. `DacStatus`/`DacBroadcast`/`DacResponse` decoders, `DacPoint` encode/decode (18 bytes, little-endian — confirmed different from the ILDA file format's big-endian), command encoders for Prepare/Begin/Data/Stop/EmergencyStop(0xFF, not 0x00 — also corrected via the cross-check)/ClearEStop/Ping. One command (`encodeQueueRateChangeCommand`) is explicitly flagged lower-confidence — neither reference implementation actually implements it.
- **`scripts/tcp-relay.ts`** (new, Node-only, `npm run tcp-relay`): duplexes one WebSocket connection with one TCP connection, zero protocol interpretation. **Real, end-to-end tested**: `tests/unit/tcp-relay.spec.ts` uses a real `net.createServer()` standing in for the DAC and a real `ws` client.
- **Tests**: `tests/unit/ilda-format.spec.ts` (12), `tests/unit/ether-dream.spec.ts` (7), `tests/unit/tcp-relay.spec.ts` (2). 21 new tests; full suite now 225.
- **Verified**: typecheck clean, full suite passes, `npm run build`/`build:lib` both succeed and remain byte-identical in size.
- **Explicitly deferred, not started**: a browser-side `EtherDreamClient` driving the actual prepare→data→begin command sequence; a patch-graph concept of "a stream of laser points" at all; real-hardware verification.

## Full production reliability audit + fixes (same session, user-requested "/ultrareview"-style pass)

`/ultrareview` itself couldn't run (the uncommitted diff — this whole session's 7-protocol arc plus prior sessions' history — exceeded its size limit: 75 files/8,888 lines vs. its 500-file/8,000-line ceiling). Substituted two sequential read-only audit forks instead, scoped explicitly to the production 24/7 render path first, plus a lighter UI/UX pass on the editor. Every finding below was verified against the actual code before fixing and every fix is covered by the existing or a new test.

**Critical (fixed):**
- **WebGL context-loss recovery reused dead GL objects — the single most important finding.** `ScreenOutput.init()` is re-run on every `webglcontextrestored` event, reusing the same `ScreenOutput` instance. Its `allocatePipeline()` only calls `new Xxx(...)` for a pass whose field is still `null` — after a restore, every pass field already holds a pre-loss JS wrapper object, so it took the "already exists, just `resize()`" branch, and `resize()` on every pass only recreates FBOs, never the program/VAO/texture created solely in each pass's constructor; `compositePass` specifically was never reconstructed past the very first init at all. Net effect: a real context loss left the screen black/frozen **permanently** on an unattended 24/7 background — the exact failure the loss/restore listeners were built to prevent, silently defeated by the pass-reuse logic underneath them. **Fixed**: `ScreenOutput.init()` now disposes the current scene and nulls every pass field before calling `allocatePipeline()`, forcing full reconstruction on every call. Also preserves an active ISF scene across a restore. **Not covered by an automated test** — GL object lifecycle across a real context-loss event has zero test coverage in this repo; the fix is verified by code inspection + typecheck/build only.
- **`AudioEngine.attach()` had a real re-entrancy race that could leave two live AudioWorklet pipelines running forever.** `index.ts`'s `tryAttachAudio()` polls every 300ms, guarded only by `engine.attached` — which stays `false` until `attach()` fully resolves, including `await ctx.audioWorklet.addModule(workletUrl)`. On a slow first load, that await can outlast 300ms, letting a second `attach()` start before the first finishes; each creates and wires its own `AudioWorkletNode` into the same shared `listeners` Set, so both stay alive indefinitely. **Fixed**: `AudioEngine` now tracks its own in-flight `attachPromise` and returns it to a concurrent caller instead of starting a second attach.

**Moderate (fixed):**
- **`OscOutBridge` never reconnected after a drop.** Fixed: auto-reconnects after 2s unless `disconnect()` was called explicitly.
- **`StructureSource`'s event/onset cursors could permanently skip a sidecar event if `positionSec` ever briefly regressed without going through `resyncTo()`.** Fixed: both `fuse()` and `synthesize()` now call a new `healPositionRegression()` internally at entry. New test: `tests/unit/structure-source.spec.ts`'s "self-heals a brief backward position jitter" case.
- **`evaluate-node.ts`'s `smoothstep` curve silently clamped bipolar signals' entire negative half to zero**, inconsistent with `exp`/`log`. Fixed to be sign-preserving. Had to fix the legacy `patchbay/curves.ts` identically in the same pass (the migration equivalence test cross-checks exactly this curve against the bipolar `bandTilt` signal). New test: `tests/unit/evaluate-node.spec.ts`.
- **A diverging Julia perturbation reference orbit was unguarded at the source.** `updateReferenceOrbit()` now checks `Number.isFinite` each iteration and, on divergence, holds the last finite point for the remainder of the texture instead of uploading `Infinity`/`NaN`.

**Polish:**
- Removed a "temporary… remove once confirmed" diagnostic `console.log` in `JuliaScene.ts`'s zoom-floor reset path.
- Added a `:focus-visible` outline rule to the patchbay editor's global styles.
- Considered but declined: extracting three panels' inline `style={{}}` usage into named CSS classes — checked first, established files use inline styles MORE, not less, so this is already the editor's actual convention.

**Verified overall**: typecheck clean, full suite (229, up from 225) passes, `npm run build`/`build:lib` both succeed.

**Explicitly not covered by this audit pass**: a full read of `render-worker.ts`'s adaptive-quality heuristics, the GL passes' shader math beyond the memory-field NaN guard already covered by a prior session, and the DMX/MIDI/ILDA modules' own internal correctness beyond the spot-checks already covered in each protocol's own session entry above.

**Status after this pass: all 7 protocols have real, tested work landed** — though several stay intentionally scoped to editor-tool/protocol-layer-only rather than full production pipelines. The natural next arc: either closing specific gaps (OSC in, a `midiCc` patch-graph node, a production `DmxOutput`/`EtherDreamClient`, a laser point-source concept), or moving on to other backlog areas entirely — a fresh gap-analysis pass against the full backlog is the right way to pick, not assuming protocol order continues to dictate priority now that it's fully covered.

## Wire the fixture patch graph into production (this session)

Closed the recurring gap flagged across the previous session's Art-Net/sACN/DMX-serial/WLED entries: every DMX-shaped protocol was editor-tool-only, with fixture-graph evaluation living entirely as ephemeral React state in the patchbay editor. A host embedding this package had no way to actually drive physical fixtures — only the dev tool could.

- **New `FixtureOutput`** (`src/render/conductor/outputs/FixtureOutput.ts`) — a worker-resident counterpart to `DmxOutPanel`'s browser-side logic: holds the current `FixtureDocument`, derives its target catalog, owns a `DmxOutBridge` connection. `send(resolved)` renders DMX universes and forwards them over the same WebSocket relay OSC uses. Deliberately does NOT cover USB/Web Serial — `DmxSerialOutput.connect()` needs a main-thread user-gesture `requestPort()` call a background worker can never trigger, so that leg stays editor-tool-only with no obvious production path.
- **`render-worker.ts` wiring**: a `fixtureGraphEvaluator` (nullable — no sane default graph exists for an unpatched install) evaluates every frame, throttled to ~25Hz for the actual wire send. Three new message kinds: `setFixtureDocument`, `setFixtureGraph` (construction-time-validated), `setFixtureOut`.
- **Real public API** on `VizInstance`: `setFixtureDocument()`, `setFixtureGraph()`, `setFixtureOut()` — opt-in/additive. Re-exports `FixtureDocument`/`FixtureInstance`/`DmxPatch`/`PatchGraph`/`FixtureOutConfig`.
- **Not done this session**: the patchbay editor itself still ran its own separate ephemeral evaluation rather than dogfooding the new production API (closed in the next session below). Also unchanged: 16-bit/fine-channel support, fixture-profile import, USB production wiring.
- Verification: typecheck clean, full suite (229, unchanged — pure wiring/glue), `npm run build`/`build:lib` both succeed. **Not verified against a real Art-Net/sACN receiver or in a browser.**

## MIDI CC + OSC-in patch graph routing, and dogfooding the fixture API in the patchbay editor (this session)

Continuation of the previous session's "wire the fixture patch graph into production" work — user asked to do all three of the natural-next-slices flagged there in one pass: OSC-in routing, a `midiCc` patch-graph node, and dogfooding the new fixture production API inside the patchbay editor itself.

- **Two new patch-graph node kinds** (`patchgraph/types.ts`): `MidiCcNode` (`ccKey`) and `OscInNode` (`address`) — both zero-input, external-state-reading nodes shaped exactly like `SignalNode`. `PatchGraphEvaluator.evaluate()` gained an optional third `external: { midiCc?, oscIn? }` parameter. A `midiCc`/`oscIn`-fed target is exempt from the servo-safety "unsmoothed transient" warning, since neither has a bus timescale tag at all.
- **`OscInBridge`** (`src/osc/osc-in-bridge.ts`) — the "OSC in" half OSC out never got: decodes real inbound OSC packets into a `Map<address, number>` a patch graph reads from. `scripts/udp-relay.ts` gained an optional `--osc-in-port` (forwards every inbound datagram to every connected browser tab as a binary WS frame — opt-in).
- **Production API**: `VizInstance.connectMidiIn()`/`disconnectMidiIn()` and `setOscIn()` — both opt-in/additive.
- **Fixture API dogfooded in the editor**: `App.tsx` no longer runs its own `PatchGraphEvaluator` copy for fixtures — it now calls `bridgeRef.current?.setFixtureDocument()`/`setFixtureGraph()`, the exact same messages `VizInstance` sends, and reads the worker's own evaluation back via a new `fixtureValues` field on the dev-only `signalBus` debug-stream message. `DmxOutPanel` now delegates Art-Net/sACN/WLED to `setFixtureOut()` — kept its own send loop **only** for USB (Web Serial genuinely can't run inside a worker).
- **Not done this session**: no address-pattern matching for `oscIn` (exact address match only), no live-value-log UI for OSC-in, MIDI clock sync is still not wired into the Conductor's tempo tracking, no macro/sub-patch blocks, graph versioning/undo.
- Verification: typecheck clean throughout, full suite grew from 229 → 242, `npm run build`/`build:lib` both succeed, both dev servers transform every new/changed module with no errors. **Not verified**: no real MIDI device, no real external OSC sender, no real Art-Net/sACN receiver, no browser at all.

## Layer 2 musical understanding + docs consolidation (this session)

User uploaded `SINTEZA_UNDERSTANDING.md` (a research-grounded design doc for the Feature Engine's
temporal/structural features — multi-scale novelty, harmony, "track prominent elements") and
asked for two things: implement its full 7-step build order, and first consolidate the scattered
AI-facing docs (this file + `SINTEZA_VIZ.md` + `SINTEZA_SIGNAL_BUS.md` +
`hysteresis-master-prompt.md` + `NEXT_SESSION_PROMPT.md`) into one file, keeping `docs/*.md`
separate since those are real per-protocol references for human users too.

**Docs consolidation**: done first, this file is the result — §1-§3 synthesize what those five
docs said (resolving real drift, e.g. `SINTEZA_SIGNAL_BUS.md`'s retired flat Patchbay/Route
model vs. its own addendum), §4 is `SINTEZA_UNDERSTANDING.md` folded in close to verbatim, §5 is
`NEXT_SESSION_PROMPT.md` trimmed, and this §6 is the untouched chronological history all five
docs used to disagree around. `SINTEZA_VIZ.md`, `SINTEZA_SIGNAL_BUS.md`,
`hysteresis-master-prompt.md`, `NEXT_SESSION_PROMPT.md` are deleted — fully absorbed.
`README.md`'s two references to `SINTEZA_VIZ.md` now point here instead.

## Layer 2 musical understanding — implementation (same session, immediate follow-up)

All 6 of §4.5's build-order steps landed (the doc's 7 numbered ambitions collapse to 6
implementation slices — beat-synchronous aggregation shares a call site with multi-scale
novelty, so it isn't a separate slice). Grounded in the real current code first (novelty.ts's
`cosineSimilarity`/`NoveltyRingBuffer`, familiarity.ts's tracker, Conductor.ts's beat-boundary
edge-detection pattern already used for `downbeatPulse`, `drop-detector.ts`'s internal
fullness/onset-jump math, `scripts/structure.ts`'s direct reuse of the browser worklet modules)
before writing anything.

- **Multi-scale novelty + beat-sync aggregation** (`src/render/conductor/familiarity.ts`,
  `Conductor.ts`): generalized `FamiliarityTracker` into `SimilarityTracker` (window size now a
  constructor param; `FamiliarityTracker` kept as an alias at the original ~12s default — zero
  behavior change for `familiarity` itself). Conductor now runs two instances — the existing one
  (`noveltySection = 1 - familiarity`) and a new short (~5s) one (`noveltyLocal`) — both pushed
  only on a beat-boundary edge (the same `beatPhase < lastBeatPhase - 0.5` wraparound check
  `beatPulse`/`downbeatPulse` already used), not every render frame, per the doc's "beat-
  synchronous features are the pro move" §4.1. **A real bug caught by a new test, not shipped**:
  `noveltyLocalValue`'s pre-first-sample default was initially 0 (copy-pasted from
  `familiarityValue`'s default) — wrong, since it stores novelty directly (1 - similarity), not
  similarity; "nothing to compare against yet" should read as maximally novel (1), not 0. Fixed
  before commit. New `tests/unit/novelty-multiscale.spec.ts` (4 tests) drives a Conductor through
  a real click-train of beat-boundary crossings (a naive fixed-`beatPhase` test never triggers a
  push at all — worth remembering, a second self-caught test bug: an early draft's A/B/A motif
  test called the beat-driving helper three separate times, each resetting its own local `t=0`,
  silently breaking every window-eviction time calculation across phases — fixed by driving the
  whole multi-phase sequence through one continuous call).
- **`onsetDensity`/`fullness` as real bus signals** (new `src/audio/worklet/brain/activity.ts`):
  extracted `FullnessTracker`/`OnsetDensityTracker` out of `DropDetector`'s inline envelope
  followers — same math, delegated, `tests/unit/drop-detector.spec.ts`'s existing 6 tests confirm
  zero behavioral drift from the extraction. `feature-worklet.ts` now owns its own separate
  instances (same "separate instance per consumer" precedent `novelty.ts`'s header already
  documents), computed **unconditionally every hop** — moved the contrast-preserving
  `dropEnergyEnvelope`/`dropEnergyNormalizer` calculation outside the `detectorsEnabled` gate so
  these two are genuinely always-alive, not gated behind the same toggle the sparse section
  detectors are. New `tests/unit/activity.spec.ts` (7 tests: the trackers in isolation, plus
  Conductor pass-through/clamping/defaulting).
- **Chromagram + harmonic novelty** (new `src/audio/worklet/chroma.ts`): a 12-bin pitch-class
  energy vector (MIDI-mod-12 convention, bins outside C1-C8 skipped), computed every hop from the
  same mono magnitude spectrum `feature-worklet.ts` already has. Exposed on the bus as a raw
  pass-through (`chroma`, same treatment as `scope`) plus two derived scalars: `harmonicNovelty`
  (a *third* `SimilarityTracker` instance, own ~6s window, same beat-boundary gating) and
  `chromaRootHue` (argmax pitch class → 0..1, recomputed every frame, not beat-gated — cheap, no
  tracker needed). New `tests/unit/chroma.spec.ts` (8 tests): synthetic pure-tone spectra
  (A4=440Hz → pitch class 9, C4 → pitch class 0) prove the bin-folding math directly, plus
  Conductor-level tests proving `harmonicNovelty` spikes on a real key change after settling low.
- **Schema-3 sidecar + Demucs stem-presence** (`src/shared/sidecar.ts`, new `scripts/demucs.ts`,
  `scripts/structure.ts`, `scripts/analyze.ts --stems`): **deliberately deviated from the design
  doc's own stated versioning convention** ("bump the literal + guard + every consumer together,
  no migration path") — that would make `isSidecar()` reject the 5 real schema-2 sidecars already
  published to the live site, a direct violation of this file's own §5 rule #1 ("never break the
  live production path"), which overrides a doc's stated convention when they conflict. Landed
  instead as a **backward-compatible** bump: `SIDECAR_SCHEMA_VERSION = 3` is what `analyze.ts`
  writes for any newly-generated sidecar, but `isSidecar()` accepts `schema === 2 || schema ===
  3`, and the new `stemPresence`/`SidecarSection.label` fields are optional — a schema-2 sidecar
  keeps validating and working exactly as before, zero risk to the deployed tracks. User's
  explicit choice for the separation runtime: shell out to the real Python Demucs CLI (not an
  ONNX bundle) — `runDemucsSeparation()` spawns `python3 -m demucs -n htdemucs -o <tmpdir>
  <input.wav>`, reads back the 4 stem WAVs Demucs' own fixed output layout produces, fails loudly
  with a clear "pip install demucs" message if the subprocess isn't found (correct here — this is
  a manual, per-track, offline tool, never part of CI/the shipped browser bundle: confirmed
  `npm run build`/`build:lib` stay byte-for-byte on the render-worker/lib output size, i.e.
  `scripts/demucs.ts`/`scripts/structure.ts`'s stem code is genuinely unreachable from either).
  `computeStemPresence()` computes vocals/drums/bass/other as RMS-per-hop envelopes
  (envelope-followed + adaptively normalized against each stem's own dynamic range — deliberately
  simpler than the main mix's full FFT/band pipeline, since "is this stem present" only needs
  broadband loudness) at the exact same `envelopeRate`/hop-grid the rest of the sidecar's
  envelopes use, so `StructureSource.sampleEnvelope()` needed zero changes to consume them.
  `StructureSource.fuse()`/`synthesize()` expose `vocalPresence`/`drumsPresence`/`bassPresence`/
  `otherPresence`/`leadPresence` on `StateFrame` when a sidecar has `stemPresence`, `undefined`
  otherwise (Conductor is what actually defaults the bus signal to 0) — the same accepted
  sidecar-only-signal precedent `buildProgress`/`tension` already set. New
  `tests/unit/sidecar.spec.ts` (7 tests, including the explicit "still accepts an already-
  published schema-2 sidecar" regression guard), extended `tests/unit/structure-source.spec.ts`
  (4 new tests), extended `tests/unit/analyze.spec.ts` with `computeStemPresence` tests against
  synthetic per-stem audio (a loud/sustained stem reads high, a silent one low; a sustained tone
  outlasts a louder-but-transient competitor in `leadPresence`'s envelope-followed reading). **The
  Demucs subprocess call itself is not exercised by any automated test** — genuinely can't be
  without a real Python + `demucs` environment, absent in this session's own sandbox — but it
  *was* verified by hand, once real Python access became available, in an immediate follow-up
  session; see that session's own §6 entry below for the real-track run.
- **Heuristic sidecar section labeling** (`scripts/structure.ts`'s `labelSections()`,
  deterministic — no LLM/embedding infra exists in this repo, and the design doc itself flags
  learned zero-shot labeling as an optional, heavy "ceiling"): existing `build`/`break`-kind
  sections get a plain label (`'build'`/`'breakdown'`); genuinely new value is synthesizing
  `'intro'`/`'outro'` spans from whatever's *not* covered by any detected section/event — the
  track's start-to-first-structure and last-structure-to-end gaps, otherwise silently unlabeled
  even though they're real, common structure for this project's typically section-sparse
  sidecars. Takes an optional `stemPresence` parameter to raise confidence (skips a positionally-
  plausible intro/outro if the mix is actually loud throughout that span — not a real intro then)
  — used by `analyzeMix()` itself without presence data (called before `--stems` ever runs, so
  every schema-3 sidecar gets best-effort positional labels regardless), available for a caller
  to re-invoke with real presence data but **not currently re-invoked that way** — `analyze.ts`
  does not call it a second time after computing `stemPresence`, so real presence data doesn't
  actually refine an already-decided label in the current wiring; flagged here rather than left
  as a silent gap between the doc comment's intent and the actual call graph. New
  `tests/unit/section-labels.spec.ts` (7 tests).
- **Lead salience within `other`** (`scripts/structure.ts`'s `computeLeadPresenceEnvelope()`,
  part of the same `--stems` pass as stem presence above, per the design doc's own simpler
  suggested approach §3.3): a per-hop FFT on the separated `other` stem, tracking the *sustained*
  peak-bin magnitude (a slower 400ms release than presence's 200ms is the actual "sustained, not
  instantaneous" distinction) rather than a real isolated-lead-instrument signal — approximate,
  documented as such everywhere it's surfaced (`SidecarStemPresence`'s doc comment,
  `StateFrame.leadPresence`'s doc comment, `SignalBus.leadPresence`'s doc comment).
- **Deliberately not done, explicitly out of scope for this pass**: none of the 12 new bus
  signals (`noveltyLocal`/`noveltySection`/`fullness`/`onsetDensity`/`harmonicNovelty`/
  `chromaRootHue`/`chroma`/the 5 presence signals) are wired into any default screen or fixture
  patch-graph route — this pass's definition of done was "the signal exists, is correct, is
  tested," not "the screen visibly reacts to it," per the plan's own stated scope (Part B's
  context note). Wiring them into `configs/screen-graph.ts`'s default routes is real, natural
  follow-up work, not started. Also not done: no repetition map ("this section = that earlier
  one," needs a full offline SSM the design doc itself calls out as not attempted here); no ISF-
  superset input types exposing these new signals to a loaded shader (§3.7's own note already
  flagged this as a separate step); the `labelSections()`/`stemPresence` re-invocation gap noted
  above.
- **Verified**: `npm run typecheck` (all 4 tsconfigs), `npm test` (281 tests, up from 242 at the
  start of this session — 39 new across 6 new test files plus extensions to 3 existing ones),
  `npm run build`, and `npm run build:lib` all green throughout, checked after every one of the 6
  steps above, not just at the end. **Not verified this session**: no real browser (none of this
  touches the GL/render path at all, so lower-risk than this file's usual GL caveats, but still
  genuinely unclicked), and the Demucs `--stems` path had never actually separated a real track —
  **both the live-signal pipeline and the Demucs path were verified against a real track in an
  immediate follow-up session**, see its own §6 entry below.

## Headless real-audio verification of the whole Layer 2 arc (immediate follow-up session)

User asked for the previous session's whole build order to be run headlessly against a real
track — a Daft Punk "Instant Crush" MP4 already sitting in `~/Downloads`. Closes the two
"not verified" gaps flagged at the end of the previous entry.

- **Audio extraction**: `ffmpeg -i <mp4> -ac 2 -ar 48000 -sample_fmt s16 <wav>` — a real 5:40
  (339.8s) 48kHz stereo WAV, `scripts/wav.ts`'s hand-rolled RIFF reader (16-bit PCM) confirmed to
  decode it with no changes needed.
- **Core pipeline (no `--stems`)**: `npm run analyze` produced a real schema-3 sidecar — 110.3bpm
  (Instant Crush's actual tempo is ~117bpm; a live PLL locking onto a plausible harmonic/
  neighboring tempo on a synth-heavy track is a known, acceptable category of drift, not a bug),
  615 beats, 155 events, 917 onsets, all envelopes genuinely varying (6367/6371 energy samples
  nonzero) — confirms `scripts/structure.ts`'s existing pipeline still works end-to-end on a real
  MP4-sourced WAV, unaffected by this arc's changes.
- **The actual new-signal verification**: a throwaway diagnostic script (written directly in
  `scripts/`, deleted immediately after use — never committed) replayed the same real audio
  through the exact hop-by-hop primitives `feature-worklet.ts` uses live (`WindowedFFT`,
  `computeChroma`, `FullnessTracker`/`OnsetDensityTracker`, `BeatTracker`/`BarTracker`) plus a
  real `Conductor` instance, logging min/max/mean for every one of this arc's new bus signals
  across all ~31,855 real hops. **Zero non-finite (NaN/Infinity) values across the entire real
  track** — the concrete thing synthetic fixtures can't prove (real audio has far messier
  transients/silence/clipping than hand-picked test vectors). Every signal showed genuine
  variation, not a flat/degenerate reading: `fullness` 0–0.72 (mean 0.56), `onsetDensity` 0–1
  (mean 0.48), `chromaRootHue` spanning 0–0.92 (real harmonic movement, not stuck on one pitch
  class), `noveltyLocal`/`noveltySection` mostly low with real spikes to 1 (a heavily
  loop-based track reading as mostly-familiar, exactly as expected, with real novelty at genuine
  transitions), `harmonicNovelty` similarly low-mean/real-spikes, `familiarity` mean 0.98 (a
  Daft Punk track being extremely repetitive is a real, correct reading, not a bug).
- **Demucs**: installed for real in an isolated venv (`python3 -m venv` + `pip install demucs` —
  pulled in a full CUDA-enabled PyTorch stack despite CPU-only execution, ~4.8GB; `torch.cuda.is_available()`
  confirmed `False`, ran on CPU throughout). **A real, previously-undiscovered gap found and
  fixed on the spot**: `demucs`'s own declared dependencies didn't pull in `numpy`/`soundfile` in
  this environment — `python3 -m demucs --help` failed with `ModuleNotFoundError: No module named
  'numpy'` before either could be installed; fixed by `pip install numpy soundfile` alongside
  `demucs` itself. Worth remembering for `docs/`-level guidance if this ever gets written up for
  end users: `pip install demucs` alone was not sufficient in this environment.
  `scripts/analyze.ts --stems` (unmodified from the previous session — no code changes were
  needed) then ran the real thing: `python3 -m demucs -n htdemucs` separated the full 5:40 track
  in ~1:45 wall-clock on CPU, all 4 stem WAVs written to Demucs' own fixed output layout exactly
  as `scripts/demucs.ts` expected, `computeStemPresence()` consumed them with zero errors,
  producing a real schema-3 sidecar with `stemPresence` populated: `vocals` mean 0.674, `drums`
  mean 0.481, `bass` mean 0.685, `other` mean 0.785, `leadPresence` mean 0.803 — all spanning
  close to the full 0..1 range, not degenerate. **Confirmed through the real production consumer
  path, not just raw JSON inspection**: `isSidecar()` accepted the real output, and
  `StructureSource.synthesize()` at six sampled positions across the track (t=10s..300s) returned
  distinct, real, time-varying `vocalPresence`/`drumsPresence`/`bassPresence`/`otherPresence`/
  `leadPresence` values at each — including `drumsPresence` dropping to 0.016 by t=300s, which
  lines up with this track's real stripped-down/vocal-heavy ending.
- **Section labeling on this real track**: only one section detected/labeled (`{start:0, end:2.592,
  kind:'break', label:'breakdown'}`) — consistent with this file's long-standing "sidecar section
  detection is currently sparse" known limitation, not a regression from this arc's changes; the
  heuristic intro/outro synthesis in `labelSections()` didn't fire here because the earliest
  structural boundary (a `breakStart` event at t=0) already sits at the very start, leaving no
  gap for an intro span to occupy.
- **Not done**: no code changes were needed or made this session — this was purely a
  verification run. The venv and downloaded model weights live in this session's job-scratch
  directory (cleaned up automatically when the job is deleted), not committed anywhere.
- **Verified**: `npm run typecheck`/`npm test` (281, unchanged) still pass after this session's
  activity (git status showed nothing unexpected touched in the repo — only tmp/scratch
  directories were used for the audio/venv/sidecar files), confirming the whole Layer 2 arc from
  the previous session is real and correct against genuine audio, not just synthetic fixtures.
  **Still not done**: none of the new signals are wired into any default screen/fixture route
  (unchanged from the previous session — still real, separate follow-up work); no browser
  verification (this arc never touched the GL/render path, so this is a pre-existing, not new,
  gap).

## Real bug found and fixed: SimilarityTracker leaked forever across a position loop/seek (same session, immediate follow-up)

User reframed the priority explicitly: the deployed background **must play for days unattended
without breaking** — non-negotiable. Before proposing next steps, ran a read-only, code-level
audit of this whole session's arc specifically for multi-day-runtime risk (unbounded growth,
NaN propagation, interaction with the earlier "24/7 reliability audit" session's fixes). Found
one real, high-priority bug, fixed immediately rather than just reported.

- **The bug**: `SimilarityTracker.sample()` (`src/render/conductor/familiarity.ts`) evicts its
  `{t, vec}` buffer with `while (buffer[0].t < cutoff) buffer.shift()`, which silently assumes
  `t` only ever increases. It doesn't — `StructureSource.synthesize()` feeds `t: positionSec`
  straight from the host's own position feed, and **position-only sync is this package's actual
  production integration** (this file's own "Position-only sync mode" section), where `t`
  genuinely moves backward on every loop repeat or seek. The instant that happens, `buffer[0].t
  < cutoff` can go permanently false (`cutoff` shrinks below the stale entries' `t`), eviction
  silently stops working, and the buffer grows roughly one entry per beat, forever, across every
  subsequent loop cycle. `Conductor` is one long-lived instance for the life of the render worker
  — never reconstructed on trackchange/seek — so this compounds without bound across days of
  unattended looped playback, hitting all three `SimilarityTracker` instances this session added
  (`familiarityTracker`/`localNoveltyTracker`/`chromaNoveltyTracker`). **This is the exact bug
  class `StructureSource`'s own `healPositionRegression()` already exists to fix** (a prior
  session's own regression test literally proved the same failure mode for event/onset cursors)
  — it was just never applied to this newer tracker.
- **The fix**: `sample()` now detects a backward jump (`t < lastEntry.t - 1e-6`, the same epsilon
  `healPositionRegression()` uses) and clears the buffer entirely rather than resyncing a cursor
  — a similarity window has no sane partial recovery from a jump (the "recent past" it held is
  genuinely gone), so a full reset is the correct self-heal, not a resync. New regression test in
  `tests/unit/familiarity.spec.ts`: drives the tracker through 20s of playback, records the buffer
  size, then simulates 50 loop cycles (a real multi-day run would do this thousands of times) and
  asserts the buffer stays bounded to roughly one window's worth of entries instead of growing to
  ~51 loops' worth (~30,600 entries, what the unfixed version would have leaked).
- **Audit also confirmed safe** (no changes needed): `FullnessTracker`/`OnsetDensityTracker` are
  pure fixed-size scalar state, no arrays. `chroma.ts`'s buffer is pre-allocated once and reused
  every hop (no per-hop GC pressure) — only the beat-gated `Array.from(frame.chroma)` push into
  `chromaNoveltyTracker` allocates, and that's the same low-frequency, bounded pattern the fix
  above now also covers. `NoveltyRingBuffer` (`DropDetector`'s own primitive) is genuinely
  fixed-capacity/count-indexed, immune to this bug class entirely. `chroma.ts`'s `Math.log2` is
  guarded by the `MIN_HZ`/`MAX_HZ` range filter before it ever runs — no unguarded log/division
  found anywhere in this session's new code. This session's changed files have zero overlap with
  the files the earlier "24/7 reliability audit" session fixed (`render-worker.ts`/
  `ScreenOutput.ts`/`AudioEngine.ts`/`src/index.ts` — confirmed via `git diff --stat`, all
  untouched). Moving `dropEnergyEnvelope`/`dropEnergyNormalizer` outside the `detectorsEnabled`
  gate (an earlier step this session) is just the same "always compute" pattern
  bands/centroid/flatness already used unconditionally — no new risk class. No new
  timers/listeners/subscriptions were added anywhere in this session's code (grepped for
  `setInterval`/`setTimeout`/`addEventListener` across every changed/new file — zero matches).
- **Verified**: `npm run typecheck`, `npm test` (282, up from 281 — the one new regression test),
  `npm run build`, `npm run build:lib` all green.
- **Not done / explicitly deferred**: no broader sweep of the *pre-existing* Conductor/detector
  state for the same backward-`t` bug class beyond what this audit specifically checked (the
  audit was scoped to this session's new code, per the actual ask) — `BeatTracker`/`BarTracker`/
  `BuildDetector`/`BreakDetector`/`DropDetector` all predate this session and were not
  re-audited for the same failure mode here; worth a dedicated pass if "days without breaking" is
  being taken further. Also still not done: the signal-routing/screen-wiring and browser
  verification gaps noted in every entry above.
- **The dedicated pass above happened immediately, same session**: checked every pre-existing
  Layer 1/2 class (`BeatTracker`/`BarTracker`/`BuildDetector`/`BreakDetector`/`DropDetector`) for
  the identical bug class. **All immune, most by construction, one structurally unreachable
  reason common to all of them**: `StructureSource.synthesize()` — the only place `t` can move
  backward — never calls into any of these five classes at all; it derives beat/bar phase itself
  via the pure, stateless `beatPositionAt()` against the sidecar's static `beats[]` array. All
  five are worklet-only, constructed once in `feature-worklet.ts`, fed exclusively by
  `currentTime` (the `AudioWorkletGlobalScope` clock — spec-guaranteed monotonic, never reachable
  from the position-only path). `BeatTracker`/`BarTracker` use fixed-size, count-indexed
  `Float32Array`s (no `.push()`, immune regardless); `BuildDetector`/`BreakDetector` hold no
  arrays at all; `DropDetector`'s novelty term already uses the fixed-capacity `NoveltyRingBuffer`
  (immune). One minor, non-urgent note: `DropDetector`'s scalar `tNow`-comparison fields
  (`refractoryUntil`/`armedAt`/`startedAt`) could theoretically stay suppressed/stuck-armed longer
  than intended after a backward jump *if* it were ever reachable that way — it isn't, so this is
  informational only, not a fix. `Conductor`'s own decay math uses `dt` sourced from a
  `requestAnimationFrame` timestamp in `render-worker.ts` (spec-monotonic), so it can't go
  negative and invert `Math.exp(-dt/TAU)` into growth either. **The `SimilarityTracker` fix above
  was the only real gap in the whole pipeline for this bug class — closed.**

## The Hysteresis format, Phase 0/1: `hysteresisSignal` inputs + reserving stateful scripts (same session, immediate follow-up)

User asked for a phased roadmap toward two things: (1) a real "Hysteresis format" — a superset of
ISF letting a shader declare it wants a live Feature Engine signal, the master-prompt's own
stated differentiator (§4.5) — built to a genuinely solid state, then (2) eventually porting the
built-in Julia scene itself onto that format instead of staying hardcoded native TypeScript, per
the project's own design principle (§3.6: *"if the built-in Julia fractal can't be forked/edited
the same way a user's custom ISF script can, the extensibility story is fake"*).

Scoped explicitly before writing anything (via a real plan-mode pass, grounded in the actual
code): `JuliaScene.ts` itself only reads 9 fields directly off `ParamBus` — the other ~13 of the
full 22-field `ParamBus` drive the surrounding memory-field/composite pipeline, not Julia's own
navigation. Its autopilot (vortex-search, perturbation orbits, spring-damper `c`-drift) is 1011
lines of stateful per-frame JS logic, something a single GLSL fragment shader categorically
cannot express — ISF's own model ("shader + JSON header") has no concept of persistent JS state
at all. User confirmed directly that an optional, per-file JS state-script companion is a real,
wanted part of the format's architecture, not just a nice-to-have ("we need state, that's the
whole idea") — so this pass's scope was widened to include *reserving* that concept at the file-
format level now (recognized, clearly rejected), even though the actual execution engine is
later work, so a future Julia-port file's shape doesn't need a breaking change when that engine
lands.

**The roadmap, for whoever picks this up next:**
0. Spec the extension mechanism — done this session.
1. Build it — done this session.
2. Prove it standalone. **Headless half done, same session, immediate follow-up** — see that
   session's own entry below: a real downloaded ISF ecosystem shader (not a self-authored
   fixture) parses/translates cleanly, and an augmented copy with a `hysteresisSignal` input
   proved end-to-end against real analyzed audio. **Still not done**: loading it through the
   editor and confirming it's visibly reactive in a real browser — no browser access in either
   session, same standing caveat as every other GL/visual slice in this file.
3. Design the compact signal set for Julia specifically — a real design conversation with the
   user once this mechanism exists to design against, not mechanical work. **Not done.**
4. The actual port + the state-script execution engine, designed against Julia's autopilot as
   the concrete motivating case (not guessed at in the abstract). **Not done**, the big one.

**This session covers Phase 0/1 only:**

- **`hysteresisSignal`** (`src/isf/types.ts`/`parse-isf.ts`/`isf-targets.ts`): a new ISF input
  `TYPE` alongside the existing `float`/`bool`/`long`/`color`/`point2D`. Declared as `{ "NAME":
  "novelty", "TYPE": "hysteresisSignal", "SIGNAL": "noveltyLocal" }` — `SIGNAL` validated at parse
  time against `SIGNAL_TAGS` (`src/render/conductor/types.ts`, the same ~35-name set the patch
  graph's own `signal` node already reads from), rejected with the full valid-name list in the
  error message if unknown. **Deliberately minimal new mechanism**: it becomes a perfectly
  ordinary routable `TargetDecl`, exactly like every other ISF input already is — no implicit
  auto-wiring, no second reading path that bypasses the patch graph. This keeps R2 (`VizOutput`
  never sees the raw `SignalBus`, only resolved targets — confirmed still true by reading
  `ScreenOutput.update()`'s actual signature before designing this) and R4 ("routing is data")
  intact; the only real difference from a plain `float` input is self-documentation (the shader
  states which bus signal it's shaped for) and a signal-appropriate default range (`0..1`
  unipolar, `-1..1` for the known bipolar signals `bandTilt`/`pan` — a small explicit lookup
  table in `isf-targets.ts`, not a general solve). `translate-isf-glsl.ts`'s `glslType()` maps it
  to a plain `float` uniform, same as the standard `float` type — the `TYPE` distinction only
  matters at the routing layer, not to the shader itself.
- **`HYSTERESIS_SCRIPT` reserved, not executed**: `parseIsf()` now throws
  `IsfUnsupportedFeatureError` if a shader's header declares a non-empty `HYSTERESIS_SCRIPT`
  string — same "reject clearly rather than silently mis-render" discipline already applied to
  multi-pass/`PERSISTENT`/`IMPORTED`/unsupported-input-type shaders. Costs almost nothing to add
  now and buys real value later: a Julia-port file's shape is stable from day one.
- **Tests**: `tests/unit/parse-isf.spec.ts` extended (valid `hysteresisSignal` parse, unknown-
  `SIGNAL` rejection with the full valid list in the message, missing-`SIGNAL` rejection,
  `HYSTERESIS_SCRIPT` rejection, empty-`HYSTERESIS_SCRIPT` NOT rejected), `tests/unit/isf-targets.spec.ts`
  extended (target generation for both a unipolar and the bipolar case, uniform round-trip) — a
  separate small fixture, not the shared one, so the existing suite's exact-target-count
  assertion stays untouched. 11 new tests; full suite now 292 (was 282).
- **`docs/isf-shaders.md`**: two new sections — `hysteresisSignal`'s exact JSON shape and the
  real signal-name list's location, and `HYSTERESIS_SCRIPT`'s reserved-but-not-yet-functional
  status, framed honestly as "planned," not "coming soon."
- **Explicitly not done, per the plan's own stated scope**: no demo/test shaders, no editor UI
  changes, no browser verification (Phase 2); no redesign of Julia's actual signal set (Phase 3);
  no state-script execution engine, no `ScreenOutput.update()` signature change, no `IsfScene.ts`
  change (Phase 4) — `HYSTERESIS_SCRIPT` is rejected, not run, on purpose. Zero change to
  production behavior — `src/index.ts`/`render-worker.ts`'s default path never loads a shader at
  all, same posture every prior ISF slice shipped with.
- **Verified**: `npm run typecheck` (all 4 tsconfigs, including catching two exhaustive-switch
  compile errors in `isf-targets.ts`/`translate-isf-glsl.ts` that needed a `hysteresisSignal` case
  added — `tsc` itself caught both, not manual review), `npm test` (292, up from 282), `npm run
  build`, `npm run build:lib` all green. No browser verification needed or attempted — this slice
  never touches GL/render-path files at all.

## Real-ecosystem-shader verification of `hysteresisSignal` (same session, immediate follow-up)

User pointed at a real `.fs` file already sitting in `~/Downloads` (`InnerDimensionalMatrix.fs`,
by mojovideotech, CC BY-NC-SA 3.0, based on Martijn Steinrucken's "The Universe Within") and asked
to use it — this is genuinely valuable: every existing ISF test fixture in this repo (parse-isf/
isf-targets/translate-isf-glsl specs) is self-authored, so this closes a real, previously-flagged
gap (`docs/isf-shaders.md`/AGENTS.md's own standing note: *"test against a handful of real
downloaded `.fs` files from the ISF ecosystem before trusting this beyond the fixture shapes
here"* — never actually done until now).

- **The unmodified real shader, run through the real importer** (a throwaway script, deleted
  after use — not committed): `parseIsf()` succeeds on it (10 real inputs, all `float`/`bool`,
  real min/max/default values with irregular tab-indented JSON formatting — a real-world
  formatting quirk no self-authored fixture had). `translateIsfFragmentShader()` produces
  structurally sound GLSL ES 300: `#version 300 es` correctly first, no `gl_FragColor`/
  `texture2D` survive, and — genuinely new territory versus the existing test suite — the real
  shader's `#ifdef GL_ES`/`#define S(a,b,t) ...` preprocessor macros, nested nine-sample nested
  loops, and a `for(float i=...)` float-typed loop counter all pass through the purely textual
  translation untouched and correctly. (No GL context in this sandbox — this confirms the
  translation is textually sound, not that it compiles on a real GPU; that's still a real-browser
  check, same standing caveat as everything else visual in this file.)
- **The actual `hysteresisSignal` proof**: made a local, uncommitted, attribution-preserving
  derivative (`InnerDimensionalMatrix.hysteresis.fs`, kept in this session's job-scratch
  directory only — deliberately not added to the repo given the shader's non-commercial license,
  same judgment call as not baking third-party ISF content into committed test fixtures) adding
  one real input — `{ "NAME": "drive", "TYPE": "hysteresisSignal", "SIGNAL": "energy" }` — wired
  into the shader's own output (`col *= 1.0 + drive * 1.5`, brightening the whole field on top of
  its existing procedural pulsing). Then ran the **entire real pipeline** end to end, no
  synthetic data anywhere: the real Instant Crush sidecar from this session's earlier real-audio
  verification → `StructureSource.synthesize()` → a real `Conductor` → a real one-node
  `PatchGraphEvaluator` graph (`signal:energy → target:isf.drive`, the exact wiring a user would
  make in the editor) → `resolvedTargetsToIsfUniforms()`. Sampled at 6 real timestamps across the
  track (5s/60s/120s/180s/240s/300s): the shader's `drive` uniform tracked `bus.energy` exactly
  at every point (0.5723, 0.5550, 0.5767, 0.5747, 0.5738, 0.5508) — the full chain from real
  analyzed audio to a real downloaded shader's own declared uniform genuinely works.
- **Not done**: no browser click-through (loading either shader through the patchbay editor,
  confirming actual GL compilation and visible reactivity) — no browser access this session,
  same standing caveat. The derivative `.fs` file lives only in this session's scratch directory,
  not the repo — if this augmented demo is wanted as a committed fixture later, its license needs
  a real decision first (§3.8's open licensing question), not an assumption.
- **Verified**: the two throwaway verification scripts were deleted after use; `git status`
  confirmed a clean tree (nothing added to the repo by this pass) before and after.
