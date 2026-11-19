//! Render body vectors with `body.rs` and report their descriptors (docs/NEXT_DECODER_THEN_BRAIN.md, D2).
//!   body_render IN.json OUT.json
//! IN:  {"seeds": [u64, ...], "bodies": [[15 values 0..1], ...]}
//! OUT: {"seeds": [...], "ok": [bool], "desc": [[37] or []], "stretch": [[one per seed]], "seconds": f64}
//! `desc` is the mean of the 37 descriptors over the seeds' clips. A body is `ok` only if every
//! seed's clip passes check 2a on the stretch ladder; otherwise `desc` is empty (a failed segment).
use std::{
    env, fs, io,
    sync::atomic::{AtomicUsize, Ordering},
    time::Instant,
};

use hyst_compile::body;

/// Mean descriptors and the stretch of each seed's clip.
type Rendered = Option<(Vec<f64>, Vec<f64>)>;

fn render(b: &body::Body, seeds: &[u64]) -> Rendered {
    let mut mean = vec![0.0; body::DESCRIPTOR_COUNT];
    let mut stretch = Vec::with_capacity(seeds.len());
    for &seed in seeds {
        let (s, score) = body::feasible(b, seed)?;
        for (m, d) in mean.iter_mut().zip(body::descriptors(&score)) {
            *m += d / seeds.len() as f64;
        }
        stretch.push(s);
    }
    Some((mean, stretch))
}

fn main() -> io::Result<()> {
    let args: Vec<String> = env::args().collect();
    let [_, input, output] = args.as_slice() else {
        return Err(io::Error::other("usage: body_render IN.json OUT.json"));
    };
    let start = Instant::now();
    let data: serde_json::Value = serde_json::from_slice(&fs::read(input)?)?;
    let seeds: Vec<u64> = serde_json::from_value(data["seeds"].clone())?;
    let bodies: Vec<body::Body> = serde_json::from_value(data["bodies"].clone())?;
    let threads = std::thread::available_parallelism().map_or(4, |n| n.get());
    let next = AtomicUsize::new(0);
    let mut done: Vec<(usize, Rendered)> = std::thread::scope(|sc| {
        (0..threads)
            .map(|_| {
                sc.spawn(|| {
                    let mut mine = Vec::new();
                    loop {
                        let i = next.fetch_add(1, Ordering::Relaxed);
                        if i >= bodies.len() {
                            return mine;
                        }
                        mine.push((i, render(&bodies[i], &seeds)));
                    }
                })
            })
            .collect::<Vec<_>>()
            .into_iter()
            .flat_map(|h| h.join().unwrap())
            .collect()
    });
    done.sort_by_key(|d| d.0);
    let out = serde_json::json!({
        "seeds": seeds,
        "ok": done.iter().map(|d| d.1.is_some()).collect::<Vec<_>>(),
        "desc": done.iter().map(|d| d.1.as_ref().map_or(vec![], |r| r.0.clone())).collect::<Vec<_>>(),
        "stretch": done.iter().map(|d| d.1.as_ref().map_or(vec![], |r| r.1.clone())).collect::<Vec<_>>(),
        "seconds": start.elapsed().as_secs_f64(),
    });
    fs::write(output, serde_json::to_vec(&out)?)?;
    println!(
        "{} bodies x {} seeds in {:.1} s on {threads} threads",
        bodies.len(),
        seeds.len(),
        start.elapsed().as_secs_f64()
    );
    Ok(())
}
