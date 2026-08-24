import type { Scene, SceneContext } from '../Scene'
import { createProgram } from '../../gl/program'
import { createFullscreenQuad, drawFullscreenQuad } from '../../gl/fullscreen-quad'
import { createFbo, deleteFbo, type Fbo } from '../../gl/fbo'
import fullscreenVertSrc from '../../gl/fullscreen.vert.glsl?raw'
import beamVertSrc from '../julia/shaders/beam.vert.glsl?raw'
import beamFragSrc from '../julia/shaders/beam.frag.glsl?raw'
import { lissajousPoint } from '../julia/lissajous'
import { SCOPE_SIZE } from '../../../../shared/constants'
import type { ParamBus } from '../../../../shared/types'
import type { IsfDocument, IsfLineTracePass, IsfScriptTexturePass } from '../../../../isf/types'
import { translateIsfFragmentShader } from '../../../../isf/translate-isf-glsl'
import { buildScriptOutputContract } from '../../../../isf/script-runtime/contract'
import { HysteresisScriptHost } from './script-runtime/script-host'

// Same idle-fallback shape as JuliaScene's own beam (lissajous.ts's header
// comment: "the substrate's idle c-drift and the beam's idle trace both
// walk this same curve so the two layers read as one stationary dynamic")
// — a lineTrace pass reuses that exact fallback so an ISF/hysteresis
// shader's beam behaves identically to the built-in one when there's no
// live waveform (StructureSource.synthesize()'s position-only mode always
// sets scope: null / idle: true — see AGENTS.md's own note on why).
const IDLE_BEAM_POINTS = 220
const BEAM_HALF_WIDTH_DEFAULT = 0.009
const BEAM_SCOPE_GAIN = 3.2
const MAX_SEGMENTS = Math.max(SCOPE_SIZE - 1, IDLE_BEAM_POINTS - 1)

interface ScriptTextureState {
  pass: IsfScriptTexturePass
  texture: WebGLTexture
}

interface LineTraceState {
  pass: IsfLineTracePass
  fbo: Fbo | null
  program: WebGLProgram
  vao: WebGLVertexArrayObject
  cornerBuffer: WebGLBuffer
  p0Buffer: WebGLBuffer
  p1Buffer: WebGLBuffer
  uAspect: WebGLUniformLocation | null
  uHalfWidth: WebGLUniformLocation | null
  uColor: WebGLUniformLocation | null
  uIntensity: WebGLUniformLocation | null
}

// Runs a user-supplied ISF/Hysteresis shader as a real screen scene
// (master-prompt.md §4.5/§6's "ISF import" backlog item) — the whole point
// is that this is NOT a special-cased built-in effect, it's the same Scene
// interface JuliaScene/MandelbulbScene implement, driven by whatever
// inputs/passes the loaded shader's own JSON header declares (see
// isf-targets.ts for how scalar inputs become routable patch targets).
// Deliberately does NOT read ParamBus for its SCALAR inputs the way
// JuliaScene does — ParamBus is a fixed, Julia-shaped struct
// (screen-composites.ts's ScreenParamAssembler); an arbitrary shader's
// inputs have arbitrary names, so ScreenOutput feeds them in directly via
// setInputValues() from the raw per-frame resolved targets, bypassing that
// assembler entirely for this scene. `scope` (a `resource` input, never a
// scalar target — see IsfResourceInput's comment in isf/types.ts) is the
// one thing this scene DOES read straight off ParamBus, same channel
// JuliaScene's own beam already uses.
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
  private idleClockSec = 0
  private uniformValues: Record<string, number | boolean | number[]> = {}

  private uTime: WebGLUniformLocation | null = null
  private uTimeDelta: WebGLUniformLocation | null = null
  private uRenderSize: WebGLUniformLocation | null = null
  private uPassIndex: WebGLUniformLocation | null = null
  private uFrameIndex: WebGLUniformLocation | null = null
  private uDate: WebGLUniformLocation | null = null
  private inputLocations = new Map<string, WebGLUniformLocation | null>()
  private passTargetLocations = new Map<string, WebGLUniformLocation | null>()

  private lineTraces: LineTraceState[] = []
  private scriptTextures: ScriptTextureState[] = []
  // Non-null only when the shader declares a real HYSTERESIS_SCRIPT — owns the sandboxed nested
  // Worker that runs it (see script-runtime/script-host.ts). null for every scriptless shader
  // (today's common case), so none of this machinery runs at all unless a shader opts in.
  private scriptHost: HysteresisScriptHost | null = null
  // Shared per-frame point buffer for every lineTrace pass whose resource
  // is 'scope' (the only known resource today — see KNOWN_RESOURCES in
  // parse-isf.ts) — computed once in update(), reused by however many
  // passes reference it, exactly mirroring JuliaScene's updateBeamGeometry.
  private scopeP0 = new Float32Array(MAX_SEGMENTS * 2)
  private scopeP1 = new Float32Array(MAX_SEGMENTS * 2)
  private scopeSegmentCount = 0

  // wantsMemoryField defaults on so a loaded ISF generator gets the same
  // "drive anything through the site's memory-field/bloom pipeline" look
  // the built-in Julia substrate gets (master-prompt.md §4.5's "same graph
  // drives screen and physical light together" framing extends to "same
  // pipeline treats a built-in and a user shader the same way") — callers
  // that want a raw, unsmeared preview can pass false.
  constructor(
    private doc: IsfDocument,
    opts: { wantsMemoryField?: boolean } = {},
  ) {
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
      if (input.type === 'resource') continue // never a uniform — see translate-isf-glsl.ts
      this.inputLocations.set(input.name, this.gl.getUniformLocation(this.program, input.name))
    }
    for (const pass of this.doc.passes) {
      if (pass.target !== '') {
        this.passTargetLocations.set(pass.target, this.gl.getUniformLocation(this.program, pass.target))
      }
    }

    this.lineTraces = this.doc.passes.filter((p): p is IsfLineTracePass => p.kind === 'lineTrace').map((pass) => this.createLineTrace(pass))
    this.scriptTextures = this.doc.passes.filter((p): p is IsfScriptTexturePass => p.kind === 'scriptTexture').map((pass) => this.createScriptTexture(pass))

    if (this.doc.hysteresisScript) {
      const contract = buildScriptOutputContract(this.doc)
      this.scriptHost = new HysteresisScriptHost(this.doc.hysteresisScript, contract, (message) => {
        // Runtime faults (a hang, a throw, a load-time syntax error) are logged clearly rather
        // than silently swallowed — rendering keeps going on last-known/default values either
        // way (see HysteresisScriptHost's own header comment), so this is diagnostic, not fatal.
        console.error(`[hysteresis-script] ${message}`)
      })
    }

    this.resize(ctx)
  }

  private createScriptTexture(pass: IsfScriptTexturePass): ScriptTextureState {
    const gl = this.gl
    const texture = gl.createTexture()
    if (!texture) throw new Error('Failed to create scriptTexture texture')
    gl.bindTexture(gl.TEXTURE_2D, texture)
    // texelFetch (what a shader reading this via GLSL is expected to use, same as
    // JuliaScene.ts's uRefOrbit) ignores filtering/wrap mode entirely, but the texture still
    // needs to be complete.
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE)
    // RG32F sampling is core WebGL2 (no extension needed) as long as it's only ever sampled,
    // never rendered to — which is all this does, same as JuliaScene.ts's own ref-orbit texture.
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RG32F, pass.length, 1, 0, gl.RG, gl.FLOAT, null)
    return { pass, texture }
  }

  private createLineTrace(pass: IsfLineTracePass): LineTraceState {
    const gl = this.gl
    const program = createProgram(gl, beamVertSrc, beamFragSrc)

    const vao = gl.createVertexArray()
    if (!vao) throw new Error('Failed to create lineTrace VAO')
    gl.bindVertexArray(vao)

    const cornerBuffer = gl.createBuffer()
    if (!cornerBuffer) throw new Error('Failed to create lineTrace corner buffer')
    gl.bindBuffer(gl.ARRAY_BUFFER, cornerBuffer)
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-0.5, 0, -0.5, 1, 0.5, 0, 0.5, 1]), gl.STATIC_DRAW)
    gl.enableVertexAttribArray(0)
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0)

    const p0Buffer = gl.createBuffer()
    if (!p0Buffer) throw new Error('Failed to create lineTrace p0 buffer')
    gl.bindBuffer(gl.ARRAY_BUFFER, p0Buffer)
    gl.bufferData(gl.ARRAY_BUFFER, this.scopeP0.byteLength, gl.DYNAMIC_DRAW)
    gl.enableVertexAttribArray(1)
    gl.vertexAttribPointer(1, 2, gl.FLOAT, false, 0, 0)
    gl.vertexAttribDivisor(1, 1)

    const p1Buffer = gl.createBuffer()
    if (!p1Buffer) throw new Error('Failed to create lineTrace p1 buffer')
    gl.bindBuffer(gl.ARRAY_BUFFER, p1Buffer)
    gl.bufferData(gl.ARRAY_BUFFER, this.scopeP1.byteLength, gl.DYNAMIC_DRAW)
    gl.enableVertexAttribArray(2)
    gl.vertexAttribPointer(2, 2, gl.FLOAT, false, 0, 0)
    gl.vertexAttribDivisor(2, 1)

    gl.bindVertexArray(null)

    return {
      pass,
      fbo: null,
      program,
      vao,
      cornerBuffer,
      p0Buffer,
      p1Buffer,
      uAspect: gl.getUniformLocation(program, 'uAspect'),
      uHalfWidth: gl.getUniformLocation(program, 'uHalfWidth'),
      uColor: gl.getUniformLocation(program, 'uColor'),
      uIntensity: gl.getUniformLocation(program, 'uIntensity'),
    }
  }

  resize(ctx: SceneContext): void {
    this.width = ctx.width
    this.height = ctx.height
    // Recreated lazily at render() time (ensureLineTraceFbos) rather than
    // here — this.gl is guaranteed set by then, and it keeps FBO lifetime
    // logic in one place instead of duplicated between init()/resize().
    for (const lt of this.lineTraces) {
      if (lt.fbo) {
        deleteFbo(this.gl, lt.fbo)
        lt.fbo = null
      }
    }
  }

  // Called by ScreenOutput each frame with the typed uniform values
  // isf-targets.ts's resolvedTargetsToIsfUniforms() reassembled from that
  // frame's resolved patch-graph targets — the seam that makes a loaded
  // shader's SCALAR inputs genuinely patchable, not just hardcoded to
  // their header defaults. `resource` inputs never appear here — see this
  // class's own header comment.
  setInputValues(values: Record<string, number | boolean | number[]>): void {
    this.uniformValues = values
  }

  update(dt: number, params: ParamBus): void {
    this.timeSec += dt
    this.frameIndex += 1
    if (params.idle) this.idleClockSec += dt

    // Fire-and-forget, per HysteresisScriptHost's own design — this frame's render() reads
    // whatever the LATEST completed reply is (possibly from a slightly earlier frame), never
    // blocking on this call. `idle` is supplied here directly off ParamBus (not a routable
    // signal — see SIGNAL_TAGS's own comment), the same non-patch-graph exception this scene
    // already makes for `scope` below. `this.uniformValues` is exactly the same resolved-target
    // snapshot the shader's own GLSL uniforms are bound from (setInputValues(), called by
    // ScreenOutput before update() each frame) — the script never sees the raw SignalBus.
    this.scriptHost?.postUpdate({ dt, time: this.timeSec, idle: params.idle, inputs: this.uniformValues })

    if (this.lineTraces.length === 0) return // no lineTrace pass declared — skip the point-buffer work entirely

    const scope = params.idle ? null : params.scope
    if (scope) {
      const n = scope.length
      this.scopeSegmentCount = n - 1
      for (let i = 0; i < n; i++) {
        const x = (i / (n - 1)) * 1.8 - 0.9
        const y = Math.max(-0.9, Math.min(0.9, scope[i] * BEAM_SCOPE_GAIN))
        if (i < n - 1) {
          this.scopeP0[i * 2] = x
          this.scopeP0[i * 2 + 1] = y
        }
        if (i > 0) {
          this.scopeP1[(i - 1) * 2] = x
          this.scopeP1[(i - 1) * 2 + 1] = y
        }
      }
    } else {
      const n = IDLE_BEAM_POINTS
      this.scopeSegmentCount = n - 1
      const phase = this.idleClockSec * 0.15
      for (let i = 0; i < n; i++) {
        const theta = (i / (n - 1)) * Math.PI * 2
        const p = lissajousPoint(theta, phase)
        if (i < n - 1) {
          this.scopeP0[i * 2] = p.x * 0.75
          this.scopeP0[i * 2 + 1] = p.y * 0.75
        }
        if (i > 0) {
          this.scopeP1[(i - 1) * 2] = p.x * 0.75
          this.scopeP1[(i - 1) * 2 + 1] = p.y * 0.75
        }
      }
    }

    const gl = this.gl
    for (const lt of this.lineTraces) {
      gl.bindBuffer(gl.ARRAY_BUFFER, lt.p0Buffer)
      gl.bufferSubData(gl.ARRAY_BUFFER, 0, this.scopeP0, 0, this.scopeSegmentCount * 2)
      gl.bindBuffer(gl.ARRAY_BUFFER, lt.p1Buffer)
      gl.bufferSubData(gl.ARRAY_BUFFER, 0, this.scopeP1, 0, this.scopeSegmentCount * 2)
    }
  }

  // Uploads this frame's latest script-produced texture data (e.g. a perturbation reference
  // orbit — see JuliaScene.ts's updateReferenceOrbit/uRefOrbit, the concrete motivating case) —
  // called once per render() right after the scriptOutput uniforms are bound, before the earlier-
  // passes texture-binding loop reads these textures. Silently a no-op for every scriptless
  // shader (this.scriptTextures is empty) and for any frame before the script's first reply
  // lands (getLatestOutput() still null — the texture just keeps whatever it was last set to,
  // zero-initialized at allocation).
  private uploadScriptTextures(): void {
    if (this.scriptTextures.length === 0) return
    const gl = this.gl
    const output = this.scriptHost?.getLatestOutput()
    if (!output) return
    for (const st of this.scriptTextures) {
      const data = output.textures[st.pass.source]
      if (!data) continue
      gl.bindTexture(gl.TEXTURE_2D, st.texture)
      gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, st.pass.length, 1, gl.RG, gl.FLOAT, new Float32Array(data))
    }
  }

  private ensureLineTraceFbos(): void {
    const gl = this.gl
    for (const lt of this.lineTraces) {
      if (!lt.fbo) lt.fbo = createFbo(gl, this.width, this.height, false)
    }
  }

  private resolveHalfWidth(pass: IsfLineTracePass): number {
    if (!pass.width) return BEAM_HALF_WIDTH_DEFAULT
    const v = this.uniformValues[pass.width]
    return typeof v === 'number' ? v : BEAM_HALF_WIDTH_DEFAULT
  }

  private renderLineTraces(): void {
    const gl = this.gl
    const aspect = this.height > 0 ? this.width / this.height : 1
    for (const lt of this.lineTraces) {
      if (!lt.fbo) continue
      gl.bindFramebuffer(gl.FRAMEBUFFER, lt.fbo.framebuffer)
      gl.viewport(0, 0, this.width, this.height)
      gl.clearColor(0, 0, 0, 0)
      gl.clear(gl.COLOR_BUFFER_BIT)
      if (this.scopeSegmentCount === 0) continue
      gl.disable(gl.BLEND)
      gl.useProgram(lt.program)
      gl.uniform1f(lt.uAspect, aspect)
      gl.uniform1f(lt.uHalfWidth, this.resolveHalfWidth(lt.pass))
      // Always full-brightness white here — tint/intensity is the
      // compositing (fullscreen) pass's job (it samples this texture and
      // decides how to color/blend it), not this pass's. This is what
      // makes "the beam is part of the shader" real: this pass only ever
      // rasterizes SHAPE, never final look.
      gl.uniform3f(lt.uColor, 1, 1, 1)
      gl.uniform1f(lt.uIntensity, 1)
      gl.bindVertexArray(lt.vao)
      gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, this.scopeSegmentCount)
      gl.bindVertexArray(null)
    }
  }

  render(targetFbo: WebGLFramebuffer | null): void {
    const gl = this.gl
    this.ensureLineTraceFbos()
    this.renderLineTraces()

    gl.bindFramebuffer(gl.FRAMEBUFFER, targetFbo)
    gl.viewport(0, 0, this.width, this.height)
    gl.disable(gl.BLEND)
    gl.useProgram(this.program)
    gl.uniform1f(this.uTime, this.timeSec)
    gl.uniform1f(this.uTimeDelta, 1 / 60)
    gl.uniform2f(this.uRenderSize, this.width, this.height)
    gl.uniform1i(this.uPassIndex, 0)
    gl.uniform1i(this.uFrameIndex, this.frameIndex)
    const now = new Date()
    gl.uniform4f(this.uDate, now.getFullYear(), now.getMonth() + 1, now.getDate(), now.getHours() * 3600 + now.getMinutes() * 60 + now.getSeconds())

    for (const input of this.doc.inputs) {
      if (input.type === 'resource') continue
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
        case 'hysteresisSignal':
          gl.uniform1f(loc, typeof value === 'number' ? value : input.default)
          break
        case 'scriptOutput': {
          // Never from `this.uniformValues` (the patch-graph-fed path) — a scriptOutput input is
          // never routable (isf-targets.ts's isfInputsToTargets returns [] for it), its value
          // only ever comes from the HYSTERESIS_SCRIPT host's latest completed reply, falling
          // back to the input's own declared default before the first reply lands or if the
          // script never supplies this name (engine-source.ts's own coercion already guarantees
          // that fallback happens inside the sandbox too — this is a second, harmless belt-and-
          // braces fallback on the trusted side).
          const scripted = this.scriptHost?.getLatestOutput()?.uniforms[input.name] ?? input.default
          switch (input.kind) {
            case 'float':
              gl.uniform1f(loc, typeof scripted === 'number' ? scripted : 0)
              break
            case 'bool':
              gl.uniform1i(loc, scripted === true ? 1 : 0)
              break
            case 'point2D': {
              const p = Array.isArray(scripted) ? scripted : [0, 0]
              gl.uniform2f(loc, p[0] ?? 0, p[1] ?? 0)
              break
            }
            case 'color': {
              const c = Array.isArray(scripted) ? scripted : [0, 0, 0, 1]
              gl.uniform4f(loc, c[0] ?? 0, c[1] ?? 0, c[2] ?? 0, c[3] ?? 1)
              break
            }
          }
          break
        }
      }
    }

    this.uploadScriptTextures()

    // Bind every earlier lineTrace/scriptTexture pass's texture to the
    // fullscreen pass's matching `uniform sampler2D <target>` — starting
    // at texture unit 1 (unit 0 is free for a future 'fullscreen'-target
    // pass; not used yet, see IsfFullscreenPass's own comment).
    let unit = 1
    for (const lt of this.lineTraces) {
      const loc = this.passTargetLocations.get(lt.pass.target)
      if (!loc || !lt.fbo) continue
      gl.activeTexture(gl.TEXTURE0 + unit)
      gl.bindTexture(gl.TEXTURE_2D, lt.fbo.texture)
      gl.uniform1i(loc, unit)
      unit++
    }
    for (const st of this.scriptTextures) {
      const loc = this.passTargetLocations.get(st.pass.target)
      if (!loc) continue
      gl.activeTexture(gl.TEXTURE0 + unit)
      gl.bindTexture(gl.TEXTURE_2D, st.texture)
      gl.uniform1i(loc, unit)
      unit++
    }
    gl.activeTexture(gl.TEXTURE0)

    gl.clearColor(0, 0, 0, 1)
    gl.clear(gl.COLOR_BUFFER_BIT)
    drawFullscreenQuad(gl, this.quad)
  }

  dispose(): void {
    const gl = this.gl
    gl.deleteProgram(this.program)
    gl.deleteVertexArray(this.quad)
    for (const lt of this.lineTraces) {
      gl.deleteProgram(lt.program)
      gl.deleteVertexArray(lt.vao)
      gl.deleteBuffer(lt.cornerBuffer)
      gl.deleteBuffer(lt.p0Buffer)
      gl.deleteBuffer(lt.p1Buffer)
      if (lt.fbo) deleteFbo(gl, lt.fbo)
    }
    for (const st of this.scriptTextures) {
      gl.deleteTexture(st.texture)
    }
    // Must terminate the nested Worker on every dispose — a shader hot-swap
    // (ScreenOutput.setIsfScene()/resetToDefaultScene() both call
    // scene.dispose() before replacing this.scene) would otherwise leak one
    // running Worker per swap, the same class of resource-lifecycle bug
    // this codebase has hit before with canvas transfers/context loss.
    this.scriptHost?.dispose()
  }
}
