import type { MainToWorklet, StateFrame, WorkletToMain } from '../shared/types'

export type StateFrameListener = (frame: StateFrame) => void

// Attach-only: this repo never owns the AudioContext or the transport
// (SINTEZA_VIZ.md §7) — the host creates/decodes/plays audio and hands us
// `{ audioContext, source }`; we just addModule() the feature worklet and
// tap `source` downstream of it.
export class AudioEngine {
  private ctx: AudioContext | null = null
  private workletNode: AudioWorkletNode | null = null
  private sourceNode: AudioNode | null = null
  private listeners = new Set<StateFrameListener>()

  onStateFrame(listener: StateFrameListener): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  get attached(): boolean {
    return this.workletNode !== null
  }

  // Two callers (SINTEZA_SIGNAL_BUS.md §4.1's debug acceptance test, and
  // src/index.ts's §4b(1) sidecar-primary gating) share this one toggle —
  // see MainToWorklet's doc comment. No-op if no worklet is attached yet.
  setDetectorsEnabled(enabled: boolean): void {
    this.workletNode?.port.postMessage({ kind: 'debugSetDetectorsEnabled', value: enabled } satisfies MainToWorklet)
  }

  // `workletUrl` is host-resolvable-asset-dependent (see src/index.ts) since
  // `audioWorklet.addModule()` targets aren't specially handled by bundlers'
  // `new URL(..., import.meta.url)` asset scanning the way `new Worker()` is.
  async attach(ctx: AudioContext, workletUrl: string | URL, source?: AudioNode): Promise<void> {
    this.detach()
    await ctx.audioWorklet.addModule(workletUrl)

    const node = new AudioWorkletNode(ctx, 'feature-processor')
    node.port.onmessage = (e: MessageEvent<WorkletToMain>) => {
      if (e.data.kind === 'state') {
        for (const listener of this.listeners) listener(e.data.frame)
      } else if (e.data.kind === 'error') {
        console.error('[sinteza-viz] worklet error:', e.data.message)
      }
    }

    if (source) source.connect(node)
    // process() never writes to `outputs` — this connection exists only so
    // the node sits on a path to the destination and keeps getting pulled
    // per the Web Audio spec's pull model (a node nothing pulls never runs).
    node.connect(ctx.destination)

    this.ctx = ctx
    this.workletNode = node
    this.sourceNode = source ?? null
  }

  detach(): void {
    // Disconnect only the specific source->worklet edge we made, not
    // `source`'s other connections (the host owns those).
    if (this.sourceNode && this.workletNode) {
      try {
        this.sourceNode.disconnect(this.workletNode)
      } catch {
        // Already disconnected (e.g. source itself was torn down) — fine.
      }
    }
    this.workletNode?.disconnect()
    this.workletNode = null
    this.sourceNode = null
  }
}
