#version 300 es
precision highp float;

in vec2 vUv;
out vec4 fragColor;

uniform sampler2D uState; // r=U, g=V
uniform float uHueShift;
uniform float uPaletteMix;
uniform int uStyle; // 0 = organic, 1 = graphic

const int STYLE_GRAPHIC = 1;
const float POSTERIZE_LEVELS = 4.0;

vec3 hsl2rgb(vec3 hsl) {
  float h = hsl.x;
  float s = hsl.y;
  float l = hsl.z;
  float a = s * min(l, 1.0 - l);
  vec3 k = mod(vec3(0.0, 8.0, 4.0) + h * 12.0, 12.0);
  vec3 kk = min(min(k - 3.0, 9.0 - k), 1.0);
  return l - a * clamp(kk, -1.0, 1.0);
}

// Soft, continuous ramp — the field reads as a diffuse organic mass.
vec3 organic(float v, float hueBase) {
  float intensity = clamp(v * 1.6, 0.0, 1.0);
  float hue = fract(hueBase + mix(0.55, 0.05, intensity));
  return hsl2rgb(vec3(hue, 0.75, intensity * 0.55));
}

// Flat quantised steps plus a hard contour, on near-black. Nothing here is a
// post-process trick: the same simulation is simply read graphically instead
// of as a smooth gradient, which is what removes the washed-out look.
vec3 graphic(float v, float hueBase) {
  float intensity = clamp(v * 1.7, 0.0, 1.0);
  float stepped = floor(intensity * POSTERIZE_LEVELS) / POSTERIZE_LEVELS;

  // Screen-space derivative gives a contour of even thickness regardless of
  // how steep the field is locally, so edges stay crisp everywhere.
  float edgeWidth = fwidth(intensity) * 1.6 + 1e-5;
  float contour = 1.0 - smoothstep(0.0, edgeWidth, abs(intensity - 0.42));

  vec3 accent = hsl2rgb(vec3(fract(hueBase + 0.02), 0.95, 0.5 + 0.16 * stepped));
  vec3 base = accent * stepped;
  vec3 outline = hsl2rgb(vec3(fract(hueBase + 0.5), 0.9, 0.78));
  return clamp(base + outline * contour, 0.0, 1.0);
}

void main() {
  float v = texture(uState, vUv).g;
  float hueBase = uHueShift + uPaletteMix * 0.3;
  fragColor = vec4(uStyle == STYLE_GRAPHIC ? graphic(v, hueBase) : organic(v, hueBase), 1.0);
}
