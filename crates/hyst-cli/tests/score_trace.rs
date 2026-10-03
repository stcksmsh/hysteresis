use std::fs;
use std::process::Command;

use hyst_compile::{Cue, JointLimits, Knot, Score};

fn write_wav(path: &std::path::Path, sample_rate: u32, frames: u32) {
    let data_bytes = frames * 2;
    let mut wav = Vec::with_capacity(44 + data_bytes as usize);
    wav.extend_from_slice(b"RIFF");
    wav.extend_from_slice(&(36 + data_bytes).to_le_bytes());
    wav.extend_from_slice(b"WAVEfmt ");
    wav.extend_from_slice(&16_u32.to_le_bytes());
    wav.extend_from_slice(&1_u16.to_le_bytes()); // PCM
    wav.extend_from_slice(&1_u16.to_le_bytes()); // mono
    wav.extend_from_slice(&sample_rate.to_le_bytes());
    wav.extend_from_slice(&(sample_rate * 2).to_le_bytes());
    wav.extend_from_slice(&2_u16.to_le_bytes());
    wav.extend_from_slice(&16_u16.to_le_bytes());
    wav.extend_from_slice(b"data");
    wav.extend_from_slice(&data_bytes.to_le_bytes());
    wav.resize(44 + data_bytes as usize, 0);
    fs::write(path, wav).unwrap();
}

fn score(duration: f64) -> Score {
    Score {
        duration,
        limits: JointLimits::default(),
        cues: vec![Cue {
            start: 0.0,
            end: duration,
            gesture: "hold".into(),
            reason: "fixture".into(),
            energy: 0.0,
            accent: 0.0,
            arrival_anchor: None,
            knots: vec![
                Knot {
                    time: 0.0,
                    phase: "hold".into(),
                    joints: [105.0, -65.0, -20.0],
                    velocity: [0.0; 3],
                    acceleration: [0.0; 3],
                },
                Knot {
                    time: duration,
                    phase: "hold".into(),
                    joints: [105.0, -65.0, -20.0],
                    velocity: [0.0; 3],
                    acceleration: [0.0; 3],
                },
            ],
        }],
    }
}

#[test]
fn trace_drains_latency_and_reaches_terminal_score_frame() {
    for source_frames in [9, 10] {
        let root = std::env::temp_dir().join(format!(
            "hyst-cli-trace-{}-{source_frames}",
            std::process::id()
        ));
        let score_path = root.with_extension("score.json");
        let wav_path = root.with_extension("wav");
        fs::write(&score_path, serde_json::to_string(&score(1.0)).unwrap()).unwrap();
        write_wav(&wav_path, 10, source_frames);
        let output = Command::new(env!("CARGO_BIN_EXE_hyst"))
            .args([
                "score-trace",
                score_path.to_str().unwrap(),
                wav_path.to_str().unwrap(),
                "10",
                "200",
            ])
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
        let frames: Vec<serde_json::Value> = String::from_utf8(output.stdout)
            .unwrap()
            .lines()
            .map(|line| serde_json::from_str(line).unwrap())
            .collect();
        assert_eq!(frames.last().unwrap()["time_seconds"], 1.0);
        assert_eq!(
            frames
                .iter()
                .filter(|frame| frame["time_seconds"] == 1.0)
                .count(),
            1
        );
        assert!(frames.windows(2).all(|pair| {
            let start = pair[0]["time_seconds"].as_f64().unwrap();
            let end = pair[1]["time_seconds"].as_f64().unwrap();
            end >= start && end - start <= 0.1 + 1e-12
        }));
    }
}

#[test]
fn trace_rejects_duration_mismatch_before_writing_frames_and_help_succeeds() {
    let root = std::env::temp_dir().join(format!("hyst-cli-mismatch-{}", std::process::id()));
    let score_path = root.with_extension("score.json");
    let wav_path = root.with_extension("wav");
    fs::write(&score_path, serde_json::to_string(&score(1.0)).unwrap()).unwrap();
    write_wav(&wav_path, 10, 8);
    let output = Command::new(env!("CARGO_BIN_EXE_hyst"))
        .args([
            "score-trace",
            score_path.to_str().unwrap(),
            wav_path.to_str().unwrap(),
        ])
        .output()
        .unwrap();
    assert!(!output.status.success());
    assert!(output.stdout.is_empty());
    assert!(String::from_utf8_lossy(&output.stderr).contains("does not match WAV duration"));
    assert!(Command::new(env!("CARGO_BIN_EXE_hyst"))
        .arg("--help")
        .output()
        .unwrap()
        .status
        .success());
}
