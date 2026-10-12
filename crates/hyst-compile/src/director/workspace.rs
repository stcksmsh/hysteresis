//! The known future of the song: events the planner can see ahead of time,
//! lifted out of the moments code. See `docs/B_WORKSPACE.md`.

use super::{mean, Evidence};

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum EventKind {
    Arrival,
    Repeat,
    Cut,
    PhraseEnd,
}

/// `sign`: +1 the music lifts, -1 it falls away, 0 neither (an entry from near
/// silence, or not a lift event). `strength`: an arrival's measured strength; a
/// repeat's similarity; a cut's length in seconds; 1 for a phrase end.
#[derive(Debug, Clone, PartialEq)]
pub struct Event {
    pub time: f64,
    pub kind: EventKind,
    pub sign: f64,
    pub strength: f64,
}

/// Events in construction order: arrivals as given, repeats, cuts, phrase ends.
#[derive(Debug, Clone, PartialEq)]
pub struct Foresight {
    pub events: Vec<Event>,
}

/// (change, lift, sign) at an arrival: the level four beats after against
/// eight beats before. Eight beats back, because the last bar of a build is
/// often a loud fill. Music starting from near nothing is an entry, not a lift.
pub(super) fn arrival_lift(
    level: &[f64],
    rate: f64,
    beat: f64,
    loud: f64,
    time: f64,
) -> (f64, f64, f64) {
    let before = mean(level, rate, time - 8.0 * beat, time - 0.5 * beat);
    let after = mean(level, rate, time + 0.5 * beat, time + 4.0 * beat);
    let change = after / before.max(1e-9);
    let entry = before < 0.15 * loud;
    let lift = if entry {
        0.0
    } else {
        ((change - 1.0) / 0.5).clamp(0.0, 1.0)
    };
    let sign = if lift > 0.0 {
        1.0
    } else if change < 1.0 && !entry {
        -1.0
    } else {
        0.0
    };
    (change, lift, sign)
}

/// Cuts: the mix drops to near nothing for half a beat to four beats between
/// two dense stretches. (from, to) in seconds.
fn cuts(data: &Evidence, beat: f64) -> Vec<(f64, f64)> {
    let level = &data.rms_envelope;
    let mut spans = Vec::new();
    if level.is_empty() {
        return spans;
    }
    let frame = data.envelope_rate;
    let mut sorted = level.clone();
    sorted.sort_by(f64::total_cmp);
    let dense = 0.6 * sorted[sorted.len() * 3 / 4];
    let mut i = 0;
    while i < level.len() {
        let around = mean(
            level,
            frame,
            i as f64 / frame - 4.0 * beat,
            i as f64 / frame,
        );
        if level[i] >= 0.2 * around || around < dense {
            i += 1;
            continue;
        }
        let start = i;
        while i < level.len() && level[i] < 0.2 * around {
            i += 1;
        }
        let (from, to) = (start as f64 / frame, i as f64 / frame);
        let after = mean(level, frame, to, to + 2.0 * beat);
        if (0.5 * beat..=4.0 * beat).contains(&(to - from)) && after >= dense {
            spans.push((from, to));
        }
    }
    spans
}

impl Foresight {
    pub(super) fn new(
        data: &Evidence,
        arrivals: &[(f64, f64)],
        level: &[f64],
        loud: f64,
        rate: f64,
        beat: f64,
    ) -> Self {
        let mut events = Vec::new();
        for &(time, strength) in arrivals {
            let sign = arrival_lift(level, rate, beat, loud, time).2;
            events.push(Event {
                time,
                kind: EventKind::Arrival,
                sign,
                strength,
            });
        }
        let phrases = &data.musical_memory.phrases;
        let repeated = phrases
            .iter()
            .filter(|p| p.repeat_of.is_some())
            .map(|p| (p.start, p.similarity));
        let material = data
            .musical_structure
            .repeated_material
            .iter()
            .map(|r| (r.repeat_start, r.similarity));
        events.extend(repeated.chain(material).map(|(time, strength)| Event {
            time,
            kind: EventKind::Repeat,
            sign: 0.0,
            strength,
        }));
        events.extend(cuts(data, beat).into_iter().map(|(from, to)| Event {
            time: from,
            kind: EventKind::Cut,
            sign: 0.0,
            strength: to - from,
        }));
        events.extend(
            phrases
                .iter()
                .filter(|p| p.end < data.duration)
                .map(|p| Event {
                    time: p.end,
                    kind: EventKind::PhraseEnd,
                    sign: 0.0,
                    strength: 1.0,
                }),
        );
        Self { events }
    }

    pub(super) fn of(&self, kind: EventKind) -> impl Iterator<Item = &Event> {
        self.events.iter().filter(move |e| e.kind == kind)
    }
}
