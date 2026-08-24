import { describe, it, expect } from 'vitest'
import { seedNodes } from '../../tools/patchbay-editor/src/seed-graph'
import { toPatchGraph } from '../../tools/patchbay-editor/src/graph-draft'
import { addFixture, emptyFixtureDocument, fixtureTargetCatalog } from '../../src/render/conductor/patchgraph/fixture-document'
import { validatePatchGraph } from '../../src/render/conductor/patchgraph/validate'
import { PatchGraphEvaluator } from '../../src/render/conductor/patchgraph/PatchGraphEvaluator'
import type { SignalBus } from '../../src/render/conductor/types'

function makeBus(overrides: Partial<SignalBus> = {}): SignalBus {
  return {
    energy: 0.6,
    sub: 0,
    low: 0.4,
    mid: 0.5,
    presence: 0.3,
    air: 0.2,
    bandTilt: 0,
    centroid: 0.7,
    flatness: 0,
    pan: 0.5,
    familiarity: 0.8,
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
    tempoBpm: 120,
    tempoConfidence: 0.5,
    idle: false,
    scope: new Float32Array(0),
    chroma: null,
    ...overrides,
  }
}

// Regression coverage for exactly the gap a real user caught in the editor:
// the demo fixture seed only wired the FIRST fixture's channel, leaving the
// other demo fixtures' widgets frozen at their default value with nothing
// driving them at all. seedNodes() now wires every target it's given, and
// this asserts that end to end — every channel resolves to a live value,
// and the graph is warning-free (a demo shipped with its own servo-safety
// warning would be a bad example to start editing from).
describe('seedNodes (patchbay editor demo wiring)', () => {
  it('wires every fixture channel across all fixture types, with no validation issues', () => {
    let doc = emptyFixtureDocument()
    doc = addFixture(doc, 'Demo Dimmer', 'dimmer')
    doc = addFixture(doc, 'Demo RGB', 'rgb')
    doc = addFixture(doc, 'Demo Servo', 'servo')
    doc = addFixture(doc, 'Demo Laser', 'mover')
    const targets = fixtureTargetCatalog(doc)
    // dimmer(1) + rgb(3) + servo(1) + mover(3) channels
    expect(targets.length).toBe(8)

    const nodes = seedNodes(targets)
    const graph = toPatchGraph('seed-test', nodes)

    const issues = validatePatchGraph(graph, targets)
    expect(issues).toEqual([])

    const evaluator = new PatchGraphEvaluator(graph, targets)
    const resolved = evaluator.evaluate(makeBus(), 1 / 20)

    for (const target of targets) {
      expect(resolved[target.id]).toBeDefined()
      expect(Number.isFinite(resolved[target.id])).toBe(true)
    }
  })

  it('range-maps non-[0,1] targets (e.g. servo angle) instead of leaving them stuck near 0-1', () => {
    let doc = emptyFixtureDocument()
    doc = addFixture(doc, 'Demo Servo', 'servo')
    const targets = fixtureTargetCatalog(doc)
    const nodes = seedNodes(targets)
    const graph = toPatchGraph('seed-test-servo', nodes)
    const evaluator = new PatchGraphEvaluator(graph, targets)

    // servo's demo chain starts at DEMO_SIGNALS[0] = 'energy' since it's the
    // only (first) target here, using the threshold-gated chain — feed a
    // high energy so the threshold is active and check the mapped value
    // actually reaches into the servo's real [0, 180] range, not just [0, 1].
    const resolved = evaluator.evaluate(makeBus({ energy: 0.9 }), 1 / 20)
    const servoTarget = targets[0]
    expect(servoTarget.range).toEqual([0, 180])
    expect(resolved[servoTarget.id]).toBeGreaterThan(1)
  })
})
