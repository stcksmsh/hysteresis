import { describe, it, expect } from 'vitest'
import { encodeArtDmx } from '../../src/dmx/artnet'

describe('encodeArtDmx', () => {
  it('writes the "Art-Net\\0" identifier at offset 0', () => {
    const bytes = encodeArtDmx({ universe: 0, sequence: 1, data: new Uint8Array(4) })
    const id = new TextDecoder().decode(bytes.subarray(0, 7))
    expect(id).toBe('Art-Net')
    expect(bytes[7]).toBe(0)
  })

  it('writes OpCode 0x5000 little-endian at offset 8', () => {
    const bytes = encodeArtDmx({ universe: 0, sequence: 1, data: new Uint8Array(4) })
    expect(bytes[8]).toBe(0x00)
    expect(bytes[9]).toBe(0x50)
  })

  it('writes protocol version 14 big-endian at offset 10', () => {
    const bytes = encodeArtDmx({ universe: 0, sequence: 1, data: new Uint8Array(4) })
    expect(bytes[10]).toBe(0)
    expect(bytes[11]).toBe(14)
  })

  it('splits the universe into SubUni/Net correctly', () => {
    // universe 0x0173 = Net 0x01, SubUni 0x73
    const bytes = encodeArtDmx({ universe: 0x0173, sequence: 1, data: new Uint8Array(2) })
    expect(bytes[14]).toBe(0x73) // SubUni
    expect(bytes[15]).toBe(0x01) // Net
  })

  it('writes sequence and physical', () => {
    const bytes = encodeArtDmx({ universe: 0, sequence: 200, physical: 3, data: new Uint8Array(2) })
    expect(bytes[12]).toBe(200)
    expect(bytes[13]).toBe(3)
  })

  it('writes the data length big-endian and the DMX data verbatim', () => {
    const data = new Uint8Array([1, 2, 3, 4, 5, 6])
    const bytes = encodeArtDmx({ universe: 0, sequence: 1, data })
    expect(bytes[16]).toBe(0)
    expect(bytes[17]).toBe(6)
    expect(Array.from(bytes.subarray(18, 24))).toEqual([1, 2, 3, 4, 5, 6])
    expect(bytes.byteLength).toBe(18 + 6)
  })

  it('pads odd-length data to an even length, per spec', () => {
    const data = new Uint8Array([9, 9, 9]) // 3 channels
    const bytes = encodeArtDmx({ universe: 0, sequence: 1, data })
    expect(bytes[17]).toBe(4) // padded to 4
    expect(bytes.byteLength).toBe(18 + 4)
    expect(bytes[18 + 3]).toBe(0) // padding byte is zero
  })

  it('pads to the minimum length of 2 even for empty data', () => {
    const bytes = encodeArtDmx({ universe: 0, sequence: 1, data: new Uint8Array(0) })
    expect(bytes[17]).toBe(2)
    expect(bytes.byteLength).toBe(20)
  })
})
