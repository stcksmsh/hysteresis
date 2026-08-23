import { SIGNAL_CATALOG } from '../../../src/render/conductor/patchbay/editor/catalog'
import { validatePatchGraph } from '../../../src/render/conductor/patchgraph/validate'
import type { PatchTargetDecl, CurveKind } from '../../../src/render/conductor/patchgraph/types'
import { makeDefaultDraft, makeNodeId, toPatchGraph, type DraftNode } from './graph-draft'

// The physical patch-graph builder (task #4's other half) — a structured
// (not canvas/drag) editor, per the earlier scoping decision: build the
// structured version to a high bar first, keep it extensible into a
// node-graph *view* later by never letting editing logic live in this
// component. Every button/input here does exactly one thing — replace this
// node's fields, or the node list — so a future graph canvas can call the
// same operations from a drag gesture instead of a form control.
const NODE_KINDS: DraftNode['kind'][] = ['signal', 'const', 'threshold', 'envelope', 'logic', 'combine', 'curve', 'map', 'target']
const CURVE_KINDS: CurveKind[] = ['linear', 'exp', 'log', 'smoothstep']

interface GraphEditorProps {
  nodes: DraftNode[]
  onChange: (next: DraftNode[]) => void
  targets: PatchTargetDecl[]
}

export function GraphEditor({ nodes, onChange, targets }: GraphEditorProps) {
  const graph = toPatchGraph('editor', nodes)
  const issues = validatePatchGraph(graph, targets)
  const issuesByNodeId = new Map<string, { message: string; severity: 'error' | 'warning' }[]>()
  for (const issue of issues) {
    const list = issuesByNodeId.get(issue.nodeId) ?? []
    list.push({ message: issue.message, severity: issue.severity })
    issuesByNodeId.set(issue.nodeId, list)
  }

  function patchNode(id: string, fields: Partial<DraftNode>) {
    onChange(nodes.map((n) => (n.id === id ? { ...n, ...fields } : n)))
  }

  function removeNode(id: string) {
    onChange(nodes.filter((n) => n.id !== id).map((n) => ({ ...n, inputs: n.inputs.filter((i) => i !== id) })))
  }

  function addNode(kind: DraftNode['kind']) {
    onChange([...nodes, makeDefaultDraft(kind, makeNodeId())])
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {nodes.length === 0 && <div className="empty-hint">No nodes yet — add one below.</div>}
      {nodes.map((node) => (
        <NodeRow key={node.id} node={node} allNodes={nodes} targets={targets} issues={issuesByNodeId.get(node.id)} onPatch={patchNode} onRemove={removeNode} />
      ))}
      <div className="kind-picker">
        {NODE_KINDS.map((kind) => (
          <button key={kind} onClick={() => addNode(kind)}>
            + {kind}
          </button>
        ))}
      </div>
    </div>
  )
}

interface NodeRowProps {
  node: DraftNode
  allNodes: DraftNode[]
  targets: PatchTargetDecl[]
  issues?: { message: string; severity: 'error' | 'warning' }[]
  onPatch: (id: string, fields: Partial<DraftNode>) => void
  onRemove: (id: string) => void
}

function NodeRow({ node, allNodes, targets, issues, onPatch, onRemove }: NodeRowProps) {
  const otherNodeIds = allNodes.filter((n) => n.id !== node.id).map((n) => n.id)
  const hasError = issues?.some((i) => i.severity === 'error')

  function setInputsFromText(text: string) {
    const inputs = text
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    onPatch(node.id, { inputs })
  }

  return (
    <div className={`node-card${hasError ? ' has-error' : ''}`}>
      <div className="node-card-header">
        <code className="mono node-card-id">{node.id}</code>
        <strong className="node-card-kind">{node.kind}</strong>
        <button onClick={() => onRemove(node.id)} style={{ marginLeft: 'auto', padding: '2px 8px', fontSize: 11 }} title="Remove node">
          ✕
        </button>
      </div>

      <NodeFields node={node} targets={targets} onPatch={onPatch} />

      {node.kind !== 'signal' && node.kind !== 'const' && (
        <label style={{ fontSize: 11, color: 'var(--text-1)' }}>
          inputs (node ids, comma-separated — available: {otherNodeIds.join(', ') || 'none yet'})
          <input
            type="text"
            value={node.inputs.join(', ')}
            onChange={(e) => setInputsFromText(e.target.value)}
            style={{ display: 'block', width: '100%', marginTop: 2, fontSize: 12 }}
          />
        </label>
      )}

      {issues && issues.length > 0 && (
        <div className="issue-list">
          {issues.map((issue, i) => (
            <div key={i} className={issue.severity === 'error' ? 'issue-error' : 'issue-warning'}>
              {issue.severity}: {issue.message}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function NodeFields({ node, targets, onPatch }: { node: DraftNode; targets: PatchTargetDecl[]; onPatch: (id: string, fields: Partial<DraftNode>) => void }) {
  switch (node.kind) {
    case 'signal':
      return (
        <div className="node-fields">
          signal:
          <select value={node.signal} onChange={(e) => onPatch(node.id, { signal: e.target.value })} style={{ fontSize: 11 }}>
            {SIGNAL_CATALOG.filter((s) => s.tag !== 'pass-through').map((s) => (
              <option key={s.name} value={s.name}>
                {s.name}
              </option>
            ))}
          </select>
        </div>
      )
    case 'const':
      return (
        <div className="node-fields">
          value:
          <input type="number" step={0.05} value={node.value ?? 0} onChange={(e) => onPatch(node.id, { value: Number(e.target.value) })} style={{ width: 70 }} />
        </div>
      )
    case 'threshold':
      return (
        <div className="node-fields">
          cut:
          <input type="number" step={0.05} value={node.cut ?? 0.5} onChange={(e) => onPatch(node.id, { cut: Number(e.target.value) })} style={{ width: 60 }} />
          hysteresis:
          <input
            type="number"
            step={0.01}
            value={node.hysteresis ?? 0}
            onChange={(e) => onPatch(node.id, { hysteresis: Number(e.target.value) })}
            style={{ width: 60 }}
          />
        </div>
      )
    case 'envelope':
      return (
        <div className="node-fields">
          attackSec:
          <input
            type="number"
            step={0.05}
            value={node.attackSec ?? 0.1}
            onChange={(e) => onPatch(node.id, { attackSec: Number(e.target.value) })}
            style={{ width: 60 }}
          />
          releaseSec:
          <input
            type="number"
            step={0.05}
            value={node.releaseSec ?? 0.5}
            onChange={(e) => onPatch(node.id, { releaseSec: Number(e.target.value) })}
            style={{ width: 60 }}
          />
        </div>
      )
    case 'logic':
      return (
        <div className="node-fields">
          op:
          <select value={node.logicOp} onChange={(e) => onPatch(node.id, { logicOp: e.target.value as DraftNode['logicOp'] })} style={{ fontSize: 11 }}>
            <option value="and">and (min)</option>
            <option value="or">or (max)</option>
            <option value="not">not (1-x, needs exactly 1 input)</option>
          </select>
        </div>
      )
    case 'combine':
      return (
        <div className="node-fields">
          op:
          <select value={node.combineOp} onChange={(e) => onPatch(node.id, { combineOp: e.target.value as DraftNode['combineOp'] })} style={{ fontSize: 11 }}>
            <option value="add">add</option>
            <option value="multiply">multiply</option>
            <option value="max">max</option>
            <option value="min">min</option>
          </select>
        </div>
      )
    case 'curve':
      return (
        <div className="node-fields">
          curve:
          <select value={node.curve} onChange={(e) => onPatch(node.id, { curve: e.target.value as CurveKind })} style={{ fontSize: 11 }}>
            {CURVE_KINDS.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
      )
    case 'map':
      return (
        <div className="node-fields" style={{ flexWrap: 'wrap' }}>
          in:
          <input
            type="number"
            step={0.05}
            value={node.inRange?.[0] ?? 0}
            onChange={(e) => onPatch(node.id, { inRange: [Number(e.target.value), node.inRange?.[1] ?? 1] })}
            style={{ width: 55 }}
          />
          –
          <input
            type="number"
            step={0.05}
            value={node.inRange?.[1] ?? 1}
            onChange={(e) => onPatch(node.id, { inRange: [node.inRange?.[0] ?? 0, Number(e.target.value)] })}
            style={{ width: 55 }}
          />
          out:
          <input
            type="number"
            step={0.05}
            value={node.outRange?.[0] ?? 0}
            onChange={(e) => onPatch(node.id, { outRange: [Number(e.target.value), node.outRange?.[1] ?? 1] })}
            style={{ width: 55 }}
          />
          –
          <input
            type="number"
            step={0.05}
            value={node.outRange?.[1] ?? 1}
            onChange={(e) => onPatch(node.id, { outRange: [node.outRange?.[0] ?? 0, Number(e.target.value)] })}
            style={{ width: 55 }}
          />
          <label>
            <input type="checkbox" checked={node.clamp ?? true} onChange={(e) => onPatch(node.id, { clamp: e.target.checked })} /> clamp
          </label>
        </div>
      )
    case 'target':
      return (
        <div className="node-fields">
          target:
          <select value={node.targetId} onChange={(e) => onPatch(node.id, { targetId: e.target.value })} style={{ fontSize: 11 }}>
            <option value="">(choose a fixture channel)</option>
            {targets.map((t) => (
              <option key={t.id} value={t.id}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
      )
  }
}
