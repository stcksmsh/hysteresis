import { SIGNAL_TAGS } from '../types'
import type { PatchGraph, PatchGraphNode, PatchTargetDecl } from './types'
import { CycleError, topoSort } from './topo-sort'

export interface PatchGraphIssue {
  nodeId: string
  message: string
  severity: 'error' | 'warning'
}

// Arity a node kind requires — checked structurally rather than trusted
// from the type system, since a hand-edited or programmatically-built graph
// can violate its own TS types at the JSON boundary (loaded from a saved
// file, or built by a future graph-UI that hasn't validated a drag yet).
function expectedInputCount(node: PatchGraphNode): { min: number; max: number } {
  switch (node.kind) {
    case 'signal':
    case 'const':
    case 'midiCc':
    case 'oscIn':
      return { min: 0, max: 0 }
    case 'threshold':
    case 'curve':
    case 'map':
    case 'target':
      return { min: 1, max: 1 }
    case 'envelope':
      // Always 3 slots — value (required) + optional attack/release
      // overrides, '' in slots 1/2 meaning "not connected" (see
      // EnvelopeNode's own comment in types.ts).
      return { min: 3, max: 3 }
    case 'logic':
      return node.op === 'not' ? { min: 1, max: 1 } : { min: 1, max: Infinity }
    case 'combine':
      return { min: 1, max: Infinity }
  }
}

// Structural + safety validation for a patch graph. Unlike the screen
// Patchbay's validate() (which throws on the first problem — §5.3's "reject
// unsafe at load time"), this collects every issue: there's no live
// hardware yet to protect, so an editor showing every problem at once beats
// crashing on the first one. Errors (dangling refs, bad arity, cycles)
// mean the graph literally cannot be evaluated; warnings (a target seeing a
// tag it shouldn't) are advisory — flagged for when this DOES drive real
// hardware, not blocking a simulated preview today.
export function validatePatchGraph(graph: PatchGraph, targets: PatchTargetDecl[]): PatchGraphIssue[] {
  const issues: PatchGraphIssue[] = []
  const byId = new Map(graph.nodes.map((n) => [n.id, n]))
  const targetsById = new Map(targets.map((t) => [t.id, t]))

  const seenIds = new Set<string>()
  for (const node of graph.nodes) {
    if (seenIds.has(node.id)) {
      issues.push({ nodeId: node.id, message: `duplicate node id "${node.id}"`, severity: 'error' })
    }
    seenIds.add(node.id)
  }

  for (const node of graph.nodes) {
    for (const inputId of node.inputs) {
      // '' is a real, valid value for envelope's optional attack/release
      // override slots (see EnvelopeNode's own comment) — deliberately not
      // a dangling reference, just "this optional slot isn't wired".
      if (inputId === '') continue
      if (!byId.has(inputId)) {
        issues.push({ nodeId: node.id, message: `references unknown node "${inputId}"`, severity: 'error' })
      }
    }
    const { min, max } = expectedInputCount(node)
    if (node.inputs.length < min || node.inputs.length > max) {
      const range = max === Infinity ? `at least ${min}` : min === max ? `exactly ${min}` : `${min}-${max}`
      issues.push({
        nodeId: node.id,
        message: `"${node.kind}" node expects ${range} input(s), has ${node.inputs.length}`,
        severity: 'error',
      })
    }
    if (node.kind === 'signal' && !(node.signal in SIGNAL_TAGS)) {
      issues.push({ nodeId: node.id, message: `"${node.signal}" is not a known bus signal`, severity: 'error' })
    }
    if (node.kind === 'midiCc' && !node.ccKey.trim()) {
      issues.push({ nodeId: node.id, message: 'midiCc node has no CC key set', severity: 'error' })
    }
    if (node.kind === 'oscIn' && !node.address.trim()) {
      issues.push({ nodeId: node.id, message: 'oscIn node has no OSC address set', severity: 'error' })
    }
    if (node.kind === 'target') {
      const target = targetsById.get(node.targetId)
      if (!target) {
        issues.push({ nodeId: node.id, message: `targets unknown fixture channel "${node.targetId}"`, severity: 'error' })
      }
    }
  }

  try {
    topoSort(graph)
  } catch (err) {
    if (err instanceof CycleError) {
      for (const id of err.cycleNodeIds) issues.push({ nodeId: id, message: err.message, severity: 'error' })
    } else {
      throw err
    }
  }

  // Servo-safety-style warning (SINTEZA_SIGNAL_BUS.md §5.3's principle,
  // advisory here): walk back from each target through curve/map/combine/
  // logic passthrough nodes to find the nearest signal node(s) whose tag
  // isn't smoothed away by an envelope/threshold in between, and warn if
  // it's 'transient' — a servo/mover physically can't follow a hi-hat.
  if (issues.every((i) => i.severity !== 'error')) {
    for (const node of graph.nodes) {
      if (node.kind !== 'target') continue
      const unsafe = findUnsmoothedTransientSignal(node.inputs[0], byId)
      if (unsafe) {
        issues.push({
          nodeId: node.id,
          message: `fed directly from transient signal "${unsafe}" with no threshold/envelope in between — a physical actuator may not be able to follow it`,
          severity: 'warning',
        })
      }
    }
  }

  return issues
}

function findUnsmoothedTransientSignal(nodeId: string, byId: Map<string, PatchGraphNode>, seen = new Set<string>()): string | null {
  if (seen.has(nodeId)) return null
  seen.add(nodeId)
  const node = byId.get(nodeId)
  if (!node) return null
  if (node.kind === 'signal') {
    return SIGNAL_TAGS[node.signal] === 'transient' ? node.signal : null
  }
  // threshold/envelope both smooth or gate a raw signal into something a
  // physical actuator can reasonably follow — stop walking back through
  // them. midiCc/oscIn are external human/tool-driven inputs with no bus
  // timescale tag at all (a knob or an external app's own fader, not
  // audio-domain analysis) — the transient-signal warning doesn't apply.
  if (node.kind === 'threshold' || node.kind === 'envelope' || node.kind === 'const' || node.kind === 'midiCc' || node.kind === 'oscIn') return null
  for (const inputId of node.inputs) {
    const found = findUnsmoothedTransientSignal(inputId, byId, seen)
    if (found) return found
  }
  return null
}
