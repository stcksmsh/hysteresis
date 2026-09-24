//! Chromagram, ported from `src/audio/worklet/chroma.ts`.

pub const CHROMA_BINS: usize = 12;

const MIN_HZ: f32 = 32.7; // C1
const MAX_HZ: f32 = 4186.0; // C8

fn freq_to_pitch_class(freq_hz: f32) -> usize {
    let midi = 69.0 + 12.0 * (freq_hz / 440.0).log2();
    let pc = midi.round().rem_euclid(12.0);
    pc as usize
}

/// Folds every FFT bin's energy into its nearest equal-tempered pitch class
/// (0=C .. 11=B), normalized. `out` must have length `CHROMA_BINS`.
pub fn compute_chroma(mags: &[f32], sample_rate: f32, fft_size: usize, out: &mut [f32]) {
    out.fill(0.0);
    let bin_hz = sample_rate / fft_size as f32;
    let mut total = 0.0f32;
    for (i, &m) in mags.iter().enumerate().skip(1) {
        let freq = i as f32 * bin_hz;
        if !(MIN_HZ..=MAX_HZ).contains(&freq) {
            continue;
        }
        let pc = freq_to_pitch_class(freq);
        out[pc] += m;
        total += m;
    }
    if total > 1e-9 {
        for v in out.iter_mut() {
            *v /= total;
        }
    }
}

/// The pitch class with the most energy, as a 0..1 hue-ready value.
pub fn dominant_pitch_class_hue(chroma: &[f32]) -> f32 {
    let mut best = 0;
    let mut best_value = chroma.first().copied().unwrap_or(0.0);
    for (i, &v) in chroma.iter().enumerate().skip(1) {
        if v > best_value {
            best = i;
            best_value = v;
        }
    }
    best as f32 / CHROMA_BINS as f32
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a440_lands_on_pitch_class_9_a() {
        // one bin exactly at 440Hz
        let fft_size = 2048;
        let sample_rate = 48_000.0;
        let bin_hz = sample_rate / fft_size as f32;
        let bin = (440.0 / bin_hz).round() as usize;
        let mut mags = vec![0.0; fft_size / 2 + 1];
        mags[bin] = 1.0;
        let mut chroma = vec![0.0; CHROMA_BINS];
        compute_chroma(&mags, sample_rate, fft_size, &mut chroma);
        let dominant = chroma
            .iter()
            .enumerate()
            .max_by(|a, b| a.1.partial_cmp(b.1).unwrap())
            .map(|(i, _)| i)
            .unwrap();
        assert_eq!(dominant, 9);
    }

    #[test]
    fn chroma_normalizes_to_sum_1() {
        let fft_size = 2048;
        let sample_rate = 48_000.0;
        let mut mags = vec![0.01; fft_size / 2 + 1];
        mags[300] = 5.0;
        let mut chroma = vec![0.0; CHROMA_BINS];
        compute_chroma(&mags, sample_rate, fft_size, &mut chroma);
        let sum: f32 = chroma.iter().sum();
        assert!((sum - 1.0).abs() < 1e-3);
    }

    #[test]
    fn dominant_hue_matches_the_loudest_bin() {
        let mut chroma = vec![0.0; CHROMA_BINS];
        chroma[4] = 0.9;
        assert_eq!(dominant_pitch_class_hue(&chroma), 4.0 / 12.0);
    }
}
