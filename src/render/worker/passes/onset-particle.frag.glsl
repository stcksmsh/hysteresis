#version 300 es
precision highp float;

in vec2 vCorner;
in float vAlpha;
out vec4 fragColor;

uniform vec3 uColor;

void main() {
  float d = length(vCorner) * 2.0;
  float falloff = smoothstep(1.0, 0.0, d);
  float a = falloff * vAlpha;
  fragColor = vec4(uColor * a, a);
}
