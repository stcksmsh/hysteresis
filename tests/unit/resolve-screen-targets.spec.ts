import { describe, it, expect } from 'vitest'
import { screenGraph } from '../../src/render/conductor/patchgraph/configs/screen-graph'
import { SCREEN_TARGETS } from '../../src/render/conductor/outputs/screen-targets'
import { PatchGraphEvaluator } from '../../src/render/conductor/patchgraph/PatchGraphEvaluator'
import { resolveScreenTargets } from '../../src/render/conductor/outputs/resolve-screen-targets'
import type { SignalBus } from '../../src/render/conductor/types'

function makeBus(overrides: Partial<SignalBus> = {}): SignalBus {
  return {
    energy: 0.5,
    sub: 0,
    low: 0,
    mid: 0,
    presence: 0,
    air: 0,
    bandTilt: 0,
    centroid: 0.3,
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
    hueDrift: 0.2,
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
    idle: true,
    tempoBpm: 120,
    tempoConfidence: 1,
    ...overrides,
  }
}

describe('screenGraph (the migrated default) + resolveScreenTargets', () => {
  it('constructs without throwing (validates clean against SCREEN_TARGETS)', () => {
    expect(() => new PatchGraphEvaluator(screenGraph, SCREEN_TARGETS)).not.toThrow()
  })

  it('routes every non-passThrough SCREEN_TARGETS id (the default config covers all of them)', () => {
    const evaluator = new PatchGraphEvaluator(screenGraph, SCREEN_TARGETS)
    const resolved = resolveScreenTargets(evaluator, SCREEN_TARGETS, makeBus(), 1 / 60)
    for (const target of SCREEN_TARGETS) {
      expect(resolved[target.id], target.id).not.toBeUndefined()
    }
  })

  it('copies idle/scope straight from the bus (passThrough — never graph-evaluated)', () => {
    const evaluator = new PatchGraphEvaluator(screenGraph, SCREEN_TARGETS)
    const scope = new Float32Array([1, 2, 3])
    const resolved = resolveScreenTargets(evaluator, SCREEN_TARGETS, makeBus({ idle: false, scope }), 1 / 60)
    expect(resolved['screen.idle']).toBe(false)
    expect(resolved['screen.scope']).toBe(scope)
  })

  it('falls back to a target’s own defaultValue, not 0, when nothing routes to it', () => {
    // tempoBpm's route always exists in the real default config, so this
    // exercises the fallback path directly against a minimal graph instead.
    const targets = SCREEN_TARGETS
    const evaluator = new PatchGraphEvaluator({ id: 'empty', nodes: [] }, targets)
    const resolved = resolveScreenTargets(evaluator, targets, makeBus(), 1 / 60)
    const tempoTarget = targets.find((t) => t.id === 'screen.tempoBpm')!
    expect(resolved['screen.tempoBpm']).toBe(tempoTarget.defaultValue)
    expect(tempoTarget.defaultValue).not.toBe(0) // otherwise this test can't distinguish from the old "silently 0" bug
  })
})
