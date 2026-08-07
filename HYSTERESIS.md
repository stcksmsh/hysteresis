# HYSTERESIS — Visualizer (v2 directions)

Repo: `hysteresis` (standalone package, consumed by `kostavukicevic.github.io`)
Status: revised directions for an ultraplan/Claude Code session. Supersedes the original
HYSTERESIS directions doc — the `[DECIDE]` on visual metaphor is now **resolved** (§4), and the
runtime model is corrected for the self-hosted / curated-audio reality.

The name still earns itself: a system whose output depends on its whole history, not just the
current input. That is the thesis — reads musical *state and events*, winds up on builds,
releases on drops, and carries memory in the field itself.

This doc covers **only** the visualizer. The host site (single-page shell, audio hosting,
player, sidecar serving) is a separate repo/spec (`IO_PAGE_CHANGESET.md`). The seam between
them is §7 (The interface) and matches §6 of the IO-page doc exactly.

---

## 0. What changed from the original directions

- **Audio is same-origin and fully analysable.** Only Kosta's own curated tracks ever play,
  self-hosted by the host site. So the `AnalyserNode`/AudioWorklet can read everything — the
  original three-layer live pipeline is intact, no cross-origin workaround needed.
- **Visual metaphor resolved:** animated **Julia-set substrate** (background) + **oscilloscope
  beam** and an optional **Mandelbulb hero** (foreground). See §4.
- **Live + precomputed fusion:** live FFT drives fast per-frame detail; a precomputed per-track
  sidecar drives reliable structure (beats, drops, sections). See §5. The offline tool that
  produces the sidecar lives in THIS repo (§6).
- **Runs as a persistent background** inside a single-page shell — must have a real idle state
  and cheap power tiers (§8).

---

## 1. Package shape

Ship as a framework-agnostic package the host mounts once:

```
init(canvas: HTMLCanvasElement, opts: {
  analyser: AnalyserNode,          // shared, from host
  audioContext: AudioContext,      // shared, from host
  source?: AudioNode,              // to attach own Worklet downstream
}): HysteresisHandle

interface HysteresisHandle {
  resize(): void;
  setTransport(evt): void;         // play | pause | seek | trackchange
  setPosition(seconds: number): void;
  loadSidecar(url: string): Promise<void>;
  setAccent(cssColor: string): void;
  setTier('full' | 'cheap' | 'idle-only'): void;
  destroy(): void;                 // host will basically never call this
}
```

No DOM ownership beyond the canvas. No routing, no player, no knowledge of the site.

---

## 2. Layer 1 — feature extraction ("the ear")

Runs in an **AudioWorklet** on the audio thread, downstream of the host's source node.

- Windowed FFT (Hann), own implementation (fft.js / KissFFT-WASM) or the shared `AnalyserNode`
  for the cheap path.
- Perceptual band split: sub / bass / low-mid / mid / high-mid / air.
- Spectral flux onset detection (per-band + broadband).
- Spectral centroid, spectral flatness (tonal vs noisy).
- RMS / short-term energy.
- Ring-buffer raw samples for the oscilloscope beam (trigger-locked to a zero-crossing so the
  waveform sits still — see §4 beam).
- `postMessage` a **compact state object** (NOT raw audio) to the render side each frame.

## 3. Layer 2 — musical state estimation ("the sense")

- Beat tracking → `tempo`, `beatPhase`, `barPhase`.
- `buildProgress` — integrated 0→1 parameter that loads over a build.
- `tension` — integrated, reads centroid climb + onset density + sub behavior.
- Drop detection — discrete event (sub returns + broadband onset spike after a build).
- Break/tension detection — sub collapse + onsets stop; the visual feels the *absence*.
- Per-frame state object:
  `{ tempo, beatPhase, barPhase, buildProgress, tension, energy, bands[], centroid,
     flatness, events:[{type,strength,t}] }`
- **Live values are fused with the precomputed sidecar (§5):** structure (beats/drops/sections)
  prefers the sidecar when a track is recognized; detail (bands/onsets/energy) always live.

## 3a. Layer 3 — choreography ("the body") — reads STATE, never samples

- **Groove** → field in equilibrium, gently pulsing on the tracked beat.
- **Build** → whole system winds up; `tension`/`buildProgress` visibly load energy.
- **Drop** → release stored tension in one gesture (palette flip / `c`-jump / shockwave).
- **Break** → decay to a held, spacious state; contrast does the emotional work on return.
- Connective tissue: **spring-damper drivers + envelope followers on every animated parameter.**
  The overshoot on a kick *is* the punch. This is what makes it feel alive vs twitchy.

---

## 4. Visual metaphor (RESOLVED)

Two layers. Mood underneath, rhythm on top. Rendered in СИНТЕЗА: violet-black `#0A0912`
substrate, vermilion `#FF5C38` beam/onset accent (host may retint via `setAccent`).

### 4a. Substrate — animated Julia set (background)

- 2D escape-time Julia set in a single fragment shader. **Cheap** (one pass, no raymarching) —
  this is why it can run behind every page forever.
- The Julia constant `c` (a single complex number) is the primary audio-driven parameter:
  walking `c` around the complex plane continuously morphs the entire fractal.
  - `c` target ← Layer 2 state (energy / tension / buildProgress), chased by a spring-damper so
    it moves musically, with overshoot on events.
  - **Idle state (nothing playing):** `c` drifts slowly along a Lissajous path — this is the
    stationary dynamics, and it ties back to the oscilloscope lineage. The field is never dead.
  - Drop event → discrete `c`-jump + palette flip.
- Coloring: smooth iteration count → palette; keep it low-contrast and violet-biased so body
  text stays readable over it (the host also scrims reading routes).
- Persistence/feedback pass optional (adds memory/trails), but the Julia field already carries
  visual state frame-to-frame via `c`; keep it subtle.

### 4b. Foreground — oscilloscope beam

- A single Woscope-style glowing vector beam (segment-as-quad + distance-to-segment falloff
  shader) rides on top of the Julia field.
- **Idle:** slow Lissajous figure (the existing idle mode, same `c`-drift energy).
- **Playing:** real-time XY / waveform trace from the trigger-locked sample ring buffer.
- This is the sharp, legible, "designed" element carrying beat and gesture; the Julia field
  carries mood and memory underneath.

### 4c. Optional — Mandelbulb hero (landing view only)

- Raymarched distance-estimated Mandelbulb as a **foreground hero on the landing view only** —
  NOT the persistent background (raymarching is far too expensive to run always-on and would
  melt low-end machines / drain phone batteries).
- Reduced march steps, **paused when off-screen** (IntersectionObserver), and skipped entirely
  on `cheap` / `idle-only` tiers. Its rotation/detail can read the same Layer 2 state.
- Treat as a nice-to-have; the Julia+beam pair is the core and ships first.

### Render path

1. scene pass — Julia field → offscreen FBO
2. beam pass — oscilloscope segments → additive onto scene
3. (optional) persistence/feedback — sample prev frame × decay, additive
4. bloom — multi-pass gaussian on a downsampled buffer
5. composite + color grade to screen
- WebGL2 primary. Render on a Worker via `OffscreenCanvas` where supported (biggest perceived-
  quality win) — with a main-thread fallback. WebGPU is a later optional branch, needs the
  WebGL2 path regardless.

---

## 5. Live + precomputed fusion

Live analysis is fully available, but it is *bad at look-ahead*: beat tracking and especially
build/drop/break detection are far more reliable offline (you can see the whole signal and
hand-correct a late drop marker). So:

- **Structure from the sidecar:** beats, section boundaries, build/drop/break markers, energy
  envelope — precomputed offline, frame-accurately synced to the host's `position` feed.
- **Detail from the live signal:** band envelopes, the oscilloscope beam, onset sparkle — always
  live, per-frame.
- **Fusion rule:** if the current track has a sidecar loaded (host called `loadSidecar` on
  `trackchange`), structural gestures fire from the timeline; otherwise fall back to live
  Layer 2 detection. Detail is live either way.
- Sync: on each `setPosition(seconds)`, look up the sidecar timeline; schedule upcoming
  structural events relative to the live clock so drops land frame-accurate, not 200ms late.

---

## 6. Offline analysis tool (produces the sidecar) — lives in THIS repo

- A `scripts/analyze.ts` (Node) that ingests a WAV master and emits
  `<slug>.sidecar.json`: `{ tempo, beats[], sections[], events:[{type,t,strength}],
  energyEnvelope[] }`.
- Runs the same Layer 1/2 logic offline with look-ahead + optional hand-correction pass.
- **Output is consumed by the IO page** as a static asset (`public/audio/<slug>.sidecar.json`).
  This repo *produces* it; the IO page *serves* it. That is the only artifact that crosses the
  repo boundary besides the runtime package.
- Keep the sidecar schema versioned (`"schema": 1`) so the two repos can evolve independently.

---

## 7. THE INTERFACE (contract with the IO page)

Mirrors §6 of `IO_PAGE_CHANGESET.md`. The host provides, this repo consumes:

1. **Mount:** host calls `init(canvas, { analyser, audioContext, source })` once; never
   destroys during navigation.
2. **Audio tap:** shared `AudioContext` + `AnalyserNode` from the host; attach the Worklet
   downstream of `source`. One context, no duplication.
3. **Transport:** `setTransport(play|pause|seek|trackchange)` + high-frequency `setPosition`.
4. **Sidecar:** host calls `loadSidecar(url)` on `trackchange`; this repo fetches + parses.
   (The file was produced by this repo's §6 tool, checked into the host as a static asset.)
5. **Accent:** `setAccent(cssColor)` forwards the host's current `--accent` for tint.
6. **Power tier:** `setTier('full'|'cheap'|'idle-only')` — this repo implements what each renders.

Everything about analysis and rendering is internal and invisible to the host.

---

## 8. Idle state & power tiers (non-negotiable, background-mode requirements)

- **Idle must be alive:** with no audio, `c` drifts on a Lissajous, beam draws a slow Lissajous.
  Never a frozen or dead screen (except under reduced-motion, where the host freezes it).
- **Tiers:**
  - `full` — Julia + beam + bloom + (landing) Mandelbulb hero, OffscreenCanvas worker.
  - `cheap` — Julia + beam, reduced FFT size, no Mandelbulb, lighter bloom, capped DPR/FPS.
  - `idle-only` — Julia `c`-drift + beam Lissajous, no live analysis attach (for low-power /
    battery-saver / coarse-pointer as decided by the host).
- Respect `prefers-reduced-motion` — the host disables the canvas, but the package must also
  no-op cleanly if told to.
- Cap device pixel ratio and target 60fps with graceful degradation; the background must never
  make the site feel heavy.

---

## 9. Build order (visualizer)

1. WebGL2 boilerplate + the Julia substrate shader with `c` on a manual slider — get the field
   looking right in СИНТЕЗА first, no audio.
2. Idle `c`-drift Lissajous path — prove the stationary dynamics.
3. Oscilloscope beam pass (Woscope segment shader) over the field; idle Lissajous beam.
4. Attach Layer 1 AudioWorklet + Layer 2 state; drive `c` and beam live from the host analyser.
5. Spring-damper drivers on every animated parameter; tune drop/build/break feel.
6. `scripts/analyze.ts` offline tool + sidecar schema; wire live+precomputed fusion.
7. Bloom + persistence polish; OffscreenCanvas worker + main-thread fallback.
8. Power tiers + reduced-motion; optional Mandelbulb hero on landing.

---

## 10. Explicitly out of scope for this repo

- The single-page shell, routing, focus/scroll handling (→ IO page).
- Audio hosting, encoding, the player UI, the `AudioContext` creation (→ IO page; this repo
  receives the context + analyser).
- Serving the sidecar / track manifest (→ IO page; this repo only produces the sidecar offline).
- СИНТЕЗА readability scrims on reading routes (→ IO page).
