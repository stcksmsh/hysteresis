// ISF (Interactive Shader Format) types — see https://isf.video/ for the
// spec this implements a real subset of. An ISF file is a GLSL fragment
// shader with a JSON header (a `/*{ ... }*/` comment at the top) declaring
// typed, host-exposed inputs. Hosts auto-generate UI controls from that
// header (master-prompt.md §4.5) — this module is what lets Hysteresis's
// patchbay do the same thing: an ISF input becomes a real PatchTargetDecl a
// user can route any signal into, the same as a built-in screen/fixture
// target.

export type IsfSupportedInputType = 'float' | 'bool' | 'long' | 'color' | 'point2D'
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

export type IsfInput = IsfFloatInput | IsfBoolInput | IsfLongInput | IsfColorInput | IsfPoint2DInput

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
