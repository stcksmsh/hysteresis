import type { NodeId, PatchGraph } from './types'

export class CycleError extends Error {
  constructor(public readonly cycleNodeIds: NodeId[]) {
    super(`patch graph has a cycle: ${cycleNodeIds.join(' -> ')}`)
  }
}

// Returns node ids in an order where every node's inputs are already earlier
// in the list — the evaluator relies on this to compute each node exactly
// once per frame in one linear pass. Throws CycleError if the graph isn't a
// DAG (a real possibility once users are wiring nodes by hand).
export function topoSort(graph: PatchGraph): NodeId[] {
  const byId = new Map(graph.nodes.map((n) => [n.id, n]))
  const state = new Map<NodeId, 'visiting' | 'done'>()
  const order: NodeId[] = []
  const stack: NodeId[] = []

  function visit(id: NodeId): void {
    const status = state.get(id)
    if (status === 'done') return
    if (status === 'visiting') {
      const cycleStart = stack.indexOf(id)
      throw new CycleError(stack.slice(cycleStart).concat(id))
    }
    const node = byId.get(id)
    if (!node) return // dangling reference — validate.ts reports this separately, not this function's job
    state.set(id, 'visiting')
    stack.push(id)
    for (const inputId of node.inputs) visit(inputId)
    stack.pop()
    state.set(id, 'done')
    order.push(id)
  }

  for (const node of graph.nodes) visit(node.id)
  return order
}
