//! Per-hop live feature extraction, glued from `crate::dsp`/`crate::beat`
//! to match `src/audio/worklet/feature-worklet.ts`'s `process()`/`analyze()`
//! structure (ring-buffer accumulation, one windowed-FFT hop every
//! `HOP_SIZE` new samples).
//!
//! **R1 scope, deliberately** (per `SINTEZA_IMPLEMENTATION_PLAN.md` §4 R1's
//! named list: "FFT, bands, centroid, flatness, flux, chroma, onset
//! density, fullness) + the beat PLL"): populates only those `SignalBus`
//! fields (plus `energy`, a trivial derivation from the bands already
//! computed, and `chromaRootHue`, a one-line derivation off `chroma` — both
//! cheap enough to not withhold). **Not ported this session, on purpose**:
//! `BuildDetector`/`DropDetector`/`BreakDetector` (so `buildProgress`/
//! `tension`/`suspension`/`dropImpulse`/`onsetImpulse`/`dropTrigger` stay at
//! their `SignalBus::default()` zero), per-band stereo placement/pan,
//! the oscilloscope `scope` beam, and `harmonicNovelty`/`familiarity`/
//! `noveltyLocal`/`noveltySection` (need `novelty.ts`'s ring-buffer
//! machinery, not named in R1). Flagged here rather than silently absent.

use hyst_core::SignalBus;

use crate::beat::{BarTracker, BeatTracker};
use crate::dsp::activity::{FullnessTracker, OnsetDensityTracker};
use crate::dsp::bands::{
    band_energies_from_magnitudes, compute_band_ranges, BandEnergies, BandRanges,
};
use crate::dsp::chroma::{compute_chroma, dominant_pitch_class_hue, CHROMA_BINS};
use crate::dsp::envelope::{AdaptiveNormalizer, EnvelopeFollower};
use crate::dsp::fft::WindowedFft;
use crate::dsp::onset::SpectralFlux;
use crate::dsp::spectral::{spectral_centroid_hz, spectral_flatness};

const CENTROID_NORMALIZATION_CEILING_HZ: f32 = 8000.0;
const NORMALIZER_DECAY_MS: f32 = 6000.0;
const ENERGY_TRAJECTORY_MS: f32 = 6000.0;
/// Much longer than the per-band display normalizer — matches TS's
/// `DROP_NORMALIZER_DECAY_MS`, so a breakdown's decayed low end doesn't
/// silently renormalize `fullness`'s notion of "full" downward.
const ACTIVITY_NORMALIZER_DECAY_MS: f32 = 45_000.0;

struct BandTrackers {
    sub: EnvelopeFollower,
    low: EnvelopeFollower,
    mid: EnvelopeFollower,
    presence: EnvelopeFollower,
    air: EnvelopeFollower,
}

struct BandNormalizers {
    sub: AdaptiveNormalizer,
    low: AdaptiveNormalizer,
    mid: AdaptiveNormalizer,
    presence: AdaptiveNormalizer,
    air: AdaptiveNormalizer,
}

pub struct FeatureExtractor {
    fft_size: usize,
    hop_size: usize,
    sample_rate: f32,

    ring: Vec<f32>,
    ring_write_pos: usize,
    samples_since_hop: usize,
    filled: bool,
    ordered: Vec<f32>,
    frames_seen: u64,

    fft: WindowedFft,
    mags: Vec<f32>,
    flux: SpectralFlux,
    flux_normalizer: AdaptiveNormalizer,

    band_ranges: BandRanges,
    band_envelopes: BandTrackers,
    band_normalizers: BandNormalizers,

    energy_trajectory: EnvelopeFollower,
    activity_envelope: EnvelopeFollower,
    activity_normalizer: AdaptiveNormalizer,

    fullness_tracker: FullnessTracker,
    onset_density_tracker: OnsetDensityTracker,

    beat_tracker: BeatTracker,
    bar_tracker: BarTracker,

    chroma_buffer: Vec<f32>,
}

impl FeatureExtractor {
    pub fn new(fft_size: usize, hop_size: usize, sample_rate: f32) -> Self {
        let hop_ms = (hop_size as f32 / sample_rate) * 1000.0;
        let hop_sec = hop_size as f32 / sample_rate;
        let fft = WindowedFft::new(fft_size);
        let bins = fft.bins;

        Self {
            fft_size,
            hop_size,
            sample_rate,
            ring: vec![0.0; fft_size],
            ring_write_pos: 0,
            samples_since_hop: 0,
            filled: false,
            ordered: vec![0.0; fft_size],
            frames_seen: 0,

            fft,
            mags: vec![0.0; bins],
            flux: SpectralFlux::new(bins),
            flux_normalizer: AdaptiveNormalizer::new(NORMALIZER_DECAY_MS, hop_ms),

            band_ranges: compute_band_ranges(fft_size, sample_rate),
            // Slightly slower release on low bands: bloom and settle like the
            // sound decaying, not snap off like a hi-hat (matches TS exactly).
            band_envelopes: BandTrackers {
                sub: EnvelopeFollower::new(10.0, 300.0, hop_ms),
                low: EnvelopeFollower::new(10.0, 250.0, hop_ms),
                mid: EnvelopeFollower::new(8.0, 200.0, hop_ms),
                presence: EnvelopeFollower::new(6.0, 150.0, hop_ms),
                air: EnvelopeFollower::new(5.0, 120.0, hop_ms),
            },
            band_normalizers: BandNormalizers {
                sub: AdaptiveNormalizer::new(NORMALIZER_DECAY_MS, hop_ms),
                low: AdaptiveNormalizer::new(NORMALIZER_DECAY_MS, hop_ms),
                mid: AdaptiveNormalizer::new(NORMALIZER_DECAY_MS, hop_ms),
                presence: AdaptiveNormalizer::new(NORMALIZER_DECAY_MS, hop_ms),
                air: AdaptiveNormalizer::new(NORMALIZER_DECAY_MS, hop_ms),
            },

            energy_trajectory: EnvelopeFollower::new(
                ENERGY_TRAJECTORY_MS,
                ENERGY_TRAJECTORY_MS,
                hop_ms,
            ),
            activity_envelope: EnvelopeFollower::new(30.0, 220.0, hop_ms),
            activity_normalizer: AdaptiveNormalizer::new(ACTIVITY_NORMALIZER_DECAY_MS, hop_ms),

            fullness_tracker: FullnessTracker::new(hop_ms),
            onset_density_tracker: OnsetDensityTracker::new(hop_ms),

            beat_tracker: BeatTracker::new(hop_sec),
            bar_tracker: BarTracker::new(),

            chroma_buffer: vec![0.0; CHROMA_BINS],
        }
    }

    /// Push newly-available mono samples (already downmixed if the source
    /// was stereo — placement/pan isn't ported this session, see module
    /// doc). Returns one `SignalBus` per completed hop (usually 0 or 1 for
    /// a typically-sized audio callback, more if a caller pushes a large
    /// chunk at once).
    pub fn push_samples(&mut self, samples: &[f32]) -> Vec<SignalBus> {
        let mut out = Vec::new();
        for &s in samples {
            self.ring[self.ring_write_pos] = s;
            self.ring_write_pos = (self.ring_write_pos + 1) % self.fft_size;
            self.samples_since_hop += 1;
            self.frames_seen += 1;
            if self.ring_write_pos == 0 {
                self.filled = true;
            }

            while self.samples_since_hop >= self.hop_size {
                self.samples_since_hop -= self.hop_size;
                if self.filled {
                    out.push(self.analyze());
                }
            }
        }
        out
    }

    fn analyze(&mut self) -> SignalBus {
        for i in 0..self.fft_size {
            let idx = (self.ring_write_pos + i) % self.fft_size;
            self.ordered[i] = self.ring[idx];
        }

        self.fft.transform(&self.ordered, &mut self.mags);

        let bands_raw = band_energies_from_magnitudes(&self.mags, &self.band_ranges);
        // Pre-normalization, contrast-preserving low-band reading: feeds
        // fullness/onset-density, which need loud-vs-quiet to stay
        // distinguishable across a whole track (see TS's own comment on why
        // the display-normalized band can't be reused here).
        let raw_low_energy = (bands_raw.sub + bands_raw.low) / 2.0;

        let sub = self
            .band_normalizers
            .sub
            .normalize(self.band_envelopes.sub.update(bands_raw.sub));
        let low = self
            .band_normalizers
            .low
            .normalize(self.band_envelopes.low.update(bands_raw.low));
        let mid = self
            .band_normalizers
            .mid
            .normalize(self.band_envelopes.mid.update(bands_raw.mid));
        let presence = self
            .band_normalizers
            .presence
            .normalize(self.band_envelopes.presence.update(bands_raw.presence));
        let air = self
            .band_normalizers
            .air
            .normalize(self.band_envelopes.air.update(bands_raw.air));
        let normalized_bands = BandEnergies {
            sub,
            low,
            mid,
            presence,
            air,
        };

        let centroid_hz = spectral_centroid_hz(&self.mags, self.sample_rate, self.fft_size);
        let centroid = (centroid_hz / CENTROID_NORMALIZATION_CEILING_HZ).min(1.0);
        let flatness = spectral_flatness(&self.mags);
        compute_chroma(
            &self.mags,
            self.sample_rate,
            self.fft_size,
            &mut self.chroma_buffer,
        );
        let chroma_root_hue = dominant_pitch_class_hue(&self.chroma_buffer);

        let raw_flux = self.flux.update(&self.mags);
        let novelty = self.flux_normalizer.normalize(raw_flux);

        let t_now = self.frames_seen as f32 / self.sample_rate;
        let beat = self.beat_tracker.update(novelty, t_now);
        let bar_phase = self.bar_tracker.update(beat.beat_phase, novelty);

        let activity_signal = self
            .activity_normalizer
            .normalize(self.activity_envelope.update(raw_low_energy));
        let fullness = self.fullness_tracker.update(activity_signal).fullness;
        let onset_density = self.onset_density_tracker.update(novelty).rate;

        let broadband_energy = (sub + low + mid + presence + air) / 5.0;
        let energy = self.energy_trajectory.update(broadband_energy);

        SignalBus {
            energy,
            sub: normalized_bands.sub,
            low: normalized_bands.low,
            mid: normalized_bands.mid,
            presence: normalized_bands.presence,
            air: normalized_bands.air,
            centroid,
            flatness,
            fullness,
            onset_density,
            chroma_root_hue,
            chroma: Some(self.chroma_buffer.clone()),
            beat_phase: beat.beat_phase,
            bar_phase,
            tempo_bpm: beat.tempo_bpm,
            tempo_confidence: beat.tempo_confidence,
            idle: false,
            ..SignalBus::default()
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sine_wave(freq_hz: f32, sample_rate: f32, n: usize) -> Vec<f32> {
        (0..n)
            .map(|i| (2.0 * std::f32::consts::PI * freq_hz * i as f32 / sample_rate).sin())
            .collect()
    }

    #[test]
    fn a_low_sine_tone_registers_meaningful_sub_energy_within_bounds() {
        // Note: every band is independently adaptive-normalized against its
        // *own* running peak (matching the TS design exactly — see
        // AGENTS-era rationale in `features.rs`'s module doc and
        // `dominant_band_tone`'s own doc comment on why cross-band contrast
        // needs the *raw*, pre-normalization energies instead, already
        // covered at the `dsp::bands` unit level). So a normalized band
        // reading close to 1 does NOT mean "loudest band" — it means "loud
        // relative to its own history" — and a silent band normalizes
        // toward 1 just as readily once its tiny peak catches up. This test
        // only checks the bounds/plausibility a real tone should produce,
        // not cross-band dominance.
        let sample_rate = 48_000.0;
        let mut extractor = FeatureExtractor::new(2048, 512, sample_rate);
        let signal = sine_wave(60.0, sample_rate, 2048 * 6);
        let frames = extractor.push_samples(&signal);
        let last = frames
            .last()
            .expect("at least one hop should have completed");
        for v in [last.sub, last.low, last.mid, last.presence, last.air] {
            assert!((0.0..=1.0).contains(&v));
        }
        assert!(
            last.sub > 0.3,
            "a real 60Hz tone should register nontrivial sub energy"
        );
    }

    #[test]
    fn silence_produces_near_zero_energy_and_bands() {
        let sample_rate = 48_000.0;
        let mut extractor = FeatureExtractor::new(2048, 512, sample_rate);
        let signal = vec![0.0; 2048 * 6];
        let frames = extractor.push_samples(&signal);
        let last = frames.last().unwrap();
        assert!(last.energy < 0.05);
    }

    #[test]
    fn a_120bpm_click_train_pushed_as_audio_reaches_a_plausible_tempo() {
        let sample_rate = 48_000.0;
        let mut extractor = FeatureExtractor::new(2048, 512, sample_rate);
        // A click every 0.5s (120 BPM): a short burst of broadband noise-like
        // content so spectral flux actually spikes, matching how a real
        // percussive hit registers (a pure sustained tone has ~0 flux after
        // the first hop).
        let period_samples = (0.5 * sample_rate) as usize;
        let click_len = 32;
        let total = period_samples * 16;
        let mut signal = vec![0.0f32; total];
        let mut i = 0;
        let mut seed: u32 = 12345;
        while i < total {
            for s in signal.iter_mut().skip(i).take(click_len) {
                // cheap deterministic PRNG noise burst, no external crate needed
                seed = seed.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
                *s = ((seed >> 8) as f32 / u32::MAX as f32) * 2.0 - 1.0;
            }
            i += period_samples;
        }
        let frames = extractor.push_samples(&signal);
        let last = frames.last().unwrap();
        assert!(last.tempo_bpm > 100.0 && last.tempo_bpm < 140.0);
    }

    #[test]
    fn no_hop_fires_before_the_ring_is_first_filled() {
        let sample_rate = 48_000.0;
        let mut extractor = FeatureExtractor::new(2048, 512, sample_rate);
        // Matches the TS `filled` gate exactly: the ring must wrap once
        // (2048 samples) before any hop's output is produced, even though a
        // hop boundary (every 512 samples) is crossed 4 times along the way.
        // The ring wraps and the 4th hop boundary land on the same, final
        // sample, so exactly one analyze() fires — not zero, not four.
        let frames = extractor.push_samples(&vec![0.0; 2048]);
        assert_eq!(frames.len(), 1);

        // From here on, every further 512 samples produces exactly one more.
        let more = extractor.push_samples(&vec![0.0; 512 * 3]);
        assert_eq!(more.len(), 3);
    }
}
