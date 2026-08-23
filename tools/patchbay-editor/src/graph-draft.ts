import type { CurveKind, PatchGraph, PatchGraphNode } from '../../../src/render/conductor/patchgraph/types'
import type { RoutableSignalName } from '../../../src/render/conductor/types'

// The graph editor works over a looser "draft" shape rather than
// PatchGraphNode directly: several real node kinds declare `inputs` as a
// fixed-length tuple (e.g. `readonly [NodeId]` for threshold/envelope/
// curve/map/target), which is the right guarantee for code that
// constructs a node once and knows its kind up front — but an interactive
// form is naturally building up a node's shape field by field, kind first,
// inputs filled in after, so forcing the exact tuple arity at every
// keystroke would fight the editor rather than help it.
// toPatchGraphNode() below is where a draft becomes a real, correctly-typed
// node — arity itself is still enforced by validatePatchGraph() (a runtime
// check, deliberately not a TS-level one, exactly because a hand-built
// graph is real input this tool has to validate, not just construct).
export interface DraftNode {
  id: string
  kind: PatchGraphNode['kind']
  inputs: string[]
  signal?: string
  value?: number
  cut?: number
  hysteresis?: number
  attackSec?: number
  releaseSec?: number
  logicOp?: 'and' | 'or' | 'not'
  combineOp?: 'add' | 'multiply' | 'max' | 'min'
  curve?: CurveKind
  inRange?: [number, number]
  outRange?: [number, number]
  clamp?: boolean
  targetId?: string
}

let nextDraftId = 1
export function makeNodeId(): string {
  return `n${nextDraftId++}`
}

export function makeDefaultDraft(kind: PatchGraphNode['kind'], id: string = makeNodeId()): DraftNode {
  switch (kind) {
    case 'signal':
      return { id, kind, inputs: [], signal: 'energy' }
    case 'const':
      return { id, kind, inputs: [], value: 0.5 }
    case 'threshold':
      return { id, kind, inputs: [], cut: 0.5, hysteresis: 0.05 }
    case 'envelope':
      return { id, kind, inputs: [], attackSec: 0.1, releaseSec: 0.5 }
    case 'logic':
      return { id, kind, inputs: [], logicOp: 'and' }
    case 'combine':
      return { id, kind, inputs: [], combineOp: 'add' }
    case 'curve':
      return { id, kind, inputs: [], curve: 'linear' }
    case 'map':
      return { id, kind, inputs: [], inRange: [0, 1], outRange: [0, 1], clamp: true }
    case 'target':
      return { id, kind, inputs: [], targetId: '' }
  }
}

export function toPatchGraphNode(d: DraftNode): PatchGraphNode {
  const inputs = d.inputs
  switch (d.kind) {
    case 'signal':
      return { id: d.id, kind: 'signal', inputs: [], signal: (d.signal ?? 'energy') as RoutableSignalName }
    case 'const':
      return { id: d.id, kind: 'const', inputs: [], value: d.value ?? 0 }
    case 'threshold':
      return { id: d.id, kind: 'threshold', inputs: [inputs[0] ?? ''], cut: d.cut ?? 0.5, hysteresis: d.hysteresis }
    case 'envelope':
      return { id: d.id, kind: 'envelope', inputs: [inputs[0] ?? ''], attackSec: d.attackSec ?? 0.1, releaseSec: d.releaseSec ?? 0.5 }
    case 'logic':
      return d.logicOp === 'not'
        ? { id: d.id, kind: 'logic', op: 'not', inputs: [inputs[0] ?? ''] }
        : { id: d.id, kind: 'logic', op: d.logicOp ?? 'and', inputs }
    case 'combine':
      return { id: d.id, kind: 'combine', op: d.combineOp ?? 'add', inputs }
    case 'curve':
      return { id: d.id, kind: 'curve', inputs: [inputs[0] ?? ''], curve: d.curve ?? 'linear' }
    case 'map':
      return {
        id: d.id,
        kind: 'map',
        inputs: [inputs[0] ?? ''],
        inRange: d.inRange ?? [0, 1],
        outRange: d.outRange ?? [0, 1],
        clamp: d.clamp ?? true,
      }
    case 'target':
      return { id: d.id, kind: 'target', inputs: [inputs[0] ?? ''], targetId: d.targetId ?? '' }
  }
}

export function toPatchGraph(id: string, drafts: DraftNode[]): PatchGraph {
  return { id, nodes: drafts.map(toPatchGraphNode) }
}

export function fromPatchGraphNode(n: PatchGraphNode): DraftNode {
  const base = { id: n.id, kind: n.kind, inputs: [...n.inputs] }
  switch (n.kind) {
    case 'signal':
      return { ...base, signal: n.signal }
    case 'const':
      return { ...base, value: n.value }
    case 'threshold':
      return { ...base, cut: n.cut, hysteresis: n.hysteresis }
    case 'envelope':
      return { ...base, attackSec: n.attackSec, releaseSec: n.releaseSec }
    case 'logic':
      return { ...base, logicOp: n.op }
    case 'combine':
      return { ...base, combineOp: n.op }
    case 'curve':
      return { ...base, curve: n.curve }
    case 'map':
      return { ...base, inRange: [...n.inRange] as [number, number], outRange: [...n.outRange] as [number, number], clamp: n.clamp }
    case 'target':
      return { ...base, targetId: n.targetId }
  }
}
