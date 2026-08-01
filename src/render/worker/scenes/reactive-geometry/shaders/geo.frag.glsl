#version 300 es
precision highp float;

in vec2 vLocal;
in float vAge;
in float vTone;
in float vStrength;

out vec4 fragColor;

uniform float uHueShift;

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
  // Low hits draw as squares, high hits as rings — so a kick and a hi-hat
  // differ in form as well as position, not just colour.
  float ring = length(vLocal);
  float box = max(abs(vLocal.x), abs(vLocal.y));
  float d = mix(box, ring, smoothstep(0.35, 0.65, vTone));

  // Hard-edged stroke of even thickness: the point of this scene is that
  // individual events are countable, which soft blobs defeat.
  float thickness = 0.16;
  float aa = fwidth(d) * 1.5 + 1e-5;
  float outer = 1.0 - smoothstep(1.0 - aa, 1.0, d);
  float inner = 1.0 - smoothstep(1.0 - thickness - aa, 1.0 - thickness, d);
  float stroke = clamp(outer - inner, 0.0, 1.0);

  float fade = 1.0 - vAge;
  float alpha = stroke * fade * (0.35 + 0.65 * vStrength);
  if (alpha <= 0.002) discard;

  vec3 color = hsl2rgb(vec3(fract(uHueShift + mix(0.02, 0.55, vTone)), 0.9, 0.62));
  fragColor = vec4(color * alpha, alpha);
}
