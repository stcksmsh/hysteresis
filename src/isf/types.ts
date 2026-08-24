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

export type IsfSupportedInputType = 'float' | 'bool' | 'long' | 'color' | 'point2D' | 'hysteresisSignal' | 'resource'
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

// The other real Hysteresis-format extension beyond hysteresisSignal
// (HYSTERESIS_VERSION 1): a live, non-scalar system resource — today just
// `scope` (SignalBus.scope's raw waveform Float32Array). Deliberately NOT
// a routable patch-graph target the way every other input type is — the
// patch graph is scalar-in/scalar-out throughout (patchgraph/types.ts's
// own module comment), so a resource is bound automatically by name
// instead, the same category TIME/RENDERSIZE already are, just opt-in per
// shader. `resource` is validated against a small explicit list
// (parse-isf.ts's KNOWN_RESOURCES) the same way hysteresisSignal's
// `signal` is validated against SIGNAL_TAGS.
export interface IsfResourceInput {
  type: 'resource'
  name: string
  label?: string
  resource: string
}

export type IsfInput = IsfFloatInput | IsfBoolInput | IsfLongInput | IsfColorInput | IsfPoint2DInput | IsfHysteresisSignalInput | IsfResourceInput

// HYSTERESIS_VERSION 1's real (scoped) multi-pass support: a pass is typed
// by KIND. 'fullscreen' is stock ISF's existing single-draw model — the
// shared `IsfDocument.body` GLSL, unchanged. 'lineTrace' is this format's
// own addition: draws an open polyline from a named `resource` input using
// the same cheap GPU-instanced-quad technique the built-in Julia scene's
// oscilloscope beam already uses (real hardware line rasterization, NOT a
// per-pixel fragment-shader loop over samples — that was costed out at
// ~2 billion segment evals/1080p-frame and rejected). A lineTrace pass has
// no shader-author GLSL body at all; it's structural, driven by the
// runtime's own beam vertex/fragment shaders.
export type HysteresisPassKind = 'fullscreen' | 'lineTrace'

export interface IsfFullscreenPass {
  kind: 'fullscreen'
  // '' = the scene's real output framebuffer (what every existing
  // single-pass shader already renders to). A non-empty name makes this
  // pass's result available to LATER passes as `uniform sampler2D <target>`
  // — not used yet (no motivating shader needs more than one fullscreen
  // pass), but the shape supports it without a breaking change later.
  target: string
}

export interface IsfLineTracePass {
  kind: 'lineTrace'
  // Always non-empty and unique among a document's passes — this is what
  // becomes the `uniform sampler2D <target>` a later fullscreen pass reads
  // to composite the beam however its own GLSL wants.
  target: string
  // The NAME of a declared `resource` input supplying this pass's points.
  points: string
  // Optional NAME of a declared float/hysteresisSignal input controlling
  // line half-width; omitted = the runtime's own default width.
  width?: string
}

export type IsfPass = IsfFullscreenPass | IsfLineTracePass

export interface IsfDocument {
  description?: string
  credit?: string
  categories: string[]
  inputs: IsfInput[]
  // undefined = a plain stock-ISF-compatible file, exactly today's
  // behavior. Only version 1 (this format's real multi-pass/resource
  // extension) is currently recognized — parse-isf.ts rejects anything
  // else clearly rather than guessing at unknown future features.
  hysteresisVersion?: number
  // Always at least one entry. A document with no HYSTERESIS_VERSION/
  // PASSES gets the implicit `[{ kind: 'fullscreen', target: '' }]` —
  // every existing single-pass shader's real, unchanged shape.
  passes: IsfPass[]
  // The GLSL source AFTER the JSON header comment — untranslated, still
  // written against ISF's built-ins (isf_FragNormCoord, RENDERSIZE, TIME,
  // gl_FragColor, texture2D, ...), not valid GLSL ES 300 on its own. See
  // translate-isf-glsl.ts. Shared by every 'fullscreen' pass (stock ISF's
  // real PASSINDEX-branching model) — 'lineTrace' passes don't use it.
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
