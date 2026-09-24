//! Julia substrate — ported from
//! `src/render/worker/scenes/julia/shaders/julia.frag.glsl`.
//!
//! **Perturbation-based deep zoom is now ported** (was previously flagged
//! as "not ported" here): [`render_julia_perturbed`] mirrors the intent of
//! the original's `uRefOrbit`/`iteratePerturbed` — a CPU-computed `f64`
//! reference orbit at the view's center, uploaded once per frame as an
//! RG32F height-1 texture (same shape `hyst_format::types::IsfPass::
//! ScriptTexture`'s own doc comment documents for this exact kind of
//! per-frame data upload), with each pixel iterating only its small,
//! float32-safe *delta* from that orbit. See [`render_julia_perturbed`]'s
//! own doc for the real depth numbers found verifying this (direct
//! iteration's precision-loss signature vs. how deep perturbation actually
//! stays sharp) — still bounded by the reference orbit's own `f64`
//! precision, not extended to arbitrary precision.
//!
//! **Not ported at all, on purpose** (plan explicitly assigns this to R6,
//! not R2): `vortex-search.ts`/`boundary.ts`/`JuliaScene.ts`'s spring-damped
//! autopilot. [`JuliaNavState`] is a plain external-state struct any caller
//! (a later R6 autopilot, or this crate's own tests) can drive.
//!
//! **Now audio-reactive** (post-R2 user feedback: "too static... doesn't
//! evolve or react to music"): [`JuliaDriver`] is a real stateful driver —
//! it owns accumulated phase (zoom-dive log-phase, a small `c`-orbit angle,
//! a color-shimmer phase) and is advanced each frame by `update(dt, &SignalBus)`,
//! integrating each phase by `dt * rate(audio)` rather than ever scaling a
//! time/phase argument by an audio value directly — see its own doc for
//! the monotonicity trap that would otherwise cause (the same class of bug
//! found and fixed in the sibling Mandelbulb pass, AGENTS.md's dated entry
//! "Beam joints reverted; Mandelbulb phase-warp bug fixed"). The escape-
//! time palette (`palette()` in both `JULIA_GLSL`/`JULIA_PERTURBED_GLSL`)
//! was also redesigned around Inigo Quilez's cosine-gradient formula
//! (`color(t) = a + b*cos(2pi*(c*t+d))`) for real multi-hue legibility, and
//! wired to real audio: `SignalBus::chroma_root_hue` drives palette hue,
//! `centroid` picks a warm/cool accent color, `flatness` sets how much
//! that accent mixes in. `JuliaNavState::driven_by_time` is kept
//! unchanged (this module's own tests and `renderer.rs`'s tests still use
//! it for a pure/deterministic state) — `JuliaDriver` is what
//! `examples/audio_driven_render.rs` actually drives the substrate with.
//!
//! **Second round of user feedback (2026-09-10): "INCREDIBLY twitchy...
//! after the first ~13 seconds its fully one color".** Three real bugs in
//! [`JuliaDriver`], all fixed: (1) `pan` was probed once in `new()` and
//! never again, so as the dive deepened the fixed centre drifted off the
//! measure-zero boundary into a solid basin — now [`steer_toward_boundary`]
//! re-probes the current view every `RESTEER_FRAMES` and `pan` eases toward
//! the boundary filament, capped so it can't snap. (2) every rate/amplitude
//! read raw per-hop `bus.energy`/`centroid`/`flatness` — now they read
//! `~1.5s`/`~0.6s` EMAs of those (`energy_env` etc.). (3) the `c`-orbit
//! radius *grew* with depth, and the fractal boundary's ~`1/zoom`
//! sensitivity to `c` turned tiny deep-zoom `c`-deltas into whole-frame
//! churn — now the orbit angle is locked to `zoom_log` (inherently smooth)
//! and its radius is bounded *relative to the view* so the visual morph
//! rate stays roughly constant with depth, plus a hard per-frame `|Δc|`
//! cap as insurance.

use crate::gpu::{GpuContext, GpuError, OffscreenTarget};
use crate::passes::{pack_slots, CommonUniforms};

#[cfg(test)]
use std::sync::atomic::{AtomicUsize, Ordering};

/// Test-only instrumentation: counts real calls to [`compute_reference_orbit`]
/// so a test can assert the CPU-side reference-orbit computation happens
/// once per [`render_julia_perturbed`] call (once per frame), not once per
/// pixel — the actual sharing-across-pixels mechanism is structural (one
/// GPU bind group, set once, covers the single fullscreen-triangle draw
/// call that runs the fragment shader for every pixel), but this makes the
/// CPU-side half of that claim concrete and checkable rather than asserted
/// by reasoning alone.
#[cfg(test)]
static REF_ORBIT_COMPUTE_CALLS: AtomicUsize = AtomicUsize::new(0);

/// Whatever the shader needs as uniforms — fields chosen to match what
/// `julia.frag.glsl` actually reads (`uC`/`uPan`/`uAspect`/`uZoom`/`uAccent`/
/// `uHueShift`/`uPaletteMix`/`uPaletteFlip`/`uFlash`), nothing more. R6
/// replaces whatever drives this externally (see module doc); this struct
/// itself is just the uniform bag, not navigation logic.
#[derive(Clone, Copy, Debug)]
pub struct JuliaNavState {
    pub c: [f32; 2],
    pub pan: [f32; 2],
    pub zoom: f32,
    pub accent: [f32; 3],
    pub hue_shift: f32,
    pub palette_mix: f32,
    pub palette_flip: f32,
    pub flash: f32,
}

impl Default for JuliaNavState {
    fn default() -> Self {
        Self {
            c: [-0.4, 0.6],
            pan: [0.0, 0.0],
            zoom: 1.5,
            accent: [0.8, 0.5, 1.0],
            hue_shift: 0.0,
            palette_mix: 0.3,
            palette_flip: 0.0,
            flash: 0.0,
        }
    }
}

/// Stateful, audio-reactive driver for the Julia substrate — replaces
/// `JuliaNavState::driven_by_time(t)` as `audio_driven_render.rs`'s actual
/// per-frame driver (that function itself is kept, still used by this
/// module's own tests and by `renderer.rs`'s tests, both of which want a
/// pure/deterministic state rather than a stateful audio-driven one).
///
/// **Why this exists**: `driven_by_time` is a pure function of absolute
/// elapsed time — none of the fractal's own motion (zoom-dive rate,
/// `c`-orbit) or its color ever responded to the music, which is exactly
/// what was reported as "too static... doesn't evolve or react to music."
///
/// **The monotonicity trap this is built to avoid** (see AGENTS.md's dated
/// entry "Beam joints reverted; Mandelbulb phase-warp bug fixed" — a real
/// bug found and fixed in the sibling Mandelbulb pass): multiplying a
/// monotonic elapsed-time argument by an audio-derived factor that itself
/// isn't monotonic (`driven_by_time(t * some_audio_value)`) makes the
/// effective phase jump non-monotonically frame to frame whenever the
/// audio factor swings — a visible "snap." **This driver never does that.**
/// Every accumulated phase field below (`zoom_log`, `c_angle`,
/// `color_phase`) only ever advances by `dt * rate(audio)` — the *rate*
/// depends on audio (perfectly safe: a rate is not itself the phase being
/// read), the accumulator itself always moves forward by a bounded,
/// per-frame `dt`-scaled amount regardless of how audio jitters. The one
/// place audio is read as a direct instantaneous value rather than
/// integrated (`chroma_root_hue` -> hue, `centroid` -> accent color,
/// `flatness` -> palette_mix) is likewise safe: none of those feed a phase
/// argument, they're just per-frame color parameters. The one *event*
/// that reads audio discretely (the golden-angle region jump at a zoom-
/// cycle reset) is also safe by construction: it fires once per reset, not
/// every frame, so there's no frame-to-frame monotonicity to violate.
#[derive(Clone, Copy, Debug)]
pub struct JuliaDriver {
    /// Accumulated log-zoom phase; `zoom = ZOOM_DOT * exp(-zoom_log)`. Only
    /// ever advances forward (`dt * rate`) for the whole clip — this is a
    /// real continuous dive, not the earlier design's short dot-to-void
    /// cycle. It only ever "wraps" (subtracting `cycle_log_len`, see
    /// `update`) once it reaches `ZOOM_FLOOR`, a real deep-zoom depth
    /// perturbation is proven to render sharply at (see
    /// `render_julia_perturbed`'s own doc: 500+ distinct colors still at
    /// `zoom=1e-9`) — at `BASE_ZOOM_RATE`'s baseline rate that takes ~170s,
    /// well past a typical clip's length, so in practice most renders never
    /// wrap at all; when one does, it reads as a deliberate "cut to a new
    /// dive," not a repeating loop.
    zoom_log: f32,
    /// Slow time-drift added on top of the *zoom-locked* `c`-orbit angle
    /// (`c_angle = zoom_log * k + c_drift`), integrated by `dt *
    /// small_rate(smoothed_energy)`. Keeps `c` evolving even where the dive
    /// momentarily slows; smooth by construction because the rate reads
    /// `energy_env`, never raw per-hop `bus.energy` (that was the
    /// "INCREDIBLY twitchy" bug).
    c_drift: f32,
    /// Angle picking which golden-angle-spaced region of the fixed circle
    /// `base_c` sits on. Only ever changes at a zoom-cycle reset (a
    /// discrete event), never per-frame.
    base_angle: f32,
    /// Current zoom centre, **eased toward `pan_target` every frame** by a
    /// step capped at a fraction of the current view width. A *fixed* pan
    /// (the old design — probed once in `new()`, never again) was the
    /// "collapses to one flat colour after ~13s" bug: a single point is
    /// never exactly on the measure-zero boundary, so past some depth the
    /// whole view sits inside one solid basin.
    pan: [f32; 2],
    /// Boundary point the last re-steer (`steer_toward_boundary`, every
    /// `RESTEER_FRAMES`) found; `pan` chases this so the fractal boundary
    /// filament — where all the escape-time detail lives — stays framed for
    /// the whole dive.
    pan_target: [f32; 2],
    /// Frame counter; gates the periodic (not per-frame) re-steer.
    frame: u32,
    /// Running reset counter; informational (not read by the shader).
    cycle_index: u32,
    /// Circular EMA of `chroma_root_hue` (~1s now, was ~0.25s → visible
    /// hue flicker). A smoothing filter on a bounded instantaneous value,
    /// not a phase accumulator.
    hue_smoothed: f32,
    /// Continuous color-cycle phase (extra shimmer independent of chroma),
    /// integrated by a smooth `dt * rate(energy_env)`.
    color_phase: f32,
    /// Heavily-smoothed (~1.5s) `bus.energy`. **Every** audio value that
    /// modulates a rate or an amplitude in `update` reads this, not the raw
    /// per-hop value — the raw signal's frame-to-frame variance driven
    /// straight into `c`-motion / zoom-rate / palette is exactly what read
    /// as twitchy.
    energy_env: f32,
    /// ~0.6s EMAs of `centroid`/`flatness` (they set palette accent/mix
    /// every frame — same twitch reason).
    centroid_env: f32,
    flatness_env: f32,
    /// Previous frame's `c`, so `update` can hard-cap the per-frame delta —
    /// belt-and-suspenders against any future retuning reintroducing a
    /// c-snap.
    c_prev: [f32; 2],
}

impl Default for JuliaDriver {
    fn default() -> Self {
        Self::new()
    }
}

impl JuliaDriver {
    /// Matches `driven_by_time`'s original opening shot: not the far-away
    /// dot, but partway through a cycle (`zoom_log` starts at
    /// `BASE_ZOOM_RATE * START_OFFSET_SECS` rather than 0).
    pub fn new() -> Self {
        const START_OFFSET_SECS: f32 = 21.0;
        let zoom_log = BASE_ZOOM_RATE * START_OFFSET_SECS;
        let base_angle = 0.0f32;
        let base_c = region_c(base_angle);
        let pan = find_interesting_pan(base_c);
        Self {
            zoom_log,
            c_drift: 0.0,
            base_angle,
            pan,
            pan_target: pan,
            frame: 0,
            cycle_index: 0,
            hue_smoothed: 0.0,
            color_phase: 0.0,
            energy_env: 0.0,
            centroid_env: 0.5,
            flatness_env: 0.3,
            c_prev: base_c,
        }
    }

    /// Advance by one real frame (`dt` seconds) using the current
    /// `SignalBus` hop, producing the `JuliaNavState` the shader reads this
    /// frame. See the struct doc / module doc for why every audio read
    /// here is safe.
    pub fn update(&mut self, dt: f32, bus: &hyst_core::SignalBus) -> JuliaNavState {
        self.frame = self.frame.wrapping_add(1);
        let cycle_log_len = (ZOOM_DOT / ZOOM_FLOOR).ln();

        // --- Smooth every audio value before it modulates a rate or an
        // amplitude. Raw per-hop `bus.*` has large frame-to-frame variance;
        // feeding it straight into c-motion / zoom-rate / palette was the
        // "INCREDIBLY twitchy" report. Simple one-pole EMAs, ~1.5s (energy)
        // and ~0.6s (colour) time constants.
        let ema = |cur: f32, target: f32, tc: f32| cur + (target - cur) * (dt / tc).min(1.0);
        self.energy_env = ema(self.energy_env, bus.energy.clamp(0.0, 1.0), 1.5);
        self.centroid_env = ema(self.centroid_env, bus.centroid.clamp(0.0, 1.0), 0.6);
        self.flatness_env = ema(self.flatness_env, bus.flatness.clamp(0.0, 1.0), 0.6);
        let e = self.energy_env;

        // --- Zoom: a smooth continuous dive whose rate breathes only with
        // *smoothed* energy. Still pure rate-integration into `zoom_log`,
        // never scaling `zoom_log`/`t` directly.
        let zoom_rate = BASE_ZOOM_RATE * (0.6 + 0.8 * e);
        self.zoom_log += dt * zoom_rate;

        // --- Colour shimmer phase: smooth rate.
        self.color_phase += dt * (0.04 + 0.12 * e);

        // --- Rare "cut to a new dive" once the dive genuinely bottoms out
        // at ZOOM_FLOOR (at this rate range, longer than a typical clip).
        if self.zoom_log >= cycle_log_len {
            self.zoom_log -= cycle_log_len;
            self.cycle_index += 1;
            const GOLDEN_ANGLE: f32 = 2.399_963;
            self.base_angle += GOLDEN_ANGLE * (1.0 + e);
            let base_c = region_c(self.base_angle);
            self.pan = find_interesting_pan(base_c);
            self.pan_target = self.pan;
            self.c_prev = base_c; // don't let the per-frame cap fight the cut
        }

        let zoom = ZOOM_DOT * (-self.zoom_log).exp();
        let base_c = region_c(self.base_angle);

        // --- c: a slow smooth dance LOCKED TO ZOOM PROGRESS. Angle is
        // `zoom_log * k` (inherently smooth — `zoom_log` is monotonic and
        // only moves by a bounded `dt * rate` per frame) plus a slow
        // smoothed-energy time drift. Orbit radius is bounded *relative to
        // the current view* (`min(cap, k2 * zoom)`) so its visual effect
        // stays roughly constant with depth instead of exploding — the old
        // design grew the radius with depth, which (with the fractal
        // boundary's ~1/zoom sensitivity to `c`) is exactly what made
        // deep-zoom `c`-changes twitch.
        self.c_drift += dt * (0.015 + 0.04 * e);
        let c_angle = self.zoom_log * 0.4 + self.c_drift;
        let c_orbit_r = (C_ORBIT_REL * zoom).min(C_ORBIT_CAP) * (0.6 + 0.4 * e);
        let mut c = [
            base_c[0] + c_orbit_r * c_angle.cos(),
            base_c[1] + c_orbit_r * (0.75 * c_angle).sin(),
        ];
        // Hard per-frame delta cap — `c` is smooth by construction now, this
        // just guarantees no future tuning mistake can bring back a c-snap.
        let dcx = c[0] - self.c_prev[0];
        let dcy = c[1] - self.c_prev[1];
        let dmag = (dcx * dcx + dcy * dcy).sqrt();
        if dmag > MAX_C_STEP {
            let s = MAX_C_STEP / dmag;
            c = [self.c_prev[0] + dcx * s, self.c_prev[1] + dcy * s];
        }
        self.c_prev = c;

        // --- Pan: keep the boundary framed for the whole dive. Re-steer
        // occasionally (not every frame), then ease toward the found
        // boundary point with a step capped at a fraction of the view width
        // so it can never snap.
        if self.frame % RESTEER_FRAMES == 0 {
            self.pan_target = steer_toward_boundary(self.pan, c, zoom);
        }
        let mut sx = (self.pan_target[0] - self.pan[0]) * PAN_EASE;
        let mut sy = (self.pan_target[1] - self.pan[1]) * PAN_EASE;
        let smag = (sx * sx + sy * sy).sqrt();
        let cap = PAN_STEP_FRAC * zoom;
        if smag > cap {
            let s = cap / smag;
            sx *= s;
            sy *= s;
        }
        self.pan[0] += sx;
        self.pan[1] += sy;

        // --- Circular (shortest-path) hue smoothing, now ~1s.
        let hue_target = bus.chroma_root_hue.rem_euclid(1.0);
        let mut diff = hue_target - self.hue_smoothed;
        if diff > 0.5 {
            diff -= 1.0;
        } else if diff < -0.5 {
            diff += 1.0;
        }
        self.hue_smoothed = (self.hue_smoothed + diff * (dt / 1.0).min(1.0)).rem_euclid(1.0);

        // --- Palette accent/mix from the SMOOTHED colour features.
        const COOL: [f32; 3] = [0.25, 0.45, 1.0];
        const WARM: [f32; 3] = [1.0, 0.55, 0.25];
        let ctr = self.centroid_env;
        let accent = [
            COOL[0] + (WARM[0] - COOL[0]) * ctr,
            COOL[1] + (WARM[1] - COOL[1]) * ctr,
            COOL[2] + (WARM[2] - COOL[2]) * ctr,
        ];
        let palette_mix = 0.2 + 0.6 * self.flatness_env;

        JuliaNavState {
            c,
            pan: self.pan,
            zoom,
            accent,
            hue_shift: self.hue_smoothed,
            palette_mix,
            palette_flip: self.color_phase.rem_euclid(1.0),
            flash: 0.0,
        }
    }
}

/// Fixed golden-angle-spread circle `driven_by_time`/`JuliaDriver` both
/// place discrete region centers on: same `c = [-0.4 + 0.35*cos(angle),
/// 0.5 + 0.35*sin(angle)]` shape either used, factored out so both agree.
fn region_c(angle: f32) -> [f32; 2] {
    [-0.4 + 0.35 * angle.cos(), 0.5 + 0.35 * angle.sin()]
}

const ZOOM_DOT: f32 = 60.0;
/// `JuliaDriver`'s real dive floor — chosen from `render_julia_perturbed`'s
/// own doc'd empirical sweep (still 500+ distinct colors at this depth, one
/// order of magnitude before perturbation's own proven breakdown at 1e-10),
/// not the old `driven_by_time`-inherited 0.03 (a depth so shallow it never
/// needed perturbation at all — the actual reason the old dive read as a
/// short, frequently-repeating loop instead of a real deep zoom).
const ZOOM_FLOOR: f32 = 1e-9;
const BASE_ZOOM_RATE: f32 = 0.15; // per second, baseline (pre-audio-boost)

// --- `JuliaDriver` `c`-orbit / pan-steering tuning ---
/// `c`-orbit radius is `min(C_ORBIT_CAP, C_ORBIT_REL * zoom)` — capped in
/// absolute `c`-units at shallow zoom, then shrinking *with* the view once
/// it's small so the visual morph rate stays bounded at depth.
const C_ORBIT_CAP: f32 = 0.05;
const C_ORBIT_REL: f32 = 4.0;
/// Absolute hard cap on `|c_n - c_{n-1}|` per frame (insurance only; the
/// orbit is already smooth).
const MAX_C_STEP: f32 = 0.004;
/// Re-run the boundary search every this-many frames (~0.2s at 30fps) —
/// "periodic, not per-frame" both for cost and to avoid grid-cell hunting.
const RESTEER_FRAMES: u32 = 6;
/// Per-frame fraction of the way `pan` moves toward `pan_target`...
const PAN_EASE: f32 = 0.18;
/// ...but never more than this fraction of the current view width in one
/// frame (so the steer can never read as a snap).
const PAN_STEP_FRAC: f32 = 0.14;

impl JuliaNavState {
    /// Deterministic test/demo driver: slowly rotates `c` around a fixed
    /// circle over time. **Explicitly a stand-in for R6's real autopilot**
    /// (spring-damped vortex-search drift/zoom-rate/theta-sweep state
    /// machine, `docs/LEGACY_TS.md`) — just enough motion to prove the
    /// render pipeline responds to a changing `c` frame over frame. Kept
    /// (not removed) alongside the newer [`JuliaDriver`] because this
    /// module's own tests and `renderer.rs`'s tests want a pure,
    /// deterministic state, not a stateful audio-driven one — `JuliaDriver`
    /// is what `examples/audio_driven_render.rs` actually drives the
    /// substrate with now (see its own doc for why).
    pub fn driven_by_time(t: f32) -> Self {
        // A real continuous zoom-in dive with NO visible cut: zoom decays
        // from ZOOM_DOT (whole set reads as a tiny dot) down to ZOOM_VOID
        // (deep enough the frame is solid interior color, same VOID_COLOR
        // as the far-background), then resets — both ends of the cut are
        // void-colored so the reset is invisible, reading as "zooming into
        // itself" (the fractal's real self-similarity, echoed not faked).
        const ZOOM_DOT: f32 = 60.0;
        const ZOOM_VOID: f32 = 0.03;
        const ZOOM_RATE: f32 = 0.15; // per second
        let cycle_len = (ZOOM_DOT / ZOOM_VOID).ln() / ZOOM_RATE;
        // User: the opening shot shouldn't be the far-away dot — start
        // partway through a cycle (already at a real, moderately-zoomed
        // view) rather than at t_in_cycle=0.
        const START_OFFSET_SECS: f32 = 21.0;
        let effective_t = t + START_OFFSET_SECS;
        let cycle_index = (effective_t / cycle_len).floor();
        let t_in_cycle = effective_t - cycle_index * cycle_len;
        let zoom = ZOOM_DOT * (-ZOOM_RATE * t_in_cycle).exp();

        // User: zoom shouldn't target a fixed center — it should dive into
        // an *interesting* region. Still not real vortex-search (R6's job:
        // navigate live toward detail as zoom deepens) but a real, cheap
        // per-cycle fix: `c` changes discretely each cycle (golden-angle
        // spread so cycles don't repeat the same region for a long time),
        // and `find_interesting_pan` actually probes for a boundary-hugging
        // point for that `c` instead of assuming the origin has detail.
        let angle = cycle_index * 2.399_963; // golden angle, radians
        let c = [-0.4 + 0.35 * angle.cos(), 0.5 + 0.35 * angle.sin()];
        let pan = find_interesting_pan(c);

        let hue_shift = (t * 0.03).rem_euclid(1.0);
        Self {
            c,
            zoom,
            pan,
            hue_shift,
            ..Self::default()
        }
    }
}

/// Mirrors `JULIA_GLSL`'s escape-time loop exactly (same `MAX_ITER=192`,
/// same `dot(z,z)>4.0` bailout) — the screen center always samples `z0 =
/// pan` regardless of zoom (`uv=(0,0)` at center, `z = pan + uv*zoom`), so
/// probing candidate `pan` points directly at this reference scale finds a
/// real point in the complex plane, not a UV/zoom-relative approximation.
fn escape_iters(p: [f32; 2], c: [f32; 2]) -> u32 {
    const MAX_ITER: u32 = 192;
    let mut z = p;
    for i in 0..MAX_ITER {
        if z[0] * z[0] + z[1] * z[1] > 4.0 {
            return i;
        }
        z = [z[0] * z[0] - z[1] * z[1] + c[0], 2.0 * z[0] * z[1] + c[1]];
    }
    MAX_ITER
}

/// A cheap, deterministic stand-in for real vortex-search (R6's job): grid-
/// search a neighborhood of the origin for the point with the HIGHEST
/// finite escape count — the closer a point sits to the boundary without
/// being captured by the interior, the longer it takes to escape, so this
/// hugs genuine fractal detail instead of assuming the origin has any.
fn find_interesting_pan(c: [f32; 2]) -> [f32; 2] {
    const GRID: i32 = 24;
    const RADIUS: f32 = 0.9;
    let mut best = [0.0f32, 0.0];
    let mut best_iters = 0u32;
    for i in 0..GRID {
        for j in 0..GRID {
            let fx = (i as f32 + 0.5) / GRID as f32 * 2.0 - 1.0;
            let fy = (j as f32 + 0.5) / GRID as f32 * 2.0 - 1.0;
            let p = [fx * RADIUS, fy * RADIUS];
            let iters = escape_iters(p, c);
            if iters < 192 && iters > best_iters {
                best_iters = iters;
                best = p;
            }
        }
    }
    best
}

/// f64 sibling of [`escape_iters`]. Used only by [`steer_toward_boundary`]
/// to *pick* a grid cell — never to shade a pixel — so f64's own eventual
/// deep-zoom limit (~1e-13) is well past anything this driver reaches, but
/// it does matter that the sample points (only ~`zoom` apart, and `zoom`
/// can be far below f32's relative precision near an O(1) `pan`) stay
/// distinguishable, which f32 would not manage.
fn escape_iters_f64(p: [f64; 2], c: [f64; 2]) -> u32 {
    const MAX_ITER: u32 = 192;
    let (mut x, mut y) = (p[0], p[1]);
    for i in 0..MAX_ITER {
        if x * x + y * y > 4.0 {
            return i;
        }
        let nx = x * x - y * y + c[0];
        y = 2.0 * x * y + c[1];
        x = nx;
    }
    MAX_ITER
}

/// Re-steer the zoom centre so the fractal boundary filament (where all the
/// escape-time detail lives) stays framed as the dive deepens.
///
/// A *fixed* `pan` was the "collapses to one flat colour after ~13s" bug:
/// a single point is never exactly on the measure-zero boundary, so past
/// some zoom depth the whole view sits inside one solid basin. This grid-
/// searches the **current view** (`pan ± zoom * span`) in f64 for the point
/// with the highest finite escape count (closest to the boundary without
/// being captured), lightly biased toward the view centre so the target
/// doesn't skate to a corner. If the view has already fallen off the
/// boundary entirely (best finite escape count too low), it retries once at
/// a much wider span to re-acquire the filament.
fn steer_toward_boundary(pan: [f32; 2], c: [f32; 2], zoom: f32) -> [f32; 2] {
    const GRID: i32 = 15;
    let cf = [c[0] as f64, c[1] as f64];
    let z = zoom as f64;
    let (px, py) = (pan[0] as f64, pan[1] as f64);

    let search = |span: f64| -> (u32, [f64; 2]) {
        let mut best_score = f64::MIN;
        let mut best_iters = 0u32;
        let mut best = [px, py];
        for i in 0..GRID {
            for j in 0..GRID {
                let fx = (i as f64 + 0.5) / GRID as f64 * 2.0 - 1.0;
                let fy = (j as f64 + 0.5) / GRID as f64 * 2.0 - 1.0;
                let p = [px + fx * z * span, py + fy * z * span];
                let iters = escape_iters_f64(p, cf);
                if iters == 0 || iters >= 192 {
                    continue;
                }
                let score = iters as f64 - 12.0 * (fx * fx + fy * fy);
                if score > best_score {
                    best_score = score;
                    best_iters = iters;
                    best = p;
                }
            }
        }
        (best_iters, best)
    };

    let (iters, best) = search(0.85);
    let best = if iters < 24 { search(6.0).1 } else { best };
    [best[0] as f32, best[1] as f32]
}

pub fn render_julia(
    ctx: &GpuContext,
    output: &OffscreenTarget,
    state: &JuliaNavState,
    aspect: f32,
) -> Result<(), GpuError> {
    let common = CommonUniforms::new(0.0, [output.width() as f32, output.height() as f32]);
    let slots = [
        [state.c[0], state.c[1], 0.0, 0.0],
        [state.pan[0], state.pan[1], 0.0, 0.0],
        [aspect, state.zoom, 0.0, 0.0],
        [state.accent[0], state.accent[1], state.accent[2], 0.0],
        [
            state.hue_shift,
            state.palette_mix,
            state.palette_flip,
            state.flash,
        ],
    ];
    output.render_glsl_fragment_shader(
        ctx,
        JULIA_GLSL,
        common.bytes(),
        Some(&pack_slots(&slots)),
        &[],
    )
}

/// Reference orbit for perturbation-based deep zoom: iterates `Z_{n+1} =
/// Z_n^2 + c` starting at `Z_0 = pan`, in real `f64`, for up to `max_iter`
/// steps. This is the one piece of the whole perturbation pass that needs
/// double precision — computed once per frame on the CPU (a few hundred
/// f64 complex multiplies, trivially cheap relative to a GPU frame), it
/// lets every pixel's *delta* from this orbit stay small (bounded by
/// `zoom`, not by absolute depth) and therefore safe to iterate in float32
/// on the GPU regardless of how deep `zoom` has gotten. Mirrors
/// `JuliaScene.ts`'s `updateReferenceOrbit`: if the orbit ever goes
/// non-finite (it eventually will, past its escape point — magnitudes
/// double-exponentiate once `|z|>2`), the last finite value is held for
/// the remainder of the array rather than uploading NaN/Inf — provably
/// harmless (see `render_julia_perturbed`'s shader: a held-constant point
/// far past escape has `dot(Zi+delta,Zi+delta) > 4` regardless of `delta`,
/// so any pixel that reaches that index bails out there, correctly).
fn compute_reference_orbit(pan: [f64; 2], c: [f64; 2], max_iter: u32) -> Vec<[f32; 2]> {
    #[cfg(test)]
    REF_ORBIT_COMPUTE_CALLS.fetch_add(1, Ordering::Relaxed);

    let mut orbit = Vec::with_capacity(max_iter as usize);
    let mut z = pan;
    for _ in 0..max_iter {
        if !z[0].is_finite() || !z[1].is_finite() {
            let last = *orbit.last().unwrap_or(&[0.0f32, 0.0]);
            orbit.resize(max_iter as usize, last);
            break;
        }
        orbit.push([z[0] as f32, z[1] as f32]);
        z = [z[0] * z[0] - z[1] * z[1] + c[0], 2.0 * z[0] * z[1] + c[1]];
    }
    orbit
}

/// GPU-side home for one frame's reference orbit: an RG32F, height-1
/// texture — the exact shape `hyst_format::types::IsfPass::ScriptTexture`'s
/// own doc comment documents as this format's convention for a script's
/// per-frame non-scalar data upload, reused here for the same reason (a
/// small array of numeric pairs, read back by exact index, not filtered).
struct RefOrbitTexture {
    view: wgpu::TextureView,
    sampler: wgpu::Sampler,
}

impl RefOrbitTexture {
    /// `Rg32Float` is not a filterable format under this crate's default
    /// device features (no `FLOAT32_FILTERABLE`) — irrelevant anyway since
    /// the shader reads it with `texelFetch` by exact integer index, never
    /// interpolated, so `Nearest`/non-filtering here costs nothing. This is
    /// also *why* this pass can't reuse `OffscreenTarget::
    /// render_glsl_fragment_shader`'s shared texture-binding path (it
    /// hardcodes `filterable: true` / a `Filtering` sampler for every
    /// sampled texture, which fails bind-group-layout validation against
    /// this format) — see [`render_glsl_with_ref_orbit`] below, this pass's
    /// own small bespoke pipeline for exactly this one binding shape.
    fn upload(ctx: &GpuContext, orbit: &[[f32; 2]]) -> Self {
        let len = orbit.len() as u32;
        let texture = ctx.device.create_texture(&wgpu::TextureDescriptor {
            label: Some("hyst-render julia reference-orbit texture"),
            size: wgpu::Extent3d {
                width: len,
                height: 1,
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Rg32Float,
            usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST,
            view_formats: &[],
        });
        ctx.queue.write_texture(
            wgpu::ImageCopyTexture {
                texture: &texture,
                mip_level: 0,
                origin: wgpu::Origin3d::ZERO,
                aspect: wgpu::TextureAspect::All,
            },
            bytemuck::cast_slice(orbit),
            wgpu::ImageDataLayout {
                offset: 0,
                bytes_per_row: Some(len * 8),
                rows_per_image: Some(1),
            },
            wgpu::Extent3d {
                width: len,
                height: 1,
                depth_or_array_layers: 1,
            },
        );
        let view = texture.create_view(&wgpu::TextureViewDescriptor::default());
        let sampler = ctx.device.create_sampler(&wgpu::SamplerDescriptor {
            address_mode_u: wgpu::AddressMode::ClampToEdge,
            address_mode_v: wgpu::AddressMode::ClampToEdge,
            address_mode_w: wgpu::AddressMode::ClampToEdge,
            mag_filter: wgpu::FilterMode::Nearest,
            min_filter: wgpu::FilterMode::Nearest,
            ..Default::default()
        });
        Self { view, sampler }
    }
}

/// Perturbation-theory sibling of [`render_julia`] for zoom depths where
/// direct float32 iteration loses precision. Uploads a fresh `f64`-computed
/// reference orbit (see [`compute_reference_orbit`]) at `Z_0 = pan` every
/// call, then runs a shader whose per-pixel loop iterates only `dz = z -
/// Z_n` (starting at `dz_0 = uv * zoom`, small by construction regardless
/// of absolute zoom depth) in float32: `dz_{n+1} = 2*Z_n*dz_n + dz_n^2`,
/// bailing out on `|Z_n + dz_n|^2 > 4`.
///
/// **Verified depth numbers (this session, 64x64 render, `MAX_ITER=192`,
/// `c=[-0.4,0.6]`, `pan` from `find_interesting_pan`, counting distinct
/// RGBA values across the frame as the escape-time-detail signal)**:
/// probing a whole range of depths, direct iteration stays plausible
/// through `zoom=1e-6` (719 distinct colors), visibly degrades by `1e-7`
/// (23 distinct), and is fully degenerate — a single flat color, all
/// escape-time detail gone — by `1e-8`. Perturbation at those same depths
/// stays rich (500-1100+ distinct colors) all the way through `zoom=1e-9`,
/// three orders of magnitude past where direct iteration already
/// collapsed. **Real remaining limit, found empirically, not the one
/// hypothesized going in**: perturbation itself degenerates to a single
/// flat color at `zoom=1e-10` in the same probe — but the cause is *not*
/// the reference orbit's own `f64` precision (nowhere close to its ~15-17
/// significant-digit floor at these depths). It's the shader's escape
/// check, `full = Zi + delta`: once `delta` (`O(zoom)`) is far enough below
/// float32's relative precision near `Zi`'s `O(1)` magnitude, the addition
/// rounds `delta` away entirely, so every pixel's bailout test collapses
/// to the same answer regardless of its true position. Fixing *that*
/// (computing the escape check at higher precision than the per-pixel
/// delta iteration itself needs) is a smaller, different follow-up than
/// arbitrary-precision reference orbits — neither is built here.
pub fn render_julia_perturbed(
    ctx: &GpuContext,
    output: &OffscreenTarget,
    state: &JuliaNavState,
    aspect: f32,
) -> Result<(), GpuError> {
    const MAX_ITER: u32 = 192;
    let pan_f64 = [state.pan[0] as f64, state.pan[1] as f64];
    let c_f64 = [state.c[0] as f64, state.c[1] as f64];
    let orbit = compute_reference_orbit(pan_f64, c_f64, MAX_ITER);
    let ref_orbit = RefOrbitTexture::upload(ctx, &orbit);

    let common = CommonUniforms::new(0.0, [output.width() as f32, output.height() as f32]);
    let slots = [
        [state.c[0], state.c[1], 0.0, 0.0],
        [state.pan[0], state.pan[1], 0.0, 0.0],
        [aspect, state.zoom, 0.0, 0.0],
        [state.accent[0], state.accent[1], state.accent[2], 0.0],
        [
            state.hue_shift,
            state.palette_mix,
            state.palette_flip,
            state.flash,
        ],
    ];
    render_glsl_with_ref_orbit(
        ctx,
        output,
        JULIA_PERTURBED_GLSL,
        common.bytes(),
        &pack_slots(&slots),
        &ref_orbit,
    )
}

/// Bespoke sibling of `OffscreenTarget::render_glsl_fragment_shader` for
/// exactly one binding shape: `Common` UBO (binding 0), `Inputs` UBO
/// (binding 1, always present here, unlike the shared helper's optional
/// one), and one *non-filterable* sampled texture (bindings 2/3) — see
/// [`RefOrbitTexture::upload`]'s doc for why the shared helper (which
/// hardcodes every sampled texture as filterable) can't be reused for this
/// one pass. Deliberately small and local to this file rather than a
/// change to the shared `gpu.rs` helper, which every other pass also calls
/// with the filterable convention — not touched here.
fn render_glsl_with_ref_orbit(
    ctx: &GpuContext,
    output: &OffscreenTarget,
    fragment_glsl: &str,
    common_ubo_bytes: &[u8],
    inputs_ubo_bytes: &[u8],
    ref_orbit: &RefOrbitTexture,
) -> Result<(), GpuError> {
    use wgpu::util::DeviceExt;

    let fs_module = ctx
        .device
        .create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("hyst-render julia perturbed fragment"),
            source: wgpu::ShaderSource::Glsl {
                shader: fragment_glsl.into(),
                stage: wgpu::naga::ShaderStage::Fragment,
                defines: Default::default(),
            },
        });
    let vs_module = ctx
        .device
        .create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("hyst-render julia perturbed fullscreen vertex"),
            source: wgpu::ShaderSource::Glsl {
                shader: FULLSCREEN_VERTEX_GLSL.into(),
                stage: wgpu::naga::ShaderStage::Vertex,
                defines: Default::default(),
            },
        });

    let entries = [
        wgpu::BindGroupLayoutEntry {
            binding: 0,
            visibility: wgpu::ShaderStages::FRAGMENT,
            ty: wgpu::BindingType::Buffer {
                ty: wgpu::BufferBindingType::Uniform,
                has_dynamic_offset: false,
                min_binding_size: None,
            },
            count: None,
        },
        wgpu::BindGroupLayoutEntry {
            binding: 1,
            visibility: wgpu::ShaderStages::FRAGMENT,
            ty: wgpu::BindingType::Buffer {
                ty: wgpu::BufferBindingType::Uniform,
                has_dynamic_offset: false,
                min_binding_size: None,
            },
            count: None,
        },
        wgpu::BindGroupLayoutEntry {
            binding: 2,
            visibility: wgpu::ShaderStages::FRAGMENT,
            ty: wgpu::BindingType::Texture {
                sample_type: wgpu::TextureSampleType::Float { filterable: false },
                view_dimension: wgpu::TextureViewDimension::D2,
                multisampled: false,
            },
            count: None,
        },
        wgpu::BindGroupLayoutEntry {
            binding: 3,
            visibility: wgpu::ShaderStages::FRAGMENT,
            ty: wgpu::BindingType::Sampler(wgpu::SamplerBindingType::NonFiltering),
            count: None,
        },
    ];
    let bgl = ctx
        .device
        .create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: None,
            entries: &entries,
        });

    let common_buf = ctx
        .device
        .create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("julia perturbed common ubo"),
            contents: common_ubo_bytes,
            usage: wgpu::BufferUsages::UNIFORM,
        });
    let inputs_buf = ctx
        .device
        .create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("julia perturbed inputs ubo"),
            contents: inputs_ubo_bytes,
            usage: wgpu::BufferUsages::UNIFORM,
        });

    let bind_group = ctx.device.create_bind_group(&wgpu::BindGroupDescriptor {
        label: None,
        layout: &bgl,
        entries: &[
            wgpu::BindGroupEntry {
                binding: 0,
                resource: common_buf.as_entire_binding(),
            },
            wgpu::BindGroupEntry {
                binding: 1,
                resource: inputs_buf.as_entire_binding(),
            },
            wgpu::BindGroupEntry {
                binding: 2,
                resource: wgpu::BindingResource::TextureView(&ref_orbit.view),
            },
            wgpu::BindGroupEntry {
                binding: 3,
                resource: wgpu::BindingResource::Sampler(&ref_orbit.sampler),
            },
        ],
    });

    let pipeline_layout = ctx
        .device
        .create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: None,
            bind_group_layouts: &[&bgl],
            push_constant_ranges: &[],
        });
    let pipeline = ctx
        .device
        .create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("hyst-render julia perturbed pipeline"),
            layout: Some(&pipeline_layout),
            vertex: wgpu::VertexState {
                module: &vs_module,
                entry_point: "main",
                buffers: &[],
                compilation_options: Default::default(),
            },
            fragment: Some(wgpu::FragmentState {
                module: &fs_module,
                entry_point: "main",
                targets: &[Some(wgpu::ColorTargetState {
                    format: wgpu::TextureFormat::Rgba8Unorm,
                    blend: None,
                    write_mask: wgpu::ColorWrites::ALL,
                })],
                compilation_options: Default::default(),
            }),
            primitive: wgpu::PrimitiveState::default(),
            depth_stencil: None,
            multisample: wgpu::MultisampleState::default(),
            multiview: None,
            cache: None,
        });

    let mut encoder = ctx
        .device
        .create_command_encoder(&wgpu::CommandEncoderDescriptor { label: None });
    {
        let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
            label: None,
            color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                view: output.view(),
                resolve_target: None,
                ops: wgpu::Operations {
                    load: wgpu::LoadOp::Clear(wgpu::Color::BLACK),
                    store: wgpu::StoreOp::Store,
                },
            })],
            depth_stencil_attachment: None,
            timestamp_writes: None,
            occlusion_query_set: None,
        });
        pass.set_pipeline(&pipeline);
        pass.set_bind_group(0, &bind_group, &[]);
        pass.draw(0..3, 0..1);
    }
    ctx.queue.submit(std::iter::once(encoder.finish()));
    Ok(())
}

/// Local copy of `gpu.rs`'s private `FULLSCREEN_VERTEX_GLSL` (not `pub`
/// there, so not reachable from this module) — same Y-flip-aware fullscreen
/// triangle, byte-for-byte, since this pass needs its own pipeline (see
/// [`render_glsl_with_ref_orbit`]) rather than the shared one.
const FULLSCREEN_VERTEX_GLSL: &str = r#"
#version 450 core
layout(location = 0) out vec2 vUv;
void main() {
  vec2 pos[3] = vec2[3](
    vec2(-1.0, -1.0),
    vec2(3.0, -1.0),
    vec2(-1.0, 3.0)
  );
  vUv = vec2(pos[gl_VertexIndex].x * 0.5 + 0.5, 0.5 - pos[gl_VertexIndex].y * 0.5);
  gl_Position = vec4(pos[gl_VertexIndex], 0.0, 1.0);
}
"#;

const JULIA_PERTURBED_GLSL: &str = r#"
#version 450 core
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 fragColor;

layout(std140, set = 0, binding = 0) uniform Common {
  float TIME;
  float TIMEDELTA;
  vec2 RENDERSIZE;
  int PASSINDEX;
  int FRAMEINDEX;
  vec4 DATE;
};
layout(std140, set = 0, binding = 1) uniform Inputs { vec4 slot[5]; };
layout(set = 0, binding = 2) uniform texture2D uRefOrbitTex;
layout(set = 0, binding = 3) uniform sampler uRefOrbitSamp;

const int MAX_ITER = 192;
const vec3 VOID_COLOR = vec3(0.03, 0.025, 0.05);

// Inigo Quilez cosine-gradient palette: color(t) = a + b*cos(2pi*(c*t+d)).
// Replaces the earlier single-frequency rainbow rotation (all three
// channels sharing the same frequency and near-equal phase offsets, which
// read as "muddy/illegible" — one desaturated hue smearing across the
// whole escape-time ramp rather than real color variety). Distinct
// per-channel frequencies (`c` below) mean the three channels drift in
// and out of phase with each other as smoothIter grows, producing genuine
// multi-hue contrast (not just a rotating tint of one hue). `hueShift`
// (driven by real audio — SignalBus::chroma_root_hue) and `paletteFlip`
// (a continuous audio-modulated shimmer phase) both land in `d`, the
// gradient's phase offset — safe, direct per-frame parameters, not a time
// argument being scaled.
vec3 palette(float smoothIter, float hueShift, float paletteMix, float paletteFlip, vec3 accent) {
  vec3 a = vec3(0.55, 0.50, 0.55);
  vec3 b = vec3(0.45, 0.45, 0.50);
  vec3 pc = vec3(1.00, 1.15, 0.80);
  vec3 d = vec3(0.00, 0.12, 0.50) + hueShift + paletteFlip * 0.5;
  // sqrt-compressed band argument, not linear in smoothIter: deep interior-
  // adjacent detail (found by rendering and looking — a real problem, not
  // a guess) can reach smoothIter close to MAX_ITER=192, and a *linear*
  // band argument there cycles through dozens of full hue rotations
  // across a handful of screen pixels — every pixel a different band,
  // reading as multicolor confetti/static, not a legible gradient. sqrt
  // compresses the high end so distant/deep detail bands slowly while
  // near-boundary detail (low smoothIter, where the real contour rings
  // live) still gets full-frequency variation.
  float bandArg = sqrt(max(smoothIter, 0.0)) * 0.55;
  // Screen-space derivative-based anti-aliasing: sub-pixel fractal detail
  // (fine self-similar filigree finer than one screen pixel, found
  // rendering a shallow-zoom view and looking) makes bandArg swing wildly
  // between neighboring pixels, which a naive cosine gradient reads as
  // harsh multicolor confetti/static rather than a legible band. `fwidth`
  // measures exactly that per-pixel rate of change; damping amplitude
  // where it's high (real screen-space aliasing) while leaving it
  // untouched everywhere the gradient varies smoothly is the standard
  // fix — and, unlike an earlier attempt that faded amplitude by absolute
  // iteration count instead (reverted: broke both deep-zoom perturbation
  // tests below, since a well-resolved deep zoom's real detail can
  // legitimately sit at high iteration counts too — smoothIter alone
  // can't tell "sub-pixel aliasing" from "real, smoothly-varying deep
  // detail," only its screen-space derivative can), this doesn't
  // wrongly flatten deep zoom's legitimately high but smoothly-varying
  // iteration counts.
  // Floored (0.35 min, was an unfloored 0/1 fade): real render stats found
  // this session (256x256 substrate-only luminance histogram) showed a
  // washed/murky look was mostly THIS damping, not the band formula itself
  // — most on-screen fractal detail sits in self-similar, high-derivative
  // territory, so the unfloored fade pushed the vast majority of visible
  // pixels toward flat mid-gray `a` (std as low as ~11/255, far below a
  // legible render's spread). A floor keeps the worst true aliasing spikes
  // damped while guaranteeing every pixel keeps at least 35% of its real
  // color variation.
  float aaFade = 0.35 + 0.65 / (1.0 + 6.0 * fwidth(bandArg));
  vec3 grad = a + b * aaFade * cos(6.28318 * (pc * bandArg + d));

  vec3 base = VOID_COLOR;
  float edge = smoothstep(3.0, 22.0, smoothIter);
  vec3 banded = mix(base, grad, edge);
  return mix(banded, accent * grad, paletteMix);
}

vec2 cMul(vec2 a, vec2 b) {
  return vec2(a.x * b.x - a.y * b.y, a.x * b.y + a.y * b.x);
}

void main() {
  vec2 pan = slot[1].xy;
  float aspect = slot[2].x;
  float zoom = slot[2].y;
  vec3 accent = slot[3].xyz;
  float hueShift = slot[4].x;
  float paletteMix = slot[4].y;
  float paletteFlip = slot[4].z;
  float flash = slot[4].w;

  vec2 uv = vUv * 2.0 - 1.0;
  uv.x *= aspect;
  uv = vec2(-uv.y, uv.x);

  // dz0 = z0 - Z0 = (pan + uv*zoom) - pan = uv*zoom: small regardless of
  // absolute zoom depth, which is exactly why iterating this delta (not
  // the full point) in float32 stays accurate deep past where direct
  // iteration of the full point loses precision.
  vec2 delta = uv * zoom;
  int iter = 0;
  vec2 full = pan + delta;
  for (int i = 0; i < MAX_ITER; i++) {
    vec2 Zi = texelFetch(sampler2D(uRefOrbitTex, uRefOrbitSamp), ivec2(i, 0), 0).xy;
    full = Zi + delta;
    if (dot(full, full) > 4.0) { break; }
    delta = 2.0 * cMul(Zi, delta) + cMul(delta, delta);
    iter++;
  }

  vec3 color;
  if (iter >= MAX_ITER) {
    color = VOID_COLOR;
  } else {
    float logZn = log(dot(full, full)) * 0.5;
    float nu = log(logZn / log(2.0)) / log(2.0);
    float smoothIter = float(iter) + 1.0 - nu;
    color = palette(smoothIter, hueShift, paletteMix, paletteFlip, accent);
  }
  color = mix(color, vec3(0.0), flash);
  fragColor = vec4(color, 1.0);
}
"#;

const JULIA_GLSL: &str = r#"
#version 450 core
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 fragColor;

layout(std140, set = 0, binding = 0) uniform Common {
  float TIME;
  float TIMEDELTA;
  vec2 RENDERSIZE;
  int PASSINDEX;
  int FRAMEINDEX;
  vec4 DATE;
};
layout(std140, set = 0, binding = 1) uniform Inputs { vec4 slot[5]; };

const int MAX_ITER = 192;
// Shared by both the interior (never-escapes) and far-background
// (near-instant-escape) cases so a deep zoom into the interior "void" and
// a huge zoomed-out view (mostly background) read as the exact same color
// — the seamless cut the zoom-cycle reset relies on (see driven_by_time).
const vec3 VOID_COLOR = vec3(0.03, 0.025, 0.05);

// ponytail: was a single linear crossfade against normalized t (MAX_ITER-relative),
// which made the whole exterior near-black except a sliver right at the boundary
// and the whole interior one flat saturated color (illegible blob, no fractal
// detail visible). Real fix: band color cyclically off the *absolute* smooth
// escape count (classic escape-time coloring) so contour rings show up well
// before MAX_ITER, and fade in from black near instant-escape pixels instead of
// needing near-MAX_ITER to show any color at all.
// Inigo Quilez cosine-gradient palette: color(t) = a + b*cos(2pi*(c*t+d)).
// Replaces the earlier single-frequency rainbow rotation (all three
// channels sharing the same frequency and near-equal phase offsets, which
// read as "muddy/illegible" — one desaturated hue smearing across the
// whole escape-time ramp rather than real color variety). Distinct
// per-channel frequencies (`c` below) mean the three channels drift in
// and out of phase with each other as smoothIter grows, producing genuine
// multi-hue contrast (not just a rotating tint of one hue). `hueShift`
// (driven by real audio — SignalBus::chroma_root_hue) and `paletteFlip`
// (a continuous audio-modulated shimmer phase) both land in `d`, the
// gradient's phase offset — safe, direct per-frame parameters, not a time
// argument being scaled.
//
// Narrow ramp (was 0..6, colored almost the whole exterior): most
// background pixels escape in 1-2 iterations, so a wide ramp fed a lot of
// color energy into the memory-field accumulator every frame from pixels
// nowhere near the fractal boundary, which is most of what was compounding
// into a saturated wash over many frames. 3..22 keeps true background
// near-black and only lights up the real boundary halo.
vec3 palette(float smoothIter, float hueShift, float paletteMix, float paletteFlip, vec3 accent) {
  vec3 a = vec3(0.55, 0.50, 0.55);
  vec3 b = vec3(0.45, 0.45, 0.50);
  vec3 pc = vec3(1.00, 1.15, 0.80);
  vec3 d = vec3(0.00, 0.12, 0.50) + hueShift + paletteFlip * 0.5;
  // sqrt-compressed band argument, not linear in smoothIter: deep interior-
  // adjacent detail (found by rendering and looking — a real problem, not
  // a guess) can reach smoothIter close to MAX_ITER=192, and a *linear*
  // band argument there cycles through dozens of full hue rotations
  // across a handful of screen pixels — every pixel a different band,
  // reading as multicolor confetti/static, not a legible gradient. sqrt
  // compresses the high end so distant/deep detail bands slowly while
  // near-boundary detail (low smoothIter, where the real contour rings
  // live) still gets full-frequency variation.
  float bandArg = sqrt(max(smoothIter, 0.0)) * 0.55;
  // Screen-space derivative-based anti-aliasing: sub-pixel fractal detail
  // (fine self-similar filigree finer than one screen pixel, found
  // rendering a shallow-zoom view and looking) makes bandArg swing wildly
  // between neighboring pixels, which a naive cosine gradient reads as
  // harsh multicolor confetti/static rather than a legible band. `fwidth`
  // measures exactly that per-pixel rate of change; damping amplitude
  // where it's high (real screen-space aliasing) while leaving it
  // untouched everywhere the gradient varies smoothly is the standard
  // fix — and, unlike an earlier attempt that faded amplitude by absolute
  // iteration count instead (reverted: broke both deep-zoom perturbation
  // tests below, since a well-resolved deep zoom's real detail can
  // legitimately sit at high iteration counts too — smoothIter alone
  // can't tell "sub-pixel aliasing" from "real, smoothly-varying deep
  // detail," only its screen-space derivative can), this doesn't
  // wrongly flatten deep zoom's legitimately high but smoothly-varying
  // iteration counts.
  // Floored 0.35 min — see JULIA_PERTURBED_GLSL's identical fix, same
  // washed/murky root cause found via real luminance-histogram stats.
  float aaFade = 0.35 + 0.65 / (1.0 + 6.0 * fwidth(bandArg));
  vec3 grad = a + b * aaFade * cos(6.28318 * (pc * bandArg + d));

  vec3 base = VOID_COLOR;
  float edge = smoothstep(3.0, 22.0, smoothIter);
  vec3 banded = mix(base, grad, edge);
  return mix(banded, accent * grad, paletteMix);
}

void main() {
  vec2 c = slot[0].xy;
  vec2 pan = slot[1].xy;
  float aspect = slot[2].x;
  float zoom = slot[2].y;
  vec3 accent = slot[3].xyz;
  float hueShift = slot[4].x;
  float paletteMix = slot[4].y;
  float paletteFlip = slot[4].z;
  float flash = slot[4].w;

  vec2 uv = vUv * 2.0 - 1.0;
  uv.x *= aspect;
  uv = vec2(-uv.y, uv.x);

  vec2 z = pan + uv * zoom;
  int iter = 0;
  for (int i = 0; i < MAX_ITER; i++) {
    if (dot(z, z) > 4.0) { break; }
    z = vec2(z.x * z.x - z.y * z.y, 2.0 * z.x * z.y) + c;
    iter++;
  }

  vec3 color;
  if (iter >= MAX_ITER) {
    // Interior (never escapes): no escape-time detail to show here, keep it
    // dark per convention — the real complexity lives just outside this.
    color = VOID_COLOR;
  } else {
    float logZn = log(dot(z, z)) * 0.5;
    float nu = log(logZn / log(2.0)) / log(2.0);
    float smoothIter = float(iter) + 1.0 - nu;
    color = palette(smoothIter, hueShift, paletteMix, paletteFlip, accent);
  }
  color = mix(color, vec3(0.0), flash);
  fragColor = vec4(color, 1.0);
}
"#;

#[cfg(test)]
mod tests {
    use super::*;

    /// Real, numeric stand-in for the manual visual review this session
    /// actually did (rendered a 512x512 preview across several
    /// `hue_shift` values, viewed the PNGs, and iterated the palette
    /// formula/band-argument scaling until confetti-like aliasing in deep
    /// mini-fractal thickets faded gracefully instead of reading as
    /// noise) — asserts the same two things by eye-check found true:
    /// real multi-hue variety (not a muddy near-single-color render), and
    /// a real recolor when `hue_shift` (driven by `chroma_root_hue` in
    /// [`JuliaDriver`]) changes.
    #[test]
    fn palette_shows_real_multi_hue_variety_and_responds_to_hue_shift() {
        let ctx = match GpuContext::new_blocking() {
            Ok(c) => c,
            Err(_) => return,
        };
        let target = OffscreenTarget::new(&ctx, 128, 128);
        let c = [-0.4f32, 0.6];
        let pan = find_interesting_pan(c);
        let base = JuliaNavState {
            c,
            pan,
            zoom: 1.2,
            palette_mix: 0.5,
            accent: [1.0, 0.55, 0.25],
            ..JuliaNavState::default()
        };

        render_julia(
            &ctx,
            &target,
            &JuliaNavState {
                hue_shift: 0.0,
                ..base
            },
            1.0,
        )
        .unwrap();
        let frame_a = target.read_pixels(&ctx).unwrap();
        let distinct_a = distinct_color_count(&frame_a);
        assert!(distinct_a > 500, "palette should show real multi-hue variety, not a muddy near-flat render, got {distinct_a} distinct colors");

        render_julia(
            &ctx,
            &target,
            &JuliaNavState {
                hue_shift: 0.5,
                ..base
            },
            1.0,
        )
        .unwrap();
        let frame_b = target.read_pixels(&ctx).unwrap();
        let changed = frame_a
            .chunks(4)
            .zip(frame_b.chunks(4))
            .filter(|(a, b)| {
                a.iter()
                    .zip(*b)
                    .any(|(x, y)| (*x as i32 - *y as i32).abs() > 10)
            })
            .count();
        assert!(changed > 100, "chroma_root_hue (hue_shift) should visibly recolor a real number of pixels, got {changed}");
    }

    #[test]
    fn renders_and_responds_to_a_changing_c() {
        let ctx = match GpuContext::new_blocking() {
            Ok(c) => c,
            Err(_) => return,
        };
        let target = OffscreenTarget::new(&ctx, 64, 64);

        render_julia(&ctx, &target, &JuliaNavState::driven_by_time(0.0), 1.0).unwrap();
        let frame0 = target.read_pixels(&ctx).unwrap();
        render_julia(&ctx, &target, &JuliaNavState::driven_by_time(5.0), 1.0).unwrap();
        let frame_later = target.read_pixels(&ctx).unwrap();

        // Most of a zoomed-out Julia view escapes in 0 iterations (uniform
        // background), which dilutes a whole-frame mean delta near to zero
        // regardless of a real change in `c` — the fractal's actual boundary
        // detail only occupies a fraction of the pixels. Count pixels whose
        // color visibly changed instead of averaging over mostly-background.
        let changed = frame0
            .chunks(4)
            .zip(frame_later.chunks(4))
            .filter(|(a, b)| {
                a.iter()
                    .zip(*b)
                    .any(|(x, y)| (*x as i32 - *y as i32).abs() > 10)
            })
            .count();
        assert!(changed > 20, "changing c should visibly change a real number of pixels (fractal boundary detail), got {changed}");
    }

    fn distinct_color_count(pixels: &[u8]) -> usize {
        use std::collections::HashSet;
        pixels
            .chunks(4)
            .map(|p| (p[0], p[1], p[2], p[3]))
            .collect::<HashSet<_>>()
            .len()
    }

    /// The real, biting verification the perturbation path exists for:
    /// render the SAME deep-zoom view through both `render_julia` (direct
    /// iteration) and `render_julia_perturbed`, and assert direct iteration
    /// actually shows its known precision-loss signature (collapses to a
    /// single flat color — no escape-time detail left at all) while
    /// perturbation, at the identical `zoom=1e-8`, shows genuine smooth
    /// variation (over a thousand distinct values in the probe run that
    /// produced this test). Real numbers found probing a whole range of
    /// depths at this `pan`/`c` (64x64, `MAX_ITER=192`): direct iteration
    /// stays plausible through `zoom=1e-6` (719 distinct colors), visibly
    /// degrades by `1e-7` (23 distinct), and is fully degenerate (1 color)
    /// by `1e-8` — the actual empirical breakdown point, not a guess.
    #[test]
    fn direct_iteration_loses_precision_at_deep_zoom_perturbation_does_not() {
        let ctx = match GpuContext::new_blocking() {
            Ok(c) => c,
            Err(_) => return,
        };
        let target = OffscreenTarget::new(&ctx, 64, 64);
        let c = [-0.4f32, 0.6];
        let pan = find_interesting_pan(c);
        let deep = JuliaNavState {
            c,
            pan,
            zoom: 1e-8,
            ..JuliaNavState::default()
        };

        render_julia(&ctx, &target, &deep, 1.0).unwrap();
        let direct_pixels = target.read_pixels(&ctx).unwrap();
        let direct_distinct = distinct_color_count(&direct_pixels);

        render_julia_perturbed(&ctx, &target, &deep, 1.0).unwrap();
        let perturbed_pixels = target.read_pixels(&ctx).unwrap();
        let perturbed_distinct = distinct_color_count(&perturbed_pixels);

        assert!(
            direct_distinct <= 4,
            "direct iteration at zoom=1e-8 should show its known precision-loss signature (collapses to a flat/near-flat render, empirically 1 distinct color), got {direct_distinct} distinct colors"
        );
        assert!(
            perturbed_distinct >= direct_distinct * 100,
            "perturbation at the same zoom=1e-8 should show real escape-time gradation, not the direct path's collapse: direct={direct_distinct}, perturbed={perturbed_distinct}"
        );
        assert!(perturbed_distinct > 500, "perturbation should show a meaningfully large number of distinct values comparable to a shallow zoom, got {perturbed_distinct}");
    }

    /// Pushes to `zoom=1e-9` — a real number found probing this session
    /// (991 distinct colors, still comparable to a shallow zoom), one order
    /// of magnitude past where direct iteration is already fully
    /// degenerate. See [`render_julia_perturbed`]'s doc for where
    /// perturbation's *own* breakdown point actually sits (empirically
    /// `zoom=1e-10` in the same probe, and *why*: not the reference
    /// orbit's f64 precision as originally hypothesized, but the shader's
    /// escape-check addition `Zi + delta` losing `delta` entirely once it's
    /// far enough below float32's relative precision near `Zi`'s O(1)
    /// magnitude).
    #[test]
    fn perturbation_stays_sharp_at_an_even_deeper_zoom() {
        let ctx = match GpuContext::new_blocking() {
            Ok(c) => c,
            Err(_) => return,
        };
        let target = OffscreenTarget::new(&ctx, 64, 64);
        let c = [-0.4f32, 0.6];
        let pan = find_interesting_pan(c);
        let deeper = JuliaNavState {
            c,
            pan,
            zoom: 1e-9,
            ..JuliaNavState::default()
        };

        render_julia_perturbed(&ctx, &target, &deeper, 1.0).unwrap();
        let pixels = target.read_pixels(&ctx).unwrap();
        let distinct = distinct_color_count(&pixels);
        assert!(distinct > 500, "perturbation at zoom=1e-9 should still show real gradation comparable to a shallow zoom, got {distinct} distinct colors");
    }

    /// Confirms the reference orbit is genuinely computed once per frame
    /// (once per `render_julia_perturbed` call) and reused across every
    /// pixel — not recomputed per pixel — by counting real calls to
    /// `compute_reference_orbit` around one render at 128x128 (16384
    /// pixels): if it were (incorrectly) recomputed per pixel, the call
    /// count would track pixel count, not frame count.
    #[test]
    fn reference_orbit_is_computed_once_per_frame_not_per_pixel() {
        let ctx = match GpuContext::new_blocking() {
            Ok(c) => c,
            Err(_) => return,
        };
        let target = OffscreenTarget::new(&ctx, 128, 128);
        let c = [-0.4f32, 0.6];
        let pan = find_interesting_pan(c);
        let state = JuliaNavState {
            c,
            pan,
            zoom: 1e-6,
            ..JuliaNavState::default()
        };

        let before = REF_ORBIT_COMPUTE_CALLS.load(Ordering::Relaxed);
        render_julia_perturbed(&ctx, &target, &state, 1.0).unwrap();
        let after = REF_ORBIT_COMPUTE_CALLS.load(Ordering::Relaxed);

        assert_eq!(after - before, 1, "one render_julia_perturbed call should compute the reference orbit exactly once, regardless of pixel count (16384 here)");
    }

    /// The exact bug class this driver is built to avoid (see its own doc
    /// and AGENTS.md's dated "Mandelbulb phase-warp bug fixed" entry):
    /// scaling a monotonic time/phase argument by a jittery audio value
    /// makes it jump non-monotonically frame to frame. Drives
    /// `JuliaDriver` with a deliberately adversarial, wildly-jittering
    /// `energy` signal (alternating near-0 and near-1 every frame, the
    /// worst case for exposing this bug) at a fixed real `dt`, and asserts
    /// `zoom` only ever changes by a bounded amount per frame — the
    /// signature of real rate-integration, not a snap.
    #[test]
    fn driver_zoom_never_snaps_even_under_wildly_jittering_audio() {
        let mut driver = JuliaDriver::new();
        let dt = 1.0 / 30.0;
        let mut prev = driver.update(dt, &hyst_core::SignalBus::default()).zoom;
        // Worst-case bound: even at the highest possible zoom_rate (energy
        // and onset_density both pinned to 1.0, the max this driver's
        // formula ever produces), one frame's real elapsed dt can only
        // move log-zoom by dt * rate_max — bound the *ratio* zoom can
        // change by per frame accordingly (zoom = ZOOM_DOT*exp(-zoom_log),
        // so a bounded zoom_log step bounds the zoom ratio step).
        let rate_max = BASE_ZOOM_RATE * (0.5 + 0.9 + 0.6);
        let max_log_step = dt * rate_max;
        for i in 0..300 {
            // Alternate near-silent and near-maximal audio every single
            // frame — deliberately adversarial jitter, not a realistic
            // signal, specifically to try to trigger a snap if one exists.
            let mut bus = hyst_core::SignalBus::default();
            if i % 2 == 0 {
                bus.energy = 0.0;
                bus.onset_density = 0.0;
                bus.chroma_root_hue = 0.0;
            } else {
                bus.energy = 1.0;
                bus.onset_density = 1.0;
                bus.chroma_root_hue = 0.9;
            }
            let state = driver.update(dt, &bus);
            // zoom is always positive and finite regardless of jitter.
            assert!(state.zoom.is_finite() && state.zoom > 0.0);
            // Bounded per-frame ratio: log(prev/zoom) or log(zoom/prev)
            // should never exceed the worst-case single-frame log-zoom
            // step, plus generous slack for the one frame a cycle resets
            // (a real, intentional discrete jump back to ZOOM_DOT — not a
            // snap, an explicit designed cut, so skip the assertion on a
            // reset frame: detectable as a zoom *increase* when the
            // previous frame was near ZOOM_VOID).
            let ratio = (state.zoom / prev).ln().abs();
            let is_reset_frame = state.zoom > prev * 2.0;
            assert!(
                is_reset_frame || ratio <= max_log_step + 1e-4,
                "frame {i}: zoom jumped from {prev} to {} (log-ratio {ratio}), exceeding the bounded per-frame rate-integration step {max_log_step} — looks like a snap",
                state.zoom
            );
            prev = state.zoom;
        }
    }

    /// `zoom_rate`/`c_speed`/`color_phase` all vary with audio, but
    /// `JuliaDriver` should still visibly evolve frame to frame even under
    /// completely silent/default audio (a real per-frame integration, not
    /// something that only moves when audio pushes it) — a stand-in for
    /// the "too static" complaint this driver replaces `driven_by_time`
    /// to fix.
    #[test]
    fn driver_state_changes_frame_to_frame_even_under_silence() {
        let mut driver = JuliaDriver::new();
        let dt = 1.0 / 30.0;
        let silence = hyst_core::SignalBus::default();
        let a = driver.update(dt, &silence);
        let b = driver.update(dt, &silence);
        assert_ne!(a.zoom, b.zoom, "zoom should keep diving even under silence");
        assert_ne!(
            a.c, b.c,
            "the c-orbit should keep moving even under silence"
        );
    }

    /// Task 1: a real continuous dive for the whole clip, not a short
    /// repeating loop. Drives `JuliaDriver` for 90s at 30fps (2700 frames,
    /// the demo's own real clip length/rate) under moderate constant audio
    /// and asserts zoom crosses several full orders of magnitude of real
    /// depth (well past ZOOM_DOT, i.e. real dive progress) without ever
    /// resetting all the way back to a shallow zoom — the exact "dive, snap
    /// back to fully zoomed out, repeat" behavior reported as the bug.
    #[test]
    fn driver_reaches_real_depth_over_a_full_clip_without_looping_back_shallow() {
        let mut driver = JuliaDriver::new();
        let dt = 1.0 / 30.0;
        let bus = hyst_core::SignalBus {
            energy: 0.5,
            onset_density: 0.3,
            chroma_root_hue: 0.4,
            ..hyst_core::SignalBus::default()
        };
        let mut min_zoom = f32::MAX;
        let mut resets = 0u32;
        let mut prev = ZOOM_DOT;
        for _ in 0..2700 {
            let state = driver.update(dt, &bus);
            if state.zoom > prev * 2.0 {
                resets += 1;
            }
            prev = state.zoom;
            min_zoom = min_zoom.min(state.zoom);
        }
        assert!(
            min_zoom < 1e-3,
            "a real 90s clip should reach real depth (perturbation-worthy zoom), got min zoom {min_zoom}"
        );
        assert!(
            resets <= 1,
            "a real 90s clip at this driver's rate range should cut to a fresh dive at most once, not repeatedly loop back shallow — got {resets} resets"
        );
    }

    /// Round 2, problem #2: `c`'s per-frame motion must NOT blow up as the
    /// zoom deepens (the old design grew the orbit radius with depth, which
    /// — with the fractal boundary's ~1/zoom sensitivity to `c` — is what
    /// read as "INCREDIBLY twitchy"). Asserts the per-frame `|Δc|` late in a
    /// deep dive is no larger than early on, stays under the hard cap, and
    /// is never a spike, under a deliberately jittery `energy` signal.
    #[test]
    fn c_per_frame_motion_stays_bounded_and_does_not_explode_at_depth() {
        let dt = 1.0 / 30.0;
        let mut driver = JuliaDriver::new();
        let mut early_max = 0.0f32;
        let mut late_max = 0.0f32;
        let mut prev_c = driver.update(dt, &jitter_bus(0)).c;
        for i in 1..2400u32 {
            let c = driver.update(dt, &jitter_bus(i)).c;
            let d = ((c[0] - prev_c[0]).powi(2) + (c[1] - prev_c[1]).powi(2)).sqrt();
            prev_c = c;
            // never exceed the hard per-frame cap (+ float slack)
            assert!(
                d <= MAX_C_STEP + 1e-5,
                "frame {i}: |Δc| = {d} exceeded the hard cap {MAX_C_STEP} — a c-snap"
            );
            if i < 300 {
                early_max = early_max.max(d);
            } else if i > 2000 {
                late_max = late_max.max(d);
            }
        }
        assert!(
            late_max <= early_max * 1.2 + 1e-6,
            "deep-dive c-motion must not blow up vs. early: early_max={early_max}, late_max={late_max}"
        );
    }

    fn jitter_bus(i: u32) -> hyst_core::SignalBus {
        // adversarial: energy/centroid/flatness slam between extremes every
        // frame — the worst case for any raw-audio-driven twitch.
        let hi = i % 2 == 0;
        hyst_core::SignalBus {
            energy: if hi { 0.95 } else { 0.02 },
            centroid: if hi { 0.9 } else { 0.1 },
            flatness: if hi { 0.8 } else { 0.05 },
            chroma_root_hue: if hi { 0.85 } else { 0.1 },
            onset_density: if hi { 0.9 } else { 0.0 },
            ..hyst_core::SignalBus::default()
        }
    }

    /// Round 2, problem #1: the zoom centre must keep tracking the fractal
    /// boundary for the whole dive, not drift off it into a solid basin
    /// (the "after ~13s its fully one color" bug — a fixed `pan` probed once
    /// at construction). Runs `JuliaDriver` through a deep dive and, at
    /// several points, samples the escape-time field across the current view
    /// in f64: a framed boundary shows a wide spread of escape counts
    /// (fast-escaping exterior next to deep interior); a dead basin shows
    /// near-zero spread.
    #[test]
    fn driver_keeps_the_boundary_framed_through_a_deep_dive() {
        let mut driver = JuliaDriver::new();
        let dt = 1.0 / 30.0;
        let bus = hyst_core::SignalBus {
            energy: 0.5,
            chroma_root_hue: 0.3,
            ..hyst_core::SignalBus::default()
        };
        let mut worst_spread = u32::MAX;
        for frame in 0..2000u32 {
            let s = driver.update(dt, &bus);
            if frame % 200 == 199 {
                let cf = [s.c[0] as f64, s.c[1] as f64];
                let (mut lo, mut hi) = (192u32, 0u32);
                const G: i32 = 9;
                for i in 0..G {
                    for j in 0..G {
                        let fx = (i as f64 + 0.5) / G as f64 * 2.0 - 1.0;
                        let fy = (j as f64 + 0.5) / G as f64 * 2.0 - 1.0;
                        let p = [
                            s.pan[0] as f64 + fx * s.zoom as f64 * 0.8,
                            s.pan[1] as f64 + fy * s.zoom as f64 * 0.8,
                        ];
                        let it = escape_iters_f64(p, cf);
                        lo = lo.min(it);
                        hi = hi.max(it);
                    }
                }
                let spread = hi - lo;
                worst_spread = worst_spread.min(spread);
                assert!(
                    spread > 15,
                    "frame {frame} (zoom {}): view collapsed to a near-uniform region (escape spread {spread}) — boundary steering failed",
                    s.zoom
                );
            }
        }
        assert!(
            worst_spread > 15,
            "worst spread over the dive was {worst_spread}"
        );
    }

    /// Task 3: the anti-alias fade floor (see `palette`'s own doc — an
    /// unfloored fade was found this session to flatten most on-screen
    /// fractal detail toward mid-gray, reading as washed/murky) should keep
    /// real, measurable contrast (luminance standard deviation) in a real
    /// render, not just a mathematically-nonzero one. Renders one
    /// representative deep-ish view and asserts the luminance spread clears
    /// a real bar.
    #[test]
    fn palette_keeps_real_contrast_not_a_flat_wash() {
        let ctx = match GpuContext::new_blocking() {
            Ok(c) => c,
            Err(_) => return,
        };
        let target = OffscreenTarget::new(&ctx, 128, 128);
        let c = [-0.4f32, 0.6];
        let pan = find_interesting_pan(c);
        let state = JuliaNavState {
            c,
            pan,
            zoom: 0.6,
            palette_mix: 0.4,
            accent: [1.0, 0.55, 0.25],
            ..JuliaNavState::default()
        };
        render_julia(&ctx, &target, &state, 1.0).unwrap();
        let pixels = target.read_pixels(&ctx).unwrap();
        let lum: Vec<f64> = pixels
            .chunks(4)
            .map(|p| 0.2126 * p[0] as f64 + 0.7152 * p[1] as f64 + 0.0722 * p[2] as f64)
            .collect();
        let mean = lum.iter().sum::<f64>() / lum.len() as f64;
        let var = lum.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / lum.len() as f64;
        let std = var.sqrt();
        assert!(
            std > 8.0,
            "palette should show real luminance contrast across the frame, got std={std:.2} (mean={mean:.2})"
        );
    }
}
