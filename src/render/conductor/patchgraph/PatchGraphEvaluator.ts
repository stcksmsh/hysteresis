import type { SignalBus } from '../types'
import type { PatchGraph, PatchTargetDecl } from './types'
import { validatePatchGraph } from './validate'
import { topoSort } from './topo-sort'
import { evaluateNode, type EnvelopeState, type ThresholdState } from './evaluate-node'

// Live non-bus inputs a graph can route from (midiCc/oscIn node kinds) —
// bundled into one optional object rather than growing evaluate()'s own
// positional parameter list per new external source. Both maps are keyed
// by each node kind's own address format (MidiCcInput's "channel:controller"
// string, an OSC address string) and omitted entirely (or empty) when that
// source was never opted into — a graph with no midiCc/oscIn nodes never
// needs to pass this at all.
export interface ExternalInputs {
  midiCc?: Map<string, number>
  oscIn?: Map<string, number>
}

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
  private targetsById: Map<string, PatchTargetDecl>

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
    this.targetsById = new Map(targets.map((t) => [t.id, t]))
  }

  // Returns { [targetId]: resolvedValue } for every `target` node in the
  // graph. A target with NO route to it simply never appears here — unlike
  // the screen Patchbay (which fills every declared target with a default
  // every frame, §5.1), this graph only exists to describe explicit wiring,
  // so callers (a fixture renderer, a future real output) decide what an
  // absent target means for their own device (hold last value, go dark,
  // whatever's safe for that hardware).
  evaluate(bus: SignalBus, dt: number, external?: ExternalInputs): Record<string, number> {
    const values = new Map<string, number>()
    const busRecord = bus as unknown as Record<string, unknown>
    const resolved: Record<string, number> = {}

    for (const id of this.order) {
      const node = this.byId.get(id)!
      if (node.kind === 'signal') {
        values.set(id, typeof busRecord[node.signal] === 'number' ? (busRecord[node.signal] as number) : 0)
        continue
      }
      if (node.kind === 'midiCc') {
        values.set(id, external?.midiCc?.get(node.ccKey) ?? 0)
        continue
      }
      if (node.kind === 'oscIn') {
        values.set(id, external?.oscIn?.get(node.address) ?? 0)
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
      if (node.kind === 'target') {
        // evaluateNode's 'target' case is a pure passthrough (see its own
        // comment) — nothing upstream guarantees a chain stays inside the
        // target's declared range (a bare signal node, a `map` with
        // clamp:false, a `combine` summing several routes...). Patchbay's
        // resolve() always clamped to target.range as the final step
        // (SINTEZA_SIGNAL_BUS.md §5.1); this evaluator didn't, which was a
        // real safety gap for exactly the case §5.3 exists to prevent (a
        // target physically can't accept out-of-range values) — every
        // target node's output is clamped here, matching that guarantee.
        const target = this.targetsById.get(node.targetId)
        resolved[node.targetId] = target ? Math.min(target.range[1], Math.max(target.range[0], value)) : value
      }
    }

    return resolved
  }
}
