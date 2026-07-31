import { defineConfig } from 'vite'

// Vite's `new URL(..., import.meta.url)` idiom only special-cases the
// `new Worker()` / `new SharedWorker()` constructors — it does NOT bundle
// `audioWorklet.addModule(url)` targets. Left alone, the worklet's raw
// TypeScript source (including its unresolved `import 'fft.js'`) gets
// base64-inlined as an opaque asset instead of compiled/bundled, which
// fails at runtime. So the AudioWorklet is built as its own standalone
// ES module via a separate lib-mode build, emitted into public/worklets/
// with a stable (non-hashed) filename, then picked up as a static asset
// by the main `vite build` (files in public/ are copied to dist/ as-is).
export default defineConfig({
  publicDir: false,
  build: {
    target: 'es2022',
    outDir: 'public/worklets',
    emptyOutDir: false,
    lib: {
      entry: new URL('src/audio/worklet/feature-worklet.ts', import.meta.url).pathname,
      formats: ['es'],
      fileName: () => 'feature-worklet.js',
    },
    rollupOptions: {
      output: {
        // single self-contained file, no code-splitting/chunking
        codeSplitting: false,
      },
    },
  },
})
