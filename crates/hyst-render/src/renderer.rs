//! One real frame loop: Julia substrate -> memory field ping-pong ->
//! persistence/decay -> bloom -> composite -> beam on top -> final
//! `OffscreenTarget`. R2's own done-when bar (plan §4): "Julia substrate +
//! memory field + beam render". **Not claimed**: a pixel-perfect diff
//! against the frozen browser build — that needs a browser, out of reach
//! here; flagged, not faked.
//!
//! Beam compositing deviates from the original's shader-side foreground/
//! background split: the beam is drawn with real alpha blending directly
//! onto the tonemapped composite output (simplest correct thing that still
//! draws real hardware line geometry on top of the substrate), rather than
//! being fed into `composite.frag.glsl` as another sampled input.

use crate::gpu::{GpuContext, GpuError, OffscreenTarget};
use crate::passes::beam::{render_beam, Segment};
use crate::passes::bloom::{render_blur, render_bright_pass};
use crate::passes::composite::render_composite;
use crate::passes::julia::{render_julia_perturbed, JuliaNavState};
use crate::passes::memory_field::{render_memory_field, MemoryFieldParams};
use crate::passes::noise_texture::NoiseTexture;

/// Per-frame knobs a caller (a driven test, or eventually `hyst-audio`
/// signals) sets; everything else about the pipeline's shape is fixed.
pub struct FrameParams {
    pub julia: JuliaNavState,
    pub memory_field: MemoryFieldParams,
    pub persistence_decay: f32,
    pub bloom_threshold: f32,
    pub bloom_strength: f32,
    /// Pre-tonemap scale (composite.rs). The memory field's `cur_gain`
    /// formula normalizes its own steady-state gain to a fixed ~7x
    /// (memory_field.rs's `DECAY_REFERENCE`) regardless of decay — by
    /// design, not a bug — so a long-running feedback loop needs real
    /// exposure headroom here or it saturates Reinhard's knee into a
    /// washed-out near-white smudge. 1.0 = no adjustment.
    pub exposure: f32,
    pub beam_segments: Vec<Segment>,
    pub beam_color: [f32; 3],
    pub beam_intensity: f32,
}

/// Owns every buffer the frame loop needs across calls (the memory field's
/// ping-pong pair persists between `render_frame` calls — that's the whole
/// point of a feedback field).
pub struct Renderer {
    width: u32,
    height: u32,
    aspect: f32,
    sampler: wgpu::Sampler,
    noise: NoiseTexture,
    julia_out: OffscreenTarget,
    field_a: OffscreenTarget,
    field_b: OffscreenTarget,
    field_is_a: bool,
    persistence_prev: OffscreenTarget,
    bright: OffscreenTarget,
    blur_h: OffscreenTarget,
    blur_v: OffscreenTarget,
    composited: OffscreenTarget,
    final_out: OffscreenTarget,
}

impl Renderer {
    /// `width`/`height` must keep `width * 4` a multiple of 256 (wgpu
    /// readback alignment — see `OffscreenTarget::read_pixels`); any
    /// multiple of 64 works.
    pub fn new(ctx: &GpuContext, width: u32, height: u32) -> Self {
        Self {
            width,
            height,
            aspect: width as f32 / height as f32,
            sampler: ctx.create_clamp_sampler(),
            noise: NoiseTexture::bake(ctx, 64, 64),
            julia_out: OffscreenTarget::new(ctx, width, height),
            field_a: OffscreenTarget::new(ctx, width, height),
            field_b: OffscreenTarget::new(ctx, width, height),
            field_is_a: true,
            persistence_prev: OffscreenTarget::new(ctx, width, height),
            bright: OffscreenTarget::new(ctx, width, height),
            blur_h: OffscreenTarget::new(ctx, width, height),
            blur_v: OffscreenTarget::new(ctx, width, height),
            composited: OffscreenTarget::new(ctx, width, height),
            final_out: OffscreenTarget::new(ctx, width, height),
        }
    }

    pub fn width(&self) -> u32 {
        self.width
    }

    pub fn height(&self) -> u32 {
        self.height
    }

    /// Renders one frame end to end, returns the final RGBA8 pixels
    /// (`read_pixels` on the internal final target).
    pub fn render_frame(
        &mut self,
        ctx: &GpuContext,
        params: &FrameParams,
    ) -> Result<Vec<u8>, GpuError> {
        // Always the perturbation path (Task 1): `render_julia` (direct
        // f32 iteration) was previously the only one wired in here —
        // `render_julia_perturbed` existed, was tested, but was genuinely
        // dead code, which is the real root cause of "perturbation doesn't
        // seem to work." Perturbation is mathematically identical to direct
        // iteration at shallow zoom (`delta = full - Z_n` is an exact
        // algebraic reformulation of the same recurrence, not an
        // approximation), so it degrades gracefully rather than needing a
        // depth-gated switch — see its own doc for the empirical depths
        // where it stays sharp well past where direct iteration collapses.
        render_julia_perturbed(ctx, &self.julia_out, &params.julia, self.aspect)?;

        let (field_prev, field_dst) = if self.field_is_a {
            (&self.field_a, &self.field_b)
        } else {
            (&self.field_b, &self.field_a)
        };
        render_memory_field(
            ctx,
            field_dst,
            &self.julia_out,
            field_prev,
            &self.noise,
            &self.sampler,
            &params.memory_field,
        )?;
        self.field_is_a = !self.field_is_a;
        let field_out = if self.field_is_a {
            &self.field_a
        } else {
            &self.field_b
        };

        crate::passes::persistence::render_persistence(
            ctx,
            &self.composited,
            field_out,
            &self.persistence_prev,
            &self.sampler,
            params.persistence_decay,
        )?;
        copy_texture(ctx, &self.composited, &self.persistence_prev);

        render_bright_pass(
            ctx,
            &self.bright,
            &self.composited,
            &self.sampler,
            params.bloom_threshold,
        )?;
        render_blur(ctx, &self.blur_h, &self.bright, &self.sampler, [1.0, 0.0])?;
        render_blur(ctx, &self.blur_v, &self.blur_h, &self.sampler, [0.0, 1.0])?;

        render_composite(
            ctx,
            &self.final_out,
            &self.composited,
            Some(&self.blur_v),
            &self.sampler,
            params.bloom_strength,
            params.exposure,
        )?;

        if !params.beam_segments.is_empty() {
            // Tried round joint discs at every vertex (fixes flat-cap
            // notches at sharp corners) — for a dense, near-straight
            // polyline this read as a visible bead/pearl chain no matter
            // how the falloff/blending was tuned (reported: "balls
            // connected together"), because a disc's silhouette always
            // bulges past a short rectangle's sides regardless of shading.
            // Reverted: segments only, matching how this looked before
            // that change. At a small enough bend angle between
            // consecutive segments (i.e. enough points) and a thin enough
            // line, a flat-cap notch is genuinely imperceptible — that's
            // the actual fix for "invisible vertices/bends", not joint
            // geometry. See `render_beam_joints` in beam.rs — kept, tested,
            // just not called here; a real primitive for sharp corners
            // elsewhere, wrong tool for this smooth curve.
            const HALF_WIDTH: f32 = 0.012;
            render_beam(
                ctx,
                &self.final_out,
                &params.beam_segments,
                params.beam_color,
                params.beam_intensity,
                self.aspect,
                HALF_WIDTH,
            )?;
        }

        self.final_out.read_pixels(ctx)
    }
}

/// `persistence.frag.glsl`'s own feedback needs last frame's *composited*
/// output as `uPrev` next frame — a plain GPU-side texture-to-texture copy,
/// no shader needed.
fn copy_texture(ctx: &GpuContext, src: &OffscreenTarget, dst: &OffscreenTarget) {
    let mut encoder = ctx
        .device
        .create_command_encoder(&wgpu::CommandEncoderDescriptor { label: None });
    encoder.copy_texture_to_texture(
        wgpu::ImageCopyTexture {
            texture: src.texture(),
            mip_level: 0,
            origin: wgpu::Origin3d::ZERO,
            aspect: wgpu::TextureAspect::All,
        },
        wgpu::ImageCopyTexture {
            texture: dst.texture(),
            mip_level: 0,
            origin: wgpu::Origin3d::ZERO,
            aspect: wgpu::TextureAspect::All,
        },
        wgpu::Extent3d {
            width: src.width(),
            height: src.height(),
            depth_or_array_layers: 1,
        },
    );
    ctx.queue.submit(std::iter::once(encoder.finish()));
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::passes::beam::Segment;

    fn default_params(t: f32) -> FrameParams {
        FrameParams {
            julia: JuliaNavState::driven_by_time(t),
            memory_field: MemoryFieldParams {
                decay: 0.9,
                aspect: 1.0,
                flow_uv: [t * 0.05, 0.0],
                flow_scale: 2.0,
                flow_strength: 0.01,
                fold_count: 4.0,
                mirror_strength: 0.5,
            },
            persistence_decay: 0.8,
            bloom_threshold: 0.3,
            bloom_strength: 0.6,
            exposure: 1.0,
            beam_segments: vec![Segment {
                p0: [-0.5, 0.0],
                p1: [0.5, 0.0],
            }],
            beam_color: [1.0, 1.0, 1.0],
            beam_intensity: 1.5,
        }
    }

    /// Bites: a full multi-frame run through every pass produces real,
    /// changing, non-degenerate (not all-black, not all-saturated) output —
    /// the actual "driveable render loop" bar, not just "no panic."
    #[test]
    fn full_frame_loop_produces_changing_non_degenerate_output() {
        let ctx = match GpuContext::new_blocking() {
            Ok(c) => c,
            Err(_) => return,
        };
        let mut renderer = Renderer::new(&ctx, 128, 128);
        let frame0 = renderer.render_frame(&ctx, &default_params(0.0)).unwrap();
        let frame10 = renderer.render_frame(&ctx, &default_params(1.0)).unwrap();

        let mean = |p: &[u8]| p.iter().map(|&b| b as f64).sum::<f64>() / p.len() as f64;
        let m0 = mean(&frame0);
        let m10 = mean(&frame10);
        assert!(
            m0 > 1.0 && m0 < 250.0,
            "frame should be non-degenerate, mean {m0}"
        );
        assert!(
            (m0 - m10).abs() > 0.1 || frame0 != frame10,
            "consecutive frames of a live feedback loop should differ"
        );
    }
}
