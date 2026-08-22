import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev-only tool (SINTEZA_SIGNAL_BUS.md §8's patchbay editor UI, built once
// the screen piece itself was stable). Entirely separate from the real
// package's build: its own Vite config, its own React dependency, its own
// dev server (`npm run patchbay`). Never referenced by vite.config.ts/
// vite.lib.config.ts/vite.render-worker.config.ts, so `npm run build`/
// `build:lib` (what actually ships) can't accidentally pull any of this in.
export default defineConfig({
  root: 'tools/patchbay-editor',
  plugins: [react()],
  worker: {
    format: 'es',
  },
  build: {
    target: 'es2022',
    outDir: '../../dist-patchbay-editor',
    emptyOutDir: true,
  },
})
