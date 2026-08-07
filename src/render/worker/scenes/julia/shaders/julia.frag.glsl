#version 300 es
precision highp float;

in vec2 vUv;
out vec4 fragColor;

uniform vec2 uC;
uniform vec2 uPan; // z-plane point the view is centered/zooming on — not always the origin
uniform float uAspect;
uniform float uZoom;
uniform vec3 uAccent;
uniform float uHueShift;
uniform float uPaletteMix;
uniform float uPaletteFlip;
uniform float uFlash; // 0..1 — blackout around a zoom-cycle reset, masks the scale jump as a blink
// Reference orbit for perturbation iteration, used only once uZoom drops
// below uPerturbThreshold (see iterate() below). Texel i holds Z_i, the
// orbit of uPan itself computed in JS double precision — JuliaScene.ts
// re-uploads this every frame.
uniform sampler2D uRefOrbit;
// Above this zoom, direct iteration (z = uPan + uv*uZoom, iterated as-is)
// is still fully accurate in float32 — that's the entire zoom range this
// scene used before perturbation existed, so it's known-good. Perturbation
// only switches in below this threshold, where direct computation would
// lose precision, in exchange for a different failure mode instead
// (localized artifacts where a pixel's true orbit diverges from the shared
// reference — no rebasing is implemented, so this is a deliberate,
// contained trade rather than a universal fix).
uniform float uPerturbThreshold;

const int MAX_ITER = 192;

vec2 cMul(vec2 a, vec2 b) {
  return vec2(a.x * b.x - a.y * b.y, a.x * b.y + a.y * b.x);
}

int iterateDirect(vec2 z0, out vec2 finalZ) {
  vec2 z = z0;
  int iter = 0;
  for (int i = 0; i < MAX_ITER; i++) {
    if (dot(z, z) > 4.0) {
      finalZ = z;
      return iter;
    }
    z = vec2(z.x * z.x - z.y * z.y, 2.0 * z.x * z.y) + uC;
    iter++;
  }
  finalZ = z;
  return iter;
}

// Perturbation: iterates only delta, the tiny offset from the reference
// orbit, via delta_{n+1} = 2*Z_n*delta_n + delta_n^2 (the c terms cancel:
// (Z_n+delta_n)^2+c - (Z_n^2+c) = 2*Z_n*delta_n+delta_n^2). delta stays
// small and well-conditioned in float32 regardless of zoom depth since it's
// never added to something orders of magnitude larger than itself until
// the final `Zi + delta` escape check, which only needs coarse accuracy.
int iteratePerturbed(vec2 delta0, out vec2 finalZ) {
  vec2 delta = delta0;
  int iter = 0;
  finalZ = uPan + delta;
  for (int i = 0; i < MAX_ITER; i++) {
    vec2 Zi = texelFetch(uRefOrbit, ivec2(i, 0), 0).xy;
    vec2 full = Zi + delta;
    if (dot(full, full) > 4.0) {
      finalZ = full;
      return iter;
    }
    delta = 2.0 * cMul(Zi, delta) + cMul(delta, delta);
    iter++;
  }
  return iter;
}

// Violet-black substrate (СИНТЕЗА), low-contrast at rest so body text stays
// readable over it; blends toward the host's accent as paletteMix (windup)
// rises (HYSTERESIS.md §4a).
vec3 palette(float t, float hueShift, float paletteMix, vec3 accent) {
  vec3 base = vec3(0.04, 0.035, 0.07);
  vec3 violet = vec3(0.29, 0.18, 0.55);
  float h = hueShift + uPaletteFlip * 0.5;
  vec3 hueRot = vec3(
    0.5 + 0.5 * cos(6.28318 * (t + h)),
    0.5 + 0.5 * cos(6.28318 * (t + h + 0.33)),
    0.5 + 0.5 * cos(6.28318 * (t + h + 0.67))
  );
  vec3 mood = mix(base, violet * hueRot, clamp(t * 1.6, 0.0, 1.0));
  return mix(mood, accent * hueRot, paletteMix * 0.6);
}

void main() {
  vec2 uv = vUv * 2.0 - 1.0;
  uv.x *= uAspect;

  vec2 z;
  int iter;
  // Uniform-only branch — every fragment in the draw call takes the same
  // side, so this costs nothing extra beyond the branch itself.
  if (uZoom > uPerturbThreshold) {
    iter = iterateDirect(uPan + uv * uZoom, z);
  } else {
    iter = iteratePerturbed(uv * uZoom, z);
  }

  float smoothIter = float(iter);
  if (iter < MAX_ITER) {
    float logZn = log(dot(z, z)) * 0.5;
    float nu = log(logZn / log(2.0)) / log(2.0);
    smoothIter = float(iter) + 1.0 - nu;
  }

  float t = smoothIter / float(MAX_ITER);
  vec3 color = palette(t, uHueShift, uPaletteMix, uAccent);
  color = mix(color, vec3(0.0), uFlash);
  fragColor = vec4(color, 1.0);
}
