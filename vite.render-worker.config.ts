import { defineConfig } from 'vite'

// render-worker.ts is instantiated as `new Worker(new URL('./render-worker.ts',
// import.meta.url), { type: 'module' })` in src/index.ts — Vite's official
// worker-bundling pattern (https://vite.dev/guide/features.html#web-workers).
// Left as a literal inline `new URL(...)`, Vite's lib build (vite.lib.config.ts)
// statically detects it and bakes an ABSOLUTE path to its own emitted chunk
// into dist/index.js. That path resolves against wherever dist/index.js is
// SERVED FROM at runtime — fine for the dev harness (same-origin), broken
// the moment this package is installed as a dependency elsewhere and its
// dist/index.js gets re-bundled into a different app's own output (the
// chunk never gets copied there, and the baked absolute path 404s).
//
// Same fix as the AudioWorklet (vite.worklet.config.ts): prebuild as its
// own standalone single-file ES module into public/, so the default
// `new URL('./render-worker.js', import.meta.url)` in src/index.ts (built
// via an indirected, non-literal call Vite's worker-detection doesn't
// pattern-match — see the RENDER_WORKER_PATH comment there) survives
// unrewritten and portable wherever this package ends up bundled.
export default defineConfig({
  publicDir: false,
  build: {
    target: 'es2022',
    outDir: 'public',
    emptyOutDir: false,
    lib: {
      entry: new URL('src/render/worker/render-worker.ts', import.meta.url).pathname,
      formats: ['es'],
      fileName: () => 'render-worker.js',
    },
    rollupOptions: {
      output: {
        // single self-contained file, no code-splitting/chunking
        codeSplitting: false,
      },
    },
  },
})
