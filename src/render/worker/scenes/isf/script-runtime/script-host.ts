import engineSourceRaw from './engine-source.js?raw'
import scriptWorkerEntryRaw from './script-worker-entry.js?raw'
import type { HysteresisScriptFrameInput, HysteresisScriptFrameOutput, HysteresisScriptOutputContract } from '../../../../../isf/script-runtime/contract'

// Owns the sandboxed nested Worker that actually runs a shader's HYSTERESIS_SCRIPT — the "uptime
// is the primary concern" half of this engine's design. Built from a Blob, not a normal
// Vite-bundled `new Worker(new URL(...))` entry: the render worker's own build
// (vite.render-worker.config.ts) is a deliberately single-file, no-code-splitting bundle (so this
// package stays portable wherever it's installed — see that config's own header comment), and a
// second statically-detected worker entry would break that invariant. The Blob's own text is
// always these two TRUSTED files' raw source (`?raw`-inlined at build time — deliberately plain
// JavaScript, not TypeScript, since `?raw` returns unprocessed file bytes with no transpilation;
// see engine-source.js's own header comment) — the shader's own untrusted script source is never
// concatenated into it; it's sent as plain string DATA in the first 'load' message and only ever
// `Function`-eval'd at runtime, inside the already-running sandboxed Worker.
//
// The render worker always renders with the LAST completed reply (getLatestOutput()), never
// blocking on a fresh one — one frame of async latency, imperceptible at these signals' actual
// timescales (springs settle over 100ms+, nav re-checks every 250ms, zoom dives run for minutes).
// A script that hangs (no reply within TIMEOUT_MS) or throws (an explicit 'error' reply — see
// script-worker-entry.js's own comment on why a throw needs an immediate reply, not silent
// timeout-only detection) counts as a fault: the Worker is terminated and a fresh one spawned,
// rendering continuing on frozen last-known values throughout. After MAX_CONSECUTIVE_FAULTS,
// stops retrying (thrashing a fundamentally broken script helps no one) and reports onFault once
// — rendering still never stops either way.
//
// "Sandboxed" here means fault/crash isolation, not a security boundary: this Worker still has
// fetch/XMLHttpRequest/importScripts and can make network requests; it just can't touch the
// render worker's GL context, DOM, or other state directly, and a hang/crash inside it can't take
// down rendering. See docs/isf-shaders.md for the same caveat stated for shader authors.
const TIMEOUT_MS = 800
const MAX_CONSECUTIVE_FAULTS = 5

function buildWorkerBlobUrl(): string {
  const combined = `${engineSourceRaw}\n${scriptWorkerEntryRaw}`
  const blob = new Blob([combined], { type: 'text/javascript' })
  return URL.createObjectURL(blob)
}

export class HysteresisScriptHost {
  private worker: Worker | null = null
  private blobUrl: string | null = null
  private latestOutput: HysteresisScriptFrameOutput | null = null
  private nextSeq = 0
  private pendingSeq: number | null = null
  private pendingSentAt = 0
  private consecutiveFaults = 0
  private permanentlyFaulted = false
  private loadFailed = false

  constructor(
    private readonly source: string,
    private readonly contract: HysteresisScriptOutputContract,
    private readonly onFault: (message: string) => void,
  ) {
    this.spawn()
  }

  private spawn(): void {
    this.blobUrl = buildWorkerBlobUrl()
    // Classic script, not `{ type: 'module' }` — engine-source.js/script-worker-entry.js have no
    // import/export at all (see their own header comments), so there's no module semantics to
    // opt into, and a classic worker is the simplest, most universally-supported construction.
    const worker = new Worker(this.blobUrl)
    worker.onmessage = (ev: MessageEvent) => this.handleMessage(ev.data)
    worker.onerror = (ev: ErrorEvent) => this.handleFault(`script worker error: ${ev.message}`)
    worker.postMessage({ kind: 'load', source: this.source, contract: this.contract })
    this.worker = worker
    this.pendingSeq = null
  }

  private handleMessage(msg: unknown): void {
    const m = msg as
      | { kind: 'loaded' }
      | { kind: 'loadError'; message: string }
      | { kind: 'result'; seq: number; uniforms: Record<string, unknown>; textures: Record<string, number[]> }
      | { kind: 'error'; seq: number; message: string }

    if (m.kind === 'loadError') {
      // The script itself never parsed — restarting the worker won't fix a syntax error, so this
      // is permanent, reported once, with rendering continuing on declared defaults forever.
      this.loadFailed = true
      this.permanentlyFaulted = true
      this.onFault(`HYSTERESIS_SCRIPT failed to load: ${m.message}`)
      return
    }
    if (m.kind === 'loaded') return
    if (m.kind === 'result') {
      if (m.seq !== this.pendingSeq) return // a stale reply for an older, already-superseded frame
      this.pendingSeq = null
      this.consecutiveFaults = 0
      // The message-boundary type is intentionally loose (structured-clone data) — engine-source.ts's
      // coerceUniform/coerceTexture already guarantee this exact shape before the reply is sent.
      this.latestOutput = { uniforms: m.uniforms as Record<string, number | boolean | number[]>, textures: m.textures }
      return
    }
    if (m.kind === 'error') {
      if (m.seq !== this.pendingSeq) return
      this.handleFault(`HYSTERESIS_SCRIPT threw: ${m.message}`)
    }
  }

  private handleFault(message: string): void {
    if (this.permanentlyFaulted || this.loadFailed) return
    this.consecutiveFaults++
    this.worker?.terminate()
    if (this.blobUrl) URL.revokeObjectURL(this.blobUrl)
    if (this.consecutiveFaults >= MAX_CONSECUTIVE_FAULTS) {
      this.permanentlyFaulted = true
      this.worker = null
      this.onFault(`${message} (${this.consecutiveFaults} consecutive faults — giving up, rendering continues on last-known values)`)
      return
    }
    this.spawn()
  }

  // Fire-and-forget — never awaited by the render loop. getLatestOutput() always returns
  // whatever the most recent completed reply was, so a slow/stuck reply just means one or more
  // frames render on slightly stale (still coherent, never garbage) script output.
  postUpdate(frame: HysteresisScriptFrameInput): void {
    if (this.permanentlyFaulted || !this.worker) return

    // A still-unanswered previous frame past TIMEOUT_MS is treated as a hang — the worker gets
    // terminated/restarted here rather than in a separate timer, since postUpdate() already runs
    // once per render frame (tens of ms apart), which is a fine-grained enough check interval for
    // an 800ms budget.
    if (this.pendingSeq !== null && performance.now() - this.pendingSentAt > TIMEOUT_MS) {
      this.handleFault('HYSTERESIS_SCRIPT stopped responding')
      if (this.permanentlyFaulted || !this.worker) return
    }

    const seq = this.nextSeq++
    this.pendingSeq = seq
    this.pendingSentAt = performance.now()
    this.worker.postMessage({ kind: 'update', seq, dt: frame.dt, time: frame.time, idle: frame.idle, inputs: frame.inputs })
  }

  getLatestOutput(): HysteresisScriptFrameOutput | null {
    return this.latestOutput
  }

  dispose(): void {
    this.worker?.terminate()
    this.worker = null
    if (this.blobUrl) URL.revokeObjectURL(this.blobUrl)
    this.blobUrl = null
  }
}
