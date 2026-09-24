//! Generic "only tell me what changed" tracking, shared by any output that transmits
//! per-element state to a downstream bus/transport where re-sending unchanged elements is
//! wasted bandwidth (a real constraint for a dense physical array — see
//! `SINTEZA_CHOREOGRAPHY.md` §5.3's "send only changed elements" requirement — but generic
//! enough for any indexed collection of values, not written against `FieldOutput` specifically).

/// Tracks the last-transmitted value at each index and reports only the indices whose value
/// has changed since the last time [`DiffTracker::diff`] was called for them.
///
/// An index that has never been diffed before counts as "changed" the first time (there is
/// nothing to compare against yet — the first tick is necessarily a full frame). Every call
/// after that only reports genuine changes.
#[derive(Debug, Clone)]
pub struct DiffTracker<T> {
    last_sent: Vec<Option<T>>,
}

impl<T: Copy + PartialEq> DiffTracker<T> {
    pub fn new(len: usize) -> Self {
        Self {
            last_sent: vec![None; len],
        }
    }

    pub fn len(&self) -> usize {
        self.last_sent.len()
    }

    pub fn is_empty(&self) -> bool {
        self.last_sent.is_empty()
    }

    /// Compares `current[i]` against what was last reported changed for index `i`, for every
    /// index. Returns `(index, value)` pairs for indices whose value differs (or has never
    /// been reported before), in index order. Updates internal state so calling this again
    /// with the same `current` reports nothing.
    ///
    /// Panics if `current.len() != self.len()` — a mismatched length means the caller resized
    /// its element set without rebuilding the tracker, which is a bug, not a runtime condition
    /// to degrade gracefully from.
    pub fn diff(&mut self, current: &[T]) -> Vec<(usize, T)> {
        assert_eq!(
            current.len(),
            self.last_sent.len(),
            "DiffTracker length mismatch"
        );
        let mut changed = Vec::new();
        for (i, &value) in current.iter().enumerate() {
            let is_changed = match self.last_sent[i] {
                Some(prev) => prev != value,
                None => true,
            };
            if is_changed {
                self.last_sent[i] = Some(value);
                changed.push((i, value));
            }
        }
        changed
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn first_diff_reports_every_element() {
        let mut tracker = DiffTracker::new(4);
        let diffs = tracker.diff(&[1.0, 2.0, 3.0, 4.0]);
        assert_eq!(diffs, vec![(0, 1.0), (1, 2.0), (2, 3.0), (3, 4.0)]);
    }

    #[test]
    fn unchanged_values_produce_an_empty_diff() {
        let mut tracker = DiffTracker::new(3);
        tracker.diff(&[1.0, 1.0, 1.0]);
        let diffs = tracker.diff(&[1.0, 1.0, 1.0]);
        assert!(diffs.is_empty());
    }

    #[test]
    fn only_the_changed_element_is_reported_a_naive_send_everything_impl_would_fail_this() {
        let mut tracker = DiffTracker::new(5);
        tracker.diff(&[0.0, 0.0, 0.0, 0.0, 0.0]);
        let diffs = tracker.diff(&[0.0, 0.0, 9.0, 0.0, 0.0]);
        assert_eq!(diffs, vec![(2, 9.0)]);
    }
}
