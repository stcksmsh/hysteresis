#version 300 es
precision highp float;

in vec2 vUv;
out vec4 fragColor;

uniform sampler2D uCurrent;
uniform sampler2D uPrev;
uniform sampler2D uNoise;
uniform vec2 uNoiseTexel;
uniform float uDecay;
uniform float uCurGain; // see memory-field-pass.ts's DECAY_REFERENCE comment
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
// propagating memory can organize, the fresh frame stays organic.
//
// This is UNCONDITIONAL — always the full fold, never mixed with the raw
// angle. An earlier version mixed the folded angle with the raw one by
// uMirrorStrength before sampling once; that's broken by construction,
// because folding-into-a-half-wedge is inherently a 2-to-1 map: exactly
// half of every wedge already sits in the canonical half and maps to
// itself (folded(theta) == theta there) regardless of uMirrorStrength, so
// that whole half never responded to it at all, while the other half did
// — a permanent, visible seam at the boundary between "always raw" and
// "graduated," independent of how smoothly the fold curve itself was
// shaped (smoothing the curve was tried first and only softened the
// derivative kink, it didn't touch this deeper asymmetry).
//
// The actual fix is in main() below: sample uPrev at BOTH the raw and the
// fully-folded position and cross-fade the resulting COLORS by
// uMirrorStrength, uniformly across the whole screen. At
// uMirrorStrength=0 every pixel is 100% its own raw history (truly no
// fold anywhere, not just in one privileged wedge); at 1 every pixel is
// 100% the folded/mirrored read (the full kaleidoscope, unchanged from
// before); at any value between, EVERY pixel — canonical wedge included —
// blends the same two sources by the same ratio, so there's no static
// "this patch never changes" region and no hard seam, just a soft,
// screen-wide cross-fade. It also keeps a share of each wedge's own real
// history alive even under high symmetry, instead of every wedge but one
// turning into a pure copy of its neighbor.
vec2 foldedDomain(vec2 uv) {
  vec2 centered = (uv - 0.5) * vec2(uAspect, 1.0);
  float r = length(centered);
  float wedge = TWO_PI / max(uFoldCount, 1.0);
  // Quarter-wedge phase offset so the fold's seams don't land on the
  // horizontal/vertical axes (purely cosmetic — rotates where the wedges
  // start, doesn't touch wedge width/count/dynamics).
  float theta = atan(centered.y, centered.x) + wedge * 0.25;
  float s = mod(theta, wedge) / wedge; // 0..1 across one wedge
  // Cosine tent instead of the textbook triangle wave: C-infinity smooth
  // (no derivative kink at the wedge boundary), same 0..wedge/2 range.
  float folded = wedge * 0.5 * (0.5 - 0.5 * cos(TWO_PI * s)) - wedge * 0.25;
  vec2 foldedCentered = vec2(cos(folded), sin(folded)) * r;
  return foldedCentered / vec2(uAspect, 1.0) + 0.5;
}

vec2 advect(vec2 domainUv) {
  vec2 flowSample = domainUv * uFlowScale + uFlowUv;
  vec2 flow = curlAt(flowSample);
  return domainUv - flow * uFlowStrength;
}

// NOTE: this deliberately doubles the pass's texture-fetch cost (11 fetches
// per fragment vs. the pre-cross-fade version's 6 — two full curlAt/advect
// evaluations instead of one, since the raw and folded UVs generally land on
// unrelated parts of the noise texture with little cache reuse between
// them). That's the accepted cost of actually fixing the seam/dead-zone bug
// above rather than an accidental double-sample — see this file's git log
// if a lower-power target ever needs this pass cheaper.
void main() {
  // uPrev's CLAMP_TO_EDGE wrap (gl/fbo.ts) handles the out-of-[0,1] case —
  // no manual clamp needed here.
  vec3 rawPrev = texture(uPrev, advect(vUv)).rgb;
  vec3 foldedPrev = texture(uPrev, advect(foldedDomain(vUv))).rgb;
  vec3 prev = mix(rawPrev, foldedPrev, uMirrorStrength) * uDecay;
  vec3 cur = texture(uCurrent, vUv).rgb;
  // uCurGain decouples steady-state brightness from persistence length (see
  // memory-field-pass.ts) — reported "too bright sometimes": this feedback
  // loop's steady-state brightness is cur/(1-decay), so raising decay to
  // hold a build/break longer (intentional) was ALSO multiplying brightness
  // by the same factor (not intentional — up to ~67-200x at the highest
  // decay tiers, well past where Reinhard tonemapping downstream crushes
  // all contrast into a washed-out mush). uCurGain cancels that out.
  vec3 result = prev + cur * uCurGain;

  // Defensive, not a fix for a known cause: this buffer is a float FBO (see
  // MemoryFieldPass's `useFloat`), which — unlike an 8-bit texture — does
  // NOT clamp on write. If a NaN/Inf value ever enters it (from anywhere
  // upstream: a spring/uniform gone bad, a degenerate divide, a dropped
  // frame with a huge dt), it doesn't just sit in one pixel — every
  // subsequent frame's advection samples nearby/through it, so the bad
  // value spreads to whichever pixels happen to sample from it next,
  // reads as corruption visibly growing across the screen over time
  // (reported: "black shaders growing... heals after a resize", which
  // reallocates this exact buffer from scratch). Sanitizing here can't fix
  // whatever produces a bad value in the first place, but stops it from
  // ever persisting into the one buffer that would otherwise carry and
  // spread it every frame after.
  if (any(isnan(result)) || any(isinf(result))) {
    result = cur;
  }
  result = clamp(result, vec3(0.0), vec3(64.0));

  fragColor = vec4(result, 1.0);
}
