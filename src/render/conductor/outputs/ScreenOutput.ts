import type { PowerTier } from '../../../shared/types'
import { createFbo, deleteFbo, type Fbo } from '../../worker/gl/fbo'
import type { GlCapabilities } from '../../worker/gl/context'
import { sceneRegistry, DEFAULT_SCENE_ID } from '../../worker/scenes/registry'
import type { Scene } from '../../worker/scenes/Scene'
import { PersistencePass } from '../../worker/passes/persistence-pass'
import { MemoryFieldPass } from '../../worker/passes/memory-field-pass'
import { BloomPass } from '../../worker/passes/bloom-pass'
import { CompositePass } from '../../worker/passes/composite-pass'
import { ScreenParamAssembler } from '../patchbay/screen-composites'
import { SCREEN_TARGETS } from './screen-targets'
import type { ResolvedTargets, TargetDecl, VizOutput } from '../types'
import { IsfScene } from '../../worker/scenes/isf/IsfScene'
import type { IsfDocument } from '../../../isf/types'
import { isfInputsToTargets, resolvedTargetsToIsfUniforms } from '../../../isf/isf-targets'

const PERSISTENCE_DECAY = 0.85
const BLOOM_THRESHOLD = 0.55
const BLOOM_STRENGTH = 0.45
const BLOOM_STRENGTH_SCALE: Record<PowerTier, number> = { full: 1, cheap: 0.5, 'idle-only': 0.5 }

// The only implemented VizOutput (SINTEZA_SIGNAL_BUS.md §6.2). Wraps the
// existing render pipeline unchanged — Scene/SceneContext, the GL passes,
// and their allocate/resize lifecycle, all moved in verbatim from
// render-worker.ts — and assembles the ParamBus-shaped struct `Scene`
// expects from patchbay-resolved targets instead of a conductor producing
// it directly. Everything after `scene.render()` today (memory field,
// persistence, bloom, composite) lives here now: it's all screen-specific
// GL work, invisible to any other output.
export class ScreenOutput implements VizOutput {
  readonly id = 'screen'
  // Not `readonly` at the class-field level (the VizOutput interface's own
  // `readonly` only forbids reassignment through that interface type) —
  // setIsfScene()/resetToDefaultScene() below widen/restore this to include
  // a loaded shader's own declared inputs as real routable targets.
  targets: TargetDecl[] = SCREEN_TARGETS

  private assembler = new ScreenParamAssembler()
  private caps: GlCapabilities | null = null
  private scene: Scene | null = null
  // Set only while an ISF scene is active — this is what tells update()
  // to reassemble typed uniform values for setInputValues() every frame;
  // null (the default/production state) means that work never runs at all.
  private isfDoc: IsfDocument | null = null
  private reducedMotion = false
  private currentTier: PowerTier = 'full'
  private lastWidth = 0
  private lastHeight = 0
  private lastDpr = 1

  private sceneFbo: Fbo | null = null
  private persistencePass: PersistencePass | null = null
  private memoryFieldPass: MemoryFieldPass | null = null
  private bloomPass: BloomPass | null = null
  private compositePass: CompositePass | null = null

  // Called once at startup, AND again on every WebGL context-loss/restore
  // cycle (render-worker.ts's `webglcontextrestored` handler re-runs this
  // exact method against the same ScreenOutput instance, reusing
  // `caps.gl` — the context object itself survives loss/restore, only its
  // GL resources do not). That reuse is exactly the bug this method used
  // to have: `allocatePipeline()` below only calls `new Xxx(...)` for a
  // pass that's still `null` — on a restore, every pass/compositePass/
  // sceneFbo field already holds a non-null JS wrapper object from BEFORE
  // the loss, so allocatePipeline took the "already exists, just resize()"
  // branch and left every pass's program/VAO/texture (created only in
  // each pass's constructor, never touched by resize()) pointing at
  // now-invalid GL objects — and `compositePass` specifically is never
  // reconstructed at all past the very first init (`if (!this.compositePass)`).
  // Net effect before this fix: after a real context loss (a real, not
  // theoretical, risk on hybrid-graphics laptops per the comment on the
  // restore listener itself), the screen went black/frozen permanently,
  // silently, on an unattended 24/7 background — the exact failure this
  // loss/restore handling was built to prevent. Nulling every GL-backed
  // field here before allocatePipeline() forces it to reconstruct
  // everything fresh on a restore; on the very first call these are
  // already null, so this changes nothing about normal startup.
  init(caps: GlCapabilities, width: number, height: number, dpr: number, reducedMotion: boolean): void {
    this.scene?.dispose()
    this.scene = null
    this.sceneFbo = null
    this.persistencePass = null
    this.memoryFieldPass = null
    this.bloomPass = null
    this.compositePass = null

    this.caps = caps
    this.reducedMotion = reducedMotion
    this.lastWidth = width
    this.lastHeight = height
    this.lastDpr = dpr
    this.allocatePipeline(width, height)
    this.scene = this.isfDoc ? new IsfScene(this.isfDoc) : sceneRegistry[DEFAULT_SCENE_ID]()
    this.scene.init({ gl: caps.gl, width, height, dpr, reducedMotion, floatFbo: caps.floatFbo })
  }

  resize(width: number, height: number, dpr: number): void {
    if (!this.caps) return
    this.lastWidth = width
    this.lastHeight = height
    this.lastDpr = dpr
    this.allocatePipeline(width, height)
    this.scene?.resize({ gl: this.caps.gl, width, height, dpr, reducedMotion: this.reducedMotion, floatFbo: this.caps.floatFbo })
  }

  setReducedMotion(value: boolean): void {
    this.reducedMotion = value
    if (!this.caps) return
    this.scene?.resize({
      gl: this.caps.gl,
      width: this.lastWidth,
      height: this.lastHeight,
      dpr: this.lastDpr,
      reducedMotion: value,
      floatFbo: this.caps.floatFbo,
    })
  }

  setQuality(scale: number): void {
    this.scene?.setQuality?.(scale)
  }

  setSimMaxEdge(maxEdge: number): void {
    this.scene?.setSimMaxEdge?.(maxEdge)
  }

  setAccent(rgb: [number, number, number]): void {
    this.scene?.setAccent?.(rgb)
  }

  setShowIdleBeam(value: boolean): void {
    this.scene?.setShowIdleBeam?.(value)
  }

  setTier(tier: PowerTier): void {
    this.currentTier = tier
  }

  // Hot-swaps the active scene to a loaded ISF shader (dev-only today, per
  // render-worker.ts's debugSetIsfShader — never called in production
  // unless something explicitly sends that message). Widens `targets` to
  // include the shader's own declared inputs so they show up as real
  // routable targets the next time a patch graph is (re)built against
  // this output — the same shape SCREEN_TARGETS already has.
  setIsfScene(doc: IsfDocument): void {
    if (!this.caps) throw new Error('ScreenOutput.setIsfScene called before init()')
    this.scene?.dispose()
    const scene = new IsfScene(doc)
    scene.init({ gl: this.caps.gl, width: this.lastWidth, height: this.lastHeight, dpr: this.lastDpr, reducedMotion: this.reducedMotion, floatFbo: this.caps.floatFbo })
    this.scene = scene
    this.isfDoc = doc
    this.targets = [...SCREEN_TARGETS, ...isfInputsToTargets(doc)]
  }

  // Reverts to the default registry scene (julia) — the counterpart to
  // setIsfScene(), used when the editor's ISF panel is cleared/reset.
  resetToDefaultScene(): void {
    if (!this.caps) return
    this.scene?.dispose()
    this.scene = sceneRegistry[DEFAULT_SCENE_ID]()
    this.scene.init({ gl: this.caps.gl, width: this.lastWidth, height: this.lastHeight, dpr: this.lastDpr, reducedMotion: this.reducedMotion, floatFbo: this.caps.floatFbo })
    this.isfDoc = null
    this.targets = SCREEN_TARGETS
  }

  update(dt: number, resolved: ResolvedTargets): void {
    if (!this.scene || !this.sceneFbo || !this.compositePass) return

    const params = this.assembler.update(dt, resolved)
    if (this.isfDoc) this.scene.setInputValues?.(resolvedTargetsToIsfUniforms(this.isfDoc, resolved))
    this.scene.update(dt, params)
    this.scene.render(this.sceneFbo.framebuffer)

    let currentTexture = this.sceneFbo.texture
    if (this.scene.wantsMemoryField && this.memoryFieldPass && !this.reducedMotion) {
      const aspect = this.sceneFbo.width / Math.max(1, this.sceneFbo.height)
      const fieldResult = this.memoryFieldPass.apply(currentTexture, dt, {
        decay: params.fieldDecay,
        flowStrength: params.flowStrength,
        symmetry: params.symmetry,
        aspect,
        flowDirection: params.flowDirection,
      })
      currentTexture = fieldResult.texture
      this.scene.renderForeground?.(fieldResult.framebuffer)
    } else if (this.scene.wantsPersistencePass && this.persistencePass && !this.reducedMotion) {
      currentTexture = this.persistencePass.apply(currentTexture, PERSISTENCE_DECAY)
    }

    let bloomTexture: WebGLTexture | null = null
    if (this.scene.wantsBloom && this.bloomPass && !this.reducedMotion) {
      bloomTexture = this.bloomPass.apply(currentTexture, BLOOM_THRESHOLD)
    }

    this.compositePass.apply(
      null,
      this.sceneFbo.width,
      this.sceneFbo.height,
      currentTexture,
      bloomTexture,
      BLOOM_STRENGTH * BLOOM_STRENGTH_SCALE[this.currentTier],
    )
  }

  private allocatePipeline(width: number, height: number): void {
    if (!this.caps) return
    const gl = this.caps.gl
    if (this.sceneFbo) deleteFbo(gl, this.sceneFbo)
    this.sceneFbo = createFbo(gl, Math.max(1, width), Math.max(1, height), this.caps.floatFbo)

    if (this.persistencePass) this.persistencePass.resize(width, height)
    else this.persistencePass = new PersistencePass(gl, width, height, this.caps.floatFbo)

    if (this.memoryFieldPass) this.memoryFieldPass.resize(width, height)
    else this.memoryFieldPass = new MemoryFieldPass(gl, width, height, this.caps.floatFbo)

    if (this.bloomPass) this.bloomPass.resize(width, height)
    else this.bloomPass = new BloomPass(gl, width, height, this.caps.floatFbo)

    if (!this.compositePass) this.compositePass = new CompositePass(gl)
  }

  dispose(): void {
    this.scene?.dispose()
  }
}
