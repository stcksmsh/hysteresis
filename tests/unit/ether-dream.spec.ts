import { describe, it, expect } from 'vitest'
import {
  decodeDacStatus,
  decodeDacBroadcast,
  decodeDacResponse,
  encodeDacPoint,
  decodeDacPoint,
  encodeBeginCommand,
  encodeQueueRateChangeCommand,
  encodeDataCommand,
  DAC_RESPONSE_ACK,
} from '../../src/ilda/ether-dream'

// A synthetic 20-byte DacStatus, field values chosen to be distinguishable
// from each other so a byte-offset mistake shows up as a wrong VALUE, not
// just a wrong TYPE.
function makeStatusBytes(): Uint8Array {
  const buf = new Uint8Array(20)
  const view = new DataView(buf.buffer)
  buf[0] = 1 // protocol
  buf[1] = 2 // lightEngineState
  buf[2] = 3 // playbackState
  buf[3] = 4 // source
  view.setUint16(4, 500, true) // lightEngineFlags
  view.setUint16(6, 600, true) // playbackFlags
  view.setUint16(8, 700, true) // sourceFlags
  view.setUint16(10, 800, true) // bufferFullness
  view.setUint32(12, 30000, true) // pointRate
  view.setUint32(16, 123456, true) // pointCount
  return buf
}

describe('decodeDacStatus', () => {
  it('decodes all 10 fields at their real byte offsets (cross-checked against 2 independent implementations)', () => {
    const status = decodeDacStatus(makeStatusBytes())
    expect(status).toEqual({
      protocol: 1,
      lightEngineState: 2,
      playbackState: 3,
      source: 4,
      lightEngineFlags: 500,
      playbackFlags: 600,
      sourceFlags: 700,
      bufferFullness: 800,
      pointRate: 30000,
      pointCount: 123456,
    })
  })
})

describe('decodeDacBroadcast', () => {
  it('decodes a real 36-byte broadcast packet (mac+hw/sw rev+capacity+rate+20-byte status)', () => {
    const buf = new Uint8Array(36)
    const view = new DataView(buf.buffer)
    buf.set([1, 2, 3, 4, 5, 6], 0) // mac
    view.setUint16(6, 10, true) // hwRevision
    view.setUint16(8, 20, true) // swRevision
    view.setUint16(10, 1799, true) // bufferCapacity
    view.setUint32(12, 100000, true) // maxPointRate
    buf.set(makeStatusBytes(), 16)

    const bp = decodeDacBroadcast(buf)
    expect(Array.from(bp.macAddress)).toEqual([1, 2, 3, 4, 5, 6])
    expect(bp.hwRevision).toBe(10)
    expect(bp.swRevision).toBe(20)
    expect(bp.bufferCapacity).toBe(1799)
    expect(bp.maxPointRate).toBe(100000)
    expect(bp.status.pointCount).toBe(123456)
  })
})

describe('decodeDacResponse', () => {
  it('decodes a real 22-byte response (1 ack + 1 command echo + 20-byte status)', () => {
    const buf = new Uint8Array(22)
    buf[0] = DAC_RESPONSE_ACK
    buf[1] = 0x64 // echoes the 'd' data command
    buf.set(makeStatusBytes(), 2)

    const resp = decodeDacResponse(buf)
    expect(resp.response).toBe(DAC_RESPONSE_ACK)
    expect(resp.command).toBe(0x64)
    expect(resp.status.pointCount).toBe(123456)
  })
})

describe('DacPoint encode/decode', () => {
  it('round-trips all 9 fields, little-endian, at the real 18-byte point layout', () => {
    const point = { control: 0, x: -1000, y: 30000, r: 65535, g: 100, b: 200, i: 50000, u1: 1, u2: 2 }
    const bytes = encodeDacPoint(point)
    expect(bytes.byteLength).toBe(18)
    expect(decodeDacPoint(bytes)).toEqual(point)
  })
})

describe('command encoders', () => {
  it('encodeBeginCommand: real 7-byte layout (command + lwm u16 LE + rate u32 LE)', () => {
    const bytes = encodeBeginCommand(0, 30000)
    expect(bytes.byteLength).toBe(7)
    expect(bytes[0]).toBe(0x62) // 'b'
    const view = new DataView(bytes.buffer)
    expect(view.getUint16(1, true)).toBe(0)
    expect(view.getUint32(3, true)).toBe(30000)
  })

  it('encodeQueueRateChangeCommand: 5-byte layout (command + rate u32 LE) — lower-confidence command, see module header', () => {
    const bytes = encodeQueueRateChangeCommand(25000)
    expect(bytes.byteLength).toBe(5)
    expect(bytes[0]).toBe(0x71) // 'q'
    const view = new DataView(bytes.buffer)
    expect(view.getUint32(1, true)).toBe(25000)
  })

  it('encodeDataCommand: command + point count (u16 LE) + N real 18-byte points', () => {
    const points = [
      { control: 0, x: 0, y: 0, r: 0, g: 0, b: 0, i: 0, u1: 0, u2: 0 },
      { control: 0, x: 1, y: 1, r: 1, g: 1, b: 1, i: 1, u1: 1, u2: 1 },
    ]
    const bytes = encodeDataCommand(points)
    expect(bytes[0]).toBe(0x64) // 'd'
    const view = new DataView(bytes.buffer)
    expect(view.getUint16(1, true)).toBe(2)
    expect(bytes.byteLength).toBe(3 + 2 * 18)
    expect(decodeDacPoint(bytes, 3 + 18)).toEqual(points[1])
  })
})
