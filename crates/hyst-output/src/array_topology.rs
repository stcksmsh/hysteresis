//! `ArrayTopology` — dense-array element mapping. Distinct from `hyst-choreo`'s `Topology`
//! (sparse-agent formations); no dependency on that crate. See `SINTEZA_CHOREOGRAPHY.md` §5.3.

/// One physical element: its normalized sample position in the field, and which output
/// channel/DOF it's bound to (a string id — transport-agnostic, no real hardware channel
/// numbering assumed yet).
#[derive(Debug, Clone)]
pub struct ElementSlot {
    pub u: f32,
    pub v: f32,
    pub channel: String,
}

/// Maps each physical element to a `(u, v)` field sample position + channel. Changing the
/// array's shape/resolution/wiring changes only this, nothing about `FieldOutput` itself.
#[derive(Debug, Clone, Default)]
pub struct ArrayTopology {
    pub elements: Vec<ElementSlot>,
}

impl ArrayTopology {
    pub fn new(elements: Vec<ElementSlot>) -> Self {
        Self { elements }
    }

    pub fn len(&self) -> usize {
        self.elements.len()
    }

    pub fn is_empty(&self) -> bool {
        self.elements.is_empty()
    }

    /// A regular `rows x cols` grid, element centers evenly spaced over `[0,1] x [0,1]`,
    /// channel ids `"{channel_prefix}{index}"`. Convenience for tests/simple rigs, not the
    /// only valid topology (a real rig may be irregular).
    pub fn grid(rows: usize, cols: usize, channel_prefix: &str) -> Self {
        let mut elements = Vec::with_capacity(rows * cols);
        for r in 0..rows {
            for c in 0..cols {
                let u = if cols > 1 {
                    (c as f32 + 0.5) / cols as f32
                } else {
                    0.5
                };
                let v = if rows > 1 {
                    (r as f32 + 0.5) / rows as f32
                } else {
                    0.5
                };
                elements.push(ElementSlot {
                    u,
                    v,
                    channel: format!("{channel_prefix}{}", r * cols + c),
                });
            }
        }
        Self { elements }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn grid_covers_full_range_with_correct_count_and_channels() {
        let topo = ArrayTopology::grid(10, 10, "e");
        assert_eq!(topo.len(), 100);
        assert_eq!(topo.elements[0].channel, "e0");
        assert_eq!(topo.elements[99].channel, "e99");
        // Corner elements sit at the first/last cell centers, not exactly 0/1.
        assert_eq!(topo.elements[0].u, 0.05);
        assert_eq!(topo.elements[9].u, 0.95);
    }
}
