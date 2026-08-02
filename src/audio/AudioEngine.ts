import type { StateFrame, WorkletToMain } from '../shared/types'

export type StateFrameListener = (frame: StateFrame) => void

export class AudioEngine {
  private ctx: AudioContext | null = null
  private workletNode: AudioWorkletNode | null = null
  private sourceNode: AudioBufferSourceNode | null = null
  private listeners = new Set<StateFrameListener>()
  private startedAtCtxTime: number | null = null

  onStateFrame(listener: StateFrameListener): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  get isPlaying(): boolean {
    return this.ctx?.state === 'running' && this.sourceNode !== null
  }

  // Seconds since the current source started, in the source's own timeline.
  // ctx.currentTime freezes while suspended, so this stays correct across
  // pause/resume with no extra bookkeeping — it just stops advancing.
  get currentTime(): number {
    if (!this.ctx || this.startedAtCtxTime === null) return 0
    return this.ctx.currentTime - this.startedAtCtxTime
  }

  async pause(): Promise<void> {
    await this.ctx?.suspend()
  }

  async resume(): Promise<void> {
    await this.ctx?.resume()
  }

  // Must be called from a user-gesture handler (file picker change/drop) —
  // AudioContext creation is autoplay-gated.
  async loadAndPlay(file: File): Promise<void> {
    const ctx = await this.ensureContext()
    const arrayBuffer = await file.arrayBuffer()
    const audioBuffer = await ctx.decodeAudioData(arrayBuffer)

    this.sourceNode?.stop()
    const source = ctx.createBufferSource()
    source.buffer = audioBuffer

    // Audible playback goes straight to the speakers. The worklet branch's
    // output is never written to (process() never touches `outputs`), so
    // connecting it onward to destination is silent — it exists only so
    // the node stays in the actively-pulled render graph and its process()
    // keeps getting called (nodes with no path to the destination are not
    // processed at all per the Web Audio spec's pull model).
    source.connect(ctx.destination)
    if (this.workletNode) source.connect(this.workletNode)

    this.startedAtCtxTime = ctx.currentTime
    source.start()
    this.sourceNode = source
  }

  private async ensureContext(): Promise<AudioContext> {
    if (this.ctx) return this.ctx

    const ctx = new AudioContext()
    const workletUrl = new URL(`${import.meta.env.BASE_URL}worklets/feature-worklet.js`, window.location.href)
    await ctx.audioWorklet.addModule(workletUrl)

    const node = new AudioWorkletNode(ctx, 'feature-processor')
    node.connect(ctx.destination)
    node.port.onmessage = (e: MessageEvent<WorkletToMain>) => {
      if (e.data.kind === 'state') {
        for (const listener of this.listeners) listener(e.data.frame)
      } else if (e.data.kind === 'error') {
        console.error('[AudioEngine] worklet error:', e.data.message)
      }
    }

    this.ctx = ctx
    this.workletNode = node
    return ctx
  }
}
