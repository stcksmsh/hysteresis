//! Formation modes (§3): pure functions `(topology, base move, timing
//! anchor) -> per-agent instructions`. Never references a literal agent —
//! only topology positions/roles — so N=1/6/12 fall out of the same
//! formula (§3's own acceptance bar, mirrored in this module's tests).
//!
//! No sequencing logic here (which formation is active when — that's R7's
//! Director). This layer only guarantees formations are clean, composable,
//! swappable pure functions.

use std::collections::{HashMap, VecDeque};

use crate::generator::Rng;
use crate::moves::{ChannelRole, Move, Pose};
use crate::topology::{AgentId, Topology};

/// Shared timing context a formation schedules against.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct TimingAnchor {
    pub start_time: f64,
    /// Resolves `Duration::Beats` moves to seconds; ignored for
    /// `Duration::Seconds`.
    pub seconds_per_beat: f64,
}

/// Which channels get value-inverted (`1.0 - eval(t)`) for a given agent —
/// how Mirror is expressed as data rather than by mutating a `Move`'s
/// curves. Evaluating/applying this is an output-layer concern (out of
/// scope here); this crate only produces the instruction.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct MirrorSpec {
    pub inverted_channels: Vec<ChannelRole>,
}

/// One agent's resolved instruction from a formation call. A single,
/// uniform record — every formation fills in only the fields its mode
/// actually varies, leaving the rest at their neutral/no-op default.
#[derive(Debug, Clone, PartialEq)]
pub struct AgentInstruction {
    pub agent: AgentId,
    pub mv: Move,
    /// Offset from `TimingAnchor::start_time`, in seconds.
    pub time_offset: f64,
    pub mirror: MirrorSpec,
    /// Affine/reference-shape pull (§3.2) — `None`/`blend=0.0` elsewhere.
    pub target_pose: Option<Pose>,
    pub blend: f32,
}

impl AgentInstruction {
    fn neutral(agent: AgentId, mv: Move) -> Self {
        AgentInstruction {
            agent,
            mv,
            time_offset: 0.0,
            mirror: MirrorSpec::default(),
            target_pose: None,
            blend: 0.0,
        }
    }
}

/// Ordering source (§3.2): one parameter, not two formation types.
#[derive(Debug, Clone)]
pub enum OrderingSource {
    /// Fixed, position-based: `topology.order` as-is.
    Spatial,
    /// Originates from whichever agent holds the highest-priority signal,
    /// propagating outward by topology distance. Default per spec.
    SalienceAnchored { salience: HashMap<AgentId, f32> },
}

/// Resolve the effective propagation order for a topology + ordering
/// source. `SalienceAnchored` picks the max-salience agent as leader, then
/// BFS-orders the rest by neighbor distance (ties broken by the agent's
/// position in `topology.order`, for determinism).
pub fn effective_order(topology: &Topology, ordering: &OrderingSource) -> Vec<AgentId> {
    match ordering {
        OrderingSource::Spatial => topology.order.clone(),
        OrderingSource::SalienceAnchored { salience } => {
            let leader = *topology
                .order
                .iter()
                .max_by(|a, b| {
                    let sa = salience.get(a).copied().unwrap_or(f32::NEG_INFINITY);
                    let sb = salience.get(b).copied().unwrap_or(f32::NEG_INFINITY);
                    sa.partial_cmp(&sb).unwrap()
                })
                .expect("topology.order must not be empty");

            let pos_in_order: HashMap<AgentId, usize> = topology
                .order
                .iter()
                .enumerate()
                .map(|(i, a)| (*a, i))
                .collect();

            let mut visited = std::collections::HashSet::new();
            let mut queue = VecDeque::new();
            let mut result = Vec::new();
            queue.push_back(leader);
            visited.insert(leader);
            while let Some(current) = queue.pop_front() {
                result.push(current);
                let mut next: Vec<AgentId> = topology
                    .neighbors
                    .get(&current)
                    .into_iter()
                    .flatten()
                    .filter(|n| !visited.contains(n))
                    .copied()
                    .collect();
                next.sort_by_key(|a| pos_in_order.get(a).copied().unwrap_or(usize::MAX));
                for n in next {
                    if visited.insert(n) {
                        queue.push_back(n);
                    }
                }
            }
            result
        }
    }
}

/// Unison: zero offset for every agent.
pub fn unison(
    topology: &Topology,
    base_move: &Move,
    _anchor: TimingAnchor,
) -> Vec<AgentInstruction> {
    topology
        .agents
        .iter()
        .map(|&agent| AgentInstruction::neutral(agent, base_move.clone()))
        .collect()
}

/// Canon/wave: agent at propagation position `i` (of `n`) starts
/// `i * (duration / n)` seconds after the anchor. At `n=1` this is
/// `0 * duration = 0` — exactly unison, with no special-cased branch.
pub fn canon(
    topology: &Topology,
    base_move: &Move,
    anchor: TimingAnchor,
    ordering: &OrderingSource,
) -> Vec<AgentInstruction> {
    let order = effective_order(topology, ordering);
    let n = order.len() as f64;
    let duration_secs = base_move.duration.to_seconds(anchor.seconds_per_beat);
    order
        .into_iter()
        .enumerate()
        .map(|(i, agent)| {
            let mut instr = AgentInstruction::neutral(agent, base_move.clone());
            instr.time_offset = i as f64 * (duration_secs / n);
            instr
        })
        .collect()
}

/// Call-and-response: leader (order[0]) plays first (offset 0); every
/// other agent answers after one full move-length delay. At `n=1` there
/// are no followers — the sole agent's instruction is the leader's,
/// unmodified.
pub fn call_and_response(
    topology: &Topology,
    base_move: &Move,
    anchor: TimingAnchor,
    ordering: &OrderingSource,
) -> Vec<AgentInstruction> {
    let order = effective_order(topology, ordering);
    let duration_secs = base_move.duration.to_seconds(anchor.seconds_per_beat);
    order
        .into_iter()
        .enumerate()
        .map(|(i, agent)| {
            let mut instr = AgentInstruction::neutral(agent, base_move.clone());
            instr.time_offset = if i == 0 { 0.0 } else { duration_secs };
            instr
        })
        .collect()
}

/// Breathe/converge-diverge: a shared envelope scales amplitude
/// (`intensity`); each agent otherwise plays its own copy of `base_move`
/// independently. `envelope = 1.0` (neutral) reproduces `base_move`
/// unmodified — the N=1 no-op case falls out of that, not a special case.
pub fn breathe(
    topology: &Topology,
    base_move: &Move,
    envelope: f32,
    _anchor: TimingAnchor,
) -> Vec<AgentInstruction> {
    topology
        .agents
        .iter()
        .map(|&agent| {
            let mut mv = base_move.clone();
            mv.intensity *= envelope;
            AgentInstruction::neutral(agent, mv)
        })
        .collect()
}

/// Affine/reference-shape: each agent with an entry in `target_poses` gets
/// that pose attached as a pull weighted by `blend` (`0.0` = no pull, i.e.
/// no-op). Agents absent from `target_poses` get `target_pose = None`.
pub fn affine(
    topology: &Topology,
    base_move: &Move,
    target_poses: &HashMap<AgentId, Pose>,
    blend: f32,
    _anchor: TimingAnchor,
) -> Vec<AgentInstruction> {
    topology
        .agents
        .iter()
        .map(|&agent| {
            let mut instr = AgentInstruction::neutral(agent, base_move.clone());
            instr.target_pose = target_poses.get(&agent).cloned();
            instr.blend = blend;
            instr
        })
        .collect()
}

/// Scatter/independent (§3.2): first-class, not a fallback. Each agent
/// gets its own independently-selected move, zero shared transform —
/// `select` is called once per agent and its result passed through
/// unmodified (offset 0, no mirror/blend), which is the identity/no-op
/// this mode's contract promises regardless of agent count.
pub fn scatter(
    topology: &Topology,
    rng: &mut Rng,
    mut select: impl FnMut(AgentId, &mut Rng) -> Move,
    _anchor: TimingAnchor,
) -> Vec<AgentInstruction> {
    topology
        .agents
        .iter()
        .map(|&agent| AgentInstruction::neutral(agent, select(agent, rng)))
        .collect()
}

/// Mirror (§3.2): a spatial transform layerable on top of any formation
/// above. Not baked into each mode — takes already-computed instructions
/// and marks the second agent of each axis pair to invert the given
/// channels. A topology with no `axis_pairs` (e.g. N=1) leaves every
/// instruction untouched, which is the N=1 no-op case for this transform.
pub fn apply_mirror(
    topology: &Topology,
    channels: &[ChannelRole],
    mut instructions: Vec<AgentInstruction>,
) -> Vec<AgentInstruction> {
    let Some(pairs) = &topology.axis_pairs else {
        return instructions;
    };
    let mirrored: std::collections::HashSet<AgentId> = pairs.iter().map(|(_, b)| *b).collect();
    for instr in &mut instructions {
        if mirrored.contains(&instr.agent) {
            instr.mirror = MirrorSpec {
                inverted_channels: channels.to_vec(),
            };
        }
    }
    instructions
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::curve::{Curve, Flavor};
    use crate::effort::Effort;
    use crate::moves::{Duration, PoseRequirement, Provenance, TimescaleRole};
    use std::collections::BTreeMap;

    fn base_move(duration_secs: f32) -> Move {
        let mut channels = BTreeMap::new();
        channels.insert(ChannelRole::PrimaryElevation, Curve::Quad(Flavor::Out));
        Move {
            channels,
            duration: Duration::Seconds(duration_secs),
            entry_pose: PoseRequirement::Agnostic,
            exit_pose: PoseRequirement::Agnostic,
            arrival_anchor: None,
            role: TimescaleRole::Groove,
            effort: Effort::NEUTRAL,
            applicability_tags: vec![],
            intensity: 1.0,
            provenance: Provenance::Authored,
        }
    }

    fn anchor() -> TimingAnchor {
        TimingAnchor {
            start_time: 0.0,
            seconds_per_beat: 0.5,
        }
    }

    // ---- the mandatory R4 acceptance test: N=1/6/12, identical inputs ----

    #[test]
    fn unison_n1_is_exact_noop() {
        let mv = base_move(2.0);
        let t = Topology::ring(1);
        let out = unison(&t, &mv, anchor());
        assert_eq!(out.len(), 1);
        assert_eq!(out[0].mv, mv);
        assert_eq!(out[0].time_offset, 0.0);
    }

    #[test]
    fn canon_n1_is_exact_noop() {
        let mv = base_move(2.0);
        let t = Topology::ring(1);
        let out = canon(&t, &mv, anchor(), &OrderingSource::Spatial);
        assert_eq!(out.len(), 1);
        assert_eq!(out[0].mv, mv);
        assert_eq!(out[0].time_offset, 0.0);
    }

    #[test]
    fn call_and_response_n1_is_exact_noop() {
        let mv = base_move(2.0);
        let t = Topology::ring(1);
        let out = call_and_response(&t, &mv, anchor(), &OrderingSource::Spatial);
        assert_eq!(out.len(), 1);
        assert_eq!(out[0].mv, mv);
        assert_eq!(out[0].time_offset, 0.0);
    }

    #[test]
    fn breathe_n1_with_neutral_envelope_is_exact_noop() {
        let mv = base_move(2.0);
        let t = Topology::ring(1);
        let out = breathe(&t, &mv, 1.0, anchor());
        assert_eq!(out.len(), 1);
        assert_eq!(out[0].mv, mv);
    }

    #[test]
    fn affine_n1_with_no_target_is_exact_noop() {
        let mv = base_move(2.0);
        let t = Topology::ring(1);
        let out = affine(&t, &mv, &HashMap::new(), 0.0, anchor());
        assert_eq!(out.len(), 1);
        assert_eq!(out[0].mv, mv);
        assert_eq!(out[0].target_pose, None);
        assert_eq!(out[0].blend, 0.0);
    }

    #[test]
    fn scatter_n1_passes_selection_through_unmodified() {
        let t = Topology::ring(1);
        let selected = base_move(3.0);
        let mut rng = Rng::new(1);
        let out = scatter(&t, &mut rng, |_, _| selected.clone(), anchor());
        assert_eq!(out.len(), 1);
        assert_eq!(out[0].mv, selected);
        assert_eq!(out[0].time_offset, 0.0);
    }

    #[test]
    fn mirror_n1_is_exact_noop_no_axis_pairs() {
        let mv = base_move(2.0);
        let t = Topology::ring(1);
        let out = unison(&t, &mv, anchor());
        let out = apply_mirror(&t, &[ChannelRole::PrimaryElevation], out);
        assert_eq!(out[0].mirror, MirrorSpec::default());
    }

    #[test]
    fn canon_n6_and_n12_offsets_match_exact_formula() {
        for n in [6u32, 12] {
            let mv = base_move(4.0); // duration = 4s
            let t = Topology::ring(n);
            let out = canon(&t, &mv, anchor(), &OrderingSource::Spatial);
            assert_eq!(out.len(), n as usize);
            for (i, instr) in out.iter().enumerate() {
                let expected = i as f64 * (4.0 / n as f64);
                assert_eq!(instr.agent, AgentId(i as u32));
                assert!(
                    (instr.time_offset - expected).abs() < 1e-9,
                    "n={n} i={i}: expected {expected}, got {}",
                    instr.time_offset
                );
                assert_eq!(instr.mv, mv);
            }
        }
    }

    #[test]
    fn call_and_response_n6_and_n12_leader_then_full_delay() {
        for n in [6u32, 12] {
            let mv = base_move(1.5);
            let t = Topology::ring(n);
            let out = call_and_response(&t, &mv, anchor(), &OrderingSource::Spatial);
            assert_eq!(out[0].time_offset, 0.0);
            for instr in &out[1..] {
                assert_eq!(instr.time_offset, 1.5);
            }
        }
    }

    #[test]
    fn breathe_n6_scales_intensity_by_shared_envelope() {
        let mv = base_move(1.0);
        let t = Topology::ring(6);
        let out = breathe(&t, &mv, 0.4, anchor());
        assert_eq!(out.len(), 6);
        for instr in out {
            assert!((instr.mv.intensity - 0.4).abs() < 1e-6);
        }
    }

    #[test]
    fn affine_n6_attaches_target_pose_only_where_provided() {
        let mv = base_move(1.0);
        let t = Topology::ring(6);
        let mut target_poses = HashMap::new();
        let mut pose: Pose = BTreeMap::new();
        pose.insert(ChannelRole::PrimaryElevation, 0.9);
        target_poses.insert(AgentId(2), pose.clone());
        let out = affine(&t, &mv, &target_poses, 0.7, anchor());
        for instr in &out {
            if instr.agent == AgentId(2) {
                assert_eq!(instr.target_pose, Some(pose.clone()));
                assert_eq!(instr.blend, 0.7);
            } else {
                assert_eq!(instr.target_pose, None);
            }
        }
    }

    #[test]
    fn mirror_n6_inverts_only_second_of_each_axis_pair() {
        let mv = base_move(1.0);
        let t = Topology::ring(6);
        let out = unison(&t, &mv, anchor());
        let out = apply_mirror(&t, &[ChannelRole::PrimaryElevation], out);
        // ring(6) axis_pairs: (0,3) (1,4) (2,5) -> agents 3,4,5 mirrored.
        for instr in &out {
            let should_mirror = instr.agent.0 >= 3;
            assert_eq!(
                !instr.mirror.inverted_channels.is_empty(),
                should_mirror,
                "agent {:?}",
                instr.agent
            );
        }
    }

    #[test]
    fn scatter_n6_gives_each_agent_its_own_independent_move() {
        let t = Topology::ring(6);
        let mut rng = Rng::new(9);
        let out = scatter(
            &t,
            &mut rng,
            |_, rng| {
                crate::generator::generate_move(
                    rng,
                    &[ChannelRole::PrimaryElevation],
                    Duration::Seconds(1.0),
                )
            },
            anchor(),
        );
        assert_eq!(out.len(), 6);
        let distinct_families: std::collections::HashSet<_> = out
            .iter()
            .map(|i| i.mv.channels[&ChannelRole::PrimaryElevation].family())
            .collect();
        assert!(
            distinct_families.len() > 1,
            "expected independent variety across agents"
        );
        for instr in &out {
            assert_eq!(instr.time_offset, 0.0);
        }
    }

    #[test]
    fn salience_anchored_ordering_picks_max_salience_leader() {
        let t = Topology::ring(6);
        let mut salience = HashMap::new();
        salience.insert(AgentId(4), 1.0);
        let order = effective_order(&t, &OrderingSource::SalienceAnchored { salience });
        assert_eq!(order[0], AgentId(4));
        // BFS neighbors of 4 in a ring are 3 and 5 (distance 1).
        assert!(order[1] == AgentId(3) || order[1] == AgentId(5));
        assert!(order[2] == AgentId(3) || order[2] == AgentId(5));
        assert_eq!(order.len(), 6);
    }

    #[test]
    fn spatial_ordering_matches_topology_order_unchanged() {
        let t = Topology::ring(12);
        let order = effective_order(&t, &OrderingSource::Spatial);
        assert_eq!(order, t.order);
    }
}
