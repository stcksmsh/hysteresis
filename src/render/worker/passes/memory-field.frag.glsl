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
//
// Two deliberate departures from the textbook abs(mod(theta,wedge)-wedge/2)
// triangle fold, both fixing visible artifacts rather than changing the
// intended look:
//   1. PHASE — the textbook fold's wedge boundaries sit at theta = 0,
//      wedge, 2*wedge, ... With FOLD_COUNT even (6), two of those land
//      exactly on the horizontal axis (0 and pi), which reads as a static
//      seam bisecting the screen. A constant phase offset (a quarter-wedge)
//      just rotates where the wedges start; it doesn't touch wedge width,
//      fold count, or dynamics, so it can't reintroduce the "spin" the
//      fixed FOLD_COUNT above was specifically chosen to avoid.
//   2. SMOOTHING — the textbook fold is piecewise-*linear* (a triangle
//      wave), which has two failure modes together: (a) a real derivative
//      kink at every wedge boundary — a visible crease in the flow — and
//      (b) it's the identity map across an entire half of every wedge
//      (folded(theta) == theta there verbatim), so that whole half never
//      responds to uMirrorStrength at all and reads as a static, un-organized
//      patch next to its heavily-folded twin. Replacing the triangle wave
//      with a cosine tent of the same period/amplitude is C-infinity
//      smooth (no crease) and only touches the identity line at isolated
//      points rather than across a whole half-wedge, so uMirrorStrength
//      graduates everywhere instead of leaving a dead zone.
vec2 foldDomain(vec2 uv) {
  vec2 centered = (uv - 0.5) * vec2(uAspect, 1.0);
  float r = length(centered);
  float wedge = TWO_PI / max(uFoldCount, 1.0);
  float theta = atan(centered.y, centered.x) + wedge * 0.25;
  float s = mod(theta, wedge) / wedge; // 0..1 across one wedge
  float folded = wedge * 0.5 * (0.5 - 0.5 * cos(TWO_PI * s));
  float mixedTheta = mix(theta, folded, uMirrorStrength) - wedge * 0.25;
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
