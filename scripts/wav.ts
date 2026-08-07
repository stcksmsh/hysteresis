import { readFileSync } from 'node:fs'

export interface DecodedWav {
  sampleRate: number
  channels: Float32Array[]
  duration: number
}

// Minimal RIFF/WAVE reader for scripts/analyze.ts. Only needs to handle what
// a typical DAW bounce writes — PCM 16/24/32-bit and 32-bit float — so it
// stays deliberately small rather than pulling in a dependency.
export function decodeWavFile(path: string): DecodedWav {
  const buf = readFileSync(path)
  if (buf.toString('ascii', 0, 4) !== 'RIFF' || buf.toString('ascii', 8, 12) !== 'WAVE') {
    throw new Error(`${path}: not a RIFF/WAVE file`)
  }

  let format = 1
  let channelCount = 0
  let sampleRate = 0
  let bitsPerSample = 0
  let dataOffset = -1
  let dataLength = 0

  let offset = 12
  while (offset + 8 <= buf.length) {
    const id = buf.toString('ascii', offset, offset + 4)
    const size = buf.readUInt32LE(offset + 4)
    const body = offset + 8

    if (id === 'fmt ') {
      format = buf.readUInt16LE(body)
      channelCount = buf.readUInt16LE(body + 2)
      sampleRate = buf.readUInt32LE(body + 4)
      bitsPerSample = buf.readUInt16LE(body + 14)
      // WAVE_FORMAT_EXTENSIBLE stores the real format in the GUID's first two bytes.
      if (format === 0xfffe && size >= 26) format = buf.readUInt16LE(body + 24)
    } else if (id === 'data') {
      dataOffset = body
      dataLength = size
    }

    offset = body + size + (size % 2) // chunks are word-aligned
  }

  if (dataOffset < 0 || channelCount === 0) throw new Error(`${path}: missing fmt/data chunk`)

  const bytesPerSample = bitsPerSample / 8
  const frameCount = Math.floor(dataLength / (bytesPerSample * channelCount))
  const channels: Float32Array[] = []
  for (let c = 0; c < channelCount; c++) channels.push(new Float32Array(frameCount))

  const readSample = (at: number): number => {
    if (format === 3) return bitsPerSample === 64 ? buf.readDoubleLE(at) : buf.readFloatLE(at)
    if (bitsPerSample === 16) return buf.readInt16LE(at) / 32768
    if (bitsPerSample === 24) {
      const v = buf.readUInt8(at) | (buf.readUInt8(at + 1) << 8) | (buf.readInt8(at + 2) << 16)
      return v / 8388608
    }
    if (bitsPerSample === 32) return buf.readInt32LE(at) / 2147483648
    if (bitsPerSample === 8) return (buf.readUInt8(at) - 128) / 128
    throw new Error(`${path}: unsupported bit depth ${bitsPerSample}`)
  }

  for (let i = 0; i < frameCount; i++) {
    const base = dataOffset + i * bytesPerSample * channelCount
    for (let c = 0; c < channelCount; c++) {
      channels[c][i] = readSample(base + c * bytesPerSample)
    }
  }

  return { sampleRate, channels, duration: frameCount / sampleRate }
}
