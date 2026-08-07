#version 300 es
// Woscope-style segment-as-quad: each instance is one line segment, expanded
// here into a camera-facing quad along its own direction so the fragment
// shader can compute a clean distance-to-segment falloff.
layout(location = 0) in vec2 aCorner; // x: -0.5..0.5 across the segment, y: 0..1 along it
layout(location = 1) in vec2 aP0;
layout(location = 2) in vec2 aP1;

uniform float uAspect;
uniform float uHalfWidth;

out float vAcross;

void main() {
  vec2 dir = aP1 - aP0;
  float len = max(length(dir), 1e-5);
  vec2 unit = dir / len;
  vec2 normal = vec2(-unit.y, unit.x);

  vec2 base = mix(aP0, aP1, aCorner.y);
  vec2 offset = normal * aCorner.x * uHalfWidth;
  offset.x /= uAspect;

  vAcross = aCorner.x;
  gl_Position = vec4(base + offset, 0.0, 1.0);
}
