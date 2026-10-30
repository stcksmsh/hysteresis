// node --test scripts/author/test_author.cjs
const test = require("node:test");
const assert = require("node:assert/strict");
const A = require("./author_core.cjs");

const ramp = (n, f) => Float64Array.from({ length: n }, (_, i) => f(i));
const lanesOf = (n, f = () => 0) => Object.fromEntries(A.INPUTS.map((k) => [k, ramp(n, f)]));

test("neutral mapping gives 0.5 on every dimension for any input", () => {
  const body = A.computeBody(A.neutralMapping(), lanesOf(50, (i) => (i % 7) / 7));
  assert.equal(body.length, 15);
  for (const b of body) for (const v of b) assert.equal(v, 0.5);
});

test("weights add to base and the sum is clamped to 0..1", () => {
  const m = A.neutralMapping();
  m.tau = m.tau.map(() => 0);
  m.weights[0][0] = 1;    // curl_extension += arousal
  m.weights[1][0] = -1;   // height -= arousal
  m.weights[2][1] = 0.25; // arch += 0.25 tension
  const lanes = lanesOf(3);
  lanes.arousal = Float64Array.from([0, 0.25, 1]);
  lanes.tension = Float64Array.from([1, 1, 1]);
  const b = A.computeBody(m, lanes);
  assert.deepEqual(Array.from(b[0]), [0.5, 0.75, 1]);
  assert.deepEqual(Array.from(b[1]), [0.5, 0.25, 0]);
  assert.deepEqual(Array.from(b[2]), [0.75, 0.75, 0.75]);
});

test("one-pole smoothing: step response follows 1 - exp(-t / tau)", () => {
  const m = A.neutralMapping();
  m.weights[3][0] = 1; m.tau[3] = 1.0;
  const lanes = lanesOf(100);
  lanes.arousal = ramp(100, (i) => (i >= 10 ? 0.5 : 0));
  const y = A.computeBody(m, lanes)[3];
  assert.equal(y[9], 0.5);
  // target 1.0 from bin 10 on; after j bins the gap to 1.0 is 0.5 * exp(-0.1 j)
  assert.ok(Math.abs(y[10] - (1 - 0.5 * Math.exp(-0.1))) < 1e-12);
  assert.ok(Math.abs(y[59] - (1 - 0.5 * Math.exp(-5.0))) < 1e-9);
});

test("normalise maps the 5th and 95th percentiles to 0 and 1 and clamps", () => {
  const a = ramp(101, (i) => i); // p5 = 5, p95 = 95
  const n = A.normalise(a);
  assert.equal(n[5], 0); assert.equal(n[95], 1); assert.equal(n[0], 0); assert.equal(n[100], 1);
  assert.ok(Math.abs(n[50] - 45 / 90) < 1e-12);
  assert.deepEqual(Array.from(A.normalise(ramp(10, () => 3))), new Array(10).fill(0));
});

test("spike lane: above threshold only, peak held, decays with tau", () => {
  const sn = Float64Array.from([0, 0.5, 1, 0.5, 0, 0, 0, 0]);
  const s = A.spikeLane(sn, 0.5, 1.0);
  assert.equal(s[0], 0); assert.equal(s[1], 0);
  assert.equal(s[2], 1);
  assert.ok(Math.abs(s[3] - Math.exp(-0.1)) < 1e-12);
  assert.ok(Math.abs(s[7] - Math.exp(-0.5)) < 1e-12);
  assert.equal(Math.max(...A.spikeLane(sn, 1, 1)), 0);       // threshold 1: nothing passes
  assert.deepEqual(Array.from(A.spikeLane(sn, 0.5, 0)), [0, 0, 1, 0, 0, 0, 0, 0]); // tau 0: no hold
});

test("mood.energy is held between 0.5 s steps", () => {
  const e = A.holdEnergy([0.1, 0.2, 0.3], 12);
  // bin k is at 0.1 (k + 1): 0.1..0.4 -> step 0, 0.5..0.9 -> step 1, 1.0.. -> step 2
  assert.deepEqual(Array.from(e), [0.1, 0.1, 0.1, 0.1, 0.2, 0.2, 0.2, 0.2, 0.2, 0.3, 0.3, 0.3]);
});

test("span means and the bodyTrack object", () => {
  const body = A.DIMS.map((_, d) => ramp(100, (i) => (d === 0 ? i / 100 : 0.25)));
  const t = A.bodyTrack(body, [[0, 5], [5, 10]], "authored-state", "test");
  assert.equal(t.version, 1);
  assert.deepEqual(t.dims, A.DIMS);
  assert.deepEqual(t.authored, []);
  assert.equal(t.phrases.length, 2);
  // bins 0..49 are stamped 0.1..5.0 -> inside [0, 5) are stamps 0.1..4.9, bins 0..48
  assert.ok(Math.abs(t.phrases[0].body[0] - 0.24) < 1e-9);
  assert.equal(t.phrases[1].body[1], 0.25);
  for (const p of t.phrases) assert.equal(p.body.length, 15);
});

test("a span with no bin takes the nearest bin", () => {
  const body = A.DIMS.map(() => ramp(100, (i) => i / 100));
  const t = A.bodyTrack(body, [[2.01, 2.02]], "s", "m");
  assert.equal(t.phrases[0].body[0], 0.19); // bin 19 is stamped 2.0, the nearest stamp to 2.015
});

test("mapping JSON round trip is exact and validation rejects bad files", () => {
  const m = A.neutralMapping();
  m.weights[4][2] = -0.35; m.base[6] = 0.8; m.tau[1] = 7.5; m.spike.threshold = 0.3; m.name = "x";
  const back = A.validateMapping(JSON.parse(JSON.stringify(m)));
  assert.deepEqual(back, m);
  for (const bad of [
    (x) => { x.version = 2; }, (x) => { x.inputs = x.inputs.slice(1); }, (x) => { x.dims[0] = "size"; },
    (x) => { x.base = x.base.slice(1); }, (x) => { x.weights[0] = [0]; }, (x) => { x.tau[0] = -1; },
    (x) => { x.weights[0][0] = null; }, (x) => { x.spike.tau = "a"; },
  ]) {
    const c = JSON.parse(JSON.stringify(A.neutralMapping()));
    bad(c);
    assert.throws(() => A.validateMapping(c));
  }
});
