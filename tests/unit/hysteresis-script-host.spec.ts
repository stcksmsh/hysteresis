import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { HysteresisScriptHost } from '../../src/render/worker/scenes/isf/script-runtime/script-host'
import type { HysteresisScriptOutputContract } from '../../src/isf/script-runtime/contract'

// This is the actual proof of the "uptime is the primary concern" design (AGENTS.md's own
// framing) — a real hang/crash inside the sandboxed nested Worker can't be reproduced against a
// live browser in this environment, so the fault-handling logic in script-host.ts is verified
// here against a mocked `Worker` global instead: a normal round trip, an unanswered reply past
// the timeout budget, an explicit error reply, and the consecutive-fault cap that stops retrying
// a fundamentally broken script — in every case, getLatestOutput() must keep returning the last
// good value and the host must never throw back into the caller (IsfScene's render loop).

class MockWorker {
  static instances: MockWorker[] = []
  onmessage: ((ev: MessageEvent) => void) | null = null
  onerror: ((ev: ErrorEvent) => void) | null = null
  sent: unknown[] = []
  terminated = false

  constructor(public url: string) {
    MockWorker.instances.push(this)
  }
  postMessage(msg: unknown): void {
    this.sent.push(msg)
  }
  terminate(): void {
    this.terminated = true
  }
  // Test helper — not part of the real Worker API.
  reply(data: unknown): void {
    this.onmessage?.({ data } as MessageEvent)
  }
}

const CONTRACT: HysteresisScriptOutputContract = { uniforms: {}, textures: {} }

let now = 0

beforeEach(() => {
  now = 0
  MockWorker.instances = []
  vi.stubGlobal('Worker', MockWorker)
  vi.stubGlobal('URL', { createObjectURL: () => 'blob:mock', revokeObjectURL: () => {} })
  vi.spyOn(performance, 'now').mockImplementation(() => now)
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

function currentWorker(): MockWorker {
  return MockWorker.instances[MockWorker.instances.length - 1]
}

describe('HysteresisScriptHost', () => {
  it('sends a load message on construction and reflects a normal round trip in getLatestOutput()', () => {
    const onFault = vi.fn()
    const host = new HysteresisScriptHost('function update() {}', CONTRACT, onFault)
    expect(currentWorker().sent[0]).toMatchObject({ kind: 'load', source: 'function update() {}' })
    currentWorker().reply({ kind: 'loaded' })

    expect(host.getLatestOutput()).toBeNull() // nothing yet before the first postUpdate/result

    host.postUpdate({ dt: 0.016, time: 0, idle: false, inputs: {} })
    const sentUpdate = currentWorker().sent.at(-1) as { kind: string; seq: number }
    expect(sentUpdate.kind).toBe('update')
    currentWorker().reply({ kind: 'result', seq: sentUpdate.seq, uniforms: { zoom: 1.5 }, textures: {} })

    expect(host.getLatestOutput()).toEqual({ uniforms: { zoom: 1.5 }, textures: {} })
    expect(onFault).not.toHaveBeenCalled()
  })

  it('ignores a stale reply for an already-superseded frame', () => {
    const host = new HysteresisScriptHost('function update() {}', CONTRACT, vi.fn())
    currentWorker().reply({ kind: 'loaded' })

    host.postUpdate({ dt: 0.016, time: 0, idle: false, inputs: {} })
    const firstSeq = (currentWorker().sent.at(-1) as { seq: number }).seq
    host.postUpdate({ dt: 0.016, time: 0.016, idle: false, inputs: {} }) // supersedes the first before it replies

    // The stale first-seq reply must not overwrite anything (there's nothing to overwrite yet).
    currentWorker().reply({ kind: 'result', seq: firstSeq, uniforms: { stale: true }, textures: {} })
    expect(host.getLatestOutput()).toBeNull()
  })

  it('a reply that never arrives past TIMEOUT_MS terminates and restarts the worker, keeping the last-known value', () => {
    const onFault = vi.fn()
    const host = new HysteresisScriptHost('function update() {}', CONTRACT, onFault)
    currentWorker().reply({ kind: 'loaded' })

    host.postUpdate({ dt: 0.016, time: 0, idle: false, inputs: {} })
    const seq = (currentWorker().sent.at(-1) as { seq: number }).seq
    currentWorker().reply({ kind: 'result', seq, uniforms: { zoom: 3 }, textures: {} })
    expect(host.getLatestOutput()).toEqual({ uniforms: { zoom: 3 }, textures: {} })

    const staleWorker = currentWorker()
    host.postUpdate({ dt: 0.016, time: 0.016, idle: false, inputs: {} }) // never replied to
    now += 1000 // past TIMEOUT_MS (800ms)
    host.postUpdate({ dt: 0.016, time: 1.016, idle: false, inputs: {} }) // this call detects the hang

    expect(staleWorker.terminated).toBe(true)
    expect(MockWorker.instances).toHaveLength(2) // restarted with a fresh worker
    expect(currentWorker().sent[0]).toMatchObject({ kind: 'load' }) // re-sent load on the new worker
    expect(host.getLatestOutput()).toEqual({ uniforms: { zoom: 3 }, textures: {} }) // frozen, not lost
    expect(onFault).not.toHaveBeenCalled() // one fault alone doesn't give up
  })

  it('an explicit error reply (a synchronous throw inside update()) is treated as an immediate fault, not silence', () => {
    const host = new HysteresisScriptHost('function update() { throw new Error("boom") }', CONTRACT, vi.fn())
    currentWorker().reply({ kind: 'loaded' })

    host.postUpdate({ dt: 0.016, time: 0, idle: false, inputs: {} })
    const seq = (currentWorker().sent.at(-1) as { seq: number }).seq
    const staleWorker = currentWorker()
    currentWorker().reply({ kind: 'error', seq, message: 'boom' })

    // No time needed to pass at all — an error reply faults immediately, unlike a hang.
    expect(staleWorker.terminated).toBe(true)
    expect(MockWorker.instances).toHaveLength(2)
  })

  it('stops retrying and fires onFault exactly once after the consecutive-fault cap, still never throwing', () => {
    const onFault = vi.fn()
    const host = new HysteresisScriptHost('function update() {}', CONTRACT, onFault)
    currentWorker().reply({ kind: 'loaded' })

    for (let i = 0; i < 6; i++) {
      host.postUpdate({ dt: 0.016, time: i, idle: false, inputs: {} })
      const seq = (currentWorker().sent.at(-1) as { seq: number }).seq
      expect(() => currentWorker().reply({ kind: 'error', seq, message: `fault ${i}` })).not.toThrow()
    }

    expect(onFault).toHaveBeenCalledTimes(1)
    const instancesAfterGivingUp = MockWorker.instances.length
    expect(() => host.postUpdate({ dt: 0.016, time: 99, idle: false, inputs: {} })).not.toThrow()
    expect(MockWorker.instances).toHaveLength(instancesAfterGivingUp) // no further spawns — genuinely gave up
  })

  it('a loadError is permanent (a syntax error will not fix itself on restart) and reported once', () => {
    const onFault = vi.fn()
    const host = new HysteresisScriptHost('not valid js (((', CONTRACT, onFault)
    currentWorker().reply({ kind: 'loadError', message: 'Unexpected token' })

    expect(onFault).toHaveBeenCalledTimes(1)
    expect(() => host.postUpdate({ dt: 0.016, time: 0, idle: false, inputs: {} })).not.toThrow()
    expect(MockWorker.instances).toHaveLength(1) // no restart attempted for a load-time failure
  })

  it('dispose() terminates the worker and does not throw on a scriptless/never-updated host', () => {
    const host = new HysteresisScriptHost('function update() {}', CONTRACT, vi.fn())
    currentWorker().reply({ kind: 'loaded' })
    expect(() => host.dispose()).not.toThrow()
    expect(currentWorker().terminated).toBe(true)
  })
})
