#version 300 es
precision highp float;

in float vAcross;
out vec4 fragColor;

uniform vec3 uColor;
uniform float uIntensity;

void main() {
  float d = abs(vAcross) * 2.0;
  float falloff = smoothstep(1.0, 0.0, d);
  fragColor = vec4(uColor * uIntensity * falloff, falloff);
}
