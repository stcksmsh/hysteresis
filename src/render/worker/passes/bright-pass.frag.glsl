#version 300 es
precision highp float;

in vec2 vUv;
out vec4 fragColor;

uniform sampler2D uScene;
uniform float uThreshold;

void main() {
  vec3 color = texture(uScene, vUv).rgb;
  float brightness = max(color.r, max(color.g, color.b));
  float contribution = smoothstep(uThreshold, uThreshold + 0.2, brightness);
  fragColor = vec4(color * contribution, 1.0);
}
