#version 300 es
precision highp float;

in vec2 vUv;
out vec4 fragColor;

const int MAX_SITES = 16;

uniform vec2 uSites[MAX_SITES];
uniform float uSiteRadius[MAX_SITES];
uniform float uSiteStrength[MAX_SITES];
uniform int uSiteCount;
uniform float uAspect;

// Localized soft blobs of V, additively blended onto the live sim state.
// Delta-only (U untouched) so an injection perturbs the existing pattern
// rather than replacing it — this is what makes an onset read as a hit and
// a drop read as a rupture, instead of a restart.
void main() {
  float total = 0.0;
  for (int i = 0; i < MAX_SITES; i++) {
    if (i >= uSiteCount) break;
    vec2 d = (vUv - uSites[i]) * vec2(uAspect, 1.0);
    float r = max(uSiteRadius[i], 1e-4);
    total += uSiteStrength[i] * exp(-dot(d, d) / (r * r));
  }
  fragColor = vec4(0.0, min(total, 1.0), 0.0, 0.0);
}
