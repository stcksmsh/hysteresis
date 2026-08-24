// The nested script Worker's own bootstrap — plain JavaScript, same reason as engine-source.js's
// own header comment (Vite's `?raw` doesn't transpile, so this text has to already be valid JS).
// `createHysteresisScriptRuntime` referenced below is defined in engine-source.js's text, which
// script-host.ts always places BEFORE this file's text in the concatenated Blob — both run in the
// same top-level scope of one classic (non-module) script, no import needed between them.
//
// The shader's own untrusted HYSTERESIS_SCRIPT source is never part of the Blob's static text —
// it arrives as plain string DATA in the first 'load' message and is only ever `Function`-eval'd
// at runtime (inside engine-source.js's createHysteresisScriptRuntime), so loading a shader never
// changes what code this Worker's own Blob was built from.

let runtime = null

self.onmessage = (ev) => {
  const msg = ev.data

  if (msg.kind === 'load') {
    try {
      runtime = createHysteresisScriptRuntime(msg.source, msg.contract)
      self.postMessage({ kind: 'loaded' })
    } catch (err) {
      self.postMessage({ kind: 'loadError', message: err instanceof Error ? err.message : String(err) })
    }
    return
  }

  if (msg.kind === 'update') {
    if (!runtime) return // 'load' never succeeded — host already has a loadError, nothing to do
    try {
      const out = runtime.update({ dt: msg.dt, time: msg.time, idle: msg.idle, inputs: msg.inputs })
      self.postMessage({ kind: 'result', seq: msg.seq, uniforms: out.uniforms, textures: out.textures })
    } catch (err) {
      // A throw inside update() does NOT kill this Worker or stop it receiving future messages —
      // replying with an explicit error here (rather than staying silent) is what lets the host
      // detect this as an immediate fault instead of waiting out a hang timeout that a
      // responsive-but-crashing script would never actually trip.
      self.postMessage({ kind: 'error', seq: msg.seq, message: err instanceof Error ? err.message : String(err) })
    }
  }
}
