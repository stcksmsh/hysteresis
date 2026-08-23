# СИНТЕЗА visualizer — signal bus, patchbay & output boundary (v4)

Repo: `sinteza-viz`
Status: **spec, not yet implemented.** This document is written to be handed to an
implementing agent (Claude Code CLI). It supersedes nothing in `SINTEZA_VIZ.md` — it
*extends* it. Where the two could appear to conflict, `SINTEZA_VIZ.md` §0 (the thesis) and
§4 (visual composition) remain authoritative on *what the screen looks like*; this doc governs
*how signals reach any output*, screen or otherwise.

Read `SINTEZA_VIZ.md` first. This doc assumes its three-layer model (§2 ear / §3 sense /
§3a body) and its MEMORY → PROCESSING → RESOLUTION spine.

---

## 0. Why this exists (the one-paragraph brief)

Today the pipeline terminates in one hardwired consumer. `Choreographer.update()` reads a
`StateFrame` and emits a `ParamBus`; exactly one thing ever reads that `ParamBus` — the
WebGL `Scene`. Two problems follow. **(a)** The choreographer collapses a rich, always-alive
feature set (six bands, centroid, flatness, beat/bar phase, pan) into a handful of drivers
that are *flat during groove*, so for most of a track's runtime the visual degrades to an
amplitude follower — the real cause behind "doesn't work with the music enough" (already noted
in `Choreographer.ts`'s own `ENERGY_SMOOTH_SEC` comment). **(b)** Because the seam between
"produce meaning" and "consume meaning" isn't a real boundary, a second output (servos, lights)
can't be added without editing the choreographer.

This spec fixes both by splitting the choreographer into **conductor → signal bus → patchbay
→ outputs**, making the screen one output among peers, and making "signal N drives target Y"
a line of *data*, not code. Servos are explicitly deferred but the boundary is designed so
they are additive: a new output file + patchbay entries, zero upstream edits.

**Non-goal / scope discipline (read this or the project balloons):** this is a *refactor of
the existing choreographer→scene link* plus the groove-reactivity work that link currently
makes impossible. It is NOT a new subsystem. Do not build servo code, a device manager, or a
mapping UI as part of this spec — those are §8's explicitly-later work. The justification for
every part of this document is that it improves the *screen* piece shipping for the September
exhibition; the servo-readiness falls out for free and must not become the driver.

---

## 1. Target architecture

```
StateFrame (Layer 2, unchanged)
   │
   ▼
Conductor            produces the Signal Bus. Knows nothing about outputs.
   │                 (this is the current Choreographer, refactored & widened)
   ▼
Signal Bus           a flat, named, normalized, timescale-tagged set of signals.
   │                 THE contract. Everything downstream reads this and only this.
   ▼
Patchbay             declarative data: routes bus signals → output targets, each
   │                 with curve + smoothing + range + invert. No logic beyond eval.
   ▼
Outputs[]            peers, pull-model. Each reads the bus (via its routed targets)
                     and drives its device. ScreenOutput is one. ServoOutput (later)
                     is another. They never know about each other.
```

Hard rules that make the boundary real (an implementing agent MUST honor these; they are
testable):

- **R1 — Conductor is output-blind.** The conductor module imports nothing output-shaped: no
  WebGL, no canvas, no `Scene`, no serial/GPIO, no DOM. Grep test: the conductor source
  contains none of `gl`, `canvas`, `Scene`, `WebGL`, `servo`, `Serial`, `port`. If it does,
  the split has failed.
- **R2 — Outputs pull, bus doesn't push.** The bus is a plain data structure produced each
  frame. Outputs read it. The bus has no list of subscribers, no `emit`, no knowledge that
  outputs exist.
- **R3 — Outputs are peers behind one interface.** Adding/removing/swapping an output touches
  only the output registry, never the conductor, bus, or other outputs.
- **R4 — Routing is data.** Which signal drives which target is a config value, not a code
  path. Rerouting = editing a patchbay config object/file.
- **R5 — Every signal is timescale-tagged** (see §3). The tag is load-bearing for output
  safety (a servo output can refuse transient-tagged signals) and must exist from day one even
  though servos are deferred — retrofitting it later is the expensive path.

---

## 2. What changes vs. what stays

**Stays exactly as-is (do not touch):**
- Layer 1 worklet (`src/audio/worklet/**`) — feature extraction is fine.
- Layer 2 brain (`src/audio/worklet/brain/**`) — the detectors are well-built; the drop
  detector's false-positive gating in particular is not to be "simplified."
- `StructureSource` fusion/synthesize logic (`src/audio/StructureSource.ts`).
- The GL passes (`memory-field-pass`, `persistence-pass`, `bloom-pass`, `composite-pass`) and
  their shaders. The memory field is the signature layer and stays.
- The public package API (`src/index.ts` `VizOpts`/`VizInstance`) and the transport/window-bus
  contract. This refactor is entirely internal to the render side.

**Changes:**
- `Choreographer` → **Conductor** (widened; see §3, §4). Same input (`StateFrame` + `dt`),
  new output (the Signal Bus instead of the current `ParamBus`).
- **New: Patchbay** (§5) — sits between bus and outputs.
- **New: Output interface + ScreenOutput** (§6). The existing `Scene` becomes an
  implementation detail *inside* ScreenOutput, fed by patchbay-routed targets rather than
  reading `ParamBus` directly.
- `ParamBus` is **retired as the cross-boundary contract.** It may survive as ScreenOutput's
  *internal* struct (the scene still wants named GL params), but it is now produced by the
  patchbay for that output, not by the conductor for the whole world.

**Migration must be behavior-preserving at each step.** After the mechanical split (before any
new signals or groove work), the screen output must look identical to today. Prove it: the
default patchbay config reproduces the current `Choreographer`→`ParamBus` mapping exactly, and
the existing unit tests (`tests/unit`, deterministic synthetic signals) still pass. Only then
add §4's new signals and reactivity.

---

## 3. The Signal Bus (THE load-bearing design)

A flat record of named signals, produced fresh every frame by the conductor. This is the one
thing expensive to change later, so it is specified in full here and changed deliberately.

Each signal has:
- **name** — stable identifier (routing references it by name).
- **value** — normalized: `0..1` for unipolar, `-1..1` for bipolar (bipolar ones are marked).
- **timescale tag** — one of `transient | beat | bar | section | continuous`. This tells the
  patchbay what an output may safely consume (§6 servo-safety). It is a property of the
  *signal*, not the route.
- **aliveness guarantee** — every signal is meaningful every frame for the entire runtime.
  A signal that is zero/constant for 90% of a track (the current `buildProgress`/`tension`
  failure) either gets a continuous fallback baked into the conductor or does not belong on
  the bus. This is the anti-"amplitude-follower-in-a-coat" rule.

### 3.1 The signal set

Keep it tight. Every entry must earn its place by driving something continuously. Grouped by
timescale.

**`continuous` (alive every frame, the groove-carriers — the fix for the core problem):**
- `energy` — smoothed broadband RMS, 0..1. The one signal available the entire runtime.
- `sub`, `low`, `mid`, `presence`, `air` — per-band energies, 0..1 each, adaptively
  normalized. These are the mix's continuous shape and are currently thrown away downstream.
- `bandTilt` — bipolar −1..1, spectral balance (low-heavy ↔ high-heavy). Derived, cheap,
  extremely useful for driving *direction* (flow-field axis, servo lean) rather than amount.
- `centroid` — 0..1 brightness.
- `flatness` — 0..1 tonal↔noisy.
- `pan` — bipolar −1..1, whole-mix stereo balance.
- `familiarity` — 0..1, **NEW signal, §4.2.** How much the current sound resembles the recent
  past. The one genuinely novel addition; the continuous "is it listening" signal.

**`beat`:**
- `beatPhase` — 0..1 sawtooth, PLL-locked, free-runs through breaks.
- `beatPulse` — 0..1, a decaying pulse re-triggered each beat boundary (a shaped view of
  `beatPhase` that's easier to route to "throb on the beat"). Survives silence because the PLL
  does.

**`bar`:**
- `barPhase` — 0..1 sawtooth across the (assumed 4/4) bar; carries the downbeat via BarTracker.
- `downbeatPulse` — 0..1 decaying pulse on beat 1.

**`section` (the sparse, dramatic signals — kept, but no longer the *only* drivers):**
- `buildWindup` — 0..1, the spring-driven integrated build (current `windup`).
- `buildProgress` — 0..1, the raw integrated build (current `buildProgress`).
- `tension` — 0..1.
- `suspension` — 0..1, the slow "have we been held" envelope (current `suspension`).

**`transient` (event-derived; NEVER routable to slow devices — see §6):**
- `dropImpulse` — 0..1, decays from 1 at a drop, else 0. (Replaces the discrete `DropTrigger`
  for routing purposes; the discrete event may still exist internally for the symmetry snap.)
- `onsetImpulse` — 0..1, decaying pulse per broadband onset.

**Pass-through (not a "signal" but carried on the bus for the beam only):**
- `scope` — `Float32Array | null`, raw waveform, unshaped. As today. Only ScreenOutput's beam
  reads it; it is exempt from the normalization/timescale rules (it's raw samples by design,
  `SINTEZA_VIZ.md` §4b/§4c).

**Meta:**
- `idle` — bool, the existing no-audio fallback flag.
- `tempoBpm`, `tempoConfidence` — for outputs that want to scale timing to tempo.

### 3.2 What is deliberately NOT on the bus

- Derived *visual* params (fold count, decay factor, hue). Those are per-output concerns the
  patchbay produces, not shared signals. `fieldDecay`/`flowStrength`/`symmetry` move OUT of the
  cross-boundary contract and become ScreenOutput targets (they're meaningless to a servo).
- Anything that would be constant for most of a track and has no continuous fallback.

---

## 4. Conductor responsibilities (the groove-reactivity work)

The conductor is the refactored `Choreographer`. Beyond mechanically emitting the bus, it must
fix the core problem: **make the `continuous` and `beat`/`bar` signals do continuous work so
the visual follows the music even with every section detector disabled.**

### 4.1 Aliveness / fallback (the actual "doesn't react enough" fix)

The section signals (`buildWindup`, `tension`, `suspension`) are sparse — they exist only
inside detected build/break spans, a small fraction of runtime. The conductor MUST guarantee
the `continuous` and `beat`/`bar` groups are the primary carriers, so that during ordinary
groove (no build/drop/break) the bus still varies richly. The existing `energy` patch was a
first step; this generalizes it to the whole continuous group.

**Acceptance test (the brutal one, make it a real toggle):** a debug flag disables the
build/drop/break detectors entirely. With them off, playing any track, the screen output must
*still obviously be following the music* — bands moving flow, beat pulsing the field, bar
breathing it. If disabling the detectors makes the visual go inert, the conductor has failed
this section and the piece is still an amplitude follower.

### 4.2 `familiarity` — the new signal (self-similarity, online)

The one genuinely novel addition and the highest-leverage single feature. Continuous "have I
heard this recently" scalar:
- Maintain a ring buffer of recent feature vectors (band energies + centroid + flatness),
  covering the last N seconds (start N ≈ 8–16s, tune by feel).
- Each frame, compute similarity (cosine distance) of the current vector against the buffer;
  reduce to a 0..1 `familiarity` (high = current material resembles the recent past / a motif
  or loop is repeating; low = novel material just arrived).
- This is the online form of the self-similarity / Foote-novelty math from MIR structure
  analysis — the same idea used as the anti-monotony metric on the AI-album project, run
  per-frame instead of batch. Keep it cheap (bounded buffer, a few dot products).
- It is a *continuous* signal, alive every frame — that is the point: it gives the visual
  meaning to express during the 90% of a track that isn't a dramatic event.

Default screen wiring (via patchbay, §5): `familiarity` drives *organization* — high
familiarity gently blooms symmetry / order (the field "recognizes" the loop and settles);
low familiarity destabilizes it. This is distinct from the drop's symmetry *snap* (a
transient event) — familiarity is the slow, continuous organization underneath.

### 4.3 Keep the spring/damper discipline

`SINTEZA_VIZ.md` §3a's rule stands: every choreographed value is driven through a spring-damper
or envelope, never read raw — overshoot on an event *is* the punch. This now applies inside
whichever stage does the shaping. Decide and document *where* smoothing lives: on the raw
signal (in the conductor) or on the routed target (in the patchbay curve). **Rule: the bus
carries lightly-smoothed, honest signals; expressive shaping (springs, overshoot, attack/
release) lives in the patchbay per-route**, so the same signal can drive a snappy screen param
and a gentle servo from one source with different dynamics. The conductor's existing
`DtSmoother`/`SpringDamper` move into the patchbay's curve/smoothing stage.

---

## 4b. Drop detection — measurement fix + sidecar-primary (NEW, addresses a known failure)

The current live `DropDetector` (`src/audio/worklet/brain/drop-detector.ts`) both misses real
drops and false-fires, and the root cause is not thresholds — it is the primitive. It gates on
`fast − slow` low-energy difference plus a `tension`-derived thinned-credit signal. That
primitive cannot distinguish "the music got **louder**" from "the music went from **sparse** to
**full**," which is what a drop actually is. Two consequences, both observed:

- **False positives on sparse material.** A sparse ambient intro (a reverbed synth hitting
  every ~0.5–1s) makes the 80ms fast envelope spike on every hit against a slow envelope that
  can't track the gaps → a large `jump` every hit. The reverb tail then holds energy across the
  300ms occupancy window, so the confirmation *passes*. `grooveSec` (cumulative, never reset)
  leaks credit during the tails and opens the `unambiguous` gate. Every synth hit reads as a
  drop. Causally this is unwinnable: at the first hit there is genuinely no way to know it's an
  intro vs a drop — the disambiguating information (it stays sparse for the next minute) is in
  the future.
- **Misses drops after a loud build.** A drop that follows a wall-of-noise build (common in the
  project's reference artists) produces *no* energy jump because energy was already high.
  Energy-difference is structurally blind to this, the most impactful kind of drop.

**Fix, in two parts.**

**(1) Sidecar-primary for own tracks (the real fix).** Drop detection is a look-ahead problem
— a drop is defined by contrast with what preceded it. Offline, with the whole waveform,
`scripts/analyze.ts` can segment the energy + onset-density curve across the entire track, place
drops at the largest sparse→full transitions, correctly place *zero* in a uniformly-sparse
intro, and support a hand-correction pass (a track has ~1–4 drops; verifying them takes a
minute). Decision: **for tracks with a sidecar, drops come from the sidecar timeline via
`StructureSource`; the live `DropDetector` does not run.** The live detector is **fallback only**
for unknown audio (the opening party's ambient/line-in), where approximately-right is
acceptable. This matches §5's existing fusion rule ("structure prefers sidecar") — drops are
just another structural gesture that should prefer the sidecar. Do NOT keep leaning on the live
causal detector for the case (own tracks) where the easy offline version is available.

**(2) Fix the live detector's primitive (for the fallback case).** Replace `fast − slow`
energy-jump with a conjunction that measures sparsity→fullness, not loudness:
- **Fullness** — energy sustained *continuously* over a multi-second window (much longer than
  the current 300ms), with high crest-factor penalized, so a pulsing reverb synth reads as
  *not full* even while its tail keeps instantaneous energy up.
- **Onset-density jump** — rhythmic events/sec (onsets already exist in Layer 1, so this is
  cheap). A drop introduces/intensifies rhythm; a metronomic sparse intro never changes its
  density, which rejects the ambient false-positive case outright.
- **Novelty contrast** — a drop is a large novelty spike against the recent past. This is the
  same self-similarity math as `familiarity` (§4.2): a drop = a sharp drop in familiarity
  (new fullness) immediately following a sparse span. Reuse that signal rather than the
  brittle `tension`/thinned-credit apparatus.
- Fire when onset-density **and** fullness jump together after a span low on both. Remove the
  `grooveSec`-never-resets leak (make any retained "a groove exists now" gate windowed, not
  cumulative) if the cumulative version is kept at all.

Fold this into the build order: it lands with §4.2 (`familiarity`) since the fixed live detector
reuses that signal, and the sidecar-primary decision is an `analyze.ts` + `StructureSource`
change independent of the bus refactor (can be done in parallel).

---

## 5. The Patchbay (routing as data)

Sits between bus and outputs. Pure evaluation of a declarative config; no domain logic.

### 5.1 A route

A route is data with these fields:
- `from` — a bus signal name (§3.1).
- `to` — an output target id (namespaced, e.g. `screen.flowStrength`, `servo.axis0`).
- `curve` — response shape: `linear | exp | log | smoothstep | threshold(cut)` etc.
- `smoothing` — attack/release time constants (this is where the spring/envelope dynamics from
  §4.3 live; a route may specify a spring instead of a simple RC for overshoot).
- `range` — output min/max (maps normalized signal into the target's real units).
- `invert` — bool.
- optional `gain`/`offset`.

Multiple routes may target the same output target (they sum, or the config picks a combine
mode — define one: default **sum, then clamp to target range**). A target with no route holds
its default. A signal with no route is simply unused.

### 5.2 Config = the personality of the show

A patchbay config is the whole mapping. Several are saved and switched:
- `screen-only` — the default; reproduces (initially) today's look, then gains §4 reactivity.
- `full-physical` — screen + servo routes (later).
- `calm` / `idle` — sparse routing for late-evening / unattended low-key mode.

For September these are **hand-authored config files/objects, loaded by name. No editor UI.**
The data format is the flexibility ("signal N moves this instead of that" = edit one route).

### 5.3 Validation (this is where servo-safety is enforced by data)

The patchbay validates routes against target declarations (§6.1) at load:
- A target declares which timescale tags it accepts. `servo.axis0` accepts
  `continuous | bar | section` only. If a config routes a `transient` or `beat` signal to it,
  the patchbay **rejects the route at load with an error** — a servo physically cannot follow a
  hi-hat and will buzz/overheat trying. This safety is structural, not a comment someone has to
  remember at 2am while tuning.
- Screen targets accept all tags.

---

## 6. Output interface & ScreenOutput

### 6.1 The interface

Every output implements one small interface (name it `VizOutput`):
- `readonly id: string`
- `readonly targets: TargetDecl[]` — each target: `{ id, acceptsTags, defaultValue, range }`.
  This is what the patchbay validates against and routes into.
- `update(dt, resolvedTargets)` — called each frame with the patchbay-resolved target values
  for this output. The output drives its device from these. It does **not** see the raw bus
  (except the `scope` pass-through exemption, which only ScreenOutput declares a need for).
- lifecycle: `init`, `resize?`, `dispose`.

Pull-model (R2): the frame loop resolves the bus through the patchbay per output, then hands
each output only its own resolved targets.

### 6.2 ScreenOutput

Wraps the existing render pipeline. Internally it still constructs a `ParamBus`-shaped struct
for the `Scene`, but that struct is now **assembled from patchbay-resolved targets**, not
produced by the conductor. Its targets are the screen's expressive params:
`screen.flowStrength`, `screen.fieldDecay`, `screen.symmetry`, `screen.foldCount`,
`screen.hueShift`, `screen.paletteMix`, `screen.cSweepRate`, `screen.zoomRate`,
`screen.beatThrob`, … (one per meaningful GL knob). All accept all timescale tags. The
`scope` pass-through is declared here.

The `Scene`/`SceneContext` interface itself is unchanged — ScreenOutput feeds it exactly what
it feeds today; only the *source* of those numbers changed. This keeps the Julia scene, beam,
memory field, bloom, tiers, and adaptive-quality logic untouched.

### 6.3 ServoOutput (SPEC ONLY — do not implement in this pass)

Documented now so the boundary is proven against a second consumer's shape, per R3. Not built.
- targets: `servo.axis0..N`, each `acceptsTags: [continuous, bar, section]`, `range` in safe
  degrees, `defaultValue` = rest angle.
- Would additionally need (all later, §8): rate-limiting, thermal duty-cycle safety, a serial/
  GPIO transport, graceful-failure behavior (a dead axis leaves the rest running), and an
  unattended auto-recover story. None of this is in scope now. Its mere *target declaration*
  above is enough to validate that the interface and patchbay generalize.

---

## 6.4 v5 addendum: the flat Patchbay/Route model (§5) is retired — one PatchGraph engine now

A later session ("do the whole thing" — unify screen and physical-fixture routing so they can
share signals/behavior, plus a real visual node-graph editor) replaced §5's flat
1-signal-in/1-target-out Route model with the node-graph engine originally built for physical
fixtures only (`src/render/conductor/patchgraph/` — `PatchGraph`/`PatchGraphEvaluator`, a small
operator graph: signal/const/threshold-with-hysteresis/envelope/logic/combine/curve/map/target
nodes, topologically evaluated with per-node persistent state). **Left in place, not rewritten,
here in §5/§6.1/§6.2** as the historical record of the original design — this addendum
documents what actually changed and why, rather than editing the sections above out from under
that record.

- **`ScreenOutput` now consumes a `PatchGraph`, not a `PatchbayConfig`.** `Patchbay`/`Route`
  (§5.1) still exist in the tree, still fully tested (`tests/unit/patchbay.spec.ts`) — kept as a
  working reference implementation, not wired into the live render path anymore.
  `screen-only.ts`'s `Route[]` config is likewise kept as the one hand-authored source of truth
  it always was, but now only as *input* to `migrateRouteConfigToGraph()` (new,
  `patchgraph/migrate-route-config.ts`), which produces the actual default screen graph
  (`patchgraph/configs/screen-graph.ts`) that ships. **This migration is not just asserted
  correct — `tests/unit/migrate-route-config.spec.ts` numerically compares
  `PatchGraphEvaluator.evaluate()` against `Patchbay.resolve()` across 200 random synthetic bus
  states (plus dedicated cases for gain/offset, invert, invert+gain/offset, a non-linear curve,
  and multi-route summing) before this was trusted for production.**
- **§5.3's "reject unsafe at load time" guarantee is preserved, just on the new engine**:
  `PatchGraphEvaluator`'s constructor throws on any error-severity `validatePatchGraph` issue,
  same as `Patchbay`'s constructor always did — `render-worker.ts`'s hot-swap handler
  (`debugSetScreenGraph`, replacing `debugSetPatchbayConfig`) still rejects a bad edit and keeps
  the previous, still-valid graph running instead of crashing.
- **What §5.1's Route model could do that a bare node graph couldn't** (gain/offset/invert as
  three separate route knobs, `passThrough` fields, per-route smoothing keyed by `from->to`) is
  now expressed as node chains (a `map` node generalizes gain/offset/invert — see
  `migrate-route-config.ts`'s header comment for the exact affine-reflection proof) — except
  `passThrough` (`screen.idle`/`screen.scope`), which **cannot** become a graph node at all: a
  `signal` node's type is scalar-only (`RoutableSignalName`, which deliberately excludes
  `idle`/`scope` — see `SIGNAL_TAGS`), and their values (a boolean, a `Float32Array`) aren't
  scalars. These two still get resolved straight from the bus, exactly like `Patchbay.resolve()`
  always did it — now living in `outputs/resolve-screen-targets.ts`, the direct successor to
  `Patchbay.resolve()`'s contract (default-fills every declared target, including the two
  pass-throughs, before overlaying whatever the graph actually routes).
- **The three genuinely nonlinear screen composites (`flowStrength`/`symmetry`/`fieldDecay`,
  §6.2's own note, `patchbay/screen-composites.ts`) were deliberately left exactly as they were
  — hand-written formulas reading `resolved[...]` values.** They still work unmodified: nothing
  about what produces `resolved` changed their contract. Reimplementing their spring/damper +
  edge-triggered-impulse dynamics as generic graph nodes was considered and explicitly **not**
  done — no browser access this session to visually re-verify a from-scratch reimplementation of
  load-bearing, hand-tuned-over-many-sessions motion math, and the equivalence-test approach
  above only proves numeric parity for the graph-expressible routing portion, not for a rewrite
  of stateful spring/impulse code with no existing test oracle to compare against. Revisit if
  there's ever a concrete reason these three specifically need to be user-routable.
- **A real target-range-clamping gap was found and fixed as part of this work**:
  `PatchGraphEvaluator`'s `target` node case had never clamped to the target's declared `range`
  at all (unlike `Patchbay.resolve()`, which always did) — a latent §5.3-adjacent safety gap for
  *both* screen and fixture targets, not something introduced by this migration. Fixed in
  `PatchGraphEvaluator.evaluate()` using the `targets` list already passed to its constructor.
- **The dev-only patchbay editor tool** (`tools/patchbay-editor/`) now authors ONE unified
  `DraftNode[]` graph seeded from both `screen-graph.ts`'s default and the fixture demo chains,
  against a merged target catalog (`SCREEN_TARGETS` ∪ the live fixture catalog) — a target node
  can point at either domain side by side in the same canvas, which is the concrete form of
  "shared behavior, one signal driving both a screen effect and a servo." Sent to the live
  render worker only after pruning to the screen-relevant subgraph
  (`patchgraph/prune.ts`'s `pruneGraphToTargets`) — the worker still has no idea a fixture half
  of the authored graph exists, same separation-of-concerns §6.1's `VizOutput` interface always
  implied. The old flat route-table UI (`RouteTable.tsx`, `patchbay/editor/patch-document.ts`)
  is deleted, not deprecated — superseded outright by the visual node canvas
  (`PatchGraphCanvas.tsx`), which also gained descriptive, renameable node labels (separate from
  each node's stable wiring `id`) and an autocomplete "find a node" search box, addressing the
  earlier `n1, n2, ...` naming complaint.
- **Not yet verified in an actual browser** — no browser access this session, same standing
  caveat as several earlier sessions' GL/layout work in `AGENTS.md`. Everything above is
  verified by typecheck, the full test suite, and direct HTTP inspection of the dev server's
  Vite-transformed module output (no compile/transform errors) — not by an eyes-on check that
  the live screen actually still looks the same. Do that check before treating this migration as
  fully proven, especially given how much of `AGENTS.md`'s change history is screen-visual
  tuning that could only ever be validated by looking at it.

---

## 7. Two run modes (venue requirement, unchanged by this refactor)

Both already fall out of the existing input layer; this refactor must not break them:
- **Live** (opening party): mic/line-in → Layer 1/2 → conductor → bus → ScreenOutput.
- **Unattended** (11 days): looped own-tracks + precomputed sidecars (best look, look-ahead
  anticipation via `StructureSource`) or ambient mic. Must auto-start, survive a crash, need no
  keyboard. This is most of the exhibition's runtime — treat as first-class. (Auto-start/
  crash-recovery is a *host*/IO-page concern, not this package — note it here so it isn't
  forgotten, but it's out of this repo's scope per `SINTEZA_VIZ.md` §10.)

---

## 8. Explicitly LATER (not this spec)

In dependency order, after the screen piece looks good:
1. ServoOutput implementation + serial/GPIO transport + safety (rate-limit, thermal,
   graceful-fail, unattended recovery).
2. Physical target declarations tuned against real hardware (the 5 test units → the full set).
3. Projection-onto-moving-mirrors coupling design.
4. **Patchbay editor UI** — a node/patchbay visual editor over the §5 data model, plus a live
   signal-meter view for tuning against real audio. Cheap *because* §5 is already declarative
   data; building it before the screen piece is good is the scope-creep tell.

Do not start any of §8 as part of implementing §1–§6.

---

## 9. Build order (for the implementing agent)

1. **Mechanical split, behavior-preserving.** Introduce `VizOutput`, the bus type (§3.1),
   the patchbay (§5), and a default `screen-only` config that reproduces today's
   `Choreographer`→`ParamBus`→`Scene` mapping *exactly*. Rename `Choreographer`→conductor,
   emit the bus. Wrap the render pipeline as `ScreenOutput`. **Existing `tests/unit` pass;
   screen looks identical.** Commit here.
2. **Widen the bus** with the full §3.1 signal set (bands, `bandTilt`, `beatPulse`,
   `downbeatPulse`, `onsetImpulse`, etc.), still with default routing that ignores the new
   ones — screen still looks identical. Commit.
3. **Groove reactivity** (§4.1): add patchbay routes so bands→flow direction,
   `beatPulse`→field throb, `barPhase`→slow breathing. Verify §4.1's detector-disable
   acceptance test. Commit.
4. **`familiarity`** (§4.2): implement the online self-similarity signal; route it to
   organization/symmetry. Commit.
5. **Perceptual memory contrast:** widen the groove/build/break decay separation so "the image
   remembers" reads unmistakably, especially the break-holds-the-ghost moment
   (`SINTEZA_VIZ.md` §0/§4b). Tune by feel in the dev harness. Commit.
6. Add unit coverage for the patchbay evaluator and the timescale-tag validation (deterministic,
   CI-friendly, matching the existing test style).

Each step is independently shippable and leaves the screen piece working. If time runs out at
any commit, what's shipped is still a strict improvement over today.

---

## 10. Definition of done (this spec)

- R1–R5 hold (R1 grepped, R4/R5 demonstrated by rerouting a signal via config only).
- Detector-disable acceptance test (§4.1) passes.
- `familiarity` exists, is continuous, and drives organization.
- Break/groove memory contrast is perceptually obvious.
- Existing tests pass; new patchbay/validation tests added.
- ServoOutput is specified (§6.3) but NOT implemented; adding it later requires no upstream
  edit — verifiable by the fact that its target declaration already validates against the
  patchbay.
- No editor UI, no servo code, no device manager built.
