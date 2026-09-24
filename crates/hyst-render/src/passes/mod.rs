//! Render passes ported from `src/render/worker/passes/*.frag.glsl` and
//! `scenes/julia/shaders/*.glsl`. Port-the-intent, not the literal WebGL2
//! plumbing (`gl/{fullscreen-quad,fbo,program,noise-texture,context}.ts`):
//! `OffscreenTarget` (from `crate::gpu`) is the ping-pong buffer,
//! `GpuContext::create_clamp_sampler` is the one sampler every pass needs,
//! and `OffscreenTarget::render_glsl_fragment_shader` is the fullscreen-pass
//! driver for every pass except the beam (real instanced geometry, its own
//! pipeline — see `beam.rs`).
//!
//! Every pass shader is hand-written directly in the naga-GLSL-450 dialect
//! (see `isf_translate`'s module doc for why: no loose uniforms, no combined
//! `sampler2D`, `gl_FragColor`) rather than mechanically re-run through
//! `translate_isf_glsl` — these aren't ISF shader bodies with a JSON header,
//! they're this engine's own internal passes, so there's no ISF document to
//! translate from; the porting step is the same substitution done by hand
//! once per shader instead of at runtime.
//!
//! Recreating a full pipeline (shader modules, bind group layout, pipeline)
//! on every `render_glsl_fragment_shader` call is real, deliberate,
//! unoptimized cost — this crate renders a handful of frames offline right
//! now, not 60fps realtime; caching pipelines is a later-pass optimization
//! per the plan's "port faithfully first, optimize second," not an
//! oversight.

pub mod beam;
pub mod bloom;
pub mod composite;
pub mod julia;
pub mod mandelbulb;
pub mod memory_field;
pub mod noise_texture;
pub mod persistence;

use bytemuck::{Pod, Zeroable};

/// The `Common` UBO every fullscreen pass binds at group 0 / binding 0,
/// std140-laid-out to match the GLSL `Common` block declared in every pass
/// shader below (`float,float,vec2,int,int,vec4` = 32 bytes, no implicit
/// padding needed since each field already starts at a multiple of its own
/// alignment).
#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable)]
pub struct CommonUniforms {
    pub time: f32,
    pub timedelta: f32,
    pub render_size: [f32; 2],
    pub passindex: i32,
    pub frameindex: i32,
    pub _pad: [f32; 2],
    pub date: [f32; 4],
}

impl CommonUniforms {
    pub fn new(time: f32, render_size: [f32; 2]) -> Self {
        Self {
            time,
            timedelta: 0.0,
            render_size,
            passindex: 0,
            frameindex: 0,
            _pad: [0.0; 2],
            date: [0.0; 4],
        }
    }

    pub fn bytes(&self) -> &[u8] {
        bytemuck::bytes_of(self)
    }
}

/// Packs a pass's scalar/vector params into one `vec4` per slot (`Inputs`
/// UBO, binding 1) — see `isf_translate`'s module doc for why loose scalar
/// uniforms aren't legal GLSL for `naga`'s Vulkan-flavored frontend. Wastes
/// up to 3 floats per slot; not worth optimizing packing density for a
/// handful of params per pass.
pub fn pack_slots(slots: &[[f32; 4]]) -> Vec<u8> {
    bytemuck::cast_slice(slots).to_vec()
}
