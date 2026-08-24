// Chromagram (AGENTS.md §4.2/§4.5 step 4) — a 12-bin pitch-class energy
// vector, the one sense this pipeline had entirely missing before (no
// harmonic signal existed anywhere in Layer 1). Cheap, standard MIR: fold
// every FFT bin's energy into its nearest equal-tempered pitch class
// (0=C, 1=C#, ... 9=A, ... 11=B — MIDI-note-mod-12 convention, so A440 at
// MIDI 69 lands on pitch class 9), then normalize. Enables harmonic novelty
// (key/chord changes as a boundary cue — one of the EDM switch-point
// predictors §4.1 cites) and a genuinely new visual driver (pitch-class ->
// hue/rotation).
export const CHROMA_BINS = 12

// Bins outside a plausible musical range are skipped: sub-audio energy
// (hum, DC leakage) below C1 has no real pitch-class meaning and would
// dominate the accumulation (1/f-shaped spectra are bass-heavy), and
// anything above C8 is past where chroma is a meaningful timbral cue for
// this project's material.
const MIN_HZ = 32.7 // C1
const MAX_HZ = 4186 // C8

function freqToPitchClass(freqHz: number): number {
  // MIDI note number relative to A4=440Hz (MIDI 69); mod 12 with A4's own
  // class (9) already baked in by using 69 as the reference, so pitch class
  // 0 lands on C the way every other MIDI-based convention expects.
  const midi = 69 + 12 * Math.log2(freqHz / 440)
  const pc = Math.round(midi) % 12
  return pc < 0 ? pc + 12 : pc
}

// Reusable output buffer, same convention as the rest of this worklet
// (feature-worklet.ts writes into pre-allocated Float32Arrays every hop to
// avoid per-hop garbage) — pass one in rather than allocating here.
export function computeChroma(mags: Float32Array, sampleRate: number, fftSize: number, out: Float32Array): void {
  out.fill(0)
  const binHz = sampleRate / fftSize
  let total = 0
  for (let i = 1; i < mags.length; i++) {
    const freq = i * binHz
    if (freq < MIN_HZ || freq > MAX_HZ) continue
    const pc = freqToPitchClass(freq)
    out[pc] += mags[i]
    total += mags[i]
  }
  if (total > 1e-9) {
    for (let i = 0; i < CHROMA_BINS; i++) out[i] /= total
  }
}

// The pitch class with the most energy, as a 0..1 hue-ready value (not a
// hue itself — the caller picks the actual color mapping) — AGENTS.md
// §4.4's `chromaRootHue`. Returns 0 (arbitrary) for a silent/flat frame.
export function dominantPitchClassHue(chroma: Float32Array): number {
  let best = 0
  let bestValue = chroma[0] ?? 0
  for (let i = 1; i < chroma.length; i++) {
    if (chroma[i] > bestValue) {
      best = i
      bestValue = chroma[i]
    }
  }
  return best / CHROMA_BINS
}
