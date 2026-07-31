#version 300 es
precision highp float;

in vec2 vUv;
out vec4 fragColor;

uniform sampler2D uCurrent;
uniform sampler2D uPrev;
uniform float uDecay;

// Trail/glow memory for memoryless scenes: keep the brighter of the decayed
// trail vs. the fresh frame, per channel — a fading trail without additive
// blowout to white over many frames.
void main() {
  vec3 prev = texture(uPrev, vUv).rgb * uDecay;
  vec3 cur = texture(uCurrent, vUv).rgb;
  fragColor = vec4(max(prev, cur), 1.0);
}
