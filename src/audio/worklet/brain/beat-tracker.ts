import { TEMPO_MIN_BPM, TEMPO_MAX_BPM } from '../../../shared/constants'

const HISTORY_SEC = 8
const TEMPO_UPDATE_SEC = 0.5
const TEMPO_SMOOTHING = 0.3 // fraction moved toward each new estimate per update
const OCTAVE_BIAS_STRENGTH = 10 // down-weights lags far (in octaves) from the previous estimate
const ONSET_THRESHOLD = 0.4 // normalized novelty above which a hop counts as an onset for phase-locking
const PLL_GAIN = 0.2 // how hard each onset nudges the phase anchor (0=no correction, 1=hard snap)

export interface BeatTrackerOutput {
  tempoBpm: number
  tempoConfidence: number
  beatPhase: number
}

// Tempo + a phase-locked oscillator that free-runs from tempo+time alone and
// only receives small proportional nudges when onsets are present (PLL-style)
// — so it glides into alignment and holds a steady grid with zero correction
// input during breaks with no percussion. This is the one requirement no
// off-the-shelf "analyze(wholeBuffer) -> one BPM" library provides.
export class BeatTracker {
  private noveltyBuffer: Float32Array
  private writeIdx = 0
  private filled = false
  private hopSec: number
  private hopsSinceTempoUpdate = 0
  private tempoUpdateIntervalHops: number

  private tempoBpm = 120 // sane default prior before enough history accumulates
  private tempoConfidence = 0
  private beatPeriodSec = 60 / 120
  private phaseAnchorSec = 0

  constructor(hopSec: number) {
    this.hopSec = hopSec
    this.noveltyBuffer = new Float32Array(Math.round(HISTORY_SEC / hopSec))
    this.tempoUpdateIntervalHops = Math.round(TEMPO_UPDATE_SEC / hopSec)
  }

  update(novelty: number, tNow: number): BeatTrackerOutput {
    this.noveltyBuffer[this.writeIdx] = novelty
    this.writeIdx = (this.writeIdx + 1) % this.noveltyBuffer.length
    if (this.writeIdx === 0) this.filled = true

    this.hopsSinceTempoUpdate++
    if (this.filled && this.hopsSinceTempoUpdate >= this.tempoUpdateIntervalHops) {
      this.hopsSinceTempoUpdate = 0
      this.updateTempoEstimate()
    }

    const beatPhase = this.computeBeatPhase(tNow)
    if (novelty > ONSET_THRESHOLD) {
      this.nudgePhase(beatPhase)
    }

    return { tempoBpm: this.tempoBpm, tempoConfidence: this.tempoConfidence, beatPhase }
  }

  private computeBeatPhase(tNow: number): number {
    const phase = (tNow - this.phaseAnchorSec) / this.beatPeriodSec
    return phase - Math.floor(phase)
  }

  private nudgePhase(beatPhase: number): void {
    // signed distance to the nearest beat boundary (0/1), in (-0.5, 0.5]
    let error = beatPhase
    if (error > 0.5) error -= 1
    this.phaseAnchorSec += error * this.beatPeriodSec * PLL_GAIN
  }

  private updateTempoEstimate(): void {
    const minLag = Math.round(60 / TEMPO_MAX_BPM / this.hopSec)
    const maxLag = Math.round(60 / TEMPO_MIN_BPM / this.hopSec)
    const buf = this.noveltyBuffer
    const n = buf.length
    const prevLag = this.beatPeriodSec / this.hopSec

    let selfEnergy = 0
    for (let i = 0; i < n; i++) selfEnergy += buf[i] * buf[i]
    if (selfEnergy < 1e-9) return

    let bestLag = -1
    let bestScore = -Infinity
    for (let lag = minLag; lag <= maxLag; lag++) {
      let sum = 0
      for (let i = 0; i < n; i++) {
        sum += buf[i] * buf[(i - lag + n) % n]
      }
      // Octave tie-breaking: bias toward continuity with the previous
      // estimate so tempo doesn't flicker between a lag and its half/double.
      const octaveDist = Math.log2(lag / prevLag)
      const biasedScore = sum * Math.exp(-octaveDist * octaveDist * OCTAVE_BIAS_STRENGTH)
      if (biasedScore > bestScore) {
        bestScore = biasedScore
        bestLag = lag
      }
    }

    if (bestLag > 0) {
      const newTempo = 60 / (bestLag * this.hopSec)
      this.tempoBpm = this.tempoBpm * (1 - TEMPO_SMOOTHING) + newTempo * TEMPO_SMOOTHING
      this.beatPeriodSec = 60 / this.tempoBpm
      this.tempoConfidence = Math.max(0, Math.min(1, bestScore / selfEnergy))
    }
  }
}

const SLOT_COUNT = 4 // assumes 4/4 time — see design-doc risk note on bar-phase confidence
const SLOT_LEARNING_RATE = 0.2

// Best-effort downbeat guess: tracks which of the 4 beat-in-bar positions
// tends to carry the strongest onset, and re-anchors "beat 1" to it each
// bar. Lower-confidence than beat-phase itself by nature of the 4/4
// assumption and heuristic re-anchoring.
export class BarTracker {
  private beatCount = -1
  private lastPhase = 0
  private slotStrength = new Float32Array(SLOT_COUNT)
  private downbeatSlot = 0
  private peakNoveltySinceBeat = 0

  update(beatPhase: number, novelty: number): number {
    this.peakNoveltySinceBeat = Math.max(this.peakNoveltySinceBeat, novelty)

    if (beatPhase < this.lastPhase - 0.5) {
      this.beatCount++
      const slot = this.beatCount % SLOT_COUNT
      this.slotStrength[slot] =
        this.slotStrength[slot] * (1 - SLOT_LEARNING_RATE) + this.peakNoveltySinceBeat * SLOT_LEARNING_RATE
      this.peakNoveltySinceBeat = 0

      if (slot === SLOT_COUNT - 1) {
        let best = 0
        for (let i = 1; i < SLOT_COUNT; i++) {
          if (this.slotStrength[i] > this.slotStrength[best]) best = i
        }
        this.downbeatSlot = best
      }
    }
    this.lastPhase = beatPhase

    if (this.beatCount < 0) return beatPhase / SLOT_COUNT
    const beatInBar = (((this.beatCount - this.downbeatSlot) % SLOT_COUNT) + SLOT_COUNT) % SLOT_COUNT
    return (beatInBar + beatPhase) / SLOT_COUNT
  }
}
