# СИНТЕЗА visualizer — directions (v3)

Repo: `sinteza-viz` (standalone package, consumed by `stcksmsh.github.io`)
Status: implementation in progress. Supersedes the v2 `HYSTERESIS.md` directions doc — v2's
package API, three-layer audio pipeline, and Julia+beam scene are the foundation this v3 doc
builds on (§4b/§4d are net-new; the rest resolves/extends v2).

**Naming.** This is *the СИНТЕЗА visualizer* — the signature audio-reactive surface of the
СИНТЕЗА design system, not a separately-branded product. It inherits the design system's name
as a descriptor. It has no competing title. **HYSTERESIS is demoted from product name to the
internal technical principle** driving the core layer (§4b): a system whose visible output
depends on its whole history, not just the current input. That principle is the whole idea.

This doc covers **only** the visualizer. The host site (single-page shell, audio hosting,
player, sidecar serving) is a separate repo/spec (`IO_PAGE_CHANGESET.md`). The seam between
them is §7 (The interface).

---

## 0. The thesis (what makes this "wow", "new", and "yours")

Almost every audio visualizer is **memoryless**: this frame reacts to this instant, then
forgets. The СИНТЕЗА visualizer is built on the opposite principle — **the image itself
accumulates history.** A feedback field continuously smears, flows, and decays past states into
the present, so the screen is a slowly-evolving *record of the last few seconds of the song*,
not a snapshot. That is rare in the wild and it is literally the hysteresis principle rendered
as an image.

The emotional arc this produces maps exactly onto electronic music structure, and it is the
spine of all choreography:

**MEMORY → PROCESSING → RESOLUTION**
- the field *accumulates* (memory: energy loads into the feedback buffer over a build),
- the flow *reorganizes* what it holds (processing: domain-warp churns and densifies),
- an event *resolves* it into a single gesture (resolution: the drop discharges the field).

Maximalism is on-brand and welcome, but it is **earned by the memory**, not piled on: the field
gets denser and more active *because it is remembering harder*, and the drop resolves it. Maximal
*because* it remembers — never maximal *and also* busy. If a visual element isn't wired to the
memory/energy/event state, it doesn't ship.

---

## 1. Package shape

Framework-agnostic package the host mounts once. The actual shipped API
(`src/index.ts`) is `VizOpts`/`VizInstance`, matching the IO page's real integration contract —
polled `getAudioContext`/`getAnalyser`, transport on a `window` `"player:transport"`
`CustomEvent` bus, not the constructor-injected shape this doc originally sketched. See
`README.md` for the real signature.

No DOM ownership beyond the canvas. No routing, no player, no knowledge of the site.

---

## 2. Layer 1 — feature extraction ("the ear")

Runs in an **AudioWorklet** on the audio thread, downstream of the host's source node.

- Windowed FFT (Hann), own implementation (fft.js / KissFFT-WASM) or the shared `AnalyserNode`
  for the cheap path.
- Perceptual band split: sub / bass / low-mid / mid / high-mid / air.
- Spectral flux onset detection (per-band + broadband).
- Spectral centroid, spectral flatness (tonal vs noisy) — flatness matters for §4d symmetry.
- RMS / short-term energy.
- Ring-buffer raw samples for the oscilloscope beam, trigger-locked to a zero-crossing so the
  waveform sits still.
- `postMessage` a compact **state object** (NOT raw audio) to the render side each frame.

## 3. Layer 2 — musical state estimation ("the sense")

- Beat tracking → `tempo`, `beatPhase`, `barPhase`.
- `buildProgress` — integrated 0→1, loads over a build (drives field density + fold count).
- `tension` — integrated; centroid climb + onset density + sub behavior.
- Drop detection — discrete event (the resolution gesture).
- Break detection — sub collapse + onsets stop; the field goes sparse and *holds its memory*
  (decay slows, so the trace of the last drop lingers into the silence — this is the payoff of
  a memory field, silence still shows history).
- Per-frame state object:
  `{ tempo, beatPhase, barPhase, buildProgress, tension, energy, bands[], centroid,
     flatness, events:[{type,strength,t}] }`
- Fused with the precomputed sidecar (§5): structure prefers sidecar, detail always live.

## 3a. Layer 3 — choreography ("the body") — reads STATE, never samples

Choreography follows MEMORY → PROCESSING → RESOLUTION:
- **Groove** → field in low-decay equilibrium, gently pulsing on the beat; warp gentle,
  asymmetric.
- **Build** → decay factor drops (field *remembers harder*), warp strength + fold count climb
  with `buildProgress`; the frame visibly densifies. This is "processing."
- **Drop** → **resolution**: discharge the accumulated field in one gesture — palette flip +
  `c`-jump + a symmetry snap for one bar + a shockwave through the flow field.
- **Break** → decay slows further, warp stills; the last drop's trace hangs suspended. Contrast
  on return does the emotional work.
- Connective tissue: **spring-damper drivers + envelope followers on every animated parameter.**
  Overshoot on a kick *is* the punch.

---

## 4. Visual composition (RESOLVED) — three layers, one flow field

Three layers occupying different *bands of the image* the way instruments occupy bands of a mix,
so they read clearly instead of turning to soup. Slow/large carries mood, sharp/thin carries
rhythm. **One shared curl-noise flow field ties them together** — it is what makes the mix feel
like a single organism, not stacked demos.

(A fourth, granular layer — onset particles, sparks dragged by the same flow field — shipped in
v3 and was deliberately removed afterward: the disliked failure mode was less "no transient layer
at all" and more "particles visibly erupting from the fractal shape specifically", which read as
distracting rather than as a texture of the mix. If a transient layer comes back, it should not
spawn from positions that visually read as tied to the substrate's own shape.)

Rendered in СИНТЕЗА: violet-black `#0A0912` substrate, vermilion `#FF5C38` accent (host may
retint via `setAccent`).

### 4a. Julia substrate — mood (slow, large)
- 2D escape-time Julia set, single fragment shader (cheap, no raymarching — runs behind every
  page forever). Ships as a XaoS-style continuous autopilot: `c` sweeps the Mandelbrot main
  cardioid's boundary (always structurally rich, never a flat region) while a distance-estimator
  autopilot pans/zooms toward genuine detail — see `JuliaScene.ts`.
- `c`'s sweep rate and the autopilot's zoom rate are driven by energy/tension (spring-damper
  chased, with overshoot on events) rather than a hand-picked constant.
- Idle: the same continuous autopilot keeps running — stationary dynamics, ties to the beam
  lineage. The field is never dead.
- Low-contrast, violet-biased coloring so body text stays readable (host also scrims reading
  routes).

### 4b. Feedback / memory field — THE signature layer (the thesis, made visible)
- Ping-pong buffer: each tick the **whole frame is fed back**, advected through a shared
  curl-noise flow field, and decayed by a factor tied to `tension`/section.
- This is "the image accumulates history." Past states smear and flow into the present; the
  screen becomes a record of the last few seconds. **This is what nothing else looks like.**
- Cheap (one extra pass, reusing the baked curl-potential noise texture already in
  `gl/noise-texture.ts`). Decay is a driven parameter: short memory (fast decay) in groove
  equilibrium, long memory (slow decay, field densifies) in a build, slowed further so the trace
  lingers through a break.
- The Julia substrate (+ beam) is *fed into* this buffer, not drawn separately on top — so the
  fractal itself is what's being remembered and smeared.

### 4c. Oscilloscope beam — rhythm (sharp, thin)
- Single Woscope-style glowing vector beam (segment-as-quad + distance-to-segment falloff),
  drawn together with the Julia substrate each frame, so it also gets remembered/smeared
  underneath as it moves — its own trail is consistent with the field's motion.
- Idle: slow Lissajous. Playing: trigger-locked real-time XY/waveform trace.

### Earned symmetry (modulates 4b's warp — never a constant filter)
- Symmetry is **always a response, never a constant kaleidoscope.** Fold-count and mirror-
  strength are driven parameters, applied to the flow field's domain (domain warp) — specifically
  to the *sampling coordinate the memory field reads its own previous frame through* — NOT
  slapped on the final composited frame.
- Rises with `tension`/`buildProgress`; **snaps to full symmetry for roughly one bar on a drop**,
  then releases. May also briefly bloom on a sustained tonal passage (high spectral flatness →
  the field "wants to organize"). It can happen anywhere — but it always *means* something
  spiked. When nothing is happening, the field is asymmetric and organic.
- Tiling, if used at all, is **domain warp** (music-driven distortion of space, tiles-but-never-
  exactly-repeats), never literal repeat — the difference between generative and wallpaper.

### Render path
1. Julia substrate + beam → offscreen FBO (`JuliaScene`, unchanged from v2)
2. composite into feedback buffer + advect through curl-noise flow field + decay (ping-pong)
   — with earned-symmetry domain warp applied to the advection sampling coordinate
3. bloom — multi-pass gaussian on a downsampled buffer
4. composite + color grade to screen
- WebGL2 primary; render on a Worker via `OffscreenCanvas` where supported (main-thread
  fallback). WebGPU a later optional branch (needs WebGL2 path regardless).

### Optional — Mandelbulb hero (landing view only)
- Raymarched Mandelbulb as a foreground hero on the landing view **only** — never the persistent
  background (raymarching always-on melts low-end GPUs / drains phone batteries). Registered in
  `scenes/registry.ts` as `mandelbulb-hero`; does not participate in the memory field.
- Reduced march steps, paused when off-screen (IntersectionObserver), skipped on `cheap`/
  `idle-only`.

---

## 5. Live + precomputed fusion

Live analysis can't look ahead; offline can. Fusion has two distinct modes depending on whether
the host has a real `AnalyserNode` to attach to at all:

**Self-hosted audio (live + precomputed fusion, `StructureSource.fuse()`):**
- **Structure from the sidecar:** beats, sections, build/drop/break markers, energy envelope —
  precomputed offline, frame-accurately synced to the host's `position` feed. Look-ahead lets
  the feedback field *start densifying before* a drop it can see coming — anticipation, which is
  what makes it feel like the music rather than a meter.
- **Detail from the live signal:** band envelopes, beam — live.
- **Fusion rule:** sidecar loaded → structural gestures fire from the timeline; otherwise fall
  back to live Layer 2 detection. Detail is live either way.

**SoundCloud / position-only mode (no live audio at all, `StructureSource.synthesize()`):** a
cross-origin embed (SoundCloud, Bandcamp) has no `AnalyserNode` to tap — the iframe's audio is
unreachable. But the *master* isn't: if the track is your own, `scripts/analyze.ts` runs against
the original WAV and the schema-2 sidecar carries enough (per-band/centroid/flatness envelopes,
a synthetic-but-real onset list) to drive the whole visual purely from playback **position** —
`init()` never attaches a Worklet for these tracks at all, it just posts `setPosition` from the
host's own position feed (e.g. the SoundCloud Widget API's `PLAY_PROGRESS`) and everything reads
off the sidecar. The one thing that can't be recovered offline is the oscilloscope beam's real
waveform (no phase information survives an FFT envelope) — the beam plays its idle Lissajous
figure instead of a fake trace; every other layer (Julia, memory field, symmetry) reacts to the
genuine track structure. If live audio *does* attach later (e.g. tier/host changes
mid-session), it takes over for good — the two modes are mutually exclusive per track, never
both at once.

---

## 6. Offline analysis tool (produces the sidecar) — lives in THIS repo

- `scripts/analyze.ts` (Node): ingests a WAV master, emits `<slug>.sidecar.json` (schema 2):
  `{ schema:2, tempo, beats[], sections[], events[], onsets[], energyEnvelope[], bandEnvelope,
  centroidEnvelope[], flatnessEnvelope[], envelopeRate }`. `bandEnvelope`/`centroidEnvelope`/
  `flatnessEnvelope`/`onsets` exist specifically to make §5's position-only mode possible — a
  schema-1 sidecar (structure only) can't drive a track with no live audio at all.
- Same Layer 1/2 logic offline, with look-ahead + optional hand-correction pass.
- **Output is consumed by the IO page** as a static asset (`public/audio/<slug>.sidecar.json`).
  This repo *produces* it; the IO page *serves* it. Only artifact crossing the boundary besides
  the runtime package. Schema versioned so the repos evolve independently.

---

## 7. THE INTERFACE (contract with the IO page)

Mirrors §6 of `IO_PAGE_CHANGESET.md`. Host provides, this repo consumes:
1. **Mount:** `init(canvas, opts)` once; never destroyed during nav.
2. **Audio tap:** polled `getAudioContext()`/`getAnalyser()` — null until the host's shared bus
   exists (first play click); attach the Worklet downstream of the analyser once they resolve.
3. **Transport:** a `window` `"player:transport"` `CustomEvent` bus — `play`/`pause`/`seek`/
   `trackchange`/high-frequency `position`, not pushed through the returned handle.
4. **Sidecar:** `trackchange`'s `track.envelope` URL, fetched and parsed internally.
5. **Accent:** `setAccent([l, c, h])` — OKLCH, converted to linear sRGB internally.
6. **Power tier:** `setTier('full'|'cheap'|'idle-only')`; this repo implements each.

Analysis and rendering are internal and invisible to the host.

---

## 8. Idle state & power tiers (non-negotiable background-mode requirements)

- **Idle must be alive:** no audio → the Julia autopilot keeps running, the beam draws a slow
  Lissajous, the feedback field keeps flowing/decaying gently. Never frozen or dead (except under
  reduced-motion, where the host freezes it).
- **Tiers:**
  - `full` — all three layers + earned symmetry + bloom + (landing) Mandelbulb, OffscreenCanvas.
  - `cheap` — Julia + feedback field + beam, reduced FFT, no Mandelbulb, lighter bloom, capped
    DPR/FPS.
  - `idle-only` — Julia autopilot + gentle feedback + beam Lissajous, no live analysis attach.
- Respect `prefers-reduced-motion` — host disables the canvas; package must also no-op cleanly.
- Cap device pixel ratio, target 60fps with graceful degradation; the background must never make
  the site feel heavy.

---

## 9. Build order (visualizer)

1. ~~WebGL2 boilerplate + Julia substrate shader~~ — done (v2).
2. ~~Idle drift + beam Lissajous over the field~~ — done (v2), the autopilot's own idle path.
3. ~~Attach Layer 1 Worklet + Layer 2 state; drive `c` and beam live~~ — done (v2).
4. ~~Spring-damper drivers everywhere~~ — done (v2, `Choreographer`).
5. **Feedback/memory field ping-pong + curl-noise advection** — the signature layer, tuned by
   hand (decay + warp) until the "remembering" look is right. This was the make-or-break step
   for v3.
6. ~~Onset particles dragged by the shared flow field~~ — built for v3, then deliberately removed
   (see §4's note) once live, particles visibly erupting from the fractal shape read as
   distracting rather than as a texture of the mix.
7. Earned-symmetry domain warp (fold count / snap / flatness bloom).
8. ~~`scripts/analyze.ts` + sidecar schema; live+precomputed fusion~~ — done (v2).
9. Bloom + color-grade polish; OffscreenCanvas worker + fallback — done (v2).
10. Power tiers + reduced-motion; optional Mandelbulb landing hero — done (v2).

---

## 10. Explicitly out of scope for this repo
- The single-page shell, routing, focus/scroll (→ IO page).
- Audio hosting, encoding, player UI, `AudioContext` creation (→ IO page).
- Serving sidecar / track manifest (→ IO page).
- СИНТЕЗА readability scrims on reading routes (→ IO page).
