import type { IsfDocument, IsfInput } from './types'

// ISF shaders are written against GLSL ES 1.00-style built-ins
// (gl_FragColor, texture2D, isf_FragNormCoord, RENDERSIZE/TIME/...
// uniforms the host is expected to supply) that don't exist verbatim in the
// GLSL ES 3.00 this codebase's WebGL2 pipeline uses everywhere else (see
// fullscreen.vert.glsl / any *.frag.glsl in render/worker/passes). This is
// a source-level translation, not a real parser — deliberately: ISF's own
// spec describes exactly this kind of textual substitution as how hosts
// bridge the two, and a real GLSL parser is far more machinery than a
// single-pass subset needs.
export function translateIsfFragmentShader(doc: IsfDocument): string {
  let body = doc.body
    .replace(/gl_FragColor/g, 'isf_FragColor')
    .replace(/texture2D\s*\(/g, 'texture(')
    .replace(/textureCube\s*\(/g, 'texture(')

  // isf_FragNormCoord must be computed from gl_FragCoord inside a function
  // body (GLSL ES forbids non-constant global initializers), so it's
  // injected as the first statement of main() rather than declared at file
  // scope like the uniform-fed built-ins above it.
  const mainMatch = body.match(/void\s+main\s*\(\s*\)\s*\{/)
  if (!mainMatch) throw new Error('ISF shader body has no main() function')
  const insertAt = mainMatch.index! + mainMatch[0].length
  body = `${body.slice(0, insertAt)}\n  vec2 isf_FragNormCoord = gl_FragCoord.xy / RENDERSIZE;\n${body.slice(insertAt)}`

  const uniformDecls = doc.inputs.map((input) => `uniform ${glslType(input)} ${input.name};`).join('\n')

  return `#version 300 es
precision highp float;

uniform float TIME;
uniform float TIMEDELTA;
uniform vec2 RENDERSIZE;
uniform int PASSINDEX;
uniform int FRAMEINDEX;
uniform vec4 DATE;
${uniformDecls}

out vec4 isf_FragColor;

${body}
`
}

function glslType(input: IsfInput): string {
  switch (input.type) {
    case 'float':
      return 'float'
    case 'bool':
      return 'bool'
    case 'long':
      return 'int'
    case 'color':
      return 'vec4'
    case 'point2D':
      return 'vec2'
    case 'hysteresisSignal':
      // A bus signal is always a plain scalar uniform in GLSL, same as `float` — the
      // TYPE distinction only matters at the patch-graph/routing layer (isf-targets.ts),
      // not to the shader itself.
      return 'float'
  }
}
