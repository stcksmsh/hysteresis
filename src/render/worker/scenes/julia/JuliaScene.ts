import type { Scene, SceneContext } from '../Scene'
import { createProgram } from '../../gl/program'
import fullscreenVertSrc from '../../gl/fullscreen.vert.glsl?raw'
import juliaFragSrc from './shaders/julia.frag.glsl?raw'
import beamVertSrc from './shaders/beam.vert.glsl?raw'
import beamFragSrc from './shaders/beam.frag.glsl?raw'
import { lissajousPoint } from './lissajous'
import { cardioidPoint } from './boundary'
import { SpringDamper } from '../../../choreography/spring-damper'
import type { ParamBus } from '../../../../shared/types'
import { SCOPE_SIZE } from '../../../../shared/constants'

// `c` continuously sweeps the Mandelbrot main cardioid's boundary (see
// boundary.ts) rather than orbiting a fixed hand-picked constant — this is
// what guarantees it never wanders into a flat filled-interior or empty-
// exterior region (both read as "one solid color") AND never repeats itself
// on any timescale a session runs for. θ only ever advances; there is no
// reset.
const THETA_SPEED_BASE = 0.008 // rad/sec at rest — one full boundary sweep in ~13min idle
const THETA_SPEED_WINDUP_GAIN = 0.02 // builds gently accelerate how fast the constant morphs
const THETA_SPEED_TENSION_GAIN = -0.006 // a break/suspension slows the morph — "held", not stalled
const THETA_DROP_JUMP = 0.1 // radians — a drop nudges into fresh boundary territory, not a cut

// Small radial wobble around the boundary itself: r<1 dips just inside the
// cardioid (connected, swirling Julia sets), r>1 just outside (dendrite/dust
// Julia sets) — both are still "on the interesting edge", just textured
// differently, so this adds variety without ever risking the flat regions
// further in/out.
const RADIAL_BASE = 1
const RADIAL_AMPLITUDE = 0.05
const RADIAL_SPEED = 0.013 // rad/sec, deliberately not a simple ratio of THETA_SPEED_BASE

const C_SPRING_STIFFNESS = 55
const C_SPRING_DAMPING = 16
const DROP_IMPULSE = 1.2 // extra velocity kick on top of the drop's theta jump, for snap

// Safety net, not the primary shaping force: hard-bounds the *rendered* `c`
// to a disc around the current (continuously moving) boundary target, so a
// stacked transient (drop landing on a zoom reset, say) still can't fling
// the view into flat territory, however the springs end up tuned.
const C_MAX_RADIUS = 0.05

// Perpetual zoom: the view continuously magnifies toward the origin — the
// critical point z=0, which for any Julia constant sits right at the
// frontier of the fractal's structure, so zooming into it never degrades to
// a flat filled region the way an arbitrary point could. Because `c` itself
// never stops moving, a reset never lands on the same fractal twice.
const ZOOM_START_MIN = 1.2
const ZOOM_START_MAX = 2.1 // randomised per cycle so resets don't all look identical either
// Above DIRECT_ZOOM_THRESHOLD, the shader iterates z = uPan + uv*uZoom
// directly — the exact same code path this scene used before perturbation
// existed, at the exact zoom range (down to the original ZOOM_MIN) it was
// already known to render correctly at. Only below that threshold does the
// shader switch to perturbation against a reference orbit (see
// REF_ORBIT_LENGTH / updateReferenceOrbit) to keep going deeper.
// Perturbation without rebasing has a real failure mode — localized
// blocky artifacts where a pixel's true orbit diverges from the shared
// reference — so ZOOM_MIN is deliberately a modest 2 orders of magnitude
// past the old floor, not the much deeper (and much glitchier in practice)
// value tried initially, to keep exposure to that failure mode small
// rather than eliminating it outright (which would need actual rebasing).
// Hitting ZOOM_MIN is treated as "genuinely as deep as this technique can
// go" — see the blackout-flash reset at the bottom of updateZoom.
const DIRECT_ZOOM_THRESHOLD = 0.0006
const ZOOM_MIN = 1e-6
const ZOOM_RATE_BASE = 0.018 // ln(zoom)/sec at rest — a full dive takes ~9min idle
const ZOOM_RATE_WINDUP_GAIN = 0.1 // builds accelerate the dive, gently — this used to run away
// Zoom runs at this fraction of normal speed until navConfidence (see
// updateNavigation) confirms real local detail has actually been found,
// ramping to full speed as it does — gives navigation real wall-clock time
// to reach good territory before the view scale moves on past it. Kept
// narrow (was 0.35, a ~2.9x speed swing) and slow to react (was 0.3/tick) —
// a bigger range and a snappier reaction were exactly what read as "speeds
// up/slows down instantly" instead of a smooth ramp.
const ZOOM_SEEK_MIN_FACTOR = 0.6
const NAV_CONFIDENCE_SMOOTH = 0.12 // how fast navConfidence reacts each check tick
// When local detail genuinely runs out (see updateNavigation's emptiness
// handling), the dive doesn't cut to a new random spot — it reverses into a
// continuous zoom-OUT reveal, watching the view pull back (at
// ZOOM_OUT_RATE, faster than the normal inward pace so the reveal doesn't
// drag) until it's ZOOM_RESET_WIDE — deliberately wider than any normal
// dive ever starts at, so the reveal reads as "oh, THAT's how far out we
// actually were" — at which point a fresh global search picks a new target
// and the dive continues inward from there. No cut, no blackout, and
// crucially this only fires as a last resort: updateNavigation tries a
// LOCAL re-search first (see LOCAL_RETARGET_RADIUS_FACTOR) so a dive keeps
// going as deep as it can before ever giving up and reversing.
const ZOOM_OUT_RATE = 0.05
const ZOOM_RESET_WIDE = 4
const ZOOM_OUT_PAN_RETURN_RATE = 0.3 // 1/sec — pan eases back toward the origin over the same reveal
// The flash brackets only the OTHER reset path (hitting ZOOM_MIN, the
// actual precision floor) — ramping to full black over the last
// PRE_FLASH_LOG_WINDOW of zoom (in ln units) before it, snapping the scale
// while the screen is dark, then fading back in. A multi-decade zoom-out
// animation from that depth would take far too long to be practical, so
// that path keeps the quick cut; the empty-space path above doesn't need
// one anymore since it's never a cut to begin with.
const PRE_FLASH_LOG_WINDOW = 0.5
const POST_FLASH_SEC = 0.28

// Each dive starts centered on the origin (the critical point z=0 — always
// structurally relevant at low zoom) and then drifts, gradually, toward
// whatever detail is nearby as it goes deeper.
//
// The earlier version scored a direction by how much its plain iteration
// count differed from the center's — but that responds to ANY smooth
// escape-time gradient, including the gentle falloff that exists all the
// way out in genuinely empty space (points further from the set escape
// gradually slower as you approach it, with no fractal structure involved
// at all). That's exactly what was dragging the view off into the void: the
// metric couldn't tell "smooth boring gradient" from "boundary detail".
//
// distanceEstimate() below is the standard escape-time *distance
// estimator* instead: it tracks dz/dz0 alongside the orbit and derives an
// actual estimate (in z-plane units) of how far the sample point is from
// the Julia set's boundary — small near boundary detail, large in a flat
// interior or exterior region, however smooth its escape-time gradient is.
// Converted to a score of current-zoom/(zoom+distance), it's ~1 when the
// boundary passes through the visible frame and ~0 when it doesn't, which
// is the actually-correct question for "is this worth zooming into".
const NAV_DIRECTIONS = 8
const NAV_PROBE_FRACTION = 0.5 // probe distance, as a fraction of the navigation scale below
const NAV_ITER_CAP = 60
const NAV_CHECK_INTERVAL_SEC = 0.25
const NAV_HEADING_SMOOTH = 0.15 // how much the heading turns toward the new reading each check
// Drift speed at full heading strength. Two caps, not one: NAV_PAN_SPEED is
// a fraction of the CURRENT zoom (so drift naturally slows as the view
// narrows), but early in a dive the zoom is still wide (~1.2-2.1), which
// alone let drift cover a lot of ground fast — NAV_PAN_SPEED_ABS_MAX is a
// hard ceiling in real z-plane units/sec, independent of zoom, so the start
// of a dive can't sprint just because the view happens to be wide.
const NAV_PAN_SPEED = 0.18
const NAV_PAN_SPEED_ABS_MAX = 0.09
// Scoring is XaoS's decades-old autopilot heuristic (see clusterScore()
// below): local color-diversity, not a continuous distance field — a
// smooth region genuinely samples as monochrome, near OR far from the set,
// so this has a real, unfakeable zero, unlike the distance-estimator
// approach tried earlier (which could always find SOME faint signal to
// chase, including in genuinely empty space, and had no natural stopping
// point). Vortex bias (see sampleOrbit's winding) is layered on top of
// diversity, not instead of it: points near a neutral/near-periodic point
// spiral several full turns before escaping — this converts that winding
// into a multiplier applied only among ALREADY-diverse candidates, so
// navigation prefers spiral structure over any other equally-diverse spot,
// without letting winding alone override the diversity gate.
// NAV_VORTEX_WINDING_SCALE (radians) is where the bonus is about
// half-saturated — roughly half a turn, from sampling real orbits;
// NAV_VORTEX_BOOST caps how much a maximally-spiraling point can outweigh
// a non-spiraling one at the same diversity.
const NAV_VORTEX_WINDING_SCALE = 4
const NAV_VORTEX_BOOST = 2.5
// How strongly pan is pulled toward the dive's searched-for vortex target
// (findVortexTarget/retarget) vs. the local probes. Both are blended as
// independently-weighted UNIT vectors (direction only), not raw scores —
// summing raw scores was the actual bug behind "doesn't track fast enough":
// clusterScore can return ~20+, so a target-pull weight of 2 was
// completely drowned out by any nearby local signal, meaning navigation
// almost never actually walked toward what it had found. Weighted as unit
// vectors, target pull stays meaningful regardless of clusterScore's
// magnitude; NAV_TARGET_PULL_WEIGHT > NAV_LOCAL_WEIGHT so the target
// dominates while far away, fading out (see targetWeight in
// updateNavigation) as pan actually arrives.
const NAV_LOCAL_WEIGHT = 1
const NAV_TARGET_PULL_WEIGHT = 2.5
const NAV_EMPTY_RETRY_AFTER_SEC = 0.6 // how long "nothing nearby" is tolerated before trying a local re-search
// Radius for the local re-search that runs when NAV_EMPTY_RETRY_AFTER_SEC
// elapses with nothing found — centered on the CURRENT pan (not the
// origin), scaled to the current zoom so it stays a "nearby" search rather
// than a jump clear across the frame. This is what lets a dive keep going
// deep instead of giving up at the first empty patch: only if THIS also
// finds nothing does updateZoom start the zoom-out reveal.
const LOCAL_RETARGET_RADIUS_FACTOR = 8 // local search radius = zoom * this, floored below
const LOCAL_RETARGET_RADIUS_MIN_FRACTION = 0.1 // ...but never narrower than this fraction of NAV_PAN_MAX_RADIUS
// Every filled Julia set is symmetric about the origin — (-z)^2+c = z^2+c —
// so with pan sitting exactly at (0,0), any probe direction and its exact
// opposite always score identically and the weighted heading vector cancels
// to precisely zero by construction; only floating-point noise broke the
// tie before, which is what made the very start of every dive feel
// erratic/undefined. Kicking the heading with a small random-direction
// nudge at the start of each dive breaks that degenerate tie with a real
// (if arbitrary) direction instead of noise, so real signal takes over
// within the first probe or two.
const NAV_INITIAL_HEADING_STRENGTH = 0.3
// Navigation's "how far/wide am I looking" scale is independent of the
// actual render zoom below this floor: without it, once the render zoom
// shrinks past whatever distance away the nearest detail was, the probe
// ring shrinks right along with it and goes blind to structure it could
// clearly see a few seconds earlier — verified by simulation to be the main
// cause of "reaches empty and drifts/resets immediately". Floored relative
// to the fixed cap below, not the current zoom, so navigation keeps a
// sensible lookahead for most of a dive.
const NAV_SCALE_MIN_FRACTION = 0.08
// Hard backstop, not the primary shaping force. Fixed, not scaled to the
// dive's (randomised, up to 2.1) starting zoom — every c this scene ever
// renders has |c| <= 0.75 (the cardioid sweep's own max, at c=-0.75), and
// any point with |z| > 2 is PROVABLY on a trivially-escaping trajectory for
// any |c| < 2 — that's the standard escape-radius bound, not a heuristic.
// 0.8 sits comfortably inside that guaranteed-non-trivial disc, which
// simulation confirmed is generally enough room to reach real detail
// without ever approaching the unconditionally-empty region beyond |z|=2.
const NAV_PAN_MAX_RADIUS = 0.8

const IDLE_DRIFT_SPEED = 0.05 // rad/sec — slow enough to read as "stationary", not spinning

const IDLE_BEAM_POINTS = 220
const BEAM_HALF_WIDTH = 0.006
const BEAM_INTENSITY_IDLE = 0.5
const BEAM_INTENSITY_PLAYING = 1.1
const BEAM_SCOPE_GAIN = 3.2
const MAX_SEGMENTS = Math.max(SCOPE_SIZE - 1, IDLE_BEAM_POINTS - 1)

// Must match julia.frag.glsl's `const int MAX_ITER` exactly — there's no
// build-time link between the two, this is the one place that has to stay
// in sync by hand.
const REF_ORBIT_LENGTH = 192

interface JuliaUniforms {
  uC: WebGLUniformLocation | null
  uPan: WebGLUniformLocation | null
  uAspect: WebGLUniformLocation | null
  uZoom: WebGLUniformLocation | null
  uAccent: WebGLUniformLocation | null
  uHueShift: WebGLUniformLocation | null
  uPaletteMix: WebGLUniformLocation | null
  uPaletteFlip: WebGLUniformLocation | null
  uFlash: WebGLUniformLocation | null
  uRefOrbit: WebGLUniformLocation | null
  uPerturbThreshold: WebGLUniformLocation | null
}

interface BeamUniforms {
  uAspect: WebGLUniformLocation | null
  uHalfWidth: WebGLUniformLocation | null
  uColor: WebGLUniformLocation | null
  uIntensity: WebGLUniformLocation | null
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v))
}

// Escape iteration count (the same integer XaoS calls a pixel's "color")
// plus total winding |Δarg(z)| along the same orbit — spiraling near a
// neutral/near-periodic point before escaping, which is what the "vortex"
// structures actually are. Both come from one orbit walk, so tracking
// winding here is free.
interface OrbitSample {
  iter: number // 0..cap; cap itself is its own bucket ("never escaped")
  winding: number
}

function sampleOrbit(zx0: number, zy0: number, cx: number, cy: number, cap: number): OrbitSample {
  let zx = zx0
  let zy = zy0
  let prevAngle = Math.atan2(zy0, zx0)
  let winding = 0
  let iter = 0
  for (; iter < cap; iter++) {
    const nzx = zx * zx - zy * zy + cx
    const nzy = 2 * zx * zy + cy
    zx = nzx
    zy = nzy
    const angle = Math.atan2(zy, zx)
    let delta = angle - prevAngle
    if (delta > Math.PI) delta -= 2 * Math.PI
    else if (delta < -Math.PI) delta += 2 * Math.PI
    winding += Math.abs(delta)
    prevAngle = angle
    if (zx * zx + zy * zy > 4) break
  }
  return { iter, winding }
}

// XaoS's autopilot heuristic (this scene's earlier distance-estimator
// approach kept getting fooled by smooth gradients that exist all the way
// out in genuinely empty space, since it measured a continuous analytic
// field that's technically nonzero almost everywhere — this measures the
// literal, unfakeable thing instead): sample a small cluster of points
// around a candidate and count how many DISTINCT escape-iteration values
// show up. A boundary-adjacent region has several different colors nearby
// (escape time changes fast); a smooth region — near OR far from the set —
// has only one (everything nearby escapes alike). "Different colors
// nearby" can't be faked by a smooth far-field the way a small analytic
// distance estimate can. Winding is folded in only as a bonus among
// already-confirmed-diverse candidates, biasing toward spiral structure
// specifically rather than any boundary-adjacent point equally.
const DIVERSITY_SAMPLES = 6
const DIVERSITY_CLUSTER_FRACTION = 0.15 // cluster spread, relative to the candidate's own probe radius

function clusterScore(px: number, py: number, clusterRadius: number, cx: number, cy: number, cap: number): number {
  const seen = new Set<number>()
  let windingSum = 0
  for (let i = 0; i < DIVERSITY_SAMPLES; i++) {
    const angle = (i / DIVERSITY_SAMPLES) * Math.PI * 2
    const sx = px + Math.cos(angle) * clusterRadius
    const sy = py + Math.sin(angle) * clusterRadius
    const sample = sampleOrbit(sx, sy, cx, cy, cap)
    seen.add(sample.iter)
    windingSum += sample.winding
  }
  const diversity = seen.size
  if (diversity <= 1) return 0 // monochrome neighborhood — XaoS's literal "boring" criterion
  const avgWinding = windingSum / DIVERSITY_SAMPLES
  const vortex = 1 - Math.exp(-avgWinding / NAV_VORTEX_WINDING_SCALE)
  return diversity * (1 + NAV_VORTEX_BOOST * vortex)
}

// Actively searches for a genuine vortex point instead of hoping the local
// hill-climb in updateNavigation() stumbles onto one by drifting — that
// local walk is a fine-tuning refinement, not a search. Mirrors XaoS's own
// "randomly looks around... zooms to the first area containing both inside
// and outside points" — just more thorough, since this only runs once per
// dive (cheap enough to be: ~100 candidates × a real iteration cap).
const VORTEX_SEARCH_RINGS = 6
const VORTEX_SEARCH_PER_RING = 16
const VORTEX_SEARCH_ITER_CAP = 90

// `centerX/Y` lets the same search run either globally from the origin (a
// fresh dive) or locally around the current pan (a nearby re-search when
// the dive's original target has run dry — see LOCAL_RETARGET_RADIUS_FACTOR).
// `found` is false when every candidate scored 0 — the caller's signal to
// escalate rather than aim at the meaningless (centerX, centerY) fallback.
function findVortexTarget(
  cx: number,
  cy: number,
  maxRadius: number,
  centerX = 0,
  centerY = 0,
): { x: number; y: number; found: boolean } {
  let bestScore = 0
  let bestX = centerX
  let bestY = centerY
  let found = false
  for (let r = 1; r <= VORTEX_SEARCH_RINGS; r++) {
    const radius = (r / VORTEX_SEARCH_RINGS) * maxRadius
    const stagger = r * 0.37 // offsets each ring's angles so candidates don't line up radially
    const clusterRadius = radius * DIVERSITY_CLUSTER_FRACTION
    for (let i = 0; i < VORTEX_SEARCH_PER_RING; i++) {
      const angle = (i / VORTEX_SEARCH_PER_RING) * Math.PI * 2 + stagger
      const x = centerX + Math.cos(angle) * radius
      const y = centerY + Math.sin(angle) * radius
      const score = clusterScore(x, y, clusterRadius, cx, cy, VORTEX_SEARCH_ITER_CAP)
      if (score > bestScore) {
        bestScore = score
        bestX = x
        bestY = y
        found = true
      }
    }
  }
  return { x: bestX, y: bestY, found }
}

// The Julia substrate + oscilloscope beam as one visual identity
// (SINTEZA_VIZ.md §4) — not two selectable scenes. Substrate carries mood and
// memory via a slowly-chased `c`; the beam rides on top as the sharp,
// legible, beat-carrying element.
export class JuliaScene implements Scene {
  readonly id = 'julia'
  readonly wantsPersistencePass = false
  readonly wantsMemoryField = true
  readonly wantsBloom = true

  private gl!: WebGL2RenderingContext
  private juliaProgram!: WebGLProgram
  private beamProgram!: WebGLProgram
  private quad!: WebGLVertexArrayObject
  private juliaUniforms!: JuliaUniforms
  private beamUniforms!: BeamUniforms

  private refOrbitTexture!: WebGLTexture
  private refOrbitData = new Float32Array(REF_ORBIT_LENGTH * 2)

  private beamVao!: WebGLVertexArrayObject
  private beamCornerBuffer!: WebGLBuffer
  private beamP0Buffer!: WebGLBuffer
  private beamP1Buffer!: WebGLBuffer
  private beamP0Data = new Float32Array(MAX_SEGMENTS * 2)
  private beamP1Data = new Float32Array(MAX_SEGMENTS * 2)
  private beamSegmentCount = 0
  private beamIntensity = BEAM_INTENSITY_IDLE

  private width = 0
  private height = 0
  private aspect = 1
  private accent: [number, number, number] = [1, 0.36, 0.22] // vermilion default (#FF5C38)

  private thetaSweep = 0
  private radialPhase = 0
  private springCx: SpringDamper
  private springCy: SpringDamper
  private idleClockSec = 0
  private paletteFlip = 0
  private hueShift = 0
  private paletteMix = 0
  private zoomStart = ZOOM_START_MAX
  private zoomLog = Math.log(this.zoomStart)
  // True while the dive is in the zoom-OUT reveal (see ZOOM_RESET_WIDE)
  // instead of diving normally — updateZoom drives zoomLog/pan differently
  // in this state.
  private zoomingOut = false
  private flash = 0
  private postFlash = 0

  // Where the view is currently zooming toward — starts at the origin every
  // cycle, then drifts toward nearby detail as updateNavigation() steers it
  // (see the NAV_* comment above). headingX/Y is the current drift
  // direction (unit-ish vector, low-pass filtered — this is what makes the
  // motion gradual instead of snapping). searchTargetX/Y is the concrete
  // vortex point found by findVortexTarget() at the start of this dive —
  // updateNavigation() pulls toward it directly (not just the local
  // 8-direction refinement), so the dive is aimed at a confirmed spiral
  // point from the outset instead of hoping to wander into one.
  private panX = 0
  private panY = 0
  private headingX = 0
  private headingY = 0
  private searchTargetX = 0
  private searchTargetY = 0
  private navEmptySec = 0
  private navConfidence = 0
  private navCheckAccum = 0

  constructor() {
    const start = cardioidPoint(0)
    this.springCx = new SpringDamper(C_SPRING_STIFFNESS, C_SPRING_DAMPING, start.x * RADIAL_BASE)
    this.springCy = new SpringDamper(C_SPRING_STIFFNESS, C_SPRING_DAMPING, start.y * RADIAL_BASE)
    this.retarget(start.x * RADIAL_BASE, start.y * RADIAL_BASE)
  }

  // Called at the start of every dive (constructor + every reset): finds a
  // real vortex point and aims the initial heading straight at it, instead
  // of the old random-direction tie-break kick.
  private retarget(cx: number, cy: number): void {
    const target = findVortexTarget(cx, cy, NAV_PAN_MAX_RADIUS)
    this.searchTargetX = target.x
    this.searchTargetY = target.y
    const dist = Math.hypot(target.x, target.y) || 1
    this.headingX = (target.x / dist) * NAV_INITIAL_HEADING_STRENGTH
    this.headingY = (target.y / dist) * NAV_INITIAL_HEADING_STRENGTH
  }

  init(ctx: SceneContext): void {
    this.gl = ctx.gl
    this.juliaProgram = createProgram(ctx.gl, fullscreenVertSrc, juliaFragSrc)
    this.beamProgram = createProgram(ctx.gl, beamVertSrc, beamFragSrc)
    this.quad = this.createFullscreenQuad()
    this.cacheUniforms()
    this.beamVao = this.createBeamGeometry()
    this.refOrbitTexture = this.createRefOrbitTexture()
    this.resize(ctx)
  }

  resize(ctx: SceneContext): void {
    this.width = ctx.width
    this.height = ctx.height
    this.aspect = ctx.width / Math.max(1, ctx.height)
  }

  update(dt: number, params: ParamBus): void {
    this.hueShift = params.hueShift
    this.paletteMix = params.paletteMix

    if (params.idle) this.idleClockSec += dt // still drives the beam's idle figure only

    // windup is a spring output and can briefly overshoot past 1 on release
    // (that's the intended "punch" elsewhere) — clamped here so a transient
    // overshoot can't spike the sweep/zoom rate into feeling glitchy.
    const windup = clamp(params.windup, 0, 1)
    const suspension = clamp(Math.max(params.tension, params.suspension), 0, 1)
    const thetaSpeed = THETA_SPEED_BASE + THETA_SPEED_WINDUP_GAIN * windup + THETA_SPEED_TENSION_GAIN * suspension
    this.thetaSweep += Math.max(0.003, thetaSpeed) * dt // never fully stalls, even under heavy tension
    this.radialPhase += RADIAL_SPEED * dt

    // Deliberately NOT reading onsetPulses here — they fire per spectral
    // band per hop (dozens/sec during a dense mix), and kicking theta on
    // each one was the actual source of the "glitchy, too fast" motion:
    // a burst of onsets could advance the sweep and yank `c` several times
    // in one rendered frame. Only structural events below move `c` directly.
    if (params.dropTrigger?.active) {
      // A drop leaps the boundary target forward (fresh territory) and gives
      // the spring an extra kick — reads as a rupture, not a restart, and
      // guarantees back-to-back drops never land on the same fractal twice.
      const strength = clamp(params.dropTrigger.strength, 0, 1)
      this.thetaSweep += THETA_DROP_JUMP * (0.5 + strength)
      this.springCx.addImpulse(DROP_IMPULSE * strength)
      this.springCy.addImpulse(-DROP_IMPULSE * strength * 0.7)
      this.paletteFlip = this.paletteFlip === 0 ? 1 : 0
    }

    const radius = RADIAL_BASE + RADIAL_AMPLITUDE * Math.sin(this.radialPhase)
    const target = cardioidPoint(this.thetaSweep)
    this.springCx.setTarget(target.x * radius)
    this.springCy.setTarget(target.y * radius)
    this.springCx.update(dt)
    this.springCy.update(dt)

    this.updateNavigation(dt)
    this.updateZoom(dt, params)
    this.updateBeamGeometry(params)
  }

  // Periodically probes NAV_DIRECTIONS points around the current pan, at a
  // distance scaled to the current zoom, using the same iteration the
  // shader runs (far fewer iterations) — combined into one score-weighted
  // heading vector (a sum over all directions, not just the single best
  // one), which is then low-pass filtered into `heading` so it only ever
  // turns gradually. `heading` gets integrated into `panX/panY` every
  // frame, continuously, so the drift itself is smooth regardless of how
  // choppy any one tick's reading is. If the combined vector stays near
  // zero — no direction stands out at all — that's "reached empty space":
  // held for NAV_EMPTY_RETRY_AFTER_SEC before trying a local re-search, and
  // only escalating to the zoom-out reveal (see updateZoom) if that also
  // comes up empty.
  private updateNavigation(dt: number): void {
    // While zooming back out (see updateZoomOut), pan is being eased back
    // toward the origin directly — searching/steering against a target
    // that's about to be discarded anyway would just fight that motion.
    if (this.zoomingOut) return

    this.navCheckAccum += dt
    if (this.navCheckAccum >= NAV_CHECK_INTERVAL_SEC) {
      this.navCheckAccum = 0

      const cx = this.springCx.current
      const cy = this.springCy.current
      const navScale = Math.max(this.zoom, NAV_PAN_MAX_RADIUS * NAV_SCALE_MIN_FRACTION)
      const probe = navScale * NAV_PROBE_FRACTION
      const clusterRadius = probe * DIVERSITY_CLUSTER_FRACTION

      let sumX = 0
      let sumY = 0
      let totalScore = 0
      for (let i = 0; i < NAV_DIRECTIONS; i++) {
        const angle = (i / NAV_DIRECTIONS) * Math.PI * 2
        const dirX = Math.cos(angle)
        const dirY = Math.sin(angle)
        // clusterScore() already reads 0 for a monochrome (XaoS: "boring")
        // neighborhood, so there's no separate gate needed here.
        const score = clusterScore(this.panX + dirX * probe, this.panY + dirY * probe, clusterRadius, cx, cy, NAV_ITER_CAP)
        sumX += dirX * score
        sumY += dirY * score
        totalScore += score
      }

      // Blend the local probe direction and a persistent pull toward the
      // vortex point found at dive-start (see findVortexTarget/retarget) as
      // two independently-weighted UNIT vectors — NOT raw scores summed
      // together (that was the bug: clusterScore's own magnitude varies a
      // lot, so a fixed-weight raw-score pull could be drowned out or
      // dominate unpredictably depending on how "loud" the local reading
      // happened to be). This way the target's pull strength is stable and
      // predictable regardless of clusterScore's scale, and fades out on
      // its own terms (targetWeight, below) as pan actually arrives.
      const localLen = Math.hypot(sumX, sumY)
      const localDirX = localLen > 0 ? sumX / localLen : 0
      const localDirY = localLen > 0 ? sumY / localLen : 0

      const toTargetX = this.searchTargetX - this.panX
      const toTargetY = this.searchTargetY - this.panY
      const toTargetDist = Math.hypot(toTargetX, toTargetY)
      // Normalized against the fixed pan disc (NAV_PAN_MAX_RADIUS), NOT
      // navScale — navScale IS the current zoom, which stays wide early in
      // a dive, and a real bug had this pull fading out too early exactly
      // when it needed to be strongest: toTargetDist (~0.3) divided by a
      // wide navScale (~1.5) gave a weak pull, zoom stayed slow because
      // "not arrived" (see below), zoom staying wide kept navScale wide,
      // which kept the pull weak — a feedback loop that could stall for
      // 10s of seconds. The disc size doesn't change during a dive, so this
      // has no such loop.
      const targetWeight = toTargetDist > 1e-6 ? Math.min(1, toTargetDist / NAV_PAN_MAX_RADIUS) * NAV_TARGET_PULL_WEIGHT : 0
      const targetDirX = toTargetDist > 1e-6 ? toTargetX / toTargetDist : 0
      const targetDirY = toTargetDist > 1e-6 ? toTargetY / toTargetDist : 0

      const desiredX = localDirX * NAV_LOCAL_WEIGHT + targetDirX * targetWeight
      const desiredY = localDirY * NAV_LOCAL_WEIGHT + targetDirY * targetWeight

      if (totalScore > 0 || targetWeight > 0) {
        const len = Math.hypot(desiredX, desiredY) || 1
        this.headingX += (desiredX / len - this.headingX) * NAV_HEADING_SMOOTH
        this.headingY += (desiredY / len - this.headingY) * NAV_HEADING_SMOOTH
      } else {
        // Nothing nearby AND already arrived at the target — let the drift
        // itself wind down rather than keep pushing.
        this.headingX *= 1 - NAV_HEADING_SMOOTH
        this.headingY *= 1 - NAV_HEADING_SMOOTH
      }

      // How confident we are that real detail is CURRENTLY found — eases
      // toward 1 while totalScore > 0, toward 0 otherwise. This (not
      // distance to searchTarget) is what updateZoom's seek-slowdown reads:
      // the local hill-climb often converges onto a genuine nearby diversity
      // peak that isn't exactly the coarser pre-search's coordinate (found
      // with much wider probe spacing) and happily orbits it — which is
      // correct, that's still real detail — but gating zoom speed on
      // "reached that exact point" never recognized it as arrived, and
      // stayed throttled indefinitely even with detail already on screen.
      this.navConfidence += ((totalScore > 0 ? 1 : 0) - this.navConfidence) * NAV_CONFIDENCE_SMOOTH

      // Emptiness is judged purely on LOCAL detail, independent of the
      // target pull — this is what still correctly reacts if the immediate
      // neighborhood really is void, target or no target (e.g. still
      // early, en route, or the searched target turns out to have been a
      // marginal call).
      if (totalScore > 0) {
        this.navEmptySec = 0
      } else {
        this.navEmptySec += NAV_CHECK_INTERVAL_SEC
        if (this.navEmptySec > NAV_EMPTY_RETRY_AFTER_SEC) {
          this.navEmptySec = 0
          // First line of defense: search again, but LOCALLY — centered on
          // where we already are, at a radius scaled to the current zoom —
          // rather than giving up. This is what lets a dive keep going as
          // deep as possible instead of reversing at the first dry patch.
          const localRadius = Math.max(this.zoom * LOCAL_RETARGET_RADIUS_FACTOR, NAV_PAN_MAX_RADIUS * LOCAL_RETARGET_RADIUS_MIN_FRACTION)
          const local = findVortexTarget(cx, cy, localRadius, this.panX, this.panY)
          if (local.found) {
            this.searchTargetX = local.x
            this.searchTargetY = local.y
          } else {
            // Nothing findable nearby at all, even after that — only now
            // does the dive give up and start the zoom-out reveal.
            this.zoomingOut = true
          }
        }
      }
    }

    const speed = Math.min(this.zoom * NAV_PAN_SPEED, NAV_PAN_SPEED_ABS_MAX)
    this.panX += this.headingX * speed * dt
    this.panY += this.headingY * speed * dt

    // Hard backstop (see NAV_PAN_MAX_RADIUS) — independent of how well the
    // distance estimate is scoring things, pan structurally cannot leave
    // this disc.
    const dist = Math.hypot(this.panX, this.panY)
    if (dist > NAV_PAN_MAX_RADIUS) {
      const nx = this.panX / dist
      const ny = this.panY / dist
      this.panX = nx * NAV_PAN_MAX_RADIUS
      this.panY = ny * NAV_PAN_MAX_RADIUS
      // Remove only the outward-pointing component of heading, keep
      // whatever's tangential — slides along the wall looking for a way
      // in, instead of fighting straight into it every frame.
      const radial = this.headingX * nx + this.headingY * ny
      if (radial > 0) {
        this.headingX -= radial * nx
        this.headingY -= radial * ny
      }
    }
  }

  private updateZoom(dt: number, params: ParamBus): void {
    if (this.zoomingOut) {
      this.updateZoomOut(dt)
      return
    }

    const windup = clamp(params.windup, 0, 1)
    // Throttled until navConfidence (see updateNavigation) confirms real
    // local detail has actually been found — full zoom speed once it has.
    // Without this, zoom was outracing navigation: by the time pan reached
    // good territory, the view had often already shrunk well past the
    // scale that mattered, so tracking never looked like it "worked" even
    // when pan genuinely was headed the right way.
    const seekSlowdown = ZOOM_SEEK_MIN_FACTOR + (1 - ZOOM_SEEK_MIN_FACTOR) * this.navConfidence
    const rate = (ZOOM_RATE_BASE + ZOOM_RATE_WINDUP_GAIN * windup) * seekSlowdown
    this.zoomLog -= rate * dt

    const logFloor = Math.log(ZOOM_MIN)
    const remaining = this.zoomLog - logFloor
    const preFlash = remaining < PRE_FLASH_LOG_WINDOW ? 1 - clamp(remaining / PRE_FLASH_LOG_WINDOW, 0, 1) : 0

    if (remaining <= 0) {
      // The actual precision floor — genuinely as deep as this technique
      // can go (see ZOOM_MIN/DIRECT_ZOOM_THRESHOLD). A multi-decade
      // zoom-out animation from here would take far too long to be
      // practical, so — unlike the empty-space path — this keeps the
      // quick blackout-flash cut.
      this.navEmptySec = 0
      this.navConfidence = 0
      this.zoomStart = ZOOM_START_MIN + Math.random() * (ZOOM_START_MAX - ZOOM_START_MIN)
      this.zoomLog = Math.log(this.zoomStart)
      this.panX = 0
      this.panY = 0
      this.retarget(this.springCx.current, this.springCy.current)
      this.postFlash = 1
    }
    this.postFlash = Math.max(0, this.postFlash - dt / POST_FLASH_SEC)
    this.flash = Math.max(preFlash, this.postFlash)
  }

  // The "went into empty space" path (as opposed to hitting the precision
  // floor above): rather than cut to a new spot, pull back out — continuing
  // to render the whole way, so the viewer watches it happen — until the
  // view is ZOOM_RESET_WIDE (deliberately wider than any normal dive starts
  // at, so this reads as "oh, THAT's how far out we actually were" rather
  // than just another reset), then pick a fresh global target and resume
  // diving from there. No cut, no flash.
  private updateZoomOut(dt: number): void {
    this.zoomLog += ZOOM_OUT_RATE * dt
    const panDist = Math.hypot(this.panX, this.panY)
    if (panDist > 1e-4) {
      const ease = Math.min(1, ZOOM_OUT_PAN_RETURN_RATE * dt)
      this.panX -= this.panX * ease
      this.panY -= this.panY * ease
    }

    if (this.zoomLog >= Math.log(ZOOM_RESET_WIDE)) {
      // Resume diving from exactly here — no snap back down to a normal
      // ZOOM_START_MIN..MAX value, which would just trade the big cut for a
      // smaller but still-visible one. panX/panY are already ~0 from the
      // easing above.
      this.zoomingOut = false
      this.navEmptySec = 0
      this.navConfidence = 0
      this.zoomStart = ZOOM_RESET_WIDE
      this.retarget(this.springCx.current, this.springCy.current)
    }

    this.postFlash = Math.max(0, this.postFlash - dt / POST_FLASH_SEC)
    this.flash = this.postFlash
  }

  private get zoom(): number {
    return Math.exp(this.zoomLog)
  }

  // Clamps only the rendered value, not the spring's own internal state —
  // the spring keeps chasing the (already-nearby) moving target normally,
  // this just guarantees the worst-case transient can never leave the
  // interesting annulus around it, however the springs end up tuned.
  private boundedC(): { x: number; y: number } {
    const radius = RADIAL_BASE + RADIAL_AMPLITUDE * Math.sin(this.radialPhase)
    const target = cardioidPoint(this.thetaSweep)
    const tx = target.x * radius
    const ty = target.y * radius
    const dx = this.springCx.current - tx
    const dy = this.springCy.current - ty
    const dist = Math.hypot(dx, dy)
    if (dist <= C_MAX_RADIUS) return { x: this.springCx.current, y: this.springCy.current }
    const scale = C_MAX_RADIUS / dist
    return { x: tx + dx * scale, y: ty + dy * scale }
  }

  // Reference orbit for the shader's perturbation iteration (see
  // julia.frag.glsl's iterate()): Z_0 = pan exactly, then the plain
  // un-perturbed z^2+c orbit from there, computed in JS (double precision —
  // this is the whole reason perturbation helps at all, since GLSL ES has
  // no double type). Both `c` (continuously swept) and `pan` (continuously
  // steered) change every frame, so this has to be recomputed and
  // re-uploaded every frame too — REF_ORBIT_LENGTH iterations of plain
  // arithmetic plus a few-KB texture upload, both trivial costs.
  private updateReferenceOrbit(cx: number, cy: number): void {
    const gl = this.gl
    let zx = this.panX
    let zy = this.panY
    for (let i = 0; i < REF_ORBIT_LENGTH; i++) {
      this.refOrbitData[i * 2] = zx
      this.refOrbitData[i * 2 + 1] = zy
      const nzx = zx * zx - zy * zy + cx
      const nzy = 2 * zx * zy + cy
      zx = nzx
      zy = nzy
    }
    gl.bindTexture(gl.TEXTURE_2D, this.refOrbitTexture)
    gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, REF_ORBIT_LENGTH, 1, gl.RG, gl.FLOAT, this.refOrbitData)
  }

  private createRefOrbitTexture(): WebGLTexture {
    const gl = this.gl
    const texture = gl.createTexture()
    if (!texture) throw new Error('Failed to create reference-orbit texture')
    gl.bindTexture(gl.TEXTURE_2D, texture)
    // texelFetch (what the shader uses to read this) ignores filtering and
    // wrap mode entirely, but the texture still needs to be complete.
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE)
    // RG32F sampling is core WebGL2 (no extension needed) as long as it's
    // only ever sampled, never rendered to — which is all this does.
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RG32F, REF_ORBIT_LENGTH, 1, 0, gl.RG, gl.FLOAT, null)
    return texture
  }

  render(targetFbo: WebGLFramebuffer | null): void {
    const gl = this.gl
    gl.bindFramebuffer(gl.FRAMEBUFFER, targetFbo)
    gl.viewport(0, 0, this.width, this.height)
    gl.disable(gl.BLEND)

    gl.useProgram(this.juliaProgram)
    const c = this.boundedC()
    const zoom = this.zoom
    // Only worth computing/uploading once the shader will actually read it
    // (see DIRECT_ZOOM_THRESHOLD) — for most of a dive it won't.
    if (zoom <= DIRECT_ZOOM_THRESHOLD) {
      this.updateReferenceOrbit(c.x, c.y)
    }
    gl.activeTexture(gl.TEXTURE0)
    gl.bindTexture(gl.TEXTURE_2D, this.refOrbitTexture)
    gl.uniform1i(this.juliaUniforms.uRefOrbit, 0)
    gl.uniform1f(this.juliaUniforms.uPerturbThreshold, DIRECT_ZOOM_THRESHOLD)
    gl.uniform2f(this.juliaUniforms.uC, c.x, c.y)
    gl.uniform2f(this.juliaUniforms.uPan, this.panX, this.panY)
    gl.uniform1f(this.juliaUniforms.uAspect, this.aspect)
    gl.uniform1f(this.juliaUniforms.uZoom, zoom)
    gl.uniform3f(this.juliaUniforms.uAccent, this.accent[0], this.accent[1], this.accent[2])
    gl.uniform1f(this.juliaUniforms.uHueShift, this.hueShift)
    gl.uniform1f(this.juliaUniforms.uPaletteMix, this.paletteMix)
    gl.uniform1f(this.juliaUniforms.uPaletteFlip, this.paletteFlip)
    gl.uniform1f(this.juliaUniforms.uFlash, this.flash)
    this.drawFullscreenQuad()

    if (this.beamSegmentCount > 0 && this.flash < 0.98) {
      gl.enable(gl.BLEND)
      gl.blendFunc(gl.ONE, gl.ONE)
      gl.useProgram(this.beamProgram)
      gl.uniform1f(this.beamUniforms.uAspect, this.aspect)
      gl.uniform1f(this.beamUniforms.uHalfWidth, BEAM_HALF_WIDTH)
      gl.uniform3f(this.beamUniforms.uColor, this.accent[0], this.accent[1], this.accent[2])
      gl.uniform1f(this.beamUniforms.uIntensity, this.beamIntensity * (1 - this.flash))
      gl.bindVertexArray(this.beamVao)
      gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, this.beamSegmentCount)
      gl.bindVertexArray(null)
      gl.disable(gl.BLEND)
    }
  }

  dispose(): void {
    const gl = this.gl
    gl.deleteProgram(this.juliaProgram)
    gl.deleteProgram(this.beamProgram)
    gl.deleteVertexArray(this.quad)
    gl.deleteVertexArray(this.beamVao)
    gl.deleteBuffer(this.beamCornerBuffer)
    gl.deleteBuffer(this.beamP0Buffer)
    gl.deleteBuffer(this.beamP1Buffer)
    gl.deleteTexture(this.refOrbitTexture)
  }

  setAccent(rgb: [number, number, number]): void {
    this.accent = rgb
  }

  private updateBeamGeometry(params: ParamBus): void {
    const gl = this.gl
    const scope = params.idle ? null : params.scope

    if (scope) {
      const n = scope.length
      this.beamSegmentCount = n - 1
      for (let i = 0; i < n; i++) {
        const x = (i / (n - 1)) * 1.8 - 0.9
        const y = clamp(scope[i] * BEAM_SCOPE_GAIN, -0.9, 0.9)
        if (i < n - 1) {
          this.beamP0Data[i * 2] = x
          this.beamP0Data[i * 2 + 1] = y
        }
        if (i > 0) {
          this.beamP1Data[(i - 1) * 2] = x
          this.beamP1Data[(i - 1) * 2 + 1] = y
        }
      }
      this.beamIntensity = BEAM_INTENSITY_PLAYING
    } else {
      const n = IDLE_BEAM_POINTS
      this.beamSegmentCount = n - 1
      const phase = this.idleClockSec * 0.15
      for (let i = 0; i < n; i++) {
        const theta = (i / (n - 1)) * Math.PI * 2
        const p = lissajousPoint(theta, phase)
        if (i < n - 1) {
          this.beamP0Data[i * 2] = p.x * 0.75
          this.beamP0Data[i * 2 + 1] = p.y * 0.75
        }
        if (i > 0) {
          this.beamP1Data[(i - 1) * 2] = p.x * 0.75
          this.beamP1Data[(i - 1) * 2 + 1] = p.y * 0.75
        }
      }
      this.beamIntensity = BEAM_INTENSITY_IDLE
    }

    gl.bindBuffer(gl.ARRAY_BUFFER, this.beamP0Buffer)
    gl.bufferSubData(gl.ARRAY_BUFFER, 0, this.beamP0Data, 0, this.beamSegmentCount * 2)
    gl.bindBuffer(gl.ARRAY_BUFFER, this.beamP1Buffer)
    gl.bufferSubData(gl.ARRAY_BUFFER, 0, this.beamP1Data, 0, this.beamSegmentCount * 2)
  }

  private createFullscreenQuad(): WebGLVertexArrayObject {
    const gl = this.gl
    const vao = gl.createVertexArray()
    if (!vao) throw new Error('Failed to create VAO')
    gl.bindVertexArray(vao)
    const buffer = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer)
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW)
    gl.enableVertexAttribArray(0)
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0)
    gl.bindVertexArray(null)
    return vao
  }

  private drawFullscreenQuad(): void {
    const gl = this.gl
    gl.bindVertexArray(this.quad)
    gl.drawArrays(gl.TRIANGLES, 0, 3)
    gl.bindVertexArray(null)
  }

  // One shared quad (2 triangles as a strip) instanced once per segment;
  // per-instance p0/p1 attributes are re-uploaded every frame in
  // updateBeamGeometry. See beam.vert.glsl for the expansion math.
  private createBeamGeometry(): WebGLVertexArrayObject {
    const gl = this.gl
    const vao = gl.createVertexArray()
    if (!vao) throw new Error('Failed to create beam VAO')
    gl.bindVertexArray(vao)

    const cornerBuffer = gl.createBuffer()
    if (!cornerBuffer) throw new Error('Failed to create corner buffer')
    gl.bindBuffer(gl.ARRAY_BUFFER, cornerBuffer)
    // Triangle strip: (-0.5,0) (-0.5,1) (0.5,0) (0.5,1)
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-0.5, 0, -0.5, 1, 0.5, 0, 0.5, 1]), gl.STATIC_DRAW)
    gl.enableVertexAttribArray(0)
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0)
    this.beamCornerBuffer = cornerBuffer

    const p0Buffer = gl.createBuffer()
    if (!p0Buffer) throw new Error('Failed to create p0 buffer')
    gl.bindBuffer(gl.ARRAY_BUFFER, p0Buffer)
    gl.bufferData(gl.ARRAY_BUFFER, this.beamP0Data.byteLength, gl.DYNAMIC_DRAW)
    gl.enableVertexAttribArray(1)
    gl.vertexAttribPointer(1, 2, gl.FLOAT, false, 0, 0)
    gl.vertexAttribDivisor(1, 1)
    this.beamP0Buffer = p0Buffer

    const p1Buffer = gl.createBuffer()
    if (!p1Buffer) throw new Error('Failed to create p1 buffer')
    gl.bindBuffer(gl.ARRAY_BUFFER, p1Buffer)
    gl.bufferData(gl.ARRAY_BUFFER, this.beamP1Data.byteLength, gl.DYNAMIC_DRAW)
    gl.enableVertexAttribArray(2)
    gl.vertexAttribPointer(2, 2, gl.FLOAT, false, 0, 0)
    gl.vertexAttribDivisor(2, 1)
    this.beamP1Buffer = p1Buffer

    gl.bindVertexArray(null)
    return vao
  }

  private cacheUniforms(): void {
    const gl = this.gl
    this.juliaUniforms = {
      uC: gl.getUniformLocation(this.juliaProgram, 'uC'),
      uPan: gl.getUniformLocation(this.juliaProgram, 'uPan'),
      uAspect: gl.getUniformLocation(this.juliaProgram, 'uAspect'),
      uZoom: gl.getUniformLocation(this.juliaProgram, 'uZoom'),
      uAccent: gl.getUniformLocation(this.juliaProgram, 'uAccent'),
      uHueShift: gl.getUniformLocation(this.juliaProgram, 'uHueShift'),
      uPaletteMix: gl.getUniformLocation(this.juliaProgram, 'uPaletteMix'),
      uPaletteFlip: gl.getUniformLocation(this.juliaProgram, 'uPaletteFlip'),
      uFlash: gl.getUniformLocation(this.juliaProgram, 'uFlash'),
      uRefOrbit: gl.getUniformLocation(this.juliaProgram, 'uRefOrbit'),
      uPerturbThreshold: gl.getUniformLocation(this.juliaProgram, 'uPerturbThreshold'),
    }
    this.beamUniforms = {
      uAspect: gl.getUniformLocation(this.beamProgram, 'uAspect'),
      uHalfWidth: gl.getUniformLocation(this.beamProgram, 'uHalfWidth'),
      uColor: gl.getUniformLocation(this.beamProgram, 'uColor'),
      uIntensity: gl.getUniformLocation(this.beamProgram, 'uIntensity'),
    }
  }
}
