import {
  IsfParseError,
  IsfUnsupportedFeatureError,
  type IsfDocument,
  type IsfInput,
  type IsfUnsupportedInputType,
} from './types'
import { SIGNAL_TAGS } from '../render/conductor/types'

const SUPPORTED_TYPES = new Set(['float', 'bool', 'long', 'color', 'point2D', 'hysteresisSignal'])
const UNSUPPORTED_TYPES: readonly IsfUnsupportedInputType[] = ['image', 'audio', 'audioFFT', 'event']

// Parses the real ISF file format: a `/*{ ... }*/` JSON header immediately
// followed by GLSL. Only single-pass, no-imported-image, no-audio-input
// shaders are accepted — see IsfUnsupportedInputType's comment for why.
// This is a deliberately real subset (most pure-generator ISF shaders —
// plasma/kaleidoscope/noise-field style effects with only float/bool/long/
// color/point2D controls — already fit it), not a stub: anything it accepts
// renders for real, and anything it can't handle is rejected with a
// specific reason instead of silently producing garbage.
export function parseIsf(source: string): IsfDocument {
  const start = source.indexOf('/*')
  if (start === -1) throw new IsfParseError('No ISF header comment found (expected a leading /*{ ... }*/ block)')
  const end = source.indexOf('*/', start + 2)
  if (end === -1) throw new IsfParseError('ISF header comment is not closed (missing */)')

  const headerText = source.slice(start + 2, end).trim()
  const body = source.slice(end + 2)

  let header: Record<string, unknown>
  try {
    header = JSON.parse(headerText) as Record<string, unknown>
  } catch (err) {
    throw new IsfParseError(`ISF header is not valid JSON: ${err instanceof Error ? err.message : String(err)}`)
  }

  const passes = header.PASSES
  if (Array.isArray(passes) && passes.length > 1) {
    throw new IsfUnsupportedFeatureError(
      `Multi-pass ISF shaders are not supported yet (this shader declares ${passes.length} PASSES) — only single-pass generators/filters work.`,
    )
  }
  if (Array.isArray(passes) && passes.some((p) => p && typeof p === 'object' && (p as Record<string, unknown>).PERSISTENT)) {
    throw new IsfUnsupportedFeatureError('PERSISTENT pass buffers are not supported yet — this shader needs its own frame memory beyond a single fullscreen draw.')
  }
  if (header.IMPORTED && typeof header.IMPORTED === 'object' && Object.keys(header.IMPORTED as object).length > 0) {
    throw new IsfUnsupportedFeatureError('IMPORTED images are not supported yet — this shader needs an asset it can\'t bring with it.')
  }
  // Reserved, not implemented (AGENTS.md's "Hysteresis format" Phase 1): a shader MAY declare a
  // HYSTERESIS_SCRIPT (per-frame JS state — orbit tracking, target-seeking, anything a single
  // GLSL fragment shader can't express, per ISF's own "shader + JSON header" model having no
  // concept of stateful JS at all). Rejecting it clearly now — rather than silently ignoring a
  // key the shader may depend on for correct rendering — means a shader authored against it
  // fails loudly instead of mis-rendering, and the file format's shape is already stable for
  // when the real execution engine (Phase 4) lands.
  if (typeof header.HYSTERESIS_SCRIPT === 'string' && header.HYSTERESIS_SCRIPT.length > 0) {
    throw new IsfUnsupportedFeatureError(
      'HYSTERESIS_SCRIPT is reserved but not executed yet — stateful per-frame JS scripts are not supported until the state-script engine lands.',
    )
  }

  const rawInputs = Array.isArray(header.INPUTS) ? (header.INPUTS as Record<string, unknown>[]) : []
  const unsupported = rawInputs.filter((i) => UNSUPPORTED_TYPES.includes(i.TYPE as IsfUnsupportedInputType))
  if (unsupported.length > 0) {
    const names = unsupported.map((i) => `${String(i.NAME)} (${String(i.TYPE)})`).join(', ')
    throw new IsfUnsupportedFeatureError(`Unsupported ISF input type(s): ${names} — only float/bool/long/color/point2D/hysteresisSignal inputs are supported.`)
  }

  const inputs: IsfInput[] = rawInputs
    .filter((i) => SUPPORTED_TYPES.has(i.TYPE as string))
    .map((i) => parseInput(i))

  return {
    description: typeof header.DESCRIPTION === 'string' ? header.DESCRIPTION : undefined,
    credit: typeof header.CREDIT === 'string' ? header.CREDIT : undefined,
    categories: Array.isArray(header.CATEGORIES) ? (header.CATEGORIES as string[]) : [],
    inputs,
    body,
  }
}

function parseInput(raw: Record<string, unknown>): IsfInput {
  const name = String(raw.NAME ?? '')
  if (!name) throw new IsfParseError('An ISF input is missing NAME')
  const label = typeof raw.LABEL === 'string' ? raw.LABEL : undefined

  switch (raw.TYPE) {
    case 'float':
      return {
        type: 'float',
        name,
        label,
        default: numberOr(raw.DEFAULT, 0),
        min: numberOr(raw.MIN, 0),
        max: numberOr(raw.MAX, 1),
      }
    case 'bool':
      return { type: 'bool', name, label, default: raw.DEFAULT === true }
    case 'long': {
      const values = Array.isArray(raw.VALUES) ? (raw.VALUES as number[]) : []
      const labels = Array.isArray(raw.LABELS) ? (raw.LABELS as string[]) : values.map((v) => String(v))
      return { type: 'long', name, label, default: numberOr(raw.DEFAULT, values[0] ?? 0), values, labels }
    }
    case 'color': {
      const d = Array.isArray(raw.DEFAULT) ? (raw.DEFAULT as number[]) : [1, 1, 1, 1]
      return {
        type: 'color',
        name,
        label,
        default: [numberOr(d[0], 1), numberOr(d[1], 1), numberOr(d[2], 1), numberOr(d[3], 1)],
      }
    }
    case 'hysteresisSignal': {
      const signal = String(raw.SIGNAL ?? '')
      if (!(signal in SIGNAL_TAGS)) {
        const known = Object.keys(SIGNAL_TAGS).join(', ')
        throw new IsfParseError(`ISF input "${name}" declares TYPE hysteresisSignal with an unknown SIGNAL "${signal}" — must be one of: ${known}`)
      }
      return { type: 'hysteresisSignal', name, label, signal, default: numberOr(raw.DEFAULT, 0) }
    }
    case 'point2D': {
      const d = Array.isArray(raw.DEFAULT) ? (raw.DEFAULT as number[]) : [0, 0]
      const min = Array.isArray(raw.MIN) ? (raw.MIN as number[]) : [0, 0]
      const max = Array.isArray(raw.MAX) ? (raw.MAX as number[]) : [1, 1]
      return {
        type: 'point2D',
        name,
        label,
        default: [numberOr(d[0], 0), numberOr(d[1], 0)],
        min: [numberOr(min[0], 0), numberOr(min[1], 0)],
        max: [numberOr(max[0], 1), numberOr(max[1], 1)],
      }
    }
    default:
      // Unreachable given the caller's SUPPORTED_TYPES filter — kept as a
      // real throw (not an assertNever) since raw.TYPE is untrusted JSON.
      throw new IsfParseError(`Unknown ISF input type: ${String(raw.TYPE)}`)
  }
}

function numberOr(v: unknown, fallback: number): number {
  return typeof v === 'number' && Number.isFinite(v) ? v : fallback
}
