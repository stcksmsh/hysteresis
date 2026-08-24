import { useEffect, useMemo, useRef, useState } from 'react'
import { validatePatchGraph } from '../../../src/render/conductor/patchgraph/validate'
import type { PatchTargetDecl } from '../../../src/render/conductor/patchgraph/types'
import { makeDefaultDraft, makeNodeId, toPatchGraph, type DraftNode } from './graph-draft'
import { withAutoLayout } from './layout'
import { nodeBoxHeight, nodeBoxWidth, NUB_START_Y, NUB_SPACING } from './node-box'
import { NODE_KINDS, NodeFields, defaultLabel, displayName, fixedInputSlotCount, hasOutput, inputSlotLabel, isVariableArity, nodeSummary } from './node-fields'

// The visual node-graph canvas: drag nodes to place them, drag from a
// node's output circle to another node's input circle to wire them, pan by
// dragging empty background, zoom with the wheel (zoom-to-cursor). Node
// positions (DraftNode.x/y) live in a fixed "canvas space" that never
// changes — pan/zoom is purely a CSS transform on the content layer, so
// every stored position and every layout.ts calculation stays in the same
// simple coordinate system regardless of the current view. Hit-testing for
// wire drops uses document.elementFromPoint on real screen coordinates,
// which is transform-agnostic — no matrix inversion needed there either.
const ZOOM_MIN = 0.25
const ZOOM_MAX = 2
const ZOOM_DEFAULT = 1

function inputSlotIndices(node: DraftNode): number[] {
  const fixed = fixedInputSlotCount(node)
  if (fixed !== null) return fixed === 0 ? [] : [0]
  // variable arity: one slot per existing input, plus one trailing empty slot to append into
  return Array.from({ length: node.inputs.length + 1 }, (_, i) => i)
}

interface Point {
  x: number
  y: number
}

function nubPoint(node: DraftNode, kind: 'input' | 'output', index: number): Point {
  const x = (node.x ?? 0) + (kind === 'output' ? nodeBoxWidth(node) : 0)
  const y = (node.y ?? 0) + (kind === 'output' ? nodeBoxHeight(node) / 2 : NUB_START_Y + index * NUB_SPACING)
  return { x, y }
}

function bezierPath(a: Point, b: Point): string {
  const dx = Math.max(50, Math.abs(b.x - a.x) / 2)
  return `M ${a.x} ${a.y} C ${a.x + dx} ${a.y}, ${b.x - dx} ${b.y}, ${b.x} ${b.y}`
}

interface DragWire {
  fromNodeId: string
  mouse: Point
}

interface DraggingNode {
  id: string
  offsetX: number
  offsetY: number
}

interface Panning {
  startClientX: number
  startClientY: number
  startPanX: number
  startPanY: number
}

interface PatchGraphCanvasProps {
  nodes: DraftNode[]
  onChange: (next: DraftNode[]) => void
  targets: PatchTargetDecl[]
}

export function PatchGraphCanvas({ nodes, onChange, targets }: PatchGraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [dragWire, setDragWire] = useState<DragWire | null>(null)
  const [draggingNode, setDraggingNode] = useState<DraggingNode | null>(null)
  const [panning, setPanning] = useState<Panning | null>(null)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameDraft, setRenameDraft] = useState('')
  const [searchText, setSearchText] = useState('')
  const [zoom, setZoom] = useState(ZOOM_DEFAULT)
  const [pan, setPan] = useState<Point>({ x: 0, y: 0 })
  const addCascadeRef = useRef(0)
  const hasAutoFitRef = useRef(false)
  const searchListId = useRef(`node-search-${Math.random().toString(36).slice(2)}`).current

  // Seed positions for nodes that don't have one yet (fresh seed graph, a
  // load, or a just-added node) — onChange's setter identity is stable
  // (React state setter / App.tsx passes setGraphNodes directly), so this
  // can't loop: after the write every node has x/y and the condition goes false.
  useEffect(() => {
    if (nodes.some((n) => n.x === undefined || n.y === undefined)) {
      onChange(withAutoLayout(nodes))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- onChange identity is stable; re-running on every nodes change is the point
  }, [nodes])

  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes])
  const graph = useMemo(() => toPatchGraph('editor', nodes), [nodes])
  const issues = useMemo(() => validatePatchGraph(graph, targets), [graph, targets])
  const issuesByNodeId = useMemo(() => {
    const map = new Map<string, { message: string; severity: 'error' | 'warning' }[]>()
    for (const issue of issues) {
      const list = map.get(issue.nodeId) ?? []
      list.push({ message: issue.message, severity: issue.severity })
      map.set(issue.nodeId, list)
    }
    return map
  }, [issues])

  function patchNode(id: string, fields: Partial<DraftNode>) {
    onChange(nodes.map((n) => (n.id === id ? { ...n, ...fields } : n)))
  }

  function removeNode(id: string) {
    onChange(nodes.filter((n) => n.id !== id).map((n) => ({ ...n, inputs: n.inputs.filter((i) => i !== id) })))
    setSelectedId((cur) => (cur === id ? null : cur))
  }

  function fitToView() {
    const container = containerRef.current
    if (!container || nodes.length === 0) return
    const rect = container.getBoundingClientRect()
    if (rect.width === 0 || rect.height === 0) return
    const minX = Math.min(...nodes.map((n) => n.x ?? 0))
    const minY = Math.min(...nodes.map((n) => n.y ?? 0))
    const maxX = Math.max(...nodes.map((n) => (n.x ?? 0) + nodeBoxWidth(n)))
    const maxY = Math.max(...nodes.map((n) => (n.y ?? 0) + nodeBoxHeight(n)))
    const PAD = 60
    const nextZoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, Math.min((rect.width - PAD * 2) / Math.max(1, maxX - minX), (rect.height - PAD * 2) / Math.max(1, maxY - minY))))
    setZoom(nextZoom)
    setPan({ x: rect.width / 2 - (nextZoom * (minX + maxX)) / 2, y: rect.height / 2 - (nextZoom * (minY + maxY)) / 2 })
  }

  // First time this graph has real positions to show, frame all of it —
  // after that the user's own pan/zoom is left alone (adding one node
  // shouldn't yank the view every time).
  useEffect(() => {
    if (hasAutoFitRef.current) return
    if (nodes.length > 0 && nodes.every((n) => n.x !== undefined)) {
      hasAutoFitRef.current = true
      fitToView()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- one-shot, guarded by the ref above
  }, [nodes])

  function addNode(kind: DraftNode['kind']) {
    const rect = containerRef.current?.getBoundingClientRect()
    const cascade = (addCascadeRef.current++ % 6) * 28
    const centerCanvasX = rect ? (rect.width / 2 - pan.x) / zoom : 200
    const centerCanvasY = rect ? (rect.height / 2 - pan.y) / zoom : 200
    const draft: DraftNode = { ...makeDefaultDraft(kind, makeNodeId()), x: centerCanvasX + cascade, y: centerCanvasY + cascade }
    onChange([...nodes, draft])
    setSelectedId(draft.id)
  }

  function connectInput(destId: string, index: number, sourceId: string) {
    onChange(
      nodes.map((n) => {
        if (n.id !== destId) return n
        const inputs = [...n.inputs]
        // Pad with '' up to `index` rather than a plain push — a
        // fixed-arity node with position-significant slots (envelope's
        // attack/release overrides) can have its slot 2 connected before
        // slot 1 (or before slot 1 is ever wired at all); a plain
        // `inputs.push(sourceId)` would land it at the wrong position
        // whenever it isn't the very next index. Harmless no-op for the
        // common append-at-the-end case every other kind already used.
        while (inputs.length <= index) inputs.push('')
        inputs[index] = sourceId
        return { ...n, inputs }
      }),
    )
  }

  function disconnectInput(destId: string, index: number) {
    onChange(
      nodes.map((n) => {
        if (n.id !== destId) return n
        const inputs = [...n.inputs]
        // Fixed-arity nodes with position-significant slots (envelope)
        // must keep every later slot at its own index — splicing index 1
        // out would silently reindex a connected slot 2 (release
        // override) into slot 1 (attack override), swapping their
        // meaning. Variable-arity nodes (combine/logic) have no such
        // positional meaning, so removing the slot entirely (shrinking
        // the list) is correct there, same as before this fix.
        if (fixedInputSlotCount(n) !== null) inputs[index] = ''
        else inputs.splice(index, 1)
        return { ...n, inputs }
      }),
    )
  }

  function toCanvasPoint(clientX: number, clientY: number): Point {
    const rect = containerRef.current?.getBoundingClientRect()
    return { x: (clientX - (rect?.left ?? 0) - pan.x) / zoom, y: (clientY - (rect?.top ?? 0) - pan.y) / zoom }
  }

  // Global listeners while a wire drag, node drag, or pan is in flight —
  // pointer can move/release outside the exact element, especially at speed.
  useEffect(() => {
    if (!dragWire && !draggingNode && !panning) return

    function onMove(e: PointerEvent) {
      if (panning) {
        setPan({ x: panning.startPanX + (e.clientX - panning.startClientX), y: panning.startPanY + (e.clientY - panning.startClientY) })
        return
      }
      const p = toCanvasPoint(e.clientX, e.clientY)
      if (dragWire) setDragWire((w) => (w ? { ...w, mouse: p } : w))
      if (draggingNode) {
        patchNode(draggingNode.id, { x: p.x - draggingNode.offsetX, y: p.y - draggingNode.offsetY })
      }
    }

    function onUp(e: PointerEvent) {
      if (dragWire) {
        const el = document.elementFromPoint(e.clientX, e.clientY)
        const nub = el?.closest<HTMLElement>('[data-role="input"]')
        const destId = nub?.dataset.node
        const indexStr = nub?.dataset.index
        if (destId && indexStr !== undefined && destId !== dragWire.fromNodeId) {
          connectInput(destId, Number(indexStr), dragWire.fromNodeId)
        }
        setDragWire(null)
      }
      setDraggingNode(null)
      setPanning(null)
    }

    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- rebinding on every nodes/pan change would drop mid-drag state; closures below read current values via refs-in-effect pattern instead
  }, [dragWire !== null, draggingNode !== null, panning !== null])

  // Wheel-zoom needs preventDefault to stop the page itself scrolling —
  // React's synthetic onWheel is registered passive by default (perf), so
  // e.preventDefault() there is silently ignored. A real, non-passive
  // native listener is the only way to actually stop the scroll.
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    function onWheel(e: WheelEvent) {
      e.preventDefault()
      const rect = el!.getBoundingClientRect()
      const cx = e.clientX - rect.left
      const cy = e.clientY - rect.top
      setZoom((prevZoom) => {
        const nextZoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, prevZoom * Math.exp(-e.deltaY * 0.001)))
        setPan((prevPan) => {
          const canvasX = (cx - prevPan.x) / prevZoom
          const canvasY = (cy - prevPan.y) / prevZoom
          return { x: cx - canvasX * nextZoom, y: cy - canvasY * nextZoom }
        })
        return nextZoom
      })
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [])

  // Delete key removes the selected node, but never while focus is inside
  // an inspector form field (a Backspace while editing a number must edit
  // the number, not delete the node it belongs to).
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (!selectedId) return
      if (e.key !== 'Delete' && e.key !== 'Backspace') return
      const tag = document.activeElement?.tagName
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return
      removeNode(selectedId)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- removeNode/nodes captured fresh each render via closure over current props/state
  }, [selectedId, nodes])

  function onOutputNubDown(nodeId: string, e: React.PointerEvent) {
    e.stopPropagation()
    setDragWire({ fromNodeId: nodeId, mouse: toCanvasPoint(e.clientX, e.clientY) })
  }

  function onInputNubDown(destId: string, index: number, sourceId: string | undefined, e: React.PointerEvent) {
    e.stopPropagation()
    if (!sourceId) return // empty slot: nothing to pick up, only a drop target
    disconnectInput(destId, index)
    setDragWire({ fromNodeId: sourceId, mouse: toCanvasPoint(e.clientX, e.clientY) })
  }

  function onHeaderDown(node: DraftNode, e: React.PointerEvent) {
    if ((e.target as HTMLElement).closest('.node-remove-btn') || (e.target as HTMLElement).closest('.node-rename-input')) return
    e.stopPropagation() // don't also start a background pan
    setSelectedId(node.id)
    if (renamingId && renamingId !== node.id) commitRename()
    const p = toCanvasPoint(e.clientX, e.clientY)
    setDraggingNode({ id: node.id, offsetX: p.x - (node.x ?? 0), offsetY: p.y - (node.y ?? 0) })
  }

  function onViewportPointerDown(e: React.PointerEvent) {
    if ((e.target as HTMLElement).closest('.graph-node')) return
    setSelectedId(null)
    setPanning({ startClientX: e.clientX, startClientY: e.clientY, startPanX: pan.x, startPanY: pan.y })
  }

  function startRename(node: DraftNode) {
    setRenamingId(node.id)
    setRenameDraft(node.label ?? defaultLabel(node))
  }

  function commitRename() {
    if (renamingId) {
      const trimmed = renameDraft.trim()
      patchNode(renamingId, { label: trimmed || undefined })
    }
    setRenamingId(null)
  }

  function jumpToNode(name: string) {
    const target = nodes.find((n) => displayName(n) === name)
    const rect = containerRef.current?.getBoundingClientRect()
    if (!target || !rect) return
    setSelectedId(target.id)
    const cx = (target.x ?? 0) + nodeBoxWidth(target) / 2
    const cy = (target.y ?? 0) + nodeBoxHeight(target) / 2
    setPan({ x: rect.width / 2 - zoom * cx, y: rect.height / 2 - zoom * cy })
  }

  const contentWidth = Math.max(1400, ...nodes.map((n) => (n.x ?? 0) + nodeBoxWidth(n) + 300))
  const contentHeight = Math.max(900, ...nodes.map((n) => (n.y ?? 0) + nodeBoxHeight(n) + 200))

  const selected = selectedId ? (byId.get(selectedId) ?? null) : null
  const selectedIssues = selectedId ? issuesByNodeId.get(selectedId) : undefined
  const errorCount = issues.filter((i) => i.severity === 'error').length

  return (
    <div className="graph-canvas-root">
      <div className="graph-toolbar">
        {NODE_KINDS.map((kind) => (
          <button key={kind} onClick={() => addNode(kind)}>
            + {kind}
          </button>
        ))}
        <input
          type="text"
          list={searchListId}
          placeholder="Find a node…"
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              jumpToNode(searchText)
              setSearchText('')
            }
          }}
          style={{ width: 160, fontSize: 12, marginLeft: 8 }}
        />
        <datalist id={searchListId}>
          {nodes.map((n) => (
            <option key={n.id} value={displayName(n)} />
          ))}
        </datalist>
        <button onClick={fitToView} title="Frame every node in view">
          ⊡ Fit
        </button>
        <span className="status-pill zoom-pill">{Math.round(zoom * 100)}%</span>
        <span className="status-pill" style={{ marginLeft: 'auto' }}>
          {errorCount > 0 ? `${errorCount} error(s)` : 'valid'}
        </span>
      </div>
      <div className="graph-canvas-body">
        <div className="graph-canvas-viewport" ref={containerRef} onPointerDown={onViewportPointerDown}>
          <div
            className="graph-canvas-content"
            style={{ width: contentWidth, height: contentHeight, transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
          >
            <svg className="graph-canvas-svg" width={contentWidth} height={contentHeight}>
              {nodes.map((node) =>
                node.inputs.map((sourceId, i) => {
                  if (!sourceId) return null
                  const source = byId.get(sourceId)
                  if (!source) return null
                  const a = nubPoint(source, 'output', 0)
                  const b = nubPoint(node, 'input', i)
                  const errored = (issuesByNodeId.get(node.id)?.length ?? 0) > 0 || (issuesByNodeId.get(sourceId)?.length ?? 0) > 0
                  return <path key={`${node.id}-${i}`} d={bezierPath(a, b)} className={errored ? 'graph-edge graph-edge-error' : 'graph-edge'} />
                }),
              )}
              {dragWire && (() => {
                const source = byId.get(dragWire.fromNodeId)
                if (!source) return null
                return <path d={bezierPath(nubPoint(source, 'output', 0), dragWire.mouse)} className="graph-edge graph-edge-dragging" />
              })()}
            </svg>

            {nodes.map((node) => {
              const nodeIssues = issuesByNodeId.get(node.id)
              const hasError = nodeIssues?.some((i) => i.severity === 'error')
              const inputSlots = inputSlotIndices(node)
              return (
                <div
                  key={node.id}
                  className={`graph-node${hasError ? ' has-error' : ''}${selectedId === node.id ? ' selected' : ''}`}
                  style={{ left: node.x ?? 0, top: node.y ?? 0, width: nodeBoxWidth(node), height: nodeBoxHeight(node) }}
                  onPointerDown={(e) => onHeaderDown(node, e)}
                >
                  <div className="graph-node-header">
                    {renamingId === node.id ? (
                      <input
                        className="node-rename-input"
                        autoFocus
                        value={renameDraft}
                        onChange={(e) => setRenameDraft(e.target.value)}
                        onBlur={commitRename}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') commitRename()
                          if (e.key === 'Escape') setRenamingId(null)
                        }}
                        onPointerDown={(e) => e.stopPropagation()}
                      />
                    ) : (
                      <strong className="graph-node-label" onDoubleClick={() => startRename(node)} title={`${node.kind} · ${node.id} — double-click to rename`}>
                        {displayName(node)}
                      </strong>
                    )}
                    <button className="node-remove-btn" onPointerDown={(e) => e.stopPropagation()} onClick={() => removeNode(node.id)} title="Remove node">
                      ✕
                    </button>
                  </div>
                  <div className="graph-node-summary">{nodeSummary(node)}</div>

                  {inputSlots.map((i) => (
                    <div
                      key={i}
                      className={`nub nub-input${node.inputs[i] ? ' filled' : ''}`}
                      style={{ top: NUB_START_Y + i * NUB_SPACING }}
                      data-role="input"
                      data-node={node.id}
                      data-index={i}
                      onPointerDown={(e) => onInputNubDown(node.id, i, node.inputs[i], e)}
                      title={(() => {
                        const label = inputSlotLabel(node, i)
                        const prefix = label ? `${label}: ` : ''
                        return node.inputs[i] ? `${prefix}from ${node.inputs[i]} — click/drag to disconnect` : `${prefix}drag a wire here to connect`
                      })()}
                    />
                  ))}
                  {hasOutput(node) && (
                    <div
                      className="nub nub-output"
                      style={{ top: nodeBoxHeight(node) / 2 }}
                      data-role="output"
                      data-node={node.id}
                      onPointerDown={(e) => onOutputNubDown(node.id, e)}
                      title="drag to wire this node's output into another node"
                    />
                  )}
                </div>
              )
            })}

            {nodes.length === 0 && <div className="empty-hint" style={{ position: 'absolute', left: 40, top: 40 }}>No nodes yet — add one above.</div>}
          </div>
        </div>

        <div className="graph-inspector">
          {selected ? (
            <>
              <div className="graph-inspector-header">
                <strong>{displayName(selected)}</strong>
                <code className="mono">{selected.kind} · {selected.id}</code>
              </div>
              <label className="node-fields" style={{ fontSize: 11 }}>
                name:
                <input
                  type="text"
                  value={selected.label ?? ''}
                  placeholder={defaultLabel(selected)}
                  onChange={(e) => patchNode(selected.id, { label: e.target.value || undefined })}
                  style={{ flex: 1, fontSize: 12 }}
                />
              </label>
              <NodeFields node={selected} targets={targets} onPatch={patchNode} />
              {selectedIssues && selectedIssues.length > 0 && (
                <div className="issue-list">
                  {selectedIssues.map((issue, i) => (
                    <div key={i} className={issue.severity === 'error' ? 'issue-error' : 'issue-warning'}>
                      {issue.severity}: {issue.message}
                    </div>
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="empty-hint">
              Click a node to edit its parameters here. Drag from the circle on a node's right edge to a circle on
              another node's left edge to wire them. Drag a node's header to move it, drag empty space to pan, scroll
              to zoom. Click a filled input circle to disconnect it. Select a node and press Delete to remove it.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
