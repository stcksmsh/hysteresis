//! Spectral flux, ported from `src/audio/worklet/onset.ts`.

pub struct SpectralFlux {
    prev: Vec<f32>,
}

impl SpectralFlux {
    pub fn new(bins: usize) -> Self {
        Self {
            prev: vec![0.0; bins],
        }
    }

    /// Sum of positive bin-to-bin magnitude increases since the last call.
    pub fn update(&mut self, mags: &[f32]) -> f32 {
        let mut flux = 0.0f32;
        for (i, &m) in mags.iter().enumerate() {
            let diff = m - self.prev[i];
            if diff > 0.0 {
                flux += diff;
            }
            self.prev[i] = m;
        }
        flux
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn silence_to_silence_has_zero_flux() {
        let mut flux = SpectralFlux::new(4);
        assert_eq!(flux.update(&[0.0, 0.0, 0.0, 0.0]), 0.0);
        assert_eq!(flux.update(&[0.0, 0.0, 0.0, 0.0]), 0.0);
    }

    #[test]
    fn a_rise_registers_flux_a_decay_does_not() {
        let mut flux = SpectralFlux::new(2);
        flux.update(&[0.0, 0.0]);
        let rise = flux.update(&[1.0, 0.0]);
        assert!(rise > 0.0);
        let decay = flux.update(&[0.0, 0.0]);
        assert_eq!(decay, 0.0);
    }
}
