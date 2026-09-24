//! Deterministic single-arm offline cue compiler.

use hyst_core::sidecar::{Sidecar, SidecarOnset};
use serde::{Deserialize, Serialize};

const HOME: [f64; 3] = [105.0, -65.0, -20.0];
const Q_V: f64 = 1.875; // max derivative of 6t^5-15t^4+10t^3
const Q_A: f64 = 5.773_502_691_896_258;

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct JointLimits {
    pub min_degrees: [f64; 3],
    pub max_degrees: [f64; 3],
    pub max_speed_degrees_per_second: [f64; 3],
    pub max_acceleration_degrees_per_second2: [f64; 3],
}
impl Default for JointLimits {
    fn default() -> Self {
        Self {
            min_degrees: [45.0, -100.0, -60.0],
            max_degrees: [140.0, -15.0, 40.0],
            max_speed_degrees_per_second: [55.0, 60.0, 70.0],
            max_acceleration_degrees_per_second2: [150.0, 170.0, 200.0],
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Knot {
    pub time: f64,
    pub phase: String,
    pub joints: [f64; 3],
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Cue {
    pub start: f64,
    pub end: f64,
    pub gesture: String,
    pub reason: String,
    pub energy: f32,
    pub accent: f32,
    /// Exact timestamp of a content event this hit/windup was planned to reach.
    #[serde(rename = "arrivalAnchor", default)]
    pub arrival_anchor: Option<f64>,
    pub knots: Vec<Knot>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Score {
    pub duration: f64,
    pub cues: Vec<Cue>,
    pub limits: JointLimits,
}

impl Score {
    /// Sample simulated joint angles in degrees at absolute audio time.
    pub fn sample(&self, time: f64) -> [f64; 3] {
        if self.cues.is_empty() {
            return HOME;
        }
        let t = time.clamp(0.0, self.duration);
        let i = self
            .cues
            .partition_point(|c| c.end < t)
            .min(self.cues.len() - 1);
        sample_knots(&self.cues[i].knots, t)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct CompileConfig {
    pub enable_hits: bool,
    pub enable_windups: bool,
}
impl Default for CompileConfig {
    fn default() -> Self {
        Self {
            enable_hits: true,
            enable_windups: true,
        }
    }
}

pub fn compile_sidecar_json(json: &str) -> Result<Score, String> {
    compile_sidecar_json_with_config(json, CompileConfig::default())
}

pub fn compile_sidecar_json_with_config(
    json: &str,
    config: CompileConfig,
) -> Result<Score, String> {
    let root: serde_json::Value = serde_json::from_str(json).map_err(|e| e.to_string())?;
    let sidecar = Sidecar::from_json_str(json).map_err(|e| e.to_string())?;
    if !sidecar.duration.is_finite()
        || !(0.0..=21_600.0).contains(&sidecar.duration)
        || sidecar.duration == 0.0
    {
        return Err("duration must be finite, positive, and <= 6 hours".into());
    }
    if !sidecar.envelope_rate.is_finite()
        || sidecar.envelope_rate <= 0.0
        || sidecar.energy_envelope.is_empty()
    {
        return Err("envelopeRate and energyEnvelope must be valid".into());
    }
    let rms = match root.get("rmsEnvelope") {
        None => None,
        Some(value) => {
            let values = value
                .as_array()
                .ok_or("rmsEnvelope must be an array")?;
            let required = (sidecar.duration * f64::from(sidecar.envelope_rate)).ceil() as usize;
            if values.len() < required {
                return Err(format!(
                    "rmsEnvelope has {} samples; needs at least {required} for duration and envelopeRate",
                    values.len()
                ));
            }
            let mut parsed = Vec::with_capacity(values.len());
            for (i, value) in values.iter().enumerate() {
                let sample = value
                    .as_f64()
                    .ok_or_else(|| format!("rmsEnvelope[{i}] must be a number"))?;
                if !sample.is_finite() || sample < 0.0 || sample > f64::from(f32::MAX) {
                    return Err(format!("rmsEnvelope[{i}] must be finite and nonnegative"));
                }
                parsed.push(sample as f32);
            }
            Some(parsed)
        }
    };
    Ok(compile(&sidecar, rms.as_deref(), config))
}

fn compile(s: &Sidecar, rms: Option<&[f32]>, config: CompileConfig) -> Score {
    let limits = JointLimits::default();
    let onset_scale = percentile(
        &s.onsets.iter().map(|o| o.strength).collect::<Vec<_>>(),
        0.82,
    )
    .max(0.05);
    let bounds = boundaries(s, rms);
    let mut cues = Vec::new();
    let mut pose = HOME;
    let mut prior = "home";
    for (n, w) in bounds.windows(2).enumerate() {
        let (start, end) = (w[0], w[1]);
        let energy = avg(&s.energy_envelope, s.envelope_rate, start, end);
        let absolute = rms.map_or(energy, |v| avg(v, s.envelope_rate, start, end));
        let onset = strongest(&s.onsets, start, end);
        let accent = onset.map_or(0.0, |o| (o.strength / onset_scale).clamp(0.0, 1.0));
        let low = avg(&s.band_envelope.low, s.envelope_rate, start, end)
            + avg(&s.band_envelope.sub, s.envelope_rate, start, end);
        let high = avg(&s.band_envelope.presence, s.envelope_rate, start, end)
            + avg(&s.band_envelope.air, s.envelope_rate, start, end);
        let centroid = avg(&s.centroid_envelope, s.envelope_rate, start, end);
        let local_onsets: Vec<_> = s
            .onsets
            .iter()
            .filter(|o| o.t >= start - 2.0 && o.t < end + 2.0)
            .collect();
        let local_mean =
            local_onsets.iter().map(|o| o.strength).sum::<f32>() / local_onsets.len().max(1) as f32;
        let distinct_accent = onset.is_some_and(|o| o.strength > local_mean * 1.45);
        let rest = if rms.is_some() {
            absolute < 0.005
        } else {
            energy < 0.045 && accent < 0.45
        };
        let rising = envelope(s, end) - envelope(s, start) > 0.11;
        let hit_anchor = anchored_onset(&s.onsets, start, end, onset_scale * 0.95);
        let coil_anchor = anchored_onset(&s.onsets, start, end, onset_scale * 0.88);
        let hit_candidate = config.enable_hits && accent >= 0.95 && distinct_accent;
        let coil_candidate = config.enable_windups && rising;
        let (gesture, reason, arrival_anchor) = if rest {
            ("hold", format!("rest: absolute level {absolute:0.4}"), None)
        } else if let Some(anchor) = hit_candidate.then_some(hit_anchor).flatten() {
            if anchor.tone < 0.46 {
                ("strike-low", format!("low accent {accent:0.2} at {:0.3}s", anchor.t), Some(anchor.t))
            } else {
                ("flick-high", format!("bright accent {accent:0.2} at {:0.3}s", anchor.t), Some(anchor.t))
            }
        } else if let Some(anchor) = coil_candidate.then_some(coil_anchor).flatten() {
            (
                "coil",
                format!("energy rise prepares arrival at {:0.3}s", anchor.t),
                Some(anchor.t),
            )
        } else {
            let choices = if low > high * 1.12 {
                ["nod", "sway", "reach"]
            } else if high > low * 1.12 || centroid > 0.58 {
                ["orbit", "flick", "reach"]
            } else {
                ["sway", "orbit", "nod"]
            };
            let signature =
                (energy * 11.0) as usize + (centroid * 7.0) as usize + (accent * 5.0) as usize + n;
            let mut g = choices[signature % 3];
            if g == prior {
                g = choices[(signature + 1) % 3];
            }
            let no_anchor = hit_candidate || coil_candidate;
            let reason = if no_anchor {
                format!("groove: no onset allows preparation and recovery; energy {energy:0.2}")
            } else {
                format!("groove: energy {energy:0.2}, low/high {low:0.2}/{high:0.2}, centroid {centroid:0.2}")
            };
            (g, reason, None)
        };
        let knots = make_knots(
            start,
            end,
            pose,
            gesture,
            f64::from(energy),
            arrival_anchor,
            &limits,
            n,
        );
        pose = knots.last().map_or(pose, |k| k.joints);
        prior = gesture;
        cues.push(Cue {
            start,
            end,
            gesture: gesture.into(),
            reason,
            energy: if rest {
                0.0
            } else {
                rms.map_or(energy, |_| (absolute / 0.3).clamp(0.0, 1.0))
            },
            accent: if rest { 0.0 } else { accent },
            arrival_anchor,
            knots,
        });
    }
    Score {
        duration: s.duration,
        cues,
        limits,
    }
}

fn boundaries(s: &Sidecar, rms: Option<&[f32]>) -> Vec<f64> {
    let source = rms.unwrap_or(&s.energy_envelope);
    let rate = f64::from(s.envelope_rate);
    let mut candidates = vec![0.0, s.duration];
    let mut last = 0.0;
    let mut was_rest =
        source.first().copied().unwrap_or(0.0) < if rms.is_some() { 0.005 } else { 0.05 };
    for i in 1..source.len() {
        let t = i as f64 / rate;
        if t >= s.duration {
            break;
        }
        let back = i.saturating_sub((rate * 0.8) as usize);
        let delta = (source[i] - source[back]).abs();
        let rest = source[i] < if rms.is_some() { 0.005 } else { 0.05 };
        let threshold = if rms.is_some() { 0.012 } else { 0.17 };
        if t - last >= 0.75 && (delta > threshold || rest != was_rest) {
            candidates.push(t);
            last = t;
        }
        was_rest = rest;
    }
    // Do not cut a cue exactly at each accent. That made every strong onset a
    // boundary, leaving no recovery time and forcing midpoint "arrivals".
    // Onsets remain planner inputs below; boundaries come from sustained content.
    candidates.retain(|t| t.is_finite() && *t >= 0.0 && *t <= s.duration);
    candidates.sort_by(f64::total_cmp);
    candidates.dedup_by(|a, b| (*a - *b).abs() < 0.04);
    let mut out = vec![0.0];
    for target in candidates.into_iter().skip(1) {
        let prev = *out.last().unwrap();
        if target < s.duration && target - prev < 1.5 {
            continue;
        }
        let mut cursor = prev;
        while target - cursor > 2.8 {
            let wanted =
                cursor + 1.55 + 0.75 * (1.0 - f64::from(envelope(s, cursor + 1.4)).clamp(0.0, 1.0));
            let snapped = nearest_beat(&s.beats, wanted).unwrap_or(wanted);
            if snapped >= target - 0.72 {
                break;
            }
            out.push(snapped);
            cursor = snapped;
        }
        out.push(target);
    }
    if *out.last().unwrap() < s.duration {
        out.push(s.duration);
    }
    out
}

fn nearest_beat(beats: &[f64], target: f64) -> Option<f64> {
    beats
        .iter()
        .copied()
        .filter(|b| b.is_finite())
        .min_by(|a, b| (a - target).abs().total_cmp(&(b - target).abs()))
        .filter(|b| (b - target).abs() <= 0.22)
}

#[allow(clippy::too_many_arguments)] // Explicit local planning inputs; no persistent planner state.
fn make_knots(
    start: f64,
    end: f64,
    from: [f64; 3],
    gesture: &str,
    energy: f64,
    arrival_anchor: Option<f64>,
    limits: &JointLimits,
    n: usize,
) -> Vec<Knot> {
    if gesture == "hold" {
        return vec![
            Knot {
                time: start,
                phase: "hold".into(),
                joints: from,
            },
            Knot {
                time: end,
                phase: "hold".into(),
                joints: from,
            },
        ];
    }
    let span = end - start;
    let arrival_t = arrival_anchor
        .filter(|t| *t > start && *t < end)
        .unwrap_or(start + span * 0.56);
    let times = [
        start,
        start + (arrival_t - start) * 0.42,
        arrival_t,
        arrival_t + (end - arrival_t) * 0.48,
        end,
    ];
    let amp = 0.3 + energy.clamp(0.0, 1.0) * 0.7;
    let sign = if n.is_multiple_of(2) { 1.0 } else { -1.0 };
    let deltas = shape(gesture, amp, sign);
    let mut poses = [from; 5];
    for i in 1..5 {
        let base = if i == 4 { HOME } else { from };
        poses[i] = constrain(
            poses[i - 1],
            add(base, deltas[i - 1]),
            times[i] - times[i - 1],
            limits,
        );
    }
    [
        "start",
        "preparation",
        "arrival",
        "followThrough",
        "recovery",
    ]
    .into_iter()
    .enumerate()
    .map(|(i, p)| Knot {
        time: times[i],
        phase: p.into(),
        joints: poses[i],
    })
    .collect()
}

fn shape(g: &str, a: f64, s: f64) -> [[f64; 3]; 4] {
    let z = |v: [f64; 3]| [v[0] * a, v[1] * a, v[2] * a];
    match g {
        "strike-low" => [
            z([-8. * s, -8., -5.]),
            z([24. * s, 18., -34.]),
            z([9. * s, 7., -16.]),
            [0.; 3],
        ],
        "flick-high" | "flick" => [
            z([-10. * s, 2., 8.]),
            z([25. * s, -13., 24.]),
            z([13. * s, 5., 11.]),
            [0.; 3],
        ],
        "coil" => [
            z([-20. * s, -12., 18.]),
            z([10. * s, 14., -18.]),
            z([18. * s, 6., -7.]),
            z([4. * s, 0., 0.]),
        ],
        "orbit" => [
            z([-17. * s, 12., 5.]),
            z([18. * s, 18., -4.]),
            z([22. * s, -9., 8.]),
            z([5. * s, 0., 0.]),
        ],
        "nod" => [
            z([4. * s, -8., 12.]),
            z([-3. * s, 15., -24.]),
            z([5. * s, 5., -11.]),
            [0.; 3],
        ],
        "reach" => [
            z([-8. * s, -5., 4.]),
            z([20. * s, 20., -20.]),
            z([16. * s, 10., -13.]),
            z([4. * s, 0., 0.]),
        ],
        _ => [
            z([-15. * s, -7., 4.]),
            z([19. * s, 10., -10.]),
            z([10. * s, -4., 7.]),
            z([3. * s, 0., 0.]),
        ],
    }
}

fn constrain(from: [f64; 3], wanted: [f64; 3], dt: f64, l: &JointLimits) -> [f64; 3] {
    std::array::from_fn(|j| {
        let travel = (l.max_speed_degrees_per_second[j] * dt / Q_V)
            .min(l.max_acceleration_degrees_per_second2[j] * dt * dt / Q_A)
            .max(0.);
        wanted[j]
            .clamp(from[j] - travel, from[j] + travel)
            .clamp(l.min_degrees[j], l.max_degrees[j])
    })
}
fn add(a: [f64; 3], b: [f64; 3]) -> [f64; 3] {
    [a[0] + b[0], a[1] + b[1], a[2] + b[2]]
}
fn sample_knots(k: &[Knot], t: f64) -> [f64; 3] {
    if k.is_empty() {
        return HOME;
    }
    if t <= k[0].time {
        return k[0].joints;
    }
    for w in k.windows(2) {
        if t <= w[1].time {
            let x = ((t - w[0].time) / (w[1].time - w[0].time)).clamp(0., 1.);
            let q = x * x * x * (10. + x * (-15. + 6. * x));
            return std::array::from_fn(|j| w[0].joints[j] + (w[1].joints[j] - w[0].joints[j]) * q);
        }
    }
    k.last().unwrap().joints
}
fn percentile(v: &[f32], q: f64) -> f32 {
    let mut x = v
        .iter()
        .copied()
        .filter(|v| v.is_finite())
        .collect::<Vec<_>>();
    if x.is_empty() {
        return 1.;
    }
    x.sort_by(f32::total_cmp);
    x[((x.len() - 1) as f64 * q).round() as usize]
}
fn envelope(s: &Sidecar, t: f64) -> f32 {
    let i = (t.max(0.) * f64::from(s.envelope_rate)).floor() as usize;
    s.energy_envelope
        .get(i)
        .copied()
        .or_else(|| s.energy_envelope.last().copied())
        .unwrap_or(0.)
}
fn avg(v: &[f32], rate: f32, start: f64, end: f64) -> f32 {
    if v.is_empty() {
        return 0.;
    }
    let a = ((start * f64::from(rate)).floor() as usize).min(v.len() - 1);
    let b = ((end * f64::from(rate)).ceil() as usize)
        .min(v.len())
        .max(a + 1);
    v[a..b].iter().sum::<f32>() / (b - a) as f32
}
fn strongest(v: &[SidecarOnset], a: f64, b: f64) -> Option<&SidecarOnset> {
    v.iter()
        .filter(|o| o.t >= a && o.t < b)
        .max_by(|x, y| x.strength.total_cmp(&y.strength))
}
/// Select only events with enough room for visible preparation and recovery.
/// Boundaries often coincide with onset timestamps; those cannot truthfully be hit cues.
fn anchored_onset(v: &[SidecarOnset], start: f64, end: f64, min_strength: f32) -> Option<&SidecarOnset> {
    const MIN_PREP: f64 = 0.38;
    const MIN_RECOVERY: f64 = 0.30;
    v.iter()
        .filter(|o| {
            o.t >= start + MIN_PREP
                && o.t <= end - MIN_RECOVERY
                && o.strength.is_finite()
                && o.strength >= min_strength
        })
        .max_by(|a, b| a.strength.total_cmp(&b.strength).then_with(|| b.t.total_cmp(&a.t)))
}

#[cfg(test)]
mod tests {
    use super::*;
    fn fixture(e: &[f32], onsets: &str, rms: Option<&[f32]>) -> String {
        let join = |v: &[f32]| {
            v.iter()
                .map(ToString::to_string)
                .collect::<Vec<_>>()
                .join(",")
        };
        let x = join(e);
        let r = rms
            .map(|v| format!(",\"rmsEnvelope\":[{}]", join(v)))
            .unwrap_or_default();
        format!(
            r#"{{"schema":3,"duration":8.0,"tempo":120.0,"beats":[0,0.5,1,1.5,2,2.5,3,3.5,4,4.5,5,5.5,6,6.5,7,7.5],"sections":[],"events":[],"onsets":[{onsets}],"energyEnvelope":[{x}],"bandEnvelope":{{"sub":[{x}],"low":[{x}],"mid":[{x}],"presence":[{x}],"air":[{x}]}},"centroidEnvelope":[{x}],"flatnessEnvelope":[{x}],"envelopeRate":1.0{r}}}"#
        )
    }
    #[test]
    fn content_changes_score() {
        let a = compile_sidecar_json(&fixture(&[0.3; 8], "", None)).unwrap();
        let b = compile_sidecar_json(&fixture(
            &[0.2, 0.9, 0.2, 0.8, 0.2, 0.7, 0.2, 0.6],
            r#"{"t":2.1,"strength":1.0,"tone":0.1,"pan":0.0}"#,
            None,
        ))
        .unwrap();
        assert_ne!(
            a.cues
                .iter()
                .map(|c| (&c.gesture, c.start.to_bits()))
                .collect::<Vec<_>>(),
            b.cues
                .iter()
                .map(|c| (&c.gesture, c.start.to_bits()))
                .collect::<Vec<_>>()
        )
    }
    #[test]
    fn rms_silence_holds() {
        let s = compile_sidecar_json(&fixture(&[0.7; 8], "", Some(&[0.; 8]))).unwrap();
        assert!(s.cues.iter().all(|c| c.gesture == "hold"))
    }
    #[test]
    fn groove_without_specials() {
        let s = compile_sidecar_json_with_config(
            &fixture(
                &[0.3, 0.5, 0.6, 0.4, 0.3, 0.6, 0.5, 0.4],
                r#"{"t":2.1,"strength":1.0,"tone":0.1,"pan":0.0}"#,
                None,
            ),
            CompileConfig {
                enable_hits: false,
                enable_windups: false,
            },
        )
        .unwrap();
        assert!(s
            .cues
            .iter()
            .all(|c| !["strike-low", "flick-high", "coil"].contains(&c.gesture.as_str())));
        assert!((1..80).any(|i| s.sample(i as f64 / 10.) != HOME))
    }
    #[test]
    fn limits_hold_dense() {
        let s = compile_sidecar_json(&fixture(
            &[0.3, 0.9, 0.6, 0.4, 0.8, 0.5, 0.7, 0.4],
            r#"{"t":2.1,"strength":1.0,"tone":0.1,"pan":0.0}"#,
            None,
        ))
        .unwrap();
        let dt = 0.002;
        let mut p = s.sample(0.);
        let mut v = [0.; 3];
        for i in 1..=(s.duration / dt) as usize {
            let q = s.sample(i as f64 * dt);
            for j in 0..3 {
                let nv = (q[j] - p[j]) / dt;
                assert!(nv.abs() <= s.limits.max_speed_degrees_per_second[j] + 0.4);
                if i > 2 {
                    assert!(
                        ((nv - v[j]) / dt).abs()
                            <= s.limits.max_acceleration_degrees_per_second2[j] + 4.
                    )
                }
                v[j] = nv;
            }
            p = q;
        }
    }
    #[test]
    fn hit_arrival_is_exact_anchor_with_continuous_limited_motion() {
        let s = compile_sidecar_json(&fixture(
            &[0.5; 8],
            r#"{"t":1.4,"strength":1.0,"tone":0.1,"pan":0.0},{"t":1.7,"strength":0.1,"tone":0.1,"pan":0.0}"#,
            None,
        ))
        .unwrap();
        let cue = s
            .cues
            .iter()
            .find(|cue| cue.gesture == "strike-low")
            .expect("interior strong onset schedules a hit");
        assert_eq!(cue.arrival_anchor, Some(1.4));
        let encoded = serde_json::to_value(cue).unwrap();
        assert_eq!(encoded["arrivalAnchor"], 1.4);
        let mut legacy = encoded.as_object().unwrap().clone();
        legacy.remove("arrivalAnchor");
        assert_eq!(
            serde_json::from_value::<Cue>(legacy.into()).unwrap().arrival_anchor,
            None
        );
        let arrival = cue.knots.iter().find(|k| k.phase == "arrival").unwrap();
        assert_eq!(arrival.time, cue.arrival_anchor.unwrap());
        assert_eq!(s.sample(1.4), arrival.joints);
        let dt = 0.001;
        let before = s.sample(1.4 - dt);
        let at = s.sample(1.4);
        let after = s.sample(1.4 + dt);
        for j in 0..3 {
            assert!(((at[j] - before[j]) / dt).abs() <= s.limits.max_speed_degrees_per_second[j]);
            assert!(((after[j] - at[j]) / dt).abs() <= s.limits.max_speed_degrees_per_second[j]);
        }
    }
    #[test]
    fn boundary_accent_falls_back_to_truthful_groove() {
        let s = compile_sidecar_json(&fixture(
            &[0.5; 8],
            r#"{"t":2.0,"strength":1.0,"tone":0.1,"pan":0.0},{"t":2.2,"strength":0.1,"tone":0.1,"pan":0.0}"#,
            None,
        ))
        .unwrap();
        let cue = s
            .cues
            .iter()
            .find(|cue| (cue.start - 2.0).abs() < 0.001)
            .unwrap_or_else(|| panic!("expected 2.0s boundary, got {:?}", s.cues));
        assert!(!["strike-low", "flick-high", "coil"].contains(&cue.gesture.as_str()));
        assert_eq!(cue.arrival_anchor, None);
        assert!(cue.reason.contains("no onset allows preparation and recovery"));
    }
    #[test]
    fn coil_uses_exact_lookahead_anchor() {
        let s = compile_sidecar_json_with_config(
            &fixture(
                &[0.1, 0.2, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9],
                r#"{"t":1.4,"strength":0.9,"tone":0.7,"pan":0.0}"#,
                None,
            ),
            CompileConfig {
                enable_hits: false,
                enable_windups: true,
            },
        )
        .unwrap();
        let cue = s.cues.iter().find(|cue| cue.gesture == "coil").unwrap();
        assert_eq!(cue.arrival_anchor, Some(1.4));
        assert_eq!(
            cue.knots.iter().find(|k| k.phase == "arrival").unwrap().time,
            1.4
        );
    }
    #[test]
    fn malformed_rms_is_rejected_without_time_compression() {
        let non_number = fixture(&[0.5; 8], "", Some(&[0.1; 8]))
            .replace("\"rmsEnvelope\":[0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1]", "\"rmsEnvelope\":[0.1,\"bad\",0.1,0.1,0.1,0.1,0.1,0.1]");
        assert!(compile_sidecar_json(&non_number).unwrap_err().contains("rmsEnvelope[1]"));
        let short = fixture(&[0.5; 8], "", Some(&[0.1; 7]));
        assert!(compile_sidecar_json(&short).unwrap_err().contains("needs at least 8"));
    }
}
