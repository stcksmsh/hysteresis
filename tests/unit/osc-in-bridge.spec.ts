import { describe, it, expect, vi, afterEach } from 'vitest'
import { OscInBridge } from '../../src/osc/osc-in-bridge'
import { encodeOscBundle, encodeOscMessage } from '../../src/osc/osc-codec'

// A minimal fake WebSocket — real network I/O isn't worth the flakiness
// here (unlike scripts/udp-relay.ts's own real-relay tests, which exist
// specifically to prove real UDP forwarding works); OscInBridge's own job
// is decode-and-store, which this exercises through its real public
// surface (connect -> the onmessage handler it installs) rather than by
// reaching into its private methods.
class FakeWebSocket {
  static instances: FakeWebSocket[] = []
  binaryType = ''
  onopen: (() => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  onmessage: ((e: { data: unknown }) => void) | null = null
  closed = false
  constructor(public url: string) {
    FakeWebSocket.instances.push(this)
  }
  close() {
    this.closed = true
    this.onclose?.()
  }
  emitOpen() {
    this.onopen?.()
  }
  emitMessage(data: ArrayBuffer) {
    this.onmessage?.({ data })
  }
}

function toArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer
}

describe('OscInBridge', () => {
  afterEach(() => {
    FakeWebSocket.instances = []
    vi.unstubAllGlobals()
  })

  it('decodes an inbound message and stores its first float argument by address', () => {
    vi.stubGlobal('WebSocket', FakeWebSocket as unknown as typeof WebSocket)
    const bridge = new OscInBridge()
    bridge.connect('ws://localhost:9090')
    const ws = FakeWebSocket.instances[0]
    ws.emitOpen()

    const bytes = encodeOscMessage('/1/fader1', [{ type: 'f', value: 0.65 }])
    ws.emitMessage(toArrayBuffer(bytes))

    expect(bridge.get('/1/fader1')).toBeCloseTo(0.65)
    expect(bridge.get('/never/sent')).toBe(0)
  })

  it('flattens a bundle and stores every element message', () => {
    vi.stubGlobal('WebSocket', FakeWebSocket as unknown as typeof WebSocket)
    const bridge = new OscInBridge()
    bridge.connect('ws://localhost:9090')
    const ws = FakeWebSocket.instances[0]
    ws.emitOpen()

    const bundle = encodeOscBundle([
      { address: '/a', args: [{ type: 'i', value: 3 }] },
      { address: '/b', args: [{ type: 'T' }] },
      { address: '/c', args: [{ type: 'F' }] },
    ])
    ws.emitMessage(toArrayBuffer(bundle))

    expect(bridge.get('/a')).toBe(3)
    expect(bridge.get('/b')).toBe(1)
    expect(bridge.get('/c')).toBe(0)
  })

  it('drops a message whose first argument is a string rather than coercing it', () => {
    vi.stubGlobal('WebSocket', FakeWebSocket as unknown as typeof WebSocket)
    const bridge = new OscInBridge()
    bridge.connect('ws://localhost:9090')
    const ws = FakeWebSocket.instances[0]
    ws.emitOpen()

    const bytes = encodeOscMessage('/label', [{ type: 's', value: 'hello' }])
    ws.emitMessage(toArrayBuffer(bytes))

    expect(bridge.get('/label')).toBe(0)
  })

  it('does not crash on a malformed inbound frame, and keeps decoding after it', () => {
    vi.stubGlobal('WebSocket', FakeWebSocket as unknown as typeof WebSocket)
    const bridge = new OscInBridge()
    bridge.connect('ws://localhost:9090')
    const ws = FakeWebSocket.instances[0]
    ws.emitOpen()

    ws.emitMessage(toArrayBuffer(new Uint8Array([1, 2, 3])))
    const bytes = encodeOscMessage('/ok', [{ type: 'f', value: 0.1 }])
    ws.emitMessage(toArrayBuffer(bytes))

    expect(bridge.get('/ok')).toBeCloseTo(0.1)
  })

  it('reports connect/disconnect status transitions', () => {
    vi.stubGlobal('WebSocket', FakeWebSocket as unknown as typeof WebSocket)
    const statuses: { connected: boolean; message?: string }[] = []
    const bridge = new OscInBridge((status) => statuses.push(status))
    bridge.connect('ws://localhost:9090')
    const ws = FakeWebSocket.instances[0]
    ws.emitOpen()
    bridge.disconnect()

    expect(statuses[0]).toEqual({ connected: true })
    expect(ws.closed).toBe(true)
  })
})
