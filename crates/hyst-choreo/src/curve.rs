//! The curve corpus (`SINTEZA_CHOREOGRAPHY.md` §2.1): a `t ∈ [0,1] → [0,1]`
//! function family, represented as a **discriminated union** — family +
//! flavor + an optional shape parameter — never a flat list of unrelated
//! variants. A generator's job is "pick a family, pick a flavor, perturb
//! the optional shape parameter" (see `crate::generator`), not "choose from
//! 30 unrelated cases."
//!
//! Every family here is the standard Penner/`easings.net` set (plus the
//! `Square` and `Bezier(tension)` escape hatches §2.1 asks for) — real
//! closed-form math, not a loose approximation. Formulas cross-checked
//! against <https://easings.net>'s reference implementations.

use std::f32::consts::PI;

/// Which side of a curve family's shape is in effect — accelerating into
/// the motion, decelerating out of it, or both (ease at both ends).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Flavor {
    In,
    Out,
    InOut,
}

/// One curve from the corpus. Discriminated union: every overshooting/
/// tunable family carries its own shape parameter (`Back`'s `overshoot`,
/// `Bezier`'s `tension`) rather than the whole enum growing a shared,
/// mostly-unused parameter bag.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Curve {
    /// The null case: `f(t) = t`. Baseline reference, and deliberately
    /// mechanical accents.
    Linear,
    Sine(Flavor),
    Quad(Flavor),
    Cubic(Flavor),
    Quart(Flavor),
    Quint(Flavor),
    Expo(Flavor),
    Circ(Flavor),
    /// Deliberate overshoot-then-settle. `overshoot` is the shape param
    /// (standard easings.net default is `1.70158`; §2.1's own example uses
    /// `1.2` — this is intentionally tunable, not fixed).
    Back {
        flavor: Flavor,
        overshoot: f32,
    },
    Elastic(Flavor),
    Bounce(Flavor),
    /// Instant on/off, for light/LED channels where a hard snap reads as
    /// *more* correct than any eased curve. Modeled as a single step at the
    /// curve's temporal midpoint (`t < 0.5 -> 0`, `t >= 0.5 -> 1`) rather
    /// than at either edge, so it behaves as a genuine curve over the
    /// move's full duration (both halves are meaningful) instead of a
    /// degenerate "jump immediately" or "jump only at the very end".
    Square,
    /// The general escape hatch (§2.1): a single `tension` knob, matching
    /// REAPER's own bezier-fade model, for any shape that doesn't fit a
    /// named family. Implemented as a symmetric cubic Bezier in the (t, v)
    /// plane with control points pulled toward/away from the diagonal by
    /// `tension`; `tension = 0.0` collapses exactly to `Linear` (see the
    /// exact-value test in this module — this is not a coincidence, it's
    /// the reason these particular control points were chosen).
    Bezier {
        tension: f32,
    },
}

impl Curve {
    /// Evaluate the curve at local normalized time `t`. Callers are
    /// expected to pass `t ∈ [0,1]`; values outside that range are not
    /// clamped (a caller driving `t` from `elapsed / duration` may briefly
    /// overshoot 1.0 due to timing jitter, and clamping here would hide
    /// that rather than let the caller decide).
    pub fn eval(&self, t: f32) -> f32 {
        match self {
            Curve::Linear => t,
            Curve::Sine(flavor) => sine(*flavor, t),
            Curve::Quad(flavor) => quad(*flavor, t),
            Curve::Cubic(flavor) => cubic(*flavor, t),
            Curve::Quart(flavor) => quart(*flavor, t),
            Curve::Quint(flavor) => quint(*flavor, t),
            Curve::Expo(flavor) => expo(*flavor, t),
            Curve::Circ(flavor) => circ(*flavor, t),
            Curve::Back { flavor, overshoot } => back(*flavor, *overshoot, t),
            Curve::Elastic(flavor) => elastic(*flavor, t),
            Curve::Bounce(flavor) => bounce(*flavor, t),
            Curve::Square => {
                if t < 0.5 {
                    0.0
                } else {
                    1.0
                }
            }
            Curve::Bezier { tension } => bezier(*tension, t),
        }
    }

    /// The curve's family, independent of flavor/shape param — used by the
    /// procedural generator's variety check and by anything that wants to
    /// group curves without matching on every flavor combination.
    pub fn family(&self) -> CurveFamily {
        match self {
            Curve::Linear => CurveFamily::Linear,
            Curve::Sine(_) => CurveFamily::Sine,
            Curve::Quad(_) => CurveFamily::Quad,
            Curve::Cubic(_) => CurveFamily::Cubic,
            Curve::Quart(_) => CurveFamily::Quart,
            Curve::Quint(_) => CurveFamily::Quint,
            Curve::Expo(_) => CurveFamily::Expo,
            Curve::Circ(_) => CurveFamily::Circ,
            Curve::Back { .. } => CurveFamily::Back,
            Curve::Elastic(_) => CurveFamily::Elastic,
            Curve::Bounce(_) => CurveFamily::Bounce,
            Curve::Square => CurveFamily::Square,
            Curve::Bezier { .. } => CurveFamily::Bezier,
        }
    }
}

/// The family tag alone, for grouping/variety checks (see [`Curve::family`]).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum CurveFamily {
    Linear,
    Sine,
    Quad,
    Cubic,
    Quart,
    Quint,
    Expo,
    Circ,
    Back,
    Elastic,
    Bounce,
    Square,
    Bezier,
}

fn in_out<F1, F2>(t: f32, in_fn: F1, out_fn: F2) -> f32
where
    F1: Fn(f32) -> f32,
    F2: Fn(f32) -> f32,
{
    if t < 0.5 {
        in_fn(t)
    } else {
        out_fn(t)
    }
}

fn sine(flavor: Flavor, t: f32) -> f32 {
    match flavor {
        Flavor::In => 1.0 - (t * PI / 2.0).cos(),
        Flavor::Out => (t * PI / 2.0).sin(),
        Flavor::InOut => -((PI * t).cos() - 1.0) / 2.0,
    }
}

fn quad(flavor: Flavor, t: f32) -> f32 {
    match flavor {
        Flavor::In => t * t,
        Flavor::Out => 1.0 - (1.0 - t) * (1.0 - t),
        Flavor::InOut => in_out(t, |t| 2.0 * t * t, |t| 1.0 - (-2.0 * t + 2.0).powi(2) / 2.0),
    }
}

fn cubic(flavor: Flavor, t: f32) -> f32 {
    match flavor {
        Flavor::In => t.powi(3),
        Flavor::Out => 1.0 - (1.0 - t).powi(3),
        Flavor::InOut => in_out(
            t,
            |t| 4.0 * t.powi(3),
            |t| 1.0 - (-2.0 * t + 2.0).powi(3) / 2.0,
        ),
    }
}

fn quart(flavor: Flavor, t: f32) -> f32 {
    match flavor {
        Flavor::In => t.powi(4),
        Flavor::Out => 1.0 - (1.0 - t).powi(4),
        Flavor::InOut => in_out(
            t,
            |t| 8.0 * t.powi(4),
            |t| 1.0 - (-2.0 * t + 2.0).powi(4) / 2.0,
        ),
    }
}

fn quint(flavor: Flavor, t: f32) -> f32 {
    match flavor {
        Flavor::In => t.powi(5),
        Flavor::Out => 1.0 - (1.0 - t).powi(5),
        Flavor::InOut => in_out(
            t,
            |t| 16.0 * t.powi(5),
            |t| 1.0 - (-2.0 * t + 2.0).powi(5) / 2.0,
        ),
    }
}

fn expo(flavor: Flavor, t: f32) -> f32 {
    match flavor {
        Flavor::In => {
            if t == 0.0 {
                0.0
            } else {
                2f32.powf(10.0 * t - 10.0)
            }
        }
        Flavor::Out => {
            if t == 1.0 {
                1.0
            } else {
                1.0 - 2f32.powf(-10.0 * t)
            }
        }
        Flavor::InOut => {
            if t == 0.0 {
                0.0
            } else if t == 1.0 {
                1.0
            } else if t < 0.5 {
                2f32.powf(20.0 * t - 10.0) / 2.0
            } else {
                (2.0 - 2f32.powf(-20.0 * t + 10.0)) / 2.0
            }
        }
    }
}

fn circ(flavor: Flavor, t: f32) -> f32 {
    match flavor {
        Flavor::In => 1.0 - (1.0 - t.powi(2)).sqrt(),
        Flavor::Out => (1.0 - (t - 1.0).powi(2)).sqrt(),
        Flavor::InOut => in_out(
            t,
            |t| (1.0 - (1.0 - (2.0 * t).powi(2)).sqrt()) / 2.0,
            |t| ((1.0 - (-2.0 * t + 2.0).powi(2)).sqrt() + 1.0) / 2.0,
        ),
    }
}

fn back(flavor: Flavor, overshoot: f32, t: f32) -> f32 {
    let c1 = overshoot;
    let c3 = c1 + 1.0;
    match flavor {
        Flavor::In => c3 * t.powi(3) - c1 * t.powi(2),
        Flavor::Out => 1.0 + c3 * (t - 1.0).powi(3) + c1 * (t - 1.0).powi(2),
        Flavor::InOut => {
            let c2 = c1 * 1.525;
            if t < 0.5 {
                ((2.0 * t).powi(2) * ((c2 + 1.0) * 2.0 * t - c2)) / 2.0
            } else {
                ((2.0 * t - 2.0).powi(2) * ((c2 + 1.0) * (2.0 * t - 2.0) + c2) + 2.0) / 2.0
            }
        }
    }
}

fn elastic(flavor: Flavor, t: f32) -> f32 {
    let c4 = (2.0 * PI) / 3.0;
    let c5 = (2.0 * PI) / 4.5;
    match flavor {
        Flavor::In => {
            if t == 0.0 {
                0.0
            } else if t == 1.0 {
                1.0
            } else {
                -(2f32.powf(10.0 * t - 10.0)) * ((t * 10.0 - 10.75) * c4).sin()
            }
        }
        Flavor::Out => {
            if t == 0.0 {
                0.0
            } else if t == 1.0 {
                1.0
            } else {
                2f32.powf(-10.0 * t) * ((t * 10.0 - 0.75) * c4).sin() + 1.0
            }
        }
        Flavor::InOut => {
            if t == 0.0 {
                0.0
            } else if t == 1.0 {
                1.0
            } else if t < 0.5 {
                -(2f32.powf(20.0 * t - 10.0) * ((20.0 * t - 11.125) * c5).sin()) / 2.0
            } else {
                (2f32.powf(-20.0 * t + 10.0) * ((20.0 * t - 11.125) * c5).sin()) / 2.0 + 1.0
            }
        }
    }
}

/// `easings.net`'s reference `bounceOut`. `bounceIn`/`bounceInOut` are
/// defined in terms of it (standard construction: `in(t) = 1 - out(1-t)`).
fn bounce_out(t: f32) -> f32 {
    let n1 = 7.5625;
    let d1 = 2.75;
    if t < 1.0 / d1 {
        n1 * t * t
    } else if t < 2.0 / d1 {
        let t2 = t - 1.5 / d1;
        n1 * t2 * t2 + 0.75
    } else if t < 2.5 / d1 {
        let t2 = t - 2.25 / d1;
        n1 * t2 * t2 + 0.9375
    } else {
        let t2 = t - 2.625 / d1;
        n1 * t2 * t2 + 0.984375
    }
}

fn bounce(flavor: Flavor, t: f32) -> f32 {
    match flavor {
        Flavor::Out => bounce_out(t),
        Flavor::In => 1.0 - bounce_out(1.0 - t),
        Flavor::InOut => {
            if t < 0.5 {
                (1.0 - bounce_out(1.0 - 2.0 * t)) / 2.0
            } else {
                (1.0 + bounce_out(2.0 * t - 1.0)) / 2.0
            }
        }
    }
}

/// Symmetric cubic Bezier in the (t, v) plane: `P0=(0,0)`, `P3=(1,1)`,
/// `P1=(1/3, 1/3+tension)`, `P2=(2/3, 2/3-tension)`. `x(u)` is monotonic
/// for `tension` within a sane range (clamped to `[-0.5, 0.5]` here — well
/// past that the control polygon folds back on itself and `x(u)` stops
/// being invertible), so a bisection search recovers `u` from `t = x(u)`
/// and `v = y(u)` is the curve's value.
///
/// At `tension = 0.0` this reduces to `x(u) = u`, `y(u) = u` exactly (the
/// two Bernstein-weighted control ordinates collapse to the identity) —
/// i.e. `Bezier { tension: 0.0 }` is bit-for-bit `Linear`. See this
/// module's test for the algebraic reason and the exact-value check it
/// gives us for this family.
fn bezier(tension: f32, t: f32) -> f32 {
    let tension = tension.clamp(-0.5, 0.5);
    let p1 = 1.0 / 3.0 + tension;
    let p2 = 2.0 / 3.0 - tension;

    let x_of = |u: f32| {
        let mu = 1.0 - u;
        3.0 * mu * mu * u * (1.0 / 3.0) + 3.0 * mu * u * u * (2.0 / 3.0) + u.powi(3)
    };
    let y_of = |u: f32| {
        let mu = 1.0 - u;
        3.0 * mu * mu * u * p1 + 3.0 * mu * u * u * p2 + u.powi(3)
    };

    if t <= 0.0 {
        return 0.0;
    }
    if t >= 1.0 {
        return 1.0;
    }

    let mut lo = 0.0f32;
    let mut hi = 1.0f32;
    for _ in 0..40 {
        let mid = (lo + hi) / 2.0;
        if x_of(mid) < t {
            lo = mid;
        } else {
            hi = mid;
        }
    }
    y_of((lo + hi) / 2.0)
}

#[cfg(test)]
mod tests {
    use super::*;

    const EPS: f32 = 1e-4;

    fn assert_close(actual: f32, expected: f32) {
        assert!(
            (actual - expected).abs() < EPS,
            "expected {expected}, got {actual}"
        );
    }

    /// Every non-overshooting family must satisfy `f(0) = 0`, `f(1) = 1`.
    fn assert_endpoints(curve: Curve) {
        assert_close(curve.eval(0.0), 0.0);
        assert_close(curve.eval(1.0), 1.0);
    }

    fn assert_monotonic_nondecreasing(curve: Curve, samples: usize) {
        let mut prev = curve.eval(0.0);
        for i in 1..=samples {
            let t = i as f32 / samples as f32;
            let v = curve.eval(t);
            assert!(
                v + 1e-5 >= prev,
                "{curve:?} not monotonic at t={t}: {prev} -> {v}"
            );
            prev = v;
        }
    }

    #[test]
    fn linear_is_identity() {
        assert_endpoints(Curve::Linear);
        assert_close(Curve::Linear.eval(0.5), 0.5);
        assert_close(Curve::Linear.eval(0.25), 0.25);
        assert_monotonic_nondecreasing(Curve::Linear, 50);
    }

    #[test]
    fn sine_family() {
        for flavor in [Flavor::In, Flavor::Out, Flavor::InOut] {
            assert_endpoints(Curve::Sine(flavor));
            assert_monotonic_nondecreasing(Curve::Sine(flavor), 50);
        }
        // sine_in(0.5) = 1 - cos(pi/4) = 1 - sqrt(2)/2
        assert_close(
            Curve::Sine(Flavor::In).eval(0.5),
            1.0 - std::f32::consts::FRAC_1_SQRT_2,
        );
        // sine_out(0.5) = sin(pi/4) = sqrt(2)/2
        assert_close(
            Curve::Sine(Flavor::Out).eval(0.5),
            std::f32::consts::FRAC_1_SQRT_2,
        );
    }

    #[test]
    fn quad_family() {
        for flavor in [Flavor::In, Flavor::Out, Flavor::InOut] {
            assert_endpoints(Curve::Quad(flavor));
            assert_monotonic_nondecreasing(Curve::Quad(flavor), 50);
        }
        // exact closed form: quad_in(0.5) = 0.25
        assert_close(Curve::Quad(Flavor::In).eval(0.5), 0.25);
        // quad_out(0.5) = 1 - 0.5^2 = 0.75
        assert_close(Curve::Quad(Flavor::Out).eval(0.5), 0.75);
    }

    #[test]
    fn cubic_family() {
        for flavor in [Flavor::In, Flavor::Out, Flavor::InOut] {
            assert_endpoints(Curve::Cubic(flavor));
            assert_monotonic_nondecreasing(Curve::Cubic(flavor), 50);
        }
        // cubic_in(0.5) = 0.125
        assert_close(Curve::Cubic(Flavor::In).eval(0.5), 0.125);
    }

    #[test]
    fn quart_family() {
        for flavor in [Flavor::In, Flavor::Out, Flavor::InOut] {
            assert_endpoints(Curve::Quart(flavor));
            assert_monotonic_nondecreasing(Curve::Quart(flavor), 50);
        }
        // quart_in(0.5) = 0.0625
        assert_close(Curve::Quart(Flavor::In).eval(0.5), 0.0625);
    }

    #[test]
    fn quint_family() {
        for flavor in [Flavor::In, Flavor::Out, Flavor::InOut] {
            assert_endpoints(Curve::Quint(flavor));
            assert_monotonic_nondecreasing(Curve::Quint(flavor), 50);
        }
        // quint_in(0.5) = 0.03125
        assert_close(Curve::Quint(Flavor::In).eval(0.5), 0.03125);
    }

    #[test]
    fn expo_family() {
        for flavor in [Flavor::In, Flavor::Out, Flavor::InOut] {
            assert_endpoints(Curve::Expo(flavor));
            assert_monotonic_nondecreasing(Curve::Expo(flavor), 50);
        }
        // expo_in(0.5) = 2^(10*0.5-10) = 2^-5 = 1/32
        assert_close(Curve::Expo(Flavor::In).eval(0.5), 1.0 / 32.0);
    }

    #[test]
    fn circ_family() {
        for flavor in [Flavor::In, Flavor::Out, Flavor::InOut] {
            assert_endpoints(Curve::Circ(flavor));
            assert_monotonic_nondecreasing(Curve::Circ(flavor), 50);
        }
        // circ_in(0.5) = 1 - sqrt(1 - 0.25) = 1 - sqrt(0.75)
        assert_close(Curve::Circ(Flavor::In).eval(0.5), 1.0 - 0.75f32.sqrt());
    }

    #[test]
    fn back_family_endpoints_exact_and_overshoots() {
        for flavor in [Flavor::In, Flavor::Out, Flavor::InOut] {
            // f(0)=0, f(1)=1 hold exactly regardless of overshoot (c3 - c1 = 1
            // algebraically), even though the family is non-monotonic.
            assert_endpoints(Curve::Back {
                flavor,
                overshoot: 1.70158,
            });
        }
        // back_in dips below 0 before rising (the "wind-up").
        let back_in = Curve::Back {
            flavor: Flavor::In,
            overshoot: 1.70158,
        };
        let min = (0..=100)
            .map(|i| back_in.eval(i as f32 / 100.0))
            .fold(f32::INFINITY, f32::min);
        assert!(min < -0.05, "expected back_in to undershoot, min={min}");
        assert!(min > -1.0, "back_in undershoot out of sane bound: {min}");

        // back_out overshoots above 1 before settling.
        let back_out = Curve::Back {
            flavor: Flavor::Out,
            overshoot: 1.70158,
        };
        let max = (0..=100)
            .map(|i| back_out.eval(i as f32 / 100.0))
            .fold(f32::NEG_INFINITY, f32::max);
        assert!(max > 1.05, "expected back_out to overshoot, max={max}");
        assert!(max < 2.0, "back_out overshoot out of sane bound: {max}");
    }

    #[test]
    fn elastic_family_endpoints_exact_and_oscillates() {
        for flavor in [Flavor::In, Flavor::Out, Flavor::InOut] {
            assert_endpoints(Curve::Elastic(flavor));
        }
        let elastic_out = Curve::Elastic(Flavor::Out);
        let max = (0..=200)
            .map(|i| elastic_out.eval(i as f32 / 200.0))
            .fold(f32::NEG_INFINITY, f32::max);
        assert!(max > 1.0, "expected elastic_out to overshoot, max={max}");
        assert!(max < 2.5, "elastic_out overshoot out of sane bound: {max}");
    }

    #[test]
    fn bounce_family_endpoints_exact_and_non_monotonic() {
        for flavor in [Flavor::In, Flavor::Out, Flavor::InOut] {
            assert_endpoints(Curve::Bounce(flavor));
        }
        // bounce_out(1) = 1 exactly (algebraic identity: 0.984375 + 0.015625).
        assert_close(Curve::Bounce(Flavor::Out).eval(1.0), 1.0);
        // Genuinely bounces: some interior sample must be a local max that
        // is later exceeded (i.e. not monotonic).
        let bounce_out = Curve::Bounce(Flavor::Out);
        let samples: Vec<f32> = (0..=100)
            .map(|i| bounce_out.eval(i as f32 / 100.0))
            .collect();
        let is_monotonic = samples.windows(2).all(|w| w[1] + 1e-5 >= w[0]);
        assert!(!is_monotonic, "expected bounce_out to be non-monotonic");
    }

    #[test]
    fn square_is_a_midpoint_step() {
        assert_close(Curve::Square.eval(0.0), 0.0);
        assert_close(Curve::Square.eval(0.49), 0.0);
        assert_close(Curve::Square.eval(0.5), 1.0);
        assert_close(Curve::Square.eval(1.0), 1.0);
    }

    #[test]
    fn bezier_zero_tension_is_exactly_linear() {
        let b = Curve::Bezier { tension: 0.0 };
        for i in 0..=20 {
            let t = i as f32 / 20.0;
            assert_close(b.eval(t), t);
        }
    }

    #[test]
    fn bezier_nonzero_tension_still_hits_endpoints_and_stays_monotonic() {
        for tension in [-0.3, 0.2, 0.4] {
            let b = Curve::Bezier { tension };
            assert_endpoints(b);
            assert_monotonic_nondecreasing(b, 50);
        }
    }

    #[test]
    fn family_tag_matches_variant_ignoring_flavor() {
        assert_eq!(
            Curve::Quad(Flavor::In).family(),
            Curve::Quad(Flavor::Out).family()
        );
        assert_ne!(
            Curve::Quad(Flavor::In).family(),
            Curve::Cubic(Flavor::In).family()
        );
        assert_eq!(
            Curve::Back {
                flavor: Flavor::In,
                overshoot: 1.0
            }
            .family(),
            Curve::Back {
                flavor: Flavor::Out,
                overshoot: 2.0
            }
            .family()
        );
    }
}
