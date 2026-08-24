// ISF (Interactive Shader Format) types — see https://isf.video/ for the
// spec this implements a real subset of. An ISF file is a GLSL fragment
// shader with a JSON header (a `/*{ ... }*/` comment at the top) declaring
// typed, host-exposed inputs. Hosts auto-generate UI controls from that
// header (master-prompt.md §4.5) — this module is what lets Hysteresis's
// patchbay do the same thing: an ISF input becomes a real PatchTargetDecl a
// user can route any signal into, the same as a built-in screen/fixture
// target.
//
// `hysteresisSignal` (AGENTS.md's "Hysteresis format" work) is this repo's
// own real extension beyond standard ISF — a shader can declare it wants a
// specific live Feature Engine signal by name (see IsfHysteresisSignalInput
// below) instead of an anonymous float a user has to know to route by hand.

export type IsfSupportedInputType = 'float' | 'bool' | 'long' | 'color' | 'point2D' | 'hysteresisSignal'
// Real ISF features this subset does not implement yet — detected and
// rejected at parse time with a clear message rather than silently
// mis-rendering. `image`/`audio`/`audioFFT` need an import/texture pipeline
// this repo has none of yet; multi-pass + PERSISTENT buffers need a
// ping-pong buffer manager per shader instead of the single fullscreen
// draw this subset does.
export type IsfUnsupportedInputType = 'image' | 'audio' | 'audioFFT' | 'event'

export interface IsfFloatInput {
  type: 'float'
  name: string
  label?: string
  default: number
  min: number
  max: number
}

export interface IsfBoolInput {
  type: 'bool'
  name: string
  label?: string
  default: boolean
}

export interface IsfLongInput {
  type: 'long'
  name: string
  label?: string
  default: number
  values: number[]
  labels: string[]
}

export interface IsfColorInput {
  type: 'color'
  name: string
  label?: string
  default: [number, number, number, number]
}

export interface IsfPoint2DInput {
  type: 'point2D'
  name: string
  label?: string
  default: [number, number]
  min: [number, number]
  max: [number, number]
}

// The Hysteresis format's actual novelty (master-prompt §4.5, AGENTS.md §3.4/§3.7): a shader can
// declare it wants a specific live Feature Engine signal by name, instead of a generic float a
// user has to know to route by hand. `signal` is a `RoutableSignalName`
// (src/render/conductor/types.ts's SIGNAL_TAGS) — validated at parse time in parse-isf.ts, kept
// as a plain string here (not that type) so this module doesn't need to import render/conductor
// just for a type alias. Still becomes a perfectly ordinary routable `TargetDecl` like every
// other ISF input (see isf-targets.ts's header comment) — no bypass of the patch graph, no
// implicit auto-wiring; the only thing this type adds is self-documentation and a
// signal-appropriate default range instead of an arbitrary 0..1.
export interface IsfHysteresisSignalInput {
  type: 'hysteresisSignal'
  name: string
  label?: string
  signal: string
  default: number
}

export type IsfInput = IsfFloatInput | IsfBoolInput | IsfLongInput | IsfColorInput | IsfPoint2DInput | IsfHysteresisSignalInput

export interface IsfDocument {
  description?: string
  credit?: string
  categories: string[]
  inputs: IsfInput[]
  // The GLSL source AFTER the JSON header comment — untranslated, still
  // written against ISF's built-ins (isf_FragNormCoord, RENDERSIZE, TIME,
  // gl_FragColor, texture2D, ...), not valid GLSL ES 300 on its own. See
  // translate-isf-glsl.ts.
  body: string
}

export class IsfParseError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'IsfParseError'
  }
}

export class IsfUnsupportedFeatureError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'IsfUnsupportedFeatureError'
  }
}
