//! Generic per-element failure tracking, shared by any output driving many independently
//! addressable physical elements.
//!
//! `SINTEZA_CHOREOGRAPHY.md` §7 treats element-level failure in a dense array as "a *when*,
//! not an *if*": hundreds of elements means hundreds of failure points, and the required
//! behavior is that a dead element degrades to a single wrong tile, never a stalled or
//! corrupted region and never a stalled bus. [`FailureMask`] is the bookkeeping primitive for
//! that — it does not decide *what* a failed element reads as (that is caller/output-specific,
//! see [`crate::field_output::FieldOutput`]'s "freeze at last value" policy), only which
//! indices are marked dead.

/// A flat "is element `i` dead" table, injectable at runtime (a real failure is discovered
/// live, not known upfront) and O(1) to query per element per tick, so marking failures
/// doesn't turn per-tick work into anything worse than the healthy case.
#[derive(Debug, Clone)]
pub struct FailureMask {
    failed: Vec<bool>,
}

impl FailureMask {
    pub fn new(len: usize) -> Self {
        Self {
            failed: vec![false; len],
        }
    }

    pub fn len(&self) -> usize {
        self.failed.len()
    }

    pub fn is_empty(&self) -> bool {
        self.failed.is_empty()
    }

    /// Marks element `index` as failed. Idempotent — marking an already-failed element again
    /// is a no-op, not an error.
    ///
    /// Panics if `index >= len()` (an out-of-range failure report is a caller bug, not a
    /// runtime condition — the element set is fixed at construction).
    pub fn mark_failed(&mut self, index: usize) {
        self.failed[index] = true;
    }

    pub fn is_failed(&self, index: usize) -> bool {
        self.failed[index]
    }

    /// Every currently-failed index, in ascending order.
    pub fn failed_indices(&self) -> impl Iterator<Item = usize> + '_ {
        self.failed
            .iter()
            .enumerate()
            .filter_map(|(i, &f)| f.then_some(i))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn starts_with_nothing_failed() {
        let mask = FailureMask::new(10);
        assert!((0..10).all(|i| !mask.is_failed(i)));
        assert_eq!(mask.failed_indices().count(), 0);
    }

    #[test]
    fn marking_one_element_does_not_affect_others() {
        let mut mask = FailureMask::new(5);
        mask.mark_failed(2);
        assert!(mask.is_failed(2));
        for i in [0, 1, 3, 4] {
            assert!(!mask.is_failed(i));
        }
    }

    #[test]
    fn marking_twice_is_idempotent() {
        let mut mask = FailureMask::new(3);
        mask.mark_failed(1);
        mask.mark_failed(1);
        assert_eq!(mask.failed_indices().collect::<Vec<_>>(), vec![1]);
    }
}
