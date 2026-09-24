//! Ported from `src/audio/worklet/spectral.ts`.

/// Spectral centroid in Hz. Bin 0 (DC) is skipped to avoid biasing the
/// average toward zero.
pub fn spectral_centroid_hz(mags: &[f32], sample_rate: f32, fft_size: usize) -> f32 {
    let bin_hz = sample_rate / fft_size as f32;
    let mut weighted_sum = 0.0f32;
    let mut mag_sum = 0.0f32;
    for (i, &m) in mags.iter().enumerate().skip(1) {
        weighted_sum += i as f32 * bin_hz * m;
        mag_sum += m;
    }
    if mag_sum > 1e-9 {
        weighted_sum / mag_sum
    } else {
        0.0
    }
}

/// Spectral flatness (Wiener entropy): geometric mean / arithmetic mean of
/// the magnitude spectrum. Near 0 = tonal, near 1 = noisy/broadband.
pub fn spectral_flatness(mags: &[f32]) -> f32 {
    let mut log_sum = 0.0f32;
    let mut sum = 0.0f32;
    let mut n = 0usize;
    for &m in mags.iter().skip(1) {
        if m > 1e-9 {
            log_sum += m.ln();
            sum += m;
            n += 1;
        }
    }
    if n == 0 || sum == 0.0 {
        return 0.0;
    }
    let geo_mean = (log_sum / n as f32).exp();
    let arith_mean = sum / n as f32;
    if arith_mean > 1e-9 {
        geo_mean / arith_mean
    } else {
        0.0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn centroid_of_a_single_high_bin_lands_near_its_frequency() {
        let mut mags = vec![0.0; 1025];
        let bin = 500;
        mags[bin] = 1.0;
        let centroid = spectral_centroid_hz(&mags, 48_000.0, 2048);
        let bin_hz = 48_000.0 / 2048.0;
        assert!((centroid - bin as f32 * bin_hz).abs() < 1.0);
    }

    #[test]
    fn flatness_of_a_single_tone_is_low() {
        // Background must clear the function's own `> 1e-9` inclusion
        // threshold (else those bins are excluded from both means entirely,
        // degenerating to a trivial single-bin ratio of 1) while still being
        // negligible next to the peak — a realistic tiny noise floor.
        let mut mags = vec![1e-6; 1025];
        mags[100] = 1.0;
        assert!(spectral_flatness(&mags) < 0.1);
    }

    #[test]
    fn flatness_of_flat_noise_is_high() {
        let mags = vec![1.0; 1025];
        assert!(spectral_flatness(&mags) > 0.9);
    }
}
