import type { SignalBus } from '../types'
import type { PatchGraph, PatchTargetDecl } from './types'
import { validatePatchGraph } from './validate'
import { topoSort } from './topo-sort'
import { evaluateNode, type EnvelopeState, type ThresholdState } from './evaluate-node'

// Runs one PatchGraph against a live SignalBus every frame, producing a
// value per `target` node. Construction validates (throws on any `error`-
// severity issue — warnings don't block, per validate.ts's reasoning) and
// precomputes the topological order once, so per-frame evaluate() is a
// single linear pass with no graph-structure work repeated.
export class PatchGraphEvaluator {
  private order: string[]
  private thresholdState = new Map<string, ThresholdState>()
  private envelopeState = new Map<string, EnvelopeState>()
  private byId: Map<string, PatchGraph['nodes'][number]>

  constructor(
    private graph: PatchGraph,
    targets: PatchTargetDecl[],
  ) {
    const issues = validatePatchGraph(graph, targets).filter((i) => i.severity === 'error')
    if (issues.length > 0) {
      throw new Error(`patch graph "${graph.id}" has ${issues.length} error(s): ${issues.map((i) => `[${i.nodeId}] ${i.message}`).join('; ')}`)
    }
    this.order = topoSort(graph)
    this.byId = new Map(graph.nodes.map((n) => [n.id, n]))
  }

  // Returns { [targetId]: resolvedValue } for every `target` node in the
  // graph. A target with NO route to it simply never appears here — unlike
  // the screen Patchbay (which fills every declared target with a default
  // every frame, §5.1), this graph only exists to describe explicit wiring,
  // so callers (a fixture renderer, a future real output) decide what an
  // absent target means for their own device (hold last value, go dark,
  // whatever's safe for that hardware).
  evaluate(bus: SignalBus, dt: number): Record<string, number> {
    const values = new Map<string, number>()
    const busRecord = bus as unknown as Record<string, unknown>
    const resolved: Record<string, number> = {}

    for (const id of this.order) {
      const node = this.byId.get(id)!
      if (node.kind === 'signal') {
        values.set(id, typeof busRecord[node.signal] === 'number' ? (busRecord[node.signal] as number) : 0)
        continue
      }
      const inputValues = node.inputs.map((inputId) => values.get(inputId) ?? 0)
      let threshold = this.thresholdState.get(id)
      if (!threshold) {
        threshold = { active: false }
        this.thresholdState.set(id, threshold)
      }
      let envelope = this.envelopeState.get(id)
      if (!envelope) {
        envelope = { value: 0 }
        this.envelopeState.set(id, envelope)
      }
      const value = evaluateNode(node, inputValues, dt, threshold, envelope)
      values.set(id, value)
      if (node.kind === 'target') resolved[node.targetId] = value
    }

    return resolved
  }
}
