import type { NodeId, PatchGraph } from './types'

// Keeps only the target nodes whose targetId is in `targetIds`, plus every
// node those targets transitively depend on — the rest of a larger,
// multi-domain graph is dropped. Exists so ONE authored graph can mix
// target nodes for different consumers (the screen's own targets and a
// physical fixture's channels, say) without each consumer's
// PatchGraphEvaluator ever seeing — and therefore having to validate or
// know anything about — a target that isn't its own (validatePatchGraph
// treats an unrecognized targetId as a hard error, correctly, since for a
// single-domain graph that IS almost always a typo). Cycle-safe: a node is
// added to `keep` before its inputs are visited, so revisiting it through a
// cycle is a no-op.
export function pruneGraphToTargets(graph: PatchGraph, targetIds: ReadonlySet<string>): PatchGraph {
  const byId = new Map(graph.nodes.map((n) => [n.id, n]))
  const keep = new Set<NodeId>()

  function mark(id: NodeId): void {
    if (keep.has(id)) return
    keep.add(id)
    const node = byId.get(id)
    if (!node) return
    for (const inputId of node.inputs) mark(inputId)
  }

  for (const node of graph.nodes) {
    if (node.kind === 'target' && targetIds.has(node.targetId)) mark(node.id)
  }

  return { id: graph.id, nodes: graph.nodes.filter((n) => keep.has(n.id)) }
}
