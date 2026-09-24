//! ISF-flavored GLSL body -> real GLSL `wgpu`/`naga` can compile.
//!
//! Ported in spirit from `src/isf/translate-isf-glsl.ts` (textual
//! substitution, not a real parser — ISF's own spec describes exactly this
//! as how a host bridges the two dialects). Two differences from the TS
//! original, forced by the target: that one emits GLSL ES 300 (WebGL2);
//! this emits GLSL 450 core, because `wgpu`'s `naga` GLSL frontend only
//! understands Vulkan-flavored GLSL (440-460), confirmed by reading
//! `naga::front::glsl`'s own module doc before choosing this approach over
//! hand-writing a GLSL->WGSL AST translator (see `crates/hyst-render/README.md`
//! "GLSL translation approach"). And: Vulkan GLSL has no default/loose
//! uniform block (`uniform float TIME;` alone is a hard compile error —
//! "uniform/buffer blocks require layout(binding=X)", verified directly
//! against a real naga build before writing this) so every scalar/vector
//! input is packed into one `binding=1` UBO of `vec4` slots instead of one
//! uniform each, and unpacked into locals with the input's original name
//! injected at the top of `main()` (the same place `isf_FragNormCoord`
//! already has to be injected, since GLSL forbids non-constant global
//! initializers) rather than declared at file scope.

use crate::hyst_format::{IsfDocument, IsfInput, IsfPass};

pub struct TranslatedShader {
    pub source: String,
    /// One entry per packed `vec4` slot in the `Inputs` UBO (binding=1),
    /// same order as `doc.inputs` with `Resource` entries skipped (those
    /// bind directly, never through a uniform — same rule as the TS
    /// original). Empty when the document declares no such inputs, in
    /// which case the `Inputs` block itself is omitted from `source`.
    pub input_slots: Vec<InputSlot>,
    /// `doc.passes` targets (excluding `""`, the final output) that became
    /// `sampler2D` uniforms, in binding order starting at 2.
    pub pass_sampler_names: Vec<String>,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum InputSlot {
    Float,
    Bool,
    Long,
    Point2d,
    Color,
}

pub fn translate_isf_glsl(doc: &IsfDocument) -> Result<TranslatedShader, String> {
    let mut body = doc.body.replace("gl_FragColor", "fragColor");
    body = body.replace("texture2D(", "texture(");
    body = body.replace("textureCube(", "texture(");

    let insert_at = find_main_open_brace(&body).ok_or("ISF shader body has no main() function")?;

    let mut prelude = String::from("\n  vec2 isf_FragNormCoord = gl_FragCoord.xy / RENDERSIZE;\n");
    let mut input_slots = Vec::new();
    for input in doc
        .inputs
        .iter()
        .filter(|i| !matches!(i, IsfInput::Resource { .. }))
    {
        let (glsl_ty, extract, slot) = input_unpack(input, input_slots.len());
        prelude.push_str(&format!("  {glsl_ty} {} = {extract};\n", input.name()));
        input_slots.push(slot);
    }
    body.insert_str(insert_at, &prelude);

    let mut header = String::from(
        "#version 450 core\n\
         layout(location = 0) out vec4 fragColor;\n\
         layout(std140, set = 0, binding = 0) uniform Common {\n\
         \x20 float TIME;\n\
         \x20 float TIMEDELTA;\n\
         \x20 vec2 RENDERSIZE;\n\
         \x20 int PASSINDEX;\n\
         \x20 int FRAMEINDEX;\n\
         \x20 vec4 DATE;\n\
         };\n",
    );
    if !input_slots.is_empty() {
        header.push_str(&format!(
            "layout(std140, set = 0, binding = 1) uniform Inputs {{ vec4 slot[{}]; }};\n",
            input_slots.len()
        ));
    }

    let mut pass_sampler_names = Vec::new();
    for pass in &doc.passes {
        let target = match pass {
            IsfPass::Fullscreen { target } => target,
            IsfPass::LineTrace { target, .. } => target,
            IsfPass::ScriptTexture { target, .. } => target,
        };
        if target.is_empty() || pass_sampler_names.contains(target) {
            continue;
        }
        let binding = 2 + pass_sampler_names.len();
        header.push_str(&format!(
            "layout(set = 0, binding = {binding}) uniform sampler2D {target};\n"
        ));
        pass_sampler_names.push(target.clone());
    }

    Ok(TranslatedShader {
        source: format!("{header}\n{body}"),
        input_slots,
        pass_sampler_names,
    })
}

fn input_unpack(input: &IsfInput, idx: usize) -> (&'static str, String, InputSlot) {
    match input {
        IsfInput::Float { .. } | IsfInput::HysteresisSignal { .. } => {
            ("float", format!("slot[{idx}].x"), InputSlot::Float)
        }
        IsfInput::Bool { .. } => ("bool", format!("(slot[{idx}].x != 0.0)"), InputSlot::Bool),
        IsfInput::Long { .. } => ("int", format!("int(slot[{idx}].x)"), InputSlot::Long),
        IsfInput::Point2d { .. } => ("vec2", format!("slot[{idx}].xy"), InputSlot::Point2d),
        IsfInput::Color { .. } => ("vec4", format!("slot[{idx}]"), InputSlot::Color),
        IsfInput::ScriptOutput { kind, .. } => match kind {
            crate::hyst_format::IsfScriptOutputKind::Float => {
                ("float", format!("slot[{idx}].x"), InputSlot::Float)
            }
            crate::hyst_format::IsfScriptOutputKind::Bool => {
                ("bool", format!("(slot[{idx}].x != 0.0)"), InputSlot::Bool)
            }
            crate::hyst_format::IsfScriptOutputKind::Point2d => {
                ("vec2", format!("slot[{idx}].xy"), InputSlot::Point2d)
            }
            crate::hyst_format::IsfScriptOutputKind::Color => {
                ("vec4", format!("slot[{idx}]"), InputSlot::Color)
            }
        },
        IsfInput::Resource { .. } => unreachable!("filtered out by caller"),
    }
}

/// Finds the byte offset right after `void main ( ) {` (whitespace-tolerant,
/// same as the TS original's regex), i.e. where to inject the prelude.
fn find_main_open_brace(body: &str) -> Option<usize> {
    let start = body.find("main")?;
    // Must be preceded by "void" (skipping whitespace) — cheap enough not to
    // bother with a real tokenizer for a single-pass textual translator.
    let before = body[..start].trim_end();
    if !before.ends_with("void") {
        return None;
    }
    let rest = &body[start + 4..];
    let paren_open = rest.find('(')?;
    let paren_close = rest[paren_open..].find(')')? + paren_open;
    let brace = rest[paren_close..].find('{')? + paren_close;
    Some(start + 4 + brace + 1)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::gpu::{GpuContext, OffscreenTarget};
    use crate::hyst_format::parse_hyst;

    const FIXTURE: &str = r#"/*{
  "DESCRIPTION": "test",
  "CREDIT": "test",
  "CATEGORIES": [],
  "INPUTS": [
    { "NAME": "brightness", "TYPE": "float", "DEFAULT": 1.0, "MIN": 0.0, "MAX": 1.0 }
  ]
}*/

void main() {
  vec4 c = vec4(isf_FragNormCoord, 0.0, 1.0);
  gl_FragColor = c * brightness;
}
"#;

    #[test]
    fn translates_and_renders_a_real_isf_fixture_on_the_real_gpu() {
        let doc = parse_hyst(FIXTURE).expect("fixture should parse");
        let translated = translate_isf_glsl(&doc).expect("translation should succeed");

        assert!(translated.source.contains("fragColor"));
        assert!(!translated.source.contains("gl_FragColor"));
        assert!(translated.source.contains("float brightness = slot[0].x;"));

        let ctx = match GpuContext::new_blocking() {
            Ok(c) => c,
            Err(_) => {
                eprintln!("skipping: no GPU adapter available");
                return;
            }
        };

        // Common UBO: TIME, TIMEDELTA, RENDERSIZE(vec2), PASSINDEX, FRAMEINDEX, DATE(vec4)
        // std140: float(4) float(4) vec2(8, offset 8) int(4) int(4) vec4(16, offset 16) = 32 bytes total.
        #[repr(C)]
        #[derive(Clone, Copy, bytemuck::Pod, bytemuck::Zeroable)]
        struct Common {
            time: f32,
            timedelta: f32,
            render_size: [f32; 2],
            passindex: i32,
            frameindex: i32,
            _pad: [f32; 2],
            date: [f32; 4],
        }
        let common = Common {
            time: 0.0,
            timedelta: 0.0,
            render_size: [64.0, 64.0],
            passindex: 0,
            frameindex: 0,
            _pad: [0.0; 2],
            date: [0.0; 4],
        };
        let inputs: [f32; 4] = [0.5, 0.0, 0.0, 0.0]; // brightness = 0.5, one vec4 slot

        let target = OffscreenTarget::new(&ctx, 64, 64);
        target
            .render_glsl_fragment_shader(
                &ctx,
                &translated.source,
                bytemuck::bytes_of(&common),
                Some(bytemuck::cast_slice(&inputs)),
                &[],
            )
            .expect("render should succeed");
        let pixels = target.read_pixels(&ctx).expect("readback should succeed");

        // isf_FragNormCoord.x sweeps 0..1 left-to-right, scaled by brightness=0.5;
        // isf_FragNormCoord.y sweeps bottom-to-top in NDC (gl_FragCoord.y grows downward
        // in wgpu's convention), so just check the horizontal (red) sweep, which is
        // unambiguous regardless of that y-convention.
        let px = |x: u32, y: u32| -> [u8; 4] {
            let i = ((y * 64 + x) * 4) as usize;
            [pixels[i], pixels[i + 1], pixels[i + 2], pixels[i + 3]]
        };
        let left = px(0, 32)[0];
        let right = px(63, 32)[0];
        assert!(left < 20, "left red should be near 0, got {left}");
        assert!(
            right > 100 && right < 160,
            "right red should be ~0.5*255, got {right}"
        );
        assert!(right > left);
    }
}
