//! Ensemble topology (§3.1) — the one piece of shared data formations
//! read. Kept generic on purpose: swapping a ring for a line means
//! constructing a different `Topology`, never touching formation logic.

use std::collections::HashMap;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct AgentId(pub u32);

#[derive(Debug, Clone, PartialEq)]
pub struct Topology {
    pub agents: Vec<AgentId>,
    /// Propagation sequence for wave/canon.
    pub order: Vec<AgentId>,
    /// Adjacency (ring: ±1).
    pub neighbors: HashMap<AgentId, Vec<AgentId>>,
    /// Mirror pairing, if a symmetry axis exists.
    pub axis_pairs: Option<Vec<(AgentId, AgentId)>>,
}

impl Topology {
    /// A ring of `n` agents (ids `0..n`), each neighboring its immediate
    /// ring neighbors, mirror-paired opposite-to-opposite when `n` is even.
    /// A convenience constructor for tests/acceptance criteria — not
    /// mandated by the spec, but the acceptance test needs *a* concrete
    /// topology to run N=1/6/12 through.
    pub fn ring(n: u32) -> Topology {
        let agents: Vec<AgentId> = (0..n).map(AgentId).collect();
        let mut neighbors = HashMap::new();
        for i in 0..n {
            let prev = AgentId((i + n - 1) % n);
            let next = AgentId((i + 1) % n);
            let list = if n == 1 {
                vec![]
            } else if n == 2 {
                vec![prev]
            } else {
                vec![prev, next]
            };
            neighbors.insert(AgentId(i), list);
        }
        let axis_pairs = if n >= 2 && n.is_multiple_of(2) {
            Some(
                (0..n / 2)
                    .map(|i| (AgentId(i), AgentId(i + n / 2)))
                    .collect(),
            )
        } else {
            None
        };
        Topology {
            agents: agents.clone(),
            order: agents,
            neighbors,
            axis_pairs,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ring_n1_has_no_neighbors_and_no_axis_pairs() {
        let t = Topology::ring(1);
        assert_eq!(t.agents, vec![AgentId(0)]);
        assert_eq!(t.neighbors[&AgentId(0)], vec![]);
        assert!(t.axis_pairs.is_none());
    }

    #[test]
    fn ring_n6_neighbors_wrap_and_axis_pairs_are_opposite() {
        let t = Topology::ring(6);
        assert_eq!(t.neighbors[&AgentId(0)], vec![AgentId(5), AgentId(1)]);
        assert_eq!(t.neighbors[&AgentId(5)], vec![AgentId(4), AgentId(0)]);
        assert_eq!(
            t.axis_pairs.unwrap(),
            vec![
                (AgentId(0), AgentId(3)),
                (AgentId(1), AgentId(4)),
                (AgentId(2), AgentId(5)),
            ]
        );
    }
}
