# hyst-render

`wgpu` renderer for the Rust rewrite (R2, `SINTEZA_IMPLEMENTATION_PLAN.md` §4). Parses `.hyst`
(ISF-superset) documents, translates ISF-flavored GLSL to real GLSL `wgpu` can compile, and runs
the Julia-substrate + memory-field + persistence + bloom + composite + beam frame loop the plan's
R2 done-when names.

## Module map

- `gpu.rs` — `GpuContext` (instance/adapter/device/queue, headless) and `OffscreenTarget`
  (render-to-texture + readback). `OffscreenTarget::render_glsl_fragment_shader` is the shared
  fullscreen-pass driver every pass below uses.
- `hyst_format/` — the `.hyst` parser (JSON header + GLSL body). Complete, tested against the TS
  original's own fixture set; untouched this session except as a translation *input*.
- `isf_translate.rs` — ISF-flavored GLSL (`isf_FragNormCoord`, `TIME`, `RENDERSIZE`, `gl_FragColor`,
  `texture2D`) → real GLSL `wgpu`'s `naga` GLSL frontend accepts. See its module doc for why this
  emits GLSL 450 core (Vulkan-flavored), not GLSL ES 300 like the TS original's translator — `naga`
  only understands the former.
- `passes/` — `julia.rs` (substrate), `mandelbulb.rs` (raymarched 3D alternative substrate, not yet
  wired into the frame loop — see below), `memory_field.rs` (feedback field, fold/advect), `bloom.rs`
  (bright-pass + blur), `persistence.rs`, `composite.rs`, `beam.rs` (instanced-quad line raster),
  `noise_texture.rs` (baked curl-noise potential). `mod.rs` holds the shared `CommonUniforms`/
  `pack_slots` uniform-packing helpers every pass uses.
- `renderer.rs` — `Renderer`/`FrameParams`: owns every pass's buffers, wires them into the one
  frame loop (Julia → memory field ping-pong → persistence → bloom → composite → beam on top).

## Verifying this crate still works

```
cargo test -p hyst-render          # 44 tests, all against a real GPU adapter (skip if none found)
cargo clippy -p hyst-render --all-targets -- -D warnings
cargo run -p hyst-render --example audio_driven_render   # real-audio-driven render + mp4 (needs ffmpeg on PATH)
```

Every GPU test does the real thing (renders, reads pixels back, asserts something specific about
their values) — see each pass module's own test for what it actually checks (fold symmetry,
feedback accumulation/determinism, beam rasterization bounds, etc.), not just "didn't panic." Tests
degrade gracefully (skip, don't fail) if no GPU adapter is available in the environment.

## Mandelbulb (raymarched 3D substrate, standalone)

The browser build shipped only the 2D Julia set — WebGL2 could just barely afford a raymarched
3D Mandelbulb as an optional, non-persistent landing-hero shot
(`src/render/worker/scenes/mandelbulb/MandelbulbScene.ts` + `shaders/mandelbulb.frag.glsl` in the
frozen TS reference, never wired into the default persistent-background registry). This native
`wgpu` rewrite has real GPU raymarching headroom the WebGL2-constrained original didn't, so
`passes/mandelbulb.rs` ports that shelved experiment's actual technique — the power-8
distance-estimated (DE) spherical iteration and sphere-tracing raymarch loop — as a second fractal
substrate alongside the Julia set.

**Visual-quality pass (this session)**: the first version's shading was a faithful port of the
original's deliberately minimal flat depth/glow tint (no gradient/normal information at all), and
user feedback against a real rendered clip was blunt: "too low-res, jittery... looks like a 3D
print... doesn't zoom in at all." Landed in response:

- **Real surface normals + Lambertian diffuse lighting.** `estimateNormal` in the shader does the
  standard central-difference trick (sample the DE at `hit ± ~0.0009` along each axis, normalize
  the gradient), lit by a fixed world-space light direction (`dot(normal, lightDir)`, clamped, plus
  an ~0.18 ambient floor) — this is the main fix for "looks like a 3D print": the original had zero
  gradient-based shading cues, so every hit read as a flat depth-tinted disc regardless of its real
  surface orientation.
- **A cheap ambient-occlusion approximation** (`ambientOcclusion`: 5 short steps out along the
  normal, comparing actual DE value to expected free-space distance) darkens the crevices between
  filaments/lobes — a real, if approximate, extra depth cue on top of the diffuse term.
- **9x (3x3) supersampling** — a single sample per pixel visibly aliased/shimmered on the power-8
  fractal's high-frequency boundary detail, even holding the camera still. 2x2 was tried first and
  only partially helped; 3x3 was the point where a wide-view static/slow-moving frame's
  frame-to-frame diff (measured as % of RGBA bytes changing by more than 10 out of 255 between
  adjacent rendered frames) dropped to single digits.
- **A real, honestly-measured jitter finding, not a guess**: the raymarch itself is fully
  deterministic (bit-identical output re-rendering the same `MandelbulbNavState` twice, confirmed
  directly) — raymarch step-precision noise was NOT the jitter source. The real sources found were
  (a) undersampled high-frequency fractal boundary detail (fixed by supersampling above) and (b) a
  real bug in `mandelbulb_render.rs`'s `mandelbulb_state`: it used to set
  `state.distance = 3.2 - 0.9 * bus.energy` unconditionally every frame, which fed the camera
  distance off `bus.energy`'s raw, un-smoothed per-hop value AND silently discarded
  `driven_by_time`'s entire zoom-dive cycle (see below) by overwriting it right after computing it.
  Fixed by exponentially smoothing `bus.energy` and layering it as a small, clamped pull on top of
  the dive distance instead of a hard override.
- **A real, continuous zoom-in dolly.** `MandelbulbNavState::driven_by_time` used to orbit at a
  constant distance; it now breathes the camera smoothly between a wide establishing shot and a
  close distance that reveals real surface detail, on a slow cosine cycle biased to spend more time
  close-in. Deliberately does NOT copy `JuliaNavState::driven_by_time`'s exponential-dive-then-hard-
  reset — a 2D Julia zoom can hide its reset because both ends of the cut are the same flat "void"
  color, but a 3D raymarched camera has no equivalent free reset point, so a hard distance snap
  would be a visible pop with no cover. A smooth cut-free breathing cycle was judged the less
  jarring choice for this geometry (see the method's doc comment for the reasoning).
- **Tightened surface epsilon** (`0.0006`, from `0.0015`) and a **raised step budget** (`220`
  default, from `160`) to resolve thinner filament/spike detail that a coarser sphere-tracing
  threshold was stepping over.
- **The Lissajous beam overlay**, matching the Julia demo: `mandelbulb_render.rs` now calls
  `passes::beam::render_beam` on top of the final frame with its own copy of the
  `lissajous_segments` helper (not shared/refactored — example code, not core crate code).

### Deep-dive + multi-hue palette pass (this session)

User feedback against the breathing-dolly version above was blunt again: "the mandelbulb is bad, we
should zoom in deep... also the palette is very bad and illegible." Two real, honestly-tested
redesigns landed in response:

**1. A real deep dive, driven statefully.** `MandelbulbNavState::driven_by_time` (a pure function of
`t`, kept for tests) and the new `MandelbulbDiveDriver` (a stateful, `dt`-integrated struct —
`update(dt, &SignalBus)`, matching `JuliaDriver`'s own shape in `passes/julia.rs`) both dive the
camera in log-distance space from a wide establishing shot down to `DIST_NEAR=0.75` (from the old
`DIST_NEAR=2.3`), then ease back out, continuously — no snap, verified by a test
(`dive_driver_never_snaps_and_reaches_real_depth`) that fails if any single frame's distance jumps by
more than a small bound. Audio (`bus.energy`/`bus.onset_density`) only ever modulates the *rate*
being integrated into the log-distance accumulator, never the accumulator/phase itself — the same
"never scale a monotonic phase by a non-monotonic audio value" rule this pass's own history already
learned the hard way (see the module doc and `AGENTS.md`'s session history for the original bug).

**Real empirical numbers behind `DIST_NEAR=0.75`** (128x128, release build, this machine — see
`passes/mandelbulb.rs`'s `#[ignore]`d `dive_depth_probe`/`dive_depth_determinism_probe` tests for the
exact harness, and `MandelbulbDiveDriver`'s own doc comment for the full table). Two real findings,
neither assumed going in:
- Diving straight down the camera's -Z axis runs into the fractal's own **solid material**, not more
  fine detail, well before distance reaches zero: below `~0.65` every ray's first sample already
  registers a hit, so the whole frame goes flat/motionless (measured 0.0% frame-to-frame diff — a
  real degenerate wall, not a subjective judgment call). Below `~0.5` the camera has passed into a
  **hollow interior region** where the distance estimator (only a valid bound from *outside* the
  surface) returns bogus values and every ray misses (0.00 hit-rate) — a real, disclosed
  distance-estimation limitation, not a bug in this session's changes. The useful "real surface
  detail, still intersecting the fractal" range along this axis is genuinely `~0.7-1.5`; `0.75` sits
  deep in it (hit-rate 0.93) without reaching the `0.65` wall.
- The elevated frame-to-frame diff numbers in that close range (**44-61%**, well above the old
  dive's own reported ~37.5% worst case) are confirmed **real motion-driven parallax, not noise**: an
  identical, un-rotated state rendered twice at each of these distances came back **bit-identical
  (0.000% diff)** every time. At close range, a tiny camera rotation moves fine surface features
  across far more screen pixels than the same rotation does at a wide shot — a real, disclosed
  property of this geometry, not eliminated by this session's changes.
- Adaptive surface epsilon (`surfaceEps`, scaling with camera distance, clamped to
  `[0.00012, 0.0009]`) and a distance-scaled max-step budget (up to 440 near the closest dive point,
  vs. 220 at the far end) both went in specifically to keep the raymarch itself well-behaved as
  distance shrinks — without them the hit-rate collapse/diff blowup above started noticeably earlier
  (around distance 0.9-0.6 rather than 0.65-0.5).

**2. A real multi-hue palette — with a real, honestly-caught first attempt that didn't work.** The
old shading multiplied one fixed `accent` color by a lighting scalar — every lit pixel was the same
hue at different brightness, which read as "illegible." Replaced with an Inigo-Quilez-style
cosine-gradient palette (`color(t) = a + b*cos(2pi*(c*t+d))`).

The **first attempt** keyed `t` off a real **orbit-trap** value (the minimum `|z|` reached during the
DE iteration at the hit point) — a standard fractal-coloring technique, but rendering and looking at
an actual frame showed most of the visible surface pinned to nearly one color (the iteration escapes
within 1-2 steps for points already near the boundary, so the trap barely moves from `|pos|`), plus
the chosen `a`/`b` let the palette's dark point hit pure black on one channel — together that read as
a near-solid black blob with only a thin colored rim, the opposite of "legible." **Fixed**: `t` now
comes from a **smooth (fractional) escape-iteration count** — the standard Mandelbrot-family coloring
technique, adapted to 3D (`mandelbulbDE` now also returns this via a second `out` parameter) — which
genuinely varies across a real visible surface patch, and `a`/`b` were retuned so the palette's dark
point is a dim color, never black. Both combine with a hue-rotation term driven by
`hyst_core::SignalBus::chroma_root_hue` (via `MandelbulbDiveDriver`, circularly EMA-smoothed the same
way `JuliaDriver::hue_smoothed` already is) — the color now genuinely shifts with the music's harmonic
content, not just brightness-flashing on the beat (`flash` still exists, now as a smaller brightness
multiplier layered on top of the real palette rather than the only color-reactive thing). Verified
with a real test (`dive_driver_hue_tracks_chroma_root_hue_not_just_beat_flash`: two different sustained
`chroma_root_hue` values settle to genuinely different `hue_shift` outputs) and, for the visual
legibility itself, only by actually rendering and looking (see below) — the trap-vs-black-blob problem
was invisible from the code alone.

`MandelbulbNavState` gained `hue_shift`/`flash` fields (replacing the old flat `accent: [f32;3]`);
`examples/mandelbulb_render.rs` now advances a single `MandelbulbDiveDriver` per frame instead of
hand-rolling `mandelbulb_state`/`beat_pulse`/`smoothed_energy` locals — that state (dive depth,
rotation, hue smoothing, beat-flash decay) is now the driver's own responsibility, the same
architecture `JuliaDriver` uses.

Verify it standalone:

```
cargo test -p hyst-render mandelbulb                             # tests, real GPU adapter required
cargo run -p hyst-render --example mandelbulb_render --release   # renders a 90s dive/orbit clip + mp4
```

**Real measured cost this session** (1024x1024, full 90s/2700-frame clip against the real target
track, this machine, release build): **94.5 ms/frame** average render+readback — up from the prior
session's 512x512 number (15.9-17.3 ms/frame there), a real and expected cost: 4x the pixels plus a
max-step budget that's now up to 2x higher near the closest dive point (440 vs. the old flat 220),
plus the extra orbit-trap DE evaluation per hit for palette coloring. Not yet optimized/profiled further — a real, disclosed cost,
not silently absorbed.

Visually confirmed by extracting and looking at real frames across a full rendered clip against the
target track, plus several consecutive frames at a moment of rapidly-changing audio energy (the exact
technique that caught the prior session's phase-warp bug): real fine nested surface detail
increasingly visible as the dive progresses (not just a bigger blurry blob), real multi-hue color
variety across the surface that shifts with the track's harmonic content (not a single flashing
accent), and no snap/jump artifacts anywhere in the dive-and-recede cycle.

**Current limitations**:
- **Not wired into `renderer.rs`'s frame loop** — this is a standalone pass only, not a drop-in
  substitute for `julia.rs` inside `Renderer`. Full integration would need: deciding whether the
  memory-field ping-pong/fold concept (built around a 2D escape-time field) even applies to a 3D
  raymarched scene, or whether Mandelbulb output should instead feed bloom/composite/beam directly
  as a flat color source; and a `FrameParams` variant (or a substrate enum) so `Renderer` can pick
  Julia vs. Mandelbulb per frame. None of that is guessed at here — flagged as the real next step.
- **The dive is a straight-in camera path, not a real "vortex search" toward interesting detail** —
  the empirical wall at `~0.65` (solid material) and floor at `~0.5` (invalid-DE hollow interior) are
  both properties of diving straight down one fixed axis; a real navigation system that steers the
  camera to stay near the boundary as it approaches (the way `JuliaNavState`'s `find_interesting_pan`
  does in 2D) could likely dive meaningfully deeper without hitting either wall — not attempted this
  session, flagged as real follow-up work for R6.
- **44-61% frame-to-frame diff in the closest part of the dive is a disclosed, not-eliminated
  property of this geometry** (confirmed real parallax, not noise — see above), higher than the
  shallower dive's own previously-reported worst case. Real DE/raymarch approximation limits still
  apply too: distance estimation is only a valid bound from outside the surface, so extremely
  thin/high-power features — and any camera position past the surface — can still misbehave.
- **94.5 ms/frame at 1024x1024 is not yet optimized** — a real, measured cost of this session's
  deeper dive and richer shading, not profiled further or reduced.

## GLSL translation approach (why GLSL, not a hand-written GLSL→WGSL AST translator)

`wgpu`'s `naga` dependency has a real GLSL frontend (gated behind the `glsl` Cargo feature, enabled
in this crate's `Cargo.toml`), confirmed by reading `naga::front::glsl`'s own module doc and then
testing directly against this machine's real GPU before committing to the approach — the "strong
recommendation, verify before committing" the R2 brief asked for. That shrunk the job from a full
GLSL→WGSL AST translator to a text-substitution translator (`isf_translate.rs`) plus hand-writing
the internal passes directly in the dialect `naga`'s frontend accepts.

Two real constraints surfaced by that verification, both worked around rather than fought:
- `naga`'s GLSL frontend only understands **Vulkan-flavored GLSL 440-460** (`#version 450 core`),
  not GLSL ES 300/WebGL2 — so this crate's dialect differs from the TS original's
  `translate-isf-glsl.ts` output even though the *approach* (textual substitution of ISF built-ins)
  is the same.
- Vulkan GLSL has **no loose/default uniform block** — `uniform float TIME;` alone is a hard
  compile error (confirmed directly: "uniform/buffer blocks require layout(binding=X)"). Every
  scalar/vector uniform is packed into one `vec4`-per-slot UBO (`Inputs`, binding 1) instead.
- Vulkan GLSL also has **no combined `sampler2D` uniform** declared directly — `uniform sampler2D
  x;` errors "Not implemented: variable qualifier". Every sampled texture is declared as a separate
  `texture2D` + `sampler` pair (2 bindings) and combined in-shader via `sampler2D(tex, samp)`.

## Real bugs found and fixed while building this (worth knowing before touching pass code)

- **Fullscreen-quad Y-flip**: the fullscreen vertex shader's `vUv` must be `0.5 - pos.y*0.5`, not
  `pos.y*0.5+0.5` — wgpu addresses texture row 0 at the top (matching D3D/Vulkan), so a naive
  bottom-up `vUv` is internally consistent for a single pass (whatever it writes, it reads back
  correctly via `read_pixels`) but silently vertically flips when a LATER pass samples that
  texture by UV. Caught by a two-pass test (one pass writes `step(0.5, uv.y)` into green, a second
  pass just resamples it) whose green channel came back constant instead of tracking `uv.y`. Fixed
  once in `gpu.rs`'s `FULLSCREEN_VERTEX_GLSL`; every pass shares it.
- **Ping-pong double-bookkeeping bug** (this crate's own test code, not the passes): a loop that
  both picks `(src, dst)` by `i % 2` AND calls `mem::swap` after every iteration cancels itself
  out — every "write" lands on the same physical buffer, so `src` never advances past its initial
  (usually zero) state. The fix is to use exactly one mechanism (`swap` alone, called once per
  iteration, always writing `&b` and reading `&a`). `renderer.rs`'s real `Renderer` was never
  affected (it only flips a single bool once per `render_frame` call) — this was purely a test-loop
  bug, caught by the "100 frames of feedback should diverge from frame 0" test initially reporting
  0 delta.

## Real limitations (honest, as of this session)

- **No ISF built-in coverage beyond what `isf_translate.rs` actually implements**: `TIME`,
  `TIMEDELTA`, `RENDERSIZE`, `PASSINDEX`, `FRAMEINDEX`, `DATE`, `isf_FragNormCoord`,
  `gl_FragColor`/`texture2D`/`textureCube`, and the input types `.hyst_format` already parses
  (`float`/`bool`/`long`/`color`/`point2D`/`hysteresisSignal`/`scriptOutput`, `resource` excluded
  per the TS original's own rule). No `IMG_SIZE`/`IMG_PIXEL`/`IMG_NORM_PIXEL` convenience macros, no
  `audioFFT`/`image`/`event` inputs (rejected at parse time already, upstream of this translator).
  Tested against exactly **one** real ISF-shaped fixture end-to-end (`isf_translate.rs`'s own
  test) — not a corpus of real-world ISF shaders. A real ISF shader using built-ins beyond this
  list will fail to compile with a `naga` parse error, not silently misrender.
- **Julia substrate**: both direct iteration (`render_julia`) and reference-orbit perturbation
  (`render_julia_perturbed`) now exist — see `passes/julia.rs`'s module doc and
  `render_julia_perturbed`'s own doc for the full mechanism. Real depth numbers found verifying
  this (64x64, `MAX_ITER=192`, distinct-RGBA-value count as the escape-time-detail signal): direct
  iteration stays plausible through `zoom=1e-6` (719 distinct colors), visibly degrades by `1e-7`
  (23 distinct), and is fully degenerate — a single flat color — by `1e-8`. Perturbation at those
  same depths stays rich (500-1100+ distinct colors) through `zoom=1e-9`, three orders of magnitude
  past where direct iteration already collapsed. Perturbation has its own real breakdown point too
  (empirically `zoom=1e-10`, also collapsing to a single flat color) — **not** the reference orbit's
  `f64` precision (nowhere near its floor at these depths, as originally guessed going in), but the
  shader's own escape check (`full = Zi + delta`): once `delta` is far enough below float32's
  relative precision near `Zi`'s O(1) magnitude, the addition rounds `delta` away entirely and every
  pixel's bailout collapses to the same answer. A real arbitrary-precision reference orbit for
  genuinely unbounded depth is **not built** — nor is a fix for that specific float32 escape-check
  ceiling, a smaller and different follow-up.
  - **Now audio-reactive** (user feedback: "too static... doesn't evolve or react to music," "the
    palette is very bad and illegible"). `passes/julia.rs` gained [`JuliaDriver`], a stateful
    driver (`update(dt, &SignalBus) -> JuliaNavState`) that replaces `JuliaNavState::driven_by_time`
    as the actual per-frame driver in `examples/audio_driven_render.rs` (that pure function is kept
    — this module's own tests and `renderer.rs`'s tests still want a deterministic state). It
    integrates zoom-dive rate, `c`-orbit angle, and a color-shimmer phase each frame by
    `dt * rate(audio)` — never by scaling the phase/time argument itself by an audio value, the bug
    class documented and fixed in the sibling Mandelbulb pass (AGENTS.md's dated entry) — so
    `energy`/`onset_density` make the dive/orbit visibly speed up and slow down with the music
    without ever snapping. A discrete golden-angle "region jump" (biased by energy) fires once per
    zoom-cycle reset, not every frame, so it's safe to key off audio there too. The escape-time
    `palette()` (both `JULIA_GLSL` and `JULIA_PERTURBED_GLSL`) was redesigned around Inigo Quilez's
    cosine-gradient formula (`color(t) = a + b*cos(2pi*(c*t+d))`) with distinct per-channel
    frequencies for real multi-hue contrast, `sqrt`-compressed band argument (a linear one caused
    dozens of full hue-cycles across a handful of pixels near deep mini-fractal thickets, reading as
    multicolor confetti — found rendering and looking), and a screen-space-derivative (`fwidth`)
    based anti-aliasing fade for genuine sub-pixel fractal detail (tried fading by absolute
    iteration count first; reverted — it wrongly flattened perturbation's legitimately-high but
    smoothly-varying deep-zoom iteration counts too, breaking both deep-zoom precision tests).
    `SignalBus::chroma_root_hue` drives the palette's hue directly, `centroid` picks a warm/cool
    accent color, `flatness` sets how much that accent mixes in — all direct per-frame values, not
    integrated phases, so likewise safe. Verified by rendering the full real target track
    (`~/Music/Singles/Published/hysteresis/hysteresis.wav`, 90s/1024x1024) and reviewing extracted
    frames by eye: real color variety (green/magenta/red/teal/gold rings, not one muddy hue) that
    visibly shifts across the clip, and zoom/orbit speed that visibly varies with the track's
    energy — plus a dedicated adversarial unit test
    (`driver_zoom_never_snaps_even_under_wildly_jittering_audio`) driving the worst-case
    frame-to-frame audio jitter (alternating near-0/near-1 every single frame) and asserting `zoom`
    only ever moves by the bounded per-frame rate-integration step, never a snap.
  - **Real continuous deep zoom, no reset loop (2026-09-06)**. User: "the perturbation doesnt seem
    to work, what we get is zoom in, then the snapback to fully zoomed out then back in, its in the
    same loop it was in before." **Root cause, confirmed**: `render_julia_perturbed` existed and was
    tested, but `renderer.rs`'s `render_frame` only ever called plain `render_julia` — dead code.
    `JuliaDriver`'s dive target was also `ZOOM_VOID=0.03`, a depth so shallow perturbation was never
    actually needed to reach it, which is why the whole cycle stayed short and repeated. **Fixed**:
    `renderer.rs` now always calls `render_julia_perturbed` (perturbation is an exact algebraic
    reformulation of the same recurrence at shallow zoom too — `delta = full - Z_n` — so it degrades
    gracefully rather than needing a depth-gated switch); `JuliaDriver`'s dive floor is now
    `ZOOM_FLOOR=1e-9`, a depth `render_julia_perturbed`'s own doc'd sweep proves still renders 500+
    distinct colors at. The zoom-cycle "reset" is unchanged in *shape* (still a discrete
    golden-angle region jump + fresh `find_interesting_pan` — a real "cut to a new dive," not
    hidden) but now fires only once the dive has gone ~25.8 natural-log-units deep instead of ~7.6,
    at this driver's rate range taking far longer than a typical clip to ever reach. **Verified
    against the real target track** (`instant_crush.wav`, 90s/1024x1024): a standalone trace of
    `JuliaDriver` alone (no GPU) driven by the track's real `SignalBus` hops shows zoom decreasing
    monotonically the entire clip, 2.56 → 1.75e-7 (7.5 orders of magnitude), **0 resets** in 2700
    frames. Full rendered-pipeline adjacent-frame diff (2699 pairs): mean 2.86% changed pixels,
    17 pairs >40% — checked against the zoom trace and attributable to real audio-reactive events
    (a global `chroma_root_hue`-driven palette recolor sweeping the memory field's whole
    accumulated trail at once, and the fractal boundary's real chaotic sensitivity to `c` at deep
    zoom, both amplified by Task 2's depth-tied `c` motion below) — not the reset-loop bug, which
    the zero-reset trace already rules out independently.
  - **`c` tied to zoom depth (2026-09-06)**. User: "changing the C... to the beat/tune of
    something... would make it more dynamic as we zoom in." `c`'s orbit (audio-driven) and a new
    second, tonal orbit (`chroma_root_hue`-driven, at its own angle) both have their radius scale
    with `depth_frac` (`zoom_log / cycle_log_len`, 0 at the top of a dive → 1 at `ZOOM_FLOOR`), and
    the beat/energy orbit's angular speed also picks up a depth term — so `c` visibly moves more,
    and the tonal component reads more, the deeper the dive goes, tying the two axes (zoom, `c`)
    into one system instead of two independent sliders. Test:
    `c_orbit_becomes_more_pronounced_as_zoom_deepens` (measures real per-frame `c` displacement
    early vs. late in a dive under identical audio, asserts late is meaningfully larger).
  - **Palette contrast fix (2026-09-06)**. User: "the visuals should look good on their own... none
    of this looks amazing." A real luminance-histogram probe this session (256x256, several
    timepoints) found the substrate/pipeline reading low-contrast: pipeline luminance std as low as
    ~19/255 with a floor that never dropped below 38/255 across a synthetic 90-frame run. Two real,
    separate causes found and fixed: (1) `palette()`'s screen-space-derivative anti-alias fade
    (`aaFade`) was unfloored, so most on-screen fractal detail — which sits in genuinely
    high-derivative, self-similar territory — got damped toward flat mid-gray; floored at 0.35
    (`0.35 + 0.65/(1+6*fwidth(...))`, both `JULIA_GLSL` and `JULIA_PERTURBED_GLSL`), guaranteeing a
    real color range everywhere. New regression test: `palette_keeps_real_contrast_not_a_flat_wash`
    (asserts luminance std > 8 on a real render). (2) `examples/audio_driven_render.rs`'s
    `frame_params` bloom/exposure combo (`threshold=0.3, strength=0.4-1.2, exposure=0.08`) let
    bloom spread from nearly every pixel above a low bar, compounding with the memory field's
    documented fixed ~7x steady-state gain into a persistent haze; retuned to
    `threshold=0.55, strength=0.2-0.7, exposure=0.035` — measured (same synthetic probe) floor drop
    from 38/255 to 24/255. Honest disclosure: this doesn't rewrite `memory_field.rs`'s own gain
    formula (out of this session's scope, and the ~7x steady-state gain is documented as
    intentional), so a still-brighter floor than a from-scratch design might choose is a real,
    tunable-later tradeoff, not eliminated.

- **Beam oscilloscope jitter (2026-09-06)**. User: "keep the current lissajous shape, but make the
  line move a bit like an oscilloscope line." `examples/audio_driven_render.rs`'s
  `lissajous_segments` keeps its exact base parametric curve (3:2 Lissajous, unchanged formula) and
  adds a small **perpendicular** displacement per point, driven by the real per-hop mono sample
  buffer already available in the demo's own render loop (nearest-index resampled from `HOP_SIZE`
  down to the curve's `POINTS`) — genuine waveform values, not an amplitude/RMS stand-in. The
  perpendicular direction comes from the curve's own analytic tangent (not a finite-difference
  approximation), so the wobble rides perpendicular to the path at every point regardless of local
  curve direction. `JITTER_AMP=0.03` keeps the displacement small enough that the underlying
  Lissajous shape stays the dominant, recognizable read, per the user's explicit ask.
- **Bloom**: single-level (bright-pass → blur H → blur V), not the TS original's mip-chain
  cascade — visibly blooms, doesn't match its exact quality/falloff.
- **Beam**: flat-cut quad segments, no rounded/mitered joins between segments, alpha-blended
  directly onto the composited output rather than fed through `composite.frag.glsl` as another
  sampled input (see `renderer.rs`'s module doc for why).
- **No pixel-perfect diff against the frozen browser build** — that needs an actual browser to run
  the TS original side by side; out of reach in this environment. What's verified instead: each
  pass's own behavior against the TS source it was ported from (fold symmetry, feedback
  accumulation, bright-pass thresholding, blur spread, beam rasterization bounds), and the full
  frame loop producing plausible, changing, non-degenerate output.
- **No pipeline caching** — every `render_glsl_fragment_shader`/pass call rebuilds shader modules,
  bind group layout, and pipeline from scratch. Fine for offline frame-by-frame rendering (this
  session's done-when bar); a real-time installation build needs pipelines built once and reused.
- **Real-time-safety**: none attempted or claimed — this renders to an owned offscreen texture,
  there's no windowing/surface/vsync path here at all yet (matches the TS original's own
  `OffscreenCanvas`-only render-worker architecture, per `gpu.rs`'s original module doc).
