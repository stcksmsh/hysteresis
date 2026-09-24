//! `FieldOutput` — a `VizOutput` for dense arrays of many single-DOF elements
//! (Rozin-style tile/pin arrays). See `SINTEZA_CHOREOGRAPHY.md` §5.3.

use hyst_core::signal::{ResolvedTargets, TargetDecl, VizOutput};

use crate::array_topology::ArrayTopology;
use crate::cadence::TickAccumulator;
use crate::diff::DiffTracker;
use crate::failure::FailureMask;
use crate::field::{FieldSource, FieldValue};

/// Field value -> element DOF. Pluggable per §5.3 ("expose the mapping as a parameter; it is
/// the array's entire aesthetic") — e.g. brightness->tilt, or value->orientation/contour.
pub type ElementMapping = Box<dyn Fn(FieldValue) -> f32 + Send>;

/// One element's value as of the last tick that changed it — what a diff-only transport sends.
#[derive(Debug, Clone, PartialEq)]
pub struct ElementUpdate {
    pub index: usize,
    pub channel: String,
    pub value: f32,
}

pub const DEFAULT_REFRESH_HZ: f32 = 15.0;

/// Samples a [`FieldSource`] through an [`ArrayTopology`] at a fixed ~15 Hz cadence
/// (independent of render frame rate — see [`crate::cadence::TickAccumulator`]), applies a
/// per-element [`ElementMapping`], and tracks a diff so only elements whose resolved value
/// actually changed are reported via [`FieldOutput::last_diff`].
///
/// Element failure: [`FieldOutput::mark_element_failed`] freezes that element's value at
/// whatever it held at the moment of failure — the element is simply excluded from all future
/// resampling, so it neither errors nor drags down any other element (§7: "a dead element
/// should read as one wrong tile, never a stalled or corrupted region").
pub struct FieldOutput {
    id: String,
    topology: ArrayTopology,
    source: Box<dyn FieldSource + Send>,
    mapping: ElementMapping,
    tick: TickAccumulator,
    diff: DiffTracker<f32>,
    failures: FailureMask,
    values: Vec<f32>,
    last_diff: Vec<ElementUpdate>,
}

impl FieldOutput {
    pub fn new(
        id: impl Into<String>,
        topology: ArrayTopology,
        source: Box<dyn FieldSource + Send>,
        mapping: ElementMapping,
    ) -> Self {
        Self::with_refresh_hz(id, topology, source, mapping, DEFAULT_REFRESH_HZ)
    }

    pub fn with_refresh_hz(
        id: impl Into<String>,
        topology: ArrayTopology,
        source: Box<dyn FieldSource + Send>,
        mapping: ElementMapping,
        hz: f32,
    ) -> Self {
        let n = topology.len();
        Self {
            id: id.into(),
            topology,
            source,
            mapping,
            tick: TickAccumulator::new(hz),
            diff: DiffTracker::new(n),
            failures: FailureMask::new(n),
            values: vec![0.0; n],
            last_diff: Vec::new(),
        }
    }

    pub fn element_count(&self) -> usize {
        self.topology.len()
    }

    /// Current resolved value for element `index` (frozen if failed).
    pub fn value(&self, index: usize) -> f32 {
        self.values[index]
    }

    pub fn is_element_failed(&self, index: usize) -> bool {
        self.failures.is_failed(index)
    }

    /// Marks an element dead. Its value stays exactly what it was at this moment forever
    /// after — it is excluded from resampling, not reset to a sentinel.
    pub fn mark_element_failed(&mut self, index: usize) {
        self.failures.mark_failed(index);
    }

    /// Elements whose value changed on the most recent tick (empty between ticks, or if
    /// nothing changed). This is the diff-only transmission surface a real transport reads.
    pub fn last_diff(&self) -> &[ElementUpdate] {
        &self.last_diff
    }

    fn tick_once(&mut self) {
        for i in 0..self.topology.len() {
            if self.failures.is_failed(i) {
                continue; // frozen: never resampled, never touched again.
            }
            let slot = &self.topology.elements[i];
            let fv = self.source.sample(slot.u, slot.v);
            self.values[i] = (self.mapping)(fv);
        }
        self.last_diff = self
            .diff
            .diff(&self.values)
            .into_iter()
            .map(|(i, value)| ElementUpdate {
                index: i,
                channel: self.topology.elements[i].channel.clone(),
                value,
            })
            .collect();
    }
}

impl VizOutput for FieldOutput {
    fn id(&self) -> &str {
        &self.id
    }

    /// No routable targets yet — this session's sources are synthetic/self-driven, not bus-fed.
    /// A future procedural FieldSource driven by live bus signals would declare targets here.
    fn targets(&self) -> &[TargetDecl] {
        &[]
    }

    fn update(&mut self, dt: f32, _resolved_targets: &ResolvedTargets) {
        let period = self.tick.period();
        let ticks = self.tick.advance(dt);
        for _ in 0..ticks {
            self.source.advance(period);
            self.tick_once();
        }
    }

    fn dispose(&mut self) {}
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::field::BilinearGradient;
    use hyst_core::signal::ResolvedTargets;

    fn empty_targets() -> ResolvedTargets {
        ResolvedTargets::new()
    }

    fn identity_mapping() -> ElementMapping {
        Box::new(|fv: FieldValue| fv.value())
    }

    /// Mandatory acceptance test (plan R5 done-when): N=100+ elements sampling a known field
    /// with exact expected values per element; failure injection degrades only the failed
    /// tiles while everything else keeps tracking a changing field.
    #[test]
    fn n100_field_exact_values_then_failure_injection_degrades_only_failed_tiles() {
        let topo = ArrayTopology::grid(10, 10, "e");
        assert_eq!(topo.len(), 100);
        let positions: Vec<(f32, f32)> = topo.elements.iter().map(|e| (e.u, e.v)).collect();

        // Coefficients live in a Cell so the test can change the field between tick batches
        // and independently recompute the exact expected value with the same formula.
        let coeffs = std::sync::Arc::new(std::sync::Mutex::new((0.0f32, 1.0f32, 0.0f32, 0.0f32)));
        struct MutableBilinear(std::sync::Arc<std::sync::Mutex<(f32, f32, f32, f32)>>);
        impl FieldSource for MutableBilinear {
            fn sample(&self, u: f32, v: f32) -> FieldValue {
                let (a, bu, bv, buv) = *self.0.lock().unwrap();
                BilinearGradient::new(a, bu, bv, buv).sample(u, v)
            }
        }

        let source = Box::new(MutableBilinear(coeffs.clone()));
        let mut output =
            FieldOutput::with_refresh_hz("test-field", topo, source, identity_mapping(), 15.0);
        let period = 1.0 / 15.0;
        let targets = empty_targets();

        // Phase 1: several ticks against a stable field. Every element must match the exact
        // bilinear formula for its own (u, v) - not "some non-zero output".
        for _ in 0..5 {
            output.update(period, &targets);
        }
        let (a, bu, bv, buv) = *coeffs.lock().unwrap();
        for (i, &(u, v)) in positions.iter().enumerate() {
            let expected = a + bu * u + bv * v + buv * u * v;
            assert_eq!(
                output.value(i),
                expected,
                "element {i} mismatch before failure injection"
            );
        }

        // Mark 8 scattered elements failed; snapshot their frozen expected value.
        let failed_indices = [3usize, 17, 22, 41, 58, 63, 79, 94];
        let mut frozen = std::collections::HashMap::new();
        for &i in &failed_indices {
            frozen.insert(i, output.value(i));
            output.mark_element_failed(i);
        }

        // Phase 2: change the field, run more ticks.
        *coeffs.lock().unwrap() = (0.5, 0.0, 1.0, 0.25);
        for _ in 0..5 {
            output.update(period, &targets);
        }
        let (a2, bu2, bv2, buv2) = *coeffs.lock().unwrap();

        for (i, &(u, v)) in positions.iter().enumerate() {
            if failed_indices.contains(&i) {
                assert_eq!(
                    output.value(i),
                    frozen[&i],
                    "failed element {i} must stay frozen"
                );
                assert!(output.is_element_failed(i));
            } else {
                let expected = a2 + bu2 * u + bv2 * v + buv2 * u * v;
                assert_eq!(
                    output.value(i),
                    expected,
                    "healthy element {i} must track the new field exactly"
                );
                assert!(!output.is_element_failed(i));
            }
        }
    }

    /// Diff-only transmission: changing one element's field input must emit exactly that one
    /// element in last_diff. A naive "resend everything every tick" impl fails this.
    #[test]
    fn diff_reports_only_the_element_that_actually_changed() {
        // Shared Mutex (not Cell/Rc: FieldSource must be Send+Sync-free but Send) so the test
        // can mutate field values after the source is boxed/moved in.
        let shared = std::sync::Arc::new(std::sync::Mutex::new([0.0f32; 5]));
        struct MapField(std::sync::Arc<std::sync::Mutex<[f32; 5]>>);
        impl FieldSource for MapField {
            fn sample(&self, u: f32, _v: f32) -> FieldValue {
                let index = (u * 10.0).round() as usize; // topology below uses u = index/10.
                FieldValue::scalar(self.0.lock().unwrap()[index])
            }
        }
        let topo = ArrayTopology::new(
            (0..5)
                .map(|i| crate::array_topology::ElementSlot {
                    u: i as f32 / 10.0,
                    v: 0.5,
                    channel: format!("c{i}"),
                })
                .collect(),
        );
        let mut output = FieldOutput::with_refresh_hz(
            "diff-test",
            topo,
            Box::new(MapField(shared.clone())),
            identity_mapping(),
            15.0,
        );
        let period = 1.0 / 15.0;
        let targets = empty_targets();

        // First tick: everything is new, so a full diff is expected and correct.
        output.update(period, &targets);
        assert_eq!(output.last_diff().len(), 5);

        // Nothing changes: diff must be empty.
        output.update(period, &targets);
        assert!(output.last_diff().is_empty());

        // Change only element 2's underlying field value.
        shared.lock().unwrap()[2] = 9.0;
        output.update(period, &targets);
        assert_eq!(
            output.last_diff().len(),
            1,
            "only element 2 changed, diff must contain exactly one entry"
        );
        assert_eq!(output.last_diff()[0].index, 2);
        assert_eq!(output.last_diff()[0].value, 9.0);
        assert_eq!(output.last_diff()[0].channel, "c2");
    }

    #[test]
    fn sub_period_dt_does_not_tick_and_produces_no_diff() {
        let topo = ArrayTopology::grid(2, 2, "e");
        let source = Box::new(BilinearGradient::horizontal_ramp());
        let mut output =
            FieldOutput::with_refresh_hz("slow", topo, source, identity_mapping(), 15.0);
        // Way under one period (1/15 ~= 0.0667s).
        output.update(0.001, &empty_targets());
        assert!(output.last_diff().is_empty());
        assert_eq!(output.value(0), 0.0); // never ticked, still the constructed default
    }
}
