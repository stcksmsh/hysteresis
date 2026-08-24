import { describe, it, expect } from 'vitest'
import engineSourceRaw from '../../src/render/worker/scenes/isf/script-runtime/engine-source.js?raw'

// Exercises the ACTUAL engine text that gets Blob-concatenated into the sandboxed script Worker
// (script-host.ts) — evaluated here the same way (a real `Function` construction over the raw
// source), not a parallel reimplementation, so these tests prove the exact code that runs in
// production, not a stand-in for it.
function loadRuntimeFactory(): (
  source: string,
  contract: { uniforms: Record<string, { kind: string; default: unknown }>; textures: Record<string, { length: number }> },
) => { update(frame: { dt: number; time: number; idle: boolean; inputs: unknown }): { uniforms: Record<string, unknown>; textures: Record<string, number[]> } } {
  const factory = new Function(`${engineSourceRaw}\nreturn createHysteresisScriptRuntime;`)
  return factory()
}

describe('HYSTERESIS_SCRIPT pure runtime (engine-source.ts)', () => {
  it('a script defining update() runs and its closure state persists across frames', () => {
    const createHysteresisScriptRuntime = loadRuntimeFactory()
    const runtime = createHysteresisScriptRuntime(
      `
      let count = 0
      function update(dt, inputs, idle, time) {
        count += 1
        return { uniforms: { calls: count }, textures: {} }
      }
      `,
      { uniforms: { calls: { kind: 'float', default: -1 } }, textures: {} },
    )
    const a = runtime.update({ dt: 0.016, time: 0, idle: false, inputs: {} })
    const b = runtime.update({ dt: 0.016, time: 0.016, idle: false, inputs: {} })
    const c = runtime.update({ dt: 0.016, time: 0.032, idle: false, inputs: {} })
    expect([a.uniforms.calls, b.uniforms.calls, c.uniforms.calls]).toEqual([1, 2, 3])
  })

  it('throws a clear load-time error when the source never defines update()', () => {
    const createHysteresisScriptRuntime = loadRuntimeFactory()
    expect(() => createHysteresisScriptRuntime('const x = 1', { uniforms: {}, textures: {} })).toThrow(/must define an update/)
  })

  it('falls back to a declared default when the script omits/malforms a uniform', () => {
    const createHysteresisScriptRuntime = loadRuntimeFactory()
    const runtime = createHysteresisScriptRuntime('function update() { return { uniforms: { zoom: "not a number" } }; }', {
      uniforms: { zoom: { kind: 'float', default: 2.5 }, c: { kind: 'point2D', default: [0.1, 0.2] } },
      textures: {},
    })
    const out = runtime.update({ dt: 0.016, time: 0, idle: false, inputs: {} })
    expect(out.uniforms.zoom).toBe(2.5) // malformed (string, not number) -> falls back
    expect(out.uniforms.c).toEqual([0.1, 0.2]) // never supplied at all -> falls back
  })

  it('falls back to a declared default for a non-finite (NaN/Infinity) float output', () => {
    const createHysteresisScriptRuntime = loadRuntimeFactory()
    const runtime = createHysteresisScriptRuntime('function update() { return { uniforms: { zoom: 1/0 } }; }', {
      uniforms: { zoom: { kind: 'float', default: 2.5 } },
      textures: {},
    })
    expect(runtime.update({ dt: 0.016, time: 0, idle: false, inputs: {} }).uniforms.zoom).toBe(2.5)
  })

  it('pads a too-short texture array with the last finite value, matching the declared length*2 shape', () => {
    const createHysteresisScriptRuntime = loadRuntimeFactory()
    const runtime = createHysteresisScriptRuntime('function update() { return { textures: { refOrbit: [1, 2, 3] } }; }', {
      uniforms: {},
      textures: { refOrbit: { length: 3 } }, // 3 texels -> 6 floats
    })
    const out = runtime.update({ dt: 0.016, time: 0, idle: false, inputs: {} })
    expect(out.textures.refOrbit).toHaveLength(6)
    expect(out.textures.refOrbit).toEqual([1, 2, 3, 3, 3, 3])
  })

  it('sanitizes a diverging (non-finite) texture value by holding the last finite entry', () => {
    const createHysteresisScriptRuntime = loadRuntimeFactory()
    const runtime = createHysteresisScriptRuntime('function update() { return { textures: { refOrbit: [1, 2, NaN, Infinity, 5] } }; }', {
      uniforms: {},
      textures: { refOrbit: { length: 3 } }, // 6 floats
    })
    const out = runtime.update({ dt: 0.016, time: 0, idle: false, inputs: {} })
    expect(out.textures.refOrbit).toEqual([1, 2, 2, 2, 5, 5])
  })

  it('a script that throws inside update() propagates the throw synchronously (caller decides how to react)', () => {
    const createHysteresisScriptRuntime = loadRuntimeFactory()
    const runtime = createHysteresisScriptRuntime('function update() { throw new Error("boom"); }', { uniforms: {}, textures: {} })
    expect(() => runtime.update({ dt: 0.016, time: 0, idle: false, inputs: {} })).toThrow(/boom/)
  })
})
