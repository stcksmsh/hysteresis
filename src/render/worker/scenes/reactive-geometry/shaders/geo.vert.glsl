#version 300 es

// Per-vertex: unit quad corner. Per-instance: one shape.
layout(location = 0) in vec2 aCorner;
layout(location = 1) in vec2 aCenter;
layout(location = 2) in float aSize;
layout(location = 3) in float aAge; // 0 = just spawned, 1 = fully faded
layout(location = 4) in float aTone;
layout(location = 5) in float aStrength;

uniform float uAspect;

out vec2 vLocal;
out float vAge;
out float vTone;
out float vStrength;

void main() {
  vLocal = aCorner;
  vAge = aAge;
  vTone = aTone;
  vStrength = aStrength;

  // Shapes expand as they age, so each hit reads as an outward gesture.
  float scale = aSize * (0.35 + 0.9 * aAge);
  vec2 offset = aCorner * scale;
  offset.x /= uAspect; // keep shapes square regardless of viewport
  vec2 pos = aCenter + offset;

  gl_Position = vec4(pos * 2.0 - 1.0, 0.0, 1.0);
}
