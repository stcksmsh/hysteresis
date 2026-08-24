#!/usr/bin/env node
import { spawn, execFileSync } from 'node:child_process'
import { readFileSync, writeFileSync, mkdtempSync, existsSync, rmSync } from 'node:fs'
import { join, resolve, extname, basename } from 'node:path'
import { tmpdir } from 'node:os'
import puppeteer, { type Browser, type Page } from 'puppeteer-core'
import { decodeWavFile } from './wav'
import { analyzeMix } from './structure'
import { parseIsf } from '../src/isf/parse-isf'
import type { Sidecar } from '../src/shared/sidecar'

// Offline video-render tool (AGENTS.md's "render-video" session): drives
// the REAL production render pipeline (render-worker.ts, unmodified logic,
// see its own renderStep() refactor) deterministically — not real-time —
// through a headless Chrome instance, muxing the result with the real
// track audio via ffmpeg. "A good thing to have" per the user's own framing,
// not a one-off script: every input is a real CLI flag, sidecar-driven by
// default (the site's own actual production integration mode), with clean
// opt-outs for the debug/fixture overlays this session added them for.

interface Options {
  input: string
  sidecarPath?: string
  isfPath?: string
  fps: number
  width: number
  height: number
  out: string
  debugOverlay: boolean
  fixtureOverlay: boolean
  chromePath: string
  duration?: number // seconds — render only the first N seconds (quick iteration), full track if omitted
  workDirParent: string // where the temp frame-sequence directory is created — a full track's frames can be multiple GB
  videoBitrateKbps?: number // omitted = ffmpeg's default CRF encode (large, quality-first); set to hit a size budget directly at render resolution instead of downscale-recompressing afterward
  audioBitrateKbps: number
}

function parseArgs(argv: string[]): Options {
  const args = [...argv]
  const positional: string[] = []
  const opts: Record<string, string> = {}
  const flags = new Set<string>()
  while (args.length > 0) {
    const a = args.shift()!
    if (a === '--no-debug-overlay') flags.add('no-debug-overlay')
    else if (a === '--no-fixture-overlay') flags.add('no-fixture-overlay')
    else if (a.startsWith('--')) opts[a.slice(2)] = args.shift() ?? ''
    else positional.push(a)
  }
  if (positional.length === 0) {
    console.error('usage: render-video <master.wav|mp4> [--sidecar path.json] [--isf shader.fs] [--fps 30]')
    console.error('                     [--width 1920] [--height 1080] [--out out.mp4] [--no-debug-overlay] [--no-fixture-overlay]')
    console.error('                     [--chrome /path/to/chrome] [--duration 120]')
    console.error('                     [--video-bitrate kbps] [--audio-bitrate kbps]')
    process.exit(1)
  }
  return {
    input: resolve(positional[0]),
    sidecarPath: opts.sidecar ? resolve(opts.sidecar) : undefined,
    isfPath: opts.isf ? resolve(opts.isf) : undefined,
    fps: opts.fps ? Number(opts.fps) : 30,
    width: opts.width ? Number(opts.width) : 1920,
    height: opts.height ? Number(opts.height) : 1080,
    out: resolve(opts.out ?? `${basename(positional[0], extname(positional[0]))}.render.mp4`),
    debugOverlay: !flags.has('no-debug-overlay'),
    fixtureOverlay: !flags.has('no-fixture-overlay'),
    chromePath: opts.chrome ?? '/usr/bin/google-chrome',
    duration: opts.duration ? Number(opts.duration) : undefined,
    // A full track's JPEG frame sequence is multiple GB — default to
    // os.tmpdir(), but make it overridable (--work-dir), since a small/full
    // root partition with a separate, larger /home (or other) mount is a
    // real, observed failure mode, not a hypothetical one (see AGENTS.md's
    // own note on this).
    workDirParent: opts['work-dir'] ?? tmpdir(),
    videoBitrateKbps: opts['video-bitrate'] ? Number(opts['video-bitrate']) : undefined,
    audioBitrateKbps: opts['audio-bitrate'] ? Number(opts['audio-bitrate']) : 128,
  }
}

function extractAudioWav(inputPath: string, outWavPath: string): void {
  execFileSync('ffmpeg', ['-y', '-i', inputPath, '-ac', '2', '-ar', '48000', '-sample_fmt', 's16', outWavPath], { stdio: 'inherit' })
}

function loadOrGenerateSidecar(wavPath: string, sidecarPath: string | undefined): Sidecar {
  if (sidecarPath) {
    return JSON.parse(readFileSync(sidecarPath, 'utf8')) as Sidecar
  }
  console.log('[render-video] no --sidecar given, analyzing the track first (analyzeMix)...')
  const wav = decodeWavFile(wavPath)
  return analyzeMix(wav)
}

async function waitForServer(url: string, timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url)
      if (res.ok || res.status === 404) return
    } catch {
      // not up yet
    }
    await new Promise((r) => setTimeout(r, 200))
  }
  throw new Error(`dev server at ${url} did not come up within ${timeoutMs}ms`)
}

async function main(): Promise<void> {
  const opts = parseArgs(process.argv.slice(2))
  console.log('[render-video] options:', opts)

  const workDir = mkdtempSync(join(opts.workDirParent, 'sinteza-render-'))
  const framesDir = join(workDir, 'frames')
  execFileSync('mkdir', ['-p', framesDir])

  // 1. Audio: extract from mp4 if needed, else use the WAV directly.
  const isMp4 = extname(opts.input).toLowerCase() !== '.wav'
  const wavPath = isMp4 ? join(workDir, 'audio.wav') : opts.input
  if (isMp4) {
    console.log('[render-video] extracting audio from', opts.input)
    extractAudioWav(opts.input, wavPath)
  }

  // 2. Sidecar: use the given one, or analyze the track (sidecar-driven by
  // default per the user's explicit ask).
  const sidecar = loadOrGenerateSidecar(wavPath, opts.sidecarPath)
  console.log(`[render-video] sidecar: ${sidecar.duration.toFixed(1)}s, ${sidecar.tempo.toFixed(1)}bpm`)

  // 3. Build the worklet (feature-worklet.js is served from public/ but
  // unused in sidecar mode — built anyway since it's a cheap, idempotent
  // step other dev entry points already run first) and start the
  // render-video harness's OWN Vite dev server (not a static build — a
  // static `vite build` mis-bundles the new Worker(new URL(...)) reference
  // as a raw .ts file; the dev server transpiles on the fly, the same
  // proven pattern tools/patchbay-editor/ already relies on).
  // Everything from here on writes into workDir (a multi-GB JPEG frame
  // sequence for a full track) — wrapped so it's ALWAYS removed on the way
  // out, success or failure. A failed run leaking its frame directory is
  // exactly what filled the disk earlier this session (see AGENTS.md's own
  // note) — cleanup can't be conditional on success.
  try {
  execFileSync('npx', ['vite', 'build', '--config', 'vite.worklet.config.ts'], { stdio: 'inherit' })
  // A random port per run (not a fixed one) so two invocations of this
  // tool never collide — and the local `vite` binary directly, not `npx
  // vite`: npx's own child-process layer doesn't reliably forward
  // SIGTERM to what it execs, which is exactly what let a previous run's
  // dev server leak past its own process exiting (see AGENTS.md's own
  // note on this real bug, found and fixed in this same session).
  // `detached: true` + killing the negative pid (the whole process group)
  // below is what actually guarantees a clean exit even if `vite` itself
  // spawns further children.
  const port = 5000 + Math.floor(Math.random() * 5000)
  const viteBin = resolve('node_modules/.bin/vite')
  const devServer = spawn(viteBin, ['--config', 'vite.render-video.config.ts', '--port', String(port), '--strictPort'], {
    stdio: ['ignore', 'pipe', 'pipe'],
    detached: true,
  })
  devServer.stdout?.on('data', (d) => process.stdout.write(`[vite] ${d}`))
  devServer.stderr?.on('data', (d) => process.stderr.write(`[vite] ${d}`))

  let browser: Browser | null = null
  try {
    await waitForServer(`http://localhost:${port}/`, 20000)

    if (!existsSync(opts.chromePath)) {
      throw new Error(`Chrome not found at ${opts.chromePath} — pass --chrome /path/to/chrome`)
    }
    browser = await puppeteer.launch({
      executablePath: opts.chromePath,
      headless: true,
      // Real GPU acceleration (this machine has a real Intel Iris Xe iGPU
      // at /dev/dri/renderD128, confirmed via `glxinfo`) via ANGLE's
      // OpenGL-over-EGL backend against the real Mesa driver — NOT
      // SwiftShader (software/CPU rendering), which is what made the first
      // full-song attempt in this session take ~5-6 hours: a full memory-
      // field/bloom/composite GL pipeline, software-rendered per pixel at
      // 1080p, is genuinely expensive. `--ignore-gpu-blocklist` is needed
      // because headless Chrome's default GPU allowlist doesn't include
      // every real driver by default.
      args: ['--use-gl=angle', '--use-angle=gl-egl', '--enable-webgl', '--ignore-gpu-blocklist', '--enable-gpu-rasterization', '--no-sandbox'],
    })
    let page: Page = await browser.newPage()
    page.on('console', (msg) => console.log('[page]', msg.text()))
    page.on('pageerror', (err) => console.error('[page error]', err))

    const renderWidth = Math.round(opts.width * 0.64) // center column — see harness.ts's SIDE_FRACTION
    const renderHeight = opts.height
    const isfSource = opts.isfPath ? readFileSync(opts.isfPath, 'utf8') : null

    // Runs the full page-load + init + sidecar + shader + fixtures
    // sequence against whatever `page` currently is — factored out so a
    // mid-render page crash/reload (a real, observed failure: frame 6748
    // of a full-song attempt failed "no sidecar loaded" on every retry,
    // because Chrome silently reloaded the page and nothing re-ran this
    // sequence afterward) can be recovered from by just calling this
    // again, rather than failing the entire multi-hundred-second render
    // over one bad moment.
    async function initPageState(p: Page): Promise<void> {
      await p.goto(`http://localhost:${port}/`, { waitUntil: 'load' })
      await p.waitForFunction(() => (window as unknown as { __ready?: boolean }).__ready === true, { timeout: 10000 })

      await p.evaluate(
        (rw, rh, ow, oh) => (window as unknown as { __init: (a: number, b: number, c: number, d: number) => Promise<void> }).__init(rw, rh, ow, oh),
        renderWidth,
        renderHeight,
        opts.width,
        opts.height,
      )

      await p.evaluate((s) => (window as unknown as { __loadSidecar: (s: unknown) => Promise<void> }).__loadSidecar(s), sidecar)

      if (isfSource) {
        const result = await p.evaluate(
          (src) => (window as unknown as { __loadIsfShader: (s: string) => Promise<{ ok: boolean; message?: string }> }).__loadIsfShader(src),
          isfSource,
        )
        if (!result.ok) throw new Error(`ISF shader failed to load: ${result.message}`)
        console.log('[render-video] loaded ISF shader', opts.isfPath)

        // Auto-wire every hysteresisSignal input the shader itself declares
        // (each one already names its own bus signal via SIGNAL) — a real
        // production graph still requires the user to author routes by hand
        // in the editor (docs/isf-shaders.md), but this render tool's whole
        // job is exercising everything a shader can take, so hand-picking
        // just one input here (as an earlier version of this tool did) would
        // silently leave the rest of a richly-driven shader static.
        const doc = parseIsf(isfSource)
        const routes = doc.inputs
          .filter((input): input is Extract<typeof input, { type: 'hysteresisSignal' }> => input.type === 'hysteresisSignal')
          .map((input) => ({ signal: input.signal, target: `isf.${input.name}` }))
        console.log(`[render-video] auto-routing ${routes.length} hysteresisSignal input(s):`, routes.map((r) => `${r.signal}->${r.target}`).join(', '))
        await p.evaluate(
          (rs) => (window as unknown as { __setScreenGraphWithHysteresisRoutes: (r: { signal: string; target: string }[]) => void }).__setScreenGraphWithHysteresisRoutes(rs),
          routes,
        )
      }

      if (opts.debugOverlay || opts.fixtureOverlay) {
        await p.evaluate(() => (window as unknown as { __setupDemoFixtures: () => void }).__setupDemoFixtures())
      }
    }

    await initPageState(page)

    // 4. Deterministic frame loop — fully offline, no real-time wait.
    const effectiveDuration = opts.duration ? Math.min(opts.duration, sidecar.duration) : sidecar.duration
    const totalFrames = Math.ceil(effectiveDuration * opts.fps)
    const dt = 1 / opts.fps
    console.log(`[render-video] rendering ${totalFrames} frames at ${opts.fps}fps...`)
    // Real, observed flake (AGENTS.md's own note): under sustained rapid
    // back-to-back frame rendering, `canvas.convertToBlob()`'s Blob
    // occasionally throws `NotReadableError` when read — a rare
    // Chrome-internal timing issue, not a logic bug (never reproduced in
    // any short smoke test, only surfaced after ~90 frames of continuous
    // load). A few retries clear it every time observed.
    //
    // A second, more serious real failure this session's own full-song
    // attempt hit: Chrome silently reloaded the page mid-render (frame
    // 6748/12111), wiping every piece of harness state — every retry after
    // that failed identically ("no sidecar loaded") because nothing ever
    // re-ran init/loadSidecar/loadIsfShader on the reloaded page. Recovered
    // here by checking a real readiness signal (`__renderReady` — see
    // harness.ts's own comment on why this has to be more specific than
    // `__ready`) before each retry, and re-running the whole
    // `initPageState` sequence when it's false OR the check itself throws
    // (a fully detached/crashed page context) — not just retrying the same
    // doomed `__renderFrame` call again.
    const MAX_FRAME_RETRIES = 5
    for (let i = 0; i < totalFrames; i++) {
      const t = i * dt
      let result: { jpeg: string } | null = null
      let lastErr: unknown = null
      for (let attempt = 0; attempt < MAX_FRAME_RETRIES; attempt++) {
        try {
          if (attempt > 0) {
            const ready = await page
              .evaluate(() => (window as unknown as { __renderReady?: () => boolean }).__renderReady?.() === true)
              .catch(() => false)
            if (!ready) {
              console.warn(`[render-video] frame ${i}: page state lost (crash/reload) — re-initializing before retry`)
              try {
                await initPageState(page)
              } catch (reinitErr) {
                // The page itself is dead (a real crash, not just a
                // navigation/reload) — even re-navigating it failed.
                // Replace it with a fresh page rather than giving up.
                console.warn(`[render-video] frame ${i}: page re-init failed too (${reinitErr instanceof Error ? reinitErr.message : String(reinitErr)}) — opening a new page`)
                page = await browser!.newPage()
                page.on('console', (msg) => console.log('[page]', msg.text()))
                page.on('pageerror', (err) => console.error('[page error]', err))
                await initPageState(page)
              }
            }
          }
          result = await page.evaluate(
            (positionSec, frameDt, showDebug, showFixtures) =>
              (window as unknown as { __renderFrame: (t: number, d: number, sd: boolean, sf: boolean) => Promise<{ jpeg: string }> }).__renderFrame(
                positionSec,
                frameDt,
                showDebug,
                showFixtures,
              ),
            t,
            dt,
            opts.debugOverlay,
            opts.fixtureOverlay,
          )
          break
        } catch (err) {
          lastErr = err
          console.warn(`[render-video] frame ${i} attempt ${attempt + 1} failed: ${err instanceof Error ? err.message : String(err)}`)
          await new Promise((r) => setTimeout(r, 100))
        }
      }
      if (!result) throw new Error(`frame ${i} failed after ${MAX_FRAME_RETRIES} attempts: ${lastErr instanceof Error ? lastErr.message : String(lastErr)}`)
      const base64 = result.jpeg.replace(/^data:image\/jpeg;base64,/, '')
      writeFileSync(join(framesDir, `frame_${String(i).padStart(6, '0')}.jpg`), Buffer.from(base64, 'base64'))
      if (i % opts.fps === 0) console.log(`[render-video] ${(t / effectiveDuration * 100).toFixed(1)}% (${i}/${totalFrames})`)
    }
    console.log('[render-video] all frames rendered, muxing with ffmpeg...')
  } finally {
    if (browser) await browser.close()
    // Kill the whole detached process group (negative pid), not just the
    // immediate child — `vite` itself can spawn further children, and a
    // plain devServer.kill() only ever reached the direct child, which is
    // exactly how a previous run's dev server leaked past this process
    // exiting (see AGENTS.md's own note on this bug).
    if (devServer.pid) {
      try {
        process.kill(-devServer.pid, 'SIGTERM')
      } catch {
        devServer.kill() // fallback if the group kill itself fails (e.g. already dead)
      }
    }
  }

  // 5. Mux frames + real audio into the final video. Bitrate-targeted
  // (--video-bitrate) when given, so a size budget is hit directly at the
  // actual render resolution — one lossy encode, not a render-at-1080p-
  // then-downscale-recompress pass (which measurably hurt legibility of
  // fine detail like the overlay text/laser icons — see AGENTS.md).
  const videoArgs = opts.videoBitrateKbps
    ? ['-c:v', 'libx264', '-b:v', `${opts.videoBitrateKbps}k`, '-maxrate', `${Math.round(opts.videoBitrateKbps * 1.15)}k`, '-bufsize', `${opts.videoBitrateKbps * 2}k`]
    : ['-c:v', 'libx264']
  execFileSync(
    'ffmpeg',
    [
      '-y',
      '-framerate', String(opts.fps),
      '-i', join(framesDir, 'frame_%06d.jpg'),
      '-i', wavPath,
      ...videoArgs,
      '-pix_fmt', 'yuv420p',
      '-c:a', 'aac',
      '-b:a', `${opts.audioBitrateKbps}k`,
      '-shortest',
      opts.out,
    ],
    { stdio: 'inherit' },
  )
  } finally {
    rmSync(workDir, { recursive: true, force: true })
  }
  console.log('[render-video] wrote', opts.out)
}

main().catch((err) => {
  console.error('[render-video] failed:', err)
  process.exitCode = 1
})
