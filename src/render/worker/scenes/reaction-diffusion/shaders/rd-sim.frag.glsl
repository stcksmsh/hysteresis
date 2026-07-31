#version 300 es
precision highp float;

in vec2 vUv;
out vec4 fragColor;

uniform sampler2D uState; // r=U, g=V
uniform vec2 uTexel;
uniform float uFeed;
uniform float uKill;
uniform float uDiffU;
uniform float uDiffV;
uniform float uDt;

// Weighted 3x3 Laplacian stencil (better isotropy than a plain 5-point
// cross), standard for Gray-Scott shader implementations.
vec2 laplacian(vec2 uv) {
  vec2 sum = vec2(0.0);
  sum += texture(uState, uv + uTexel * vec2(-1.0, -1.0)).rg * 0.05;
  sum += texture(uState, uv + uTexel * vec2(0.0, -1.0)).rg * 0.2;
  sum += texture(uState, uv + uTexel * vec2(1.0, -1.0)).rg * 0.05;
  sum += texture(uState, uv + uTexel * vec2(-1.0, 0.0)).rg * 0.2;
  sum += texture(uState, uv).rg * -1.0;
  sum += texture(uState, uv + uTexel * vec2(1.0, 0.0)).rg * 0.2;
  sum += texture(uState, uv + uTexel * vec2(-1.0, 1.0)).rg * 0.05;
  sum += texture(uState, uv + uTexel * vec2(0.0, 1.0)).rg * 0.2;
  sum += texture(uState, uv + uTexel * vec2(1.0, 1.0)).rg * 0.05;
  return sum;
}

void main() {
  vec2 state = texture(uState, vUv).rg;
  float u = state.r;
  float v = state.g;
  vec2 lap = laplacian(vUv);

  float reaction = u * v * v;
  float du = uDiffU * lap.r - reaction + uFeed * (1.0 - u);
  float dv = uDiffV * lap.g + reaction - (uFeed + uKill) * v;

  u = clamp(u + du * uDt, 0.0, 1.0);
  v = clamp(v + dv * uDt, 0.0, 1.0);

  fragColor = vec4(u, v, 0.0, 1.0);
}
