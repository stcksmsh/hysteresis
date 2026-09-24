//! Minimal WAV decoding via `hound` into interleaved `f32`. No TS
//! precedent — the browser package never decoded audio itself, the host's
//! `<audio>`/`AudioContext` did. Resampling to match the output device's
//! rate is explicitly NOT done here (flagged, see `Playback::new`) — this
//! first pass requires the file's sample rate to match the device's.

use std::path::Path;

#[derive(Debug, thiserror::Error)]
pub enum WavSourceError {
    #[error("failed to open/read WAV at {path}: {source}")]
    Hound {
        path: String,
        #[source]
        source: hound::Error,
    },
}

pub struct WavSource {
    pub sample_rate: u32,
    pub channels: u16,
    /// Interleaved, e.g. `[L0, R0, L1, R1, ...]` for stereo.
    pub samples: Vec<f32>,
}

impl WavSource {
    pub fn load(path: impl AsRef<Path>) -> Result<Self, WavSourceError> {
        let path_ref = path.as_ref();
        let mut reader =
            hound::WavReader::open(path_ref).map_err(|source| WavSourceError::Hound {
                path: path_ref.display().to_string(),
                source,
            })?;
        let spec = reader.spec();

        let samples: Result<Vec<f32>, hound::Error> = match spec.sample_format {
            hound::SampleFormat::Float => reader.samples::<f32>().collect(),
            hound::SampleFormat::Int => {
                let max_amplitude = (1i64 << (spec.bits_per_sample - 1)) as f32;
                reader
                    .samples::<i32>()
                    .map(|s| s.map(|v| v as f32 / max_amplitude))
                    .collect()
            }
        };
        let samples = samples.map_err(|source| WavSourceError::Hound {
            path: path_ref.display().to_string(),
            source,
        })?;

        Ok(Self {
            sample_rate: spec.sample_rate,
            channels: spec.channels,
            samples,
        })
    }

    pub fn duration_secs(&self) -> f64 {
        let frames = self.samples.len() as f64 / self.channels.max(1) as f64;
        frames / self.sample_rate as f64
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn write_test_wav(path: &std::path::Path, sample_rate: u32, channels: u16, frames: usize) {
        let spec = hound::WavSpec {
            channels,
            sample_rate,
            bits_per_sample: 16,
            sample_format: hound::SampleFormat::Int,
        };
        let mut writer = hound::WavWriter::create(path, spec).unwrap();
        for i in 0..frames {
            for c in 0..channels {
                let v = ((i + c as usize) % 100) as i16 - 50;
                writer.write_sample(v).unwrap();
            }
        }
        writer.finalize().unwrap();
    }

    #[test]
    fn loads_a_mono_16bit_wav() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("mono.wav");
        write_test_wav(&path, 48_000, 1, 1000);
        let source = WavSource::load(&path).unwrap();
        assert_eq!(source.sample_rate, 48_000);
        assert_eq!(source.channels, 1);
        assert_eq!(source.samples.len(), 1000);
    }

    #[test]
    fn loads_a_stereo_16bit_wav_interleaved() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("stereo.wav");
        write_test_wav(&path, 44_100, 2, 500);
        let source = WavSource::load(&path).unwrap();
        assert_eq!(source.channels, 2);
        assert_eq!(source.samples.len(), 1000); // 500 frames * 2 channels
        assert!((source.duration_secs() - 500.0 / 44_100.0).abs() < 1e-9);
    }

    #[test]
    fn errors_cleanly_on_a_missing_file() {
        let result = WavSource::load("/definitely/not/a/real/path.wav");
        assert!(result.is_err());
    }
}
