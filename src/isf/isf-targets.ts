import type { IsfDocument, IsfInput } from './types'
import type { TargetDecl, TimescaleTag } from '../render/conductor/types'

// The few bus signals that are bipolar (-1..1) rather than the common
// unipolar (0..1) case — see SignalBus's own field comments in
// render/conductor/types.ts. A small, explicit lookup rather than a general
// solve: adding a new bipolar signal to the bus means adding it here too.
const BIPOLAR_SIGNALS = new Set(['bandTilt', 'pan'])

// TargetDecl (mutable acceptsTags/range) rather than PatchTargetDecl
// (readonly): this is the shape ScreenOutput.targets itself needs
// (TargetDecl[]) — and per patchgraph/types.ts's own note, a plain
// TargetDecl is already structurally assignable wherever a PatchTargetDecl
// is expected (the editor's merged target catalog), so one shape serves
// both call sites. `label` is TargetDecl's one legitimate extension here,
// same as PatchTargetDecl already declares it.
type IsfTargetDecl = TargetDecl & { label?: string }

// ISF inputs accept any signal shape — there's no physical safety concern
// (SINTEZA_SIGNAL_BUS.md §5.3) the way a servo/LED target has, so every
// timescale tag is accepted, same as the screen's own targets
// (screen-targets.ts).
const ALL_TAGS: TimescaleTag[] = ['transient', 'beat', 'bar', 'section', 'continuous']

// The prefix every generated target id carries, so a loaded ISF shader's
// inputs can never collide with SCREEN_TARGETS or a fixture's channel ids
// in the merged catalog the patchbay editor builds (App.tsx's
// mergedCatalog).
export const ISF_TARGET_PREFIX = 'isf.'

// Turns a parsed ISF document's declared INPUTS into real, routable patch
// targets — this IS the "auto-generate patchbay node UI from ISF's JSON
// header" backlog item (master-prompt.md §6): a color/point2D input
// expands into its scalar components since the patch graph's node model is
// scalar-in/scalar-out throughout (patchgraph/types.ts's module comment).
export function isfInputsToTargets(doc: IsfDocument): IsfTargetDecl[] {
  return doc.inputs.flatMap((input): IsfTargetDecl[] => {
    switch (input.type) {
      case 'float':
        return [target(input.name, input.label, input.default, [input.min, input.max])]
      case 'bool':
        return [target(input.name, input.label, input.default ? 1 : 0, [0, 1])]
      case 'long': {
        const maxIndex = Math.max(0, input.values.length - 1)
        const defaultIndex = Math.max(0, input.values.indexOf(input.default))
        return [target(input.name, input.label, defaultIndex, [0, maxIndex])]
      }
      case 'color':
        return (['r', 'g', 'b', 'a'] as const).map((channel, i) =>
          target(`${input.name}.${channel}`, labelFor(input, channel), input.default[i], [0, 1]),
        )
      case 'point2D':
        return (['x', 'y'] as const).map((axis, i) =>
          target(`${input.name}.${axis}`, labelFor(input, axis), input.default[i], [input.min[i], input.max[i]]),
        )
      case 'hysteresisSignal': {
        const range: [number, number] = BIPOLAR_SIGNALS.has(input.signal) ? [-1, 1] : [0, 1]
        return [target(input.name, input.label, input.default, range)]
      }
      case 'resource':
        // Deliberately NOT a routable target — see IsfResourceInput's own
        // comment in types.ts. A resource is bound automatically by name
        // (IsfScene), never appears in the patch graph's target catalog.
        return []
    }
  })

  function target(name: string, label: string | undefined, defaultValue: number, range: readonly [number, number]): IsfTargetDecl {
    return { id: `${ISF_TARGET_PREFIX}${name}`, label: label ?? name, acceptsTags: ALL_TAGS, defaultValue, range: [range[0], range[1]] }
  }
  function labelFor(input: IsfInput, suffix: string): string {
    return `${input.label ?? input.name} (${suffix})`
  }
}

// The inverse direction: given a frame's resolved target values (a flat
// `{ [targetId]: number }`, same shape resolveScreenTargets produces for
// the screen), reassembles the typed uniform values IsfScene needs to bind
// (a color input is one vec4 uniform, not four separate ones) — the patch
// graph itself never sees anything but scalars, so this is where the
// component targets above get put back together.
export function resolvedTargetsToIsfUniforms(doc: IsfDocument, resolved: Record<string, unknown>): Record<string, number | boolean | number[]> {
  const uniforms: Record<string, number | boolean | number[]> = {}
  const read = (name: string) => {
    const v = resolved[`${ISF_TARGET_PREFIX}${name}`]
    return typeof v === 'number' ? v : 0
  }

  for (const input of doc.inputs) {
    switch (input.type) {
      case 'float':
        uniforms[input.name] = read(input.name)
        break
      case 'bool':
        uniforms[input.name] = read(input.name) >= 0.5
        break
      case 'long':
        uniforms[input.name] = input.values[Math.round(read(input.name))] ?? input.default
        break
      case 'color':
        uniforms[input.name] = [read(`${input.name}.r`), read(`${input.name}.g`), read(`${input.name}.b`), read(`${input.name}.a`)]
        break
      case 'point2D':
        uniforms[input.name] = [read(`${input.name}.x`), read(`${input.name}.y`)]
        break
      case 'hysteresisSignal':
        uniforms[input.name] = read(input.name)
        break
      case 'resource':
        // Not a scalar uniform at all — IsfScene binds it directly from
        // ParamBus (e.g. `scope`), not through this resolved-targets path.
        break
    }
  }
  return uniforms
}
