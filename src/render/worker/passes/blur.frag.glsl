#version 300 es
precision highp float;

in vec2 vUv;
out vec4 fragColor;

uniform sampler2D uTex;
uniform vec2 uDirection;
uniform vec2 uTexel;

// Separable 9-tap Gaussian-ish blur, one direction per invocation — two
// passes (horizontal then vertical) approximate a full 2D blur cheaply.
void main() {
  float w0 = 0.227027;
  float w1 = 0.1945946;
  float w2 = 0.1216216;
  float w3 = 0.054054;
  float w4 = 0.016216;

  vec3 result = texture(uTex, vUv).rgb * w0;
  vec2 o1 = uDirection * uTexel * 1.0;
  vec2 o2 = uDirection * uTexel * 2.0;
  vec2 o3 = uDirection * uTexel * 3.0;
  vec2 o4 = uDirection * uTexel * 4.0;
  result += texture(uTex, vUv + o1).rgb * w1 + texture(uTex, vUv - o1).rgb * w1;
  result += texture(uTex, vUv + o2).rgb * w2 + texture(uTex, vUv - o2).rgb * w2;
  result += texture(uTex, vUv + o3).rgb * w3 + texture(uTex, vUv - o3).rgb * w3;
  result += texture(uTex, vUv + o4).rgb * w4 + texture(uTex, vUv - o4).rgb * w4;

  fragColor = vec4(result, 1.0);
}
