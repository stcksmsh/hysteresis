//! Beam — GPU-instanced-quad line rasterization, ported from
//! `scenes/julia/shaders/beam.vert.glsl`/`beam.frag.glsl`. Real hardware
//! line drawing (each segment expanded to a camera-facing quad in the
//! vertex shader, one instance per segment) — **not** a per-pixel loop,
//! which the TS original's own comments record as costed out and rejected.
//!
//! Unlike the fullscreen passes, this needs real vertex buffers (a constant
//! per-vertex quad-corner buffer + a per-instance P0/P1 buffer), so it
//! doesn't go through `OffscreenTarget::render_glsl_fragment_shader` (fixed
//! to the fullscreen triangle) — its own small pipeline, built fresh per
//! call like every other pass here (see `passes` module doc on why that's
//! an accepted cost right now).

use wgpu::util::DeviceExt;

use crate::gpu::{GpuContext, GpuError, OffscreenTarget};

/// One line segment in NDC (-1..1) space.
#[derive(Clone, Copy, Debug, bytemuck::Pod, bytemuck::Zeroable)]
#[repr(C)]
pub struct Segment {
    pub p0: [f32; 2],
    pub p1: [f32; 2],
}

pub fn render_beam(
    ctx: &GpuContext,
    output: &OffscreenTarget,
    segments: &[Segment],
    color: [f32; 3],
    intensity: f32,
    aspect: f32,
    half_width: f32,
) -> Result<(), GpuError> {
    if segments.is_empty() {
        return Ok(());
    }
    let vs_module = ctx
        .device
        .create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("beam vs"),
            source: wgpu::ShaderSource::Glsl {
                shader: BEAM_VERT_GLSL.into(),
                stage: wgpu::naga::ShaderStage::Vertex,
                defines: Default::default(),
            },
        });
    let fs_module = ctx
        .device
        .create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("beam fs"),
            source: wgpu::ShaderSource::Glsl {
                shader: BEAM_FRAG_GLSL.into(),
                stage: wgpu::naga::ShaderStage::Fragment,
                defines: Default::default(),
            },
        });

    let bgl = ctx
        .device
        .create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: None,
            entries: &[
                wgpu::BindGroupLayoutEntry {
                    binding: 0,
                    visibility: wgpu::ShaderStages::VERTEX,
                    ty: wgpu::BindingType::Buffer {
                        ty: wgpu::BufferBindingType::Uniform,
                        has_dynamic_offset: false,
                        min_binding_size: None,
                    },
                    count: None,
                },
                wgpu::BindGroupLayoutEntry {
                    binding: 1,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Buffer {
                        ty: wgpu::BufferBindingType::Uniform,
                        has_dynamic_offset: false,
                        min_binding_size: None,
                    },
                    count: None,
                },
            ],
        });
    let vertex_params: [f32; 4] = [aspect, half_width, 0.0, 0.0];
    let fragment_params: [f32; 4] = [color[0], color[1], color[2], intensity];
    let vbuf = ctx
        .device
        .create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("beam vertex params"),
            contents: bytemuck::bytes_of(&vertex_params),
            usage: wgpu::BufferUsages::UNIFORM,
        });
    let fbuf = ctx
        .device
        .create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("beam fragment params"),
            contents: bytemuck::bytes_of(&fragment_params),
            usage: wgpu::BufferUsages::UNIFORM,
        });
    let bind_group = ctx.device.create_bind_group(&wgpu::BindGroupDescriptor {
        label: None,
        layout: &bgl,
        entries: &[
            wgpu::BindGroupEntry {
                binding: 0,
                resource: vbuf.as_entire_binding(),
            },
            wgpu::BindGroupEntry {
                binding: 1,
                resource: fbuf.as_entire_binding(),
            },
        ],
    });

    // Constant per-vertex quad: x in -0.5..0.5 across the segment, y in 0..1 along it.
    const CORNERS: [[f32; 2]; 6] = [
        [-0.5, 0.0],
        [0.5, 0.0],
        [-0.5, 1.0],
        [-0.5, 1.0],
        [0.5, 0.0],
        [0.5, 1.0],
    ];
    let corner_buf = ctx
        .device
        .create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("beam corners"),
            contents: bytemuck::cast_slice(&CORNERS),
            usage: wgpu::BufferUsages::VERTEX,
        });
    let instance_buf = ctx
        .device
        .create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("beam segments"),
            contents: bytemuck::cast_slice(segments),
            usage: wgpu::BufferUsages::VERTEX,
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
            label: Some("beam pipeline"),
            layout: Some(&pipeline_layout),
            vertex: wgpu::VertexState {
                module: &vs_module,
                entry_point: "main",
                buffers: &[
                    wgpu::VertexBufferLayout {
                        array_stride: 8,
                        step_mode: wgpu::VertexStepMode::Vertex,
                        attributes: &[wgpu::VertexAttribute {
                            format: wgpu::VertexFormat::Float32x2,
                            offset: 0,
                            shader_location: 0,
                        }],
                    },
                    wgpu::VertexBufferLayout {
                        array_stride: 16,
                        step_mode: wgpu::VertexStepMode::Instance,
                        attributes: &[
                            wgpu::VertexAttribute {
                                format: wgpu::VertexFormat::Float32x2,
                                offset: 0,
                                shader_location: 1,
                            },
                            wgpu::VertexAttribute {
                                format: wgpu::VertexFormat::Float32x2,
                                offset: 8,
                                shader_location: 2,
                            },
                        ],
                    },
                ],
                compilation_options: Default::default(),
            },
            fragment: Some(wgpu::FragmentState {
                module: &fs_module,
                entry_point: "main",
                targets: &[Some(wgpu::ColorTargetState {
                    format: wgpu::TextureFormat::Rgba8Unorm,
                    blend: Some(wgpu::BlendState::ALPHA_BLENDING),
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
                view: output.view(),
                resolve_target: None,
                ops: wgpu::Operations {
                    load: wgpu::LoadOp::Load,
                    store: wgpu::StoreOp::Store,
                },
            })],
            depth_stencil_attachment: None,
            timestamp_writes: None,
            occlusion_query_set: None,
        });
        pass.set_pipeline(&pipeline);
        pass.set_bind_group(0, &bind_group, &[]);
        pass.set_vertex_buffer(0, corner_buf.slice(..));
        pass.set_vertex_buffer(1, instance_buf.slice(..));
        pass.draw(0..6, 0..segments.len() as u32);
    }
    ctx.queue.submit(std::iter::once(encoder.finish()));
    Ok(())
}

/// Draws a soft round disc at every point in `points` — fills the notch/gap
/// `render_beam`'s flat-capped segment quads leave at any joint that isn't
/// perfectly straight, so a polyline reads as one continuous rounded tube
/// (a "neon light") instead of visibly faceted straight segments meeting at
/// hard corners. Call after `render_beam` for the same polyline, same
/// `color`/`intensity`/`half_width` (`radius` here) so the two blend into
/// one consistent line.
pub fn render_beam_joints(
    ctx: &GpuContext,
    output: &OffscreenTarget,
    points: &[[f32; 2]],
    color: [f32; 3],
    intensity: f32,
    aspect: f32,
    radius: f32,
) -> Result<(), GpuError> {
    if points.is_empty() {
        return Ok(());
    }
    let vs_module = ctx
        .device
        .create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("beam joint vs"),
            source: wgpu::ShaderSource::Glsl {
                shader: BEAM_JOINT_VERT_GLSL.into(),
                stage: wgpu::naga::ShaderStage::Vertex,
                defines: Default::default(),
            },
        });
    let fs_module = ctx
        .device
        .create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("beam joint fs"),
            source: wgpu::ShaderSource::Glsl {
                shader: BEAM_JOINT_FRAG_GLSL.into(),
                stage: wgpu::naga::ShaderStage::Fragment,
                defines: Default::default(),
            },
        });

    let bgl = ctx
        .device
        .create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: None,
            entries: &[
                wgpu::BindGroupLayoutEntry {
                    binding: 0,
                    visibility: wgpu::ShaderStages::VERTEX,
                    ty: wgpu::BindingType::Buffer {
                        ty: wgpu::BufferBindingType::Uniform,
                        has_dynamic_offset: false,
                        min_binding_size: None,
                    },
                    count: None,
                },
                wgpu::BindGroupLayoutEntry {
                    binding: 1,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Buffer {
                        ty: wgpu::BufferBindingType::Uniform,
                        has_dynamic_offset: false,
                        min_binding_size: None,
                    },
                    count: None,
                },
            ],
        });
    let vertex_params: [f32; 4] = [aspect, radius, 0.0, 0.0];
    let fragment_params: [f32; 4] = [color[0], color[1], color[2], intensity];
    let vbuf = ctx
        .device
        .create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("beam joint vertex params"),
            contents: bytemuck::bytes_of(&vertex_params),
            usage: wgpu::BufferUsages::UNIFORM,
        });
    let fbuf = ctx
        .device
        .create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("beam joint fragment params"),
            contents: bytemuck::bytes_of(&fragment_params),
            usage: wgpu::BufferUsages::UNIFORM,
        });
    let bind_group = ctx.device.create_bind_group(&wgpu::BindGroupDescriptor {
        label: None,
        layout: &bgl,
        entries: &[
            wgpu::BindGroupEntry {
                binding: 0,
                resource: vbuf.as_entire_binding(),
            },
            wgpu::BindGroupEntry {
                binding: 1,
                resource: fbuf.as_entire_binding(),
            },
        ],
    });

    // A unit square in local space; the fragment shader turns it into a
    // circle via a radial falloff, so this is the same 6-vertex-per-instance
    // shape as render_beam's quad, just centered/local rather than
    // segment-aligned.
    const CORNERS: [[f32; 2]; 6] = [
        [-1.0, -1.0],
        [1.0, -1.0],
        [-1.0, 1.0],
        [-1.0, 1.0],
        [1.0, -1.0],
        [1.0, 1.0],
    ];
    let corner_buf = ctx
        .device
        .create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("beam joint corners"),
            contents: bytemuck::cast_slice(&CORNERS),
            usage: wgpu::BufferUsages::VERTEX,
        });
    let instance_buf = ctx
        .device
        .create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("beam joint centers"),
            contents: bytemuck::cast_slice(points),
            usage: wgpu::BufferUsages::VERTEX,
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
            label: Some("beam joint pipeline"),
            layout: Some(&pipeline_layout),
            vertex: wgpu::VertexState {
                module: &vs_module,
                entry_point: "main",
                buffers: &[
                    wgpu::VertexBufferLayout {
                        array_stride: 8,
                        step_mode: wgpu::VertexStepMode::Vertex,
                        attributes: &[wgpu::VertexAttribute {
                            format: wgpu::VertexFormat::Float32x2,
                            offset: 0,
                            shader_location: 0,
                        }],
                    },
                    wgpu::VertexBufferLayout {
                        array_stride: 8,
                        step_mode: wgpu::VertexStepMode::Instance,
                        attributes: &[wgpu::VertexAttribute {
                            format: wgpu::VertexFormat::Float32x2,
                            offset: 0,
                            shader_location: 1,
                        }],
                    },
                ],
                compilation_options: Default::default(),
            },
            fragment: Some(wgpu::FragmentState {
                module: &fs_module,
                entry_point: "main",
                targets: &[Some(wgpu::ColorTargetState {
                    format: wgpu::TextureFormat::Rgba8Unorm,
                    // Standard alpha-over blending here compounds every time a
                    // disc overlaps an already-lit segment (which is almost
                    // everywhere, for a dense near-straight polyline) — each
                    // vertex reads as a brighter bump on top of the line,
                    // giving a visible beaded/pearl-necklace look instead of a
                    // smooth tube. Max blending fixes this at the source: a
                    // disc only RAISES a pixel that's currently darker (the
                    // notch a flat-capped join leaves), never re-brightens a
                    // pixel the segment already covers at equal or higher
                    // value.
                    blend: Some(wgpu::BlendState {
                        color: wgpu::BlendComponent {
                            src_factor: wgpu::BlendFactor::One,
                            dst_factor: wgpu::BlendFactor::One,
                            operation: wgpu::BlendOperation::Max,
                        },
                        alpha: wgpu::BlendComponent {
                            src_factor: wgpu::BlendFactor::One,
                            dst_factor: wgpu::BlendFactor::One,
                            operation: wgpu::BlendOperation::Max,
                        },
                    }),
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
                view: output.view(),
                resolve_target: None,
                ops: wgpu::Operations {
                    load: wgpu::LoadOp::Load,
                    store: wgpu::StoreOp::Store,
                },
            })],
            depth_stencil_attachment: None,
            timestamp_writes: None,
            occlusion_query_set: None,
        });
        pass.set_pipeline(&pipeline);
        pass.set_bind_group(0, &bind_group, &[]);
        pass.set_vertex_buffer(0, corner_buf.slice(..));
        pass.set_vertex_buffer(1, instance_buf.slice(..));
        pass.draw(0..6, 0..points.len() as u32);
    }
    ctx.queue.submit(std::iter::once(encoder.finish()));
    Ok(())
}

const BEAM_JOINT_VERT_GLSL: &str = r#"
#version 450 core
layout(location = 0) in vec2 aCorner;
layout(location = 1) in vec2 aCenter;
layout(std140, set = 0, binding = 0) uniform Vertex { vec4 slot0; };
layout(location = 0) out vec2 vLocal;
void main() {
  float aspect = slot0.x;
  float radius = slot0.y;
  vec2 offset = aCorner * radius;
  offset.x /= aspect;
  vLocal = aCorner;
  gl_Position = vec4(aCenter + offset, 0.0, 1.0);
}
"#;

const BEAM_JOINT_FRAG_GLSL: &str = r#"
#version 450 core
layout(location = 0) in vec2 vLocal;
layout(location = 0) out vec4 fragColor;
layout(std140, set = 0, binding = 1) uniform Fragment { vec4 slot0; };
void main() {
  vec3 color = slot0.xyz;
  float intensity = slot0.w;
  float d = length(vLocal);
  // Was smoothstep(1.0, 0.75, d) — solid core out to 75% radius then a
  // sharp cutoff, a much harder edge than the segment's falloff (below:
  // fades linearly-ish across its ENTIRE half-width). That mismatch is
  // exactly what made joints read as separate beads/pearls instead of
  // blending into the line — match the segment's own profile exactly.
  float falloff = smoothstep(1.0, 0.0, d);
  fragColor = vec4(color * intensity * falloff, falloff);
}
"#;

const BEAM_VERT_GLSL: &str = r#"
#version 450 core
layout(location = 0) in vec2 aCorner;
layout(location = 1) in vec2 aP0;
layout(location = 2) in vec2 aP1;
layout(std140, set = 0, binding = 0) uniform Vertex { vec4 slot0; };
layout(location = 0) out float vAcross;
void main() {
  float aspect = slot0.x;
  float halfWidth = slot0.y;
  vec2 dir = aP1 - aP0;
  float len = max(length(dir), 1e-5);
  vec2 unit = dir / len;
  vec2 normal = vec2(-unit.y, unit.x);
  vec2 base = mix(aP0, aP1, aCorner.y);
  vec2 offset = normal * aCorner.x * halfWidth;
  offset.x /= aspect;
  vAcross = aCorner.x;
  gl_Position = vec4(base + offset, 0.0, 1.0);
}
"#;

const BEAM_FRAG_GLSL: &str = r#"
#version 450 core
layout(location = 0) in float vAcross;
layout(location = 0) out vec4 fragColor;
layout(std140, set = 0, binding = 1) uniform Fragment { vec4 slot0; };
void main() {
  vec3 color = slot0.xyz;
  float intensity = slot0.w;
  float d = abs(vAcross) * 2.0;
  float falloff = smoothstep(1.0, 0.0, d);
  fragColor = vec4(color * intensity * falloff, falloff);
}
"#;

#[cfg(test)]
mod tests {
    use super::*;

    /// Bites: rasterizes non-background pixels along the exact expected
    /// coordinates of a known 2-point horizontal line, and nowhere else
    /// (checked well off the line's band, not just "some pixels changed").
    #[test]
    fn rasterizes_a_known_segment_and_only_there() {
        let ctx = match GpuContext::new_blocking() {
            Ok(c) => c,
            Err(_) => return,
        };
        let target = OffscreenTarget::new(&ctx, 128, 128);
        target.render_glsl_fragment_shader(&ctx, "#version 450 core\nlayout(location=0) out vec4 fragColor;\nvoid main(){fragColor=vec4(0.0,0.0,0.0,1.0);}", &[0u8; 32], None, &[]).unwrap();

        // Horizontal segment across the vertical center, in NDC.
        let seg = Segment {
            p0: [-0.8, 0.0],
            p1: [0.8, 0.0],
        };
        render_beam(&ctx, &target, &[seg], [1.0, 1.0, 1.0], 2.0, 1.0, 0.05).unwrap();
        let pixels = target.read_pixels(&ctx).unwrap();
        let px = |x: u32, y: u32| pixels[((y * 128 + x) * 4) as usize];

        // Center row (NDC y=0 maps to pixel row 64) along the segment's span should be lit.
        assert!(
            px(64, 64) > 100,
            "expected the beam lit at its center, got {}",
            px(64, 64)
        );
        assert!(
            px(20, 64) > 100,
            "expected the beam lit along its span, got {}",
            px(20, 64)
        );
        // Far above/below the line's half-width band: must stay background.
        assert_eq!(
            px(64, 10),
            0,
            "expected background far from the line, got {}",
            px(64, 10)
        );
        assert_eq!(
            px(64, 118),
            0,
            "expected background far from the line, got {}",
            px(64, 118)
        );
        // Off the segment's horizontal span entirely (x beyond p1) but same y: falls off the quad, background.
        assert_eq!(
            px(127, 64),
            0,
            "expected background past the segment's endpoint, got {}",
            px(127, 64)
        );
    }

    /// Bites: proves the joint disc fills exactly the notch two angled
    /// segments' flat end-caps leave — a point straight off to one side of
    /// the shared vertex, past where either segment's quad reaches, but
    /// within the joint's own radius, must be lit only once the joint is
    /// drawn.
    #[test]
    fn joint_disc_fills_the_notch_two_angled_segments_leave() {
        let ctx = match GpuContext::new_blocking() {
            Ok(c) => c,
            Err(_) => return,
        };
        let target = OffscreenTarget::new(&ctx, 128, 128);
        target.render_glsl_fragment_shader(&ctx, "#version 450 core\nlayout(location=0) out vec4 fragColor;\nvoid main(){fragColor=vec4(0.0,0.0,0.0,1.0);}", &[0u8; 32], None, &[]).unwrap();

        // A sharp corner at the origin: one segment approaches from the
        // left, the other leaves upward — their flat end-caps leave the
        // notch directly to the lower-right of the vertex uncovered.
        let seg_a = Segment {
            p0: [-0.5, 0.0],
            p1: [0.0, 0.0],
        }; // horizontal, ends at origin
        let seg_b = Segment {
            p0: [0.0, 0.0],
            p1: [0.0, 0.5],
        }; // vertical, starts at origin
        let half_width = 0.1;
        // NDC (0.05, -0.05): within the joint's radius (dist ~0.0707 < 0.1)
        // from the shared vertex, but outside BOTH segments' quads — seg_a's
        // quad only spans x in [-0.5, 0], seg_b's only spans y in [0, 0.5].
        // wgpu clip space is Y-up; row 0 of the read-back buffer is the top
        // of the image, so pixel_row = (0.5 - ndc_y*0.5) * height.
        // Closer to the vertex than the joint's own radius/2 — the softer
        // falloff (matching the segment's profile) fades out gradually
        // across the whole radius, so a point right at ~70% of the radius
        // reads quite dim (falloff is applied twice, once in fragColor.rgb
        // and once via alpha blending — same as the segment shader does);
        // pick a point close enough to the vertex to read clearly lit.
        let ndc = (0.03f32, -0.03f32);
        let notch_x = ((ndc.0 * 0.5 + 0.5) * 128.0) as u32;
        let notch_y = ((0.5 - ndc.1 * 0.5) * 128.0) as u32;

        render_beam(
            &ctx,
            &target,
            &[seg_a, seg_b],
            [1.0, 1.0, 1.0],
            2.0,
            1.0,
            half_width,
        )
        .unwrap();
        let pixels = target.read_pixels(&ctx).unwrap();
        let px = |x: u32, y: u32| pixels[((y * 128 + x) * 4) as usize];
        assert_eq!(
            px(notch_x, notch_y),
            0,
            "sanity: notch should be unlit by the segments alone"
        );

        render_beam_joints(
            &ctx,
            &target,
            &[seg_a.p0, seg_a.p1, seg_b.p1],
            [1.0, 1.0, 1.0],
            2.0,
            1.0,
            half_width,
        )
        .unwrap();
        let pixels = target.read_pixels(&ctx).unwrap();
        let px = |x: u32, y: u32| pixels[((y * 128 + x) * 4) as usize];
        assert!(
            px(notch_x, notch_y) > 50,
            "expected the joint disc to fill the notch, got {}",
            px(notch_x, notch_y)
        );
    }
}
