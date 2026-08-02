import { WindowedFFT } from '../../src/audio/worklet/fft'
import { spectralCentroidHz } from '../../src/audio/worklet/spectral'
import { SpectralFlux } from '../../src/audio/worklet/onset'
import { EnvelopeFollower } from '../../src/audio/worklet/envelope'
import { FFT_SIZE, HOP_SIZE } from '../../src/shared/constants'
import type { DecodedWav } from './wav'

export interface StemHit {
  t: number
  level: number
  tone: number
}

export interface StemAnalysis {
  events: StemHit[]
  envelopeLevel: Uint8Array
  envelopeTone: Uint8Array
  envelopeRate: number
  medianTone: number
}

const CENTROID_CEILING_HZ = 8000
const ONSET_THRESHOLD = 0.3
// Exported: structure.ts's baked buildProgress/tension curves must share
// this rate with the per-track envelopes above, since Timeline.envelopes
// carries one `rate` for all of them.
export const ENVELOPE_RATE_HZ = 20

function percentile(sorted: Float32Array, p: number): number {
  if (sorted.length === 0) return 0
  const idx = Math.min(sorted.length - 1, Math.floor(p * sorted.length))
  return sorted[idx]
}

// Offline analysis of one isolated stem. Unlike the realtime worklet path,
// the whole signal is available up front, so normalisation uses a real
// percentile of the entire file instead of a causal adaptive peak — there is
// no reason to approximate what full knowledge of the file already gives us
// for free.
export function analyzeStem(wav: DecodedWav): StemAnalysis {
  const { sampleRate, channels } = wav
  const frameCount = channels[0].length
  const mono = new Float32Array(frameCount)
  for (let i = 0; i < frameCount; i++) {
    let sum = 0
    for (const c of channels) sum += c[i]
    mono[i] = sum / channels.length
  }

  const fft = new WindowedFFT(FFT_SIZE)
  const mags = new Float32Array(fft.bins)
  const flux = new SpectralFlux(fft.bins)
  const hopSec = HOP_SIZE / sampleRate
  const levelFollower = new EnvelopeFollower(15, 200, hopSec * 1000)

  const totalHops = Math.max(0, Math.floor((frameCount - FFT_SIZE) / HOP_SIZE) + 1)
  const window = new Float32Array(FFT_SIZE)
  const rawLevel = new Float32Array(totalHops)
  // Instantaneous, un-followed RMS per hop. `rawLevel`'s 200ms release makes
  // it stay "elevated" long after a short transient's actual content is gone
  // — fine for a display envelope, but it means gating on rawLevel picks up
  // mostly-silent decay-tail hops. Tone activity gating needs the instant
  // value instead, or a percussive stem's medianTone collapses to silence.
  const rawInstantLevel = new Float32Array(totalHops)
  const rawFlux = new Float32Array(totalHops)
  const rawTone = new Float32Array(totalHops)

  for (let h = 0; h < totalHops; h++) {
    const start = h * HOP_SIZE
    window.fill(0)
    window.set(mono.subarray(start, Math.min(frameCount, start + FFT_SIZE)))
    fft.transform(window, mags)

    let sumSq = 0
    const end = Math.min(frameCount, start + HOP_SIZE)
    for (let i = start; i < end; i++) sumSq += mono[i] * mono[i]
    const rms = Math.sqrt(sumSq / Math.max(1, end - start))

    rawLevel[h] = levelFollower.update(rms)
    rawInstantLevel[h] = rms
    rawFlux[h] = flux.update(mags)
    rawTone[h] = Math.min(1, spectralCentroidHz(mags, sampleRate, FFT_SIZE) / CENTROID_CEILING_HZ)
  }

  const levelPeak = percentile(Float32Array.from(rawLevel).sort(), 0.98) || 1e-6
  const instantPeak = percentile(Float32Array.from(rawInstantLevel).sort(), 0.98) || 1e-6
  const fluxPeak = percentile(Float32Array.from(rawFlux).sort(), 0.98) || 1e-6

  const events: StemHit[] = []
  let wasAbove = false
  for (let h = 0; h < totalHops; h++) {
    const novelty = Math.min(1, rawFlux[h] / fluxPeak)
    const above = novelty > ONSET_THRESHOLD
    if (above && !wasAbove) {
      events.push({
        t: (h * HOP_SIZE) / sampleRate,
        level: Math.min(1, Math.max(rawLevel[h] / levelPeak, novelty)),
        tone: rawTone[h],
      })
    }
    wasAbove = above
  }

  const hopsPerEnvelopeSample = Math.max(1, Math.round(1 / ENVELOPE_RATE_HZ / hopSec))
  const envelopeLength = Math.ceil(totalHops / hopsPerEnvelopeSample)
  const envelopeLevel = new Uint8Array(envelopeLength)
  const envelopeTone = new Uint8Array(envelopeLength)
  for (let i = 0; i < envelopeLength; i++) {
    const start = i * hopsPerEnvelopeSample
    const end = Math.min(totalHops, start + hopsPerEnvelopeSample)
    let lsum = 0
    let tsum = 0
    let n = 0
    for (let h = start; h < end; h++) {
      lsum += Math.min(1, rawLevel[h] / levelPeak)
      tsum += rawTone[h]
      n++
    }
    envelopeLevel[i] = n > 0 ? Math.round((lsum / n) * 255) : 0
    envelopeTone[i] = n > 0 ? Math.round((tsum / n) * 255) : 0
  }

  // Median over the *whole* file would be dominated by silence for anything
  // percussive and sparse (a hat firing 20ms out of every 500ms is silent
  // 96% of the time), collapsing every track's home height to "silence's
  // tone". Restrict the median to hops where the stem is actually sounding.
  const activeTones: number[] = []
  const activityFloor = 0.15
  for (let h = 0; h < totalHops; h++) {
    if (rawInstantLevel[h] / instantPeak > activityFloor) activeTones.push(rawTone[h])
  }
  const toneSample = activeTones.length > 0 ? Float32Array.from(activeTones) : rawTone
  const sortedTone = toneSample.slice().sort()
  const medianTone = percentile(sortedTone, 0.5)

  return { events, envelopeLevel, envelopeTone, envelopeRate: ENVELOPE_RATE_HZ, medianTone }
}
