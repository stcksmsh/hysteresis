import {
  IsfParseError,
  IsfUnsupportedFeatureError,
  type IsfDocument,
  type IsfInput,
  type IsfPass,
  type IsfUnsupportedInputType,
} from './types'
import { SIGNAL_TAGS } from '../render/conductor/types'

const SUPPORTED_TYPES = new Set(['float', 'bool', 'long', 'color', 'point2D', 'hysteresisSignal', 'resource'])
const UNSUPPORTED_TYPES: readonly IsfUnsupportedInputType[] = ['image', 'audio', 'audioFFT', 'event']

// HYSTERESIS_VERSION 1's real (scoped) multi-pass/resource extension — see
// types.ts's header comments on IsfPass/IsfResourceInput for the design.
const CURRENT_HYSTERESIS_VERSION = 1
// The only non-scalar live signal that actually exists today
// (SignalBus.scope — see IsfResourceInput's comment). Grown one real entry
// at a time, same posture as isf-targets.ts's BIPOLAR_SIGNALS lookup:
// explicit and small, not a general solve for a case that doesn't exist
// yet.
const KNOWN_RESOURCES = new Set(['scope'])

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

  // HYSTERESIS_VERSION: the real future-proofing mechanism (see types.ts's
  // IsfDocument comment) — an unrecognized version is rejected clearly
  // rather than parsed optimistically, since a newer file may use features
  // this parser genuinely can't understand. Absent entirely = a plain
  // stock-ISF-compatible file, zero behavior change from before this
  // extension existed.
  let hysteresisVersion: number | undefined
  if (header.HYSTERESIS_VERSION !== undefined) {
    if (typeof header.HYSTERESIS_VERSION !== 'number' || header.HYSTERESIS_VERSION !== CURRENT_HYSTERESIS_VERSION) {
      throw new IsfUnsupportedFeatureError(
        `HYSTERESIS_VERSION ${JSON.stringify(header.HYSTERESIS_VERSION)} is not supported by this parser — only version ${CURRENT_HYSTERESIS_VERSION} is known.`,
      )
    }
    hysteresisVersion = header.HYSTERESIS_VERSION
  }

  const passesRaw = header.PASSES
  if (Array.isArray(passesRaw) && passesRaw.some((p) => p && typeof p === 'object' && (p as Record<string, unknown>).PERSISTENT)) {
    throw new IsfUnsupportedFeatureError('PERSISTENT pass buffers are not supported yet — this shader needs its own frame memory beyond a single fullscreen draw.')
  }
  let passes: IsfPass[]
  if (Array.isArray(passesRaw) && passesRaw.length > 1) {
    // Real Hysteresis-format multi-pass (KIND-typed, e.g. lineTrace) needs
    // HYSTERESIS_VERSION declared — a stock ISF ecosystem shader declaring
    // >1 PASSES without it is still the same "not supported" case as
    // before this extension existed, same message as before for that
    // exact scenario (an ecosystem shader genuinely using ISF's own
    // PASSINDEX-branching multi-pass model, which this parser still
    // doesn't implement).
    if (hysteresisVersion === undefined) {
      throw new IsfUnsupportedFeatureError(
        `Multi-pass ISF shaders are not supported yet (this shader declares ${passesRaw.length} PASSES) — only single-pass generators/filters work, unless HYSTERESIS_VERSION declares real Hysteresis-format multi-pass support.`,
      )
    }
    passes = passesRaw.map((p, i) => parsePass(p, i))
  } else {
    passes = [{ kind: 'fullscreen', target: '' }]
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

  // Cross-validate lineTrace passes against the inputs they actually
  // reference — a POINTS/WIDTH name that doesn't match a declared input is
  // a real authoring bug, caught here rather than silently reading as
  // "resource not found" deep in the render path.
  for (const pass of passes) {
    if (pass.kind !== 'lineTrace') continue
    const pointsInput = inputs.find((i) => i.name === pass.points)
    if (!pointsInput || pointsInput.type !== 'resource') {
      throw new IsfParseError(`PASSES lineTrace pass's POINTS "${pass.points}" does not match any declared TYPE resource input`)
    }
    if (pass.width !== undefined) {
      const widthInput = inputs.find((i) => i.name === pass.width)
      if (!widthInput || (widthInput.type !== 'float' && widthInput.type !== 'hysteresisSignal')) {
        throw new IsfParseError(`PASSES lineTrace pass's WIDTH "${pass.width}" does not match any declared TYPE float/hysteresisSignal input`)
      }
    }
  }

  return {
    description: typeof header.DESCRIPTION === 'string' ? header.DESCRIPTION : undefined,
    credit: typeof header.CREDIT === 'string' ? header.CREDIT : undefined,
    categories: Array.isArray(header.CATEGORIES) ? (header.CATEGORIES as string[]) : [],
    inputs,
    hysteresisVersion,
    passes,
    body,
  }
}

function parsePass(raw: unknown, index: number): IsfPass {
  if (!raw || typeof raw !== 'object') throw new IsfParseError(`PASSES[${index}] is not an object`)
  const p = raw as Record<string, unknown>
  const kind = typeof p.KIND === 'string' ? p.KIND : 'fullscreen'
  const target = typeof p.TARGET === 'string' ? p.TARGET : ''
  if (kind === 'fullscreen') {
    return { kind: 'fullscreen', target }
  }
  if (kind === 'lineTrace') {
    const points = typeof p.POINTS === 'string' ? p.POINTS : ''
    if (!points) throw new IsfParseError(`PASSES[${index}] (lineTrace) is missing POINTS (the NAME of a declared TYPE resource input)`)
    if (!target) throw new IsfParseError(`PASSES[${index}] (lineTrace) is missing TARGET (the name later passes will sample it by)`)
    const width = typeof p.WIDTH === 'string' ? p.WIDTH : undefined
    return { kind: 'lineTrace', target, points, width }
  }
  throw new IsfUnsupportedFeatureError(`PASSES[${index}] has unknown KIND "${kind}" — only "fullscreen"/"lineTrace" are supported.`)
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
    case 'resource': {
      const resource = String(raw.RESOURCE ?? '')
      if (!KNOWN_RESOURCES.has(resource)) {
        const known = [...KNOWN_RESOURCES].join(', ')
        throw new IsfParseError(`ISF input "${name}" declares TYPE resource with an unknown RESOURCE "${resource}" — must be one of: ${known}`)
      }
      return { type: 'resource', name, label, resource }
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
