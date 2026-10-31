//! B1 baseline (docs/BRAIN_SPEC.md 2.1): run the hyst-audio PLL (`BeatTracker`, inside `FeatureExtractor`) over
//! WAV files and print its beat times, one JSON object per file on stdout.
//!
//!   cargo run --release -p hyst-audio --example beat_pll -- a.wav [b.wav ...]
//!
//! The PLL is not re-implemented: a beat is the hop at which `beat_phase` wraps, its time interpolated linearly.
//! Hop = 512 samples, FFT 2048, as the live extractor. The PLL's clock is the time of the *end* of the FFT
//! window, so `beats` is the PLL's own raw time and `beats_centred` is the same times minus half a window
//! (1024 samples), which puts them on the audio the flux actually describes. Both are printed; the choice of
//! which one the check scores is the overseer's.

use hyst_audio::{FeatureExtractor, WavSource};

const FFT: usize = 2048;
const HOP: usize = 512;

fn main() {
    let paths: Vec<String> = std::env::args().skip(1).collect();
    if paths.is_empty() {
        eprintln!("usage: beat_pll FILE.wav [FILE.wav ...]");
        std::process::exit(2);
    }
    for path in paths {
        match run(&path) {
            Ok(line) => println!("{line}"),
            Err(e) => {
                eprintln!("{path}: {e}");
                std::process::exit(1);
            }
        }
    }
}

fn run(path: &str) -> Result<String, String> {
    let wav = WavSource::load(path).map_err(|e| e.to_string())?;
    let sr = wav.sample_rate as f32;
    let channels = wav.channels.max(1) as usize;
    let mono: Vec<f32> = wav
        .samples
        .chunks(channels)
        .map(|f| f.iter().sum::<f32>() / channels as f32)
        .collect();
    let mut extractor = FeatureExtractor::new(FFT, HOP, sr);
    let (mut beats, mut tempos) = (Vec::new(), Vec::new());
    let mut prev: Option<(f32, f32)> = None; // (time, phase)
    let mut pushed = 0usize;
    for chunk in mono.chunks(HOP) {
        pushed += chunk.len();
        for bus in extractor.push_samples(chunk) {
            let t = pushed as f32 / sr;
            let phase = bus.beat_phase;
            if let Some((t0, p0)) = prev {
                if phase < p0 - 0.5 {
                    // wrapped: the phase went from p0 up through 1 and on to `phase`
                    let frac = (1.0 - p0) / (1.0 - p0 + phase);
                    beats.push(t0 + frac * (t - t0));
                }
            }
            prev = Some((t, phase));
            if t > 5.0 {
                tempos.push(bus.tempo_bpm);
            }
        }
    }
    tempos.sort_by(f32::total_cmp);
    let tempo = tempos.get(tempos.len() / 2).copied().unwrap_or(0.0);
    let fmt = |v: &[f32], shift: f32| {
        v.iter()
            .map(|b| format!("{:.4}", b + shift))
            .collect::<Vec<_>>()
            .join(",")
    };
    Ok(format!(
        "{{\"path\":{path:?},\"sample_rate\":{},\"tempo_bpm\":{tempo:.3},\"beats\":[{}],\"beats_centred\":[{}]}}",
        wav.sample_rate,
        fmt(&beats, 0.0),
        fmt(&beats, -(FFT as f32 / 2.0) / sr)
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Click train at `bpm` for `seconds`, written as a mono 44.1 kHz WAV; the PLL's tempo and beat spacing lock on.
    #[test]
    fn click_train_locks() {
        let sr = 44_100u32;
        let dir = std::env::temp_dir().join(format!("beat_pll_test_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        for bpm in [120.0f32, 90.0] {
            let path = dir.join(format!("c{bpm}.wav"));
            let mut w = hound::WavWriter::create(
                &path,
                hound::WavSpec {
                    channels: 1,
                    sample_rate: sr,
                    bits_per_sample: 16,
                    sample_format: hound::SampleFormat::Int,
                },
            )
            .unwrap();
            let period = (60.0 / bpm * sr as f32) as usize;
            for i in 0..(30 * sr as usize) {
                let k = i % period;
                let v = if k < 200 {
                    (1.0 - k as f32 / 200.0) * 0.9
                } else {
                    0.0
                };
                w.write_sample((v * 32767.0) as i16).unwrap();
            }
            w.finalize().unwrap();
            let line = run(path.to_str().unwrap()).unwrap();
            let tempo: f32 = line
                .split("\"tempo_bpm\":")
                .nth(1)
                .unwrap()
                .split(',')
                .next()
                .unwrap()
                .parse()
                .unwrap();
            assert!((tempo - bpm).abs() < 4.0, "{bpm}: {tempo}");
            let beats: Vec<f32> = line
                .split("\"beats\":[")
                .nth(1)
                .unwrap()
                .split(']')
                .next()
                .unwrap()
                .split(',')
                .map(|s| s.parse().unwrap())
                .collect();
            let late: Vec<f32> = beats.iter().copied().filter(|b| *b > 15.0).collect();
            assert!(late.len() >= 10);
            let gap = late.windows(2).map(|w| w[1] - w[0]).sum::<f32>() / (late.len() - 1) as f32;
            assert!((gap - 60.0 / bpm).abs() < 0.03, "{bpm}: {gap}");
        }
        std::fs::remove_dir_all(dir).ok();
    }
}
