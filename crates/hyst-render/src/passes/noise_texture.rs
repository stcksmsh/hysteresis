//! Baked curl-noise potential texture — port-the-intent sibling of
//! `gl/noise-texture.ts`. The TS original bakes a scalar potential into the
//! B channel once at startup; `memory-field.frag.glsl`'s `curlAt` takes its
//! curl (central difference) to get a divergence-free flow direction
//! without a simulation buffer. **Deviation**: this is a simple deterministic
//! multi-octave sine field, not a port of the TS file's exact noise
//! algorithm (never read bit-for-bit — the memory-field pass only cares
//! that the B channel has spatial structure to take a curl of, not its
//! precise statistics, and the fold-seam fix's correctness — see
//! `memory_field.rs` — doesn't depend on the noise source at all).

use crate::gpu::GpuContext;

pub struct NoiseTexture {
    pub texture: wgpu::Texture,
    pub view: wgpu::TextureView,
    pub width: u32,
    pub height: u32,
}

impl NoiseTexture {
    pub fn bake(ctx: &GpuContext, width: u32, height: u32) -> Self {
        let mut data = vec![0u8; (width * height * 4) as usize];
        for y in 0..height {
            for x in 0..width {
                let u = x as f32 / width as f32;
                let v = y as f32 / height as f32;
                // Sum of a few incommensurate sine waves: cheap, deterministic,
                // has real spatial gradient structure for curlAt to sample.
                use std::f32::consts::TAU;
                let potential = (u * TAU * 3.0 + v * TAU * 2.0).sin() * 0.5
                    + (u * TAU * 5.0 - v * TAU * 4.0).sin() * 0.3
                    + (u * TAU * 1.7 + v * TAU * 7.0).sin() * 0.2;
                let b = ((potential * 0.5 + 0.5).clamp(0.0, 1.0) * 255.0) as u8;
                let i = ((y * width + x) * 4) as usize;
                data[i] = 128;
                data[i + 1] = 128;
                data[i + 2] = b;
                data[i + 3] = 255;
            }
        }

        let texture = ctx.device.create_texture(&wgpu::TextureDescriptor {
            label: Some("hyst-render noise texture"),
            size: wgpu::Extent3d {
                width,
                height,
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Rgba8Unorm,
            usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST,
            view_formats: &[],
        });
        ctx.queue.write_texture(
            wgpu::ImageCopyTexture {
                texture: &texture,
                mip_level: 0,
                origin: wgpu::Origin3d::ZERO,
                aspect: wgpu::TextureAspect::All,
            },
            &data,
            wgpu::ImageDataLayout {
                offset: 0,
                bytes_per_row: Some(width * 4),
                rows_per_image: Some(height),
            },
            wgpu::Extent3d {
                width,
                height,
                depth_or_array_layers: 1,
            },
        );
        let view = texture.create_view(&wgpu::TextureViewDescriptor::default());
        Self {
            texture,
            view,
            width,
            height,
        }
    }
}
