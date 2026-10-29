// Writes mappings/neutral.json and mappings/example-sketch.json with the page's own core, so both are valid by construction.
const fs = require("node:fs");
const A = require("./author_core.cjs");
const W = (m, dim, input, w) => { m.weights[A.DIMS.indexOf(dim)][A.INPUTS.indexOf(input)] = w; };

const neutral = A.neutralMapping();
neutral.note = "Neutral start: every base 0.5, every weight 0. The body stays at 0.5 on all 15 dimensions.";

const sketch = A.neutralMapping();
sketch.name = "example-sketch";
sketch.note = "THIS IS A SKETCH to start editing from, not a claim and not a recommendation. Directions follow the body.rs notes " +
  "(weight 0 = light, 1 = strong; curl_extension 0 = bent up, 1 = extended; height 0 = low) and are guesses until watched.";
W(sketch, "energy", "arousal", 0.6);
W(sketch, "size", "arousal", 0.5);
W(sketch, "height", "tension", -0.5);
W(sketch, "curl_extension", "tension", -0.5);
W(sketch, "flow", "spike", 0.7);
W(sketch, "space", "spike", 0.5);
W(sketch, "weight", "familiarity", -0.4);
sketch.tau[A.DIMS.indexOf("energy")] = 1.0;
sketch.tau[A.DIMS.indexOf("size")] = 1.0;
sketch.tau[A.DIMS.indexOf("flow")] = 0.5;
sketch.tau[A.DIMS.indexOf("space")] = 0.5;
sketch.spike = { threshold: 0.6, tau: 2.0 };

for (const [name, m] of [["neutral", neutral], ["example-sketch", sketch]]) {
  A.validateMapping(m);
  fs.writeFileSync(`${__dirname}/mappings/${name}.json`, JSON.stringify(m, null, 1) + "\n");
}
