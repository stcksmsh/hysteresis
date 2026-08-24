import type { Scene, SceneContext } from '../Scene'
import { createProgram } from '../../gl/program'
import { createFullscreenQuad, drawFullscreenQuad } from '../../gl/fullscreen-quad'
import fullscreenVertSrc from '../../gl/fullscreen.vert.glsl?raw'
import type { ParamBus } from '../../../../shared/types'
import type { IsfDocument } from '../../../../isf/types'
import { translateIsfFragmentShader } from '../../../../isf/translate-isf-glsl'

// Runs a user-supplied ISF shader as a real screen scene (master-prompt.md
// §4.5/§6's "ISF import" backlog item) — the whole point is that this is
// NOT a special-cased built-in effect, it's the same Scene interface
// JuliaScene/MandelbulbScene implement, driven by whatever inputs the
// loaded shader's own JSON header declares (see isf-targets.ts for how
// those become routable patch targets). Deliberately does NOT read
// ParamBus for its inputs the way JuliaScene does — ParamBus is a fixed,
// Julia-shaped struct (screen-composites.ts's ScreenParamAssembler); an
// arbitrary ISF shader's inputs have arbitrary names, so ScreenOutput feeds
// them in directly via setInputValues() from the raw per-frame resolved
// targets, bypassing that assembler entirely for this scene. `update()`
// still exists (the Scene interface requires it) purely to track TIME.
export class IsfScene implements Scene {
  readonly id = 'isf'
  readonly wantsPersistencePass = false
  readonly wantsMemoryField: boolean
  readonly wantsBloom = true

  private gl!: WebGL2RenderingContext
  private program!: WebGLProgram
  private quad!: WebGLVertexArrayObject
  private width = 0
  private height = 0
  private timeSec = 0
  private frameIndex = 0
  private uniformValues: Record<string, number | boolean | number[]> = {}

  private uTime: WebGLUniformLocation | null = null
  private uTimeDelta: WebGLUniformLocation | null = null
  private uRenderSize: WebGLUniformLocation | null = null
  private uPassIndex: WebGLUniformLocation | null = null
  private uFrameIndex: WebGLUniformLocation | null = null
  private uDate: WebGLUniformLocation | null = null
  private inputLocations = new Map<string, WebGLUniformLocation | null>()

  // wantsMemoryField defaults on so a loaded ISF generator gets the same
  // "drive anything through the site's memory-field/bloom pipeline" look
  // the built-in Julia substrate gets (master-prompt.md §4.5's "same graph
  // drives screen and physical light together" framing extends to "same
  // pipeline treats a built-in and a user shader the same way") — callers
  // that want a raw, unsmeared preview can pass false.
  constructor(private doc: IsfDocument, opts: { wantsMemoryField?: boolean } = {}) {
    this.wantsMemoryField = opts.wantsMemoryField ?? true
  }

  init(ctx: SceneContext): void {
    this.gl = ctx.gl
    const fragSrc = translateIsfFragmentShader(this.doc)
    this.program = createProgram(ctx.gl, fullscreenVertSrc, fragSrc)
    this.quad = createFullscreenQuad(ctx.gl)

    this.uTime = this.gl.getUniformLocation(this.program, 'TIME')
    this.uTimeDelta = this.gl.getUniformLocation(this.program, 'TIMEDELTA')
    this.uRenderSize = this.gl.getUniformLocation(this.program, 'RENDERSIZE')
    this.uPassIndex = this.gl.getUniformLocation(this.program, 'PASSINDEX')
    this.uFrameIndex = this.gl.getUniformLocation(this.program, 'FRAMEINDEX')
    this.uDate = this.gl.getUniformLocation(this.program, 'DATE')
    for (const input of this.doc.inputs) {
      this.inputLocations.set(input.name, this.gl.getUniformLocation(this.program, input.name))
    }
    this.resize(ctx)
  }

  resize(ctx: SceneContext): void {
    this.width = ctx.width
    this.height = ctx.height
  }

  // Called by ScreenOutput each frame with the typed uniform values
  // isf-targets.ts's resolvedTargetsToIsfUniforms() reassembled from that
  // frame's resolved patch-graph targets — the seam that makes a loaded
  // shader's inputs genuinely patchable, not just hardcoded to their
  // header defaults.
  setInputValues(values: Record<string, number | boolean | number[]>): void {
    this.uniformValues = values
  }

  update(dt: number, _params: ParamBus): void {
    this.timeSec += dt
    this.frameIndex += 1
  }

  render(targetFbo: WebGLFramebuffer | null): void {
    const gl = this.gl
    gl.bindFramebuffer(gl.FRAMEBUFFER, targetFbo)
    gl.viewport(0, 0, this.width, this.height)
    gl.useProgram(this.program)
    gl.uniform1f(this.uTime, this.timeSec)
    gl.uniform1f(this.uTimeDelta, 1 / 60)
    gl.uniform2f(this.uRenderSize, this.width, this.height)
    gl.uniform1i(this.uPassIndex, 0)
    gl.uniform1i(this.uFrameIndex, this.frameIndex)
    const now = new Date()
    gl.uniform4f(this.uDate, now.getFullYear(), now.getMonth() + 1, now.getDate(), now.getHours() * 3600 + now.getMinutes() * 60 + now.getSeconds())

    for (const input of this.doc.inputs) {
      const loc = this.inputLocations.get(input.name)
      if (!loc) continue
      const value = this.uniformValues[input.name]
      switch (input.type) {
        case 'float':
          gl.uniform1f(loc, typeof value === 'number' ? value : input.default)
          break
        case 'bool':
          gl.uniform1i(loc, value === true ? 1 : 0)
          break
        case 'long':
          gl.uniform1i(loc, typeof value === 'number' ? value : input.default)
          break
        case 'color': {
          const c = Array.isArray(value) ? value : input.default
          gl.uniform4f(loc, c[0] ?? 0, c[1] ?? 0, c[2] ?? 0, c[3] ?? 1)
          break
        }
        case 'point2D': {
          const p = Array.isArray(value) ? value : input.default
          gl.uniform2f(loc, p[0] ?? 0, p[1] ?? 0)
          break
        }
      }
    }

    gl.clearColor(0, 0, 0, 1)
    gl.clear(gl.COLOR_BUFFER_BIT)
    drawFullscreenQuad(gl, this.quad)
  }

  dispose(): void {
    this.gl.deleteProgram(this.program)
    this.gl.deleteVertexArray(this.quad)
  }
}
