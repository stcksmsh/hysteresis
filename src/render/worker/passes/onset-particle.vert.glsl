#version 300 es
// One glowing point-sprite per onset particle, expanded from a shared unit
// quad (mirrors JuliaScene's beam.vert.glsl instancing pattern).
layout(location = 0) in vec2 aCorner; // -0.5..0.5 quad corner
layout(location = 1) in vec2 aCenter; // per-instance center, raw clip space
layout(location = 2) in vec2 aSizeAlpha; // x: sprite size, y: current alpha

uniform float uAspect;

out vec2 vCorner;
out float vAlpha;

void main() {
  vCorner = aCorner;
  vAlpha = aSizeAlpha.y;
  vec2 offset = aCorner * aSizeAlpha.x;
  offset.x /= uAspect;
  gl_Position = vec4(aCenter + offset, 0.0, 1.0);
}
