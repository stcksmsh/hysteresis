import type { CurveKind, PatchGraphNode } from './types'

function clamp01(v: number): number {
  return Math.max(0, Math.min(1, v))
}

function applyCurve(kind: CurveKind, v: number): number {
  switch (kind) {
    case 'linear':
      return v
    case 'exp':
      return Math.sign(v) * v * v
    case 'log':
      return Math.sign(v) * Math.log1p(Math.abs(v) * (Math.E - 1))
    case 'smoothstep': {
      const t = clamp01(v)
      return t * t * (3 - 2 * t)
    }
    default:
      return v
  }
}

// Per-node persistent state the two stateful node kinds need across frames
// (everything else is a pure function of its inputs this frame). Owned by
// PatchGraphEvaluator, one instance per node id, never shared across graphs.
export interface ThresholdState {
  active: boolean
}
export interface EnvelopeState {
  value: number
}

// Evaluates exactly one node's output for this frame, given its already-
// resolved input values (the evaluator guarantees inputs are computed
// before the node that reads them — see topo-sort.ts). Pure except for the
// two state objects, which the caller owns and passes in by reference.
export function evaluateNode(
  node: PatchGraphNode,
  inputValues: number[],
  dt: number,
  thresholdState: ThresholdState,
  envelopeState: EnvelopeState,
): number {
  switch (node.kind) {
    case 'signal':
      // The evaluator resolves signal nodes directly from the bus before
      // calling this function (see PatchGraphEvaluator.evaluate) — signal
      // nodes never actually reach here with real inputValues, but a
      // well-typed switch still needs a case.
      return inputValues[0] ?? 0
    case 'const':
      return node.value
    case 'threshold': {
      const v = inputValues[0] ?? 0
      const releasePoint = node.cut - (node.hysteresis ?? 0)
      if (thresholdState.active) {
        if (v < releasePoint) thresholdState.active = false
      } else {
        if (v >= node.cut) thresholdState.active = true
      }
      return thresholdState.active ? 1 : 0
    }
    case 'envelope': {
      const target = inputValues[0] ?? 0
      const tc = target > envelopeState.value ? node.attackSec : node.releaseSec
      // Same discretized-RC form as the screen side's DtSmoother — the two
      // are independently implemented (see this module's header comment)
      // but there's exactly one sane way to do a frame-rate-independent
      // attack/release, so they end up numerically identical on purpose.
      const alpha = tc > 0 ? 1 - Math.exp(-dt / tc) : 1
      envelopeState.value += (target - envelopeState.value) * alpha
      return envelopeState.value
    }
    case 'logic': {
      if (node.op === 'not') return 1 - clamp01(inputValues[0] ?? 0)
      if (node.op === 'and') return inputValues.length ? Math.min(...inputValues.map(clamp01)) : 0
      return inputValues.length ? Math.max(...inputValues.map(clamp01)) : 0
    }
    case 'combine': {
      if (!inputValues.length) return 0
      switch (node.op) {
        case 'add':
          return inputValues.reduce((a, b) => a + b, 0)
        case 'multiply':
          return inputValues.reduce((a, b) => a * b, 1)
        case 'max':
          return Math.max(...inputValues)
        case 'min':
          return Math.min(...inputValues)
      }
      break
    }
    case 'curve':
      return applyCurve(node.curve, inputValues[0] ?? 0)
    case 'map': {
      const [inLo, inHi] = node.inRange
      const [outLo, outHi] = node.outRange
      const v = inputValues[0] ?? 0
      const t = inHi === inLo ? 0 : (v - inLo) / (inHi - inLo)
      let out = outLo + t * (outHi - outLo)
      if (node.clamp) {
        const lo = Math.min(outLo, outHi)
        const hi = Math.max(outLo, outHi)
        out = Math.min(hi, Math.max(lo, out))
      }
      return out
    }
    case 'target':
      return inputValues[0] ?? 0
  }
}
