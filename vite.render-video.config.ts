import { defineConfig } from 'vite'

// Dev-only offline-render harness (AGENTS.md's "render-video" tool). No
// React, no UI — this page is driven entirely by scripts/render-video.ts's
// Puppeteer automation via page.evaluate() calls into harness.ts's
// window.__render* functions. Same posture as vite.patchbay-editor.config.ts:
// its own root/build, never referenced by vite.config.ts/vite.lib.config.ts/
// vite.render-worker.config.ts, so the real shipped package can't
// accidentally pull any of this in.
export default defineConfig({
  root: 'tools/render-video',
  // The real project's public/ dir (worklets/feature-worklet.js — built by
  // `npm run build:worklet`, which scripts/render-video.ts runs first via
  // the same prebuild step every other dev entry point relies on).
  publicDir: '../../public',
  worker: {
    format: 'es',
  },
  build: {
    target: 'es2022',
    outDir: '../../dist-render-video',
    emptyOutDir: true,
  },
})
