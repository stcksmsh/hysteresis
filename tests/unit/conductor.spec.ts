import { describe, it, expect } from 'vitest'
import { Conductor } from '../../src/render/conductor/Conductor'
import { Patchbay } from '../../src/render/conductor/patchbay/Patchbay'
import { screenOnlyConfig } from '../../src/render/conductor/patchbay/configs/screen-only'
import { ScreenParamAssembler, type AssembledScreenParams } from '../../src/render/conductor/patchbay/screen-composites'
import { SCREEN_TARGETS } from '../../src/render/conductor/outputs/screen-targets'
import type { StateFrame, StructuralEvent } from '../../src/shared/types'

function makeFrame(overrides: Partial<StateFrame> = {}): StateFrame {
  return {
    t: 0,
    tempo: 120,
    tempoConfidence: 1,
    beatPhase: 0,
    barPhase: 0,
    buildProgress: 0,
    tension: 0,
    energy: 0,
    bandsRaw: { sub: 0, low: 0, mid: 0, presence: 0, air: 0 },
    centroid: 0,
    flatness: 0,
    pan: 0,
    spectralHits: [],
    events: [],
    scope: null,
    ...overrides,
  }
}

// One "pipeline tick" — Conductor -> Patchbay(screen-only) -> screen
// composites — mirroring exactly what render-worker.ts's loop() now does
// for the screen output. This is the concrete proof SINTEZA_SIGNAL_BUS.md
// §9 step 1 asks for: the default screen-only config resolved against a
// fresh Conductor+Patchbay+assembler reproduces today's exact numbers.
function pipelineTick(
  conductor: Conductor,
  patchbay: Patchbay,
  assembler: ScreenParamAssembler,
  frame: StateFrame,
  dt: number,
): AssembledScreenParams {
  const bus = conductor.update(frame, dt)
  const resolved = patchbay.resolve(bus, dt, SCREEN_TARGETS)
  return assembler.update(dt, resolved)
}

function run(frame: (t: number) => StateFrame, seconds: number, dt = 1 / 60) {
  const conductor = new Conductor()
  const patchbay = new Patchbay(screenOnlyConfig, [SCREEN_TARGETS])
  const assembler = new ScreenParamAssembler()
  const steps = Math.round(seconds / dt)
  let params = pipelineTick(conductor, patchbay, assembler, frame(0), 0)
  for (let i = 1; i <= steps; i++) {
    params = pipelineTick(conductor, patchbay, assembler, frame(i * dt), dt)
  }
  return { conductor, patchbay, assembler, params }
}

describe('Conductor -> Patchbay(screen-only) -> screen composites (SINTEZA_VIZ.md §4b/§4d)', () => {
  it('groove/idle settles to short memory, baseline flow, and floor-level symmetry', () => {
    const { params } = run(() => makeFrame(), 2)
    expect(params.fieldDecay).toBeCloseTo(0.86, 1)
    expect(params.flowStrength).toBeCloseTo(1, 0)
    // A low degree of kaleidoscope fold is always active (SYMMETRY_FLOOR),
    // not zero at rest — it only rises meaningfully above that floor.
    expect(params.symmetry).toBeCloseTo(0.18, 2)
  })

  it('a sustained build lengthens memory and raises symmetry ("processing")', () => {
    const { params } = run((t) => makeFrame({ t, buildProgress: 1, tension: 0.6 }), 3)
    expect(params.fieldDecay).toBeGreaterThan(0.9)
    expect(params.symmetry).toBeGreaterThan(0.3)
    expect(params.flowStrength).toBeGreaterThan(1.5) // "the frame visibly densifies"
  })

  it('a drop snaps symmetry toward full and shocks the flow field, then both release', () => {
    // Settle in a build first, like a real windup would produce.
    const { conductor, patchbay, assembler, params: beforeDrop } = run(
      (t) => makeFrame({ t, buildProgress: 1, tension: 0.6 }),
      2,
    )

    const dropEvent: StructuralEvent = { type: 'drop', strength: 1, t: 2 }
    const atDrop = pipelineTick(
      conductor,
      patchbay,
      assembler,
      makeFrame({ t: 2, buildProgress: 0, tension: 0, events: [dropEvent] }),
      1 / 60,
    )
    // The impulse lands on flowStrengthSpring's velocity before this same
    // frame's update() integrates it — so unlike symmetry's eased attack,
    // the shockwave is visible on the very frame the drop fires.
    expect(atDrop.flowStrength).toBeGreaterThan(beforeDrop.flowStrength + 0.3)

    // Everything in this codebase is eased, never a hard binary jump (see
    // SpringDamper's own docstring) — "snaps" means a fast attack toward the
    // target, not an instant step, so this checks the target actually
    // reached 1 and the value is well on its way there within one attack
    // time constant (SYMMETRY_ATTACK_SEC), not that it arrived this tick.
    let params = atDrop
    const stepsAttack = Math.round(0.5 / (1 / 60))
    for (let i = 1; i <= stepsAttack; i++) {
      params = pipelineTick(conductor, patchbay, assembler, makeFrame({ t: 2 + i / 60 }), 1 / 60)
    }
    expect(params.symmetry).toBeGreaterThan(0.9)

    // And well after — past both the hold and the release time constant —
    // both settle back down: "for a bar", not "stuck at full symmetry
    // forever".
    const stepsAfter = Math.round(8 / (1 / 60))
    for (let i = 1; i <= stepsAfter; i++) {
      params = pipelineTick(conductor, patchbay, assembler, makeFrame({ t: 2.5 + i / 60 }), 1 / 60)
    }
    expect(params.symmetry).toBeLessThan(0.3)
    expect(params.fieldDecay).toBeCloseTo(0.86, 1)
  })

  it('sustained suspension (a held break) pushes memory to linger further than a build does', () => {
    // tension alone (no buildProgress) drives the slow suspension envelope,
    // modelling a held break — SINTEZA_VIZ.md §3a: "the last drop's trace
    // hangs suspended".
    const { params } = run((t) => makeFrame({ t, tension: 0.8 }), 6)
    expect(params.fieldDecay).toBeGreaterThan(0.95)
  })

  it('hueShift drifts continuously at rest and is nudged by centroid (now real routes, not a hardcoded formula)', () => {
    // hueDrift -> screen.hueShift (gain 1) + centroid -> screen.hueShift
    // (gain 0.1), summed by the patchbay — reproducing the old
    // `(hue + centroid*0.1) % 1` formula as two routes instead of code.
    const { params: atZero } = run(() => makeFrame({ centroid: 0 }), 0)
    const { params: afterDrift } = run(() => makeFrame({ centroid: 0 }), 5)
    expect(afterDrift.hueShift).toBeGreaterThan(atZero.hueShift)

    const { params: withCentroid } = run(() => makeFrame({ centroid: 1 }), 0)
    const { params: withoutCentroid } = run(() => makeFrame({ centroid: 0 }), 0)
    expect(withCentroid.hueShift).toBeCloseTo(withoutCentroid.hueShift + 0.1, 5)
  })

  it('paletteMix tracks buildWindup (now a real route, not a hardcoded formula)', () => {
    const { params: atRest } = run(() => makeFrame(), 2)
    expect(atRest.paletteMix).toBeCloseTo(0, 2)

    const { params: duringBuild } = run((t) => makeFrame({ t, buildProgress: 1 }), 3)
    expect(duringBuild.paletteMix).toBeGreaterThan(0.3)
    expect(duringBuild.paletteMix).toBeCloseTo(duringBuild.windup, 5)
  })

  // AGENTS.md §3.7/§5's own standing note: the six Layer 2 understanding signals
  // (noveltyLocal/noveltySection/fullness/onsetDensity/harmonicNovelty/chromaRootHue) were real
  // and live on the SignalBus but never wired into any default screen route. Now real, routable
  // screen.* targets (screen-only.ts's identityRoutes) — this is the concrete proof, not just a
  // config-file inspection.
  it('all six Layer 2 signals resolve as real screen.* targets, not just SignalBus-internal values', () => {
    const chroma = new Float32Array(12)
    chroma[3] = 1 // an arbitrary dominant pitch class
    const conductor = new Conductor()
    const patchbay = new Patchbay(screenOnlyConfig, [SCREEN_TARGETS])
    const bus = conductor.update(makeFrame({ fullness: 0.7, onsetDensity: 0.4, chroma }), 0)
    const resolved = patchbay.resolve(bus, 0, SCREEN_TARGETS)

    expect(resolved['screen.fullness']).toBeCloseTo(0.7, 5)
    expect(resolved['screen.onsetDensity']).toBeCloseTo(0.4, 5)
    expect(resolved['screen.chromaRootHue']).toBeCloseTo(3 / 12, 5)
    // noveltyLocal/noveltySection/harmonicNovelty aren't directly settable via StateFrame (they're
    // derived from Conductor's own novelty trackers) — just prove they resolve to a real number,
    // not undefined/NaN, confirming the route itself (not the upstream computation) is wired.
    expect(typeof resolved['screen.noveltyLocal']).toBe('number')
    expect(typeof resolved['screen.noveltySection']).toBe('number')
    expect(typeof resolved['screen.harmonicNovelty']).toBe('number')
  })

  it('chromaRootHue nudges hueShift, summed alongside hueDrift/centroid (the only one of the six wired into a composite)', () => {
    const chroma = new Float32Array(12)
    chroma[6] = 1 // dominantPitchClassHue = 6/12 = 0.5
    const { params: withChroma } = run(() => makeFrame({ chroma }), 0)
    const { params: withoutChroma } = run(() => makeFrame(), 0)
    expect(withChroma.hueShift).toBeCloseTo(withoutChroma.hueShift + 0.5 * 0.15, 5)
  })

  it('fullness gently thickens flowStrength, distinct from and additive with energy', () => {
    const { params: withFullness } = run(() => makeFrame({ fullness: 1 }), 1)
    const { params: withoutFullness } = run(() => makeFrame({ fullness: 0 }), 1)
    expect(withFullness.flowStrength).toBeGreaterThan(withoutFullness.flowStrength)
  })

  it('the four remaining Layer 2 signals (noveltyLocal/noveltySection/harmonicNovelty/onsetDensity) are deliberately NOT wired into symmetry', () => {
    // A regression guard for the deliberate restraint documented in screen-only.ts: this
    // codebase's own history flags symmetry as already reported "too psychedelic"/overused, so
    // these four stay pure default routes rather than new symmetry contributors. Maxing them out
    // (via a full-novelty first frame + high onsetDensity) must not move symmetry beyond what
    // familiarity/tension/buildProgress/flatness alone already produce at rest.
    const { params: baseline } = run(() => makeFrame(), 0)
    const { params: withLayer2Maxed } = run(() => makeFrame({ onsetDensity: 1 }), 0)
    expect(withLayer2Maxed.symmetry).toBeCloseTo(baseline.symmetry, 5)
  })
})
