import { defineConfig } from 'vite'

// Library build: src/index.ts -> dist/index.js, the package HYSTERESIS.md §1
// describes (init(canvas, opts): HysteresisHandle). `publicDir` defaults to
// 'public', so this also copies public/worklets/feature-worklet.js (built
// by vite.worklet.config.ts) into dist/worklets/ alongside it — see
// AudioEngine's workletUrl default in src/index.ts.
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
