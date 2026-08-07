#version 300 es
precision highp float;

in vec2 vUv;
out vec4 fragColor;

uniform float uAspect;
uniform float uPower;
uniform float uRotation;
uniform vec3 uAccent;
uniform int uMaxSteps;

const int MAX_ITER = 8;
const float BAILOUT = 2.5;

// Classic distance-estimated Mandelbulb (power-8 default, driven toward
// power-9/10 by build/tension — HYSTERESIS.md §4c). Landing-hero only: this
// is far too expensive to run as a persistent background.
float mandelbulbDE(vec3 pos, float power) {
  vec3 z = pos;
  float dr = 1.0;
  float r = 0.0;
  for (int i = 0; i < MAX_ITER; i++) {
    r = length(z);
    if (r > BAILOUT) break;

    float theta = acos(clamp(z.z / max(r, 1e-6), -1.0, 1.0));
    float phi = atan(z.y, z.x);
    dr = pow(r, power - 1.0) * power * dr + 1.0;

    float zr = pow(r, power);
    theta *= power;
    phi *= power;

    z = zr * vec3(sin(theta) * cos(phi), sin(theta) * sin(phi), cos(theta));
    z += pos;
  }
  return 0.5 * log(max(r, 1e-6)) * r / dr;
}

vec3 rotateY(vec3 p, float a) {
  float c = cos(a);
  float s = sin(a);
  return vec3(c * p.x + s * p.z, p.y, -s * p.x + c * p.z);
}

void main() {
  vec2 uv = vUv * 2.0 - 1.0;
  uv.x *= uAspect;

  vec3 ro = vec3(0.0, 0.0, -3.0);
  vec3 rd = normalize(vec3(uv, 1.6));
  ro = rotateY(ro, uRotation);
  rd = rotateY(rd, uRotation);

  float t = 0.0;
  float glow = 0.0;
  bool hit = false;
  for (int i = 0; i < 256; i++) {
    if (i >= uMaxSteps) break;
    vec3 p = ro + rd * t;
    float d = mandelbulbDE(p, uPower);
    glow += 0.0025 / max(d, 0.0008);
    if (d < 0.0015) {
      hit = true;
      break;
    }
    t += d;
    if (t > 8.0) break;
  }

  vec3 base = vec3(0.02, 0.018, 0.035);
  vec3 color = base + uAccent * glow * 0.06;
  if (hit) {
    float shade = clamp(1.0 - t / 6.0, 0.0, 1.0);
    color = mix(base, uAccent * 1.2, shade);
  }
  fragColor = vec4(color, 1.0);
}
