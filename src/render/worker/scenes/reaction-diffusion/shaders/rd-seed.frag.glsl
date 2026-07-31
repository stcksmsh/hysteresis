#version 300 es
precision highp float;

in vec2 vUv;
out vec4 fragColor;

uniform float uSeedPhase;
uniform float uStrength;

float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7)) + uSeedPhase * 37.0) * 43758.5453123);
}

// Delta-only output (zero for U) so this can be additively blended onto the
// live sim state without disturbing U — used both for the initial seed
// burst (on top of a plain baseline clear) and for reseeding on a drop.
void main() {
  float n = hash(floor(vUv * 24.0));
  float bump = n > 0.92 ? uStrength : 0.0;
  fragColor = vec4(0.0, bump, 0.0, 0.0);
}
