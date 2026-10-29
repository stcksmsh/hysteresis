//! `hyst` command-line entry point.
//!
//!   hyst score-csv SCORE_JSON OUT.csv [--hz 50] [--mode off|layered] [--body-source NAME]
//!   hyst check-csv FILE.csv
//!
//! `score-csv` writes one arm's joint angles (step H of docs/NEXT_DECODER_THEN_BRAIN.md);
//! `check-csv` exits 1 and names the first breaches of the Layered limits. Neither sends anything
//! anywhere; for the dance preview see crates/hyst-previz/README.md.

use std::process::ExitCode;

use hyst_compile::body::LIMITS;
use hyst_compile::ensemble::EnsembleScore;
use hyst_compile::score_csv::{check, export, Meta, SHOWN};

const USAGE: &str = "usage: hyst score-csv SCORE_JSON OUT.csv [--hz 50] [--mode off|layered] [--body-source NAME]\n       hyst check-csv FILE.csv";

fn run(args: &[String]) -> Result<ExitCode, String> {
    match args.first().map(String::as_str) {
        Some("score-csv") if args.len() >= 3 => {
            let (mut hz, mut mode, mut body_source) = (50.0, None, "none".to_string());
            let mut rest = args[3..].iter();
            while let Some(flag) = rest.next() {
                let value = rest.next().ok_or(format!("{flag} needs a value"))?;
                match flag.as_str() {
                    "--hz" => hz = value.parse().map_err(|_| "bad --hz")?,
                    "--mode" => mode = Some(value.clone()),
                    "--body-source" => body_source = value.clone(),
                    _ => return Err(format!("unknown option {flag}\n{USAGE}")),
                }
            }
            let text =
                std::fs::read_to_string(&args[1]).map_err(|e| format!("{}: {e}", args[1]))?;
            let score: EnsembleScore = serde_json::from_str(&text).map_err(|e| e.to_string())?;
            // A Layered score carries body.rs's limits as its rig envelope.
            let layered = score.rig.channels.iter().zip(LIMITS).all(|(c, (v, a))| {
                c.max_speed_degrees_per_second == v && c.max_acceleration_degrees_per_second2 == a
            });
            let mode = mode.unwrap_or_else(|| if layered { "layered" } else { "off" }.into());
            let name = std::path::Path::new(&args[1])
                .file_name()
                .map_or(String::new(), |n| n.to_string_lossy().into());
            let csv = export(
                &score,
                hz,
                &Meta {
                    source_score: &name,
                    mode: &mode,
                    body_source: &body_source,
                },
            )?;
            std::fs::write(&args[2], csv).map_err(|e| format!("{}: {e}", args[2]))?;
            println!("wrote {} ({mode}, {hz} Hz)", args[2]);
            Ok(ExitCode::SUCCESS)
        }
        Some("check-csv") if args.len() == 2 => {
            let text =
                std::fs::read_to_string(&args[1]).map_err(|e| format!("{}: {e}", args[1]))?;
            let breaches = check(&text)?;
            if breaches.is_empty() {
                println!("{}: accepted", args[1]);
                return Ok(ExitCode::SUCCESS);
            }
            println!(
                "{}: REFUSED, {} breaches; first {}:",
                args[1],
                breaches.len(),
                SHOWN.min(breaches.len())
            );
            for b in breaches.iter().take(SHOWN) {
                println!("  {b}");
            }
            Ok(ExitCode::FAILURE)
        }
        _ => Err(USAGE.into()),
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    run(&args).unwrap_or_else(|e| {
        eprintln!("{e}");
        ExitCode::from(2)
    })
}
