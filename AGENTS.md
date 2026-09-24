# AGENTS.md — Hysteresis (native Rust rewrite)

## Active user priority — 2026-09-24 dance handoff

Read `docs/DANCE_HANDOFF.md` for current task, assets and acceptance. User confirms
audio-synchronized 16-beat study does not meet goal: motion must respond to song
content. User authorizes coordinator cross-crate integration for this vertical
slice; assign workers bounded file ownership. Frozen `src/` and `tools/` remain
read-only. Explicitly delegate coding to cheaper agents; Astra medium coordinates.
Preserve substantial pre-existing uncommitted/untracked native rewrite.


The single AI-facing entry point for this repo, **for the Rust rewrite currently in progress.**
The browser/TypeScript system this rewrite supersedes is archived verbatim at
`docs/LEGACY_TS.md` — frozen reference material, never edited, see its own header.

Read in this order: §1 (what this is) → §2 (source of truth) → §3 (rules) → §4 (resume /
operating mode) → §5 (session history — trust this over any summary above when they conflict).

---

## 1. What this is

A native Rust rewrite of the СИНТЕЗА visualizer / Hysteresis patch instrument — a music
visualizer that becomes the brain of a physical installation (screen + DMX/LED lighting +
servo-driven choreography + dense physical arrays), replacing the browser/TS implementation
entirely. See `SINTEZA_IMPLEMENTATION_PLAN.md` §0 for the full rationale (native for coherence
with the installation's machine-native aesthetic, not because the browser was a performance
bottleneck) and its non-negotiable decisions (Rust incl. renderer, Lua scripting via `mlua`, a
plain-directory + `.hystproj`-zip project format, CI-built binaries).

**Naming**: same project as before — "Hysteresis" is both the technical principle (a system
whose output depends on its whole history) and the working name of the whole patch-instrument
project. See `docs/LEGACY_TS.md` §1 for the full thesis if it's ever needed; not restated here.

---

## 2. Source of truth

- **`SINTEZA_IMPLEMENTATION_PLAN.md` is the plan of record.** It is a work-split (crate
  boundaries, dependency waves, per-workstream done-when criteria), not a design document —
  read the spec section your workstream names before writing code (its own §1.1).
- **`SINTEZA_OFFLINE_SSM.md`** (workstream A) and **`SINTEZA_CHOREOGRAPHY.md`** (workstreams
  R4/R5/R7/R9) are older companion specs, **directional background, not verified current design**
  — they predate this session's confirmation that the implementation plan is what's authoritative.
  Treat their specifics (e.g. `allin1` as the chosen MIR tool, the exact Effort/curve taxonomy) as
  plausible but unconfirmed; flag anything load-bearing before building on it rather than assuming
  it's settled.
- **`docs/LEGACY_TS.md`** is the frozen TS system — read freely for porting reference (signal bus
  shape, sidecar schema, detector logic), never edited.
- `docs/*.md` (`isf-shaders.md`, `dmx-out.md`, `midi.md`, `osc.md`, `ilda.md`,
  `patchbay-editor.md`) describe TS-era, browser-specific surfaces (npm embed API, the patchbay
  editor UI) that the implementation plan §0.8/§6 explicitly drops, not ports. Reference only for
  protocol/format detail (e.g. the real ILDA/Art-Net specifics) that outlives the rewrite.

---

## 3. Rules every agent follows

Verbatim from `SINTEZA_IMPLEMENTATION_PLAN.md` §1 — repeated here so they're not missed:

1. Read the spec sections your workstream names before writing code.
2. The Rust tree is new. **Never edit the TypeScript tree** (`src/`, `tools/` — the latter is the
   patchbay-editor/render-video dev tools, genuinely frozen too) — it is frozen reference. Read
   freely, port from it, don't touch it. **Correction (verified 2026-09-05): the plan's "tools/" in
   its workstream-A description is a misnomer** — the real, still-live Node/Python offline pipeline
   is `scripts/` (`analyze.ts`/`structure.ts`/`demucs.ts`/`wav.ts`), not `tools/`. `scripts/` is the
   one part of the TS-looking tree workstream A may edit; everything under `src/` (including
   `src/shared/sidecar.ts`) stays frozen — a schema-4 field extension belongs in a new type defined
   inside `scripts/` itself (extending, not modifying, the frozen `Sidecar` interface), the same way
   `hyst-core`'s Rust `Sidecar` already carries schema-4 as additive/optional fields.
3. `cargo check` / `cargo test` / `cargo clippy` green at every commit, workspace-wide.
4. Stay inside your workstream's crate boundary (`crates/hyst-*`, see the plan's §2 layout).
   Needing to cross it means stopping and flagging, not editing across the seam.
5. Additive schema changes only for anything the offline pipeline emits (sidecar, and later the
   Choreography Score) — a published sidecar must keep validating.
6. Verify against real audio, not only synthetic fixtures, wherever a spec says so.
7. Build nothing from the deferred lists (plan §0.8, §6, plus each spec's own "explicitly
   deferred" section). Flag instead of guessing it's fine to build early.

---

## 4. Resume / operating mode

**Where things stand** (see §5 for the dated detail): **R0/R1/R2/R3/R4/R5 and workstream A have all
landed** (R2/R3/R4/R5/A via parallel subagents in one session, R0/R1 the session before). Workspace:
199 tests green (`hyst-core` 8, `hyst-audio` 40, `hyst-render` 44, `hyst-script` 22, `hyst-choreo`
37, `hyst-output` 18 — plus 30 in `scripts/` TS via vitest), `cargo clippy -D warnings` clean
workspace-wide, TS `npm run typecheck`/`vitest` still green (untouched). A real audio-driven render
(Julia + memory field + bloom/composite + beam, 512×512/24fps/45s, driven by `hyst-audio` reading a
real WAV) was produced and sent to the user — R2's done-when is met (no browser exists to diff
against; flagged, not faked).

**Critical path now**: **Phase 2** — R6 (Julia autopilot → Lua, needs R2+R3, both done), R7
(choreography compiler, needs workstream A + R4, both done — A's beat grid is the causal fallback,
not allin1, see below), R9 (previz, only needs R4's types per the plan's own dependency note — pull
it forward into this phase rather than waiting for R7/R8's wave).

**allin1 (workstream A's preferred beat/boundary source) is NOT wired in — deliberately, not
forgotten.** Two real attempts: first hit a slow-pip-resolver hang on PyTorch's CUDA matrix; a
retry fixed that (pin `torch` CPU wheel first) and got further, but hit a second, different, real
blocker — `natten` (an allin1 model dependency) has no prebuilt wheel for this Python/torch ABI and
needs a from-source C++/CUDA-extension build (a real hour+ compile, not a resolver issue). User
chose to keep the fallback rather than spend that budget. The causal-beat-grid fallback (in
`scripts/ssm.ts`/`repetition.ts`) is real, tested against 3 real tracks, and was deliberately
designed beat-grid-source-agnostic — swapping in allin1 later (if `natten` ever gets a wheel, or
someone's willing to eat the compile) touches nothing in the SSM/repetition-map math itself.

**Real-time-safety debt, flagged not fixed**: `hyst-audio`'s cpal callback (`playback.rs`)
allocates per callback and runs the full feature extractor synchronously on the audio thread —
fine for this pass, but a glitch-free installation build needs this off the audio thread before a
real show. No resampling — `Playback::new` requires the source WAV's sample rate to exactly match
the output device's. `hyst-render`: no pipeline/bind-group caching (rebuilds every pass call — fine
offline, not real-time), no reference-orbit perturbation (deep Julia zoom will lose precision,
untested), bloom is single-level not mip-cascaded. `hyst-script`: instruction budget
(2,000,000/frame) is untuned, never profiled against a real script; a fault wipes a script's
persistent state (same tradeoff the TS original made, flagged for R6 to reconsider if it bites).

**Operating mode** (unchanged in spirit from the TS era, `docs/LEGACY_TS.md` §5):
- Gap-analysis first every time you resume — diff the plan's workstream table against what's
  actually in `crates/`, don't assume where the last session left off.
- One coherent workstream slice per session where possible; a workstream's own "done when" is the
  bar, not "some progress."
- Append a dated/titled §5 entry per session — what changed, what's verified vs. not (cargo
  test/clippy is not the same as a real-audio/real-hardware check), what's explicitly deferred.
- Respect plan §0.8/§6's non-goals as hard scope boundaries.
- If a decision genuinely needs the user's input (an old spec's specifics, anything expensive to
  reverse, a crate-boundary crossing), ask; don't guess and proceed.

---

## 5. Session history (append-only, newest last)

### R0 foundation — Cargo workspace + hyst-core (2026-09-05)

First Rust session. Scaffolded the workspace per plan §2 (`crates/hyst-{core,audio,render,script,
choreo,compile,output,hw,previz}` + `hyst-cli`'s `hyst` binary) — every crate but `hyst-core` is
an intentional one-line stub so the workspace checks/clippies/tests clean from commit one, per §3
rule 3, without pretending unstarted workstreams have content.

`hyst-core` (`crates/hyst-core/src/`):
- `signal.rs` — `TimescaleTag`, `SignalBus` (every field from the TS `SignalBus`, `snake_case`d),
  `signal_tag()` (a match, not a `HashMap`, replacing the TS `SIGNAL_TAGS` const — same coverage,
  unit-tested that every routable field has a tag and `scope`/`chroma`/`idle` don't), `TargetDecl`,
  `ResolvedTargetValue`/`ResolvedTargets`, the `VizOutput` trait (`update(&mut self, dt, &
  ResolvedTargets)`, `dispose`).
- `sidecar.rs` — `Sidecar`/`SidecarSection`/`SidecarEvent`/`SidecarOnset`/`SidecarBandEnvelope`/
  `SidecarStemPresence` ported field-for-field from `src/shared/sidecar.ts` (schema 2/3, real,
  verified against the TS file read in full). Schema-4 additions (`SidecarRepeat`,
  `noveltyLocalEnvelope`/`noveltySectionEnvelope`, `SidecarSection.boundaryConfidence`) ported from
  `SINTEZA_OFFLINE_SSM.md` §2 — **explicitly flagged in the module doc comment as directional**,
  since that spec is older and nothing in `tools/` emits schema 4 yet. All schema-3/4 fields are
  `Option`, matching the additive-only precedent (rule 5). `SidecarSchemaVersion` round-trips
  through `u8` via `TryFrom`/`Into` so an unknown version (e.g. `99`) is a real parse error, not a
  silent default.
- `project.rs` — **new, no TS precedent** (the browser package had no project container at all —
  a track was just a URL). Designed minimal: `project.json` manifest (`name`, `format_version`,
  optional `audio`/`sidecar` relative paths) at a directory's root. `Project::load_dir` reads and
  validates it (rejects an unknown/future `format_version`, does *not* eagerly check that
  `audio`/`sidecar` paths exist — a caller opening one gets a real io error naming the actual
  missing path). `Project::export_zip` walks the directory (`walkdir`) and stores every file's raw
  bytes under its relative path — no re-serialization, no line-ending normalization, so the
  `.hystproj` is byte-faithful per plan §0.6. `Project::load_hystproj` extracts into a caller-given
  directory (via the `zip` crate, `enclosed_name()` guards path traversal) then delegates to
  `load_dir`. Round-trip test (`hystproj_export_and_reload_round_trips_byte_faithfully`) confirms
  a `.wav`-like binary file and a `.hyst`-like text file both survive export→reload with identical
  bytes.
- `error.rs` — `HystError` (`thiserror`), `Io`/`Json` variants carry the offending path so a
  failure names a real file, not just "something went wrong."

**Verified**: `cargo check --workspace`, `cargo test --workspace` (8 tests, all in `hyst-core` —
every other crate is a stub with none yet), `cargo clippy --workspace --all-targets -- -D
warnings`, all clean. `npm run typecheck` on the existing TS tree re-run and confirmed still green
(nothing there was touched). Added `/target/` to `.gitignore`.

**Not done / explicitly deferred to R1+**: no audio, no rendering, no script runtime — R0 is
foundation types only, as scoped. The project manifest shape (`project.json`) is a first cut, not
finalized — later workstreams (`.hyst` assets, Lua scripts, Choreography Scores) will likely add
fields to it; keep additions additive per the same schema precedent, don't redesign it from
scratch when that need arrives.

**This session also restructured AGENTS.md itself**: the full TS-era content (architecture,
target-architecture backlog, Layer 2 spec, and the entire prior session-history appendix) moved
verbatim to `docs/LEGACY_TS.md` (frozen, header added). This file was rewritten lean and
Rust-facing, per user request, now that the TS system is reference-only.

### R1 — `hyst-audio`: playback, clock, live analysis (2026-09-05, same day as R0)

Second Rust session, same day. Full R1 scope from the plan's named list landed: "FFT, bands,
centroid, flatness, flux, chroma, onset density, fullness) + the beat PLL", plus playback/clock/
latency-compensation. **Deliberately not in this pass** (not named in the plan's R1 item, flagged
rather than silently skipped): `BuildDetector`/`DropDetector`/`BreakDetector` (so `buildProgress`/
`tension`/`dropImpulse`/etc. stay at `SignalBus::default()`'s zero), per-band stereo placement/pan,
the oscilloscope `scope` beam, `harmonicNovelty`/`familiarity`/`noveltyLocal`/`noveltySection`
(need `novelty.ts`'s ring-buffer machinery, not named in R1), and any resampling (source WAV
sample rate must exactly match the output device's).

`hyst-audio` (`crates/hyst-audio/src/`):
- `clock.rs` — `AudioClock`: atomics-based, `logical_position_secs()` (sample-accurate, advanced
  by the audio callback) and `audible_position_secs()` (logical minus the configurable output
  latency, clamped ≥0) — the literal mechanism plan §4 R1 asks for ("audio can be delayed a few ms
  to compensate servo travel time... make it expressible from day one").
- `delay_line.rs` — `DelayLine`: a fixed-capacity interleaved ring buffer. The callback writes
  undelayed samples in for the clock/analysis to see immediately, while what actually reaches the
  device is read `delay_frames` behind — silence until enough frames have ever been written, not a
  wraparound read of stale data. Pure logic, no device needed, unit-tested directly (zero-delay
  passthrough, multi-call persistence, stereo-channel independence, over-capacity clamping).
- `dsp/` — `fft.rs` (`WindowedFft`, Hann window ported bit-for-bit from `fft.ts`, `realfft` standing
  in for `fft.js`'s `realTransform` — its `size/2+1` bin convention already matches exactly, no
  reinterpretation needed), `bands.rs`, `envelope.rs` (`EnvelopeFollower`/`AdaptiveNormalizer`),
  `spectral.rs` (centroid/flatness), `onset.rs` (`SpectralFlux`), `chroma.rs`, `activity.rs`
  (`FullnessTracker`/`OnsetDensityTracker`) — all ported faithfully from
  `src/audio/worklet/{fft,bands,envelope,spectral,onset,chroma,brain/activity}.ts`, each with its
  own synthetic-signal unit tests (pure tone → correct FFT bin, A440 → pitch class 9, flat noise →
  high spectral flatness, etc.) since none of these need a real device to verify their math.
- `beat.rs` — `BeatTracker`/`BarTracker`, ported line-for-line from
  `src/audio/worklet/brain/beat-tracker.ts` ("port the working PLL first" — plan §4 R1). The exact
  three tests from `tests/unit/beat-tracker.spec.ts` (120 BPM click-train lock-on, 90 BPM
  lock-on, beat-phase free-running smoothly through a silent gap) are mirrored here and pass.
- `features.rs` — `FeatureExtractor`: glues the above into a per-hop `analyze()` matching
  `feature-worklet.ts`'s ring-buffer-accumulate-then-hop structure exactly (2048-sample FFT window,
  512-sample hop, the same "ring must wrap once before any hop fires" gate — verified by a test
  that deliberately checks 1, not 0 or 4, hops fire crossing that exact boundary). Populates a
  `hyst_core::SignalBus` (which gained a `#[derive(Default)]` this session, a small additive
  follow-up to R0, so a partial producer has a sane zeroed starting point).
- `wav_source.rs` — `WavSource::load` via `hound` (int and float WAV, no TS precedent — the browser
  package never decoded audio itself, the host's `<audio>`/`AudioContext` did).
- `playback.rs` — `Playback::new` opens the real default output device via `cpal`, requires the
  source's sample rate to match it exactly (mismatch is a named, clear error — resampling flagged
  as follow-up, not silently wrong), maps mono/stereo/other channel counts sensibly, and wires
  `AudioClock` + `DelayLine` + `FeatureExtractor` together in the output callback. Exposes
  `latest_bus()` and `set_output_latency_ms()`. **Flagged, not fixed**: the callback allocates and
  runs the full extractor synchronously on the audio thread — real-time-safety hardening is
  explicitly deferred, not attempted this pass.
- `examples/play.rs` — a real, kept manual-verification tool (`cargo run -p hyst-audio --example
  play -- file.wav [latency_ms]`), deliberately outside `cargo test`/CI since it opens a real audio
  device and produces real sound.

**Verified against real hardware, not just synthetic fixtures** (asked the user first, given this
session runs as a background job and playing audio is an audible, real-world action) — this is
the first workstream in the Rust rewrite to clear that bar. Generated a short (4s), moderate-volume,
faded-envelope 440Hz beep track at 120 BPM matching the real default output device's config
(44100 Hz, stereo, f32, queried live via `cpal`), played it through `examples/play.rs` with 30ms
output latency configured, and confirmed by reading the printed log (not by ear alone): tempo
locked to 120 BPM matching the true click rate; `sub`/`low` band energy tracked the beeps and
dropped to ~0 after the track ended; `audible_position_secs` stayed consistently ~30ms behind
`logical_position_secs` throughout — the output-latency compensation lever works end-to-end, not
just in the `DelayLine`'s own unit tests. All three of R1's stated done-when criteria (sample-
accurate position, live bus signals populate, configurable output latency demonstrably applied)
are now real, not just unit-tested in isolation. The two throwaway diagnostic examples used to get
here (`device_info.rs`, `gen_test_tone.rs`) were deleted afterward — not real deliverables.

**Verified (automated)**: `cargo check`/`test`/`clippy -D warnings` clean workspace-wide (48 tests:
8 `hyst-core` + 40 `hyst-audio`). `npm run typecheck` reconfirmed green (TS tree untouched, per
rule 2). No cpal device is opened by the automated test suite — that stays a deliberate, human-
gated action (this session's real-hardware run was explicitly confirmed with the user first, per
the project's action-care guidelines around audible/real-world side effects).

**Not done / explicitly deferred**: no resampling; no real-time-safety hardening on the audio
callback (both flagged above); the sidecar-caching-after-first-playthrough item plan §4 R1 calls
"optional, nearly free, worth doing" was not attempted this session — genuinely optional per the
plan's own wording, not silently dropped.

### R2 (partial) — `hyst-render`: `.hyst` parsing + `wgpu` bootstrap (2026-09-05, same day as R0/R1)

Third Rust session, same day, continuing straight from R1. **This is a deliberately partial slice
of R2** — the two most independent, well-scoped "Do" items landed; the render passes and Julia
substrate (the bulk of the workstream, and R2's actual done-when: "Julia substrate + memory field
+ beam render, visually diffable against the frozen browser build") remain open, flagged below
rather than claimed done.

**`.hyst` format parser** (`crates/hyst-render/src/hyst_format/`): ported `src/isf/types.ts` +
`src/isf/parse-isf.ts` field-for-field — `IsfInput` (float/bool/long/color/point2D/
hysteresisSignal/resource/scriptOutput, each with its real fields, as a Rust enum rather than a
TS discriminated union), `IsfPass` (fullscreen/lineTrace/scriptTexture), `IsfDocument`,
`IsfParseError`. `parse_hyst()` mirrors `parseIsf()`'s exact behavior: header-comment extraction,
`HYSTERESIS_VERSION` gating (absent = plain ISF, unrecognized version = a specific rejection,
current version unlocks real multi-pass/script extensions), `PERSISTENT`/multi-pass/`IMPORTED`
rejection with the same specific messages, `hysteresisSignal`'s `SIGNAL` validated against
`hyst_core::ROUTABLE_SIGNAL_NAMES` (a small, justified R0 follow-up addition — `hyst_core::signal`
gained this exported const, alongside the existing `signal_tag()` lookup, so a second consumer
doesn't need to duplicate the name list), lineTrace/scriptTexture cross-validation against declared
inputs, and scriptOutput/scriptTexture requiring a real `HYSTERESIS_SCRIPT`. **Every one of the 33
tests in `tests/unit/parse-isf.spec.ts` was ported 1:1** (same fixtures, same rejection messages
asserted via substring match on `Display`) and **passed on the first run, no fixture adjustments
needed** — the strongest port-fidelity signal so far this rewrite.
**Deliberately not ported this session**: `translate-isf-glsl.ts` (the GLSL-body translation from
ISF's browser-flavored built-ins to valid shader source) — `IsfDocument.body` is carried through
verbatim, untranslated, unusable by any renderer as-is yet. Flagged as necessary follow-up work,
not forgotten.

**`wgpu` bootstrap** (`crates/hyst-render/src/gpu.rs`): `GpuContext` (instance/adapter/device/queue,
headless — no window/surface, matching the render-worker's own `OffscreenCanvas`-only architecture
in the TS original) and `OffscreenTarget` (a fixed-size RGBA8 render-to-texture target, a hardcoded
fullscreen-triangle vertex shader in the classic `@builtin(vertex_index)` style, a
`render_fragment_shader()`/`read_pixels()` pair). **Verified against this machine's real GPU, not
mocked or skipped**: confirmed a real Vulkan adapter/device exists (`vulkaninfo`, `/dev/dri`) before
writing any code, then wrote a test that requests a real adapter, renders an actual horizontal-
gradient WGSL fragment shader to a 64×64 texture, reads it back via the real buffer-copy/map-async
path, and asserts the readback shows a genuine left-to-right gradient (near-0 red at x=0, near-max
at x=63, monotonic in between) — not just "did it not crash." This is a real, repeatable
`cargo test` (no manual/human-gated step needed here, unlike R1's audio playback — reading pixels
back to a buffer has no audible/visible side effect on the user's machine, so no confirmation was
needed before running it). **Deliberately not built yet**: any actual render pass (memory field,
persistence, bloom, composite, beam), the Julia substrate shader, and the GLSL(ISF)-to-WGSL
translation layer that would let a real `.hyst` fragment body actually compile and run through this
pipeline — `OffscreenTarget::render_fragment_shader` only accepts hand-written WGSL today. Also not
addressed: general (non-64px-aligned) readback padding — `read_pixels` explicitly errors rather than
silently misreading if `width * 4` isn't already a multiple of 256, a real render pass will need
that padding handled, not just documented as a caller's constraint.

**Verified**: `cargo check`/`test`/`clippy -D warnings` clean workspace-wide (82 tests: 8 + 40 + 34,
`hyst-render`'s 34 includes the one real GPU-hardware test above). `npm run typecheck` reconfirmed
green. `hyst_core::signal`'s new `ROUTABLE_SIGNAL_NAMES` export is covered by the existing tag-
coverage test (updated to iterate it instead of a second hardcoded list, removing a duplication that
existed only because R0 predated this need).

**Not done / explicitly deferred to the rest of R2**: the render passes, the Julia substrate, ISF-
GLSL-to-WGSL translation, general (non-64px) texture readback, and wiring `.hyst` multi-pass into an
actual renderer that consumes it (today `parse_hyst()` produces structured data nothing downstream
reads yet). R2's own stated done-when ("Julia substrate + memory field + beam render, visually
diffable against the frozen browser build") is NOT met by this session's slice — don't read the 82
green tests as R2 being complete.

### Post-Phase-1 fix — memory-field exposure/wash-out (2026-09-05, same day)

User reported the fixed-palette render was "still smudged" after the earlier palette fix. Root
cause was two compounding issues, found by actually rendering and looking (tests didn't catch
either — see the note above about visual review being necessary here):
1. `memory_field.rs`'s `cur_gain` was a caller-supplied constant (0.25 in the demo), not derived
   from `decay` — the real spec (`memory-field-pass.ts`) computes
   `cur_gain = max(0, (1-decay)/(1-DECAY_REFERENCE))`, `DECAY_REFERENCE=0.86`, specifically so
   raising decay doesn't ALSO multiply steady-state brightness by the same factor. Fixed:
   `cur_gain` is no longer a `MemoryFieldParams` field at all — computed internally, matching spec.
   This formula normalizes steady-state gain to a **constant ~7.14x regardless of decay**, by
   design — worth remembering before "fixing" it again.
2. That normalized ~7x gain needs real exposure headroom before Reinhard tonemap, which this
   fresh (non-ported, R2's own) composite/bloom pipeline didn't have — a long-running (45s, 1000+
   frame) feedback loop compounded past Reinhard's knee into a washed-out near-white smudge, and
   the Julia palette was feeding color into the accumulator from almost the entire exterior (any
   pixel escaping in as few as 1-2 iterations still got partial color), not just real boundary
   detail — most of what was compounding.
   Fixed: `composite.rs`'s `render_composite` gained a real `exposure: f32` parameter (pre-tonemap
   scale, `1.0` default = no change, existing tests use `1.0`; the demo now uses `0.08`) —
   `renderer.rs::FrameParams` carries it through. `julia.rs`'s color ramp narrowed from
   `smoothstep(0,6,smoothIter)` to `smoothstep(4,24,smoothIter)` so true background stays
   near-black and only the real boundary halo feeds color into the accumulator.
   Confirmed by rendering and inspecting frames at multiple points across the full 45s (not just
   the first few seconds) — contrast holds steady late into the clip, doesn't drift back toward
   saturation. All 44 `hyst-render` tests still pass unmodified through every step of this fix.

### Post-Phase-1 fix #2 — beam/symmetry/composition demo tuning (2026-09-05, same day)

User: better, still not good enough — beam "just blinks to beat", plus (asked directly, multi-
select) blurry/soft overall, kaleidoscope repetitive/artificial, composition/framing boring. All
demo-level tuning in `examples/audio_driven_render.rs` (+ one small, justified `julia.rs` change),
no new correctness bugs found this round:
- **Beam**: was a single static `Segment` whose only reactivity was brightness pulsing on the
  beat — `hyst-audio` doesn't expose real waveform/scope data yet (R1 scope), so there was nothing
  else to trace. Real design intent per `lissajous.ts`: an idle 3:2 Lissajous curve. Added
  `lissajous_segments()` (96-segment polyline, amplitude breathing with `energy`, phase drifting
  with `t`) — a legitimate stand-in matching the actual spec, not an arbitrary demo choice.
- **Kaleidoscope "repetitive/artificial"**: the demo held `mirror_strength` at a flat `0.5` the
  entire clip — this directly violates the project's own stated design principle (`docs/
  LEGACY_TS.md`/AGENTS-era thesis: "earned symmetry... rises with tension/energy, snaps to full
  only on an event, never a constant filter"). Now `0.15 + 0.5*energy` — the demo was quietly
  breaking its own inherited design rule, not a hyst-render bug.
- **"Too blurry/soft"**: `decay` was held near its max (`0.85-0.95`) for the full 45s — trail
  length scales ~`1/(1-decay)`, so this compounded into ever-softening blur with no real "memory
  fades" moment. Lowered to `0.55-0.75`. (Distinct from the earlier exposure/wash-out fix — that
  was brightness saturation, this is trail length/softness; both were real, separate problems.)
- **"Composition/framing boring"**: `JuliaNavState::driven_by_time` (still explicitly R6's
  placeholder, not real autopilot) held `zoom`/`pan`/`hue_shift` at fixed defaults the whole time —
  only `c` orbited. Added slow zoom breathing, pan drift, hue drift — cheap, still clearly a
  stand-in, but no longer a frozen centered frame.
All 44 `hyst-render` tests still pass unmodified. Confirmed by rendering and inspecting multiple
frames across the clip (not just eyeballing one) before sending.

### Post-Phase-1 fix #3 — real zoom dive + rarer kaleidoscope (2026-09-05, same day)

User, third round: still not good enough — kaleidoscope "too frequent and shitty", and the
fractal has no zoom-in. Two real fixes:
- **No zoom-in**: `driven_by_time`'s zoom only *breathed* (oscillated `1.6±0.6`) from the previous
  round, never actually dove in. Replaced with a real exponential zoom-in cycle (`ZOOM_START=2.5`
  → `ZOOM_FLOOR`, rate `0.12`/s, resets and dives again) — matches the project's own actual thesis
  (XaoS-style continuous dive, `docs/LEGACY_TS.md`'s zoom-rate history). **A real bug surfaced
  fixing this, not just tuning**: zooming into a *fixed* point (this placeholder has no vortex-
  search toward genuine boundary detail — that's explicitly R6's job) frequently drifted into the
  Julia set's uniformly-featureless interior well before any float-precision limit — confirmed by
  rendering and inspecting frames at multiple points in the dive, not assumed. Fixed by keeping pan
  drift small (was `0.25/0.2`, now `0.04/0.03`) and choosing `ZOOM_FLOOR=0.6` (was tried at `0.15`
  first — went empty; `0.6` keeps real detail in frame the whole cycle). This is still a
  placeholder centered zoom, not real navigation — R6 replaces it for real.
- **Kaleidoscope "too frequent"**: previous round's `0.15+0.5*energy` meant symmetry was visible
  most of the time (real tracks spend a lot of time above a low energy threshold). Changed to a
  hard-gated `smoothstep(0.65, 0.9, energy) * 0.55` — near-zero below 65% energy, only appearing
  in genuinely loud moments. "Shitty"-looking wasn't separately chased this round — rarity was the
  concrete, actionable part of the complaint; if it still looks bad only in the rare loud moments
  once frequency is fixed, that's the next thing to isolate.
All 44 `hyst-render` tests still pass unmodified; each change verified by rendering and inspecting
multiple real frames (not assumed from formulas alone) before sending.

### Post-Phase-1 fix #4 — seamless dot↔void zoom cycle, tempo-gated beam (2026-09-05, same day)

User now at the machine — **stop sending files, render full quality locally instead** (this
session's `SendUserFile` use for this render ends here; future review is local file inspection).
Two real, substantive requests, not just tuning:
- **"No cuts" on the zoom reset**: previous round's reset (`ZOOM_FLOOR` back to `ZOOM_START`) was
  a visible jump between two populated-with-detail frames. Redesigned per the user's own idea:
  the dive now runs from `ZOOM_DOT=60` (whole set reads as a tiny dot) all the way down to
  `ZOOM_VOID=0.03` (deep enough the frame is solid interior color), *then* resets — and the
  interior "void" color and the far-background (near-instant-escape) color were unified into one
  shared `VOID_COLOR` constant specifically so both ends of the cut are the same color, making the
  reset itself invisible. The visible effect: zoom in from a dot, grow into full boundary detail,
  keep zooming past it into featureless void, cut (unnoticeable), reappear as a tiny dot again —
  echoes the fractal's own real self-similarity rather than faking it. Not perfectly seamless on
  inspection (a faint residual texture from the memory field's own lingering accumulation is
  visible for a couple seconds right after reset — flagged, not hidden) but a real, large
  improvement over a hard cut.
- **Beam "tries to glow to the BPM before the kick starts and misses"**: the local demo pulse
  (added in an earlier round, since `hyst-audio` doesn't compute `beat_pulse` yet) triggered on
  any `beat_phase` wraparound regardless of confidence — during a quiet intro, `BeatTracker`'s
  phase free-runs from a low-confidence/default estimate, so the pulse was visibly guessing wrong
  before real tempo lock. Gated on `bus.tempo_confidence > 0.2` — no pulse at all until the
  tracker actually locks onto a real beat. User does NOT want the Lissajous beam removed, just
  fixed — kept, not touched otherwise.
- Also bumped to real quality for review: 1024×1024, 30fps, 90s (was 512×512/24fps/45s) — renders
  in ~34s on this machine's GPU, still fast. Output path (not sent, inspect locally):
  `crates/hyst-render/test-output/audio_driven_render_with_audio.mp4`.
All 44 `hyst-render` tests still pass unmodified; verified by rendering and inspecting frames
specifically at the dot/void/reset transition points (not just spot-checking arbitrary frames)
before reporting back.

### Post-Phase-1 fix #5 — boundary-probe pan target, closer opening shot (2026-09-05, same day)

User: zoom shouldn't target a fixed center, it should aim at "interesting regions"; opening shot
shouldn't be the far-away dot, should start closer. Both real, implemented (not just tuned):
- **`find_interesting_pan(c)`** (new, `julia.rs`): a cheap, deterministic stand-in for real
  vortex-search (still R6's actual job) — grid-searches a 24×24 neighborhood of the origin (radius
  0.9) for the point with the *highest finite* escape-iteration count via `escape_iters`, which
  mirrors `JULIA_GLSL`'s own escape loop exactly (same `MAX_ITER=192`, same bailout). The insight
  that makes this correct rather than approximate: the screen center always samples `z0 = pan`
  regardless of zoom (`uv=(0,0)` at center, `z = pan + uv*zoom`), so probing candidate `pan` values
  directly at this reference scale finds a real point in the complex plane, not a UV/zoom-relative
  guess. A point near the boundary (without being captured by the interior) takes the longest to
  escape, so maximizing finite escape count hugs genuine detail. `c` itself is now discrete-per-
  cycle (golden-angle spread across `cycle_index`, was continuous rotation) specifically so each
  dive lands on a different probed region — real cycle-to-cycle variety, confirmed by rendering
  multiple cycles and comparing (dendrite detail spread asymmetrically across frame, not a
  recurring centered blob).
- **Opening shot too far away**: `driven_by_time` started exactly at `t_in_cycle=0` (`zoom=
  ZOOM_DOT=60`, the tiny-dot extreme). Added `START_OFFSET_SECS=21.0` added to `t` before deriving
  `cycle_index`/`t_in_cycle`, landing the very first frame already at a moderately-zoomed, detail-
  populated view instead of a nearly-invisible dot.
All 44 `hyst-render` tests still pass unmodified. Per user's prior instruction, this render was
**not** sent — verified locally by extracting and inspecting frames across multiple cycles, output
left at `crates/hyst-render/test-output/audio_driven_render_with_audio.mp4` for the user's own
local review.

### Post-Phase-1 additions — perturbation deep zoom + Mandelbulb (2026-09-05, same day)

User asked two real technical questions ("what stops us zooming forever," "could we use a better
fractal now we're not WebGL2-limited") and green-lit both as parallel subagent builds.

**Julia perturbation-orbit deep zoom** (`passes/julia.rs`, new `render_julia_perturbed` alongside
the untouched `render_julia`): CPU computes an `f64` reference orbit once per frame at the view
center, uploads it as an `Rg32Float` height-1 texture (reusing the `.hyst` format's own
`scriptTexture` convention), and each pixel iterates only its small float32 delta from that orbit.
**Real, honestly-reported numbers**: direct iteration degrades from plausible (719 distinct colors
at a 64×64 test render) to fully degenerate (1 color) between `zoom=1e-6` and `1e-8`; perturbation
holds 500-1100+ distinct colors through `1e-9` — three orders of magnitude deeper. Perturbation's
own breakdown at `1e-10` turned out to be a *different* mechanism than hypothesized going in (the
shader's `full = Zi + delta` float32 addition losing `delta` near `Zi`'s O(1) magnitude, not the
reference orbit's own f64 precision) — found and reported honestly rather than assumed. Not yet
wired into the demo's zoom cycle (which only goes to `zoom=0.03`, nowhere near needing this) —
real integration is R6's job once real deep-zoom navigation exists.

**Mandelbulb** (`passes/mandelbulb.rs`, new, standalone): power-8 raymarched 3D fractal ported
from the frozen TS tree's never-shipped `MandelbulbScene.ts`/`mandelbulb.frag.glsl`.
`MandelbulbNavState` (camera distance/rotation/power/max_steps/accent) + `render_mandelbulb`,
matching `JuliaNavState`/`render_julia`'s shape. **Not wired into `renderer.rs`'s pipeline** —
open question flagged by the agent itself: does the 2D memory-field ping-pong/fold concept even
apply to a 3D raymarched scene, or does Mandelbulb need its own composite path. Own standalone
example (`examples/mandelbulb_render.rs`) proves it renders real shaded fractal surface (confirmed
by rendering and inspecting a frame — a real lobed power-8 bulb with glow, not blank/garbage).

Both: full `cargo check/test/clippy --workspace` clean (173 tests total). Neither sent to the user
(per the earlier "stop sending, I'm at the machine" instruction) — rendered/verified locally.

### Mandelbulb quality pass + beam fixes (2026-09-05, same day)

User rendered both fractals against the real Downloads mp4 song ("Instant Crush") and reported
Mandelbulb "too low-res, jittery, looks like a mess... doesn't zoom in at all, undetailed, looks
like a 3d print" — a real quality gap, delegated to a subagent given its size.

**Mandelbulb** (`passes/mandelbulb.rs`): real DE-gradient surface normals (central-difference) +
Lambertian diffuse + a cheap 5-step ambient-occlusion approximation (was flat/glow-only shading —
this is what actually caused the "3D print" look, exactly as hypothesized). 9x supersampling to
fight power-8 boundary aliasing. Tightened surface epsilon (0.0015→0.0006), raised step budget
(160→220). A real continuous zoom-in dolly (cosine breathe cycle — no hard-cut reset attempted,
since a 3D camera has no free "void-colored" transition point the way Julia's 2D zoom does).
**Found and fixed a real bug** in the demo: `mandelbulb_state` was overwriting the whole zoom-dive
distance every frame with an unsmoothed `3.2 - 0.9*energy`, silently discarding the dive entirely
— fixed with exponential energy smoothing layered on top of the dive instead of a hard override.
**Verified, not assumed**: determinism check (identical state twice → byte-identical output, ruling
out raymarch-noise as a jitter source), frame-to-frame diff across a full clip (median ~3.9%, worst
~37.5% at the deepest/loudest moment — real, disclosed, only partially solved: 512×512+9xSSAA isn't
enough resolution to fully resolve power-8 detail that close), and direct visual inspection of 7
frames across the clip confirming real depth/shading and a genuine zoom progression. Cost: 15.9-
17.3ms/frame at 512×512 (was ~2.8ms pre-quality-pass) — a real, disclosed tradeoff, not profiled at
the demo's actual 1024×1024/90s target by the subagent (done by the orchestrator next, see below).

**Beam ("lissajous isn't high-res enough... should look like a perfectly rounded neon light, no
visible seams/turns/vertices")** — done directly, not delegated (touches the shared `beam.rs` pass
both fractals use). Root cause: `render_beam`'s segments are flat-capped rectangular quads with no
join geometry — any angle between consecutive segments leaves a visible notch. Added
`render_beam_joints` (round discs at every polyline vertex) to `passes/beam.rs`, wired into
`renderer.rs`'s frame loop automatically after `render_beam`. **Two real follow-up bugs found by
actually rendering and looking, not assumed fixed on the first pass**:
1. First attempt's joint falloff profile (`smoothstep(1.0,0.75,d)`, solid core to 75% radius then
   a hard cutoff) was harder-edged than the segments' own falloff — read as a visible bead/pearl
   chain, not a smooth tube. Fixed by matching the segment's exact falloff shape.
2. Still beaded after that — the REAL cause: standard alpha blending compounds every time a joint
   disc overlaps an already-lit segment (nearly everywhere, for a dense near-straight polyline),
   re-brightening every vertex into a bump. Fixed with `Max` blending on the joint pass (`BlendOperation::Max`,
   factors `One`/`One`) — a disc can only raise a pixel darker than itself (the actual notch), never
   re-brighten one the segment already covers.
3. Still visibly beaded even after both fixes — the ACTUAL remaining cause was purely geometric,
   not a shading/blending bug: at line half-width 0.02 (~20px at 1024px) and 240 polyline points,
   segment spacing (~9px) was *shorter* than the line's own width — a round join's disc always
   bulges past a short rectangle's parallel sides, independent of blend mode. Fixed by *reducing*
   point count (240→72) and thinning the line (half-width 0.02→0.012) — round joins already handle
   arbitrary angles fine on their own; the fix was fewer, longer segments, not more, shorter ones.
Real test added (`joint_disc_fills_the_notch_two_angled_segments_leave`) — a known notch point
proven unlit by segments alone, then proven lit once joints are drawn. All `hyst-render` tests pass
(52), full workspace clean.

### Beam joints reverted; Mandelbulb phase-warp bug fixed (2026-09-05, same day)

User rendered the "fixed" beam and reported it looked *worse* — "balls connected together chain
shit" — and separately that Mandelbulb now "rotates/zooms, then snaps back, then again and again."

**Beam**: the round-joint-disc approach (previous entry) was fundamentally the wrong tool for a
dense, near-straight polyline — a disc's circular silhouette always bulges past a short
rectangle's parallel sides, independent of falloff/blend tuning, reading as a bead chain at any
point density high enough to look smooth otherwise. **Reverted**: `renderer.rs` no longer calls
`render_beam_joints` (the function/test stay in `beam.rs`, unused — a real primitive for sharp
corners elsewhere, just wrong for this smooth curve). Back to segments-only, but with enough
points (72→220) and a thin enough line (half-width 0.012) that flat-cap notches at the tiny bend
angle between consecutive segments are genuinely imperceptible — "invisible vertices/bends"
without needing join geometry at all, matching what the user actually asked for.

**Mandelbulb**: real bug, not a tuning issue. `examples/mandelbulb_render.rs`'s `mandelbulb_state`
fed `driven_by_time(t * (0.6 + 0.8 * bus.sub))` — scaling the phase argument itself by a per-hop
audio value. `t` always increases, but `t * factor` does NOT stay monotonic frame-to-frame when
`factor` swings on every bass hit (e.g. `t=10,factor=0.6→6` then `t=10.1,factor=1.4→14.1`, a
forward jump far exceeding one frame's real elapsed time) — exactly the reported "snap." Fixed:
`driven_by_time(t)` — the plain elapsed time, letting `MandelbulbNavState`'s own cosine breathe
cycle stay smooth as designed; audio now only modulates `distance`/`accent`, never the phase
argument driving the deterministic cycle. Verified by re-rendering and comparing consecutive
frames (100/101/102) directly — no jump. General lesson worth remembering for R6 (the real
autopilot, which will modulate motion parameters from audio far more): **never scale a monotonic
time/phase argument by a value that itself isn't monotonic** — modulate rate via integration
(accumulate a phase variable by `dt * rate` each frame) or modulate a separate parameter, never
multiply elapsed time directly by a jittery signal.

Both re-rendered against the full real target track ("Instant Crush," 90s/1024×1024) and visually
confirmed fixed before reporting. `cargo check/test/clippy --workspace` clean throughout.

### Phase 1 completion — R2/R3/R4/R5/A via parallel subagents (2026-09-05, same day)

User asked for phase/section-parallel subagent execution against the full plan. Launched 5
parallel subagents against Phase 1 (everything blocked only on R0/R1, per the plan's own wave 1):
R2 continuation, R3, R4, R5, workstream A. Each worked only inside its own crate/`scripts/`,
none touched `AGENTS.md`/root `Cargo.toml`/each other. All 5 landed clean; full detail below is
condensed from each subagent's own final report (available in this session's history if more depth
is ever needed).

**R2 (`hyst-render`)** — done-when met: `isf_translate.rs` (ISF-flavored GLSL → real GLSL, using
`wgpu`'s `naga` GLSL frontend directly — much less work than a hand-rolled GLSL→WGSL text
translator, verified end-to-end against a real `.hyst` fixture through `parse_hyst()` →
translate → render → readback); `gpu.rs` gained a generic GLSL fullscreen-pass driver + fixed a
real fullscreen-quad Y-flip bug found via a two-pass test; `passes/` — `julia.rs` (substrate,
`JuliaNavState` as the externally-settable seam R6 will drive), `memory_field.rs` (curl-noise +
kaleidoscope fold, **using the documented cross-fade-by-color fix, not the naive angle-blend that
caused the original fold-seam bug**), `persistence.rs`, `bloom.rs`, `composite.rs`, `beam.rs` (real
instanced-quad line rasterization), `noise_texture.rs`; `renderer.rs` wires all of it into one real
frame loop. A real ping-pong bug (double-bookkeeping cancelling itself out, frame 100 silently
identical to frame 0) was caught by a test, not eyeballing. `examples/audio_driven_render.rs`:
real WAV → `hyst_audio::FeatureExtractor` → driven render → mp4 via `ffmpeg`. 44 tests (was 34).
Deviations: GLSL is Vulkan-flavored (`#version 450 core`, forced by `naga`), no perturbation-orbit
deep-zoom precision, bloom single-level not mip-cascaded, beam alpha-blended onto final output
rather than fed through `composite.frag.glsl` as a sampled input. No pixel-diff against the (now
nonexistent-without-a-browser) frozen build — flagged honestly, not fakeable.

**R3 (`hyst-script`)** — `mlua` 0.12 (lua54+vendored). `contract.rs`/`frame.rs`/`lua_bridge.rs`/
`shared_state.rs`/`runtime.rs`/`engine.rs`. Real fault-isolation test: script errors on frame 5,
frame 5's exposed value asserted equal to frame 4's (not zero, no panic); real infinite-loop
script interrupted via `mlua`'s instruction-count hook (wall-clock-asserted <2s); persistent
cross-call Lua state asserted against an exact closed-form decay (`0.9^7`), proving real state
survival, not reset-per-call; wrong-length `scriptTexture` output coerced to declared length
*before* ever leaving the sandbox. 22 tests. `ScriptContract` is its own type, not shared with
`hyst-render`'s `IsfScriptOutputKind` — R2/R3 are parallel workstreams, shapes match by contract
not by dependency; translating a parsed `.hyst` into a `ScriptContract` is future glue for R6.

**R4 (`hyst-choreo`)** — `curve.rs` (real Penner/easings.net formulas, exact closed-form test per
family, `Bezier(0.0)` provably collapses to exact `Linear`), `effort.rs` (Time/Weight/Space only,
no Flow), `moves.rs`, `generator.rs` (hand-rolled xorshift64\* RNG — avoided adding `rand` as a
dependency), `topology.rs`, `formation.rs` (unison/canon/call-and-response/breathe/affine/scatter,
composable `mirror`, ordering-source as one parameter not two formation types). **The mandatory
acceptance test is real and exact**: N=1 is provably a no-op for every formation mode (same
formula, no special case), N=6/N=12 canon offsets assert the exact `i*(duration/n)` formula, not
just "differs from agent 0". 37 tests. All formation modes return one uniform `AgentInstruction`
struct (unused fields at neutral default) — this uniformity is *why* N=1-no-op falls out
structurally rather than needing a branch.

**R5 (`hyst-output`)** — `cadence.rs`/`diff.rs`/`failure.rs` (generic, reusable by any future
output), `field.rs` (`FieldSource` trait + synthetic `BilinearGradient`/`Checkerboard`/
`MovingGaussianBlob` — no dependency on `hyst-render` actually being finished, per instruction),
`array_topology.rs`, `field_output.rs` (`FieldOutput: VizOutput`, ~15Hz cadence, diff-only
transmission, `mark_element_failed` freezes one element without touching any other). **Mandatory
acceptance test real and exact**: N=100 grid, exact bilinear expected value per element, 8
scattered failures injected mid-run, field then changes — asserts failed elements frozen while
every other element tracks the new field exactly, no panic/stall. 18 tests. `ChoreographyOutput`
(needs R7) and real hardware transport correctly out of scope this session.

**Workstream A (offline SSM pipeline, `scripts/`)** — corrected the plan's own misnamed directory
(it's `scripts/`, not `tools/` — fixed in this file's rule 2 above). `ssm.ts` (beat-sync features,
z-score normalized; `buildSSM`; `checkerboardNovelty`/`pickPeaks` promoted from
fallback-only-per-spec to **load-bearing**, since allin1 was infeasible this session — see below);
`repetition.ts` (orchestrates into a full schema-4 sidecar); `schema4.ts` (new additive TS types,
field-for-field matching `crates/hyst-core/src/sidecar.rs`'s Rust schema-4 shape — defined in
`scripts/`, never touching the frozen `src/shared/sidecar.ts`). Synthetic SSM test: two-identical-
halves cross-block similarity 0.95+ vs. <0.3 for a shuffled control. **Real-track verification,
reported honestly, not fabricated**: `hysteresis.wav`/`afterimage.wav` each found one plausible
intro-recurs-near-outro repeat (sim 0.72/0.45); `panicspiral.wav` found 9 repeats, one clean
(sim 0.76, same bookend shape) but several weak (0.17–0.3) explicitly flagged as marginal/
unconfirmed by ear — no hard assertion was written for the weak cases, per the brief's own
instruction not to assert unverified numbers. 351 TS tests total (schema-2/3/4 fixtures unmodified
and green). `analyze.ts`'s CLI has no `--repeats` flag yet — `computeSchema4Sidecar` is library-only.

**allin1 retry (separate follow-up subagent, same day)**: user asked why allin1 (the plan's
originally-preferred beat/boundary source) couldn't be used, given the first attempt's "pip hung"
verdict looked like it might just need patience. Retried properly: pinned a CPU-only `torch` wheel
first (the actual fix — avoids pip's resolver considering the full CUDA wheel matrix), which
worked; `allin1` itself then installed; `madmom` (an allin1 dependency) needed 3 known, mechanical
Python-3.12/numpy-2 compatibility patches, applied and confirmed importable. **Real, different,
new blocker found**: `natten` (a neighborhood-attention CUDA/C++ extension allin1's model needs)
has no prebuilt wheel for this Python/torch ABI, and its from-source build re-downloads and
rebuilds a full `torch` copy just to read its own build requirements — a real hour+ compile, not
a resolver hang. Killed after a bounded budget rather than let run unbounded; user chose to keep
the existing causal-beat-grid fallback rather than spend that budget (§4 above). No leftover venv/
cache (routed to `/secondary`, ~4.1G freed after cleanup — root `/` only had 1.3G free, correctly
avoided). `scripts/README.md`'s "Known limitations" section documents the real current state
(torch/allin1 install path now works; `madmom`'s patch; `natten` as the specific remaining
blocker) — read that before re-attempting rather than repeating this session's diagnosis.

**A real audio-driven render was produced and sent to the user** — first with the demo's own
6s/256×256 clip (no audio, per the example's original scope), then, after the user asked for a
longer clip with a "frame of reference," bumped to 45s/512×512/24fps and the real `hysteresis.wav`
audio muxed in via `ffmpeg` (video: `-c:v copy`, audio: `pcm→aac`). Also fixed in the demo (not in
`hyst-audio` itself, which hasn't built this signal yet — flagged in §4): `SignalBus.beat_pulse` is
never populated by `hyst-audio`'s `FeatureExtractor` (R1 scope never included it), so the beam
never actually pulsed on the beat in the first render — the demo now computes a local decaying
pulse from `beat_phase` wraparound detection instead. This is a demo-local fix, not a real
`hyst-audio` fix — `beat_pulse` staying unpopulated in the actual `SignalBus` is still a real,
un-fixed gap worth closing in a future `hyst-audio` session.

**Real bug found from the sent render, fixed same session**: user reported the first render
"illegible" — correctly. `passes/julia.rs`'s `palette()` normalized color against
`smoothIter/MAX_ITER` with a single linear crossfade: exterior pixels needed near-MAX_ITER escape
time to show any color at all (most of the frame stayed near-black), while the *interior*
(never-escapes) region got the one fully-saturated color — backwards from standard escape-time
convention, and it produced exactly the flat, blobby, boundary-detail-free look reported. Fixed:
color now bands cyclically off the *absolute* smooth escape count (real escape-time coloring,
contour rings visible well before MAX_ITER) and the true interior is forced dark instead of
bright. All 44 `hyst-render` tests still pass unmodified; re-rendered and visually confirmed real
fractal detail/banding/bloom now show up. Worth remembering: **a green test suite did not catch
this** — the existing tests check pixel-level mechanics (does color change, is symmetry real) not
whether the image is actually legible/attractive. Visual review of an actual render remains
necessary for anything user-facing here, tests alone aren't sufficient signal for render quality.

### Julia reacts to music + dynamic IQ-cosine palettes on both fractals (2026-09-06)

User: Julia "too static... doesn't react to music", Mandelbulb "bad, should zoom in deep", both
palettes "very bad and illegible... make dynamic too". Two subagents, in parallel.

**Julia (`passes/julia.rs`)** — added `JuliaDriver`, a stateful `dt`-integrated driver replacing
`JuliaNavState::driven_by_time(t)` (kept, unused by the demo now, still backing its own tests) as
what `audio_driven_render.rs` actually drives with: owns `zoom_log`/`c_angle`/circular
`hue_smoothed` EMA of `chroma_root_hue`/`color_phase`; zoom-rate and c-orbit-rate integrated via
`dt * rate(audio)` (energy/onset_density-modulated) — never scaling the phase itself by audio (see
this file's own prior "snap" bug entries). Golden-angle region jumps stay gated to discrete
zoom-cycle-reset events only, since those are one-shot, not continuous. Palette in both
`JULIA_GLSL`/`JULIA_PERTURBED_GLSL` rebuilt on the IQ cosine-gradient formula
(`a + b*cos(2pi*(c*t+d))`), hue from `chroma_root_hue`, accent from `centroid`, mix from
`flatness`. New tests: adversarial jittering-audio snap check, silence-still-evolves check,
real-multi-hue-variety check.

**Mandelbulb (`passes/mandelbulb.rs`)** — added `MandelbulbDiveDriver`: real deep dive (log-distance
integration down to `DIST_NEAR=1.2`, DIST_FAR=4.6 unchanged), same safe rate-integration shape as
`JuliaDriver`. `DIST_NEAR` picked from a real empirical sweep (see the struct's own doc for the full
table) — first choice `0.75` looked safe at one baseline rotation angle but a full rendered clip
caught single-frame flash-pops at ~20/32 sampled angles (camera embedded in solid material,
angle-dependent, not just distance-dependent); `1.2` swept clean at 0/240 angles. A second real bug
(also only caught by diffing a full rendered clip, not by the angle sweep) — a ray grazing tangent
to the surface near the recede phase could blow up the glow-accumulator's clamped floor into a
single all-magenta frame — fixed by raising that floor. Palette rebuilt on the same IQ
cosine-gradient formula, input `t` from a real smooth escape-iteration count (an orbit-trap input
was tried first and rejected — stayed too flat across a visible surface patch, see `mandelbulbDE`'s
doc) plus `chroma_root_hue`. Adaptive surface epsilon added (scales with camera distance) so a
fixed epsilon isn't wrong at both ends of the now-much-larger dive range. This subagent's task
process hit a rate-limit error before delivering its final report; its actual work was still fully
committed, compiling clean, and all tests passing — verified directly rather than trusted blind.

**Verification, both**: `cargo clippy --workspace --all-targets -- -D warnings` clean.
90s/1024×1024 real-audio (`instant_crush.wav`, extracted from the user's own YouTube download)
renders for both. Mandelbulb: 0/2700 frames show the historical flash-pop signature (byte-diff
sweep across every adjacent pair). Julia: mean frame RGB checked at 6 points across the clip, shows
real drift (e.g. blue-dominant early → red/purple mid → balanced late), not a static frame; only
1/2700 adjacent-frame pairs shows a large jump, consistent with a real beat-flash rather than a
snap bug. Rendered outputs: `crates/hyst-render/test-output/audio_driven_render.mp4` (Julia),
`/home/stcksmsh/.claude/jobs/4f2df065/tmp/out_mandelbulb/mandelbulb_render.mp4` (Mandelbulb, kept
outside the shared `test-output/` dir via the `MANDELBULB_OUT_DIR` env var to dodge the
parallel-render race documented above). Both awaiting user's own lookthrough before R6.

### Julia: real continuous deep zoom, depth-tied `c`, contrast fix, oscilloscope beam (2026-09-06)

User, verbatim, on the previous entry's Julia work: "the julia also looks bad... changing the C...
to the beat/tune of something... would make it more dynamic as we zoom in, also the perturbation
doesnt seem to work, what we get is zoom in, then the snapback to fully zoomed out then back in,
its in the same loop it was in before... the visuals should look good on their own." Separately, on
the Lissajous beam: "keep the current lissajous shape, but make the line move a bit like an
osciloscope line." Four tasks, one subagent, `passes/julia.rs`/`renderer.rs`/
`examples/audio_driven_render.rs`/this file only (Mandelbulb handled in parallel by a sibling
subagent, no file overlap).

**Root cause of "perturbation doesn't work," confirmed exactly as hypothesized going in**:
`render_julia_perturbed` existed, was tested, but `renderer.rs::render_frame` only ever called
plain `render_julia` — dead code. Separately, `JuliaDriver`'s dive floor was `ZOOM_VOID=0.03`, a
depth so shallow perturbation was never needed to reach it — the real reason the whole cycle read
as short and repeating regardless. **Fixed**: `renderer.rs` now always calls
`render_julia_perturbed` (it's an exact algebraic reformulation of the same recurrence at shallow
zoom too, not an approximation, so it degrades gracefully — no depth-gated switch needed);
`JuliaDriver`'s floor is now `ZOOM_FLOOR=1e-9` (within `render_julia_perturbed`'s own doc'd proven
range, 500+ distinct colors at that depth), so the cycle now takes ~25.8 natural-log-units instead
of ~7.6 to complete — at this driver's rate range, longer than a typical clip. The reset event
itself is unchanged in shape (still a discrete golden-angle jump + fresh `find_interesting_pan`, a
real "cut to a new dive"), just far rarer. **Verified against the real target track**
(`instant_crush.wav`, 90s/1024x1024): a standalone CPU-only trace of `JuliaDriver` driven by the
track's real `SignalBus` hops (no GPU needed) shows zoom decreasing monotonically for the entire
clip, 2.56 → 1.75e-7 (7.5 orders of magnitude), **0 resets across 2700 frames**. Full rendered-clip
adjacent-frame byte-diff (2699 pairs, `>10`-per-channel-changed pixel count): mean 2.86%, 17 pairs
>40% — cross-checked against the zero-reset trace (ruling out the reported bug specifically) and
attributed to two real, disclosed, non-bug causes: a global `chroma_root_hue`-driven palette
recolor sweeping the memory field's whole accumulated trail at once, and the fractal boundary's
genuine chaotic sensitivity to `c` at deep zoom (amplified on purpose by the next fix). Not chased
to zero — both are legitimate consequences of "make it reactive," not artifacts of the old bug.

**`c` tied to zoom depth**: added a second, tonal `c`-orbit (driven directly by `chroma_root_hue`,
at its own angle) alongside the existing beat/energy orbit, and scaled *both* orbits' radius (plus
the beat orbit's angular speed) by `depth_frac = zoom_log / cycle_log_len` — 0 at the top of a dive,
1 at `ZOOM_FLOOR`. `c` now visibly moves more, and reads more tonally, the deeper the dive goes,
tying zoom and `c` into one system rather than two independent sliders. New test:
`c_orbit_becomes_more_pronounced_as_zoom_deepens` (measures real per-frame `c` displacement early
vs. late in a dive under identical audio; had to warm up the "early" driver 10 frames first — the
first couple of frames' `hue_smoothed` EMA convergence transient was initially swamping the actual
depth-based signal being tested, a real methodology bug caught by the test's own first failing run,
not shipped unnoticed).

**Palette/contrast ("visuals should look good on their own")**: a real luminance-histogram probe
(256x256, several timepoints, both raw substrate and full pipeline) found real low contrast — full
pipeline luminance std as low as ~19/255, floor never dropping below 38/255 across a synthetic
90-frame run. Two separate real causes, both fixed: (1) `palette()`'s `fwidth`-based anti-alias fade
was unfloored, damping most on-screen fractal detail (genuinely high-derivative, self-similar
territory) toward flat mid-gray — floored at 0.35 (`0.35 + 0.65/(1+6*fwidth(...))`, both
`JULIA_GLSL`/`JULIA_PERTURBED_GLSL`). New regression test: `palette_keeps_real_contrast_not_a_flat_
wash`. (2) `audio_driven_render.rs`'s bloom/exposure (`threshold=0.3, strength=0.4-1.2,
exposure=0.08`) let bloom spread from nearly every pixel above a low bar, compounding with the
memory field's documented fixed ~7x steady-state gain into a persistent haze; retuned to
`threshold=0.55, strength=0.2-0.7, exposure=0.035`, measured (same synthetic probe) floor drop
38→24/255. Honest disclosure: `memory_field.rs`'s own gain formula wasn't touched (out of scope,
and documented as intentional) — a real, tunable-later tradeoff remains, not eliminated.

**Beam oscilloscope jitter**: `lissajous_segments` keeps its exact base 3:2 Lissajous formula
unchanged (per the user's explicit "keep the current lissajous shape") and adds a small
**perpendicular** wobble per point, driven by the demo's own real per-hop mono sample buffer
(nearest-index resampled down to the curve's point count) — genuine waveform values, not an
amplitude/RMS stand-in — using the curve's own analytic tangent (not a finite-difference
approximation) to find each point's true perpendicular direction. `JITTER_AMP=0.03` keeps the
wobble subtle enough the base shape stays the dominant, recognizable read.

**Verification**: `cargo check/test/clippy --workspace` clean throughout — 58 `hyst-render` tests
(was 55, +3: the depth-tied-`c` test, the no-reset-loop-over-a-full-clip test, the contrast-floor
test). Rendered the real target track end to end (`instant_crush.wav`, 90s/1024x1024, 2700 frames,
muxed to mp4 via `ffmpeg`) to `/home/stcksmsh/.claude/jobs/4f2df065/tmp/out_julia2/` (a session-local
`JULIA_OUT_DIR` env var override added to the demo, mirroring the sibling Mandelbulb demo's
`MANDELBULB_OUT_DIR`, specifically to avoid any risk of the two concurrent renders' `.ppm` frame
files colliding in the shared `test-output/` dir — in the end both demos write different filenames
there anyway, so the collision risk was never real, but kept the override since it cost nothing).
Verified numerically throughout (histogram/mean/diff-percentage scripts), never by opening a
rendered image, per this session's own standing instruction.

### R9 first slice — single-arm motion preview (2026-09-23)

User requested simple arm simulation. `hyst-previz` now contains dependency-free
Rust forward kinematics and three authored, beat-driven motion studies, exported
as self-contained HTML through `cargo run -p hyst-previz --example arm_preview`.
Preview supports play/pause, tempo, seeking, study selection, and optional synthetic
click track. Three illustrative links show shoulder/elbow/wrist coordination,
preparation, reach, follow-through, recovery, and hold. Frozen TS tree untouched.

Verified: targeted crate check/test/clippy, three motion/geometry/continuity tests,
and generated JavaScript syntax. Browser visual inspection unavailable; aesthetic
quality remains for user review. This is synthetic choreography, not music analysis,
physics, hardware validation, score playback integration, or dense-array preview.
Full R9 remains incomplete. Coding verification delegated to gpt-5.6-luna at user request.

### R9 music synchronization slice (2026-09-24)

`hyst-previz` preview accepts optional track URL and sidecar JSON. Audio
`currentTime` drives authored 16-beat motif; whole-track play/pause/seek, study
changes, provisional detected grid, manual BPM/beat-zero, and grid offset work.
Detected mode disables manual-only controls. Synthetic mode remains available.
Frozen TS tree untouched; coding delegated, parent handled approval integration.

Used user's Downloads Instant Crush video: lossless AAC extraction and existing
analyzer produced 617 beats at ~109.96 BPM. Grid contains startup anomalies and
remains unverified by listening. This is music-synchronized authored motion, not
autonomous musical choreography or hardware/physics validation.

Verified: targeted Rust tests/clippy, generated JS syntax, timing helper regression
checks, and headless Chrome real playback/pause/60-second seek/study/manual-offset/
synthetic/mobile-overflow checks; no JS errors. Screenshot inspected. Browser
seeking initially failed with Python static server (seekable range 0..0); range-
capable local media server fixed it. Assets remain outside repo in task output.

### Song-conditioned single-arm slice — 2026-09-24

Implemented compiler, absolute RMS enrichment, cue JSON export, song-default browser
previz + shared visual panel. Full track219 cues; content selects gestures/rests;
quintic constrained transitions replace repeating16-beat study on song path.
Targeted8 Rust tests, JS regressions and workspace check pass. Real track analytical
limits + sampled floor clearance pass; browser play/pause/seek inspected. Full
workspace GPU test running at allowance checkpoint; see docs/DANCE_HANDOFF.md for
logs, remaining limits and launch. No commit, frozen trees untouched. This does not
claim full R7/R9 or perceptually finished dance. Account allowance reached100%.

### Song slice follow-up — exact arrivals + shared visual timing (2026-09-24)

Hit/coil arrival knots now match chosen onset timestamp; unschedulable accents
become truthful groove. Added optional arrivalAnchor, strict RMS validation,
whole-score audit CLI, matching visual pulse and Next accent inspection. Real track
222 cues/56 exact anchors; constraints +120Hz floor check pass (min29.26cm).
Compiler8/previz4 tests and targeted clippy/JS pass; workspace CPU tests pass.
Full clippy blocked by existing julia.rs modulo warnings; GPU probe timed out45s,
/dev/dri absent. Browser play/pause/seek/delay+anchors pass, no console errors.
Updated docs/DANCE_HANDOFF.md + previz README. No commit or frozen-tree changes.

### Song slice — sections, motif recurrence, remote clock (2026-09-24)

`hyst-compile` segments song by z-scored multi-feature novelty (4s windows,
median+2·MAD, >=8s), classes sections quiet/mid/peak/rest, reuses motifs for
feature-similar sections (mirrored/scaled variation), inserts gather/settle
transition cues and section postures. `Score.sections`/`Cue.section` additive.
Audit moved to `hyst_previz::audit_score`; `tests/acceptance.rs` covers audit,
recurrence, transitions, structure-driven decisions, anchors. Viewer remote
mode clock handoff fixed. Real track re-extracted from user MP4: 19 sections,
218 cues, audit pass (27.84cm clearance). Browser smoke via Playwright/WAV.
Heuristic phrasing; perceptual quality unreviewed. Details: docs/DANCE_HANDOFF.md.

### Song slice — expressive phrase planner (2026-09-24)

User rejected small-cue output. `hyst-compile` core now plans bar-based phrases
between full-range key poses (+mirrors) per section level, arrivals exactly on
bar lines/strong onsets, anticipation/overshoot, beat bounces, onset hits,
frozen rests; floor guard >=8 cm; limits = assumed servo class. Fixed lead-
truncation smear bug. Tests rewritten (compile 5, acceptance 6). Real track
audit pass. Perceptual quality awaiting user review of rendered MP4.

### Song slice — flow + section-edge timing (2026-09-24)

Section cuts refined to signed loudness steps (first loud block now 92.0–129.7s,
was 97.9–135.1). Knots gain optional velocity (C2 quintic Hermite, limit-checked),
Score gains `jointLagSeconds` (overlapping action), held bars drift toward next
pose, motif picks max-contrast poses, poses evolve per cycle. Audit now dense
1 kHz. New `sample_score` example for offline renders. Tests green; clippy clean.

### Song slice — element-following planner (2026-09-24)

Planner = calm phrase home path + voice layer following the dominant element
(vocals melody height, synth orbit, bass swing, drum dip) from new
`scripts/arm_elements.py` (heuristic HPSS/mid-side; Demucs weights host is
network-blocked in cloud env). Section cuts snap to bar lines at the start of
the loudness change. Tests: element-following acceptance test added.
