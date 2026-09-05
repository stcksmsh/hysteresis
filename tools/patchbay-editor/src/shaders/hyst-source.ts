// Pure text-shape helpers for the Shaders screen's Header/GLSL/Script tab
// split — deliberately NOT a second parser. Real validation of the
// reassembled source (scriptOutput/scriptTexture shapes, unknown SIGNAL
// names, version gating, everything parse-isf.ts already enforces) always
// happens via the real `parseIsf()` at Apply/live-feedback time; these
// functions only reshape a .hyst file's plain text into three editable
// panes and back, tolerant of any syntactically-valid JSON header
// regardless of whether it would pass parseIsf()'s full semantic checks —
// those surface through the real parser, not duplicated here.

export interface HystDraft {
  headerText: string // the header JSON, WITHOUT HYSTERESIS_SCRIPT (that's its own tab/field below) — pretty-printed
  glslText: string
  scriptText: string // '' means no script
}

export function splitHystSource(source: string): HystDraft | { error: string } {
  const start = source.indexOf('/*')
  if (start === -1) return { error: 'No ISF header comment found (expected a leading /*{ ... }*/ block)' }
  const end = source.indexOf('*/', start + 2)
  if (end === -1) return { error: 'ISF header comment is not closed (missing */)' }

  const headerRaw = source.slice(start + 2, end).trim()
  const glslText = source.slice(end + 2).replace(/^\n+/, '')

  let header: Record<string, unknown>
  try {
    header = JSON.parse(headerRaw) as Record<string, unknown>
  } catch (err) {
    return { error: `Header is not valid JSON: ${err instanceof Error ? err.message : String(err)}` }
  }

  const scriptText = typeof header.HYSTERESIS_SCRIPT === 'string' ? header.HYSTERESIS_SCRIPT : ''
  delete header.HYSTERESIS_SCRIPT

  return { headerText: JSON.stringify(header, null, 2), glslText, scriptText }
}

export function buildHystSource(draft: HystDraft): { ok: true; source: string } | { ok: false; error: string } {
  let header: Record<string, unknown>
  try {
    header = JSON.parse(draft.headerText) as Record<string, unknown>
  } catch (err) {
    return { ok: false, error: `Header is not valid JSON: ${err instanceof Error ? err.message : String(err)}` }
  }
  if (draft.scriptText.trim()) {
    header.HYSTERESIS_SCRIPT = draft.scriptText
    // HYSTERESIS_SCRIPT requires HYSTERESIS_VERSION to be declared
    // (parse-isf.ts) — auto-set it here rather than making the user
    // remember to add it by hand whenever they enable the Script tab.
    if (header.HYSTERESIS_VERSION === undefined) header.HYSTERESIS_VERSION = 1
  } else {
    delete header.HYSTERESIS_SCRIPT
  }
  return { ok: true, source: `/*${JSON.stringify(header, null, 2)}*/\n\n${draft.glslText}` }
}

export const BLANK_HYST_DRAFT: HystDraft = {
  headerText: JSON.stringify(
    {
      DESCRIPTION: 'New shader',
      CATEGORIES: ['generator'],
      INPUTS: [{ NAME: 'speed', TYPE: 'float', DEFAULT: 1.0, MIN: 0.0, MAX: 4.0 }],
    },
    null,
    2,
  ),
  glslText: `void main() {
  vec2 uv = isf_FragNormCoord;
  gl_FragColor = vec4(uv, 0.5 + 0.5 * sin(TIME * speed), 1.0);
}
`,
  scriptText: '',
}

export const BLANK_SCRIPT_TEMPLATE = `// HYSTERESIS_SCRIPT: called once per render frame.
// dt: seconds since the last call. inputs: this shader's own declared
// hysteresisSignal (and other patch-routed scalar) input values, resolved
// for this frame. idle: true when no live audio is driving the scene.
// time: this shader's running clock (matches the GLSL TIME uniform).
// Must return { uniforms, textures } — uniforms supplies a value for every
// declared scriptOutput input by name; textures supplies a flat number[]
// for every declared scriptTexture pass's SOURCE name. All per-frame state
// (springs, accumulators, search targets) lives in this closure.
function update(dt, inputs, idle, time) {
  return { uniforms: {}, textures: {} }
}
`
