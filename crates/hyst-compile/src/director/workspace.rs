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

// ---------------------------------------------------------------------------
// B: the workspace. Not wired into `compile_ensemble`; nothing reads it yet.

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum WorkspaceMode {
    #[default]
    Off,
    Rehearsed,
    Schematic,
}

/// One beat of observation, at `beat_zero + n * beat_period`. The means run
/// over the beat itself: [time, time + period).
#[derive(Debug, Clone, PartialEq)]
pub struct BeatObs {
    pub time: f64,
    /// Mean wholeTrackActivity: bass, drums, vocals, other.
    pub activity: [f64; 4],
    /// sqrt of the summed stem absoluteRms²: the `level` series.
    pub level: f64,
    pub drum_density: f64,
    /// (lane index, brightness) of the leading lane; None without a noteTrack.
    pub leader: Option<(usize, f64)>,
    /// The 32-step rhythm of the phrase that starts on this beat.
    pub phrase: Option<Vec<f64>>,
    /// Sidecar novelty candidate on this beat (percentile). Sidecar knowledge:
    /// `step` honours it only when it has Foresight.
    pub novelty: Option<f64>,
}

/// Plain slices from the sidecar. `phrases`: (start, 32-step rhythm).
/// `novelty`: (time, scale in beats, percentile). `repeats`: repeat start times.
pub struct ObsInput<'a> {
    pub beat_zero: f64,
    pub beat_period: f64,
    pub duration: f64,
    pub rate: f64,
    pub activity: [&'a [f64]; 4],
    pub absolute_rms: [&'a [f64]; 4],
    pub drum_density: &'a [f64],
    /// Per beat: leader lane index, leader brightness.
    pub leader: Option<(&'a [usize], &'a [f64])>,
    pub phrases: &'a [(f64, &'a [f64])],
    pub novelty: &'a [(f64, u32, f64)],
    pub repeats: &'a [f64],
}

pub fn observations(input: &ObsInput) -> Vec<BeatObs> {
    let ObsInput {
        beat_zero,
        beat_period: period,
        rate,
        ..
    } = *input;
    let count = ((input.duration - beat_zero) / period).floor().max(-1.0) as i64 + 1;
    let count = count.max(0) as usize;
    let frames = input
        .absolute_rms
        .iter()
        .map(|s| s.len())
        .min()
        .unwrap_or(0);
    let level: Vec<f64> = (0..frames)
        .map(|i| {
            let power = input.absolute_rms.iter().map(|s| s[i].powi(2));
            power.sum::<f64>().sqrt()
        })
        .collect();
    let mut obs: Vec<BeatObs> = (0..count)
        .map(|n| {
            let time = beat_zero + n as f64 * period;
            let at = |series: &[f64]| mean(series, rate, time, time + period);
            BeatObs {
                time,
                activity: std::array::from_fn(|i| at(input.activity[i])),
                level: at(&level),
                drum_density: at(input.drum_density),
                leader: input
                    .leader
                    .and_then(|(index, brightness)| Some((*index.get(n)?, *brightness.get(n)?))),
                phrase: None,
                novelty: None,
            }
        })
        .collect();
    let beat_of = |t: f64| ((t - beat_zero) / period).round().max(0.0) as usize;
    for (start, rhythm) in input.phrases {
        if let Some(o) = obs.get_mut(beat_of(*start)) {
            o.phrase = Some(rhythm.to_vec());
        }
    }
    // "Within one phrase of a repeat": a typical phrase, 16 beats if unknown.
    let span = match input.phrases {
        [first, .., last] => (last.0 - first.0) / (input.phrases.len() - 1) as f64,
        _ => 16.0 * period,
    };
    for &(time, scale, percentile) in input.novelty {
        let near_repeat = input.repeats.iter().any(|r| (r - time).abs() < span);
        if scale >= 8 && percentile >= 0.94 && !near_repeat {
            if let Some(o) = obs.get_mut(beat_of(time)) {
                o.novelty = Some(percentile);
            }
        }
    }
    obs
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Field {
    /// Arousal, 0..1.5. Slow decay is the afterglow.
    pub gain: f64,
    /// Held breath, 0..1.
    pub tension: f64,
    /// Composure, 0..1. Low: the ensemble briefly loses unity.
    pub precision: f64,
    /// Valence prediction error at an arrival, -1..1.
    pub approach: f64,
    /// Familiarity within the song, 0..2.
    pub habituation: f64,
    /// Schematic surprise, 0..1.
    pub surprise: f64,
}

impl Default for Field {
    fn default() -> Self {
        Self {
            gain: 0.0,
            tension: 0.0,
            precision: 1.0,
            approach: 0.0,
            habituation: 0.0,
            surprise: 0.0,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum BasinKind {
    Recognition,
    Lift,
    Novelty,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Basin {
    pub time: f64,
    pub beat: usize,
    pub kind: BasinKind,
    pub strength: f64,
}

const DIMS: usize = 8;
/// Time constants in beats of L1 (bar), L2 (phrase), L4 (section).
const TAU: [f64; 3] = [4.0, 16.0, 64.0];
/// Weights for L1, L2, L3, L4.
const WEIGHTS: [f64; 4] = [0.5, 0.3, 0.3, 0.2];
/// An RMS z-score below KNEE is no error; KNEE + SPAN is full error. Not in
/// the spec: a steady loop has z of about 1, so raw z cannot be an error.
const Z_KNEE: f64 = 1.5;
const Z_SPAN: f64 = 4.0;
/// Floor on a dimension's variance (sd 0.05), so a flat signal does not make
/// the first wiggle an infinite z.
const VAR_FLOOR: f64 = 0.0025;
/// Gain: attack and decay in beats.
const GAIN_ATTACK: f64 = 0.5;
const GAIN_DECAY: f64 = 16.0;
const TENSION_TAU: f64 = 1.0;
const TENSION_WINDOW: f64 = 32.0;
const PRECISION_RECOVERY: f64 = 8.0;
const APPROACH_DECAY: f64 = 8.0;
const HABITUATION_DECAY: f64 = 64.0;
const PEAK_DECAY: f64 = 256.0;

/// Fraction of the way a first-order system moves in one beat.
fn step_rate(tau: f64) -> f64 {
    1.0 - (-1.0 / tau).exp()
}

fn approach(x: f64, target: f64, tau: f64) -> f64 {
    x + (target - x) * step_rate(tau)
}

/// Leaky mean and variance per dimension, and the error against them.
#[derive(Debug, Clone)]
struct Leaky {
    tau: f64,
    mean: [f64; DIMS],
    var: [f64; DIMS],
    init: [bool; DIMS],
}

impl Leaky {
    fn new(tau: f64) -> Self {
        Self {
            tau,
            mean: [0.0; DIMS],
            var: [0.0; DIMS],
            init: [false; DIMS],
        }
    }

    /// Error of `x` against the state before it, then learn `x`. 0 until
    /// `tau` beats have been seen.
    fn error(&mut self, x: &[Option<f64>; DIMS], n: usize) -> f64 {
        let (mut sum, mut used) = (0.0, 0);
        let a = 1.0 / self.tau;
        for (d, v) in x.iter().enumerate() {
            let Some(v) = *v else { continue };
            if self.init[d] {
                let gap = v - self.mean[d];
                sum += gap * gap / (self.var[d] + VAR_FLOOR);
                used += 1;
                self.mean[d] += a * gap;
                self.var[d] += a * (gap * gap - self.var[d]);
            } else {
                self.init[d] = true;
                self.mean[d] = v;
            }
        }
        if used == 0 || (n as f64) < self.tau {
            return 0.0;
        }
        (((sum / used as f64).sqrt() - Z_KNEE) / Z_SPAN).clamp(0.0, 1.0)
    }
}

/// Leaky variance of one error series: its precision is 1 / (1 + this).
#[derive(Debug, Clone, Default)]
struct ErrorSpread {
    mean: f64,
    var: f64,
}

impl ErrorSpread {
    fn precision_then_learn(&mut self, e: f64, tau: f64) -> f64 {
        let precision = 1.0 / (1.0 + self.var);
        let a = 1.0 / tau;
        let gap = e - self.mean;
        self.mean += a * gap;
        self.var += a * (gap * gap - self.var);
        precision
    }
}

fn pearson(a: &[f64], b: &[f64]) -> f64 {
    let n = a.len().min(b.len()) as f64;
    let (ma, mb) = (a.iter().sum::<f64>() / n, b.iter().sum::<f64>() / n);
    let (mut ab, mut aa, mut bb) = (0.0, 0.0, 0.0);
    for (x, y) in a.iter().zip(b) {
        ab += (x - ma) * (y - mb);
        aa += (x - ma).powi(2);
        bb += (y - mb).powi(2);
    }
    if aa < 1e-12 || bb < 1e-12 {
        // A flat rhythm matches only another flat rhythm of the same height.
        return if aa < 1e-12 && bb < 1e-12 && (ma - mb).abs() < 1e-6 {
            1.0
        } else {
            0.0
        };
    }
    ab / (aa * bb).sqrt()
}

/// One workspace, one beat at a time. `step` is pure in (self, obs,
/// foresight, n): Schematic never sees a beat after `n`.
#[derive(Debug, Clone)]
pub struct State {
    period: f64,
    levels: [Leaky; 3],
    spread: [ErrorSpread; 4],
    phrases: Vec<Vec<f64>>,
    recent_level: std::collections::VecDeque<f64>,
    peak: f64,
    prev_surprise: f64,
    field: Field,
    /// Basins emitted by the latest `step`.
    pub basins: Vec<Basin>,
}

impl State {
    pub fn new(beat_period: f64) -> Self {
        Self {
            period: beat_period,
            levels: TAU.map(Leaky::new),
            spread: Default::default(),
            phrases: Vec::new(),
            recent_level: Default::default(),
            peak: 0.0,
            prev_surprise: 0.0,
            field: Field::default(),
            basins: Vec::new(),
        }
    }

    pub fn step(&mut self, obs: &BeatObs, foresight: Option<&Foresight>, n: usize) -> Field {
        self.basins.clear();
        let half = 0.5 * self.period;
        let mut f = self.field;

        // Schematic surprise: only this beat and earlier.
        let x: [Option<f64>; DIMS] = [
            Some(obs.activity[0]),
            Some(obs.activity[1]),
            Some(obs.activity[2]),
            Some(obs.activity[3]),
            Some(obs.level),
            Some(obs.drum_density),
            obs.leader.map(|l| l.0 as f64 / 8.0),
            obs.leader.map(|l| l.1 / 128.0),
        ];
        let [e1, e2, e4] = [0, 1, 2].map(|i| self.levels[i].error(&x, n));
        // L3 predicts a phrase from the most similar earlier one. The phrase
        // starting now counts as "now": its own rhythm is read at its first
        // beat, an allowance the spec makes on purpose.
        let mut e3 = 0.0;
        if let Some(rhythm) = &obs.phrase {
            if !self.phrases.is_empty() {
                let best = (self.phrases.iter())
                    .map(|p| pearson(rhythm, p))
                    .fold(f64::MIN, f64::max);
                e3 = (1.0 - best).clamp(0.0, 1.0);
            }
            self.phrases.push(rhythm.clone());
        }
        let pi = [
            self.spread[0].precision_then_learn(e1, TAU[0]),
            self.spread[1].precision_then_learn(e2, TAU[1]),
            if obs.phrase.is_some() {
                self.spread[2].precision_then_learn(e3, 2.0)
            } else {
                1.0 / (1.0 + self.spread[2].var)
            },
            self.spread[3].precision_then_learn(e4, TAU[2]),
        ];
        let errors = [e1, e2, e3, e4];
        let s = (0..4)
            .map(|i| WEIGHTS[i] * pi[i] * errors[i])
            .sum::<f64>()
            .clamp(0.0, 1.0);

        // Level against its recent past, for the measured sign at an arrival.
        self.peak = obs.level.max(self.peak * (1.0 - 1.0 / PEAK_DECAY));
        let measured = if self.recent_level.is_empty() {
            0.0
        } else {
            let before = self.recent_level.iter().sum::<f64>() / self.recent_level.len() as f64;
            let change = obs.level / before.max(1e-9);
            if before < 0.15 * self.peak {
                0.0
            } else if change > 1.1 {
                1.0
            } else if change < 0.9 {
                -1.0
            } else {
                0.0
            }
        };
        self.recent_level.push_back(obs.level);
        if self.recent_level.len() > 8 {
            self.recent_level.pop_front();
        }

        // Known events on this beat: the veridical stream.
        let here = |e: &&Event| e.time >= obs.time - half && e.time < obs.time + half;
        let (mut arrival, mut recognition): (Option<&Event>, Option<f64>) = (None, None);
        if let Some(fore) = foresight {
            arrival = fore
                .of(EventKind::Arrival)
                .filter(here)
                .max_by(|a, b| a.strength.total_cmp(&b.strength));
            recognition = fore
                .of(EventKind::Repeat)
                .filter(here)
                .filter(|e| e.strength >= 0.8)
                .map(|e| e.strength)
                .max_by(f64::total_cmp);
        }
        let lift = arrival.filter(|e| e.sign > 0.0);

        // Field.
        let intensity = (obs.level / self.peak.max(1e-9)).min(1.0);
        let target = intensity + 0.6 * s;
        let tau = if target > f.gain {
            GAIN_ATTACK
        } else {
            GAIN_DECAY
        };
        f.gain = approach(f.gain, target, tau);

        let tension_before = f.tension;
        let ramp = foresight
            .and_then(|fore| {
                (fore.of(EventKind::Arrival))
                    .filter(|e| e.sign > 0.0 && e.time >= obs.time + half)
                    .map(|e| e.time)
                    .min_by(f64::total_cmp)
            })
            .map_or(0.0, |time| {
                let d = (time - obs.time) / self.period;
                if d <= TENSION_WINDOW {
                    (1.0 - d / TENSION_WINDOW) * (1.0 - s)
                } else {
                    0.0
                }
            });
        f.tension = if lift.is_some() {
            0.0
        } else {
            approach(f.tension, ramp, TENSION_TAU)
        };
        if let Some(e) = lift {
            f.gain += 0.5 + 0.5 * tension_before;
            self.basins.push(Basin {
                time: obs.time,
                beat: n,
                kind: BasinKind::Lift,
                strength: e.strength,
            });
        }

        f.precision = approach(f.precision, 1.0, PRECISION_RECOVERY);
        if s > 0.5 {
            f.precision -= s;
        }
        f.habituation = approach(f.habituation, 0.0, HABITUATION_DECAY);
        if let Some(similarity) = recognition {
            f.precision = 1.0;
            f.habituation += 1.0;
            f.gain += 0.2;
            self.basins.push(Basin {
                time: obs.time,
                beat: n,
                kind: BasinKind::Recognition,
                strength: similarity,
            });
        }

        // An arrival: a known one (Rehearsed, expected sign from Foresight) or,
        // without foresight, a surprise that just crossed 0.5 (expected 0).
        let arrived = match arrival {
            Some(e) => Some(e.sign),
            None => (foresight.is_none() && s > 0.5 && self.prev_surprise <= 0.5).then_some(0.0),
        };
        f.approach = approach(f.approach, 0.0, APPROACH_DECAY);
        if let Some(expected) = arrived {
            f.approach = (measured - expected).clamp(-1.0, 1.0);
        }

        let novel = match foresight {
            Some(_) => obs.novelty,
            None => (obs.phrase.is_some() && e3 > 0.5).then_some(e3),
        };
        if let Some(strength) = novel {
            f.precision -= s;
            f.gain += 0.3 * s;
            self.basins.push(Basin {
                time: obs.time,
                beat: n,
                kind: BasinKind::Novelty,
                strength,
            });
        }

        f.gain = f.gain.clamp(0.0, 1.5);
        f.tension = f.tension.clamp(0.0, 1.0);
        f.precision = f.precision.clamp(0.0, 1.0);
        f.approach = f.approach.clamp(-1.0, 1.0);
        f.habituation = f.habituation.clamp(0.0, 2.0);
        f.surprise = s;
        self.prev_surprise = s;
        self.field = f;
        f
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct Workspace {
    pub field: Vec<Field>,
    pub basins: Vec<Basin>,
    pub beat_zero: f64,
    pub beat_period: f64,
}

impl Workspace {
    /// Linear between beats, clamped at the ends.
    pub fn field_at(&self, t: f64) -> Field {
        let last = self.field.len() - 1;
        let x = ((t - self.beat_zero) / self.beat_period).clamp(0.0, last as f64);
        let i = (x.floor() as usize).min(last);
        let (a, b) = (self.field[i], self.field[(i + 1).min(last)]);
        let k = x - i as f64;
        let mix = |p: f64, q: f64| p + (q - p) * k;
        Field {
            gain: mix(a.gain, b.gain),
            tension: mix(a.tension, b.tension),
            precision: mix(a.precision, b.precision),
            approach: mix(a.approach, b.approach),
            habituation: mix(a.habituation, b.habituation),
            surprise: mix(a.surprise, b.surprise),
        }
    }
}

/// None for `Off` and for an empty `obs`. `Rehearsed` hands `foresight` to
/// every step; `Schematic` hands none.
pub fn run(
    mode: WorkspaceMode,
    beat_zero: f64,
    beat_period: f64,
    obs: &[BeatObs],
    foresight: &Foresight,
) -> Option<Workspace> {
    if mode == WorkspaceMode::Off || obs.is_empty() {
        return None;
    }
    let fore = (mode == WorkspaceMode::Rehearsed).then_some(foresight);
    let mut state = State::new(beat_period);
    let mut basins = Vec::new();
    let field = obs
        .iter()
        .enumerate()
        .map(|(n, o)| {
            let f = state.step(o, fore, n);
            basins.append(&mut state.basins);
            f
        })
        .collect();
    Some(Workspace {
        field,
        basins,
        beat_zero,
        beat_period,
    })
}

#[cfg(test)]
mod workspace_tests {
    use super::super::tests::synthetic;
    use super::*;

    const BEAT: f64 = 0.5;

    fn obs_of(json: &str) -> (Evidence, Vec<BeatObs>) {
        let data: Evidence = serde_json::from_str(json).unwrap();
        let sources: Vec<_> = ["bass", "drums", "vocals", "other"]
            .iter()
            .map(|k| &data.stem_interpretation.sources[*k])
            .collect();
        let phrases: Vec<(f64, &[f64])> = (data.musical_memory.phrases.iter())
            .map(|p| (p.start, p.rhythm.as_slice()))
            .collect();
        let obs = observations(&ObsInput {
            beat_zero: 0.0,
            beat_period: BEAT,
            duration: data.duration,
            rate: 10.0,
            activity: std::array::from_fn(|i| sources[i].whole_track_activity.as_slice()),
            absolute_rms: std::array::from_fn(|i| sources[i].absolute_rms.as_slice()),
            drum_density: &sources[1].transient_density,
            leader: None,
            phrases: &phrases,
            novelty: &[],
            repeats: &[],
        });
        (data, obs)
    }

    /// A period-4 groove: it varies, but it is the same every bar.
    fn groove(n: usize) -> [f64; 4] {
        let k = [0.3, 0.5, 0.35, 0.6][n % 4];
        [k, 0.4 + 0.2 * (n % 2) as f64, 0.2, 0.3]
    }

    fn run_mode(mode: WorkspaceMode, obs: &[BeatObs], f: &Foresight) -> Workspace {
        run(mode, 0.0, BEAT, obs, f).unwrap()
    }

    fn drop_at(a: usize) -> Foresight {
        Foresight {
            events: vec![Event {
                time: a as f64 * BEAT,
                kind: EventKind::Arrival,
                sign: 1.0,
                strength: 1.0,
            }],
        }
    }

    #[test]
    fn off_makes_nothing() {
        let (_, obs) = obs_of(&synthetic(8, groove, |_| 0.4, 4, &[]));
        assert!(run(WorkspaceMode::Off, 0.0, BEAT, &obs, &drop_at(4)).is_none());
    }

    #[test]
    fn schematic_field_up_to_n_ignores_the_future() {
        let (_, a) = obs_of(&synthetic(80, groove, |_| 0.4, 16, &[]));
        let (_, mut b) = obs_of(&synthetic(
            80,
            |n| if n > 30 { [0.9; 4] } else { groove(n) },
            |n| if n > 30 { 0.9 } else { 0.4 },
            16,
            &[],
        ));
        b[32].phrase = Some(vec![0.5; 32]);
        let none = Foresight { events: vec![] };
        let (fa, fb) = (
            run_mode(WorkspaceMode::Schematic, &a, &none),
            run_mode(WorkspaceMode::Schematic, &b, &none),
        );
        assert_eq!(fa.field[..=30], fb.field[..=30]);
        assert_ne!(fa.field[40], fb.field[40]);
    }

    #[test]
    fn steady_loop_is_not_surprising() {
        let (_, obs) = obs_of(&synthetic(
            48,
            groove,
            |n| 0.4 + 0.02 * (n % 4) as f64,
            16,
            &[],
        ));
        let w = run_mode(
            WorkspaceMode::Schematic,
            &obs,
            &Foresight { events: vec![] },
        );
        let worst = w.field[32..].iter().map(|f| f.surprise).fold(0.0, f64::max);
        println!("loop: max s after two phrases {worst:.4}");
        assert!(worst < 0.1, "s {worst}");
    }

    #[test]
    fn groove_break_spikes() {
        let jump = |n| if n >= 48 { [0.9; 4] } else { groove(n) };
        let (_, obs) = obs_of(&synthetic(
            56,
            jump,
            |n| if n >= 48 { 0.8 } else { 0.4 },
            16,
            &[],
        ));
        let w = run_mode(
            WorkspaceMode::Schematic,
            &obs,
            &Foresight { events: vec![] },
        );
        println!("break: s at jump {:.4}", w.field[48].surprise);
        assert!(w.field[48].surprise > 0.5);
    }

    /// Level 0.4, rising to 0.6 on beat 48: a lift the evidence itself measures.
    fn build_case(mode: WorkspaceMode) -> Workspace {
        let json = synthetic(
            60,
            |_| [0.4; 4],
            |n| if n >= 48 { 0.6 } else { 0.4 },
            16,
            &[],
        );
        let (data, obs) = obs_of(&json);
        let level: Vec<f64> = (0..data.rms_envelope.len())
            .map(|i| data.rms_envelope[i])
            .collect();
        let loud = 0.6;
        let f = Foresight::new(&data, &[(48.0 * BEAT, 1.0)], &level, loud, 10.0, BEAT);
        assert_eq!(f.of(EventKind::Arrival).next().unwrap().sign, 1.0);
        run_mode(mode, &obs, &f)
    }

    #[test]
    fn held_breath_builds_then_releases_only_when_rehearsed() {
        let w = build_case(WorkspaceMode::Rehearsed);
        let t: Vec<f64> = w.field.iter().map(|f| f.tension).collect();
        for n in 33..48 {
            assert!(t[n] > t[n - 1], "T fell at {n}: {:?}", &t[30..50]);
        }
        let peak = t[47];
        println!(
            "T: starts beat {} peak {peak:.4}; after: {:?}",
            t.iter().position(|v| *v > 0.0).unwrap(),
            &t[48..51]
        );
        assert!(t[50] < 0.1 * peak && t[48] < 0.1 * peak);
        let s = build_case(WorkspaceMode::Schematic);
        assert!(s.field.iter().all(|f| f.tension == 0.0));
    }

    /// Steady 0.4 after one loud beat: a gain well under the ceiling.
    fn gain_after(a: usize, foresight_from: usize) -> Vec<f64> {
        let (_, obs) = obs_of(&synthetic(
            80,
            |_| [0.4; 4],
            |n| if n == 0 { 1.0 } else { 0.4 },
            16,
            &[],
        ));
        let full = drop_at(a);
        let empty = Foresight { events: vec![] };
        let mut state = State::new(BEAT);
        (0..80)
            .map(|n| {
                let fore = if n >= foresight_from { &full } else { &empty };
                state.step(&obs[n], Some(fore), n).gain
            })
            .collect()
    }

    #[test]
    fn payoff_is_bigger_after_a_build() {
        let built = gain_after(50, 0);
        let cold = gain_after(50, 49);
        println!(
            "payoff: before {:.4}; gain at drop with build {:.4}, without {:.4}",
            built[49], built[50], cold[50]
        );
        assert!(built[50] > cold[50] + 0.1);
    }

    #[test]
    fn afterglow_decays_over_sixteen_beats() {
        let (_, obs) = obs_of(&synthetic(120, |_| [0.4; 4], |_| 0.4, 16, &[]));
        let w = run_mode(WorkspaceMode::Rehearsed, &obs, &drop_at(40));
        // Steady intensity is 1; the gain settles there, jumps, then relaxes.
        let excess = |n: usize| w.field[n].gain - 1.0;
        let tau = 16.0 / (excess(42) / excess(58)).ln();
        println!(
            "afterglow: excess {:.4} -> {:.4}, tau {tau:.3}",
            excess(42),
            excess(58)
        );
        assert!((tau - 16.0).abs() <= 1.6);
    }

    #[test]
    fn a_returning_phrase_is_recognised() {
        let blip = |n| if n == 30 { [0.95; 4] } else { groove(n) };
        let json = synthetic(48, blip, |n| if n == 30 { 0.9 } else { 0.4 }, 16, &[(2, 0)]);
        let (data, obs) = obs_of(&json);
        let f = Foresight::new(&data, &[], &[0.4], 0.4, 10.0, BEAT);
        let seen = run_mode(WorkspaceMode::Rehearsed, &obs, &f);
        let blind = run_mode(WorkspaceMode::Schematic, &obs, &f);
        println!(
            "recognition: s at blip {:.3}; precision at 32 rehearsed {:.3} schematic {:.3}; h {:.3} -> {:.3}",
            seen.field[30].surprise, seen.field[32].precision, blind.field[32].precision,
            seen.field[31].habituation, seen.field[32].habituation
        );
        assert!(seen.field[30].surprise > 0.5);
        assert_eq!(seen.field[32].precision, 1.0);
        assert!(blind.field[32].precision < 1.0);
        assert!(seen.field[32].habituation > seen.field[31].habituation);
        assert!(seen
            .basins
            .iter()
            .any(|b| b.kind == BasinKind::Recognition && b.beat == 32));
    }

    #[test]
    fn field_at_interpolates_and_clamps() {
        let (_, obs) = obs_of(&synthetic(8, groove, |_| 0.4, 4, &[]));
        let w = run_mode(
            WorkspaceMode::Schematic,
            &obs,
            &Foresight { events: vec![] },
        );
        let mid = w.field_at(1.25 * BEAT).gain;
        let (a, b) = (w.field[1].gain, w.field[2].gain);
        assert!((mid - (a + 0.25 * (b - a))).abs() < 1e-12);
        assert_eq!(w.field_at(-5.0), w.field[0]);
        assert_eq!(w.field_at(99.0), *w.field.last().unwrap());
    }
}
