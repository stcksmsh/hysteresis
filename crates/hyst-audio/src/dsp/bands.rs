//! Perceptual band split, ported from `src/audio/worklet/bands.ts`.

pub const BAND_EDGES_HZ: [f32; 6] = [20.0, 80.0, 250.0, 2000.0, 6000.0, 20000.0];
pub const BAND_NAMES: [&str; 5] = ["sub", "low", "mid", "presence", "air"];

#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub struct BandEnergies {
    pub sub: f32,
    pub low: f32,
    pub mid: f32,
    pub presence: f32,
    pub air: f32,
}

impl BandEnergies {
    pub fn get(&self, index: usize) -> f32 {
        match index {
            0 => self.sub,
            1 => self.low,
            2 => self.mid,
            3 => self.presence,
            _ => self.air,
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub struct BandRanges {
    /// (lo, hi) bin index pairs, in `BAND_NAMES` order.
    pub ranges: [(usize, usize); 5],
}

/// Bin ranges depend on sample rate, so this is computed once per audio
/// session rather than hardcoded.
pub fn compute_band_ranges(fft_size: usize, sample_rate: f32) -> BandRanges {
    let bin_hz = sample_rate / fft_size as f32;
    let edge_bins: Vec<usize> = BAND_EDGES_HZ
        .iter()
        .map(|hz| (hz / bin_hz).round() as usize)
        .collect();
    let mut ranges = [(0usize, 0usize); 5];
    for i in 0..5 {
        let lo = edge_bins[i];
        let hi = (edge_bins[i + 1]).max(lo + 1);
        ranges[i] = (lo, hi);
    }
    BandRanges { ranges }
}

/// RMS magnitude per band (raw, pre-envelope, pre-normalization).
pub fn band_energies_from_magnitudes(mags: &[f32], ranges: &BandRanges) -> BandEnergies {
    let mut out = BandEnergies::default();
    for (i, &(lo, hi)) in ranges.ranges.iter().enumerate() {
        let end = hi.min(mags.len());
        let mut sum_sq = 0.0f32;
        let mut count = 0usize;
        for &m in &mags[lo.min(end)..end] {
            sum_sq += m * m;
            count += 1;
        }
        let value = if count > 0 {
            (sum_sq / count as f32).sqrt()
        } else {
            0.0
        };
        match i {
            0 => out.sub = value,
            1 => out.low = value,
            2 => out.mid = value,
            3 => out.presence = value,
            _ => out.air = value,
        }
    }
    out
}

/// Dominant band as a 0..1 position across the spectrum (sub -> air).
pub fn dominant_band_tone(bands: &BandEnergies) -> f32 {
    let mut best_index = 0;
    let mut best_value = -1.0f32;
    for i in 0..5 {
        let v = bands.get(i);
        if v > best_value {
            best_value = v;
            best_index = i;
        }
    }
    best_index as f32 / 4.0
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ranges_are_monotonic_and_cover_low_to_high() {
        let ranges = compute_band_ranges(2048, 48_000.0);
        for i in 0..4 {
            assert!(ranges.ranges[i].1 <= ranges.ranges[i + 1].0 + 1);
        }
        assert!(ranges.ranges[0].0 <= ranges.ranges[4].1);
    }

    #[test]
    fn energy_in_sub_range_only_shows_up_in_sub_band() {
        let ranges = compute_band_ranges(2048, 48_000.0);
        let mut mags = vec![0.0; 1025];
        let (lo, _hi) = ranges.ranges[0];
        mags[lo] = 1.0;
        let bands = band_energies_from_magnitudes(&mags, &ranges);
        assert!(bands.sub > 0.0);
        assert_eq!(bands.mid, 0.0);
        assert_eq!(bands.air, 0.0);
    }

    #[test]
    fn dominant_band_tone_picks_the_loudest_band() {
        let bands = BandEnergies {
            sub: 0.1,
            low: 0.1,
            mid: 0.1,
            presence: 0.9,
            air: 0.1,
        };
        assert_eq!(dominant_band_tone(&bands), 3.0 / 4.0);
    }
}
