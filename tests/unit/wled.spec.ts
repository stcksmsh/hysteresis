import { describe, it, expect } from 'vitest'
import { encodeWledDrgb, encodeWledWarls } from '../../src/dmx/wled'

describe('encodeWledDrgb', () => {
  it('prepends protocol byte 2 and the timeout byte, then the RGB stream verbatim', () => {
    const rgb = new Uint8Array([255, 0, 0, 0, 255, 0])
    const bytes = encodeWledDrgb(rgb, 5)
    expect(bytes[0]).toBe(2)
    expect(bytes[1]).toBe(5)
    expect(Array.from(bytes.subarray(2))).toEqual([255, 0, 0, 0, 255, 0])
  })

  it('defaults the timeout to 1 second', () => {
    const bytes = encodeWledDrgb(new Uint8Array(3))
    expect(bytes[1]).toBe(1)
  })
})

describe('encodeWledWarls', () => {
  it('prepends protocol byte 1 and the timeout byte, then index+RGB quads per pixel', () => {
    const bytes = encodeWledWarls(
      [
        { index: 0, r: 255, g: 0, b: 0 },
        { index: 5, r: 0, g: 0, b: 255 },
      ],
      3,
    )
    expect(bytes[0]).toBe(1)
    expect(bytes[1]).toBe(3)
    expect(Array.from(bytes.subarray(2, 6))).toEqual([0, 255, 0, 0])
    expect(Array.from(bytes.subarray(6, 10))).toEqual([5, 0, 0, 255])
    expect(bytes.byteLength).toBe(2 + 2 * 4)
  })
})
