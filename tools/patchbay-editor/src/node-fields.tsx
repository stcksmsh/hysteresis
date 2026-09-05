import { SIGNAL_CATALOG } from '../../../src/render/conductor/patchbay/editor/catalog'
import { applyCurve } from '../../../src/render/conductor/patchgraph/evaluate-node'
import type { PatchTargetDecl, CurveKind } from '../../../src/render/conductor/patchgraph/types'
import type { DraftNode } from './graph-draft'
import { Select } from './ui/Select'
import { NumberInput } from './ui/NumberInput'
import { TextInput } from './ui/TextInput'
import { Toggle } from './ui/Toggle'
import { Badge } from './ui/Badge'

// Shared between the node-graph canvas's per-node inspector and (formerly)
// the flat form editor — kept as its own module so neither has to duplicate
// the field set for all 9 node kinds. Pure display/edit of one node's
// params; wiring (inputs) is the canvas's job now, not this component's.
export const NODE_KINDS: DraftNode['kind'][] = ['signal', 'const', 'midiCc', 'oscIn', 'threshold', 'envelope', 'logic', 'combine', 'curve', 'map', 'target']
export const CURVE_KINDS: CurveKind[] = ['linear', 'exp', 'log', 'smoothstep']

// A tiny inline sparkline of the actual curve shape, using the real
// applyCurve() math (evaluate-node.ts) so it can never drift from what
// actually runs — before this, `curve` was pure invisible text ("exp" as a
// word) with no visual cue for what the shape looks like at all.
const CURVE_PREVIEW_SAMPLES = 24
function CurvePreview({ curve }: { curve: CurveKind }) {
  const w = 64
  const h = 28
  const points: string[] = []
  for (let i = 0; i <= CURVE_PREVIEW_SAMPLES; i++) {
    const t = (i / CURVE_PREVIEW_SAMPLES) * 2 - 1 // -1..1, since curves are sign-preserving/bipolar-aware
    const v = applyCurve(curve, t)
    const x = (i / CURVE_PREVIEW_SAMPLES) * w
    const y = h / 2 - (v / 2) * h
    points.push(`${x.toFixed(1)},${Math.max(0, Math.min(h, y)).toFixed(1)}`)
  }
  return (
    <svg width={w} height={h} className="curve-preview" viewBox={`0 0 ${w} ${h}`}>
      <line x1={0} y1={h / 2} x2={w} y2={h / 2} className="curve-preview-axis" />
      <polyline points={points.join(' ')} className="curve-preview-line" />
    </svg>
  )
}

export function NodeFields({ node, targets, onPatch }: { node: DraftNode; targets: PatchTargetDecl[]; onPatch: (id: string, fields: Partial<DraftNode>) => void }) {
  switch (node.kind) {
    case 'signal':
      return (
        <div className="node-fields">
          signal:
          <Select uiSize="sm" value={node.signal} onChange={(e) => onPatch(node.id, { signal: e.target.value })}>
            {SIGNAL_CATALOG.filter((s) => s.tag !== 'pass-through').map((s) => (
              <option key={s.name} value={s.name}>
                {s.name}
              </option>
            ))}
          </Select>
        </div>
      )
    case 'const':
      return (
        <div className="node-fields">
          value:
          <NumberInput step={0.05} width={70} value={node.value ?? 0} onChange={(v) => onPatch(node.id, { value: v })} />
        </div>
      )
    case 'midiCc':
      return (
        <div className="node-fields">
          CC key ("channel:controller"):
          <TextInput placeholder="0:1" value={node.ccKey ?? ''} onChange={(e) => onPatch(node.id, { ccKey: e.target.value })} style={{ width: 80 }} />
        </div>
      )
    case 'oscIn':
      return (
        <div className="node-fields">
          OSC address:
          <TextInput placeholder="/1/fader1" value={node.address ?? ''} onChange={(e) => onPatch(node.id, { address: e.target.value })} style={{ width: 120 }} />
        </div>
      )
    case 'threshold':
      return (
        <div className="node-fields">
          cut:
          <NumberInput step={0.05} width={60} value={node.cut ?? 0.5} onChange={(v) => onPatch(node.id, { cut: v })} />
          hysteresis:
          <NumberInput step={0.01} width={60} min={0} value={node.hysteresis ?? 0} onChange={(v) => onPatch(node.id, { hysteresis: v })} />
        </div>
      )
    case 'envelope': {
      const atkLive = Boolean(node.inputs[1])
      const relLive = Boolean(node.inputs[2])
      return (
        <div className="node-fields">
          attackSec:
          <NumberInput step={0.05} width={60} min={0} disabled={atkLive} value={node.attackSec ?? 0.1} onChange={(v) => onPatch(node.id, { attackSec: v })} />
          {atkLive && <Badge tone="accent">live</Badge>}
          releaseSec:
          <NumberInput step={0.05} width={60} min={0} disabled={relLive} value={node.releaseSec ?? 0.5} onChange={(v) => onPatch(node.id, { releaseSec: v })} />
          {relLive && <Badge tone="accent">live</Badge>}
        </div>
      )
    }
    case 'logic':
      return (
        <div className="node-fields">
          op:
          <Select uiSize="sm" value={node.logicOp} onChange={(e) => onPatch(node.id, { logicOp: e.target.value as DraftNode['logicOp'] })}>
            <option value="and">and (min)</option>
            <option value="or">or (max)</option>
            <option value="not">not (1-x, needs exactly 1 input)</option>
          </Select>
        </div>
      )
    case 'combine':
      return (
        <div className="node-fields">
          op:
          <Select uiSize="sm" value={node.combineOp} onChange={(e) => onPatch(node.id, { combineOp: e.target.value as DraftNode['combineOp'] })}>
            <option value="add">add</option>
            <option value="multiply">multiply</option>
            <option value="max">max</option>
            <option value="min">min</option>
          </Select>
        </div>
      )
    case 'curve': {
      const curve = node.curve ?? 'linear'
      return (
        <div className="node-fields">
          curve:
          <Select uiSize="sm" value={curve} onChange={(e) => onPatch(node.id, { curve: e.target.value as CurveKind })}>
            {CURVE_KINDS.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
          <CurvePreview curve={curve} />
        </div>
      )
    }
    case 'map':
      return (
        <div className="node-fields" style={{ flexWrap: 'wrap' }}>
          in:
          <NumberInput step={0.05} width={55} value={node.inRange?.[0] ?? 0} onChange={(v) => onPatch(node.id, { inRange: [v, node.inRange?.[1] ?? 1] })} />
          –
          <NumberInput step={0.05} width={55} value={node.inRange?.[1] ?? 1} onChange={(v) => onPatch(node.id, { inRange: [node.inRange?.[0] ?? 0, v] })} />
          out:
          <NumberInput step={0.05} width={55} value={node.outRange?.[0] ?? 0} onChange={(v) => onPatch(node.id, { outRange: [v, node.outRange?.[1] ?? 1] })} />
          –
          <NumberInput step={0.05} width={55} value={node.outRange?.[1] ?? 1} onChange={(v) => onPatch(node.id, { outRange: [node.outRange?.[0] ?? 0, v] })} />
          <Toggle checked={node.clamp ?? true} onChange={(v) => onPatch(node.id, { clamp: v })} label="clamp" />
        </div>
      )
    case 'target':
      return (
        <div className="node-fields">
          target:
          <Select uiSize="sm" value={node.targetId} onChange={(e) => onPatch(node.id, { targetId: e.target.value })}>
            <option value="">(choose a fixture channel)</option>
            {targets.map((t) => (
              <option key={t.id} value={t.id}>
                {t.label ?? t.id}
              </option>
            ))}
          </Select>
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
