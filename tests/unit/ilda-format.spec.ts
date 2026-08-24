import { describe, it, expect } from 'vitest'
import { encodeIldaHeader, decodeIldaHeader, encodeIldaPoints, decodeIldaPoints, encodeIldaFile, decodeIldaFile, type IldaPoint } from '../../src/ilda/ilda-format'

describe('ILDA header', () => {
  it('writes the "ILDA" magic at offset 0', () => {
    const bytes = encodeIldaHeader({ format: 5, dataName: '', companyName: '', numRecords: 0, dataNumber: 0, colorOrTotalFrames: 0, projectorNumber: 0 })
    expect(String.fromCharCode(...bytes.subarray(0, 4))).toBe('ILDA')
  })

  it('round-trips every field, including truncated ASCII names', () => {
    const header = { format: 5 as const, dataName: 'MyFrame1', companyName: 'Hysteres', numRecords: 100, dataNumber: 3, colorOrTotalFrames: 10, projectorNumber: 2 }
    const bytes = encodeIldaHeader(header)
    expect(bytes.byteLength).toBe(32)
    const decoded = decodeIldaHeader(bytes)
    expect(decoded).toEqual(header)
  })

  it('places fields at the exact spec-published byte offsets (format at 7, names at 8/16, numRecords at 24)', () => {
    const bytes = encodeIldaHeader({ format: 5, dataName: 'AB', companyName: 'CD', numRecords: 300, dataNumber: 0, colorOrTotalFrames: 0, projectorNumber: 0 })
    expect(bytes[7]).toBe(5)
    expect(bytes[8]).toBe('A'.charCodeAt(0))
    expect(bytes[16]).toBe('C'.charCodeAt(0))
    expect((bytes[24] << 8) | bytes[25]).toBe(300) // big-endian uint16
  })

  it('rejects a non-ILDA section header', () => {
    const bytes = new Uint8Array(32)
    expect(() => decodeIldaHeader(bytes)).toThrow(/ILDA/)
  })

  it('truncates a name longer than 8 ASCII characters', () => {
    const bytes = encodeIldaHeader({ format: 5, dataName: 'WayTooLongAName', companyName: '', numRecords: 0, dataNumber: 0, colorOrTotalFrames: 0, projectorNumber: 0 })
    expect(decodeIldaHeader(bytes).dataName).toBe('WayTooLo')
  })
})

describe('ILDA format 5 points (2D true color)', () => {
  const points: IldaPoint[] = [
    { x: 100, y: -200, blanking: false, r: 255, g: 0, b: 0 },
    { x: -32768, y: 32767, blanking: true, r: 0, g: 255, b: 0, isLastPoint: true },
  ]

  it('round-trips coordinates, RGB, and blanking/last-point flags', () => {
    const bytes = encodeIldaPoints(5, points)
    expect(bytes.byteLength).toBe(2 * 8) // 4 bytes coords + 1 status + 3 RGB
    const decoded = decodeIldaPoints(5, bytes, 2)
    expect(decoded[0]).toMatchObject({ x: 100, y: -200, blanking: false, r: 255, g: 0, b: 0 })
    expect(decoded[1]).toMatchObject({ x: -32768, y: 32767, blanking: true, r: 0, g: 255, b: 0, isLastPoint: true })
    expect(decoded[0].isLastPoint).toBe(false)
  })
})

describe('ILDA format 0 points (3D indexed color)', () => {
  it('round-trips x/y/z and a color palette index', () => {
    const points: IldaPoint[] = [{ x: 1, y: 2, z: 3, blanking: false, colorIndex: 42 }]
    const bytes = encodeIldaPoints(0, points)
    expect(bytes.byteLength).toBe(8) // 6 bytes coords + 1 status + 1 color index
    const decoded = decodeIldaPoints(0, bytes, 1)
    expect(decoded[0]).toMatchObject({ x: 1, y: 2, z: 3, blanking: false, colorIndex: 42 })
  })
})

describe('ILDA format 2 (color palette)', () => {
  it('round-trips a plain RGB triplet with no coordinate fields', () => {
    const points: IldaPoint[] = [{ x: 0, y: 0, blanking: false, r: 10, g: 20, b: 30 }]
    const bytes = encodeIldaPoints(2, points)
    expect(bytes.byteLength).toBe(3)
    expect(Array.from(bytes)).toEqual([10, 20, 30])
  })
})

describe('encodeIldaFile / decodeIldaFile', () => {
  it('produces a real, loadable multi-frame file terminated by an end-of-file header (numRecords === 0)', () => {
    const file = encodeIldaFile([
      { format: 5, points: [{ x: 0, y: 0, blanking: false, r: 255, g: 255, b: 255 }] },
      { format: 5, points: [{ x: 10, y: 10, blanking: false, r: 0, g: 0, b: 255 }] },
    ])
    const decoded = decodeIldaFile(file)
    expect(decoded).toHaveLength(2)
    expect(decoded[0].points[0]).toMatchObject({ x: 0, y: 0, r: 255, g: 255, b: 255 })
    expect(decoded[1].points[0]).toMatchObject({ x: 10, y: 10, r: 0, g: 0, b: 255 })

    // The end-of-file header should be the last 32 bytes, with numRecords === 0.
    const lastHeader = decodeIldaHeader(file.subarray(file.byteLength - 32))
    expect(lastHeader.numRecords).toBe(0)
  })

  it('sets the LAST_POINT status bit on each frame\'s final point automatically', () => {
    const file = encodeIldaFile([{ format: 5, points: [{ x: 0, y: 0, blanking: false, r: 1, g: 1, b: 1 }, { x: 1, y: 1, blanking: false, r: 2, g: 2, b: 2 }] }])
    const decoded = decodeIldaFile(file)
    expect(decoded[0].points[0].isLastPoint).toBe(false)
    expect(decoded[0].points[1].isLastPoint).toBe(true)
  })

  it('fills dataNumber/colorOrTotalFrames from the frame sequence automatically', () => {
    const file = encodeIldaFile([
      { format: 5, points: [{ x: 0, y: 0, blanking: false, r: 0, g: 0, b: 0 }] },
      { format: 5, points: [{ x: 0, y: 0, blanking: false, r: 0, g: 0, b: 0 }] },
    ])
    const header0 = decodeIldaHeader(file.subarray(0, 32))
    const header1 = decodeIldaHeader(file.subarray(32 + 8, 32 + 8 + 32))
    expect(header0.dataNumber).toBe(0)
    expect(header0.colorOrTotalFrames).toBe(2)
    expect(header1.dataNumber).toBe(1)
  })

  it('produces an empty frame list for a file that is only the end-of-file header', () => {
    const file = encodeIldaFile([])
    expect(decodeIldaFile(file)).toEqual([])
  })
})
