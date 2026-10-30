// Mapping maths for the authoring page (docs/NEXT_DECODER_THEN_BRAIN.md, the pivot). Pure functions, no DOM.
// Used inline by author_template.html and by test_author.cjs under node.
(function (root) {
  const DT = 0.1; // all lanes are at 10 Hz; bin k is stamped 0.1 * (k + 1)
  const DIMS = ["curl_extension", "height", "arch", "time", "weight", "flow", "space", "succession_direction",
    "succession_delay", "initiation", "breath_depth", "breath_rate", "size", "energy", "rhythm"]; // body.rs PARAMS
  const INPUTS = ["arousal", "tension", "familiarity", "surprisal", "spike", "band1", "band2", "band3", "band4", "energy"];
  const clamp01 = (x) => Math.min(1, Math.max(0, x));

  function neutralMapping() {
    return {
      version: 1, name: "neutral", note: "",
      inputs: INPUTS.slice(), dims: DIMS.slice(),
      base: DIMS.map(() => 0.5),
      weights: DIMS.map(() => INPUTS.map(() => 0)),
      tau: DIMS.map(() => 2.0),
      spike: { threshold: 0.6, tau: 2.0 },
    };
  }

  // The mapping must be exactly what the page edits: same inputs and dims in the same order, finite numbers.
  function validateMapping(m) {
    const same = (a, b) => Array.isArray(a) && a.length === b.length && a.every((v, i) => v === b[i]);
    const fin = (x) => typeof x === "number" && Number.isFinite(x);
    if (!m || m.version !== 1) throw new Error("mapping: version is not 1");
    if (!same(m.inputs, INPUTS)) throw new Error("mapping: inputs differ from the page's inputs");
    if (!same(m.dims, DIMS)) throw new Error("mapping: dims are not the body PARAMS in order");
    if (!Array.isArray(m.base) || m.base.length !== DIMS.length || !m.base.every(fin)) throw new Error("mapping: base");
    if (!Array.isArray(m.tau) || m.tau.length !== DIMS.length || !m.tau.every((x) => fin(x) && x >= 0)) throw new Error("mapping: tau");
    if (!Array.isArray(m.weights) || m.weights.length !== DIMS.length ||
        !m.weights.every((r) => Array.isArray(r) && r.length === INPUTS.length && r.every(fin))) throw new Error("mapping: weights");
    if (!m.spike || !fin(m.spike.threshold) || !fin(m.spike.tau) || m.spike.tau < 0) throw new Error("mapping: spike");
    return m;
  }

  // 5th / 95th percentile (linear interpolation) of the finite values.
  function percentile(a, p) {
    const s = Array.from(a).filter(Number.isFinite).sort((x, y) => x - y);
    if (!s.length) return 0;
    const r = (p / 100) * (s.length - 1), lo = Math.floor(r), hi = Math.ceil(r);
    return s[lo] + (s[hi] - s[lo]) * (r - lo);
  }

  // Per-song normalisation to 0..1 by the 5th / 95th percentiles; a flat lane maps to 0.
  function normalise(a) {
    const lo = percentile(a, 5), hi = percentile(a, 95);
    return Float64Array.from(a, (x) => (hi > lo && Number.isFinite(x) ? clamp01((x - lo) / (hi - lo)) : 0));
  }

  // Spike lane: surprisal (normalised) above the threshold, rescaled to 0..1, peak-held with decay tau.
  function spikeLane(sn, threshold, tau, dt = DT) {
    const k = tau > 0 ? Math.exp(-dt / tau) : 0, out = new Float64Array(sn.length);
    let y = 0;
    for (let i = 0; i < sn.length; i++) {
      const x = threshold < 1 ? clamp01((sn[i] - threshold) / (1 - threshold)) : 0;
      y = Math.max(x, y * k);
      out[i] = y;
    }
    return out;
  }

  // mood.energy at 0.5 s steps, held: bin k (time 0.1 (k+1)) takes the latest step whose centre i * 0.5 <= t.
  function holdEnergy(steps, n, hop = 0.5, dt = DT) {
    return Float64Array.from({ length: n }, (_, k) => steps[Math.min(steps.length - 1, Math.floor((dt * (k + 1)) / hop + 1e-9))]);
  }

  // Song data -> the 10 input lanes (each 0..1, Float64Array of n bins), in INPUTS order.
  function inputLanes(song, spike) {
    const n = song.n_bins;
    const sn = normalise(song.surprisal_total);
    return {
      arousal: normalise(song.arousal), tension: normalise(song.tension), familiarity: normalise(song.familiarity),
      surprisal: sn, spike: spikeLane(sn, spike.threshold, spike.tau),
      band1: normalise(song.band_power[0]), band2: normalise(song.band_power[1]),
      band3: normalise(song.band_power[2]), band4: normalise(song.band_power[3]),
      energy: Float64Array.from(holdEnergy(song.mood_energy, n), clamp01),
    };
  }

  // body_d(t) = clamp(base_d + sum_i w_di input_i(t), 0, 1), then a one-pole smoother with tau_d (0 = none).
  function computeBody(m, lanes, dt = DT) {
    const n = lanes[INPUTS[0]].length;
    return DIMS.map((_, d) => {
      const out = new Float64Array(n), k = m.tau[d] > 0 ? 1 - Math.exp(-dt / m.tau[d]) : 1;
      let y = 0;
      for (let t = 0; t < n; t++) {
        let x = m.base[d];
        for (let i = 0; i < INPUTS.length; i++) x += m.weights[d][i] * lanes[INPUTS[i]][t];
        x = clamp01(x);
        y = t === 0 ? x : y + k * (x - y);
        out[t] = y;
      }
      return out;
    });
  }

  // Mean body over each [start, end) span (bins stamped 0.1 (k+1) inside it; the nearest bin if none). -> [[15 values]...]
  function spanMeans(body, spans, dt = DT) {
    const n = body[0].length;
    return spans.map(([s, e]) => {
      const lo = Math.max(0, Math.ceil(s / dt - 1 - 1e-9)), hi = Math.min(n, Math.ceil(e / dt - 1 - 1e-9));
      if (hi > lo) return body.map((b) => { let a = 0; for (let k = lo; k < hi; k++) a += b[k]; return a / (hi - lo); });
      const k = Math.min(n - 1, Math.max(0, Math.round(((s + e) / 2) / dt - 1)));
      return body.map((b) => b[k]);
    });
  }

  // The bodyTrack object of crates/hyst-compile/src/body_track.rs (version 1). spans: [[start, end]...] in order.
  function bodyTrack(body, spans, source, map) {
    const means = spanMeans(body, spans);
    return {
      version: 1, source, map, dims: DIMS.slice(), authored: [],
      phrases: spans.map(([start, end], i) => ({ start, end, body: means[i].map((v) => Math.round(v * 1e6) / 1e6) })),
    };
  }

  const api = { DT, DIMS, INPUTS, neutralMapping, validateMapping, percentile, normalise, spikeLane, holdEnergy,
    inputLanes, computeBody, spanMeans, bodyTrack };
  if (typeof module !== "undefined") module.exports = api; else root.AuthorCore = api;
})(typeof window !== "undefined" ? window : globalThis);
