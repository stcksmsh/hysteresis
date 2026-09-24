//! The field abstraction `FieldOutput` samples through, decoupled from any real renderer.
//!
//! `SINTEZA_CHOREOGRAPHY.md` §5.3: "the natural sources are what the screen pipeline already
//! renders — the memory field, the Julia substrate, any `.hyst` shader's output... a dense
//! array is a low-resolution physical render target for the existing visual layer." That
//! renderer (R2, `hyst-render`) is not finished yet (see `AGENTS.md` §4: passes/Julia
//! substrate/GLSL-to-WGSL translation all still open) — [`FieldSource`] is the seam that lets
//! `FieldOutput` be built and tested now, and swapped onto a real renderer later without
//! touching `FieldOutput` itself.
//!
//! **Future real integration point** (once R2 lands): a `FieldSource` impl that wraps R2's
//! render target — most likely reading back a rendered texture/buffer for the current frame
//! (the same `wgpu` readback path `hyst-render`'s `OffscreenTarget::read_pixels` already
//! exercises) and bilinearly sampling it at `(u, v)`. `FieldOutput` itself needs no changes;
//! only a new `FieldSource` implementation is added, in `hyst-render` or here, whichever side
//! ends up owning the `wgpu` dependency.

/// A sampled field value at one point. Modeled as up to four scalar components rather than a
/// bare `f32` because §5.3 names two different mapping families: brightness → tilt (needs one
/// scalar) and value → orientation/contour (can want more than one, e.g. a gradient direction).
/// Synthetic/scalar sources only ever populate `components[0]`; a future richer source (e.g. an
/// RGBA render target) can use more.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct FieldValue {
    pub components: [f32; 4],
}

impl FieldValue {
    pub fn scalar(v: f32) -> Self {
        Self {
            components: [v, 0.0, 0.0, 0.0],
        }
    }

    /// The primary (first) component — what a scalar mapping function reads.
    pub fn value(&self) -> f32 {
        self.components[0]
    }
}

/// A field `FieldOutput` can sample, at a normalized `(u, v)` in `[0, 1] x [0, 1]`.
///
/// Deliberately minimal and with no dependency on any renderer crate — see the module doc for
/// what a real implementation will look like once R2 exists. `sample` takes `&self` (many
/// elements sample the same field per tick); `advance` is the separate, explicit hook for a
/// source with internal time-varying state (e.g. a moving blob) to step itself forward — called
/// once per tick by `FieldOutput`, with that tick's fixed period, before any element samples.
pub trait FieldSource {
    fn sample(&self, u: f32, v: f32) -> FieldValue;

    /// Advance any internal time-varying state by `dt` seconds. Default no-op for static
    /// fields (a fixed gradient, a fixed checkerboard).
    fn advance(&mut self, _dt: f32) {}
}

/// A synthetic bilinear field: `value(u, v) = a + bu*u + bv*v + buv*u*v`. Exact and trivially
/// recomputable by a test — the reference "known field" fixture for FieldOutput's acceptance
/// test.
#[derive(Debug, Clone, Copy)]
pub struct BilinearGradient {
    pub a: f32,
    pub bu: f32,
    pub bv: f32,
    pub buv: f32,
}

impl BilinearGradient {
    pub fn new(a: f32, bu: f32, bv: f32, buv: f32) -> Self {
        Self { a, bu, bv, buv }
    }

    /// A plain horizontal ramp: `value(u, v) = u`.
    pub fn horizontal_ramp() -> Self {
        Self::new(0.0, 1.0, 0.0, 0.0)
    }
}

impl FieldSource for BilinearGradient {
    fn sample(&self, u: f32, v: f32) -> FieldValue {
        FieldValue::scalar(self.a + self.bu * u + self.bv * v + self.buv * u * v)
    }
}

/// A synthetic checkerboard: alternates between `0.0` and `1.0` over a `cells x cells` grid.
#[derive(Debug, Clone, Copy)]
pub struct Checkerboard {
    pub cells: u32,
}

impl FieldSource for Checkerboard {
    fn sample(&self, u: f32, v: f32) -> FieldValue {
        let cells = self.cells.max(1) as f32;
        let cu = (u * cells) as i64;
        let cv = (v * cells) as i64;
        FieldValue::scalar(if (cu + cv) % 2 == 0 { 1.0 } else { 0.0 })
    }
}

/// A synthetic moving Gaussian blob, orbiting the field center. Exercises `advance` (internal
/// time-varying state), unlike the two static sources above.
#[derive(Debug, Clone, Copy)]
pub struct MovingGaussianBlob {
    pub sigma: f32,
    pub angular_speed: f32,
    pub orbit_radius: f32,
    t: f32,
}

impl MovingGaussianBlob {
    pub fn new(sigma: f32, angular_speed: f32, orbit_radius: f32) -> Self {
        Self {
            sigma,
            angular_speed,
            orbit_radius,
            t: 0.0,
        }
    }
}

impl FieldSource for MovingGaussianBlob {
    fn advance(&mut self, dt: f32) {
        self.t += dt;
    }

    fn sample(&self, u: f32, v: f32) -> FieldValue {
        let cx = 0.5 + self.orbit_radius * (self.angular_speed * self.t).cos();
        let cy = 0.5 + self.orbit_radius * (self.angular_speed * self.t).sin();
        let d2 = (u - cx).powi(2) + (v - cy).powi(2);
        FieldValue::scalar((-d2 / (2.0 * self.sigma * self.sigma)).exp())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bilinear_gradient_matches_its_own_formula_exactly() {
        let g = BilinearGradient::new(0.1, 0.5, -0.25, 2.0);
        for &(u, v) in &[(0.0f32, 0.0f32), (0.3, 0.7), (1.0, 1.0)] {
            let expected = 0.1 + 0.5 * u + -0.25 * v + 2.0 * u * v;
            assert_eq!(g.sample(u, v).value(), expected);
        }
    }

    #[test]
    fn horizontal_ramp_is_exactly_u() {
        let g = BilinearGradient::horizontal_ramp();
        assert_eq!(g.sample(0.0, 0.9).value(), 0.0);
        assert_eq!(g.sample(0.25, 0.9).value(), 0.25);
        assert_eq!(g.sample(1.0, 0.0).value(), 1.0);
    }

    #[test]
    fn checkerboard_alternates() {
        let board = Checkerboard { cells: 2 };
        // cell (0,0) -> 0, cell (1,0) -> 1, cell (0,1) -> 1, cell (1,1) -> 0
        assert_eq!(board.sample(0.1, 0.1).value(), 1.0);
        assert_eq!(board.sample(0.6, 0.1).value(), 0.0);
        assert_eq!(board.sample(0.1, 0.6).value(), 0.0);
        assert_eq!(board.sample(0.6, 0.6).value(), 1.0);
    }

    #[test]
    fn moving_blob_only_changes_after_advance() {
        let mut blob = MovingGaussianBlob::new(0.2, 1.0, 0.3);
        let v0 = blob.sample(0.8, 0.5).value();
        // Sampling repeatedly without advancing must be stable.
        assert_eq!(blob.sample(0.8, 0.5).value(), v0);
        blob.advance(0.5);
        let v1 = blob.sample(0.8, 0.5).value();
        assert_ne!(v0, v1);
    }
}
