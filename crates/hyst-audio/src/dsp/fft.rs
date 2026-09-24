//! Windowed FFT, ported from `src/audio/worklet/fft.ts`. Own Hann window
//! (not a library default) so the exact window function matches the TS
//! original bin-for-bin; `realfft` (built on `rustfft`) stands in for
//! `fft.js`'s `realTransform`, and its bin convention (`size/2 + 1`,
//! DC..Nyquist) already matches `fft.js`'s exactly, so `bins` needs no
//! reinterpretation.

use realfft::{num_complex::Complex32, RealFftPlanner, RealToComplex};
use std::sync::Arc;

pub struct WindowedFft {
    pub size: usize,
    pub bins: usize,
    fft: Arc<dyn RealToComplex<f32>>,
    window: Vec<f32>,
    windowed: Vec<f32>,
    spectrum: Vec<Complex32>,
}

impl WindowedFft {
    pub fn new(size: usize) -> Self {
        let mut planner = RealFftPlanner::<f32>::new();
        let fft = planner.plan_fft_forward(size);
        let spectrum = fft.make_output_vec();
        let bins = spectrum.len();
        debug_assert_eq!(bins, size / 2 + 1);
        Self {
            size,
            bins,
            fft,
            window: make_hann_window(size),
            windowed: vec![0.0; size],
            spectrum,
        }
    }

    /// `samples` must have length `self.size`. `magnitude_out` must have
    /// length `self.bins`; filled with the magnitude spectrum (DC..Nyquist).
    pub fn transform(&mut self, samples: &[f32], magnitude_out: &mut [f32]) {
        debug_assert_eq!(samples.len(), self.size);
        debug_assert_eq!(magnitude_out.len(), self.bins);
        for ((w, &s), &win) in self.windowed.iter_mut().zip(samples).zip(&self.window) {
            *w = s * win;
        }
        self.fft
            .process(&mut self.windowed, &mut self.spectrum)
            .expect("fixed-size buffers always match the planned transform");
        for (out, spec) in magnitude_out.iter_mut().zip(&self.spectrum) {
            *out = spec.norm();
        }
    }
}

fn make_hann_window(size: usize) -> Vec<f32> {
    (0..size)
        .map(|i| 0.5 - 0.5 * (2.0 * std::f32::consts::PI * i as f32 / (size as f32 - 1.0)).cos())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pure_tone_peaks_at_the_right_bin() {
        let size = 2048;
        let sample_rate = 48_000.0;
        let freq_hz = 1000.0;
        let mut fft = WindowedFft::new(size);
        let samples: Vec<f32> = (0..size)
            .map(|i| (2.0 * std::f32::consts::PI * freq_hz * i as f32 / sample_rate).sin())
            .collect();
        let mut mags = vec![0.0; fft.bins];
        fft.transform(&samples, &mut mags);

        let expected_bin = (freq_hz * size as f32 / sample_rate).round() as usize;
        let peak_bin = mags
            .iter()
            .enumerate()
            .max_by(|a, b| a.1.partial_cmp(b.1).unwrap())
            .map(|(i, _)| i)
            .unwrap();
        assert!(
            (peak_bin as i64 - expected_bin as i64).abs() <= 1,
            "expected peak near bin {expected_bin}, got {peak_bin}"
        );
    }

    #[test]
    fn silence_produces_near_zero_magnitude() {
        let size = 2048;
        let mut fft = WindowedFft::new(size);
        let samples = vec![0.0; size];
        let mut mags = vec![0.0; fft.bins];
        fft.transform(&samples, &mut mags);
        assert!(mags.iter().all(|&m| m < 1e-5));
    }

    #[test]
    fn bins_matches_size_over_2_plus_1() {
        let fft = WindowedFft::new(2048);
        assert_eq!(fft.bins, 1025);
    }
}
