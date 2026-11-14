//! Body study regions under addenda 4 and 8 of `docs/BODY_STUDY.md`: a region is one
//! body vector (its centre sweep clip plus 11 clips with fresh seeds), and regions
//! must be separated by 1.5 times their seed spread.

/// Separation factor (overseer's proposal, accepted by the user; addendum 4).
pub const FACTOR: f64 = 1.5;
/// Clips per region: the centre plus 11 made clips (addendum 8).
pub const CLIPS_PER_REGION: usize = 12;
/// Seeds tried per region before its centre is replaced.
pub const MAX_SEEDS: usize = 200;
/// Seed of the made clips' seed order (addendum 4; addendum 8 sets none, so kept).
pub const SEED_ORDER: u64 = 20_261_015;

pub fn dist(a: &[f64], b: &[f64]) -> f64 {
    a.iter()
        .zip(b)
        .map(|(x, y)| (x - y).powi(2))
        .sum::<f64>()
        .sqrt()
}

/// Midrank of a descriptor vector against the sweep's sorted columns (addendum 8):
/// (number of sweep values below + half the number equal) / N, per descriptor.
pub fn rank(sorted: &[Vec<f64>], d: &[f64]) -> Vec<f64> {
    d.iter()
        .zip(sorted)
        .map(|(v, col)| {
            let below = col.partition_point(|x| x < v);
            let equal = col.partition_point(|x| x <= v) - below;
            (below as f64 + equal as f64 / 2.0) / col.len() as f64
        })
        .collect()
}

/// Candidate centres (addendum 1): the points whose distance to their 9th nearest
/// other point is at or under the median of that distance.
pub fn candidates(points: &[Vec<f64>]) -> Vec<usize> {
    let d9: Vec<f64> = points
        .iter()
        .map(|p| {
            let mut d: Vec<f64> = points.iter().map(|q| dist(p, q)).collect();
            d.sort_by(f64::total_cmp);
            d[9] // d[0] is the point itself
        })
        .collect();
    let mut s = d9.clone();
    s.sort_by(f64::total_cmp);
    let n = s.len();
    let median = if n % 2 == 1 {
        s[n / 2]
    } else {
        (s[n / 2 - 1] + s[n / 2]) / 2.0
    };
    (0..n).filter(|&i| d9[i] <= median).collect()
}

/// Seed spread w: mean pairwise distance of a region's clips.
pub fn spread(clips: &[Vec<f64>]) -> f64 {
    let d: Vec<f64> = (0..clips.len())
        .flat_map(|a| (a + 1..clips.len()).map(move |b| (a, b)))
        .map(|(a, b)| dist(&clips[a], &clips[b]))
        .collect();
    d.iter().sum::<f64>() / d.len().max(1) as f64
}

/// Position m: mean of a region's rank vectors.
pub fn position(clips: &[Vec<f64>]) -> Vec<f64> {
    (0..clips[0].len())
        .map(|k| clips.iter().map(|c| c[k]).sum::<f64>() / clips.len() as f64)
        .collect()
}

/// Every pair (i, j, |m_i - m_j|, ratio |m_i - m_j| / max(w_i, w_j)).
pub fn pairs(m: &[Vec<f64>], w: &[f64]) -> Vec<(usize, usize, f64, f64)> {
    (0..m.len())
        .flat_map(|i| (i + 1..m.len()).map(move |j| (i, j)))
        .map(|(i, j)| {
            let d = dist(&m[i], &m[j]);
            (i, j, d, d / w[i].max(w[j]))
        })
        .collect()
}

/// The pair with the smallest ratio, if it breaks the rule (ratio < FACTOR).
pub fn worst_pair(m: &[Vec<f64>], w: &[f64]) -> Option<(usize, usize, f64)> {
    pairs(m, w)
        .into_iter()
        .min_by(|a, b| a.3.total_cmp(&b.3))
        .filter(|p| p.3 < FACTOR)
        .map(|(i, j, _, r)| (i, j, r))
}

/// Farthest-point order: the candidate, not in `excluded`, farthest from all `kept`
/// (from `mean` when nothing is kept).
pub fn next_centre(
    points: &[Vec<f64>],
    candidates: &[usize],
    kept: &[usize],
    excluded: &[usize],
    mean: &[f64],
) -> Option<usize> {
    let far = |c: usize| {
        if kept.is_empty() {
            dist(&points[c], mean)
        } else {
            kept.iter()
                .map(|&o| dist(&points[c], &points[o]))
                .fold(f64::MAX, f64::min)
        }
    };
    candidates
        .iter()
        .copied()
        .filter(|c| !excluded.contains(c) && !kept.contains(c))
        .max_by(|&a, &b| far(a).total_cmp(&far(b)))
}

/// The first `n` centres by farthest-point sampling over the candidates.
pub fn initial_centres(
    points: &[Vec<f64>],
    candidates: &[usize],
    mean: &[f64],
    n: usize,
) -> Vec<usize> {
    let mut c = Vec::new();
    while c.len() < n {
        match next_centre(points, candidates, &c, &[], mean) {
            Some(x) => c.push(x),
            None => break,
        }
    }
    c
}

#[derive(Debug, Clone, PartialEq)]
pub enum Event {
    /// Region at `slot` built from centre `centre` with `clips` clips (short when < 9).
    Built {
        slot: usize,
        centre: usize,
        clips: usize,
    },
    /// Centre of `slot` replaced: `pair` and `ratio` are set when the separation rule
    /// caused it, None when the region was short of clips.
    Replaced {
        slot: usize,
        old: usize,
        new: usize,
        pair: Option<(usize, usize)>,
        ratio: Option<f64>,
    },
    /// Candidates ran out while replacing `slot`.
    Exhausted { slot: usize },
}

pub struct Outcome<R> {
    pub centres: Vec<usize>,
    /// Each slot's region (its rank vectors and whatever the builder keeps).
    pub regions: Vec<R>,
    pub events: Vec<Event>,
    /// True when every pair keeps the rule and every region has 9 clips.
    pub holds: bool,
}

/// Addendum 4, steps 1-5. `build(centre)` returns the region's rank vectors (centre
/// first) and its payload; fewer than 9 vectors means the region is short.
/// A short region or the later-chosen centre of the worst pair is replaced by the
/// next candidate in farthest-point order from all centres kept; stops when the rule
/// holds or candidates run out.
pub fn select<R>(
    points: &[Vec<f64>],
    candidates: &[usize],
    mean: &[f64],
    n: usize,
    mut build: impl FnMut(usize) -> (Vec<Vec<f64>>, R),
) -> Outcome<R> {
    let mut centres = initial_centres(points, candidates, mean, n);
    let mut chosen_at: Vec<usize> = (0..n).collect();
    let mut order = n;
    let mut used: Vec<usize> = centres.clone();
    let mut events = Vec::new();
    let mut built: Vec<Option<(Vec<Vec<f64>>, R)>> = (0..n).map(|_| None).collect();
    // Replace slot k; false when candidates run out.
    let mut replace = |k: usize,
                       pair: Option<(usize, usize)>,
                       ratio: Option<f64>,
                       centres: &mut Vec<usize>,
                       chosen_at: &mut Vec<usize>,
                       events: &mut Vec<Event>| {
        let kept: Vec<usize> = (0..n).filter(|&i| i != k).map(|i| centres[i]).collect();
        match next_centre(points, candidates, &kept, &used, mean) {
            Some(c) => {
                events.push(Event::Replaced {
                    slot: k,
                    old: centres[k],
                    new: c,
                    pair,
                    ratio,
                });
                used.push(c);
                centres[k] = c;
                chosen_at[k] = order;
                order += 1;
                true
            }
            None => {
                events.push(Event::Exhausted { slot: k });
                false
            }
        }
    };
    loop {
        // Build every slot that has no region yet; replace short ones.
        let mut short = None;
        for k in 0..n {
            if built[k].is_none() {
                let r = build(centres[k]);
                events.push(Event::Built {
                    slot: k,
                    centre: centres[k],
                    clips: r.0.len(),
                });
                if r.0.len() < CLIPS_PER_REGION {
                    short = Some(k);
                    break;
                }
                built[k] = Some(r);
            }
        }
        if let Some(k) = short {
            if !replace(k, None, None, &mut centres, &mut chosen_at, &mut events) {
                break;
            }
            continue;
        }
        let regions: Vec<&Vec<Vec<f64>>> = built.iter().map(|r| &r.as_ref().unwrap().0).collect();
        let w: Vec<f64> = regions.iter().map(|r| spread(r)).collect();
        let m: Vec<Vec<f64>> = regions.iter().map(|r| position(r)).collect();
        let Some((i, j, ratio)) = worst_pair(&m, &w) else {
            return Outcome {
                centres,
                regions: built.into_iter().map(|r| r.unwrap().1).collect(),
                events,
                holds: true,
            };
        };
        let k = if chosen_at[i] > chosen_at[j] { i } else { j };
        if !replace(
            k,
            Some((i, j)),
            Some(ratio),
            &mut centres,
            &mut chosen_at,
            &mut events,
        ) {
            break;
        }
        built[k] = None;
    }
    // Stopped: report whatever regions exist. After a failed rule replacement all 8
    // are the last full set; after a failed short-region replacement one is missing.
    Outcome {
        centres,
        regions: built.into_iter().filter_map(|r| r.map(|r| r.1)).collect(),
        events,
        holds: false,
    }
}

/// Seed stream for made clips of the region centred on sweep clip `centre`:
/// fixed by SEED_ORDER and the centre, independent of when the region is built.
pub fn made_seeds(centre: usize) -> impl Iterator<Item = u64> {
    let mut s = SEED_ORDER.wrapping_add((centre as u64 + 1).wrapping_mul(0x2545_F491_4F6C_DD1D));
    std::iter::repeat_with(move || {
        // splitmix64, 53-bit seeds as `body::draw` gives
        s = s.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = s;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        (z ^ (z >> 31)) >> 11
    })
    .take(MAX_SEEDS)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn region(c: [f64; 2], w: f64) -> Vec<Vec<f64>> {
        // CLIPS_PER_REGION points: centre and the rest around it, spread grows with w
        (0..CLIPS_PER_REGION)
            .map(|i| {
                if i == 0 {
                    c.to_vec()
                } else {
                    let a = i as f64 * std::f64::consts::TAU / (CLIPS_PER_REGION - 1) as f64;
                    vec![c[0] + w * a.cos(), c[1] + w * a.sin()]
                }
            })
            .collect()
    }

    #[test]
    fn rule_takes_the_larger_spread() {
        let m = vec![vec![0.0, 0.0], vec![3.0, 0.0]];
        assert!(worst_pair(&m, &[1.0, 2.0]).is_none()); // 3 >= 1.5 x 2
        let (i, j, r) = worst_pair(&m, &[1.0, 2.1]).unwrap();
        assert_eq!((i, j), (0, 1));
        assert!((r - 3.0 / 2.1).abs() < 1e-12);
        // smallest ratio picked among several
        let m = vec![vec![0.0, 0.0], vec![10.0, 0.0], vec![11.0, 0.0]];
        assert_eq!(worst_pair(&m, &[1.0, 1.0, 1.0]).unwrap().0, 1);
    }

    #[test]
    fn rank_counts_values_below() {
        let sorted = vec![vec![1.0, 2.0, 2.0, 2.0, 3.0, 4.0]];
        // midrank: below + half the equal ones
        assert_eq!(rank(&sorted, &[2.5]), vec![4.0 / 6.0]);
        assert_eq!(rank(&sorted, &[2.0]), vec![2.5 / 6.0]);
        assert_eq!(rank(&sorted, &[1.0]), vec![0.5 / 6.0]);
        assert_eq!(rank(&sorted, &[0.0]), vec![0.0]);
        assert_eq!(rank(&sorted, &[4.0]), vec![5.5 / 6.0]);
    }

    #[test]
    fn candidates_are_the_denser_half() {
        // 11 points packed near 0, 11 spread out far apart: the packed ones are
        // the candidates
        let mut p: Vec<Vec<f64>> = (0..11).map(|i| vec![i as f64 * 0.01]).collect();
        p.extend((0..11).map(|i| vec![100.0 + i as f64 * 10.0]));
        assert_eq!(candidates(&p), (0..11).collect::<Vec<_>>());
    }

    #[test]
    fn spread_and_position() {
        let r = region([1.0, 2.0], 1.0);
        let m = position(&r);
        assert!((m[0] - 1.0).abs() < 1e-12 && (m[1] - 2.0).abs() < 1e-12);
        assert!(spread(&r) > 0.9 && spread(&r) < 1.5);
        assert!(spread(&region([0.0, 0.0], 2.0)) > 2.0 * spread(&r) - 1e-9);
    }

    /// Synthetic set on a line: candidates 0..6 at x = 0, 14, 1, 9, 5, 20, 40.
    fn line() -> (Vec<Vec<f64>>, Vec<f64>) {
        let xs = [0.0, 14.0, 1.0, 9.0, 5.0, 20.0, 40.0];
        let p: Vec<Vec<f64>> = xs.iter().map(|&x| vec![x, 0.0]).collect();
        let mean = vec![xs.iter().sum::<f64>() / xs.len() as f64, 0.0];
        (p, mean)
    }

    type Rep = (usize, usize, usize, Option<(usize, usize)>);
    fn replaced(out: &Outcome<usize>) -> Vec<Rep> {
        out.events
            .iter()
            .filter_map(|e| match e {
                Event::Replaced {
                    slot,
                    old,
                    new,
                    pair,
                    ..
                } => Some((*slot, *old, *new, *pair)),
                _ => None,
            })
            .collect()
    }

    #[test]
    fn farthest_point_order() {
        // mean 12.7: farthest 40 (id 6); then 0 (id 0); then 20 (id 5); then 9 (id 3)
        let (p, mean) = line();
        let c = initial_centres(&p, &(0..7).collect::<Vec<_>>(), &mean, 4);
        assert_eq!(c, vec![6, 0, 5, 3]);
    }

    #[test]
    fn replaces_later_chosen_of_worst_pair_until_rule_holds() {
        let (p, mean) = line();
        let cand: Vec<usize> = (0..7).collect();
        // Region at x = 9 (id 3, chosen 4th) is about 50 times wider than the others.
        // Pair (x 0, x 9) has the smallest ratio, under 1.5. Its later-chosen centre, id 3,
        // goes; next in farthest-point order from {40, 0, 20}: 14 (id 1).
        let out = select(&p, &cand, &mean, 4, |c| {
            (region([p[c][0], 0.0], if c == 3 { 5.0 } else { 0.1 }), c)
        });
        assert!(out.holds);
        assert_eq!(replaced(&out), vec![(3, 3, 1, Some((1, 3)))]);
        assert_eq!(out.centres, vec![6, 0, 5, 1]);
        assert_eq!(out.regions, vec![6, 0, 5, 1]);
    }

    #[test]
    fn short_region_replaced_then_exhaustion_stops() {
        let (p, mean) = line();
        let cand: Vec<usize> = (0..7).collect();
        // Region of id 5 (slot 2) builds only 4 clips: replaced by the farthest from
        // {40, 0, 9}: 14 (id 1, 5 away) over 5 (id 4, 4 away).
        let out = select(&p, &cand, &mean, 4, |c| {
            let mut r = region([p[c][0], 0.0], 0.1);
            if c == 5 {
                r.truncate(4);
            }
            (r, c)
        });
        assert!(out.holds);
        assert_eq!(replaced(&out), vec![(2, 5, 1, None)]);
        // Every region too wide: the rule cannot hold, candidates run out.
        let out = select(&p, &cand, &mean, 4, |c| (region([p[c][0], 0.0], 50.0), c));
        assert!(!out.holds);
        assert_eq!(replaced(&out).len(), 3);
        assert!(matches!(out.events.last(), Some(Event::Exhausted { .. })));
        // the last full set is kept for the report
        assert_eq!(out.regions.len(), 4);
    }

    #[test]
    fn made_seeds_fixed_per_centre() {
        let a: Vec<u64> = made_seeds(7).collect();
        assert_eq!(a.len(), MAX_SEEDS);
        assert_eq!(a, made_seeds(7).collect::<Vec<_>>());
        assert_ne!(a[0], made_seeds(8).next().unwrap());
    }
}
