import { makeDefaultDraft, makeNodeId, type DraftNode } from './graph-draft'
import type { PatchTargetDecl } from '../../../src/render/conductor/patchgraph/types'

// Continuous-tagged signals only — safe to feed any target (including
// servo/mover's CONTINUOUS_ONLY channels) with no threshold/envelope in
// between, per validate.ts's transient-signal warning. Rotated across
// targets so the demo fixtures visibly animate differently from each
// other rather than all pulsing in lockstep off the same one signal.
export const DEMO_SIGNALS: DraftNode['signal'][] = ['energy', 'low', 'mid', 'presence', 'air', 'centroid', 'pan', 'familiarity']

// Appends a range-mapping node between `sourceId` and the target if the
// target's range isn't already [0,1] — evaluate-node's `target` case is a
// pure passthrough, nothing clamps/rescales for it on its own, so a target
// like servo angle ([0,180]) would otherwise be fed a raw 0-1 value and
// visually barely move at all (the exact bug class this seed exists to
// avoid: a fixture that LOOKS wired but is actually stuck near its floor).
function mapIntoRange(target: PatchTargetDecl, sourceId: string, nodes: DraftNode[]): string {
  const [lo, hi] = target.range
  if (lo === 0 && hi === 1) return sourceId
  const map = makeDefaultDraft('map', makeNodeId())
  map.inRange = [0, 1]
  map.outRange = [lo, hi]
  map.clamp = true
  map.inputs = [sourceId]
  nodes.push(map)
  return map.id
}

// One target's demo chain: a signal, range-mapped into the target's own
// range, into the target. Every fixture channel gets one of these so every
// FixtureVisuals widget is actually live from the moment the editor opens,
// not just the first one.
export function seedChainForTarget(target: PatchTargetDecl, signal: DraftNode['signal']): DraftNode[] {
  const sig = makeDefaultDraft('signal', makeNodeId())
  sig.signal = signal
  const nodes: DraftNode[] = [sig]
  const mappedId = mapIntoRange(target, sig.id, nodes)
  const tgt = makeDefaultDraft('target', makeNodeId())
  tgt.targetId = target.id
  tgt.inputs = [mappedId]
  nodes.push(tgt)
  return nodes
}

// Seed graph: the first target keeps the original threshold-gated demo
// chain (still the clearest single example of a threshold node), range-
// mapped the same as every other target so it isn't a special case that
// can silently stay stuck in 0-1 space if the first fixture happens to be
// a servo/mover. Every other fixture channel gets a direct/range-mapped
// signal chain so nothing sits at its default value with no wiring at all.
export function seedNodes(targets: readonly PatchTargetDecl[]): DraftNode[] {
  if (targets.length === 0) return []
  const [first, ...rest] = targets
  const sig = makeDefaultDraft('signal', makeNodeId())
  const th = makeDefaultDraft('threshold', makeNodeId())
  th.inputs = [sig.id]
  const nodes: DraftNode[] = [sig, th]
  const mappedId = mapIntoRange(first, th.id, nodes)
  const tgt = makeDefaultDraft('target', makeNodeId())
  tgt.inputs = [mappedId]
  tgt.targetId = first.id
  nodes.push(tgt)
  rest.forEach((target, i) => {
    nodes.push(...seedChainForTarget(target, DEMO_SIGNALS[i % DEMO_SIGNALS.length]))
  })
  return nodes
}
