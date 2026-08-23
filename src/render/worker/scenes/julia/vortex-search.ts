// The Julia scene's "where's the interesting structure" heuristic, pulled
// out of JuliaScene.ts into its own module specifically so it's testable in
// isolation — before this, these functions had ZERO test coverage across
// several sessions of hand-tuning constants against live visual feedback,
// which is exactly why a real bug here (see IMPROVED_VORTEX_SEARCH_ITER_CAP
// below) went unnoticed for so long: nothing could ever verify a hypothesis
// about this code except "look at it running and guess."

export interface Vec2 {
  x: number
  y: number
}

// Escape iteration count (the same integer XaoS calls a pixel's "color")
// plus total winding |Δarg(z)| along the same orbit — spiraling near a
// neutral/near-periodic point before escaping, which is what the "vortex"
// structures actually are. Both come from one orbit walk, so tracking
// winding here is free.
export interface OrbitSample {
  iter: number // 0..cap; cap itself is its own bucket ("never escaped")
  winding: number
}

export function sampleOrbit(zx0: number, zy0: number, cx: number, cy: number, cap: number): OrbitSample {
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
export const DIVERSITY_SAMPLES = 6
export const DIVERSITY_CLUSTER_FRACTION = 0.15 // cluster spread, relative to the candidate's own probe radius

// NAV_VORTEX_WINDING_SCALE (radians) is where the bonus is about
// half-saturated — roughly half a turn, from sampling real orbits.
// NAV_VORTEX_BOOST caps how much a maximally-spiraling point can outweigh
// an equally-diverse but non-spiraling one.
export const NAV_VORTEX_WINDING_SCALE = 4
export const NAV_VORTEX_BOOST = 2.5

export function clusterScore(px: number, py: number, clusterRadius: number, cx: number, cy: number, cap: number): number {
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
export const VORTEX_SEARCH_RINGS = 6
export const VORTEX_SEARCH_PER_RING = 16
// Was 90. `c` on this scene always sits on (or within a hair's-width radial
// wobble of) the Mandelbrot main cardioid's boundary (see boundary.ts) —
// EVERY such c has a parabolic (neutral, multiplier-1-ish) fixed point by
// construction, which is precisely what makes the dynamics rich enough to
// bother sweeping over in the first place. But parabolic dynamics converge
// POLYNOMIALLY (~1/sqrt(n)), not the usual geometric/exponential rate real
// (hyperbolic) Julia sets escape at — orbits near the actual boundary
// structure can need several hundred iterations just to separate from each
// other at all. At cap=90, a whole cluster of samples genuinely NEAR the
// most interesting structure could all still read as "never escaped"
// (iter===cap for every sample) — indistinguishable from a boring, deep
// interior region under clusterScore's diversity test, and get rejected as
// diversity<=1 exactly where real detail was. This is a plausible root
// cause for "the navigation misses the interesting spirals/flowers every
// iteration" reported after many sessions of retuning the scoring formula
// itself without success — the formula was never the whole problem if the
// measurements feeding it were this systematically blind at the
// boundary-adjacent points that matter most. Raised well past where a
// cauliflower-point synthetic test (see vortex-search.spec.ts) actually
// needs to correctly separate a near-boundary point from a deep-interior
// one. This only runs once per dive (see comment above) and once per local
// re-search (LOCAL_RETARGET_RADIUS_FACTOR in JuliaScene.ts), so the extra
// cost is a one-shot, not a per-frame one.
export const VORTEX_SEARCH_ITER_CAP = 400

// `centerX/Y` lets the same search run either globally from the origin (a
// fresh dive) or locally around the current pan (a nearby re-search when
// the dive's original target has run dry — see LOCAL_RETARGET_RADIUS_FACTOR
// in JuliaScene.ts). `found` is false when every candidate scored 0 — the
// caller's signal to escalate rather than aim at the meaningless
// (centerX, centerY) fallback.
export function findVortexTarget(cx: number, cy: number, maxRadius: number, centerX = 0, centerY = 0): { x: number; y: number; found: boolean } {
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
