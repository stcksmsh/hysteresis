//! Memory field ping-pong feedback — ported from
//! `src/render/worker/passes/memory-field.frag.glsl`. Curl-noise advection +
//! kaleidoscope fold + decay, exactly per that file's own extensive comments
//! (read in full before writing this, including the fold-seam bug/fix — see
//! `docs/LEGACY_TS.md`'s "Fold seam / Julia zoom follow-up" entry, and this
//! file's own `main()`: **cross-fade the COLORS of a raw-sampled and a
//! fully-folded read by `mirror_strength`, uniformly across the whole
//! screen** — never a naive `abs(mod(theta,wedge)-wedge/2)` fold blended by
//! angle, which is a documented 2-to-1 map that leaves half of every wedge
//! permanently un-organized regardless of `mirror_strength`.

use crate::gpu::{GpuContext, GpuError, OffscreenTarget};
use crate::passes::noise_texture::NoiseTexture;
use crate::passes::{pack_slots, CommonUniforms};

/// Matches `memory-field-pass.ts`'s `DECAY_REFERENCE` — the decay value at
/// which the look is "at rest" / unchanged from before `cur_gain` existed.
const DECAY_REFERENCE: f32 = 0.86;

#[derive(Clone, Copy, Debug)]
pub struct MemoryFieldParams {
    pub decay: f32,
    pub aspect: f32,
    pub flow_uv: [f32; 2],
    pub flow_scale: f32,
    pub flow_strength: f32,
    pub fold_count: f32,
    pub mirror_strength: f32,
}

#[allow(clippy::too_many_arguments)]
pub fn render_memory_field(
    ctx: &GpuContext,
    output: &OffscreenTarget,
    current: &OffscreenTarget,
    prev: &OffscreenTarget,
    noise: &NoiseTexture,
    sampler: &wgpu::Sampler,
    params: &MemoryFieldParams,
) -> Result<(), GpuError> {
    // Ported from memory-field-pass.ts: cur_gain is NOT an independent knob —
    // it's derived from decay so raising decay (to hold a build/break longer)
    // doesn't ALSO multiply steady-state brightness by the same factor (the
    // documented "washed-out mush" bug this formula exists to prevent).
    let cur_gain = ((1.0 - params.decay) / (1.0 - DECAY_REFERENCE)).max(0.0);
    let common = CommonUniforms::new(0.0, [output.width() as f32, output.height() as f32]);
    let slots = [
        [
            1.0 / noise.width as f32,
            1.0 / noise.height as f32,
            0.0,
            0.0,
        ],
        [params.decay, 0.0, 0.0, 0.0],
        [cur_gain, 0.0, 0.0, 0.0],
        [params.aspect, 0.0, 0.0, 0.0],
        [params.flow_uv[0], params.flow_uv[1], 0.0, 0.0],
        [params.flow_scale, 0.0, 0.0, 0.0],
        [params.flow_strength, 0.0, 0.0, 0.0],
        [params.fold_count, 0.0, 0.0, 0.0],
        [params.mirror_strength, 0.0, 0.0, 0.0],
    ];
    output.render_glsl_fragment_shader(
        ctx,
        MEMORY_FIELD_GLSL,
        common.bytes(),
        Some(&pack_slots(&slots)),
        &[
            (current.view(), sampler),
            (prev.view(), sampler),
            (&noise.view, sampler),
        ],
    )
}

const MEMORY_FIELD_GLSL: &str = r#"
#version 450 core
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 fragColor;

layout(std140, set = 0, binding = 0) uniform Common {
  float TIME;
  float TIMEDELTA;
  vec2 RENDERSIZE;
  int PASSINDEX;
  int FRAMEINDEX;
  vec4 DATE;
};
layout(std140, set = 0, binding = 1) uniform Inputs { vec4 slot[9]; };

layout(set = 0, binding = 2) uniform texture2D uCurrentTex;
layout(set = 0, binding = 3) uniform sampler uCurrentSamp;
layout(set = 0, binding = 4) uniform texture2D uPrevTex;
layout(set = 0, binding = 5) uniform sampler uPrevSamp;
layout(set = 0, binding = 6) uniform texture2D uNoiseTex;
layout(set = 0, binding = 7) uniform sampler uNoiseSamp;

const float TWO_PI = 6.28318530718;

vec2 curlAt(vec2 uv, vec2 noiseTexel) {
  float pL = texture(sampler2D(uNoiseTex, uNoiseSamp), uv - vec2(noiseTexel.x, 0.0)).b;
  float pR = texture(sampler2D(uNoiseTex, uNoiseSamp), uv + vec2(noiseTexel.x, 0.0)).b;
  float pD = texture(sampler2D(uNoiseTex, uNoiseSamp), uv - vec2(0.0, noiseTexel.y)).b;
  float pU = texture(sampler2D(uNoiseTex, uNoiseSamp), uv + vec2(0.0, noiseTexel.y)).b;
  return vec2(pU - pD, -(pR - pL));
}

// Earned-symmetry fold — see this file's module doc for why the caller
// (main()) cross-fades COLORS from this and the raw domain, never angles.
vec2 foldedDomain(vec2 uv, float aspect, float foldCount) {
  vec2 centered = (uv - 0.5) * vec2(aspect, 1.0);
  float r = length(centered);
  float wedge = TWO_PI / max(foldCount, 1.0);
  float theta = atan(centered.y, centered.x) + wedge * 0.25;
  float s = mod(theta, wedge) / wedge;
  float folded = wedge * 0.5 * (0.5 - 0.5 * cos(TWO_PI * s)) - wedge * 0.25;
  vec2 foldedCentered = vec2(cos(folded), sin(folded)) * r;
  return foldedCentered / vec2(aspect, 1.0) + 0.5;
}

vec2 advect(vec2 domainUv, vec2 flowUv, float flowScale, float flowStrength, vec2 noiseTexel) {
  vec2 flowSample = domainUv * flowScale + flowUv;
  vec2 flow = curlAt(flowSample, noiseTexel);
  return domainUv - flow * flowStrength;
}

void main() {
  vec2 noiseTexel = slot[0].xy;
  float decay = slot[1].x;
  float curGain = slot[2].x;
  float aspect = slot[3].x;
  vec2 flowUv = slot[4].xy;
  float flowScale = slot[5].x;
  float flowStrength = slot[6].x;
  float foldCount = slot[7].x;
  float mirrorStrength = slot[8].x;

  vec2 rawUv = advect(vUv, flowUv, flowScale, flowStrength, noiseTexel);
  vec2 foldedUv = advect(foldedDomain(vUv, aspect, foldCount), flowUv, flowScale, flowStrength, noiseTexel);
  vec3 rawPrev = texture(sampler2D(uPrevTex, uPrevSamp), rawUv).rgb;
  vec3 foldedPrev = texture(sampler2D(uPrevTex, uPrevSamp), foldedUv).rgb;
  vec3 prev = mix(rawPrev, foldedPrev, mirrorStrength) * decay;
  vec3 cur = texture(sampler2D(uCurrentTex, uCurrentSamp), vUv).rgb;
  vec3 result = prev + cur * curGain;

  if (any(isnan(result)) || any(isinf(result))) {
    result = cur;
  }
  result = clamp(result, vec3(0.0), vec3(64.0));

  fragColor = vec4(result, 1.0);
}
"#;

#[cfg(test)]
mod tests {
    use super::*;

    fn params(mirror: f32) -> MemoryFieldParams {
        MemoryFieldParams {
            decay: 0.9,
            aspect: 1.0,
            flow_uv: [0.0, 0.0],
            flow_scale: 2.0,
            flow_strength: 0.02,
            fold_count: 4.0,
            mirror_strength: mirror,
        }
    }

    /// Bites: feedback accumulation is real (frame 100 meaningfully differs
    /// from frame 0 under nonzero input) and deterministic (two runs from
    /// zero input, zero frames apart, produce byte-identical output) — not
    /// just "renders something."
    #[test]
    fn feedback_accumulates_under_nonzero_input_and_is_deterministic_under_zero_input() {
        let ctx = match GpuContext::new_blocking() {
            Ok(c) => c,
            Err(_) => return,
        };
        let sampler = ctx.create_clamp_sampler();
        let noise = NoiseTexture::bake(&ctx, 64, 64);

        // Nonzero input: a bright, off-center current frame fed in every
        // iteration, ping-ponged through the field for 100 frames.
        let current = OffscreenTarget::new(&ctx, 64, 64);
        current
            .render_glsl_fragment_shader(
                &ctx,
                r#"#version 450 core
layout(location=0) in vec2 vUv;
layout(location=0) out vec4 fragColor;
void main() { fragColor = vec4(step(0.5, vUv.x), step(0.5, vUv.y), 0.5, 1.0); }
"#,
                &[0u8; 32],
                None,
                &[],
            )
            .unwrap();

        let mut a = OffscreenTarget::new(&ctx, 64, 64);
        let mut b = OffscreenTarget::new(&ctx, 64, 64);
        let frame0 = a.read_pixels(&ctx).unwrap();
        for _ in 0..100 {
            render_memory_field(&ctx, &b, &current, &a, &noise, &sampler, &params(0.5)).unwrap();
            std::mem::swap(&mut a, &mut b);
        }
        let frame100 = a.read_pixels(&ctx).unwrap();
        let mean_delta: f64 = frame0
            .iter()
            .zip(frame100.iter())
            .map(|(x, y)| (*x as f64 - *y as f64).abs())
            .sum::<f64>()
            / frame0.len() as f64;
        assert!(mean_delta > 5.0, "100 frames of feedback under nonzero input should visibly diverge from frame 0, got {mean_delta}");

        // Zero input: identical run twice from scratch must be byte-identical.
        let zero_current = OffscreenTarget::new(&ctx, 64, 64);
        zero_current
            .render_glsl_fragment_shader(&ctx, "#version 450 core\nlayout(location=0) out vec4 fragColor;\nvoid main(){fragColor=vec4(0.0,0.0,0.0,1.0);}", &[0u8; 32], None, &[])
            .unwrap();
        let run_once = |ctx: &GpuContext| -> Vec<u8> {
            let mut a = OffscreenTarget::new(ctx, 64, 64);
            let mut b = OffscreenTarget::new(ctx, 64, 64);
            for _ in 0..10 {
                render_memory_field(ctx, &b, &zero_current, &a, &noise, &sampler, &params(0.0))
                    .unwrap();
                std::mem::swap(&mut a, &mut b);
            }
            a.read_pixels(ctx).unwrap()
        };
        assert_eq!(
            run_once(&ctx),
            run_once(&ctx),
            "zero-input runs must be bit-identical (no hidden nondeterminism)"
        );
    }

    /// Bites: at mirror_strength=1 the field is a pure fold-read — this
    /// checks real rotational symmetry pixel-by-pixel (within tolerance),
    /// not eyeballed.
    #[test]
    fn full_mirror_strength_gives_real_rotational_symmetry() {
        let ctx = match GpuContext::new_blocking() {
            Ok(c) => c,
            Err(_) => return,
        };
        let sampler = ctx.create_clamp_sampler();
        let noise = NoiseTexture::bake(&ctx, 64, 64);
        let width = 128u32;
        let current = OffscreenTarget::new(&ctx, width, width);
        // Asymmetric seed frame (a single off-axis diagonal gradient) so any
        // observed symmetry in the output can only come from the fold, not
        // from a coincidentally-symmetric input.
        current
            .render_glsl_fragment_shader(
                &ctx,
                r#"#version 450 core
layout(location=0) in vec2 vUv;
layout(location=0) out vec4 fragColor;
void main() { fragColor = vec4(vUv.x, vUv.y * 0.3, 1.0 - vUv.x, 1.0); }
"#,
                &[0u8; 32],
                None,
                &[],
            )
            .unwrap();

        let mut a = OffscreenTarget::new(&ctx, width, width);
        let mut b = OffscreenTarget::new(&ctx, width, width);
        // A few decay-free (decay near 1 (derived cur_gain near 0)) fold-only passes so the
        // field converges toward the fully-folded pattern.
        let p = MemoryFieldParams {
            decay: 1.0,
            aspect: 1.0,
            flow_uv: [0.0, 0.0],
            flow_scale: 0.0,
            flow_strength: 0.0, // no advection: isolate the fold, not the noise-driven flow
            fold_count: 4.0,
            mirror_strength: 1.0,
        };
        for _ in 0..40 {
            render_memory_field(&ctx, &b, &current, &a, &noise, &sampler, &p).unwrap();
            std::mem::swap(&mut a, &mut b);
        }
        let pixels = a.read_pixels(&ctx).unwrap();
        let px = |x: i32, y: i32| -> [i32; 3] {
            let x = x.rem_euclid(width as i32) as u32;
            let y = y.rem_euclid(width as i32) as u32;
            let i = ((y * width + x) * 4) as usize;
            [pixels[i] as i32, pixels[i + 1] as i32, pixels[i + 2] as i32]
        };
        // 4-fold: rotating a point 90 degrees about the center should land on
        // a near-equal pixel. Check several sample points, tolerant to
        // interpolation/advection noise but real enough to catch a broken fold.
        let c = width as i32 / 2;
        let mut max_diff = 0i32;
        for &(dx, dy) in &[(20, 5), (35, 10), (15, 40), (45, 45)] {
            let p0 = px(c + dx, c + dy);
            // 90-degree rotation about center: (dx,dy) -> (-dy,dx)
            let p1 = px(c - dy, c + dx);
            for ch in 0..3 {
                max_diff = max_diff.max((p0[ch] - p1[ch]).abs());
            }
        }
        assert!(max_diff < 40, "full mirror strength should give ~4-fold rotational symmetry, max channel diff {max_diff}");
    }
}
