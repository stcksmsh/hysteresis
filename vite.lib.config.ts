import { defineConfig } from 'vite'

// Library build: src/index.ts -> dist/index.js, the package SINTEZA_VIZ.md §1
// describes (init(canvas, opts): VizInstance). `publicDir` defaults to
// 'public', so this also copies public/worklets/feature-worklet.js (built
// by vite.worklet.config.ts) and public/render-worker.js (built by
// vite.render-worker.config.ts) into dist/ alongside it — see
// workletUrl/renderWorkerUrl's defaults in src/index.ts.
export default defineConfig({
  worker: {
    format: 'es',
  },
  build: {
    target: 'es2022',
    outDir: 'dist',
    lib: {
      entry: new URL('src/index.ts', import.meta.url).pathname,
      formats: ['es'],
      fileName: () => 'index.js',
    },
  },
})
