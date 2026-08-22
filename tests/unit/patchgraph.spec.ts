import { describe, it, expect } from 'vitest'
import { PatchGraphEvaluator } from '../../src/render/conductor/patchgraph/PatchGraphEvaluator'
import { validatePatchGraph } from '../../src/render/conductor/patchgraph/validate'
import { topoSort, CycleError } from '../../src/render/conductor/patchgraph/topo-sort'
import type { PatchGraph, PatchTargetDecl } from '../../src/render/conductor/patchgraph/types'
import type { SignalBus } from '../../src/render/conductor/types'

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
    idle: false,
    tempoBpm: 120,
    tempoConfidence: 1,
    ...overrides,
  }
}

const LED_TARGET: PatchTargetDecl = {
  id: 'led.strip1.brightness',
  label: 'LED strip 1',
  acceptsTags: ['continuous', 'section', 'bar'],
  defaultValue: 0,
  range: [0, 1],
}
const SERVO_TARGET: PatchTargetDecl = {
  id: 'servo.axis0.angle',
  label: 'Servo axis 0',
  acceptsTags: ['continuous', 'section'],
  defaultValue: 90,
  range: [0, 180],
}

describe('topoSort', () => {
  it('orders inputs before the nodes that read them', () => {
    const graph: PatchGraph = {
      id: 'g',
      nodes: [
        { id: 'a', kind: 'signal', inputs: [], signal: 'energy' },
        { id: 'b', kind: 'curve', inputs: ['a'], curve: 'linear' },
        { id: 't', kind: 'target', inputs: ['b'], targetId: LED_TARGET.id },
      ],
    }
    const order = topoSort(graph)
    expect(order.indexOf('a')).toBeLessThan(order.indexOf('b'))
    expect(order.indexOf('b')).toBeLessThan(order.indexOf('t'))
  })

  it('throws CycleError for a graph with a cycle', () => {
    const graph: PatchGraph = {
      id: 'g',
      nodes: [
        { id: 'a', kind: 'curve', inputs: ['b'], curve: 'linear' },
        { id: 'b', kind: 'curve', inputs: ['a'], curve: 'linear' },
      ],
    }
    expect(() => topoSort(graph)).toThrow(CycleError)
  })
})

describe('validatePatchGraph', () => {
  it('reports no errors for a valid graph', () => {
    const graph: PatchGraph = {
      id: 'g',
      nodes: [
        { id: 'a', kind: 'signal', inputs: [], signal: 'energy' },
        { id: 't', kind: 'target', inputs: ['a'], targetId: LED_TARGET.id },
      ],
    }
    expect(validatePatchGraph(graph, [LED_TARGET])).toEqual([])
  })

  it('flags a dangling input reference', () => {
    const graph: PatchGraph = {
      id: 'g',
      nodes: [{ id: 't', kind: 'target', inputs: ['nonexistent'], targetId: LED_TARGET.id }],
    }
    const issues = validatePatchGraph(graph, [LED_TARGET])
    expect(issues.some((i) => i.severity === 'error' && i.message.includes('unknown node'))).toBe(true)
  })

  it('flags a target node pointing at an unknown fixture channel', () => {
    const graph: PatchGraph = {
      id: 'g',
      nodes: [
        { id: 'a', kind: 'signal', inputs: [], signal: 'energy' },
        { id: 't', kind: 'target', inputs: ['a'], targetId: 'not.a.real.target' },
      ],
    }
    const issues = validatePatchGraph(graph, [LED_TARGET])
    expect(issues.some((i) => i.severity === 'error' && i.message.includes('unknown fixture channel'))).toBe(true)
  })

  it('flags wrong arity (and needs at least 1 input, not 0)', () => {
    const graph: PatchGraph = { id: 'g', nodes: [{ id: 'a', kind: 'logic', op: 'and', inputs: [] }] }
    const issues = validatePatchGraph(graph, [LED_TARGET])
    expect(issues.some((i) => i.severity === 'error' && i.message.includes('expects at least 1'))).toBe(true)
  })

  it('flags wrong arity for "not" (exactly 1 input)', () => {
    const graph: PatchGraph = {
      id: 'g',
      nodes: [
        { id: 'a', kind: 'signal', inputs: [], signal: 'energy' },
        { id: 'b', kind: 'signal', inputs: [], signal: 'tension' },
        { id: 'n', kind: 'logic', op: 'not', inputs: ['a', 'b'] },
      ],
    }
    const issues = validatePatchGraph(graph, [LED_TARGET])
    expect(issues.some((i) => i.nodeId === 'n' && i.message.includes('expects exactly 1'))).toBe(true)
  })

  it('warns (not errors) when a target is fed an unsmoothed transient signal', () => {
    const graph: PatchGraph = {
      id: 'g',
      nodes: [
        { id: 'a', kind: 'signal', inputs: [], signal: 'dropImpulse' },
        { id: 't', kind: 'target', inputs: ['a'], targetId: SERVO_TARGET.id },
      ],
    }
    const issues = validatePatchGraph(graph, [SERVO_TARGET])
    expect(issues).toHaveLength(1)
    expect(issues[0].severity).toBe('warning')
    expect(issues[0].message).toMatch(/transient/)
  })

  it('does not warn when a transient signal is gated through a threshold first', () => {
    const graph: PatchGraph = {
      id: 'g',
      nodes: [
        { id: 'a', kind: 'signal', inputs: [], signal: 'dropImpulse' },
        { id: 'th', kind: 'threshold', inputs: ['a'], cut: 0.5 },
        { id: 't', kind: 'target', inputs: ['th'], targetId: SERVO_TARGET.id },
      ],
    }
    expect(validatePatchGraph(graph, [SERVO_TARGET])).toEqual([])
  })
})

describe('PatchGraphEvaluator', () => {
  it('evaluates a plain signal -> target passthrough', () => {
    const graph: PatchGraph = {
      id: 'g',
      nodes: [
        { id: 'a', kind: 'signal', inputs: [], signal: 'energy' },
        { id: 't', kind: 'target', inputs: ['a'], targetId: LED_TARGET.id },
      ],
    }
    const evalr = new PatchGraphEvaluator(graph, [LED_TARGET])
    const result = evalr.evaluate(makeBus({ energy: 0.7 }), 1 / 60)
    expect(result[LED_TARGET.id]).toBeCloseTo(0.7)
  })

  it('constructor throws on a graph with error-severity issues', () => {
    const graph: PatchGraph = { id: 'g', nodes: [{ id: 't', kind: 'target', inputs: ['missing'], targetId: LED_TARGET.id }] }
    expect(() => new PatchGraphEvaluator(graph, [LED_TARGET])).toThrow(/error/)
  })

  it('logic AND is the min of its inputs, OR is the max, NOT is 1-x', () => {
    const graph: PatchGraph = {
      id: 'g',
      nodes: [
        { id: 'a', kind: 'signal', inputs: [], signal: 'energy' },
        { id: 'b', kind: 'signal', inputs: [], signal: 'tension' },
        { id: 'and', kind: 'logic', op: 'and', inputs: ['a', 'b'] },
        { id: 'or', kind: 'logic', op: 'or', inputs: ['a', 'b'] },
        { id: 'not', kind: 'logic', op: 'not', inputs: ['a'] },
        { id: 't1', kind: 'target', inputs: ['and'], targetId: LED_TARGET.id },
        { id: 't2', kind: 'target', inputs: ['or'], targetId: SERVO_TARGET.id },
      ],
    }
    const evalr = new PatchGraphEvaluator(graph, [LED_TARGET, SERVO_TARGET])
    const result = evalr.evaluate(makeBus({ energy: 0.3, tension: 0.8 }), 1 / 60)
    expect(result[LED_TARGET.id]).toBeCloseTo(0.3) // and = min
    expect(result[SERVO_TARGET.id]).toBeCloseTo(0.8) // or = max
  })

  it('combine add/multiply/max/min match arithmetic', () => {
    const mk = (op: 'add' | 'multiply' | 'max' | 'min'): PatchGraph => ({
      id: 'g',
      nodes: [
        { id: 'a', kind: 'const', inputs: [], value: 0.2 },
        { id: 'b', kind: 'const', inputs: [], value: 0.5 },
        { id: 'c', kind: 'combine', op, inputs: ['a', 'b'] },
        { id: 't', kind: 'target', inputs: ['c'], targetId: LED_TARGET.id },
      ],
    })
    expect(new PatchGraphEvaluator(mk('add'), [LED_TARGET]).evaluate(makeBus(), 1 / 60)[LED_TARGET.id]).toBeCloseTo(0.7)
    expect(new PatchGraphEvaluator(mk('multiply'), [LED_TARGET]).evaluate(makeBus(), 1 / 60)[LED_TARGET.id]).toBeCloseTo(0.1)
    expect(new PatchGraphEvaluator(mk('max'), [LED_TARGET]).evaluate(makeBus(), 1 / 60)[LED_TARGET.id]).toBeCloseTo(0.5)
    expect(new PatchGraphEvaluator(mk('min'), [LED_TARGET]).evaluate(makeBus(), 1 / 60)[LED_TARGET.id]).toBeCloseTo(0.2)
  })

  it('map remaps a 0..1 signal into an arbitrary output range, inversion included', () => {
    const graph: PatchGraph = {
      id: 'g',
      nodes: [
        { id: 'a', kind: 'signal', inputs: [], signal: 'energy' },
        { id: 'm', kind: 'map', inputs: ['a'], inRange: [0, 1], outRange: [180, 0], clamp: true },
        { id: 't', kind: 'target', inputs: ['m'], targetId: SERVO_TARGET.id },
      ],
    }
    const evalr = new PatchGraphEvaluator(graph, [SERVO_TARGET])
    expect(evalr.evaluate(makeBus({ energy: 0 }), 1 / 60)[SERVO_TARGET.id]).toBeCloseTo(180)
    expect(evalr.evaluate(makeBus({ energy: 1 }), 1 / 60)[SERVO_TARGET.id]).toBeCloseTo(0)
  })

  it('threshold gates 0/1 at the cut point and holds state across frames', () => {
    const graph: PatchGraph = {
      id: 'g',
      nodes: [
        { id: 'a', kind: 'signal', inputs: [], signal: 'energy' },
        { id: 'th', kind: 'threshold', inputs: ['a'], cut: 0.5 },
        { id: 't', kind: 'target', inputs: ['th'], targetId: LED_TARGET.id },
      ],
    }
    const evalr = new PatchGraphEvaluator(graph, [LED_TARGET])
    expect(evalr.evaluate(makeBus({ energy: 0.3 }), 1 / 60)[LED_TARGET.id]).toBe(0)
    expect(evalr.evaluate(makeBus({ energy: 0.6 }), 1 / 60)[LED_TARGET.id]).toBe(1)
    expect(evalr.evaluate(makeBus({ energy: 0.51 }), 1 / 60)[LED_TARGET.id]).toBe(1)
  })

  it('threshold hysteresis prevents chattering right at the cut', () => {
    const graph: PatchGraph = {
      id: 'g',
      nodes: [
        { id: 'a', kind: 'signal', inputs: [], signal: 'energy' },
        { id: 'th', kind: 'threshold', inputs: ['a'], cut: 0.5, hysteresis: 0.1 },
        { id: 't', kind: 'target', inputs: ['th'], targetId: LED_TARGET.id },
      ],
    }
    const evalr = new PatchGraphEvaluator(graph, [LED_TARGET])
    // Rises above cut -> active.
    expect(evalr.evaluate(makeBus({ energy: 0.55 }), 1 / 60)[LED_TARGET.id]).toBe(1)
    // Dips just below cut, but still above (cut - hysteresis) = 0.4 -> stays active.
    expect(evalr.evaluate(makeBus({ energy: 0.45 }), 1 / 60)[LED_TARGET.id]).toBe(1)
    // Drops below the release point -> deactivates.
    expect(evalr.evaluate(makeBus({ energy: 0.35 }), 1 / 60)[LED_TARGET.id]).toBe(0)
  })

  it('envelope moves toward its target using attack/release time constants', () => {
    const graph: PatchGraph = {
      id: 'g',
      nodes: [
        { id: 'a', kind: 'signal', inputs: [], signal: 'energy' },
        { id: 'e', kind: 'envelope', inputs: ['a'], attackSec: 0.1, releaseSec: 1 },
        { id: 't', kind: 'target', inputs: ['e'], targetId: LED_TARGET.id },
      ],
    }
    const evalr = new PatchGraphEvaluator(graph, [LED_TARGET])
    const afterAttack = evalr.evaluate(makeBus({ energy: 1 }), 0.1)[LED_TARGET.id]
    // A fast attack (0.1s time constant) should move meaningfully toward 1 in one 0.1s step.
    expect(afterAttack).toBeGreaterThan(0.5)
    const afterRelease = evalr.evaluate(makeBus({ energy: 0 }), 0.1)[LED_TARGET.id]
    // A slow release (1s time constant) should barely move in one 0.1s step.
    expect(afterRelease).toBeGreaterThan(afterAttack - 0.15)
    expect(afterRelease).toBeLessThan(afterAttack)
  })

  it('a target with no route to it is simply absent from the result', () => {
    const graph: PatchGraph = {
      id: 'g',
      nodes: [
        { id: 'a', kind: 'signal', inputs: [], signal: 'energy' },
        { id: 't', kind: 'target', inputs: ['a'], targetId: LED_TARGET.id },
      ],
    }
    const evalr = new PatchGraphEvaluator(graph, [LED_TARGET, SERVO_TARGET])
    const result = evalr.evaluate(makeBus(), 1 / 60)
    expect(SERVO_TARGET.id in result).toBe(false)
  })
})
