//! `wgpu` bootstrap (R2's first "Do" item) — instance/adapter/device setup
//! plus a minimal offscreen render-to-texture pipeline, verified by an
//! actual headless render + pixel readback against whatever real GPU
//! adapter this machine exposes (no window/surface needed — `wgpu` renders
//! to an owned texture just as well). This is the foundation the later
//! Julia/memory-field/beam passes build on; **not yet built this session**,
//! flagged rather than silently absent — see this module's own doc and
//! `AGENTS.md` §5 for exactly what's deferred.

use std::sync::mpsc;
use wgpu::util::DeviceExt;

#[derive(Debug, thiserror::Error)]
pub enum GpuError {
    #[error("no compatible GPU adapter found")]
    NoAdapter,
    #[error("failed to request a device: {0}")]
    RequestDevice(#[from] wgpu::RequestDeviceError),
    #[error("failed to create shader/pipeline: {0}")]
    Pipeline(String),
    #[error("buffer readback failed: {0}")]
    Readback(String),
}

/// Owns the instance/adapter/device/queue — created once, reused by every
/// render pass. No window/surface: this crate renders to owned textures,
/// consistent with the plan's "port faithfully first" render-to-texture
/// architecture (the render worker owns an `OffscreenCanvas` in the TS
/// original too, not a window it draws to directly).
pub struct GpuContext {
    pub instance: wgpu::Instance,
    pub adapter: wgpu::Adapter,
    pub device: wgpu::Device,
    pub queue: wgpu::Queue,
}

impl GpuContext {
    pub async fn new() -> Result<Self, GpuError> {
        let instance = wgpu::Instance::new(wgpu::InstanceDescriptor {
            backends: wgpu::Backends::all(),
            ..Default::default()
        });
        let adapter = instance
            .request_adapter(&wgpu::RequestAdapterOptions {
                power_preference: wgpu::PowerPreference::HighPerformance,
                compatible_surface: None,
                force_fallback_adapter: false,
            })
            .await
            .ok_or(GpuError::NoAdapter)?;
        let (device, queue) = adapter
            .request_device(&wgpu::DeviceDescriptor::default(), None)
            .await?;
        Ok(Self {
            instance,
            adapter,
            device,
            queue,
        })
    }

    /// Blocking convenience for non-async call sites (tests, the eventual
    /// CLI wiring) — `pollster::block_on` over `new()`.
    pub fn new_blocking() -> Result<Self, GpuError> {
        pollster::block_on(Self::new())
    }

    /// Linear-filter, clamp-to-edge sampler — the one sampler every render
    /// pass uses (matches the TS original's `fbo.ts` default: `CLAMP_TO_EDGE`
    /// so out-of-[0,1] advection reads in memory-field.frag.glsl don't wrap).
    pub fn create_clamp_sampler(&self) -> wgpu::Sampler {
        self.device.create_sampler(&wgpu::SamplerDescriptor {
            address_mode_u: wgpu::AddressMode::ClampToEdge,
            address_mode_v: wgpu::AddressMode::ClampToEdge,
            address_mode_w: wgpu::AddressMode::ClampToEdge,
            mag_filter: wgpu::FilterMode::Linear,
            min_filter: wgpu::FilterMode::Linear,
            ..Default::default()
        })
    }
}

/// A fixed-size RGBA8 render target with no vertex buffers — the fragment
/// shader is driven by a hardcoded fullscreen-triangle vertex shader
/// (the standard `@builtin(vertex_index)` trick), matching the TS
/// original's `fullscreen-quad.ts`/`fullscreen.vert.glsl` pattern (a real
/// GLSL-to-WGSL shader translation layer, for an actual `.hyst` fragment
/// body, is explicitly NOT built this session — see module doc).
pub struct OffscreenTarget {
    texture: wgpu::Texture,
    view: wgpu::TextureView,
    width: u32,
    height: u32,
}

const FULLSCREEN_VERTEX_WGSL: &str = r#"
@vertex
fn vs_main(@builtin(vertex_index) idx: u32) -> @builtin(position) vec4<f32> {
    var pos = array<vec2<f32>, 3>(
        vec2<f32>(-1.0, -1.0),
        vec2<f32>(3.0, -1.0),
        vec2<f32>(-1.0, 3.0),
    );
    return vec4<f32>(pos[idx], 0.0, 1.0);
}
"#;

impl OffscreenTarget {
    /// `width`/`height` should keep `width * 4` a multiple of 256 (wgpu's
    /// buffer-copy row-alignment requirement) for the simplest possible
    /// `read_pixels` — 64 (256 bytes/row) is a convenient choice used by
    /// this module's own tests; a general offscreen target used by a real
    /// render pass later will need real padding-aware readback.
    pub fn new(ctx: &GpuContext, width: u32, height: u32) -> Self {
        let texture = ctx.device.create_texture(&wgpu::TextureDescriptor {
            label: Some("hyst-render offscreen target"),
            size: wgpu::Extent3d {
                width,
                height,
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Rgba8Unorm,
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT
                | wgpu::TextureUsages::COPY_SRC
                | wgpu::TextureUsages::COPY_DST
                | wgpu::TextureUsages::TEXTURE_BINDING,
            view_formats: &[],
        });
        let view = texture.create_view(&wgpu::TextureViewDescriptor::default());
        Self {
            texture,
            view,
            width,
            height,
        }
    }

    /// Compiles `fragment_wgsl` (must expose an `fs_main` returning
    /// `@location(0) vec4<f32>`) alongside the fixed fullscreen-triangle
    /// vertex shader, and renders one frame into this target.
    pub fn render_fragment_shader(
        &self,
        ctx: &GpuContext,
        fragment_wgsl: &str,
    ) -> Result<(), GpuError> {
        let combined = format!("{FULLSCREEN_VERTEX_WGSL}\n{fragment_wgsl}");
        let shader = ctx
            .device
            .create_shader_module(wgpu::ShaderModuleDescriptor {
                label: Some("hyst-render offscreen smoke-test shader"),
                source: wgpu::ShaderSource::Wgsl(combined.into()),
            });

        let pipeline_layout = ctx
            .device
            .create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
                label: Some("hyst-render offscreen pipeline layout"),
                bind_group_layouts: &[],
                push_constant_ranges: &[],
            });
        let pipeline = ctx
            .device
            .create_render_pipeline(&wgpu::RenderPipelineDescriptor {
                label: Some("hyst-render offscreen pipeline"),
                layout: Some(&pipeline_layout),
                vertex: wgpu::VertexState {
                    module: &shader,
                    entry_point: "vs_main",
                    buffers: &[],
                    compilation_options: Default::default(),
                },
                fragment: Some(wgpu::FragmentState {
                    module: &shader,
                    entry_point: "fs_main",
                    targets: &[Some(wgpu::ColorTargetState {
                        format: wgpu::TextureFormat::Rgba8Unorm,
                        blend: None,
                        write_mask: wgpu::ColorWrites::ALL,
                    })],
                    compilation_options: Default::default(),
                }),
                primitive: wgpu::PrimitiveState::default(),
                depth_stencil: None,
                multisample: wgpu::MultisampleState::default(),
                multiview: None,
                cache: None,
            });

        let mut encoder = ctx
            .device
            .create_command_encoder(&wgpu::CommandEncoderDescriptor {
                label: Some("hyst-render offscreen encoder"),
            });
        {
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("hyst-render offscreen pass"),
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &self.view,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(wgpu::Color::BLACK),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                depth_stencil_attachment: None,
                timestamp_writes: None,
                occlusion_query_set: None,
            });
            pass.set_pipeline(&pipeline);
            pass.draw(0..3, 0..1);
        }
        ctx.queue.submit(std::iter::once(encoder.finish()));
        Ok(())
    }

    /// Reads the target back as tightly-packed RGBA8 (`width * height * 4`
    /// bytes) — only correct when `width * 4` is already a multiple of 256;
    /// see the constructor's doc comment.
    pub fn read_pixels(&self, ctx: &GpuContext) -> Result<Vec<u8>, GpuError> {
        let bytes_per_row = self.width * 4;
        if !bytes_per_row.is_multiple_of(256) {
            return Err(GpuError::Readback(format!(
                "width {} gives {bytes_per_row} bytes/row, not a multiple of wgpu's required 256 — pad the buffer copy for a general-purpose readback (not needed for this smoke test's fixed 64px width)",
                self.width
            )));
        }
        let buffer_size = (bytes_per_row * self.height) as u64;
        let buffer = ctx.device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("hyst-render offscreen readback buffer"),
            size: buffer_size,
            usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
            mapped_at_creation: false,
        });

        let mut encoder = ctx
            .device
            .create_command_encoder(&wgpu::CommandEncoderDescriptor {
                label: Some("hyst-render readback encoder"),
            });
        encoder.copy_texture_to_buffer(
            wgpu::ImageCopyTexture {
                texture: &self.texture,
                mip_level: 0,
                origin: wgpu::Origin3d::ZERO,
                aspect: wgpu::TextureAspect::All,
            },
            wgpu::ImageCopyBuffer {
                buffer: &buffer,
                layout: wgpu::ImageDataLayout {
                    offset: 0,
                    bytes_per_row: Some(bytes_per_row),
                    rows_per_image: Some(self.height),
                },
            },
            wgpu::Extent3d {
                width: self.width,
                height: self.height,
                depth_or_array_layers: 1,
            },
        );
        ctx.queue.submit(std::iter::once(encoder.finish()));

        let slice = buffer.slice(..);
        let (tx, rx) = mpsc::channel();
        slice.map_async(wgpu::MapMode::Read, move |result| {
            let _ = tx.send(result);
        });
        ctx.device.poll(wgpu::Maintain::Wait);
        rx.recv()
            .map_err(|e| GpuError::Readback(e.to_string()))?
            .map_err(|e| GpuError::Readback(e.to_string()))?;

        let data = slice.get_mapped_range().to_vec();
        buffer.unmap();
        Ok(data)
    }

    pub fn width(&self) -> u32 {
        self.width
    }

    pub fn height(&self) -> u32 {
        self.height
    }

    pub fn view(&self) -> &wgpu::TextureView {
        &self.view
    }

    pub fn texture(&self) -> &wgpu::Texture {
        &self.texture
    }

    /// Renders one frame of a real GLSL (`naga`-flavored, `#version 450
    /// core`) fragment shader, as produced by [`crate::isf_translate`] or
    /// hand-written for the internal passes — the general-purpose sibling of
    /// [`Self::render_fragment_shader`]'s WGSL smoke test. Binding layout is
    /// fixed and small on purpose (this crate has no per-shader-author
    /// binding *declarations* to honor beyond what the translator itself
    /// emits): group 0, binding 0 = the `Common` UBO (`common_ubo_bytes`,
    /// required even if the shader ignores it — simplest to always bind);
    /// binding 1 = the optional `Inputs` UBO (only bound when
    /// `inputs_ubo_bytes` is `Some`, matching whether the translator emitted
    /// an `Inputs` block at all); bindings 2, 4, 6, ... /odd = each sampled
    /// texture's `texture2D`/`sampler` pair in `sampled_textures` order (see
    /// the naga-GLSL-frontend limitation noted on `isf_translate` — no
    /// combined `sampler2D` uniform, so every sampled texture costs 2
    /// bindings, not 1).
    pub fn render_glsl_fragment_shader(
        &self,
        ctx: &GpuContext,
        fragment_glsl: &str,
        common_ubo_bytes: &[u8],
        inputs_ubo_bytes: Option<&[u8]>,
        sampled_textures: &[(&wgpu::TextureView, &wgpu::Sampler)],
    ) -> Result<(), GpuError> {
        let fs_module = ctx
            .device
            .create_shader_module(wgpu::ShaderModuleDescriptor {
                label: Some("hyst-render glsl fragment"),
                source: wgpu::ShaderSource::Glsl {
                    shader: fragment_glsl.into(),
                    stage: wgpu::naga::ShaderStage::Fragment,
                    defines: Default::default(),
                },
            });
        let vs_module = ctx
            .device
            .create_shader_module(wgpu::ShaderModuleDescriptor {
                label: Some("hyst-render glsl fullscreen vertex"),
                source: wgpu::ShaderSource::Glsl {
                    shader: FULLSCREEN_VERTEX_GLSL.into(),
                    stage: wgpu::naga::ShaderStage::Vertex,
                    defines: Default::default(),
                },
            });

        let mut entries = vec![wgpu::BindGroupLayoutEntry {
            binding: 0,
            visibility: wgpu::ShaderStages::FRAGMENT,
            ty: wgpu::BindingType::Buffer {
                ty: wgpu::BufferBindingType::Uniform,
                has_dynamic_offset: false,
                min_binding_size: None,
            },
            count: None,
        }];
        if inputs_ubo_bytes.is_some() {
            entries.push(wgpu::BindGroupLayoutEntry {
                binding: 1,
                visibility: wgpu::ShaderStages::FRAGMENT,
                ty: wgpu::BindingType::Buffer {
                    ty: wgpu::BufferBindingType::Uniform,
                    has_dynamic_offset: false,
                    min_binding_size: None,
                },
                count: None,
            });
        }
        for (i, _) in sampled_textures.iter().enumerate() {
            let base = 2 + i as u32 * 2;
            entries.push(wgpu::BindGroupLayoutEntry {
                binding: base,
                visibility: wgpu::ShaderStages::FRAGMENT,
                ty: wgpu::BindingType::Texture {
                    sample_type: wgpu::TextureSampleType::Float { filterable: true },
                    view_dimension: wgpu::TextureViewDimension::D2,
                    multisampled: false,
                },
                count: None,
            });
            entries.push(wgpu::BindGroupLayoutEntry {
                binding: base + 1,
                visibility: wgpu::ShaderStages::FRAGMENT,
                ty: wgpu::BindingType::Sampler(wgpu::SamplerBindingType::Filtering),
                count: None,
            });
        }
        let bgl = ctx
            .device
            .create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
                label: None,
                entries: &entries,
            });

        let common_buf = ctx
            .device
            .create_buffer_init(&wgpu::util::BufferInitDescriptor {
                label: Some("common ubo"),
                contents: common_ubo_bytes,
                usage: wgpu::BufferUsages::UNIFORM,
            });
        let inputs_buf = inputs_ubo_bytes.map(|bytes| {
            ctx.device
                .create_buffer_init(&wgpu::util::BufferInitDescriptor {
                    label: Some("inputs ubo"),
                    contents: bytes,
                    usage: wgpu::BufferUsages::UNIFORM,
                })
        });

        let mut bg_entries = vec![wgpu::BindGroupEntry {
            binding: 0,
            resource: common_buf.as_entire_binding(),
        }];
        if let Some(buf) = &inputs_buf {
            bg_entries.push(wgpu::BindGroupEntry {
                binding: 1,
                resource: buf.as_entire_binding(),
            });
        }
        for (i, (view, sampler)) in sampled_textures.iter().enumerate() {
            let base = 2 + i as u32 * 2;
            bg_entries.push(wgpu::BindGroupEntry {
                binding: base,
                resource: wgpu::BindingResource::TextureView(view),
            });
            bg_entries.push(wgpu::BindGroupEntry {
                binding: base + 1,
                resource: wgpu::BindingResource::Sampler(sampler),
            });
        }
        let bind_group = ctx.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &bgl,
            entries: &bg_entries,
        });

        let pipeline_layout = ctx
            .device
            .create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
                label: None,
                bind_group_layouts: &[&bgl],
                push_constant_ranges: &[],
            });
        let pipeline = ctx
            .device
            .create_render_pipeline(&wgpu::RenderPipelineDescriptor {
                label: Some("hyst-render glsl pipeline"),
                layout: Some(&pipeline_layout),
                vertex: wgpu::VertexState {
                    module: &vs_module,
                    entry_point: "main",
                    buffers: &[],
                    compilation_options: Default::default(),
                },
                fragment: Some(wgpu::FragmentState {
                    module: &fs_module,
                    entry_point: "main",
                    targets: &[Some(wgpu::ColorTargetState {
                        format: wgpu::TextureFormat::Rgba8Unorm,
                        blend: None,
                        write_mask: wgpu::ColorWrites::ALL,
                    })],
                    compilation_options: Default::default(),
                }),
                primitive: wgpu::PrimitiveState::default(),
                depth_stencil: None,
                multisample: wgpu::MultisampleState::default(),
                multiview: None,
                cache: None,
            });

        let mut encoder = ctx
            .device
            .create_command_encoder(&wgpu::CommandEncoderDescriptor { label: None });
        {
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: None,
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &self.view,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(wgpu::Color::BLACK),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                depth_stencil_attachment: None,
                timestamp_writes: None,
                occlusion_query_set: None,
            });
            pass.set_pipeline(&pipeline);
            pass.set_bind_group(0, &bind_group, &[]);
            pass.draw(0..3, 0..1);
        }
        ctx.queue.submit(std::iter::once(encoder.finish()));
        Ok(())
    }
}

/// Fullscreen-triangle vertex shader, GLSL flavor (naga's Vulkan-only GLSL
/// frontend doesn't accept `gl_VertexID`, only `gl_VertexIndex` — verified
/// against a real naga build, see `isf_translate` module doc). Functionally
/// identical to `FULLSCREEN_VERTEX_WGSL` above, just for the GLSL pipeline
/// path (`render_glsl_fragment_shader`), which cannot mix WGSL and GLSL
/// modules in one pipeline.
// `vUv.y` is deliberately `0.5 - pos.y*0.5`, not `pos.y*0.5+0.5`: wgpu (like
// D3D/Vulkan) addresses row 0 of a texture at the TOP (NDC y=+1 maps to
// viewport row 0), but `texture()` sampling addresses v=0 at that same top
// row too — so a naive `pos*0.5+0.5` vUv, while internally consistent for a
// single pass writing-and-reading its own fragCoord, silently vertically
// flips relative to any LATER pass sampling this pass's output texture by
// UV. Verified the hard way: a two-pass test where pass A wrote
// `vec4(step(0.5,uv.x), step(0.5,uv.y), ...)` and pass B just resampled it
// showed pass B's green channel constant instead of tracking uv.y, i.e.
// exactly a Y-flip bug. This flipped formula makes `vUv` mean the same
// thing whether a shader is computing a fragment's own screen position or
// sampling another pass's texture by that same coordinate.
const FULLSCREEN_VERTEX_GLSL: &str = r#"
#version 450 core
layout(location = 0) out vec2 vUv;
void main() {
  vec2 pos[3] = vec2[3](
    vec2(-1.0, -1.0),
    vec2(3.0, -1.0),
    vec2(-1.0, 3.0)
  );
  vUv = vec2(pos[gl_VertexIndex].x * 0.5 + 0.5, 0.5 - pos[gl_VertexIndex].y * 0.5);
  gl_Position = vec4(pos[gl_VertexIndex], 0.0, 1.0);
}
"#;

#[cfg(test)]
mod tests {
    use super::*;

    /// The one real smoke test: request a real adapter/device on whatever
    /// GPU this machine has, render a horizontal red gradient (a trivial,
    /// deterministic fragment shader) to a 64x64 offscreen target, read it
    /// back, and confirm the gradient actually happened — left edge near 0
    /// red, right edge near max red. This is the "wgpu setup" done-when
    /// bar for this session's slice: real pixels out of a real GPU, not
    /// just "the crate compiles."
    #[test]
    fn renders_a_gradient_and_reads_it_back_from_a_real_gpu() {
        let ctx = match GpuContext::new_blocking() {
            Ok(ctx) => ctx,
            Err(GpuError::NoAdapter) => {
                eprintln!("skipping: no GPU adapter available in this environment");
                return;
            }
            Err(e) => panic!("unexpected GPU setup failure: {e}"),
        };

        let target = OffscreenTarget::new(&ctx, 64, 64);
        let fragment_wgsl = r#"
@fragment
fn fs_main(@builtin(position) frag_coord: vec4<f32>) -> @location(0) vec4<f32> {
    let r = frag_coord.x / 64.0;
    return vec4<f32>(r, 0.0, 0.0, 1.0);
}
"#;
        target
            .render_fragment_shader(&ctx, fragment_wgsl)
            .expect("render should succeed");
        let pixels = target.read_pixels(&ctx).expect("readback should succeed");

        assert_eq!(pixels.len(), 64 * 64 * 4);

        let pixel_at = |x: u32, y: u32| -> [u8; 4] {
            let i = ((y * 64 + x) * 4) as usize;
            [pixels[i], pixels[i + 1], pixels[i + 2], pixels[i + 3]]
        };

        let left = pixel_at(0, 32);
        let right = pixel_at(63, 32);
        assert!(
            left[0] < 20,
            "left edge should be near-black red channel, got {}",
            left[0]
        );
        assert!(
            right[0] > 235,
            "right edge should be near-max red channel, got {}",
            right[0]
        );
        assert_eq!(left[1], 0);
        assert_eq!(left[2], 0);
        assert_eq!(left[3], 255);

        // Monotonic across the middle row — confirms a real gradient, not a
        // uniform fill that happened to average out.
        let mid_left = pixel_at(10, 32)[0];
        let mid_right = pixel_at(50, 32)[0];
        assert!(mid_right > mid_left);
    }
}
