import type { DraftNode } from './graph-draft'
import { displayName, isVariableArity } from './node-fields'

// Shared node-box sizing — one source of truth for both the auto-layout
// packer (layout.ts) and the canvas's own rendering/hit-testing
// (PatchGraphCanvas.tsx). They must agree exactly: layout.ts packs rows
// using these sizes, and if the canvas rendered nodes at a different size
// than what was packed for, nodes would visually overlap.
export const NUB_START_Y = 40
export const NUB_SPACING = 20
export const MIN_BOX_H = 90
const MIN_BOX_W = 150
const MAX_BOX_W = 260
// Rough monospace-ish character width at the label's actual font-size
// (13px, semibold — see .graph-node-label) plus header chrome (remove
// button, padding) — doesn't need to be exact, just close enough that a
// descriptive label (the whole point of renaming nodes) isn't truncated in
// the common case, without every node ballooning to the same max width.
const CHAR_WIDTH = 7.2
const HEADER_CHROME = 46

export function nodeBoxWidth(node: DraftNode): number {
  const width = displayName(node).length * CHAR_WIDTH + HEADER_CHROME
  return Math.max(MIN_BOX_W, Math.min(MAX_BOX_W, Math.round(width)))
}

export function nodeBoxHeight(node: DraftNode): number {
  if (isVariableArity(node.kind)) {
    const slots = node.inputs.length + 1 // +1 trailing empty "add another input" slot
    return Math.max(MIN_BOX_H, NUB_START_Y + slots * NUB_SPACING + 16)
  }
  return MIN_BOX_H
}
