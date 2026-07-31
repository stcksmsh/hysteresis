#version 300 es
precision highp float;

in vec2 vUv;
out vec4 fragColor;

uniform sampler2D uState; // r=U, g=V
uniform float uHueShift;
uniform float uPaletteMix;

vec3 hsl2rgb(vec3 hsl) {
  float h = hsl.x;
  float s = hsl.y;
  float l = hsl.z;
  float a = s * min(l, 1.0 - l);
  vec3 k = mod(vec3(0.0, 8.0, 4.0) + h * 12.0, 12.0);
  vec3 kk = min(min(k - 3.0, 9.0 - k), 1.0);
  return l - a * clamp(kk, -1.0, 1.0);
}

void main() {
  vec2 state = texture(uState, vUv).rg;
  float v = state.g;
  float intensity = clamp(v * 1.6, 0.0, 1.0);
  float hue = fract(uHueShift + mix(0.55, 0.05, intensity) + uPaletteMix * 0.3);
  vec3 color = hsl2rgb(vec3(hue, 0.75, intensity * 0.55));
  fragColor = vec4(color, 1.0);
}
