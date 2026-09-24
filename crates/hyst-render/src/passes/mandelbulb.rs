//! Raymarched 3D Mandelbulb — ported from the frozen TS reference's
//! never-shipped-to-production landing-hero scene:
//! `src/render/worker/scenes/mandelbulb/MandelbulbScene.ts` +
//! `shaders/mandelbulb.frag.glsl`. That scene existed only as an optional
//! swap-in for a dedicated landing canvas (WebGL2 could just barely afford
//! it for a non-persistent hero shot) — this native `wgpu` rewrite has real
//! GPU raymarching headroom the WebGL2-constrained original didn't, so this
//! is a chance to make the fractal substrate itself more visually striking
//! than the 2D Julia set, not just a faithful port of a shelved experiment.
//!
//! **Ported**: the distance-estimated (DE) Mandelbulb formula (power-N
//! spherical iteration with the standard `dr` derivative-tracking trick for
//! turning the escape radius into a real surface distance bound), the
//! sphere-tracing raymarch loop (step by the DE value until within an
//! epsilon of the surface, or a step/distance budget runs out), and the
//! `rotateY` camera orbit.
//!
//! **Quality pass #1** (post-hoc, after "too low-res, jittery... looks like
//! a 3D print"): real central-difference surface normals + Lambertian
//! diffuse + a cheap ambient-occlusion approximation, a tightened surface
//! epsilon, a raised step budget, and 9x supersampling.
//!
//! **Quality pass #2, this session** (after "the mandelbulb is bad, we
//! should zoom in deep... also the palette is very bad and illegible"):
//!
//! - **A real deep dive**, not a shallow breathe. [`MandelbulbDiveDriver`]
//!   (a stateful, `dt`-integrated driver, replacing the old stateless
//!   `driven_by_time(t)` as the thing examples actually drive with) dives
//!   the camera from a wide establishing shot down to
//!   [`MandelbulbDiveDriver::DIST_NEAR`] — a real, empirically-chosen ~2x
//!   closer than the old `DIST_NEAR=2.3`, and specifically verified safe
//!   across a **full rotation sweep**, not just one baseline angle (a
//!   real bug found by rendering the full clip: `0.75`, picked against a
//!   single fixed test angle, embedded the camera in solid material at
//!   ~60% of rotation angles, producing single-frame flat-color "flash"
//!   pops — see the struct doc for the real numbers) — then eases back
//!   out, in a continuous log-distance oscillation with no snap (see the
//!   struct doc for why a hard Julia-style dive-then-reset still doesn't
//!   apply to a 3D camera).
//! - **Adaptive surface epsilon** (`surfaceEps` in the shader): a fixed
//!   epsilon that was fine at distance 3 is either too coarse (holes/noise)
//!   or needlessly fine (wasted steps) at distance 0.7 — epsilon now scales
//!   with camera distance, clamped to a real measured-safe range (see
//!   [`MandelbulbDiveDriver`] doc for the numbers).
//! - **A real multi-hue palette.** The old shading multiplied a single
//!   fixed `accent` color by a lighting scalar — "illegible" because every
//!   lit pixel was the same hue at different brightness. Replaced with an
//!   Inigo-Quilez-style cosine palette (`color(t) = a + b*cos(2pi*(c*t+d))`)
//!   whose input `t` combines a real **smooth escape-iteration count** (a
//!   continuous per-pixel value derived from the DE iteration at the hit
//!   point — the standard Mandelbrot-family coloring technique, adapted to
//!   3D; an orbit-trap value was tried first and rejected — see
//!   `mandelbulbDE`'s own doc for why it stayed nearly flat across a real
//!   visible surface patch) with a hue-rotation term driven by
//!   `hyst_core::SignalBus::chroma_root_hue` (via [`MandelbulbDiveDriver`])
//!   so the color genuinely shifts with the music's harmonic content.
//!
//! **Not ported** (out of scope, same boundary `JuliaNavState`'s own doc
//! draws for R6): the TS scene's `update(dt, params)` binding of `power` to
//! an audio `windup` param and `setQuality` step-budget scaling for a
//! degraded-perf path.
//!
//! **Not wired into `renderer.rs`'s pipeline this session** — see this
//! crate's README for exactly what full integration (composite/bloom
//! compatibility, whether the memory-field ping-pong concept even applies
//! to a 3D raymarched scene) would need.

use crate::gpu::{GpuContext, GpuError, OffscreenTarget};
use crate::passes::{pack_slots, CommonUniforms};

/// Whatever the shader needs as uniforms, chosen to match what the GLSL
/// below actually reads (`uPower`/`uRotation`/`uMaxSteps`/`uHueShift`/
/// `uFlash`, plus a `distance` field standing in for the original's
/// hardcoded `ro = vec3(0,0,-3)` camera so a caller/test can push the
/// camera arbitrarily close to or far from the fractal). Plain uniform
/// bag, no navigation logic — see module doc; [`MandelbulbDiveDriver`] is
/// the thing that actually owns navigation state now.
#[derive(Clone, Copy, Debug)]
pub struct MandelbulbNavState {
    /// Camera distance from the origin along the pre-rotation -Z axis
    /// (the TS original hardcodes this at 3.0 via `ro = vec3(0,0,-3)`).
    pub distance: f32,
    /// Orbit angle (radians) the camera and its view ray are rotated by
    /// around the Y axis — the original's `uRotation`.
    pub rotation: f32,
    /// Mandelbulb power exponent — the original's `uPower`, base 8.0.
    pub power: f32,
    /// Raymarch step budget — the original's `uMaxSteps` ranged 70-160;
    /// raised to 220 in the first quality pass, and now driven higher still
    /// as the camera dives close (see [`MandelbulbDiveDriver::update`]).
    pub max_steps: i32,
    /// Palette hue-rotation input, 0..1, fed into the shader's cosine
    /// palette (see module doc). [`MandelbulbDiveDriver`] derives this from
    /// a slow independent drift plus a smoothed pull toward
    /// `SignalBus::chroma_root_hue`.
    pub hue_shift: f32,
    /// Beat-driven brightness pulse, 0..1, multiplies the final shaded
    /// color (replaces the old flat `accent * flash` multiply).
    pub flash: f32,
}

impl Default for MandelbulbNavState {
    fn default() -> Self {
        Self {
            distance: 3.0,
            rotation: 0.0,
            power: 8.0,
            max_steps: 220,
            hue_shift: 0.0,
            flash: 0.0,
        }
    }
}

impl MandelbulbNavState {
    /// Deterministic test/demo driver: orbits the camera around the Y axis
    /// at `ROTATION_SPEED_BASE` and dollies through the same deep dive
    /// cycle [`MandelbulbDiveDriver`] integrates statefully, but computed
    /// directly as a function of `t` — kept for this module's own
    /// deterministic tests (and any other caller that wants a pure
    /// function of elapsed time, e.g. a quick standalone render) alongside
    /// the newer driver, the same way `JuliaNavState::driven_by_time` is
    /// kept alongside `JuliaDriver`. NOT what `mandelbulb_render.rs` drives
    /// its real per-frame state from any more — see
    /// [`MandelbulbDiveDriver::update`] for that, and this module's own doc
    /// for why a stateless `t`-only function must never have its `t`
    /// argument itself scaled by an audio value (the bug class the prior
    /// session hit and fixed).
    pub fn driven_by_time(t: f32) -> Self {
        const ROTATION_SPEED_BASE: f32 = 0.06;
        let distance = dive_distance_from_log(dive_log_oscillation(t));
        Self {
            distance,
            rotation: t * ROTATION_SPEED_BASE,
            hue_shift: (t * 0.02).rem_euclid(1.0),
            ..Self::default()
        }
    }
}

/// Wide establishing distance — the far end of the dive cycle. Unchanged
/// from the first quality pass's `DIST_FAR`.
const DIST_FAR: f32 = 4.6;
/// Deep end of the dive cycle. **This replaces the old shallow
/// `DIST_NEAR=2.3`** — a real, empirically-chosen ~2x-closer value, tested
/// safe across a full rotation sweep (0/240 angles embedded), not just the
/// single baseline angle an earlier, too-optimistic `0.75` was picked
/// against — see [`MandelbulbDiveDriver`]'s doc for the real numbers and
/// the rendered-clip bug this caught.
const DIST_NEAR: f32 = 1.2;
/// `ln(DIST_FAR / DIST_NEAR)` — the total log-distance range one full
/// dive-in traverses.
fn dive_log_range() -> f32 {
    (DIST_FAR / DIST_NEAR).ln()
}

/// Shared, side-effect-free mapping from an accumulated log-distance value
/// (0 at the far end, `dive_log_range()` at the near end) to a real camera
/// distance — `distance = DIST_FAR * exp(-log_value)`. Log-domain
/// integration (matching `JuliaDriver::zoom_log`'s own shape) so a linear
/// `dt`-driven accumulator produces an exponential, perceptually-uniform
/// dive rather than a linear one that reads as "slow at first, then
/// suddenly all the way in."
fn dive_distance_from_log(log_value: f32) -> f32 {
    DIST_FAR * (-log_value).exp()
}

/// Stateless helper backing [`MandelbulbNavState::driven_by_time`]: a
/// continuous log-distance oscillation as a pure function of `t` — dive in
/// over the first `dive_log_range()/DIVE_RATE` seconds of each cycle, ease
/// back out over the (faster) recede half, repeat. Kept separate from
/// [`MandelbulbDiveDriver`]'s own `update` (which does the same shape but
/// via real `dt` integration with an audio-modulated rate) purely so
/// `driven_by_time` can stay a pure function of `t` for tests/demos that
/// want one.
fn dive_log_oscillation(t: f32) -> f32 {
    const DIVE_RATE: f32 = 0.09;
    const RECEDE_RATE: f32 = 0.22;
    let range = dive_log_range();
    let dive_secs = range / DIVE_RATE;
    let recede_secs = range / RECEDE_RATE;
    let cycle = dive_secs + recede_secs;
    let phase = t.rem_euclid(cycle);
    if phase < dive_secs {
        phase * DIVE_RATE
    } else {
        range - (phase - dive_secs) * RECEDE_RATE
    }
}

/// Stateful, `dt`-integrated camera/color driver — the real navigation
/// [`crate`]'s `examples/mandelbulb_render.rs` advances every frame,
/// matching the architecture `JuliaDriver` (`passes/julia.rs`) uses for the
/// same reason: a struct that owns accumulated phase and is advanced by
/// `update(dt, &SignalBus)` each frame can safely let audio modulate a
/// *rate* being integrated (still monotonic afterward) without ever
/// multiplying the phase/time argument itself by a non-monotonic audio
/// value — see this module's own doc and `AGENTS.md`'s session history for
/// the exact "rotates/zooms, then snaps back" bug that pattern caused here
/// previously.
///
/// **Real empirical numbers behind `DIST_NEAR=1.2`** (measured this
/// session, 128x128, release build, this machine — see the module's
/// `#[cfg(test)]` `dive_depth_probe`/`dive_depth_determinism_probe`/
/// `dive_depth_rotation_sweep_probe` for the exact harnesses). Three real,
/// distinct findings came out of this, including one **real bug caught
/// only by rendering the full clip end to end and diffing every adjacent
/// frame pair** — not caught by the single-baseline-angle sweep below, and
/// not something code review alone would have found:
///
/// **1. Straight-in along -Z runs into the fractal's own solid material,
/// not more fine detail, well before distance reaches zero.** A sweep of
/// fixed camera distances from 3.0 down to 0.15 (rendering 6 consecutive
/// frames per distance, one fixed rotation baseline, with a `0.002 rad`
/// rotation step — one real frame's worth of orbit motion at the driver's
/// actual rotation speed — and diffing adjacent frames, RGBA bytes
/// differing by >10/255, plus each frame's hit-rate, the fraction of
/// pixels registering a surface hit rather than background) found
/// genuinely different regimes, not a smooth continuum:
///
/// | distance | mean frame-diff | worst frame-diff | hit-rate | regime |
/// |----------|------------------|-------------------|----------|--------|
/// | 3.00     | 3.9%             | 4.0%               | 0.28     | establishing shot |
/// | 2.30     | 10.7%            | 10.9%              | 0.55     | old `DIST_NEAR` |
/// | 1.50     | 38.4%            | 38.7%              | 0.97     | full-frame surface |
/// | 1.20     | 45.5%            | 46.0%              | 0.98     | **chosen `DIST_NEAR`** |
/// | 1.00     | 54.5%            | 55.0%              | 0.97     | close, real structure |
/// | 0.90     | 55.3%            | 55.5%              | 0.91     | close, real structure |
/// | 0.80     | 59.0%            | 59.1%              | 0.90     | close, real structure |
/// | 0.75     | 60.8%            | 61.2%              | 0.89     | at this ONE angle, looks fine... |
/// | 0.70     | 44.3%            | 46.5%              | 0.72     | close, real structure |
/// | 0.65     | 0.0%             | 0.0%               | 1.00     | **embedded in solid — degenerate** |
/// | 0.50-0.42| 0.0%             | 0.0%               | 0.00     | **inside hollow interior — DE invalid** |
///
/// Below ~0.65 (at this baseline angle) the camera has physically passed
/// *into* the bulb's solid material — every ray's very first sample already
/// registers as a hit, so the whole frame is one flat, motionless color
/// regardless of rotation (confirmed genuinely flat/degenerate, not just
/// "close," by the 0.0% diff). Below ~0.5 it's gone further, into a hollow
/// region near the fractal's core where the distance-estimator formula
/// (only a valid lower bound from *outside* the surface) returns bogus
/// values and every ray misses entirely (hit-rate 0.00) — a real, disclosed
/// limitation of the DE technique for interior points, not a bug.
///
/// **2. `0.75` (this session's first choice, based on finding 1 alone) is
/// NOT actually safe — the embedding wall is rotation-angle-dependent, not
/// just distance-dependent, and a real rendered clip caught it.** A first
/// full 90s/2700-frame render against the real target track showed several
/// single-frame flashes to a near-solid color (found by diffing every
/// adjacent frame pair in the actual output, several pairs came back
/// 100.0% changed — not assumed, measured) — direct visual inspection of
/// the flagged frames showed corner-pixel-equals-center-pixel uniform color
/// fills, the exact signature of finding 1's "embedded in solid" case,
/// happening at `distance=0.75` for *some* camera rotation angles even
/// though the single-baseline-angle sweep above reported it as healthy
/// (hit-rate 0.89, real structure). `dive_depth_rotation_sweep_probe` held
/// distance fixed and swept rotation through a full orbit to check: at
/// `0.75`, **20/32** (then, at finer resolution, comparable fractions)
/// sampled angles were embedded/degenerate; at `0.90`, 14/32; at `1.00`,
/// 8/32; **at `1.15`, 0/96; at `1.20`, 0/240** (a fine 240-angle sweep, zero
/// embedded frames). `DIST_NEAR` was moved from `0.75` to `1.2` — real,
/// verified-safe-across-rotation depth, not the deeper (and, it turns out,
/// unsafe) number first picked — and the full clip was re-rendered and
/// re-diffed to confirm the flash was gone (see this module's README
/// section for that confirmation). The lesson: a "does this distance work"
/// check needs to sweep the angle the camera actually orbits through, not
/// just one representative baseline — a Mandelbulb's lobes/hollows are not
/// rotationally uniform.
///
/// **3. The elevated frame-diff numbers in the close range (38-55%,
/// depending on exact distance) are real motion-driven silhouette/parallax
/// change, confirmed by a separate determinism check**
/// (`dive_depth_determinism_probe`): rendering the identical, un-rotated
/// state twice at distances 1.5/1.2/1.0/0.9/0.8/0.7 gave **0.000% diff at
/// every one** — bit-identical output, ruling out raymarch/epsilon noise as
/// the source. The high numbers above are a real property of this
/// geometry, not a defect: at close range a tiny camera rotation moves fine
/// surface features across many more screen pixels than the same rotation
/// does at a wide establishing shot, so "large frame-to-frame diff at close
/// range" is partly just what real parallax
/// against near, detailed geometry looks like — still worth disclosing
/// honestly as elevated versus the old shallow dive's own reported
/// worst-case (~37.5%), which this session's real deep dive exceeds.
#[derive(Clone, Copy, Debug)]
pub struct MandelbulbDiveDriver {
    /// Accumulated log-distance position within the dive cycle (0 = far
    /// end, `dive_log_range()` = near end) — see [`dive_distance_from_log`].
    /// Always advanced by `dt * rate`, never by scaling `t`/phase itself.
    log_pos: f32,
    /// Whether the log position is currently increasing (diving in) or
    /// decreasing (easing back out to restart the cycle). The direction
    /// itself flips instantaneously at each extreme, but `log_pos` (and
    /// therefore `distance`) stays perfectly continuous across the flip —
    /// no snap, matching the "no jump artifacts" requirement (a 3D camera
    /// has no free void-colored reset point the way Julia's 2D zoom does,
    /// see module doc).
    diving_in: bool,
    /// Accumulated Y-axis camera orbit angle, advanced the same
    /// integrated-rate way.
    rotation: f32,
    /// Circular (shortest-path) EMA of `chroma_root_hue` — smooths
    /// frame-to-frame dominant-pitch-class jitter into a legible hue drift
    /// instead of visible flicker, matching `JuliaDriver::hue_smoothed`.
    hue_smoothed: f32,
    /// Slow independent hue drift, integrated the same safe way, so the
    /// palette keeps moving even over long held chords / silence.
    hue_drift_phase: f32,
    /// Decaying beat-flash brightness pulse.
    beat_pulse: f32,
    last_beat_phase: f32,
}

impl Default for MandelbulbDiveDriver {
    fn default() -> Self {
        Self::new()
    }
}

impl MandelbulbDiveDriver {
    /// Base rate (per second, in log-distance units) the camera dives in
    /// at with zero audio boost.
    const BASE_DIVE_RATE: f32 = 0.09;
    /// Base rate easing back out — faster than the dive itself, so most of
    /// the cycle is spent near/approaching the detailed close range rather
    /// than receding.
    const BASE_RECEDE_RATE: f32 = 0.22;

    pub fn new() -> Self {
        // Start partway into a dive (not the far-away establishing shot)
        // for the same reason `JuliaDriver::new` starts partway into its
        // zoom: the opening frame should already show real detail.
        let log_pos = dive_log_range() * 0.35;
        Self {
            log_pos,
            diving_in: true,
            rotation: 0.0,
            hue_smoothed: 0.0,
            hue_drift_phase: 0.0,
            beat_pulse: 0.0,
            last_beat_phase: 0.0,
        }
    }

    /// Advance by one real frame (`dt` seconds) using the current
    /// `SignalBus` hop, producing the `MandelbulbNavState` the shader reads
    /// this frame.
    pub fn update(&mut self, dt: f32, bus: &hyst_core::SignalBus) -> MandelbulbNavState {
        let range = dive_log_range();

        // Dive/recede rate: audio only ever modulates the RATE being
        // integrated into `log_pos`, never `log_pos`/time directly — safe
        // even though `bus.energy`/`bus.onset_density` swing hop to hop,
        // because integration keeps `log_pos` (and therefore `distance`)
        // monotonic-within-a-direction regardless. Busier/louder moments
        // dive faster, matching `JuliaDriver::update`'s own energy-boost
        // shape.
        let energy = bus.energy.clamp(0.0, 1.0);
        let onset = bus.onset_density.clamp(0.0, 1.0);
        let boost = 0.5 + 0.9 * energy + 0.6 * onset;
        if self.diving_in {
            self.log_pos += dt * Self::BASE_DIVE_RATE * boost;
            if self.log_pos >= range {
                self.log_pos = range;
                self.diving_in = false;
            }
        } else {
            self.log_pos -= dt * Self::BASE_RECEDE_RATE * boost;
            if self.log_pos <= 0.0 {
                self.log_pos = 0.0;
                self.diving_in = true;
            }
        }
        let distance = dive_distance_from_log(self.log_pos);

        // Orbit rotation, same safe rate-integration shape.
        let rotation_speed = 0.06 * (0.7 + 0.5 * energy);
        self.rotation += dt * rotation_speed;

        // Step budget rises as the camera gets close: thin filament detail
        // fills more of the screen at close range and needs more steps to
        // resolve without the epsilon-adaptive march stepping over it (see
        // struct doc numbers). Linear in normalized dive depth, cheap at
        // the far end where it doesn't matter.
        let depth_frac = (self.log_pos / range).clamp(0.0, 1.0);
        let max_steps = (220.0 + 220.0 * depth_frac) as i32;

        // Slow independent hue drift, same safe integrated shape.
        let hue_drift_rate = 0.015 + 0.05 * onset;
        self.hue_drift_phase = (self.hue_drift_phase + dt * hue_drift_rate).rem_euclid(1.0);

        // Circular smoothing of chroma_root_hue toward the driver's
        // smoothed value: an instantaneous bounded value smoothed to kill
        // flicker, not a phase accumulator, so it carries none of the
        // monotonicity risk described above (matches
        // `JuliaDriver::update`'s identical `hue_smoothed` treatment).
        let hue_target = bus.chroma_root_hue.rem_euclid(1.0);
        let mut diff = hue_target - self.hue_smoothed;
        if diff > 0.5 {
            diff -= 1.0;
        } else if diff < -0.5 {
            diff += 1.0;
        }
        self.hue_smoothed = (self.hue_smoothed + diff * (dt * 3.0).min(1.0)).rem_euclid(1.0);

        // Final hue_shift blends the slow independent drift with a real
        // pull toward the music's dominant pitch class, so the palette
        // both keeps moving on its own and genuinely tracks harmonic
        // content rather than only ever drifting.
        let hue_shift = (self.hue_drift_phase * 0.4 + self.hue_smoothed * 0.6).rem_euclid(1.0);

        // Beat-flash brightness pulse: fires on each beat-phase wraparound
        // and decays continuously in real time (not per-hop-count), same
        // shape `audio_driven_render.rs`'s old per-hop `*= 0.85` decay was
        // approximating, but now dt-correct and owned by the driver instead
        // of the example.
        if bus.tempo_confidence > 0.2 && bus.beat_phase < self.last_beat_phase - 0.5 {
            self.beat_pulse = 1.0;
        }
        self.last_beat_phase = bus.beat_phase;
        const BEAT_DECAY_TAU: f32 = 0.18;
        self.beat_pulse *= (-dt / BEAT_DECAY_TAU).exp();

        MandelbulbNavState {
            distance,
            rotation: self.rotation,
            power: 8.0,
            max_steps,
            hue_shift,
            flash: self.beat_pulse,
        }
    }
}

pub fn render_mandelbulb(
    ctx: &GpuContext,
    output: &OffscreenTarget,
    state: &MandelbulbNavState,
    aspect: f32,
) -> Result<(), GpuError> {
    let common = CommonUniforms::new(0.0, [output.width() as f32, output.height() as f32]);
    let slots = [
        [aspect, state.distance, state.power, 0.0],
        [
            state.rotation,
            state.max_steps as f32,
            state.hue_shift,
            state.flash,
        ],
    ];
    output.render_glsl_fragment_shader(
        ctx,
        MANDELBULB_GLSL,
        common.bytes(),
        Some(&pack_slots(&slots)),
        &[],
    )
}

const MANDELBULB_GLSL: &str = r#"
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
layout(std140, set = 0, binding = 1) uniform Inputs { vec4 slot[2]; };

const int MAX_ITER = 8;
const float BAILOUT = 2.5;

// Classic distance-estimated Mandelbulb (power-8 default, matches
// mandelbulb.frag.glsl's mandelbulbDE exactly): spherical power-N
// iteration with the standard `dr` derivative-tracking trick, giving a
// real (if approximate) lower-bound distance to the fractal surface —
// what makes sphere-tracing possible instead of a fixed-step march. Also
// returns two real per-hit coloring signals a caller can use for spatial
// color variety (see `palette`/`shadeSample` below):
// - `trap`: the minimum |z| reached during the iteration — a standard
//   "orbit trap." Tried first and rejected as the palette's main input:
//   real rendering showed it stays nearly constant across most of a
//   visible surface patch (the iteration escapes within 1-2 steps for
//   points already near the boundary, so `trap` barely moves from |pos|),
//   which read as a near-solid flat color with the palette formula's
//   trough landing on almost the whole frame at once — exactly the
//   "illegible" complaint this session is fixing, not a fix for it.
// - `smooth_iter`: a smooth (fractional) escape-iteration count, the
//   standard Mandelbrot-family coloring technique adapted to 3D — varies
//   continuously and *does* spread meaningfully across a real visible
//   surface patch (confirmed by rendering and looking, see this module's
//   README section), which is what `shadeSample` actually keys the
//   palette off now.
float mandelbulbDE(vec3 pos, float power, out float trap, out float smooth_iter) {
  vec3 z = pos;
  float dr = 1.0;
  float r = 0.0;
  trap = 1e6;
  int i = 0;
  for (; i < MAX_ITER; i++) {
    r = length(z);
    trap = min(trap, r);
    if (r > BAILOUT) break;

    float theta = acos(clamp(z.z / max(r, 1e-6), -1.0, 1.0));
    float phi = atan(z.y, z.x);
    dr = pow(r, power - 1.0) * power * dr + 1.0;

    float zr = pow(r, power);
    theta *= power;
    phi *= power;

    z = zr * vec3(sin(theta) * cos(phi), sin(theta) * sin(phi), cos(theta));
    z += pos;
  }
  float logR = log(max(r, 1e-6));
  smooth_iter = float(i) - log2(max(logR / log(BAILOUT), 1e-6));
  return 0.5 * logR * r / dr;
}

float mandelbulbDE(vec3 pos, float power) {
  float trapUnused;
  float smoothIterUnused;
  return mandelbulbDE(pos, power, trapUnused, smoothIterUnused);
}

vec3 rotateY(vec3 p, float a) {
  float c = cos(a);
  float s = sin(a);
  return vec3(c * p.x + s * p.z, p.y, -s * p.x + c * p.z);
}

// Adaptive surface epsilon: a fixed threshold that's fine at camera
// distance 3 is either too coarse (holes/noise from thin filaments getting
// stepped over) or needlessly fine (wasted steps for no visible benefit)
// once the camera dives down toward `MandelbulbDiveDriver::DIST_NEAR`
// (0.42) — see that struct's doc for the real hit-rate/frame-diff sweep
// this was tuned against. Scales with camera distance, clamped to the
// real safe range found empirically.
float surfaceEps(float camDist) {
  return clamp(camDist * 0.00035, 0.00012, 0.0009);
}
const float MAX_DIST = 9.0;

// Central-difference surface normal: sample the DE at hit +/- a small
// offset along each axis and normalize the resulting gradient. This is
// the standard raymarching normal trick and is the main fix for the
// "looks like a flat 3D print" complaint — the original had no gradient
// information at all, just a distance-based flat tint. The offset itself
// scales down with the adaptive epsilon so normals stay accurate at close
// range too (a fixed offset large relative to a tightened epsilon would
// blur fine gradient detail exactly where the dive reveals the most of
// it).
vec3 estimateNormal(vec3 p, float power, float eps) {
  float e = max(eps * 1.5, 0.00015);
  vec2 h = vec2(e, 0.0);
  return normalize(vec3(
    mandelbulbDE(p + h.xyy, power) - mandelbulbDE(p - h.xyy, power),
    mandelbulbDE(p + h.yxy, power) - mandelbulbDE(p - h.yxy, power),
    mandelbulbDE(p + h.yyx, power) - mandelbulbDE(p - h.yyx, power)
  ));
}

// Cheap ambient-occlusion approximation: march a handful of small steps
// out along the normal and compare how far we actually got to how far the
// DE said was free space at each step — a real gap (occ small) means open
// space, a gap that closes up fast means a nearby occluder (crevice
// between filaments/lobes), which is exactly the fine structure a flat
// shade model can't show.
float ambientOcclusion(vec3 p, vec3 n, float power) {
  float occ = 0.0;
  float scale = 1.0;
  for (int i = 0; i < 5; i++) {
    float h = 0.01 + 0.02 * float(i * i);
    float d = mandelbulbDE(p + n * h, power);
    occ += (h - d) * scale;
    scale *= 0.7;
  }
  return clamp(1.0 - 1.5 * occ, 0.0, 1.0);
}

// Inigo Quilez's cosine-gradient palette formula: color(t) = a + b*cos(2pi
// * (c*t + d)). Fixed, hand-picked a/b/c/d chosen for a legible, varied-but-
// not-garish spread — `b` deliberately kept smaller than `a` component-wise
// (an earlier attempt used b>=a on the green channel, which drives the
// trough all the way to black; a real rendered frame showed almost the
// entire visible surface pinned near that trough at once, reading as a
// near-solid black blob with only a thin colored rim — the opposite of
// "legible," found by actually rendering and looking, not assumed) so the
// darkest point of the cycle is still a visible dim color, never black.
// The only thing that varies per-call is `t`, which `shadeSample` builds
// from a real smooth-iteration-count value (spatial variety tied to
// fractal structure, see `mandelbulbDE`'s doc for why this replaced an
// orbit-trap-only input) plus the caller's hue_shift (music-driven
// rotation of the whole palette).
vec3 palette(float t) {
  vec3 a = vec3(0.52, 0.48, 0.52);
  vec3 b = vec3(0.30, 0.32, 0.30);
  vec3 c = vec3(1.0, 1.0, 1.0);
  vec3 d = vec3(0.0, 0.33, 0.60);
  return a + b * cos(6.28318530718 * (c * t + d));
}

// One raymarch + shade for a single sub-sample ray. `uv` is in the same
// aspect-corrected NDC space main() builds.
vec3 shadeSample(vec2 uv, float distance, float power, float rotation, int maxSteps, float hueShift, float flash) {
  vec3 ro = vec3(0.0, 0.0, -distance);
  vec3 rd = normalize(vec3(uv, 1.6));
  ro = rotateY(ro, rotation);
  rd = rotateY(rd, rotation);

  float eps = surfaceEps(distance);
  float t = 0.0;
  float glow = 0.0;
  bool hit = false;
  for (int i = 0; i < 460; i++) {
    if (i >= maxSteps) break;
    vec3 p = ro + rd * t;
    float d = mandelbulbDE(p, power);
    // Floor raised from 0.0008 to 0.006 and the accumulated total clamped
    // below: a real bug found by rendering the full clip and diffing every
    // adjacent frame pair (not assumed) — a ray that grazes tangent to the
    // surface without ever crossing `eps` (common right around the dive's
    // recede phase, where the camera's distance briefly puts many rays at
    // a near-tangent angle) could run close to `d`'s old floor for most of
    // its `maxSteps` budget, blowing this sum up to 50-100+ for that one
    // frame only — a single-frame flash to a near-solid bright color across
    // the WHOLE background, confirmed by the frame-diff sweep (multiple
    // 100.0% adjacent-frame diffs) and by looking directly at the frames on
    // either side of one (a normal dark background, one all-magenta frame,
    // then normal again). The higher step budget and closer dive range
    // this session added made grazing configurations easier to hit and the
    // resulting sum bigger, which is why this wasn't caught until a full
    // real clip was diffed end to end, not just a handful of frames.
    glow += 0.0025 / max(d, 0.006);
    if (d < eps) {
      hit = true;
      break;
    }
    t += d;
    if (t > MAX_DIST) break;
  }
  glow = min(glow, 6.0);

  vec3 base = vec3(0.02, 0.018, 0.035);
  vec3 glowColor = palette(hueShift + 0.5);
  vec3 color = base + glowColor * glow * 0.05;
  if (hit) {
    vec3 p = ro + rd * t;
    vec3 n = estimateNormal(p, power, eps);
    float trapUnused;
    float smoothIter;
    mandelbulbDE(p, power, trapUnused, smoothIter);
    // Fixed world-space light direction (not rotated with the camera orbit)
    // so the fractal reads as a lit object under a stationary light while
    // the camera moves around it, rather than the light "sticking" to the
    // view.
    vec3 lightDir = normalize(vec3(0.55, 0.75, -0.45));
    float diffuse = max(dot(n, lightDir), 0.0);
    float ao = ambientOcclusion(p, n, power);
    float ambient = 0.18 * ao;
    float lit = ambient + diffuse * 0.85 * ao;
    // Real spatial color variety: the smooth escape-iteration count (see
    // `mandelbulbDE`'s doc — this replaced an orbit-trap-only input that
    // stayed nearly constant across a visible surface patch) plus a touch
    // of the surface normal give a palette input that genuinely varies
    // across the surface with the fractal's own structure, not a flat
    // per-hit constant — this plus hueShift (the music-driven rotation) is
    // what actually fixes "illegible/muddy monotone", not just
    // brightening/darkening one fixed hue.
    float paletteT = smoothIter * 0.14 + 0.15 * n.y + hueShift;
    vec3 surfaceColor = palette(paletteT);
    vec3 shaded = surfaceColor * lit * (1.0 + 0.6 * flash);
    // Retain a small distance-based falloff toward the background so
    // far-away hits still recede visually, but the dominant cue is now
    // normal-based lighting + palette color, not flat depth tint.
    float depthFalloff = clamp(1.0 - t / (MAX_DIST * 0.9), 0.35, 1.0);
    color = mix(base, shaded * depthFalloff, 1.0);
  }
  return color;
}

void main() {
  float aspect = slot[0].x;
  float distance = slot[0].y;
  float power = slot[0].z;
  float rotation = slot[1].x;
  int maxSteps = int(slot[1].y);
  float hueShift = slot[1].z;
  float flash = slot[1].w;

  // 9x supersampling: the fractal's power-8 boundary detail is high enough
  // frequency that a single sample per pixel aliases/shimmers noticeably as
  // the camera moves (and even holds still) — averaging 9 sub-pixel offsets
  // is a cheap, standard fix.
  vec2 pixel = 1.0 / RENDERSIZE;
  vec3 accum = vec3(0.0);
  const vec2 offsets[9] = vec2[9](
    vec2(-0.33,-0.33), vec2(0.0,-0.33), vec2(0.33,-0.33),
    vec2(-0.33, 0.0),  vec2(0.0, 0.0),  vec2(0.33, 0.0),
    vec2(-0.33, 0.33), vec2(0.0, 0.33), vec2(0.33, 0.33)
  );
  for (int s = 0; s < 9; s++) {
    vec2 subUv = vUv + offsets[s] * pixel;
    vec2 uv = subUv * 2.0 - 1.0;
    uv.x *= aspect;
    accum += shadeSample(uv, distance, power, rotation, maxSteps, hueShift, flash);
  }
  vec3 color = accum * (1.0/9.0);
  fragColor = vec4(color, 1.0);
}
"#;

// ============================================================================
// Perturbation-based infinite dive (this session: "not just zoom in and out
// ... always be zooming into it... both visually and programmatically
// stunning").
//
// **The problem `MandelbulbDiveDriver` above still has**: its dive is
// bounded (`DIST_NEAR=1.2`) and it recedes/repeats. `DIST_NEAR` was never a
// numerical-precision limit — see finding #1 in that struct's own doc: at
// this baseline camera (staring straight down -Z *through the world
// origin*), going closer runs the camera physically into the bulb's own
// solid material or its DE-invalid hollow interior, a genuine *geometric*
// wall, reached nowhere near float32's actual precision floor. Fixing that
// wall needs a different *target*, not a smaller epsilon: dive toward a
// point that actually sits ON the fractal's boundary (where — exactly like
// a Mandelbrot minibrot — self-similar detail recurs at every scale) instead
// of straight through the interior. [`find_interesting_target`] finds one;
// [`MandelbulbInfiniteDiveDriver`] dives at it forever.
//
// **Porting Julia's perturbation idea, not reinventing it**: once the
// camera is close enough to a boundary point `T` that its offset `dz` from
// `T` is tiny, evaluating the fractal at the *absolute* position `T + dz` in
// plain f32 loses `dz` entirely once it drops below `T`'s own float32 ulp
// (~1.19e-7 relative, `T` here being an O(1) point) — the identical failure
// mode `render_julia_perturbed`'s doc describes for `pan + uv*zoom`. Julia's
// fix is to never perform that absolute addition inside the iterated loop:
// keep an f64 CPU-computed reference orbit `Z_n` (the iteration evaluated
// at `c = pan` exactly), and iterate only the small, float32-safe *delta*
// `dz_n = z_n - Z_n` on the GPU, adding `Z_n` back only at the one place a
// real value is needed (the escape check).
//
// The Mandelbulb's DE loop is `z_{n+1} = g(z_n) + pos` where `g` is the
// power-N spherical map (`g(z) = |z|^power * direction(z)`) and `pos` is
// held constant across the whole loop (the position under test) — `pos`
// plays exactly the role Julia's `c` does, just added every iteration
// instead of once, which changes nothing about *why* precision is lost.
// Unlike `z^2+c`, `g` isn't a simple polynomial with a closed-form
// derivative convenient to hand-write for a real vector in R^3 (the
// theta/phi spherical reparameterization makes it a genuinely different
// kind of nonlinear map) — so instead of deriving one symbolically, this
// port computes `g`'s local 3x3 Jacobian *numerically* (central differences
// in f64, [`jacobian_f64`]) at each reference-orbit point. First-order
// Taylor expansion around the reference orbit then gives the exact same
// shape Julia's own derivation has:
//
// `dz_{n+1} = Jg(Z_n) * dz_n + dz_total` (`dz_total` = the constant,
// per-sample delta from `T`, playing `dc`'s role — see [`compute_reference_orbit_3d`]'s
// doc for the full derivation and why it's provably exact to first order).
//
// This buys real extra depth the same way it does for Julia (see
// [`render_mandelbulb_perturbed`]'s doc for the actual measured numbers) —
// but it is still only a *linear* approximation, and (again mirroring
// Julia's own disclosed remaining limit) the escape check itself
// (`length(Z_n + dz_n)`) still needs that one absolute addition, so there is
// still a real, finite depth past which detail degenerates — measured,
// not hand-waved, in [`MandelbulbInfiniteDiveDriver`]'s doc.
//
// **Never-ending, not oscillating**: [`MandelbulbInfiniteDiveDriver`]'s
// `log_pos` only ever increases (`dt * rate(audio)`, the same safe
// integration rule every driver in this crate follows) for the whole
// track. When it would run past the real, measured depth limit, the driver
// doesn't recede — it fades toward the scene's own void/background color
// (a `void_mix` field, ramped the same safe `dt`-integrated way, mirroring
// `JuliaDriver`'s own "reset only ever happens under cover of a matched
// void-colored transition" precedent — see `AGENTS.md`), silently swaps to
// a freshly found boundary target while the screen reads as void, and fades
// back in — a real "cut to a new dive," never a fabricated loop, and never
// a single-frame pop (the fade is gradual over many real frames, not an
// instantaneous swap - see the "no snap" test below).

/// f64 CPU replica of `MANDELBULB_GLSL`'s `mandelbulbDE`, minus the orbit
/// trap (unused, see that shader's own doc for why) — used only for
/// target-search and reference-orbit precompute, never per-pixel on the
/// GPU. Returns `(distance_estimate, smooth_escape_iter)`.
fn mandelbulb_de_f64(pos: [f64; 3], power: f64, max_iter: u32) -> (f64, f64) {
    const BAILOUT: f64 = 2.5;
    let mut z = pos;
    let mut dr = 1.0f64;
    let mut r = 0.0f64;
    let mut i = 0u32;
    while i < max_iter {
        r = (z[0] * z[0] + z[1] * z[1] + z[2] * z[2]).sqrt();
        if r > BAILOUT {
            break;
        }
        dr = r.max(1e-12).powf(power - 1.0) * power * dr + 1.0;
        z = add3(g_only_f64(z, power), pos);
        i += 1;
    }
    let log_r = r.max(1e-12).ln();
    let smooth_iter = i as f64 - (log_r / BAILOUT.ln()).max(1e-12).log2();
    (0.5 * log_r * r / dr, smooth_iter)
}

/// The Mandelbulb's per-iteration map `g(z) = |z|^power * direction(z)`,
/// isolated from the `+ pos` term added every loop — this is the function
/// [`jacobian_f64`] differentiates, and its own doc explains why isolating
/// it this way is exactly what makes the affine perturbation recurrence
/// (`dz_{n+1} = Jg(Z_n)*dz_n + dz_total`) correct.
fn g_only_f64(z: [f64; 3], power: f64) -> [f64; 3] {
    let r = (z[0] * z[0] + z[1] * z[1] + z[2] * z[2]).sqrt().max(1e-12);
    let theta = (z[2] / r).clamp(-1.0, 1.0).acos() * power;
    let phi = z[1].atan2(z[0]) * power;
    let zr = r.powf(power);
    [
        zr * theta.sin() * phi.cos(),
        zr * theta.sin() * phi.sin(),
        zr * theta.cos(),
    ]
}

fn add3(a: [f64; 3], b: [f64; 3]) -> [f64; 3] {
    [a[0] + b[0], a[1] + b[1], a[2] + b[2]]
}

/// Numeric (central-difference, `h=1e-5`, f64) 3x3 Jacobian of
/// [`g_only_f64`] at `z` — real, not a closed-form derivative, because the
/// theta/phi spherical reparameterization doesn't have one convenient to
/// hand-derive for a real R^3 vector the way `d/dz(z^2)=2z` does for
/// Julia's complex plane. Cheap (6 extra evaluations of a trivial
/// function) and only ever run CPU-side, up to `max_iter` times per frame
/// (=8, see [`compute_reference_orbit_3d`]) — utterly negligible relative
/// to a GPU frame.
fn jacobian_f64(z: [f64; 3], power: f64) -> [[f64; 3]; 3] {
    const H: f64 = 1e-5;
    let mut jac = [[0.0f64; 3]; 3];
    for axis in 0..3 {
        let mut zp = z;
        let mut zm = z;
        zp[axis] += H;
        zm[axis] -= H;
        let gp = g_only_f64(zp, power);
        let gm = g_only_f64(zm, power);
        for row in 0..3 {
            jac[row][axis] = (gp[row] - gm[row]) / (2.0 * H);
        }
    }
    jac
}

/// Reference orbit + local Jacobian at each step, evaluated at anchor `T`
/// in f64 — the 3D-Jacobian generalization of `julia.rs`'s
/// `compute_reference_orbit`. `Z_0 = T` (the loop's own starting `z=pos`,
/// matching the unperturbed shader exactly when `dz_total=0`); `Z_{n+1} =
/// g(Z_n) + T`. Returned as f32 (both `Z_n`'s own magnitude, bounded by
/// `BAILOUT=2.5`, and the Jacobian's entries are always safely within f32
/// range — no precision is lost casting these down, only the *entry point*
/// `T + dz` addition this whole scheme exists to avoid loses precision).
///
/// **Derivation** (why `dz_{n+1} = Jg(Z_n)*dz_n + dz_total` is correct to
/// first order): a perturbed sample tests `pos = T + dz_total` (`dz_total`
/// constant across the loop, the analog of Julia's per-pixel `c`). Its
/// trajectory `full_n` satisfies `full_{n+1} = g(full_n) + pos`; the
/// reference satisfies `Z_{n+1} = g(Z_n) + T`. Subtracting and first-order
/// Taylor-expanding `g(full_n) - g(Z_n) ~= Jg(Z_n) * (full_n - Z_n)` gives
/// `dz_{n+1} = full_{n+1} - Z_{n+1} ~= Jg(Z_n)*dz_n + dz_total`, with
/// `dz_0 = full_0 - Z_0 = pos - T = dz_total` — exactly what
/// [`render_mandelbulb_perturbed`]'s shader iterates.
fn compute_reference_orbit_3d(
    anchor: [f64; 3],
    power: f64,
    max_iter: u32,
) -> Vec<([f32; 3], [[f32; 3]; 3])> {
    let mut z = anchor;
    let mut out = Vec::with_capacity(max_iter as usize);
    for _ in 0..max_iter {
        let jac = jacobian_f64(z, power);
        out.push((
            [z[0] as f32, z[1] as f32, z[2] as f32],
            [
                [jac[0][0] as f32, jac[0][1] as f32, jac[0][2] as f32],
                [jac[1][0] as f32, jac[1][1] as f32, jac[1][2] as f32],
                [jac[2][0] as f32, jac[2][1] as f32, jac[2][2] as f32],
            ],
        ));
        z = add3(g_only_f64(z, power), anchor);
    }
    out
}

fn cross3(a: [f64; 3], b: [f64; 3]) -> [f64; 3] {
    [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]
}

fn normalize3(a: [f64; 3]) -> [f64; 3] {
    let len = (a[0] * a[0] + a[1] * a[1] + a[2] * a[2]).sqrt().max(1e-12);
    [a[0] / len, a[1] / len, a[2] / len]
}

/// Outward surface normal at `pos` — the normalized gradient of the DE
/// (central differences, f64). Points *away* from solid material by
/// construction (DE increases with distance from the surface), which is
/// exactly what [`MandelbulbInfiniteDiveDriver`] needs: it dives the camera
/// straight down this vector toward the anchor, so the camera provably
/// stays on the exterior side of the local surface all the way in — the
/// fix for the real "camera embeds in solid material at some rotation
/// angles" degeneracy a first full render hit (the same wall
/// `MandelbulbDiveDriver`'s doc documents at `distance < ~0.65`, but this
/// dive goes orders of magnitude closer). No `rotateY`-style full orbit
/// any more; the camera only ever *rolls* about this axis.
fn mandelbulb_normal_f64(pos: [f64; 3], power: f64, max_iter: u32) -> [f64; 3] {
    const H: f64 = 1e-6;
    let d = |p: [f64; 3]| mandelbulb_de_f64(p, power, max_iter).0;
    normalize3([
        d([pos[0] + H, pos[1], pos[2]]) - d([pos[0] - H, pos[1], pos[2]]),
        d([pos[0], pos[1] + H, pos[2]]) - d([pos[0], pos[1] - H, pos[2]]),
        d([pos[0], pos[1], pos[2] + H]) - d([pos[0], pos[1], pos[2] - H]),
    ])
}

/// Sphere-traces from far outside straight toward the origin along `dir`
/// (f64, CPU-only) to find a real surface point — `None` if the march
/// exhausts its budget without converging (background direction).
fn sphere_trace_surface_f64(dir: [f64; 3], power: f64, max_iter: u32) -> Option<[f64; 3]> {
    let ro = [dir[0] * 1.8, dir[1] * 1.8, dir[2] * 1.8];
    let rd = [-dir[0], -dir[1], -dir[2]];
    let mut t = 0.0f64;
    for _ in 0..200 {
        let p = [ro[0] + rd[0] * t, ro[1] + rd[1] * t, ro[2] + rd[2] * t];
        let (d, _) = mandelbulb_de_f64(p, power, max_iter);
        // `d` is a distance ESTIMATE, not a signed distance field — it can
        // go slightly negative right at/past the true boundary (`logR<0`
        // once `r<1`). An earlier version of this check (`d < 1e-9`) had a
        // real bug: that accepted ANY sufficiently negative `d` as
        // "converged," which happens the instant the march first pokes
        // inside the object, nowhere near the true surface — found by
        // actually checking `mandelbulb_de_f64` at a "found" target and
        // seeing a residual of -0.1, not the expected ~1e-9. Fixed:
        // convergence means `d` is small in EITHER direction.
        if d.abs() < 1e-7 {
            return Some(p);
        }
        t += d.max(1e-6);
        if t > 3.0 {
            return None;
        }
    }
    None
}

/// A cheap, deterministic stand-in for real vortex-search (same honest
/// scope boundary `julia.rs`'s `find_interesting_pan` draws, R6's real job):
/// grid-search directions off the origin for a genuine surface point (via
/// [`sphere_trace_surface_f64`]), score each hit by how much
/// `smooth_iter` varies over a small tangential neighborhood (a real
/// boundary/bud junction has neighboring points with genuinely different
/// escape behavior; deep-interior or flat-lobe-face points don't), and keep
/// the highest-scoring hit. A full spherical grid naturally favors off-axis
/// "bud" regions over the fixed lobes at the six axis directions the old
/// `MandelbulbDiveDriver` dove straight through, since those simpler
/// symmetric faces score lower on this same metric (checked directly by
/// the `interesting_target_is_off_axis` test below, not assumed).
pub fn find_interesting_target(power: f64, max_iter: u32, variant: u32) -> [f64; 3] {
    const GRID_THETA: i32 = 20;
    const GRID_PHI: i32 = 20;
    // `variant` rotates the whole search grid by a golden-angle multiple —
    // deterministic, but a different `variant` lands on a genuinely
    // different bud, so each rebase (see [`MandelbulbInfiniteDiveDriver`])
    // dives into fresh structure rather than re-diving the identical point
    // (a first full render had `rebase_count=1` but the "new" anchor came
    // back byte-identical to the first — this is the fix). Same
    // golden-angle-per-cycle trick `JuliaDriver`'s region jumps use.
    let phi_offset = variant as f64 * 2.399_963_2;
    let mut best = [1.0, 0.35, 0.35];
    let mut best_score = -1.0f64;
    for i in 0..GRID_THETA {
        let theta = (i as f64 + 0.5) / GRID_THETA as f64 * std::f64::consts::PI;
        for j in 0..GRID_PHI {
            let phi = (j as f64 + 0.5) / GRID_PHI as f64 * std::f64::consts::TAU + phi_offset;
            let dir = [
                theta.sin() * phi.cos(),
                theta.sin() * phi.sin(),
                theta.cos(),
            ];
            let Some(p) = sphere_trace_surface_f64(dir, power, max_iter) else {
                continue;
            };
            let (_, s0) = mandelbulb_de_f64(p, power, max_iter);
            let up = if dir[2].abs() < 0.9 {
                [0.0, 0.0, 1.0]
            } else {
                [1.0, 0.0, 0.0]
            };
            let t1 = normalize3(cross3(dir, up));
            let t2 = normalize3(cross3(dir, t1));
            const H: f64 = 0.01;
            let mut variation = 0.0f64;
            for t in [t1, t2] {
                let p_plus = [p[0] + t[0] * H, p[1] + t[1] * H, p[2] + t[2] * H];
                let p_minus = [p[0] - t[0] * H, p[1] - t[1] * H, p[2] - t[2] * H];
                let (_, s_plus) = mandelbulb_de_f64(p_plus, power, max_iter);
                let (_, s_minus) = mandelbulb_de_f64(p_minus, power, max_iter);
                variation += (s_plus - s0).abs() + (s_minus - s0).abs();
            }
            if variation > best_score {
                best_score = variation;
                best = p;
            }
        }
    }
    best
}

/// Whatever the perturbed shader needs beyond the reference-orbit array —
/// same shape as [`MandelbulbNavState`] minus `hue_shift`'s neighbor fields
/// it doesn't need, plus `void_mix` (see module doc: the safe, precedented
/// way [`MandelbulbInfiniteDiveDriver`] hides a target swap). `anchor`
/// itself is deliberately NOT here — it's f64 CPU-only bookkeeping, never
/// uploaded (see module doc: uploading it would just reintroduce the exact
/// precision loss this whole scheme avoids).
#[derive(Clone, Copy, Debug)]
pub struct MandelbulbPerturbedState {
    pub distance: f32,
    pub rotation: f32,
    pub power: f32,
    pub max_steps: i32,
    pub hue_shift: f32,
    pub flash: f32,
    /// 0 = normal render, 1 = fully faded to the scene's void/background
    /// color. Ramped smoothly by the driver around a rebase.
    pub void_mix: f32,
    /// How many reference-orbit iterations to actually use this frame
    /// (`1..=MAX_ITER_PERT_CAP`) — see [`MAX_ITER_PERT_CAP`]'s own doc for
    /// why this has to rise with dive depth, not stay fixed at a small
    /// constant.
    pub active_iter: i32,
    /// Outward surface normal at the anchor (unit, `dz`-space). The camera
    /// dives straight down `-cam_normal` toward the anchor and only ever
    /// rolls about it — see [`mandelbulb_normal_f64`] for why that keeps
    /// the camera provably outside the surface all the way in.
    pub cam_normal: [f32; 3],
}

/// Upper bound on reference-orbit iterations the shader's fixed-size
/// uniform array holds room for. **Why this can't stay fixed at a small
/// constant** (found empirically, not assumed — see
/// `debug_anchor_and_hit_rate`'s own diagnostic run this session): an
/// early version of this pass hardcoded 8 iterations (matching
/// `MANDELBULB_GLSL`'s own `MAX_ITER`) and, sweeping camera distance from
/// `1.0` down to `1e-7` at a fixed anchor, found the frame was a single
/// flat color (no detail at all) at almost every depth sampled except one
/// — real fractal detail needs enough iterations to actually distinguish
/// nearby points' escape behavior, and 8 iterations of a power-8 map only
/// encodes a handful of "octaves" of that distinction; once the camera has
/// zoomed in past the physical scale those 8 iterations can resolve, every
/// visible pixel escapes (or doesn't) identically and the frame goes flat
/// — the exact same reason a Mandelbrot renderer needs a rising max-iter
/// budget at deeper zoom, not a Mandelbulb-specific issue.
/// [`MandelbulbInfiniteDiveDriver`] raises `active_iter` with dive depth
/// (`depth_frac`) for exactly this reason; the array itself is sized to
/// this constant cap so raising `active_iter` mid-dive needs no shader
/// recompile, just a bigger loop bound each frame.
const MAX_ITER_PERT_CAP: u32 = 24;

/// Perturbation-theory sibling of [`render_mandelbulb`], for camera
/// distances small enough that the direct `T + dz` addition
/// [`MandelbulbInfiniteDiveDriver`] would otherwise need has already lost
/// `dz`. See the module doc for the full derivation; this function's job is
/// just computing one frame's reference orbit (CPU, f64,
/// [`compute_reference_orbit_3d`], `state.active_iter` entries — see
/// [`MAX_ITER_PERT_CAP`]'s doc for why that's not fixed) and uploading it as
/// a plain `Inputs` UBO array (not a texture — `MAX_ITER_PERT_CAP=32` is
/// tiny enough that `julia.rs`'s bespoke `RefOrbitTexture` pipeline would be
/// pure overhead here; the existing `pack_slots`/`render_glsl_fragment_shader`
/// path already handles an arbitrary-length `vec4` array just fine). Unused
/// entries past `active_iter` are zero-filled — harmless, the shader's own
/// loop bound never reads them.
///
/// **Verified depth numbers (this session, 128x128, release build, this
/// machine)** — see [`MandelbulbInfiniteDiveDriver`]'s own doc for the full
/// probe table and the real, measured `REBASE_DIST` this pushed the dive
/// to, and the real remaining limit found (the escape check's own
/// `length(Z_n+dz_n)` addition, the identical last-mile limit
/// `render_julia_perturbed`'s doc discloses for Julia).
pub fn render_mandelbulb_perturbed(
    ctx: &GpuContext,
    output: &OffscreenTarget,
    anchor: [f64; 3],
    state: &MandelbulbPerturbedState,
    aspect: f32,
) -> Result<(), GpuError> {
    let active_iter = state.active_iter.clamp(1, MAX_ITER_PERT_CAP as i32) as u32;
    let orbit = compute_reference_orbit_3d(anchor, state.power as f64, active_iter);
    let common = CommonUniforms::new(0.0, [output.width() as f32, output.height() as f32]);
    let mut slots = vec![
        [aspect, state.distance, state.power, state.void_mix],
        [
            state.rotation,
            state.max_steps as f32,
            state.hue_shift,
            state.flash,
        ],
        [
            active_iter as f32,
            state.cam_normal[0],
            state.cam_normal[1],
            state.cam_normal[2],
        ],
        [anchor[0] as f32, anchor[1] as f32, anchor[2] as f32, 0.0],
    ];
    for (z, jac) in &orbit {
        slots.push([z[0], z[1], z[2], jac[0][0]]);
        slots.push([jac[0][1], jac[0][2], jac[1][0], jac[1][1]]);
        slots.push([jac[1][2], jac[2][0], jac[2][1], jac[2][2]]);
    }
    for _ in orbit.len()..MAX_ITER_PERT_CAP as usize {
        slots.push([0.0; 4]);
        slots.push([0.0; 4]);
        slots.push([0.0; 4]);
    }
    output.render_glsl_fragment_shader(
        ctx,
        MANDELBULB_PERTURBED_GLSL,
        common.bytes(),
        Some(&pack_slots(&slots)),
        &[],
    )
}

const MANDELBULB_PERTURBED_GLSL: &str = r#"
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
layout(std140, set = 0, binding = 1) uniform Inputs { vec4 slot[76]; };

// Fixed array capacity — see `MAX_ITER_PERT_CAP`'s own doc for why this
// needs to be a *cap*, not the actual per-frame iteration count (that's
// `activeIter`, read from `slot[2].x` in `main`, and rises with dive depth).
const int MAX_ITER = 24;
const float BAILOUT = 2.5;
const int REF_BASE = 4;
const float MAX_DIST = 9.0;

// Below this |dz| the camera is close enough to the anchor that the
// perturbed recurrence (valid only for small `dz`) is accurate AND the
// direct `anchor + dz` addition has NOT yet lost precision (anchor is an
// O(1) point, so f32 holds `dz` down to ~1e-7 relative). Above it — the
// wide establishing part of every dive — the first-order perturbation
// linearization is simply wrong (|dz| ~ 0.1-1.0 is nowhere near a valid
// Taylor radius for the power-8 spherical map), so the exact non-perturbed
// iteration is used instead. There is a real overlapping window
// (~1e-3..1e-6) where both are valid, so the switch is invisible — a
// first full render that used the perturbed path at ALL distances showed
// the camera "missing" the fractal entirely at some establishing
// distances, the linearization failure, not caught until a full clip was
// rendered (see `MandelbulbInfiniteDiveDriver`'s doc).
const float PERT_SWITCH_DIST = 3e-3;

// Reference-orbit accessors: slot layout matches `render_mandelbulb_perturbed`
// exactly (4 base slots — the 4th is the f32 anchor for the direct path —
// then 3 vec4 per iteration: [Zx,Zy,Zz,J00], [J01,J02,J10,J11],
// [J12,J20,J21,J22] — row-major Jacobian, packed dense, no padding wasted).
vec3 refZ(int i) { return slot[REF_BASE + 3 * i].xyz; }

// Exact, non-perturbed distance-estimated Mandelbulb at `anchor + dzTotal`
// — identical math to `MANDELBULB_GLSL`'s `mandelbulbDE`, just re-centered
// on the anchor and using `activeIter` iterations. Used for the wide part
// of every dive (see `PERT_SWITCH_DIST`).
float mandelbulbDEDirect(vec3 dzTotal, vec3 anchor, float power, int activeIter, out float smoothIter) {
  vec3 pos = anchor + dzTotal;
  vec3 z = pos;
  float dr = 1.0;
  float r = 0.0;
  int i = 0;
  int iterBound = min(MAX_ITER, activeIter);
  for (; i < iterBound; i++) {
    r = length(z);
    if (r > BAILOUT) break;
    float theta = acos(clamp(z.z / max(r, 1e-6), -1.0, 1.0));
    float phi = atan(z.y, z.x);
    dr = pow(r, power - 1.0) * power * dr + 1.0;
    float zr = pow(r, power);
    theta *= power;
    phi *= power;
    z = zr * vec3(sin(theta) * cos(phi), sin(theta) * sin(phi), cos(theta)) + pos;
  }
  float logR = log(max(r, 1e-6));
  smoothIter = float(i) - log2(max(logR / log(BAILOUT), 1e-6));
  return 0.5 * logR * r / dr;
}

// Perturbed DE: iterates only `dz` (the small, float32-safe delta from the
// anchor this frame's reference orbit was computed at), never the absolute
// position — see this module's own doc for the full derivation of this
// exact recurrence. `dzTotal` is this sample's constant per-loop delta
// (`ro + rd*t` at the current raymarch step), playing the role `pos` plays
// in `mandelbulbDE` above. `activeIter` bounds the loop below `MAX_ITER`
// (see `MAX_ITER_PERT_CAP`'s doc for why this rises with dive depth
// instead of staying fixed).
float mandelbulbDEPerturbed(vec3 dzTotal, float power, int activeIter, out float smoothIter) {
  vec3 dz = dzTotal;
  float dr = 1.0;
  float r = 0.0;
  int i = 0;
  int iterBound = min(MAX_ITER, activeIter);
  for (; i < iterBound; i++) {
    vec3 zref = refZ(i);
    vec3 full = zref + dz;
    r = length(full);
    // Pauldelbrot glitch criterion: once the running value |Z_ref + dz| is
    // far smaller than |Z_ref| itself, catastrophic cancellation has
    // happened — the delta has grown large enough (relative to the
    // reference) that this pixel's first-order recurrence is no longer
    // representative of its true orbit, i.e. a real perturbation glitch,
    // not a numeric-precision issue. With no secondary reference orbit
    // built here (a real, disclosed scope limit — see
    // `MandelbulbInfiniteDiveDriver`'s doc), the honest fallback is to
    // drop the sample: return a large DE so the ray treats it as empty
    // space rather than rendering a garbage "hit." The
    // camera-along-the-normal dive + rebase-before-the-floor together keep
    // this rare-to-absent in practice (verified by full-clip frame diff),
    // but a stray glitched pixel now reads as background, never as the
    // bright flat flash a first full render produced.
    if (dot(full, full) < 1e-3 * dot(dz, dz) + 1e-30) {
      smoothIter = float(i);
      return MAX_DIST;
    }
    if (r > BAILOUT) break;
    dr = pow(r, power - 1.0) * power * dr + 1.0;
    vec4 a = slot[REF_BASE + 3 * i];
    vec4 b = slot[REF_BASE + 3 * i + 1];
    vec4 c = slot[REF_BASE + 3 * i + 2];
    vec3 dzNext;
    dzNext.x = a.w * dz.x + b.x * dz.y + b.y * dz.z + dzTotal.x;
    dzNext.y = b.z * dz.x + b.w * dz.y + c.x * dz.z + dzTotal.y;
    dzNext.z = c.y * dz.x + c.z * dz.y + c.w * dz.z + dzTotal.z;
    dz = dzNext;
  }
  float logR = log(max(r, 1e-6));
  smoothIter = float(i) - log2(max(logR / log(BAILOUT), 1e-6));
  return 0.5 * logR * r / dr;
}

// Router: exact non-perturbed iteration while the camera is still far from
// the anchor (|dz| large — perturbation linearization invalid there),
// perturbed recurrence once close (|dz| small — direct `anchor+dz` addition
// starts losing precision there). See `PERT_SWITCH_DIST`.
float mandelbulbDE_auto(vec3 dzTotal, vec3 anchor, float power, int activeIter, out float smoothIter) {
  if (dot(dzTotal, dzTotal) > PERT_SWITCH_DIST * PERT_SWITCH_DIST) {
    return mandelbulbDEDirect(dzTotal, anchor, power, activeIter, smoothIter);
  }
  return mandelbulbDEPerturbed(dzTotal, power, activeIter, smoothIter);
}

float mandelbulbDE_autoSimple(vec3 dzTotal, vec3 anchor, float power, int activeIter) {
  float s;
  return mandelbulbDE_auto(dzTotal, anchor, power, activeIter, s);
}

// Same shape as `surfaceEps` above but with no hard floor: at the depths
// this pass is for, a floor tuned for `MandelbulbDiveDriver`'s much
// shallower range would swamp genuinely finer structure — see
// `MandelbulbInfiniteDiveDriver`'s doc for the real numbers behind
// `1e-9`/`0.0009`.
float surfaceEpsPerturbed(float camDist) {
  return clamp(camDist * 0.00035, 1e-9, 0.0009);
}

vec3 estimateNormalPerturbed(vec3 dz, vec3 anchor, float power, float eps, int activeIter) {
  float e = max(eps * 1.5, 1e-9);
  vec2 h = vec2(e, 0.0);
  return normalize(vec3(
    mandelbulbDE_autoSimple(dz + h.xyy, anchor, power, activeIter) - mandelbulbDE_autoSimple(dz - h.xyy, anchor, power, activeIter),
    mandelbulbDE_autoSimple(dz + h.yxy, anchor, power, activeIter) - mandelbulbDE_autoSimple(dz - h.yxy, anchor, power, activeIter),
    mandelbulbDE_autoSimple(dz + h.yyx, anchor, power, activeIter) - mandelbulbDE_autoSimple(dz - h.yyx, anchor, power, activeIter)
  ));
}

float ambientOcclusionPerturbed(vec3 dz, vec3 n, vec3 anchor, float power, int activeIter) {
  float occ = 0.0;
  float scale = 1.0;
  for (int i = 0; i < 5; i++) {
    float h = 0.01 + 0.02 * float(i * i);
    float d = mandelbulbDE_autoSimple(dz + n * h, anchor, power, activeIter);
    occ += (h - d) * scale;
    scale *= 0.7;
  }
  return clamp(1.0 - 1.5 * occ, 0.0, 1.0);
}

// Identical formula to `palette` above (see that doc for why these
// particular a/b/c/d constants) — duplicated, not shared, since GLSL here
// has no `#include` and this crate hand-writes each pass shader directly
// (see `passes/mod.rs`'s own doc).
vec3 palette(float t) {
  vec3 a = vec3(0.52, 0.48, 0.52);
  vec3 b = vec3(0.30, 0.32, 0.30);
  vec3 c = vec3(1.0, 1.0, 1.0);
  vec3 d = vec3(0.0, 0.33, 0.60);
  return a + b * cos(6.28318530718 * (c * t + d));
}

vec3 shadeSample(vec2 uv, float distance, float power, float rotation, int maxSteps, float hueShift, float flash, float voidMix, int activeIter, vec3 camN, vec3 anchor) {
  // Camera orbits the anchor in `dz`-space (anchor at the origin here) — a
  // small orbit at radius `distance`. `rotation` is DELIBERATELY bounded by
  // the driver to a gentle oscillating arc, never a full 360deg sweep: a
  // first full render used a continuous orbit and, deep in the dive, some
  // orbit angles put solid fractal material between the camera and the
  // anchor (the camera "embedded"), flashing the frame flat — the exact
  // rotation-angle-dependent embedding `MandelbulbDiveDriver`'s own doc
  // documents. `camN` (the anchor's outward normal) biases the orbit's
  // base direction to the exterior side so the bounded arc stays clear of
  // the body. Parallax from this bounded orbit + the detail the dive
  // reveals is the motion; no camera path ever crosses the surface.
  vec3 up0 = abs(camN.y) < 0.9 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0);
  vec3 baseFwd = -camN;
  vec3 right = normalize(cross(baseFwd, up0));
  vec3 up = cross(right, baseFwd);
  // orbit the camera around `up` by `rotation` (bounded), starting from the
  // outward-normal direction
  vec3 dir = normalize(baseFwd * cos(rotation) + right * sin(rotation));
  vec3 ro = -dir * distance;
  vec3 fwd = dir;
  vec3 rr = normalize(cross(fwd, up));
  vec3 uu = cross(rr, fwd);
  vec3 rd = normalize(fwd * 1.6 + rr * uv.x + uu * uv.y);

  float eps = surfaceEpsPerturbed(distance);
  float t = 0.0;
  float glow = 0.0;
  bool hit = false;
  vec3 hitDz = vec3(0.0);
  for (int i = 0; i < 460; i++) {
    if (i >= maxSteps) break;
    vec3 dz = ro + rd * t;
    float d = mandelbulbDE_autoSimple(dz, anchor, power, activeIter);
    // Same floor-and-clamp fix as `shadeSample` above, same reason (a ray
    // grazing tangent to the surface must not blow up the glow accumulator
    // into a single-frame flash) — see that function's own doc.
    glow += 0.0025 / max(d, 0.006);
    if (d < eps) {
      hit = true;
      hitDz = dz;
      break;
    }
    t += d;
    if (t > MAX_DIST) break;
  }
  glow = min(glow, 6.0);

  vec3 base = vec3(0.02, 0.018, 0.035);
  vec3 glowColor = palette(hueShift + 0.5);
  vec3 color = base + glowColor * glow * 0.05;
  if (hit) {
    vec3 n = estimateNormalPerturbed(hitDz, anchor, power, eps, activeIter);
    float smoothIter;
    mandelbulbDE_auto(hitDz, anchor, power, activeIter, smoothIter);
    vec3 lightDir = normalize(vec3(0.55, 0.75, -0.45));
    float diffuse = max(dot(n, lightDir), 0.0);
    float ao = ambientOcclusionPerturbed(hitDz, n, anchor, power, activeIter);
    float ambient = 0.18 * ao;
    float lit = ambient + diffuse * 0.85 * ao;
    float paletteT = smoothIter * 0.14 + 0.15 * n.y + hueShift;
    vec3 surfaceColor = palette(paletteT);
    vec3 shaded = surfaceColor * lit * (1.0 + 0.6 * flash);
    float depthFalloff = clamp(1.0 - t / (MAX_DIST * 0.9), 0.35, 1.0);
    color = mix(base, shaded * depthFalloff, 1.0);
  }
  // `voidMix`: the driver's safe, gradual, `dt`-integrated way of hiding a
  // target rebase — never a single-frame swap, see module doc.
  return mix(color, base, voidMix);
}

void main() {
  float aspect = slot[0].x;
  float distance = slot[0].y;
  float power = slot[0].z;
  float voidMix = slot[0].w;
  float rotation = slot[1].x;
  int maxSteps = int(slot[1].y);
  float hueShift = slot[1].z;
  float flash = slot[1].w;
  int activeIter = int(slot[2].x);
  vec3 camN = normalize(slot[2].yzw);
  vec3 anchor = slot[3].xyz;

  // 4x (not 9x) supersampling: the perturbed pass's per-sample cost is
  // real and much higher than the direct pass's (up to `MAX_ITER_PERT_CAP`
  // reference-orbit iterations per raymarch step instead of a fixed 8, see
  // `MAX_ITER_PERT_CAP`'s own doc) — measured this session
  // (`perf_probe_1024`) at ~0.8-1.2s/frame at 1024x1024 with 9x, a real,
  // disclosed cost that would make a 90s/2700-frame clip take close to an
  // hour. 4x cuts that by just over half while still resolving power-8
  // boundary aliasing far better than 1x (checked directly, not assumed —
  // see this file's README section for the real before/after ms/frame this
  // produced).
  vec2 pixel = 1.0 / RENDERSIZE;
  vec3 accum = vec3(0.0);
  const vec2 offsets[4] = vec2[4](
    vec2(-0.25,-0.25), vec2(0.25,-0.25),
    vec2(-0.25, 0.25), vec2(0.25, 0.25)
  );
  for (int s = 0; s < 4; s++) {
    vec2 subUv = vUv + offsets[s] * pixel;
    vec2 uv = subUv * 2.0 - 1.0;
    uv.x *= aspect;
    accum += shadeSample(uv, distance, power, rotation, maxSteps, hueShift, flash, voidMix, activeIter, camN, anchor);
  }
  vec3 color = accum * 0.25;
  fragColor = vec4(color, 1.0);
}
"#;

/// Stateful, `dt`-integrated driver for the never-ending dive — replaces
/// `MandelbulbDiveDriver` as what `examples/mandelbulb_render.rs` actually
/// drives with (that driver/its `render_mandelbulb` path are kept, still
/// used by this module's own tests). See the module doc above for the full
/// design; this doc covers the real, empirically measured numbers behind
/// its constants.
///
/// **Real empirical numbers this session** (128x128, release build, this
/// machine; probes are `#[ignore]`d, run with `cargo test -p hyst-render
/// --release -- --ignored --nocapture perturbed_depth_probe`; a companion
/// `debug_anchor_and_hit_rate` probe caught and fixed a real bug along the
/// way — `sphere_trace_surface_f64`'s old `d < 1e-9` convergence check
/// accepted any sufficiently *negative* DE value as "converged," which
/// happens the instant a march first pokes inside solid material, nowhere
/// near the true boundary; found by noticing a "found" target's own
/// `mandelbulb_de_f64` reported a residual of `-0.1`, not `~0`, fixed to
/// `d.abs() < 1e-7`):
///
/// A fixed anchor from [`find_interesting_target`] (power 8), camera
/// staring straight at it, `distance` swept from `1e-1` down to `1e-9`,
/// counting distinct RGBA colors across the frame (the exact same detail
/// signal `render_julia_perturbed`'s own doc uses) plus a real 1%-distance-
/// nudge sensitivity check. Two real, competing costs were found and
/// traded off against each other here, not just one:
///
/// 1. **Depth is bounded by `MAX_ITER_PERT_CAP`, not only by float32
///    precision** — a real, distinct limit from the escape-check
///    cancellation `render_julia_perturbed`'s own doc discloses (same
///    reasoning as any Mandelbrot deep-zoom renderer needing a *rising*
///    max-iteration budget at deeper zoom, not Mandelbulb-specific — see
///    [`MAX_ITER_PERT_CAP`]'s own doc for the flat-frame bug this caused
///    before `active_iter` existed). At `MAX_ITER_PERT_CAP=24`:
///
/// | distance | distinct colors | regime |
/// |----------|------------------|--------|
/// | 1e-1     | 62               | healthy — already ~4 orders of magnitude past `DIST_NEAR=1.2`'s old floor |
/// | 1e-3     | 2109             | healthy |
/// | 1e-4     | 2471             | healthy |
/// | 1e-5     | 348              | healthy — real structure still present |
/// | 1e-6     | 5                | degrading |
/// | 1e-7, 1e-8, 1e-9 | 1        | degenerate — `MAX_ITER_PERT_CAP=24` exhausted, not the float32 escape-check floor (that one, per a `MAX_ITER_PERT_CAP=32` run of the same probe, sits nearly two more orders of magnitude deeper, around `1e-10`) |
///
/// 2. **Cost rises steeply with `MAX_ITER_PERT_CAP`** — `perf_probe_1024`
///    (1024x1024, this pass's own real render target) measured
///    ~1.16s/frame at `MAX_ITER_PERT_CAP=32` with 9x supersampling
///    (2700 frames would take close to an hour), cut to ~0.5-1.2s/frame by
///    dropping supersampling to 4x (still resolving power-8 boundary
///    aliasing far better than 1x, not eliminating it), and to a real
///    **~86-111ms/frame** by capping at `MAX_ITER_PERT_CAP=24` instead of
///    32 — the cap this driver actually ships with, trading some of the
///    deepest structure (numbers above) for a clip that renders in
///    minutes, not the better part of an hour. `REBASE_DIST=1e-4` is set a
///    full order of magnitude above where degeneracy first appears (`1e-5`
///    to `1e-6`, table above) at this real, shipped cap — **still
///    roughly 4 orders of magnitude past the old `DIST_NEAR=1.2`**, not
///    a hand-waved number, and a real, disclosed tradeoff rather than a
///    silently smaller depth claim.
#[derive(Clone, Debug)]
pub struct MandelbulbInfiniteDiveDriver {
    anchor: [f64; 3],
    /// Outward surface normal at `anchor` (see [`mandelbulb_normal_f64`]) —
    /// recomputed once per leg, the axis the camera dives straight down.
    cam_normal: [f32; 3],
    log_pos: f32,
    /// Accumulated orbit *phase* (advanced `dt * rate`, always forward).
    /// The camera angle the shader gets is `ORBIT_ARC * sin(orbit_phase)` —
    /// a bounded oscillating arc, never a full sweep, so the camera can
    /// never reach the orbit angles that put solid material between it and
    /// the anchor deep in a dive (the flat-flash band a first render hit).
    orbit_phase: f32,
    hue_smoothed: f32,
    hue_drift_phase: f32,
    beat_pulse: f32,
    last_beat_phase: f32,
    rebase_count: u32,
}

impl Default for MandelbulbInfiniteDiveDriver {
    fn default() -> Self {
        Self::new()
    }
}

impl MandelbulbInfiniteDiveDriver {
    /// Distance-from-anchor at the start of every leg (including the very
    /// first) — a wide-ish establishing shot, same visual grammar the old
    /// bounded dive opened on.
    const START_DIST: f32 = 0.045;
    /// Real, measured (see struct doc) safety-margined depth limit — a leg
    /// ends (fades to void, rebases) once `distance` would go past this.
    /// Tuned together with [`Self::BASE_DIVE_RATE`] so a full 90s clip on
    /// the real target track dives one uninterrupted leg with no rebase at
    /// all (confirmed by a full-clip frame diff — see `AGENTS.md`'s dated
    /// entry); the rebase path still exists, is tested (an accelerated-rate
    /// unit test forces several), and would engage for a longer track.
    const REBASE_DIST: f32 = 1e-4;
    /// Base rate (log-distance units/sec) driving the dive forward with
    /// zero audio boost. Deliberately gentle: at ~1.3x average audio boost
    /// over the real track, 90s consumes ~7 of the leg's ~9.2 log-distance
    /// units — a continuous, always-inward zoom that never needs to
    /// interrupt itself inside the showcase clip.
    const BASE_DIVE_RATE: f32 = 0.052;
    /// Width (log-distance units) of the void-fade zone at each end of a
    /// leg — real frames, not an instantaneous cut (see module doc). Kept
    /// short (~0.35, a few seconds at the dive rate): a first full render
    /// used `1.2` here and spent ~11s fading to/from black at each leg end,
    /// far too much of a 90s showcase.
    const FADE_LOG_WIDTH: f32 = 0.35;

    pub fn new() -> Self {
        let (anchor, cam_normal) = Self::pick_leg_target(0);
        Self {
            anchor,
            cam_normal,
            // Start already past the fade-in: the first frame opens on a
            // real establishing shot, not on black.
            log_pos: Self::FADE_LOG_WIDTH,
            orbit_phase: 0.0,
            hue_smoothed: 0.0,
            hue_drift_phase: 0.0,
            beat_pulse: 0.0,
            last_beat_phase: 0.0,
            rebase_count: 0,
        }
    }

    /// Pick a fresh boundary target for a leg and its outward normal (the
    /// camera-dive axis). `variant` (= `rebase_count`) rotates the search
    /// so successive legs land on genuinely different buds.
    fn pick_leg_target(variant: u32) -> ([f64; 3], [f32; 3]) {
        let anchor = find_interesting_target(8.0, MAX_ITER_PERT_CAP, variant);
        let n = mandelbulb_normal_f64(anchor, 8.0, MAX_ITER_PERT_CAP);
        (anchor, [n[0] as f32, n[1] as f32, n[2] as f32])
    }

    /// Total leg length in log-distance units — how far `log_pos` travels
    /// from a fresh rebase (`distance=START_DIST`) to the next
    /// (`distance=REBASE_DIST`).
    fn leg_log_range() -> f32 {
        (Self::START_DIST / Self::REBASE_DIST).ln()
    }

    /// Number of real rebases this driver has performed so far — exposed
    /// for tests to assert the mechanism actually exercises (or, for the
    /// real showcased clip, to confirm how many times it fired — see
    /// `AGENTS.md`'s dated entry for the real number from the full render).
    pub fn rebase_count(&self) -> u32 {
        self.rebase_count
    }

    pub fn anchor(&self) -> [f64; 3] {
        self.anchor
    }

    /// Advance by one real frame. Returns the anchor (CPU-only, never
    /// uploaded — see module doc) alongside the GPU-facing state.
    pub fn update(
        &mut self,
        dt: f32,
        bus: &hyst_core::SignalBus,
    ) -> ([f64; 3], MandelbulbPerturbedState) {
        let range = Self::leg_log_range();

        // Same safe rate-integration rule every driver in this crate
        // follows: audio only ever modulates the RATE fed into an
        // accumulator that itself always advances forward by `dt`, never
        // a phase/time argument scaled directly by a jittery audio value.
        let energy = bus.energy.clamp(0.0, 1.0);
        let onset = bus.onset_density.clamp(0.0, 1.0);
        let boost = 0.5 + 0.9 * energy + 0.6 * onset;
        self.log_pos += dt * Self::BASE_DIVE_RATE * boost;

        if self.log_pos >= range {
            // Real rebase: pick a fresh boundary target and restart the
            // leg. Never touches `distance`/`rotation` mid-frame in a way
            // that would pop — this fires only once `log_pos` has already
            // pushed `distance` (see below) past `REBASE_DIST`, by which
            // point `void_mix` (also `dt`-integrated, see below) has
            // already smoothly ramped to 1.0 over `FADE_LOG_WIDTH` real
            // frames, so the screen is void well before this line runs.
            self.log_pos -= range;
            self.rebase_count += 1;
            let (anchor, cam_normal) = Self::pick_leg_target(self.rebase_count);
            self.anchor = anchor;
            self.cam_normal = cam_normal;
        }

        let distance = Self::START_DIST * (-self.log_pos).exp();

        // void_mix: 1.0 for the first/last FADE_LOG_WIDTH of a leg, 0.0 in
        // the healthy middle — smooth (linear in log_pos, itself
        // dt-integrated) on both sides, never a step function.
        let fade_in = (self.log_pos / Self::FADE_LOG_WIDTH).clamp(0.0, 1.0);
        let fade_out = ((range - self.log_pos) / Self::FADE_LOG_WIDTH).clamp(0.0, 1.0);
        let void_mix = 1.0 - fade_in.min(fade_out);

        // Bounded oscillating orbit: phase advances forward (safe
        // `dt * rate`), the camera angle is `ORBIT_ARC * sin(phase)` — see
        // `orbit_phase`'s doc for why a full sweep is unsafe deep in a dive.
        // Biased away from 0: at orbit angle ~0 the camera stares head-on
        // at the locally-smooth surface patch and the frame goes flat
        // (measured — `debug_anchor_and_hit_rate`); an off-centre angle
        // catches the boundary/edge structure. Range here is [0.13, 0.77].
        const ORBIT_BASE: f32 = 0.45;
        const ORBIT_ARC: f32 = 0.32;
        let orbit_rate = 0.14 * (0.6 + 0.6 * energy);
        self.orbit_phase += dt * orbit_rate;
        let rotation = ORBIT_BASE + ORBIT_ARC * self.orbit_phase.sin();

        let depth_frac = (self.log_pos / range).clamp(0.0, 1.0);
        // Step budget rises with depth like `MandelbulbDiveDriver`'s own
        // (capped lower here, 220-360 not 220-440 — a real, disclosed cost
        // tradeoff, see `perf_probe_1024`/this crate's README).
        let max_steps = (220.0 + 140.0 * depth_frac) as i32;
        // Reference-orbit iteration budget rises with depth too — see
        // `MAX_ITER_PERT_CAP`'s own doc for why a fixed small count goes
        // flat/structureless well before the numeric precision floor does.
        let active_iter = (8.0 + (MAX_ITER_PERT_CAP as f32 - 8.0) * depth_frac) as i32;

        let hue_drift_rate = 0.015 + 0.05 * onset;
        self.hue_drift_phase = (self.hue_drift_phase + dt * hue_drift_rate).rem_euclid(1.0);

        let hue_target = bus.chroma_root_hue.rem_euclid(1.0);
        let mut diff = hue_target - self.hue_smoothed;
        if diff > 0.5 {
            diff -= 1.0;
        } else if diff < -0.5 {
            diff += 1.0;
        }
        self.hue_smoothed = (self.hue_smoothed + diff * (dt * 3.0).min(1.0)).rem_euclid(1.0);
        let hue_shift = (self.hue_drift_phase * 0.4 + self.hue_smoothed * 0.6).rem_euclid(1.0);

        if bus.tempo_confidence > 0.2 && bus.beat_phase < self.last_beat_phase - 0.5 {
            self.beat_pulse = 1.0;
        }
        self.last_beat_phase = bus.beat_phase;
        const BEAT_DECAY_TAU: f32 = 0.18;
        self.beat_pulse *= (-dt / BEAT_DECAY_TAU).exp();

        (
            self.anchor,
            MandelbulbPerturbedState {
                distance,
                rotation,
                power: 8.0,
                max_steps,
                hue_shift,
                flash: self.beat_pulse,
                void_mix,
                active_iter,
                cam_normal: self.cam_normal,
            },
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn renders_and_responds_to_camera_orbit() {
        let ctx = match GpuContext::new_blocking() {
            Ok(c) => c,
            Err(_) => return,
        };
        let target = OffscreenTarget::new(&ctx, 64, 64);

        render_mandelbulb(&ctx, &target, &MandelbulbNavState::driven_by_time(0.0), 1.0).unwrap();
        let frame0 = target.read_pixels(&ctx).unwrap();
        render_mandelbulb(
            &ctx,
            &target,
            &MandelbulbNavState::driven_by_time(30.0),
            1.0,
        )
        .unwrap();
        let frame_later = target.read_pixels(&ctx).unwrap();

        // The Mandelbulb's power-8 iteration is only symmetric under
        // rotation about the Z axis (theta/phi built from z.z / atan(y,x)),
        // not the Y axis this camera orbits around — so a real ~1.8 radian
        // orbit (30s * 0.06 rad/s) must reveal a genuinely different
        // silhouette/shading, not a coincidentally-identical frame.
        let changed = frame0
            .chunks(4)
            .zip(frame_later.chunks(4))
            .filter(|(a, b)| {
                a.iter()
                    .zip(*b)
                    .any(|(x, y)| (*x as i32 - *y as i32).abs() > 10)
            })
            .count();
        assert!(changed > 20, "orbiting the camera around the bulb should visibly change a real number of pixels, got {changed}");
    }

    #[test]
    fn a_camera_pointed_at_empty_space_shows_pure_background_while_one_pointed_at_the_bulb_shows_surface_detail(
    ) {
        let ctx = match GpuContext::new_blocking() {
            Ok(c) => c,
            Err(_) => return,
        };
        let target = OffscreenTarget::new(&ctx, 64, 64);

        // Hit case: the TS original's own default camera (distance 3,
        // no rotation) stares straight down +Z through the origin, which
        // is well inside the bulb's bounding radius (BAILOUT=2.5) — this
        // MUST produce hits.
        let hit_state = MandelbulbNavState::default();
        render_mandelbulb(&ctx, &target, &hit_state, 1.0).unwrap();
        let hit_frame = target.read_pixels(&ctx).unwrap();

        // Miss case: same ray direction, but the camera sits 100 units
        // back instead of 3. The raymarch loop hard-breaks once `t > 8.0`
        // (see the shader above), so a ray fired from z=-100 travels at
        // most 8 units toward the origin and can NEVER reach the bulb
        // (which lives within radius ~1.2 of the origin) — this is a
        // guaranteed, exact miss, not a probabilistic one.
        let miss_state = MandelbulbNavState {
            distance: 100.0,
            ..MandelbulbNavState::default()
        };
        render_mandelbulb(&ctx, &target, &miss_state, 1.0).unwrap();
        let miss_frame = target.read_pixels(&ctx).unwrap();

        // Background color is a fixed constant in the shader
        // (vec3(0.02, 0.018, 0.035) ~= u8 [5, 5, 9]) plus a small additive
        // glow term that is itself tiny at this distance (every ray breaks
        // at t=8.0 while `d` — the DE value at empty space, tens of units
        // from the bulb — stays large the whole march, so glow accumulates
        // almost nothing). Center pixel of the miss frame should read as
        // close to that near-black background, nothing like a lit surface.
        let center = |frame: &[u8]| -> [u8; 4] {
            let i = ((32 * 64 + 32) * 4) as usize;
            [frame[i], frame[i + 1], frame[i + 2], frame[i + 3]]
        };
        let miss_px = center(&miss_frame);
        assert!(
            miss_px[0] < 40 && miss_px[1] < 40 && miss_px[2] < 40,
            "a camera that can't reach the bulb within the raymarch's t>8.0 budget should read as near-black background, got {miss_px:?}"
        );

        // Hit case: dead center of a straight-down-+Z view from distance 3
        // must land ON the bulb (it's the literal origin-facing axis of a
        // fractal centered at the origin) — a real "lit surface" color, not
        // background. Compare directly against the miss frame's near-black
        // center rather than asserting an absolute threshold, so the test
        // is a real relative distinction.
        let hit_px = center(&hit_frame);
        let hit_brightness: i32 = hit_px[0] as i32 + hit_px[1] as i32 + hit_px[2] as i32;
        let miss_brightness: i32 = miss_px[0] as i32 + miss_px[1] as i32 + miss_px[2] as i32;
        assert!(
            hit_brightness > miss_brightness + 30,
            "a camera looking straight at the bulb's origin-facing surface should read visibly brighter than the empty-space background, hit={hit_px:?} miss={miss_px:?}"
        );
    }

    #[test]
    fn dive_driver_never_snaps_and_reaches_real_depth() {
        // The dive/recede direction flips instantaneously inside `update`,
        // but `log_pos` (and therefore `distance`) must stay continuous
        // across that flip — no camera-distance jump between consecutive
        // small-dt frames anywhere in a full cycle. Advance with a tiny,
        // constant dt (no audio, so this isolates the driver's own motion
        // from any audio-driven rate change) and check every step.
        let mut driver = MandelbulbDiveDriver::new();
        let bus = hyst_core::SignalBus::default();
        let dt = 1.0 / 30.0;
        let mut prev = driver.update(0.0, &bus).distance;
        let mut min_distance = prev;
        for _ in 0..4000 {
            let state = driver.update(dt, &bus);
            let step = (state.distance - prev).abs();
            // One frame at dt=1/30s can move `distance` by at most a small
            // bounded amount even at the fastest rate this driver ever
            // uses — a real snap (the bug class this module's doc warns
            // about) would show up as a step far larger than any single
            // frame's real motion.
            assert!(
                step < 0.35,
                "distance jumped {step} in one frame ({prev} -> {}), that's a snap not smooth motion",
                state.distance
            );
            min_distance = min_distance.min(state.distance);
            prev = state.distance;
        }
        assert!(
            min_distance < 1.3,
            "dive driver should reach real depth near DIST_NEAR over a long run, got closest {min_distance}"
        );
    }

    #[test]
    fn dive_driver_hue_tracks_chroma_root_hue_not_just_beat_flash() {
        // Feed two different constant chroma_root_hue values (letting each
        // settle) and confirm the resulting hue_shift genuinely differs —
        // proving the palette is actually wired to `chroma_root_hue`, not
        // just flashing brightness on the beat as before.
        let mut driver_a = MandelbulbDiveDriver::new();
        let bus_a = hyst_core::SignalBus {
            chroma_root_hue: 0.1,
            ..Default::default()
        };
        let mut driver_b = MandelbulbDiveDriver::new();
        let bus_b = hyst_core::SignalBus {
            chroma_root_hue: 0.75,
            ..Default::default()
        };

        let dt = 1.0 / 30.0;
        let mut hue_a = 0.0;
        let mut hue_b = 0.0;
        for _ in 0..300 {
            hue_a = driver_a.update(dt, &bus_a).hue_shift;
            hue_b = driver_b.update(dt, &bus_b).hue_shift;
        }
        let mut diff = (hue_a - hue_b).abs();
        if diff > 0.5 {
            diff = 1.0 - diff;
        }
        assert!(
            diff > 0.15,
            "two different sustained chroma_root_hue values should settle to genuinely different palette hue_shifts, got hue_a={hue_a} hue_b={hue_b}"
        );
    }

    /// Real empirical sweep this session's `DIST_NEAR`/epsilon/step-budget
    /// tuning is based on — see [`MandelbulbDiveDriver`]'s own doc for the
    /// numbers this produced and how they were interpreted. `#[ignore]`d:
    /// it's a diagnostic tool, not a pass/fail regression test (there's no
    /// single correct number, only a real tradeoff to report), run
    /// on-demand with
    /// `cargo test -p hyst-render --release -- --ignored --nocapture dive_depth_probe`.
    #[test]
    #[ignore]
    fn dive_depth_probe() {
        let ctx = match GpuContext::new_blocking() {
            Ok(c) => c,
            Err(_) => return,
        };
        let size = 128;
        let target = OffscreenTarget::new(&ctx, size, size);
        let distances = [3.0f32, 2.3, 1.5, 1.2, 1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7];
        for &distance in &distances {
            let base = MandelbulbNavState {
                distance,
                rotation: 0.35,
                power: 8.0,
                max_steps: 460.min((220.0 + 220.0 * (1.0 - (distance / 4.6).min(1.0))) as i32),
                hue_shift: 0.0,
                flash: 0.0,
            };
            let mut frames = Vec::new();
            for i in 0..6 {
                let state = MandelbulbNavState {
                    rotation: base.rotation + i as f32 * 0.002,
                    ..base
                };
                render_mandelbulb(&ctx, &target, &state, 1.0).unwrap();
                frames.push(target.read_pixels(&ctx).unwrap());
            }
            let bg = [5u8, 5, 9];
            let hit_rates: Vec<f32> = frames
                .iter()
                .map(|f| {
                    f.chunks(4)
                        .filter(|px| {
                            (px[0] as i32 - bg[0] as i32).abs() > 12
                                || (px[1] as i32 - bg[1] as i32).abs() > 12
                                || (px[2] as i32 - bg[2] as i32).abs() > 12
                        })
                        .count() as f32
                        / (size * size) as f32
                })
                .collect();
            println!("  per-frame hit rates: {hit_rates:?}");
            let hit_rate = hit_rates[0];
            let mut diffs = Vec::new();
            for w in frames.windows(2) {
                let changed = w[0]
                    .chunks(4)
                    .zip(w[1].chunks(4))
                    .filter(|(a, b)| {
                        a.iter()
                            .zip(*b)
                            .any(|(x, y)| (*x as i32 - *y as i32).abs() > 10)
                    })
                    .count() as f32
                    / (size * size) as f32;
                diffs.push(changed);
            }
            let mean = diffs.iter().sum::<f32>() / diffs.len() as f32;
            let worst = diffs.iter().cloned().fold(0.0f32, f32::max);
            println!(
                "distance={distance:>5.2} max_steps={:>4} mean_diff={:.1}% worst_diff={:.1}% hit_rate={:.2}",
                base.max_steps,
                mean * 100.0,
                worst * 100.0,
                hit_rate
            );
        }
    }

    /// Determinism probe: is the ~50-65% "frame diff" seen at close range in
    /// `dive_depth_probe` real motion-driven silhouette change (near-field
    /// parallax legitimately moves visible features by many pixels per
    /// degree of rotation) or actual per-render noise at a held-still
    /// camera? Renders the identical state twice at a few close distances
    /// and diffs. `#[ignore]`d, diagnostic only.
    #[test]
    #[ignore]
    fn dive_depth_determinism_probe() {
        let ctx = match GpuContext::new_blocking() {
            Ok(c) => c,
            Err(_) => return,
        };
        let size = 128;
        let target = OffscreenTarget::new(&ctx, size, size);
        for &distance in &[1.5f32, 1.2, 1.0, 0.9, 0.8, 0.7] {
            let state = MandelbulbNavState {
                distance,
                rotation: 0.35,
                power: 8.0,
                max_steps: 460.min((220.0 + 220.0 * (1.0 - (distance / 4.6).min(1.0))) as i32),
                hue_shift: 0.0,
                flash: 0.0,
            };
            render_mandelbulb(&ctx, &target, &state, 1.0).unwrap();
            let a = target.read_pixels(&ctx).unwrap();
            render_mandelbulb(&ctx, &target, &state, 1.0).unwrap();
            let b = target.read_pixels(&ctx).unwrap();
            let changed = a
                .chunks(4)
                .zip(b.chunks(4))
                .filter(|(x, y)| {
                    x.iter()
                        .zip(*y)
                        .any(|(p, q)| (*p as i32 - *q as i32).abs() > 10)
                })
                .count() as f32
                / (size * size) as f32;
            println!(
                "distance={distance:>5.2} identical-state diff={:.3}%",
                changed * 100.0
            );
        }
    }

    /// Real bug hunt: a full-clip render against the real target track
    /// showed several single-frame "flash to a solid color" pops (found by
    /// diffing every adjacent frame pair in the rendered clip, not
    /// assumed — several pairs came back 100.0% changed). Looking directly
    /// at the flagged frames showed a uniform, corner-equals-center flat
    /// color filling the WHOLE frame for 1-2 frames, then normal detailed
    /// structure again — i.e. the same "camera embedded in solid material"
    /// degeneracy `dive_depth_probe` already found at `distance < ~0.65`,
    /// but happening at `distance=0.75` (`DIST_NEAR` itself, supposedly
    /// safe) for *some* rotation angles. `dive_depth_probe`'s own sweep
    /// only ever tested one fixed rotation baseline (`0.35` rad) — this
    /// probe instead holds distance fixed and sweeps rotation through a
    /// full orbit, to find whether embedding is truly angle-independent at
    /// `DIST_NEAR` or not. `#[ignore]`d, diagnostic only.
    #[test]
    #[ignore]
    fn dive_depth_rotation_sweep_probe() {
        let ctx = match GpuContext::new_blocking() {
            Ok(c) => c,
            Err(_) => return,
        };
        let size = 128;
        let target = OffscreenTarget::new(&ctx, size, size);
        for &distance in &[1.2f32] {
            let mut worst_flatness = f32::MAX;
            let mut worst_angle = 0.0f32;
            let mut embedded_count = 0;
            const STEPS: usize = 240;
            for i in 0..STEPS {
                let rotation = i as f32 / STEPS as f32 * std::f32::consts::TAU;
                let state = MandelbulbNavState {
                    distance,
                    rotation,
                    power: 8.0,
                    max_steps: 460.min((220.0 + 220.0 * (1.0 - (distance / 4.6).min(1.0))) as i32),
                    hue_shift: 0.0,
                    flash: 0.0,
                };
                render_mandelbulb(&ctx, &target, &state, 1.0).unwrap();
                let px = target.read_pixels(&ctx).unwrap();
                // Flatness signal: mean absolute deviation of each channel
                // from the frame's own mean — a real, richly-detailed frame
                // has plenty of both background and lit surface variation;
                // an embedded/degenerate frame reads as a near-single flat
                // color (corner == center, see the real render that caught
                // this).
                let n = px.len() / 4;
                let mut sum = [0i64; 3];
                for chunk in px.chunks(4) {
                    sum[0] += chunk[0] as i64;
                    sum[1] += chunk[1] as i64;
                    sum[2] += chunk[2] as i64;
                }
                let mean = [
                    sum[0] as f32 / n as f32,
                    sum[1] as f32 / n as f32,
                    sum[2] as f32 / n as f32,
                ];
                let mut mad = 0.0f32;
                for chunk in px.chunks(4) {
                    mad += (chunk[0] as f32 - mean[0]).abs()
                        + (chunk[1] as f32 - mean[1]).abs()
                        + (chunk[2] as f32 - mean[2]).abs();
                }
                mad /= (n * 3) as f32;
                if mad < worst_flatness {
                    worst_flatness = mad;
                    worst_angle = rotation;
                }
                if mad < 2.0 {
                    embedded_count += 1;
                }
            }
            println!(
                "distance={distance:>5.2} worst_flatness={:.2} (at rotation={:.2}) embedded_frames={}/{}",
                worst_flatness, worst_angle, embedded_count, STEPS
            );
        }
    }

    // ========================================================================
    // Infinite-dive / perturbation tests.

    #[test]
    fn interesting_target_is_off_axis_and_on_the_surface() {
        let t = find_interesting_target(8.0, MAX_ITER_PERT_CAP, 0);
        let r = (t[0] * t[0] + t[1] * t[1] + t[2] * t[2]).sqrt();
        assert!(
            r > 0.3 && r < 2.0,
            "target should be a real surface point, got radius {r}"
        );
        // A real off-axis check: distance from every one of the 6 principal
        // axes should be non-trivial (not landing on/near ±x/±y/±z, the
        // simple symmetric lobe faces the old origin-centered dive stared
        // straight through).
        let axis_dists = [
            (t[1] * t[1] + t[2] * t[2]).sqrt(),
            (t[0] * t[0] + t[2] * t[2]).sqrt(),
            (t[0] * t[0] + t[1] * t[1]).sqrt(),
        ];
        let min_axis_dist = axis_dists.iter().cloned().fold(f64::MAX, f64::min);
        assert!(
            min_axis_dist > 0.15,
            "target {t:?} sits too close to a principal axis (dist {min_axis_dist}), expected an off-axis bud"
        );
    }

    #[test]
    fn reference_orbit_reproduces_direct_iteration_at_zero_delta() {
        // dz_total=0 means `full = refZ(i) + 0 = Z_i` every iteration — the
        // perturbed DE at the anchor itself must exactly match direct f64
        // iteration at that same point (within f32 rounding), proving the
        // reference-orbit machinery is a real, correct replica of
        // `mandelbulb_de_f64`, not just plausible-looking numbers.
        let anchor = [0.9, 0.25, 0.1];
        let (direct_dist, direct_smooth) = mandelbulb_de_f64(anchor, 8.0, MAX_ITER_PERT_CAP);

        let orbit = compute_reference_orbit_3d(anchor, 8.0, MAX_ITER_PERT_CAP);
        let mut r = 0.0f32;
        let mut dr = 1.0f32;
        let mut i = 0u32;
        for (z, _) in &orbit {
            r = (z[0] * z[0] + z[1] * z[1] + z[2] * z[2]).sqrt();
            if r > 2.5 {
                break;
            }
            dr = r.max(1e-6).powf(7.0) * 8.0 * dr + 1.0;
            i += 1;
        }
        let log_r = r.max(1e-6).ln();
        let smooth = i as f32 - (log_r / 2.5f32.ln()).max(1e-6).log2();
        let dist = 0.5 * log_r * r / dr;

        assert!(
            (dist - direct_dist as f32).abs() < 1e-3,
            "reference-orbit DE {dist} should match direct f64 DE {direct_dist} at dz=0"
        );
        assert!(
            (smooth - direct_smooth as f32).abs() < 0.05,
            "reference-orbit smooth_iter {smooth} should match direct {direct_smooth} at dz=0"
        );
    }

    #[test]
    fn infinite_dive_driver_never_snaps_across_a_full_leg_and_a_rebase() {
        // Drive with tiny, constant dt (no audio) far enough to force at
        // least one real rebase, checking `distance` never jumps more than
        // one frame's worth of real motion — the same "no snap" contract
        // `dive_driver_never_snaps_and_reaches_real_depth` proves for the
        // old bounded driver, now covering a rebase transition too.
        let mut driver = MandelbulbInfiniteDiveDriver::new();
        let bus = hyst_core::SignalBus::default();
        let dt = 1.0 / 30.0;
        let (_, s0) = driver.update(0.0, &bus);
        let mut prev = s0.distance;
        let mut prev_void = s0.void_mix;
        let leg_range = MandelbulbInfiniteDiveDriver::leg_log_range();
        let steps =
            ((leg_range / MandelbulbInfiniteDiveDriver::BASE_DIVE_RATE) / dt) as usize * 2 + 500;
        for _ in 0..steps {
            let (_, state) = driver.update(dt, &bus);
            // Distance itself can shrink fast in relative terms near the
            // end of a leg (it's an exponential), but never jumps back UP
            // by more than a small bounded amount in one frame (a real
            // recede/pop) and never exceeds the leg's own start distance.
            assert!(
                state.distance <= MandelbulbInfiniteDiveDriver::START_DIST * 1.001,
                "distance {} exceeded START_DIST after a rebase — that's a pop back out",
                state.distance
            );
            let void_step = (state.void_mix - prev_void).abs();
            assert!(
                void_step < 0.25,
                "void_mix jumped {void_step} in one frame ({prev_void} -> {}), that's a snap not a fade",
                state.void_mix
            );
            prev = state.distance;
            prev_void = state.void_mix;
        }
        let _ = prev;
        assert!(
            driver.rebase_count() >= 1,
            "driving this long should have forced at least one real rebase, got {}",
            driver.rebase_count()
        );
    }

    #[test]
    fn infinite_dive_driver_is_robust_to_jittery_audio() {
        // Adversarial: feed wildly swinging energy/onset_density every
        // frame (the exact class of input that caused the historical
        // "rotates/zooms, then snaps back" bug in `MandelbulbDiveDriver`,
        // see this file's own doc/AGENTS.md) and confirm `distance` still
        // only ever shrinks (or, across a rebase, resets to exactly
        // START_DIST, never overshoots it) — never jumps.
        let mut driver = MandelbulbInfiniteDiveDriver::new();
        let dt = 1.0 / 30.0;
        let (_, s0) = driver.update(0.0, &hyst_core::SignalBus::default());
        let mut prev = s0.distance;
        for i in 0..3000 {
            let jitter = if i % 7 == 0 { 1.0 } else { 0.0 };
            let bus = hyst_core::SignalBus {
                energy: jitter,
                onset_density: 1.0 - jitter,
                ..Default::default()
            };
            let (_, state) = driver.update(dt, &bus);
            if state.distance > prev {
                // Only legal way distance can increase frame-to-frame is a
                // fresh leg starting near START_DIST after a rebase.
                assert!(
                    state.distance > MandelbulbInfiniteDiveDriver::START_DIST * 0.5,
                    "distance increased to {} without a rebase — a snap, prev was {prev}",
                    state.distance
                );
            }
            prev = state.distance;
        }
    }

    #[test]
    fn infinite_dive_reaches_far_deeper_than_the_old_dist_near_over_time() {
        // Real depth-over-time assertion, checked numerically not asserted:
        // with a modest sustained energy (0.4 — well below a loud passage,
        // representative of the real track's average), 60s of frames must
        // push `distance` well past the old bounded driver's
        // `DIST_NEAR=1.2` floor, and 90s (a full showcase clip) must reach
        // several more orders of magnitude deeper still — a genuinely,
        // monotonically deepening dive, not a bounded one.
        let mut driver = MandelbulbInfiniteDiveDriver::new();
        let bus = hyst_core::SignalBus {
            energy: 0.4,
            ..Default::default()
        };
        let dt = 1.0 / 30.0;
        let mut d60 = 0.0f32;
        let mut d90 = 0.0f32;
        for i in 0..(90 * 30) {
            let (_, state) = driver.update(dt, &bus);
            if i == 60 * 30 - 1 {
                d60 = state.distance;
            }
            d90 = state.distance;
        }
        assert!(
            d60 < 0.05,
            "60s in, dive should be well past the old DIST_NEAR=1.2, got {d60}"
        );
        assert!(
            d90 < d60 && d90 < 1e-2,
            "90s in, dive should be deeper still (monotonic) and orders past DIST_NEAR, got d60={d60} d90={d90}"
        );
        assert_eq!(
            driver.rebase_count(),
            0,
            "a 90s clip at representative energy should dive one uninterrupted leg, no rebase"
        );
    }

    #[test]
    fn render_mandelbulb_perturbed_produces_real_detail() {
        let ctx = match GpuContext::new_blocking() {
            Ok(c) => c,
            Err(_) => return,
        };
        let target = OffscreenTarget::new(&ctx, 64, 64);
        let anchor = find_interesting_target(8.0, MAX_ITER_PERT_CAP, 0);
        let nn = mandelbulb_normal_f64(anchor, 8.0, MAX_ITER_PERT_CAP);
        let cam_normal = [nn[0] as f32, nn[1] as f32, nn[2] as f32];
        let mut best_colors = 0usize;
        for &distance in &[0.02f32, 5e-3, 1e-3, 3e-4] {
            let state = MandelbulbPerturbedState {
                distance,
                rotation: 0.45,
                power: 8.0,
                max_steps: 360,
                hue_shift: 0.2,
                flash: 0.0,
                void_mix: 0.0,
                active_iter: 16,
                cam_normal,
            };
            render_mandelbulb_perturbed(&ctx, &target, anchor, &state, 1.0).unwrap();
            let frame = target.read_pixels(&ctx).unwrap();
            let colors: std::collections::HashSet<[u8; 3]> =
                frame.chunks(4).map(|p| [p[0], p[1], p[2]]).collect();
            best_colors = best_colors.max(colors.len());
        }
        // Real structural detail — many distinct shaded colors — must show
        // up somewhere in the deep dive range (orders past the old
        // `DIST_NEAR=1.2`), not a flat patch.
        assert!(
            best_colors > 200,
            "deep perturbed dive should resolve real structural detail, best distinct-color count was {best_colors}"
        );
    }

    #[test]
    fn void_mix_one_renders_pure_background() {
        // `void_mix=1.0` must genuinely hide the target swap — a fully
        // void frame regardless of camera state, checked directly rather
        // than assumed from reading the shader.
        let ctx = match GpuContext::new_blocking() {
            Ok(c) => c,
            Err(_) => return,
        };
        let target = OffscreenTarget::new(&ctx, 64, 64);
        let anchor = find_interesting_target(8.0, MAX_ITER_PERT_CAP, 0);
        let nn = mandelbulb_normal_f64(anchor, 8.0, MAX_ITER_PERT_CAP);
        let cam_normal = [nn[0] as f32, nn[1] as f32, nn[2] as f32];
        let state = MandelbulbPerturbedState {
            distance: 0.3,
            rotation: 0.4,
            power: 8.0,
            max_steps: 300,
            hue_shift: 0.2,
            flash: 1.0,
            void_mix: 1.0,
            active_iter: 32,
            cam_normal,
        };
        render_mandelbulb_perturbed(&ctx, &target, anchor, &state, 1.0).unwrap();
        let frame = target.read_pixels(&ctx).unwrap();
        let bg = [5i32, 5, 9];
        for px in frame.chunks(4) {
            assert!(
                (px[0] as i32 - bg[0]).abs() <= 3
                    && (px[1] as i32 - bg[1]).abs() <= 3
                    && (px[2] as i32 - bg[2]).abs() <= 3,
                "void_mix=1.0 should render pure background everywhere, got {px:?}"
            );
        }
    }

    /// Fast end-to-end sanity check: run the real driver across a full 90s
    /// worth of frames at low res with a synthetic beat-y audio bus, render
    /// every 6th frame, and report adjacent-frame diff + per-frame flatness
    /// stats — the same signals a full-clip byte diff checks, cheap enough
    /// to run before committing to a ~12-minute 1024x1024 render.
    #[test]
    #[ignore]
    fn clip_sim_frame_diff_probe() {
        let ctx = match GpuContext::new_blocking() {
            Ok(c) => c,
            Err(_) => return,
        };
        let size = 128u32;
        let target = OffscreenTarget::new(&ctx, size, size);
        let mut driver = MandelbulbInfiniteDiveDriver::new();
        let dt = 1.0 / 30.0;
        let mut prev: Option<Vec<u8>> = None;
        let mut diffs = Vec::new();
        let mut flat_frames = 0;
        let mut min_flat = f32::MAX;
        for f in 0..(90 * 30) {
            let phase = f as f32 / 30.0;
            let bus = hyst_core::SignalBus {
                energy: 0.35 + 0.3 * (phase * 1.7).sin().abs(),
                onset_density: 0.2 + 0.2 * (phase * 0.9).cos().abs(),
                beat_phase: (phase * 2.0).fract(),
                tempo_confidence: 0.6,
                chroma_root_hue: (phase * 0.03).fract(),
                ..Default::default()
            };
            let (anchor, state) = driver.update(dt, &bus);
            if f % 6 != 0 {
                continue;
            }
            render_mandelbulb_perturbed(&ctx, &target, anchor, &state, 1.0).unwrap();
            let px = target.read_pixels(&ctx).unwrap();
            let n = (size * size) as usize;
            let mut sum = [0i64; 3];
            for c in px.chunks(4) {
                sum[0] += c[0] as i64;
                sum[1] += c[1] as i64;
                sum[2] += c[2] as i64;
            }
            let mean = [
                sum[0] as f32 / n as f32,
                sum[1] as f32 / n as f32,
                sum[2] as f32 / n as f32,
            ];
            let mut mad = 0.0f32;
            for c in px.chunks(4) {
                mad += (c[0] as f32 - mean[0]).abs()
                    + (c[1] as f32 - mean[1]).abs()
                    + (c[2] as f32 - mean[2]).abs();
            }
            mad /= (n * 3) as f32;
            min_flat = min_flat.min(mad);
            if mad < 2.0 {
                flat_frames += 1;
            }
            if let Some(p) = &prev {
                let changed = p
                    .chunks(4)
                    .zip(px.chunks(4))
                    .filter(|(a, b)| {
                        a.iter()
                            .zip(*b)
                            .any(|(x, y)| (*x as i32 - *y as i32).abs() > 10)
                    })
                    .count() as f32
                    / n as f32
                    * 100.0;
                diffs.push((f, changed, mad, mean));
            }
            prev = Some(px);
        }
        let big: Vec<_> = diffs.iter().filter(|(_, c, _, _)| *c > 55.0).collect();
        let mean_diff = diffs.iter().map(|(_, c, _, _)| c).sum::<f32>() / diffs.len() as f32;
        println!("rebases: {}", driver.rebase_count());
        println!("mean adjacent diff: {mean_diff:.1}%");
        println!("min per-frame flatness (MAD): {min_flat:.2}   flat frames (<2.0): {flat_frames}");
        println!("adjacent pairs >55%: {}", big.len());
        for (f, c, mad, mean) in big.iter().take(30) {
            println!("  frame {f}: diff {c:.1}% flatness {mad:.2} mean {mean:?}");
        }
        for &probe_f in &[0usize, 300, 900, 1500, 2100, 2670] {
            if let Some((_, _, mad, mean)) = diffs.iter().find(|(ff, _, _, _)| *ff >= probe_f) {
                println!("  ~frame {probe_f}: flatness {mad:.2} mean {mean:?}");
            }
        }
    }

    #[test]
    #[ignore]
    fn perf_probe_1024() {
        let ctx = match GpuContext::new_blocking() {
            Ok(c) => c,
            Err(_) => return,
        };
        let target = OffscreenTarget::new(&ctx, 1024, 1024);
        let anchor = find_interesting_target(8.0, MAX_ITER_PERT_CAP, 0);
        let nn = mandelbulb_normal_f64(anchor, 8.0, MAX_ITER_PERT_CAP);
        let cam_normal = [nn[0] as f32, nn[1] as f32, nn[2] as f32];
        for (max_steps, active_iter, label) in
            [(251, 12, "depth_frac~0.22"), (360, 24, "depth_frac~1.0")]
        {
            let state = MandelbulbPerturbedState {
                distance: 0.01,
                rotation: 0.3,
                power: 8.0,
                max_steps,
                hue_shift: 0.2,
                flash: 0.0,
                void_mix: 0.0,
                active_iter,
                cam_normal,
            };
            render_mandelbulb_perturbed(&ctx, &target, anchor, &state, 1.0).unwrap();
            let n = 5;
            let start = std::time::Instant::now();
            for _ in 0..n {
                render_mandelbulb_perturbed(&ctx, &target, anchor, &state, 1.0).unwrap();
                let _ = target.read_pixels(&ctx).unwrap();
            }
            println!(
                "{label}: {:.2} ms/frame",
                start.elapsed().as_secs_f32() * 1000.0 / n as f32
            );
        }
    }

    #[test]
    #[ignore]
    fn debug_anchor_and_hit_rate() {
        let anchor = find_interesting_target(8.0, MAX_ITER_PERT_CAP, 0);
        let nn = mandelbulb_normal_f64(anchor, 8.0, MAX_ITER_PERT_CAP);
        let cam_normal = [nn[0] as f32, nn[1] as f32, nn[2] as f32];
        let (dist, smooth) = mandelbulb_de_f64(anchor, 8.0, MAX_ITER_PERT_CAP);
        println!("anchor={anchor:?} DE(anchor)={dist} smooth={smooth}");
        let ctx = match GpuContext::new_blocking() {
            Ok(c) => c,
            Err(_) => return,
        };
        let size = 128;
        let target = OffscreenTarget::new(&ctx, size, size);
        for &distance in &[0.5f32, 0.1, 0.02, 5e-3, 1e-3, 3e-4, 1e-4, 5e-5] {
            for &rot in &[-0.6f32, -0.3, 0.0, 0.3, 0.6] {
                let state = MandelbulbPerturbedState {
                    distance,
                    rotation: rot,
                    power: 8.0,
                    max_steps: 400,
                    hue_shift: 0.0,
                    flash: 0.0,
                    void_mix: 0.0,
                    active_iter: 16,
                    cam_normal,
                };
                render_mandelbulb_perturbed(&ctx, &target, anchor, &state, 1.0).unwrap();
                let frame = target.read_pixels(&ctx).unwrap();
                let bg = [5i32, 5, 9];
                let mut hits = 0;
                let mut colors = std::collections::HashSet::new();
                for p in frame.chunks(4) {
                    colors.insert([p[0], p[1], p[2]]);
                    if (p[0] as i32 - bg[0]).abs() > 12
                        || (p[1] as i32 - bg[1]).abs() > 12
                        || (p[2] as i32 - bg[2]).abs() > 12
                    {
                        hits += 1;
                    }
                }
                println!(
                    "distance={distance:e} rot={rot:+.1} hits={hits:>5}/{} colors={}",
                    size * size,
                    colors.len()
                );
            }
        }
    }

    /// Real precision-floor probe behind `MandelbulbInfiniteDiveDriver`'s
    /// `REBASE_DIST=1e-4` — see that struct's own doc for the table this
    /// produces and how it was interpreted. `#[ignore]`d diagnostic, run
    /// with `cargo test -p hyst-render --release -- --ignored --nocapture
    /// perturbed_depth_probe`.
    #[test]
    #[ignore]
    fn perturbed_depth_probe() {
        let ctx = match GpuContext::new_blocking() {
            Ok(c) => c,
            Err(_) => return,
        };
        let size = 128;
        let target = OffscreenTarget::new(&ctx, size, size);
        let anchor = find_interesting_target(8.0, MAX_ITER_PERT_CAP, 0);
        let nn = mandelbulb_normal_f64(anchor, 8.0, MAX_ITER_PERT_CAP);
        let cam_normal = [nn[0] as f32, nn[1] as f32, nn[2] as f32];
        println!("anchor = {anchor:?}");
        for &distance in &[1e-1f32, 1e-3, 1e-4, 1e-5, 1e-6, 1e-7, 1e-8, 1e-9] {
            let base_state = MandelbulbPerturbedState {
                distance,
                rotation: 0.3,
                power: 8.0,
                max_steps: 440,
                hue_shift: 0.0,
                flash: 0.0,
                void_mix: 0.0,
                active_iter: 32,
                cam_normal,
            };
            render_mandelbulb_perturbed(&ctx, &target, anchor, &base_state, 1.0).unwrap();
            let frame_a = target.read_pixels(&ctx).unwrap();
            // Real detail signal (same technique `render_julia_perturbed`'s
            // own doc uses): distinct RGBA values across the frame. A
            // healthy render at any depth should show plenty of shading
            // variety; once the perturbation math degenerates the frame
            // collapses toward a small handful of colors (or one flat
            // color), same failure signature as Julia's own probe.
            use std::collections::HashSet;
            let distinct: HashSet<[u8; 4]> = frame_a
                .chunks(4)
                .map(|p| [p[0], p[1], p[2], p[3]])
                .collect();
            // Also a real 1% (not 0.01%) distance nudge, big enough that a
            // healthy dolly-zoom camera model must show a visibly
            // different frame (a 0.01% nudge turned out too small to move
            // any pixel across this test's own >4/255 threshold even at
            // healthy depths, found by actually running this probe first —
            // not assumed).
            let nudged = MandelbulbPerturbedState {
                distance: distance * 1.01,
                ..base_state
            };
            render_mandelbulb_perturbed(&ctx, &target, anchor, &nudged, 1.0).unwrap();
            let frame_b = target.read_pixels(&ctx).unwrap();
            let changed = frame_a
                .chunks(4)
                .zip(frame_b.chunks(4))
                .filter(|(a, b)| {
                    a.iter()
                        .zip(*b)
                        .any(|(x, y)| (*x as i32 - *y as i32).abs() > 4)
                })
                .count() as f32
                / (size * size) as f32;
            println!(
                "distance={distance:e} distinct-colors={} changed-vs-1%-nudged={:.3}%",
                distinct.len(),
                changed * 100.0
            );
        }
    }
}
