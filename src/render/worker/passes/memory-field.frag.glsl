#version 300 es
precision highp float;

in vec2 vUv;
out vec4 fragColor;

uniform sampler2D uCurrent;
uniform sampler2D uPrev;
uniform sampler2D uNoise;
uniform vec2 uNoiseTexel;
uniform float uDecay;
uniform float uAspect;
uniform vec2 uFlowUv;         // slowly-drifting offset into the noise texture — keeps the field evolving
uniform float uFlowScale;     // spatial frequency of the curl sample, relative to screen UV
uniform float uFlowStrength;  // advection displacement this frame
uniform float uFoldCount;     // earned symmetry: kaleidoscope wedge count (>= 1)
uniform float uMirrorStrength; // 0 = organic/asymmetric, 1 = full fold

const float TWO_PI = 6.28318530718;

// Divergence-free flow direction from the baked noise texture's B channel
// (a scalar potential — see gl/noise-texture.ts) via a central-difference
// curl: (dP/dy, -dP/dx). Cheap: 4 texture fetches, no simulation buffer.
vec2 curlAt(vec2 uv) {
  float pL = texture(uNoise, uv - vec2(uNoiseTexel.x, 0.0)).b;
  float pR = texture(uNoise, uv + vec2(uNoiseTexel.x, 0.0)).b;
  float pD = texture(uNoise, uv - vec2(0.0, uNoiseTexel.y)).b;
  float pU = texture(uNoise, uv + vec2(0.0, uNoiseTexel.y)).b;
  return vec2(pU - pD, -(pR - pL));
}

// Earned-symmetry domain warp (SINTEZA_VIZ.md §4d): folds the coordinate
// used to sample the PREVIOUS frame's memory into a uFoldCount-wedge
// mirror-symmetric kaleidoscope. Never applied to uCurrent below — only the
// propagating memory can organize, the fresh frame stays organic — and
// mix()'d by uMirrorStrength so it's a graduated response, never a switch.
vec2 foldDomain(vec2 uv) {
  vec2 centered = (uv - 0.5) * vec2(uAspect, 1.0);
  float r = length(centered);
  float theta = atan(centered.y, centered.x);
  float wedge = TWO_PI / max(uFoldCount, 1.0);
  float folded = wedge * 0.5 - abs(mod(theta, wedge) - wedge * 0.5);
  float mixedTheta = mix(theta, folded, uMirrorStrength);
  vec2 foldedCentered = vec2(cos(mixedTheta), sin(mixedTheta)) * r;
  return foldedCentered / vec2(uAspect, 1.0) + 0.5;
}

void main() {
  vec2 domainUv = foldDomain(vUv);
  vec2 flowSample = domainUv * uFlowScale + uFlowUv;
  vec2 flow = curlAt(flowSample);
  vec2 advectedUv = domainUv - flow * uFlowStrength;

  // uPrev's CLAMP_TO_EDGE wrap (gl/fbo.ts) handles the out-of-[0,1] case —
  // no manual clamp needed here.
  vec3 prev = texture(uPrev, advectedUv).rgb * uDecay;
  vec3 cur = texture(uCurrent, vUv).rgb;
  fragColor = vec4(prev + cur, 1.0);
}
