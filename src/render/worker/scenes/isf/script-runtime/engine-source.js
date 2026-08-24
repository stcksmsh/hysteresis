// The actual HYSTERESIS_SCRIPT execution engine — deliberately plain JavaScript, not TypeScript.
// script-host.ts loads this file's raw source text via `?raw` (Vite's `?raw` returns UNPROCESSED
// file bytes — it does not transpile TypeScript, so a `.ts` file's type annotations would reach
// the runtime as literal, invalid syntax) and concatenates it with script-worker-entry.js's raw
// text into one Blob, run as a classic-script nested Worker — see script-host.ts's own header
// comment for why a Blob rather than a normal Vite-bundled worker entry (the render worker's own
// build is a deliberately single-file, no-code-splitting bundle; a second statically-detected
// worker entry would break that invariant).
//
// This tradeoff — no `tsc` coverage for this one file — is deliberate and documented, not an
// oversight: the whole point is that the exact text here is what actually runs (in the Worker,
// and identically in tests/unit/hysteresis-script-runtime.spec.ts, which loads and evaluates this
// same raw text) — real unit test coverage of the real runtime behavior matters more here than
// static typing of a small, self-contained, thoroughly-tested file.

// Coerces one script-returned uniform value against its declared { kind, default } shape —
// wrong-typed/non-finite values fall back to the declared default rather than reaching the
// trusted render-worker side malformed. Logged once per name so a persistently-wrong script
// doesn't spam the console every frame.
const warnedUniforms = new Set()
function coerceUniform(name, kind, value, fallback) {
  const bad = () => {
    if (!warnedUniforms.has(name)) {
      warnedUniforms.add(name)
      console.warn(`[hysteresis-script] output "${name}" (kind ${kind}) was missing or malformed — using its declared default`)
    }
    return fallback
  }
  switch (kind) {
    case 'float':
      return typeof value === 'number' && Number.isFinite(value) ? value : bad()
    case 'bool':
      return typeof value === 'boolean' ? value : bad()
    case 'point2D': {
      if (!Array.isArray(value) || value.length !== 2) return bad()
      const [x, y] = value
      return typeof x === 'number' && typeof y === 'number' && Number.isFinite(x) && Number.isFinite(y) ? [x, y] : bad()
    }
    case 'color': {
      if (!Array.isArray(value) || value.length !== 4) return bad()
      return value.every((v) => typeof v === 'number' && Number.isFinite(v)) ? value : bad()
    }
    default:
      return bad()
  }
}

// Coerces one script-returned texture array against its declared fixed length (RG32F, one texel
// = 2 floats — see script-host.ts's own comment on why `length` here is already texel-count*2) —
// padded with the last finite value if short, truncated if long, entries sanitized to finite
// numbers (mirrors JuliaScene.ts's own updateReferenceOrbit: once a diverging orbit stops being
// finite, hold the last finite value rather than propagate NaN/Infinity into a texture upload).
const warnedTextures = new Set()
function coerceTexture(name, length, value) {
  const out = new Array(length).fill(0)
  const isArrayLike = Array.isArray(value) || (!!value && typeof value === 'object' && 'length' in value)
  if (!isArrayLike) {
    if (!warnedTextures.has(name)) {
      warnedTextures.add(name)
      console.warn(`[hysteresis-script] texture "${name}" was missing or not array-like — using zeros`)
    }
    return out
  }
  let last = 0
  for (let i = 0; i < length; i++) {
    const v = i < value.length ? value[i] : last
    const finite = typeof v === 'number' && Number.isFinite(v) ? v : last
    out[i] = finite
    last = finite
  }
  return out
}

// Wraps a shader's raw HYSTERESIS_SCRIPT source, which must define (and leave in scope) a real
// `update(dt, inputs, idle, time)` function — its closure is where all per-frame state (springs,
// search targets, zoom accumulators) actually lives, exactly like JuliaScene.ts's private fields
// do for the built-in scene. Throws synchronously if the source is malformed or never defines
// `update` — the caller (script-worker-entry.js, or a test) turns that into a clear load-time
// error rather than a silent no-op scene.
function createHysteresisScriptRuntime(source, contract) {
  const factory = new Function(
    `"use strict";\n${source}\nif (typeof update !== "function") { throw new Error("HYSTERESIS_SCRIPT must define an update(dt, inputs, idle, time) function"); }\nreturn update;`,
  )
  const scriptUpdate = factory()

  return {
    update(frame) {
      const raw = scriptUpdate(frame.dt, frame.inputs, frame.idle, frame.time)
      const rawUniforms = raw && typeof raw === 'object' ? (raw.uniforms ?? {}) : {}
      const rawTextures = raw && typeof raw === 'object' ? (raw.textures ?? {}) : {}

      const uniforms = {}
      for (const [name, decl] of Object.entries(contract.uniforms)) {
        uniforms[name] = coerceUniform(name, decl.kind, rawUniforms[name], decl.default)
      }
      const textures = {}
      for (const [name, decl] of Object.entries(contract.textures)) {
        // RG32F, one texel = 2 floats (R, G) — decl.length is the declared TEXEL count (matches
        // PASSES' LENGTH in the .hyst header and JuliaScene.ts's own REF_ORBIT_LENGTH), so the
        // flat array this script returns (and the one IsfScene later uploads via texSubImage2D)
        // is twice that many floats, interleaved per texel exactly like JuliaScene.ts's
        // refOrbitData (Float32Array(REF_ORBIT_LENGTH * 2)).
        textures[name] = coerceTexture(name, decl.length * 2, rawTextures[name])
      }
      return { uniforms, textures }
    },
  }
}
