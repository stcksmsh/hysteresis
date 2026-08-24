// The typed contract between a loaded .hyst shader's optional HYSTERESIS_SCRIPT companion and
// the render worker that hosts it. Kept as plain, structured-clone-safe data (no GL/DOM/Worker
// imports) so it can be built here from a real IsfDocument, sent as-is over postMessage to the
// sandboxed script Worker, and used there (engine-source.ts) to validate/coerce every frame's
// script output BEFORE it's ever handed back to the trusted render-worker side — see that file's
// header comment for why validation has to happen inside the sandbox, not after.

import type { IsfDocument, IsfScriptOutputKind } from '../types'

// Exactly resolvedTargetsToIsfUniforms(doc, resolved)'s own return shape, restricted at the call
// site (IsfScene) to the shader's declared hysteresisSignal (and other patch-routed) inputs — the
// script never sees the raw SignalBus (R2: a VizOutput never touches it directly), only what the
// patch graph already resolved for this frame, same as the shader's own GLSL uniforms get.
export type HysteresisScriptInputs = Record<string, number | boolean | number[]>

export interface HysteresisScriptFrameInput {
  dt: number
  time: number
  // Not a routable/resolved signal (SIGNAL_TAGS explicitly excludes it — see
  // render/conductor/types.ts's own comment on `idle`) — supplied directly the same
  // non-patch-graph way IsfScene already reads params.idle/params.scope off ParamBus.
  idle: boolean
  inputs: HysteresisScriptInputs
}

export interface HysteresisScriptFrameOutput {
  uniforms: Record<string, number | boolean | number[]>
  textures: Record<string, number[]>
}

// What a script's per-frame output is allowed to contain, derived from the loaded document's own
// declared scriptOutput inputs / scriptTexture passes. Plain, JSON-serializable — sent verbatim
// to the script Worker in the initial 'load' message so engine-source.ts's runtime can coerce
// every frame's actual output against it without needing to import types.ts at all.
export interface HysteresisScriptOutputContract {
  uniforms: Record<string, { kind: IsfScriptOutputKind; default: number | boolean | number[] }>
  textures: Record<string, { length: number }>
}

export function buildScriptOutputContract(doc: IsfDocument): HysteresisScriptOutputContract {
  const uniforms: HysteresisScriptOutputContract['uniforms'] = {}
  for (const input of doc.inputs) {
    if (input.type !== 'scriptOutput') continue
    uniforms[input.name] = { kind: input.kind, default: input.default }
  }
  const textures: HysteresisScriptOutputContract['textures'] = {}
  for (const pass of doc.passes) {
    if (pass.kind !== 'scriptTexture') continue
    textures[pass.source] = { length: pass.length }
  }
  return { uniforms, textures }
}
