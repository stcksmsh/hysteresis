//! Dump score joint angles at a fixed rate for offline video rendering.
//! cargo run -p hyst-previz --example sample_score -- score.json 30 > frames.json
use hyst_compile::Score;
use std::{env, fs};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = env::args().skip(1);
    let path = args.next().ok_or("usage: sample_score score.json [fps]")?;
    let fps: f64 = args.next().map_or(Ok(30.0), |s| s.parse())?;
    let score: Score = serde_json::from_str(&fs::read_to_string(path)?)?;
    let frames: Vec<[f64; 3]> = (0..(score.duration * fps) as usize)
        .map(|i| score.sample(i as f64 / fps))
        .collect();
    println!("{}", serde_json::to_string(&frames)?);
    Ok(())
}
