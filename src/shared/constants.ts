// Analysis window/hop sizing. At 44.1-48kHz these give a ~42-46ms window
// at a ~11-12ms hop (~86-94Hz analysis rate).
export const FFT_SIZE = 2048
export const HOP_SIZE = 512

// Beat tracking search range (BPM).
export const TEMPO_MIN_BPM = 60
export const TEMPO_MAX_BPM = 190

// Bark-scale-ish band edges (Hz), splitting the spectrum into five
// perceptual bands: sub, low, mid, presence, air.
export const BAND_EDGES_HZ = [20, 80, 250, 2000, 6000, 20000] as const
