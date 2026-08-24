// ILDA Image Data Transfer Format — the real, published file-format
// standard behind master-prompt.md §5's "ILDA / laser DAC support" entry.
// Implemented against the ILDA Technical Committee's IDTF spec (Revision
// 011, 2014-11-16, https://www.ilda.com/resources/StandardsDocs/ILDA_IDTF14_rev011.pdf)
// cross-checked against nannou-org/ilda-idtf (a real, maintained Rust
// implementation of the same spec: https://github.com/nannou-org/ilda-idtf/blob/master/src/layout.rs)
// — both independently agree on every byte offset/field size used here, so
// this isn't a from-memory guess the way an unverified spec would be.
//
// A `.ild` file is a sequence of 32-byte section headers, each followed by
// that section's data records (points, for formats 0/1/4/5, or colors for
// the format-2 palette), terminated by a header with numRecords === 0
// (the spec's own "end of file" marker — no records follow it).

export type IldaFormat = 0 | 1 | 2 | 4 | 5

export interface IldaHeader {
  format: IldaFormat
  dataName: string // ASCII, truncated to 8 bytes on encode
  companyName: string // ASCII, truncated to 8 bytes on encode
  numRecords: number
  dataNumber: number // frame number (formats 0/1/4/5) or palette number (format 2)
  colorOrTotalFrames: number // total frames in the sequence (0/1/4/5) — SHALL be 0 for format 2
  projectorNumber: number
}

// The point-record shape this module accepts/returns for formats 0/1/4/5 —
// a superset of every format's real fields (z/colorIndex only apply to
// some), so callers don't need one type per format. `encodeIldaPoints`
// only reads the fields relevant to the format actually being encoded.
export interface IldaPoint {
  x: number // -32768..32767 (left negative, right positive, per spec)
  y: number // -32768..32767 (down negative, up positive, per spec)
  z?: number // 3D formats only (0, 4) — far negative, near positive
  blanking: boolean // laser off (moving, not drawing) for this point
  isLastPoint?: boolean // set automatically by encodeIldaFrame on the final point — see its own comment
  colorIndex?: number // indexed-color formats only (0, 1) — 0..255 into a palette
  r?: number // true-color formats only (4, 5) — 0..255
  g?: number
  b?: number
}

const HEADER_SIZE = 32
const ILDA_MAGIC = 'ILDA'
const STATUS_LAST_POINT = 0b10000000
const STATUS_BLANKING = 0b01000000

function writeAsciiField(view: DataView, offset: number, length: number, text: string): void {
  for (let i = 0; i < length; i++) view.setUint8(offset + i, i < text.length ? text.charCodeAt(i) & 0x7f : 0)
}

function readAsciiField(view: DataView, offset: number, length: number): string {
  const bytes: number[] = []
  for (let i = 0; i < length; i++) {
    const b = view.getUint8(offset + i)
    if (b === 0) break
    bytes.push(b)
  }
  return String.fromCharCode(...bytes)
}

export function encodeIldaHeader(header: IldaHeader): Uint8Array {
  const buf = new Uint8Array(HEADER_SIZE)
  const view = new DataView(buf.buffer)
  for (let i = 0; i < 4; i++) buf[i] = ILDA_MAGIC.charCodeAt(i)
  // bytes 4-6: reserved, zeroed (Uint8Array default)
  view.setUint8(7, header.format)
  writeAsciiField(view, 8, 8, header.dataName)
  writeAsciiField(view, 16, 8, header.companyName)
  view.setUint16(24, header.numRecords, false)
  view.setUint16(26, header.dataNumber, false)
  view.setUint16(28, header.colorOrTotalFrames, false)
  view.setUint8(30, header.projectorNumber)
  // byte 31: reserved, zeroed
  return buf
}

export function decodeIldaHeader(bytes: Uint8Array): IldaHeader {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  const magic = String.fromCharCode(bytes[0], bytes[1], bytes[2], bytes[3])
  if (magic !== ILDA_MAGIC) throw new Error(`Not an ILDA section header (expected "ILDA", got "${magic}")`)
  return {
    format: view.getUint8(7) as IldaFormat,
    dataName: readAsciiField(view, 8, 8),
    companyName: readAsciiField(view, 16, 8),
    numRecords: view.getUint16(24, false),
    dataNumber: view.getUint16(26, false),
    colorOrTotalFrames: view.getUint16(28, false),
    projectorNumber: view.getUint8(30),
  }
}

function pointRecordSize(format: IldaFormat): number {
  switch (format) {
    case 0:
      return 8 // x,y,z (6) + status (1) + colorIndex (1)
    case 1:
      return 6 // x,y (4) + status (1) + colorIndex (1)
    case 2:
      return 3 // r,g,b
    case 4:
      return 10 // x,y,z (6) + status (1) + r,g,b (3)
    case 5:
      return 8 // x,y (4) + status (1) + r,g,b (3)
  }
}

// Encodes one section's worth of point/color records (NOT including its
// header) for the given format.
export function encodeIldaPoints(format: IldaFormat, points: IldaPoint[]): Uint8Array {
  const size = pointRecordSize(format)
  const buf = new Uint8Array(points.length * size)
  const view = new DataView(buf.buffer)

  points.forEach((p, i) => {
    let offset = i * size
    if (format === 2) {
      buf[offset] = p.r ?? 0
      buf[offset + 1] = p.g ?? 0
      buf[offset + 2] = p.b ?? 0
      return
    }
    view.setInt16(offset, p.x, false)
    offset += 2
    view.setInt16(offset, p.y, false)
    offset += 2
    if (format === 0 || format === 4) {
      view.setInt16(offset, p.z ?? 0, false)
      offset += 2
    }
    let status = 0
    if (p.isLastPoint) status |= STATUS_LAST_POINT
    if (p.blanking) status |= STATUS_BLANKING
    buf[offset] = status
    offset += 1
    if (format === 0 || format === 1) {
      buf[offset] = p.colorIndex ?? 0
    } else {
      buf[offset] = p.r ?? 0
      buf[offset + 1] = p.g ?? 0
      buf[offset + 2] = p.b ?? 0
    }
  })

  return buf
}

export function decodeIldaPoints(format: IldaFormat, bytes: Uint8Array, count: number): IldaPoint[] {
  const size = pointRecordSize(format)
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  const points: IldaPoint[] = []

  for (let i = 0; i < count; i++) {
    let offset = i * size
    if (format === 2) {
      points.push({ x: 0, y: 0, blanking: false, r: bytes[offset], g: bytes[offset + 1], b: bytes[offset + 2] })
      continue
    }
    const x = view.getInt16(offset, false)
    offset += 2
    const y = view.getInt16(offset, false)
    offset += 2
    let z: number | undefined
    if (format === 0 || format === 4) {
      z = view.getInt16(offset, false)
      offset += 2
    }
    const status = bytes[offset]
    offset += 1
    const point: IldaPoint = {
      x,
      y,
      z,
      blanking: (status & STATUS_BLANKING) !== 0,
      isLastPoint: (status & STATUS_LAST_POINT) !== 0,
    }
    if (format === 0 || format === 1) {
      point.colorIndex = bytes[offset]
    } else {
      point.r = bytes[offset]
      point.g = bytes[offset + 1]
      point.b = bytes[offset + 2]
    }
    points.push(point)
  }

  return points
}

export interface IldaFrame {
  format: IldaFormat
  dataName?: string
  companyName?: string
  points: IldaPoint[]
}

// Encodes a complete, real, loadable .ild file: one section per frame
// (header + its points, with the LAST_POINT status bit set on each
// frame's final point per spec) plus the mandatory end-of-file header
// (numRecords === 0). Frame numbers/total-frame counts are filled in
// automatically from the frames' own position/length.
export function encodeIldaFile(frames: IldaFrame[]): Uint8Array {
  const sections = frames.map((frame, i) => {
    const points = frame.points.map((p, pi) => (pi === frame.points.length - 1 ? { ...p, isLastPoint: true } : p))
    const header = encodeIldaHeader({
      format: frame.format,
      dataName: frame.dataName ?? '',
      companyName: frame.companyName ?? 'Hysteresis',
      numRecords: points.length,
      dataNumber: i,
      colorOrTotalFrames: frames.length,
      projectorNumber: 0,
    })
    return { header, points: encodeIldaPoints(frame.format, points) }
  })

  const endOfFile = encodeIldaHeader({
    format: frames[0]?.format ?? 5,
    dataName: '',
    companyName: 'Hysteresis',
    numRecords: 0,
    dataNumber: 0,
    colorOrTotalFrames: 0,
    projectorNumber: 0,
  })

  const totalLength = sections.reduce((sum, s) => sum + s.header.length + s.points.length, 0) + endOfFile.length
  const out = new Uint8Array(totalLength)
  let offset = 0
  for (const s of sections) {
    out.set(s.header, offset)
    offset += s.header.length
    out.set(s.points, offset)
    offset += s.points.length
  }
  out.set(endOfFile, offset)
  return out
}

// Decodes every section up to (not including) the end-of-file header.
export function decodeIldaFile(bytes: Uint8Array): IldaFrame[] {
  const frames: IldaFrame[] = []
  let offset = 0
  while (offset + HEADER_SIZE <= bytes.byteLength) {
    const header = decodeIldaHeader(bytes.subarray(offset, offset + HEADER_SIZE))
    offset += HEADER_SIZE
    if (header.numRecords === 0) break // end-of-file marker
    const size = pointRecordSize(header.format)
    const pointsBytes = bytes.subarray(offset, offset + header.numRecords * size)
    frames.push({ format: header.format, dataName: header.dataName, companyName: header.companyName, points: decodeIldaPoints(header.format, pointsBytes, header.numRecords) })
    offset += pointsBytes.length
  }
  return frames
}
