//! Trail/glow memory for memoryless scenes — ported from
//! `src/render/worker/passes/persistence.frag.glsl`: keep the brighter of
//! the decayed trail vs. the fresh frame, per channel.

use crate::gpu::{GpuContext, GpuError, OffscreenTarget};
use crate::passes::{pack_slots, CommonUniforms};

pub fn render_persistence(
    ctx: &GpuContext,
    output: &OffscreenTarget,
    current: &OffscreenTarget,
    prev: &OffscreenTarget,
    sampler: &wgpu::Sampler,
    decay: f32,
) -> Result<(), GpuError> {
    let common = CommonUniforms::new(0.0, [output.width() as f32, output.height() as f32]);
    let slots = [[decay, 0.0, 0.0, 0.0]];
    output.render_glsl_fragment_shader(
        ctx,
        PERSISTENCE_GLSL,
        common.bytes(),
        Some(&pack_slots(&slots)),
        &[(current.view(), sampler), (prev.view(), sampler)],
    )
}

const PERSISTENCE_GLSL: &str = r#"
#version 450 core
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 fragColor;

layout(std140, set = 0, binding = 0) uniform Common {
  float TIME; float TIMEDELTA; vec2 RENDERSIZE; int PASSINDEX; int FRAMEINDEX; vec4 DATE;
};
layout(std140, set = 0, binding = 1) uniform Inputs { vec4 slot[1]; };

layout(set = 0, binding = 2) uniform texture2D uCurrentTex;
layout(set = 0, binding = 3) uniform sampler uCurrentSamp;
layout(set = 0, binding = 4) uniform texture2D uPrevTex;
layout(set = 0, binding = 5) uniform sampler uPrevSamp;

void main() {
  float decay = slot[0].x;
  vec3 prev = texture(sampler2D(uPrevTex, uPrevSamp), vUv).rgb * decay;
  vec3 cur = texture(sampler2D(uCurrentTex, uCurrentSamp), vUv).rgb;
  fragColor = vec4(max(prev, cur), 1.0);
}
"#;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn keeps_brighter_of_decayed_trail_and_fresh_frame() {
        let ctx = match GpuContext::new_blocking() {
            Ok(c) => c,
            Err(_) => return,
        };
        let sampler = ctx.create_clamp_sampler();
        let current = OffscreenTarget::new(&ctx, 64, 64);
        current.render_glsl_fragment_shader(&ctx, "#version 450 core\nlayout(location=0) out vec4 fragColor;\nvoid main(){fragColor=vec4(0.2,0.2,0.2,1.0);}", &[0u8; 32], None, &[]).unwrap();
        let prev = OffscreenTarget::new(&ctx, 64, 64);
        prev.render_glsl_fragment_shader(&ctx, "#version 450 core\nlayout(location=0) out vec4 fragColor;\nvoid main(){fragColor=vec4(1.0,1.0,1.0,1.0);}", &[0u8; 32], None, &[]).unwrap();

        let out = OffscreenTarget::new(&ctx, 64, 64);
        render_persistence(&ctx, &out, &current, &prev, &sampler, 0.9).unwrap();
        let pixels = out.read_pixels(&ctx).unwrap();
        // prev*0.9 = 0.9*255 ~= 229 > cur (0.2*255=51) -> max picks the trail.
        assert!(
            pixels[0] > 200,
            "expected the decayed bright trail to win, got {}",
            pixels[0]
        );
    }
}
