import { SIGNAL_CATALOG } from '../../../src/render/conductor/patchbay/editor/catalog'
import type { PatchTargetDecl, CurveKind } from '../../../src/render/conductor/patchgraph/types'
import type { DraftNode } from './graph-draft'

// Shared between the node-graph canvas's per-node inspector and (formerly)
// the flat form editor — kept as its own module so neither has to duplicate
// the field set for all 9 node kinds. Pure display/edit of one node's
// params; wiring (inputs) is the canvas's job now, not this component's.
export const NODE_KINDS: DraftNode['kind'][] = ['signal', 'const', 'midiCc', 'oscIn', 'threshold', 'envelope', 'logic', 'combine', 'curve', 'map', 'target']
export const CURVE_KINDS: CurveKind[] = ['linear', 'exp', 'log', 'smoothstep']

export function NodeFields({ node, targets, onPatch }: { node: DraftNode; targets: PatchTargetDecl[]; onPatch: (id: string, fields: Partial<DraftNode>) => void }) {
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
    case 'midiCc':
      return (
        <div className="node-fields">
          CC key ("channel:controller"):
          <input type="text" placeholder="0:1" value={node.ccKey ?? ''} onChange={(e) => onPatch(node.id, { ccKey: e.target.value })} style={{ width: 80 }} />
        </div>
      )
    case 'oscIn':
      return (
        <div className="node-fields">
          OSC address:
          <input type="text" placeholder="/1/fader1" value={node.address ?? ''} onChange={(e) => onPatch(node.id, { address: e.target.value })} style={{ width: 120 }} />
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
                {t.label ?? t.id}
              </option>
            ))}
          </select>
        </div>
      )
  }
}

// One-line compact summary shown inside a node's box on the canvas — the
// canvas is deliberately small/dense (many nodes on screen at once), full
// field editing happens in the inspector for whichever node is selected.
export function nodeSummary(node: DraftNode): string {
  switch (node.kind) {
    case 'signal':
      return node.signal ?? '—'
    case 'const':
      return String(node.value ?? 0)
    case 'midiCc':
      return node.ccKey || '(unset)'
    case 'oscIn':
      return node.address || '(unset)'
    case 'threshold':
      return `cut ${(node.cut ?? 0.5).toFixed(2)}${node.hysteresis ? ` ±${node.hysteresis.toFixed(2)}` : ''}`
    case 'envelope': {
      const atkLive = node.inputs[1] ? ' (live)' : ''
      const relLive = node.inputs[2] ? ' (live)' : ''
      return `atk ${(node.attackSec ?? 0.1).toFixed(2)}${atkLive} / rel ${(node.releaseSec ?? 0.5).toFixed(2)}${relLive}`
    }
    case 'logic':
      return node.logicOp ?? 'and'
    case 'combine':
      return node.combineOp ?? 'add'
    case 'curve':
      return node.curve ?? 'linear'
    case 'map': {
      const inR = node.inRange ?? [0, 1]
      const outR = node.outRange ?? [0, 1]
      return `${inR[0]}–${inR[1]} → ${outR[0]}–${outR[1]}`
    }
    case 'target':
      return node.targetId || '(unset)'
  }
}

// Auto-generated name for a node with no user-set label — kept short (this
// is what the canvas shows in a node's header when unlabeled), distinct
// from nodeSummary()'s fuller one-line param dump.
export function defaultLabel(node: DraftNode): string {
  switch (node.kind) {
    case 'signal':
      return node.signal ?? 'signal'
    case 'const':
      return `const ${node.value ?? 0}`
    case 'midiCc':
      return 'midi cc'
    case 'oscIn':
      return 'osc in'
    case 'threshold':
      return 'threshold'
    case 'envelope':
      return 'envelope'
    case 'logic':
      return node.logicOp ?? 'logic'
    case 'combine':
      return node.combineOp ?? 'combine'
    case 'curve':
      return node.curve ?? 'curve'
    case 'map':
      return 'map'
    case 'target':
      return node.targetId || 'target'
  }
}

export function displayName(node: DraftNode): string {
  return node.label?.trim() || defaultLabel(node)
}

export function isVariableArity(kind: DraftNode['kind']): boolean {
  return kind === 'combine' || kind === 'logic'
}

// Fixed-arity nodes always want exactly this many input slots shown (even
// before they're wired, so there's always somewhere to drop a wire); a
// `logic` node's slot count depends on its op (`not` is unary despite the
// kind being "variable" in general).
export function fixedInputSlotCount(node: DraftNode): number | null {
  switch (node.kind) {
    case 'signal':
    case 'const':
    case 'midiCc':
    case 'oscIn':
      return 0
    case 'threshold':
    case 'curve':
    case 'map':
    case 'target':
      return 1
    case 'envelope':
      // value + optional attack/release override slots — see EnvelopeNode's
      // own comment in patchgraph/types.ts. Always shown (even before
      // wired) so there's somewhere to drop a wire for the live-knob case.
      return 3
    case 'logic':
      return node.logicOp === 'not' ? 1 : null
    case 'combine':
      return null
  }
}

// Per-slot label for a fixed-arity node whose slots aren't interchangeable
// (currently just envelope) — shown in the input nub's tooltip so "drag a
// wire here" actually says what that wire would do. Every other fixed-arity
// kind has exactly one, unambiguous slot and needs no label; variable-arity
// nodes (combine/logic) don't have positionally-meaningful slots at all.
export function inputSlotLabel(node: DraftNode, index: number): string | null {
  if (node.kind !== 'envelope') return null
  return ['value', 'attack override (optional)', 'release override (optional)'][index] ?? null
}

export function hasOutput(node: DraftNode): boolean {
  return node.kind !== 'target'
}
