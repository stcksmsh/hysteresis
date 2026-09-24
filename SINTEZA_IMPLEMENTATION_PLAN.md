# СИНТЕЗА — implementation plan (Rust rewrite)

Repo: `hysteresis`
Companions: `SINTEZA_OFFLINE_SSM.md` (offline analysis), `SINTEZA_CHOREOGRAPHY.md` (physical
output, moves, formations, compiler), `AGENTS.md` (the existing TypeScript system — now
**reference implementation only**).

**This plan supersedes the previous browser-targeted implementation plan entirely.**

---

## 0. The decisions this plan encodes

Settled in design discussion; do not relitigate without new information.

1. **Native Rust, including the renderer.** The browser version is scaffolding. The reason is
   primarily coherence — a gallery installation whose brain is a browser tab sits wrong against
   the project's machine-native aesthetic — with real secondary gains in timing determinism,
   live-analysis quality, and direct hardware access. (Note honestly: GPU rendering itself was
   never the bottleneck; the wins are CPU-side scheduling, I/O, and coherence.)
2. **The browser version is dropped once Rust surpasses it.** Until then it is *frozen reference
   material*: keep it running, don't maintain it, don't backport, don't half-migrate. Its value
   is behavioural diffing ("does the Rust memory field look like the browser one"). Delete in one
   commit when superseded. The live site becomes a promo video; no embed path is preserved.
3. **The app always owns audio output.** All audio — file playback or pass-through of external
   input — exits through the app. Therefore the app always has sample-accurate playback position
   and owns the master clock. There is no "infer our position in the track" problem, ever.
4. **Three modes, distinguished by knowledge of the future, not by position tracking:**
   - *Known track* (sidecar exists) → compiled score, full anticipation.
   - *Unknown audio* (passing through) → live-reactive; position is still exact, but nothing about
     the future is known.
   - *No audio* → ambient/script-driven.
   Note this is strictly better than a mic-listening design: analysis sees clean pre-output
   samples, not a room mic hearing the installation's own output.
5. **Scripting is Lua (`mlua`)** — not WASM, not native plugins. WASM existed to decouple `.hyst`
   from JS across two hosts; with exactly one host that benefit is gone, leaving its costs (compile
   step, binary artifacts inside a git-tracked working directory, worse debugging). Lua keeps
   scripts as readable, diffable, editable text, gives real sandboxing and instruction limits, and
   needs no toolchain. If a script ever profiles hot, that one moves into Rust.
6. **Project format**: working format is a plain directory (git-friendly, diffable); `.hystproj`
   is a zip of that directory for export/sharing, **byte-faithful** — export must not transform
   content. The loader accepts both.
7. **`.hyst` stays a shader-asset format** (ISF-superset: GLSL + JSON header). The project
   directory is the container above it. Distinct things, distinct extensions.
8. **Deliberately dropped, not ported**: protocols beyond what an installation actually needs, the
   patchbay editor UI, ILDA/laser, npm packaging / `build:lib` / public embed API, and
   browser-shaped hardening (context-loss recovery, adaptive quality stepping — these get *deleted*,
   not translated). Most were scope creep; this is the moment to shed them.
9. **CI builds binaries.** GitHub Actions matrix build on tag → Linux/macOS/Windows artifacts.
   `wgpu` (Vulkan/Metal/DX12 from one codebase) makes this tractable.

---

## 1. Rules every agent follows

1. **Read the spec sections your workstream names before writing code.** This plan is a
   work-split, not a design document.
2. **The Rust tree is new. Never edit the TypeScript tree** — it is frozen reference. Read it
   freely, port from it, don't touch it.
3. **`cargo check` / `cargo test` / `cargo clippy` green at every commit.**
4. **Stay inside your workstream's crate boundary.** Needing to cross it means stopping and
   flagging, not editing across the seam. That boundary is what makes parallel work safe.
5. **Additive schema changes only** for anything the offline pipeline emits — a published sidecar
   must keep validating.
6. **Verify against real audio**, not only synthetic fixtures, wherever a spec says so. The
   existing project's headless real-audio verification discipline carries over.
7. **Build nothing from the deferred lists** (§0.8, §6, plus each spec's own). Flag instead.

---

## 2. Workspace layout

A Cargo workspace. Crate boundaries *are* the parallelization seams.

```
crates/
  hyst-core        types, signal bus, project loading, clock        (foundation)
  hyst-audio       playback, pass-through, live analysis, clock
  hyst-render      wgpu renderer, .hyst parsing, passes
  hyst-script      Lua runtime, script contract, sandboxing
  hyst-choreo      moves, curves, Effort, formations
  hyst-compile     offline choreography compiler → cue list
  hyst-output      VizOutput implementations (screen, choreography, field)
  hyst-hw          servo/serial/GPIO drivers + the safety layer
  hyst-previz      2D simulation viewer
  hyst-cli         binary, wiring, modes
tools/             existing Node/Python offline pipeline (unchanged, still used)
```

---

## 3. Dependency graph

```
Wave 0 (blocking)
┌─────────────────────────────────────────────────┐
│ R0. hyst-core   types, signal bus, project load │
│ R1. hyst-audio  playback + clock ownership      │ ← answers the timing unknowns
└──────────────────┬──────────────────────────────┘
                   │
Wave 1 (parallel once R0/R1 land)
   ┌──────────┬──────────┬──────────┬──────────┐
   ▼          ▼          ▼          ▼          ▼
 R2 render  R3 script  R4 choreo  R5 field   [A offline*]
   │          │          │          │
Wave 2 ▼──────┴──┐       │          │
 R6 autopilot    │   R7 compiler    │
                 │       │          │
Wave 3           ▼       ▼          ▼
              R8 score playback   R9 previz
                         │
Wave 4                   ▼
                  R10 servo spike (hardware)

* A is fully independent of all Rust work — starts NOW, in parallel.
```

**Critical path**: R0 → R1 → R2 → R6. Everything else parallelizes around it.

**On sequencing the spike**: the hardware spike (R10) is deliberately late, but note that R1 is
itself spike-work — the audio/clock/latency unknowns surface the moment a Rust process plays
audio and runs a clock, before any hardware exists. Get R1 right and R10 only has to answer
genuinely hardware-shaped questions.

---

## 4. Workstreams

### A. Offline analysis pipeline — **START NOW, PARALLEL TO ALL RUST WORK**
**Spec:** `SINTEZA_OFFLINE_SSM.md` (read §0b first — it overrides the original plan).
**Language:** existing Node/Python in `tools/`. **Completely unaffected by the Rust decision.**
**Do:** `allin1` subprocess wrapper (beats, downbeats, tempo, boundaries, functional labels)
alongside the existing Demucs shell-out; tempo sanity-check + hand-correction path (models emit
confident-but-wrong activations; the standard 55 BPM floor forces double-tempo on ~21% of slow
tracks); beat-synchronous feature vectors over `allin1`'s grid; full SSM; **the repetition map**;
schema-4 additive fields; `StructureSource`-equivalent exposure.
Skip §1.3/§1.4 (checkerboard novelty/peak-picking) — fallback only now.
**Done when:** a real track yields a schema-4 sidecar with a correct repetition map (verify an
obviously-repeated chorus); older sidecar fixtures still validate untouched.

### R0. `hyst-core` — foundation
**Blocks everything.**
**Do:** signal-bus types (port the vocabulary and **timescale tags** from the TS
`SignalBus`/`SIGNAL_TAGS` — the tags are load-bearing for physical-output safety); sidecar
deserialization (schema 2–4); project-directory loader + `.hystproj` zip loader (§0.6); the
`VizOutput` trait; error/result conventions.
**Done when:** a project directory and a schema-4 sidecar both load and round-trip in tests.

### R1. `hyst-audio` — playback, clock, live analysis
**Blocks R2+. Answers the timing questions that cannot be settled on paper.**
**Do:**
- Audio output via `cpal`. **The app owns output** (§0.3) — file playback and pass-through both
  exit through the app.
- **Master clock** derived from audio playback position, sample-accurate.
- **Deliberate output-latency compensation**: because the app owns output, audio can be delayed a
  few ms to compensate servo travel time. This is a second, complementary lever on
  `SINTEZA_CHOREOGRAPHY.md` §6's kinematics problem, and only possible with this design — make it
  expressible from day one.
- Live feature extraction ported from the TS worklet (FFT, bands, centroid, flatness, flux,
  chroma, onset density, fullness) + the beat PLL. Port the working PLL first; native removes the
  model-size ceiling so better live beat tracking is possible later, but that is not this task.
- **Optional, nearly free, worth doing**: cache a sidecar for unknown audio after first
  playthrough, so a second play of the same track can be fully compiled.
**Done when:** a track plays with sample-accurate position, live bus signals populate, and
configurable output latency is demonstrably applied.

### R2. `hyst-render` — wgpu renderer + `.hyst`
**Blocked by:** R0, R1.
**Do:** `wgpu` setup; port the passes (memory field, persistence, bloom, composite, and the beam's
instanced-quad line rasterization); `.hyst` parsing (JSON header + GLSL) and multi-pass
(`fullscreen`, `lineTrace`, `scriptTexture`); the Julia substrate itself.
**Note:** WebGL2's ceiling is gone — compute shaders and storage buffers are available, and the
memory field is the obvious beneficiary. **Port faithfully first, optimize second**, so the
behavioural diff against the frozen browser build stays meaningful.
**Do NOT port:** context-loss recovery, adaptive quality/resolution stepping.
**Done when:** Julia substrate + memory field + beam render, visually diffable against the frozen
browser build.

### R3. `hyst-script` — Lua runtime
**Blocked by:** R0. Parallel with R2.
**Do:** `mlua` integration; the **script contract** — what a script reads (bus signals, dt, time,
playback position, idle flag), what it writes (named typed state: scalars, plus buffers for
`scriptTexture`), when it runs (once per frame, declared order, **no script-to-script calls**);
sandboxing + instruction-count limits; fault isolation with restart-and-continue-on-last-known-
values (port the *behaviour* of the existing nested-Worker host, not its mechanism); a **shared
named state namespace** that scripts write and any output reads.
**Design the contract against the real Julia autopilot (R6), not in the abstract** — the existing
engine did exactly this and was right to.
**Why the shared-namespace shape matters:** it lets one "ambient conductor" script coordinate the
shader *and* the arms without outputs ever calling each other, preserving the DAG and the output
isolation that makes adding a new output free.
**Done when:** a Lua script runs per-frame and writes named state; a deliberately hanging or
throwing script is contained without taking the process down.

### R4. `hyst-choreo` — moves, curves, Effort, formations
**Blocked by:** R0 only. Fully parallel with R2/R3.
**Spec:** `SINTEZA_CHOREOGRAPHY.md` §2 (moves, curve corpus, Effort), §3 (formations).
**Do:** the curve corpus as pure `t∈[0,1]→[0,1]` functions in a **discriminated-union**
representation (family + flavor + optional shape param), never a flat 30-value enum; the move type
(named DOF channel roles, local normalized time + outer duration, entry/exit pose, future-arrival
anchor, hit/groove/windup/hold tag, **descriptive not emotive** applicability tags, intensity
scalar, provenance); the **Effort vector** (Time = velocity-profile local-extrema count, Weight =
path displacement bias, Space = heading variation) as a **modifier over any move** — **Flow is
excluded deliberately**, do not add it; the procedural move generator (generation is the primary
population path, hand-authoring is the override); `Topology`; formation modes (unison, canon/wave,
call-and-response, breathe/converge-diverge, affine, mirror as a layerable transform,
**scatter as first-class**) as pure functions; salience-anchored vs. spatial ordering as **one
parameter**, not two formation types.
**No sequencing logic here** — that is R7's job.
**Done when:** formations produce correct per-agent instructions for N=1/6/12 from identical
inputs, and **N=1 is a no-op transform rather than a special case**.

### R5. `hyst-output` — output plumbing + `FieldOutput`
**Blocked by:** R0.
**Spec:** `SINTEZA_CHOREOGRAPHY.md` §0 (two-paradigm table), §5.3, §7.
**Do:** shared `VizOutput` plumbing; **`FieldOutput`** — `ArrayTopology` (element → normalized
(u,v) + channel binding), field sampling from a rendered source (**a dense array is a
low-resolution physical render target, not a new authoring surface**), per-element mapping function
as a parameter (brightness→tilt; value→orientation/contour), ~15 Hz refresh with **diff-only
transmission** (send changed elements only), element-level graceful degradation.
**Done when:** a simulated array renders a field at N=100+ and injected element failures degrade to
single wrong tiles, never stalled regions or a stalled bus.

### R6. Julia autopilot port
**Blocked by:** R2, R3.
**Do:** port the 1000+-line stateful autopilot (vortex search, perturbation reference orbits,
spring-damped c-drift, zoom dives, blackout reset) from TS to **Lua**. JS→Lua is a far smaller
translation than JS→WASM would have been — both dynamically typed, similar structure. This is the
first real script and the concrete driver for R3's contract.
**Done when:** ambient/no-audio mode is visually equivalent to the frozen browser build.

### R7. `hyst-compile` — the choreography compiler
**Blocked by:** A (schema-4 sidecar), R4.
**Spec:** `SINTEZA_CHOREOGRAPHY.md` §4, §5.2, §6.
**Do:** the offline compiler producing a **cue list** (show-control vocabulary — cue / cueList /
trigger / go); nested decision cadence (section-level character → phrase-level move rotation →
hit-level windups anchored to known future timestamps → fully compiled role/salience assignment);
repetition-map reuse-vs-vary as a compiler parameter; **§6 kinematics back-calculation** (per-DOF
velocity/accel/jerk profile; back-calculate start times so arrivals land on time — complementary
to R1's output-latency lever).
**Mandatory acceptance test (§4.2):** disable every hit/windup special case — **the groove must
still look alive.** If scatter mode goes inert between events, this workstream has failed, exactly
as the pre-fix screen renderer once did.
**Done when:** a real track compiles to a full cue list and the acceptance test passes.

### R8. Score playback output
**Blocked by:** R7.
**Do:** `ChoreographyOutput` — sample the compiled cue list at the current playback position.
Because everything is resolved offline, there is **no runtime formation evaluation and no
patch-graph involvement** on this path.
**Done when:** a score plays back deterministically against R1's clock.

### R9. `hyst-previz` — **REQUIRED before hardware**
**Blocked by:** R4 types (can render synthetic scores before R7 exists).
**Spec:** `SINTEZA_CHOREOGRAPHY.md` §9.
**Do:** a 2D top-down animation of a topology executing a score, no hardware. Must cover **both**
paradigms: agent poses (choreography) and a rendered element grid (field).
**Done when:** obviously-wrong motion is visible on screen. This is the gate enforcing "never send
an unpreviewed score to hardware" — previsualization is standard practice in entertainment
automation, not optional polish.

### R10. Servo spike — the hardware unknowns
**Blocked by:** R1, R7, R8, R9.
**Do:** `hyst-hw` — serial/GPIO servo driver plus **the unconditional physical-safety layer**
(rate limiting, thermal duty-cycle, graceful single-axis failure) that **all** paths pass through,
compiled or live. Then: one track, one servo, moving in time to a compiled cue.
**This answers what paper cannot**: calibration (per-unit zero/range, mechanical slop, persistence),
real kinematic profiles, and whether the latency compensation actually lands movements on the beat.
**Done when:** a servo visibly lands a movement on a drop — verified by eye *and* by measurement.

---

## 5. Known gaps this plan does not close

Flagged honestly; several need hardware or decisions rather than code.

- **Calibration** (per-servo zero/range, mechanical slop, persistence) — designed during R10.
- **Power budget** — N servos + LEDs + projector. Servo stall current is the classic
  brown-out-on-opening-night failure. Needed before any multi-servo build.
- **Projection mapping onto moving surfaces** — projector calibration, keystone, whether the
  renderer needs to know arm positions. Currently an assumption, not a decision.
- **System-level watchdog** — process crash at 2am, auto-restart, resume-mid-score vs.
  restart-track, what a visitor sees during recovery. Was legitimately "host concern, out of scope"
  when the host was a webpage; **going native makes it squarely in scope.**
- **Hardware-in-the-loop testing** — no CI story for the choreography/hardware path.
- **Physical safety around people** — an arm at head height in a public gallery has liability
  implications distinct from thermal/mechanical safety.
- **Content plan** — which tracks get compiled for the first show.
- **Move-library scoping** (global vs. per-project) — the project container arguably answers this
  now; worth closing explicitly.
- **Screen↔servo cross-link** (`SINTEZA_CHOREOGRAPHY.md` §8) — correctly deferred until both exist
  and can be watched together.

---

## 6. Out of scope for every workstream

ILDA/laser, the protocol suite beyond installation needs, patchbay editor UI, npm/embed packaging,
nested sub-formations, Flow Effort, live stem separation, any attempt to make a sidecar-only
capability run live, and any edit to the frozen TypeScript tree.
