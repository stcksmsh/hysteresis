import { describe, it, expect } from 'vitest'
import { Patchbay } from '../../src/render/conductor/patchbay/Patchbay'
import { screenOnlyConfig } from '../../src/render/conductor/patchbay/configs/screen-only'
import { SCREEN_TARGETS } from '../../src/render/conductor/outputs/screen-targets'
import { migrateRouteConfigToGraph } from '../../src/render/conductor/patchgraph/migrate-route-config'
import { PatchGraphEvaluator } from '../../src/render/conductor/patchgraph/PatchGraphEvaluator'
import type { PatchbayConfig, Route } from '../../src/render/conductor/patchbay/types'
import type { SignalBus, TargetDecl } from '../../src/render/conductor/types'

function makeBus(overrides: Partial<SignalBus> = {}): SignalBus {
  return {
    energy: 0,
    sub: 0,
    low: 0,
    mid: 0,
    presence: 0,
    air: 0,
    bandTilt: 0,
    centroid: 0,
    flatness: 0,
    pan: 0,
    familiarity: 0,
    noveltyLocal: 0,
    noveltySection: 0,
    fullness: 0,
    onsetDensity: 0,
    harmonicNovelty: 0,
    chromaRootHue: 0,
    vocalPresence: 0,
    drumsPresence: 0,
    bassPresence: 0,
    otherPresence: 0,
    leadPresence: 0,
    hueDrift: 0,
    beatPhase: 0,
    beatPulse: 0,
    barPhase: 0,
    downbeatPulse: 0,
    buildWindup: 0,
    buildProgress: 0,
    tension: 0,
    suspension: 0,
    dropImpulse: 0,
    onsetImpulse: 0,
    dropTrigger: null,
    scope: null,
    chroma: null,
    idle: false,
    tempoBpm: 120,
    tempoConfidence: 1,
    ...overrides,
  }
}

// Deterministic pseudo-random bus states — no need for true randomness, just
// wide coverage of the signal space (including negative/bipolar fields and
// values outside 0..1) across many frames, with a fixed seed so a failure is
// reproducible.
function mulberry32(seed: number): () => number {
  let a = seed
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function randomBus(rand: () => number): SignalBus {
  const u = () => rand() // 0..1
  const bp = () => rand() * 2 - 1 // -1..1
  return makeBus({
    energy: u(),
    sub: u(),
    low: u(),
    mid: u(),
    presence: u(),
    air: u(),
    bandTilt: bp(),
    centroid: u(),
    flatness: u(),
    pan: bp(),
    familiarity: u(),
    hueDrift: u(),
    beatPhase: u(),
    beatPulse: u(),
    barPhase: u(),
    buildWindup: rand() * 5 - 1, // this target's range is [-2,3], exercise beyond 0..1
    buildProgress: u(),
    tension: u(),
    suspension: u(),
    dropImpulse: u(),
    tempoBpm: rand() * 300,
    tempoConfidence: u(),
    idle: rand() > 0.5,
  })
}

function checkParity(config: PatchbayConfig, targets: TargetDecl[]) {
  const patchbay = new Patchbay(config, [targets])
  const migrated = migrateRouteConfigToGraph(config, targets)
  const evaluator = new PatchGraphEvaluator(migrated.graph, targets)

  const rand = mulberry32(20260823)
  const nonPassThroughTargets = targets.filter((t) => !t.passThrough)

  for (let frame = 0; frame < 200; frame++) {
    const bus = randomBus(rand)
    const dt = 1 / 60 + rand() * (1 / 20) // vary dt too — a smoothing/envelope route is dt-sensitive
    const fromPatchbay = patchbay.resolve(bus, dt, targets)
    const fromGraph = evaluator.evaluate(bus, dt)

    for (const target of nonPassThroughTargets) {
      const expected = fromPatchbay[target.id] as number
      // A target with no route in the graph simply doesn't appear in
      // evaluate()'s output (see PatchGraphEvaluator's own doc comment) —
      // the migrated screen-only config routes every non-passThrough
      // target, so this only fires if that ever regresses.
      const actual = target.id in fromGraph ? fromGraph[target.id] : target.defaultValue
      expect(actual, `frame ${frame}, target "${target.id}"`).toBeCloseTo(expected, 5)
    }
  }
}

describe('migrateRouteConfigToGraph — equivalence with Patchbay', () => {
  it('reproduces screen-only.ts exactly across many random bus states/dt values', () => {
    checkParity(screenOnlyConfig, SCREEN_TARGETS)
  })

  it('handles gain + offset (affine, non-1/0)', () => {
    const targets: TargetDecl[] = [{ id: 'out.a', acceptsTags: ['continuous'], defaultValue: 0, range: [-10, 10] }]
    const config: PatchbayConfig = { id: 'test', routes: [{ from: 'energy', to: 'out.a', curve: 'linear', gain: 3, offset: -1 }] }
    checkParity(config, targets)
  })

  it('handles invert against the target range', () => {
    const targets: TargetDecl[] = [{ id: 'out.a', acceptsTags: ['continuous'], defaultValue: 0, range: [0, 1] }]
    const config: PatchbayConfig = { id: 'test', routes: [{ from: 'energy', to: 'out.a', curve: 'linear', invert: true }] }
    checkParity(config, targets)
  })

  it('handles invert combined with gain/offset', () => {
    const targets: TargetDecl[] = [{ id: 'out.a', acceptsTags: ['continuous'], defaultValue: 0, range: [-5, 5] }]
    const config: PatchbayConfig = {
      id: 'test',
      routes: [{ from: 'centroid', to: 'out.a', curve: 'linear', gain: 2, offset: 0.5, invert: true }],
    }
    checkParity(config, targets)
  })

  it('handles a non-linear curve', () => {
    const targets: TargetDecl[] = [{ id: 'out.a', acceptsTags: ['continuous'], defaultValue: 0, range: [-1, 1] }]
    const config: PatchbayConfig = { id: 'test', routes: [{ from: 'bandTilt', to: 'out.a', curve: 'smoothstep' }] }
    checkParity(config, targets)
  })

  it('handles multiple routes summing into the same target', () => {
    const targets: TargetDecl[] = [{ id: 'out.a', acceptsTags: ['continuous'], defaultValue: 0, range: [0, 2] }]
    const config: PatchbayConfig = {
      id: 'test',
      routes: [
        { from: 'energy', to: 'out.a', curve: 'linear', gain: 0.5 },
        { from: 'centroid', to: 'out.a', curve: 'linear', gain: 0.5 },
      ],
    }
    checkParity(config, targets)
  })

  it('separates out passThrough routes rather than turning them into graph nodes', () => {
    const targets: TargetDecl[] = [
      { id: 'out.idle', acceptsTags: [], defaultValue: 0, range: [0, 1], passThrough: true },
      { id: 'out.a', acceptsTags: ['continuous'], defaultValue: 0, range: [0, 1] },
    ]
    const passThroughRoute: Route = { from: 'idle', to: 'out.idle', passThrough: true }
    const config: PatchbayConfig = { id: 'test', routes: [passThroughRoute, { from: 'energy', to: 'out.a' }] }
    const { graph, passThroughRoutes } = migrateRouteConfigToGraph(config, targets)
    expect(passThroughRoutes).toEqual([passThroughRoute])
    expect(graph.nodes.some((n) => n.kind === 'target' && n.targetId === 'out.idle')).toBe(false)
    expect(graph.nodes.some((n) => n.kind === 'target' && n.targetId === 'out.a')).toBe(true)
  })

  it('throws on an unknown bus signal rather than silently producing NaN', () => {
    const targets: TargetDecl[] = [{ id: 'out.a', acceptsTags: ['continuous'], defaultValue: 0, range: [0, 1] }]
    const config: PatchbayConfig = { id: 'test', routes: [{ from: 'totallyMadeUp', to: 'out.a' }] }
    expect(() => migrateRouteConfigToGraph(config, targets)).toThrow(/not a known bus signal/)
  })
})
