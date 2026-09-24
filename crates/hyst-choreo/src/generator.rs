//! Procedural move generator (§2's closing note: generation is the
//! *primary* population path, hand-authoring is the override).
//!
//! Picks a curve family/flavor and perturbs shape params + Effort within
//! sane bounds. Deterministic given a seed (own tiny xorshift64* PRNG —
//! not pulling in a `rand` dependency for this; the workspace has none and
//! a handful of `next_f32`-shaped calls don't justify adding one).

use std::collections::BTreeMap;

use crate::curve::{Curve, Flavor};
use crate::effort::Effort;
use crate::moves::{ChannelRole, Duration, Move, PoseRequirement, Provenance, TimescaleRole};

/// Deterministic PRNG, seeded explicitly so generator tests are
/// reproducible. xorshift64* (Vigna) — fast, small, good enough for
/// "perturb a shape param," not cryptographic.
pub struct Rng(u64);

impl Rng {
    pub fn new(seed: u64) -> Self {
        Rng(seed | 1) // must be nonzero
    }

    fn next_u64(&mut self) -> u64 {
        let mut x = self.0;
        x ^= x >> 12;
        x ^= x << 25;
        x ^= x >> 27;
        self.0 = x;
        x.wrapping_mul(0x2545_F491_4F6C_DD1D)
    }

    /// Uniform float in `[0.0, 1.0)`.
    pub fn next_f32(&mut self) -> f32 {
        (self.next_u64() >> 40) as f32 / (1u64 << 24) as f32
    }

    pub fn range(&mut self, lo: f32, hi: f32) -> f32 {
        lo + self.next_f32() * (hi - lo)
    }

    fn index(&mut self, len: usize) -> usize {
        (self.next_u64() as usize) % len
    }
}

const FLAVORS: [Flavor; 3] = [Flavor::In, Flavor::Out, Flavor::InOut];
const TAG_VOCABULARY: [&str; 6] = [
    "sharp",
    "floating",
    "coiled",
    "direct",
    "sustained",
    "punchy",
];

/// Pick a random flavor.
fn random_flavor(rng: &mut Rng) -> Flavor {
    FLAVORS[rng.index(FLAVORS.len())]
}

/// Pick a random curve family + flavor, perturbing shape params within
/// sane bounds (`Back` overshoot, `Bezier` tension).
pub fn generate_curve(rng: &mut Rng) -> Curve {
    match rng.index(12) {
        0 => Curve::Linear,
        1 => Curve::Sine(random_flavor(rng)),
        2 => Curve::Quad(random_flavor(rng)),
        3 => Curve::Cubic(random_flavor(rng)),
        4 => Curve::Quart(random_flavor(rng)),
        5 => Curve::Quint(random_flavor(rng)),
        6 => Curve::Expo(random_flavor(rng)),
        7 => Curve::Circ(random_flavor(rng)),
        8 => Curve::Back {
            flavor: random_flavor(rng),
            overshoot: rng.range(1.0, 2.0),
        },
        9 => Curve::Elastic(random_flavor(rng)),
        10 => Curve::Bounce(random_flavor(rng)),
        11 => Curve::Bezier {
            tension: rng.range(-0.4, 0.4),
        },
        _ => unreachable!(),
    }
}

fn generate_effort(rng: &mut Rng) -> Effort {
    Effort {
        time: rng.next_f32(),
        weight: rng.next_f32(),
        space: rng.next_f32(),
    }
}

fn generate_role(rng: &mut Rng) -> TimescaleRole {
    match rng.index(4) {
        0 => TimescaleRole::Hit,
        1 => TimescaleRole::Groove,
        2 => TimescaleRole::Windup,
        _ => TimescaleRole::Hold,
    }
}

fn generate_tags(rng: &mut Rng) -> Vec<String> {
    let n = rng.index(3); // 0..=2 tags
    (0..n)
        .map(|_| TAG_VOCABULARY[rng.index(TAG_VOCABULARY.len())].to_string())
        .collect()
}

/// Generate a valid, varied `Move` for the given channel roles. Entry/exit
/// pose is left agnostic (the generator has no chain context to know a
/// required pose — that's an authoring/compiler concern); `arrival_anchor`
/// is left `None` for the same reason (R7's job, not this crate's).
pub fn generate_move(rng: &mut Rng, roles: &[ChannelRole], duration: Duration) -> Move {
    let mut channels = BTreeMap::new();
    for role in roles {
        channels.insert(role.clone(), generate_curve(rng));
    }
    Move {
        channels,
        duration,
        entry_pose: PoseRequirement::Agnostic,
        exit_pose: PoseRequirement::Agnostic,
        arrival_anchor: None,
        role: generate_role(rng),
        effort: generate_effort(rng),
        applicability_tags: generate_tags(rng),
        intensity: rng.range(0.5, 1.5),
        provenance: Provenance::Generated,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashSet;

    #[test]
    fn generated_moves_are_structurally_valid() {
        let mut rng = Rng::new(42);
        let roles = [
            ChannelRole::PrimaryElevation,
            ChannelRole::AccentLightIntensity,
        ];
        for _ in 0..30 {
            let mv = generate_move(&mut rng, &roles, Duration::Seconds(1.0));
            assert_eq!(mv.channels.len(), roles.len());
            assert!(mv.effort.in_range());
            assert!(mv.intensity >= 0.5 && mv.intensity <= 1.5);
            for curve in mv.channels.values() {
                // every curve's own endpoint behavior is unit-tested in
                // curve.rs; here just confirm it evaluates without panicking
                // across the domain, including overshooting families.
                for i in 0..=10 {
                    let _ = curve.eval(i as f32 / 10.0);
                }
            }
        }
    }

    #[test]
    fn generated_moves_show_real_variety() {
        let mut rng = Rng::new(7);
        let roles = [ChannelRole::PrimaryElevation];
        let mut families = HashSet::new();
        for _ in 0..30 {
            let mv = generate_move(&mut rng, &roles, Duration::Seconds(1.0));
            for curve in mv.channels.values() {
                families.insert(curve.family());
            }
        }
        assert!(
            families.len() > 1,
            "expected variety across curve families, got only {families:?}"
        );
    }

    #[test]
    fn rng_is_deterministic_given_same_seed() {
        let mut a = Rng::new(123);
        let mut b = Rng::new(123);
        for _ in 0..20 {
            assert_eq!(a.next_f32(), b.next_f32());
        }
    }
}
