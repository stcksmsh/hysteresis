import type { DraftNode } from './graph-draft'
import { nodeBoxHeight, nodeBoxWidth } from './node-box'

// Initial placement for nodes that don't have a saved x/y yet (freshly
// seeded graph, or one loaded from a file — positions are UI-only, see
// graph-draft.ts, so a load always needs this). Column = longest-path depth
// from a root (a node with no inputs), so signal/const sources sit on the
// left and chains flow rightward toward their eventual target node, reading
// the same direction the graph actually evaluates in. Row packing uses each
// node's REAL box height (node-box.ts — shared with the canvas's own
// rendering, so packing and drawing always agree) rather than a fixed slot,
// so a column mixing short (signal/const) and tall (a combine node with
// many inputs) boxes doesn't waste space padding every row to the tallest.
const COL_GAP = 60
const ROW_GAP = 24
const MARGIN = 40

export function computeAutoLayout(nodes: DraftNode[]): Record<string, { x: number; y: number }> {
  const byId = new Map(nodes.map((n) => [n.id, n]))

  function depth(id: string, seen: Set<string>): number {
    if (seen.has(id)) return 0 // cycle guard — validate.ts flags cycles separately, layout just needs to terminate
    const node = byId.get(id)
    if (!node || node.inputs.length === 0) return 0
    const nextSeen = new Set(seen)
    nextSeen.add(id)
    let max = 0
    for (const inputId of node.inputs) {
      if (!inputId) continue
      max = Math.max(max, depth(inputId, nextSeen))
    }
    return 1 + max
  }

  const byDepth = new Map<number, string[]>()
  let maxDepth = 0
  for (const node of nodes) {
    const d = depth(node.id, new Set())
    maxDepth = Math.max(maxDepth, d)
    const list = byDepth.get(d) ?? []
    list.push(node.id)
    byDepth.set(d, list)
  }

  // Each column's x is the previous columns' actual max width, not a fixed
  // pitch — a column of short `signal` nodes shouldn't reserve as much
  // horizontal room as one full of wide `target` nodes.
  const colX: number[] = [MARGIN]
  for (let d = 0; d <= maxDepth; d++) {
    const ids = byDepth.get(d) ?? []
    const widest = ids.reduce((max, id) => Math.max(max, nodeBoxWidth(byId.get(id)!)), 0)
    colX[d + 1] = colX[d] + widest + COL_GAP
  }

  const positions: Record<string, { x: number; y: number }> = {}
  for (const [d, ids] of byDepth) {
    let y = MARGIN
    for (const id of ids) {
      positions[id] = { x: colX[d], y }
      y += nodeBoxHeight(byId.get(id)!) + ROW_GAP
    }
  }
  return positions
}

// Fills in x/y for any node missing them, leaving already-placed nodes
// (dragged by the user) untouched — so re-running this after adding one new
// node doesn't reshuffle everything else.
export function withAutoLayout(nodes: DraftNode[]): DraftNode[] {
  if (nodes.every((n) => n.x !== undefined && n.y !== undefined)) return nodes
  const computed = computeAutoLayout(nodes)
  return nodes.map((n) => (n.x !== undefined && n.y !== undefined ? n : { ...n, x: computed[n.id]?.x ?? MARGIN, y: computed[n.id]?.y ?? MARGIN }))
}
