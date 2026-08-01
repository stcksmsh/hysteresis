#version 300 es
precision highp float;

in vec2 vUv;
out vec4 fragColor;

uniform sampler2D uState; // r=U, g=V
uniform sampler2D uNoiseTex; // r=feed offset, g=kill offset (baked once)
uniform vec2 uTexel;
uniform float uFeed;
uniform float uKill;
uniform float uDiffU;
uniform float uDiffV;
uniform float uDt;
uniform float uNoiseScale;
uniform vec2 uNoiseDrift;
uniform float uFeedRange;
uniform float uKillRange;
uniform float uAdvect; // texels of transport per substep
uniform float uFlowScale;

// Divergence-free-ish flow from the curl of a scalar noise field. Curl of a
// potential has zero divergence, so the field is transported without being
// compressed or torn — structure keeps its shape while it travels.
vec2 flowAt(vec2 uv) {
  vec2 e = uTexel * 2.0;
  float p0 = texture(uNoiseTex, (uv + vec2(0.0, e.y)) * uFlowScale + uNoiseDrift * 0.5).b;
  float p1 = texture(uNoiseTex, (uv - vec2(0.0, e.y)) * uFlowScale + uNoiseDrift * 0.5).b;
  float p2 = texture(uNoiseTex, (uv + vec2(e.x, 0.0)) * uFlowScale + uNoiseDrift * 0.5).b;
  float p3 = texture(uNoiseTex, (uv - vec2(e.x, 0.0)) * uFlowScale + uNoiseDrift * 0.5).b;
  return vec2(p0 - p1, -(p2 - p3)) * 40.0;
}

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
  // Semi-Lagrangian advection: read the previous state from upstream of the
  // flow rather than from this texel. The pattern is physically carried
  // along, so it keeps its crisp structure while visibly moving — unlike
  // modulating the chemistry, which creates motion by dissolving structure.
  vec2 srcUv = vUv - flowAt(vUv) * uAdvect * uTexel;

  vec2 state = texture(uState, srcUv).rg;
  float u = state.r;
  float v = state.g;
  vec2 lap = laplacian(srcUv);

  // Feed/kill vary across space and drift slowly. With uniform parameters
  // Gray-Scott converges to a steady state and visibly stops; letting
  // regions sit in different regimes — and letting the boundaries between
  // them move — keeps the field perpetually reorganising.
  vec2 n = texture(uNoiseTex, vUv * uNoiseScale + uNoiseDrift).rg;
  float feed = uFeed + uFeedRange * (n.r - 0.5);
  float kill = uKill + uKillRange * (n.g - 0.5);

  float reaction = u * v * v;
  float du = uDiffU * lap.r - reaction + feed * (1.0 - u);
  float dv = uDiffV * lap.g + reaction - (feed + kill) * v;

  u = clamp(u + du * uDt, 0.0, 1.0);
  v = clamp(v + dv * uDt, 0.0, 1.0);

  fragColor = vec4(u, v, 0.0, 1.0);
}
