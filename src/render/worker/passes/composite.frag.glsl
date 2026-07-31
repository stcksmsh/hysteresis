#version 300 es
precision highp float;

in vec2 vUv;
out vec4 fragColor;

uniform sampler2D uScene;
uniform sampler2D uBloom;
uniform float uBloomStrength;
uniform bool uHasBloom;

// Reinhard tone-map — keeps accents from clipping to flat white mush at
// high energy, compresses gracefully instead of hard-clamping.
vec3 tonemapReinhard(vec3 c) {
  return c / (1.0 + c);
}

void main() {
  vec3 color = texture(uScene, vUv).rgb;
  if (uHasBloom) {
    color += texture(uBloom, vUv).rgb * uBloomStrength;
  }
  color = tonemapReinhard(color);
  color = pow(color, vec3(1.0 / 2.2));
  fragColor = vec4(color, 1.0);
}
