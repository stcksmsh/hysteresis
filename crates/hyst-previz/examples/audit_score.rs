//! Audit exported score, including exact quintic extrema and sampled clearance.
//! cargo run -p hyst-previz --example audit_score -- score.json
use hyst_compile::Score;
use std::{env, fs};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let path = env::args().nth(1).ok_or("usage: audit_score score.json")?;
    let score: Score = serde_json::from_str(&fs::read_to_string(path)?)?;
    let report = hyst_previz::audit_score(&score)?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}
