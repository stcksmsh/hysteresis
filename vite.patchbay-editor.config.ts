import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import { writeFileSync, mkdirSync } from 'node:fs'
import { resolve, normalize } from 'node:path'

// Task #5: a real "Save" button writes an actual, committable .ts file to
// disk instead of a copy-paste-from-a-textarea workaround. Dev-only (this
// plugin only runs under `npm run patchbay`'s dev server, never in
// build/build:lib) and deliberately restricted to one directory — this is
// local-machine-only tooling, but there's no reason to accept an arbitrary
// path from the page when a fixed prefix does the job just as well.
const SAVE_DIR_PREFIX = 'src/render/conductor/patchbay/editor/saved/'
function patchbaySavePlugin(): Plugin {
  return {
    name: 'patchbay-save',
    configureServer(server) {
      server.middlewares.use('/__patchbay-save', (req, res) => {
        if (req.method !== 'POST') {
          res.statusCode = 405
          res.end('POST only')
          return
        }
        let body = ''
        req.on('data', (chunk) => (body += chunk))
        req.on('end', () => {
          try {
            const { filename, source } = JSON.parse(body) as { filename: string; source: string }
            // Only a bare filename (letters/digits/dash/underscore + .ts),
            // no path separators — rules out escaping SAVE_DIR_PREFIX via
            // "../" or an absolute path.
            if (!/^[a-zA-Z0-9_-]+\.ts$/.test(filename)) {
              res.statusCode = 400
              res.end('invalid filename')
              return
            }
            const repoRoot = resolve(import.meta.dirname)
            const dir = resolve(repoRoot, SAVE_DIR_PREFIX)
            const fullPath = normalize(resolve(dir, filename))
            if (!fullPath.startsWith(dir)) {
              res.statusCode = 400
              res.end('invalid path')
              return
            }
            mkdirSync(dir, { recursive: true })
            writeFileSync(fullPath, source, 'utf-8')
            res.statusCode = 200
            res.end(JSON.stringify({ ok: true, path: `${SAVE_DIR_PREFIX}${filename}` }))
          } catch (err) {
            res.statusCode = 500
            res.end(String(err instanceof Error ? err.message : err))
          }
        })
      })
    },
  }
}

// Dev-only tool (SINTEZA_SIGNAL_BUS.md §8's patchbay editor UI, built once
// the screen piece itself was stable). Entirely separate from the real
// package's build: its own Vite config, its own React dependency, its own
// dev server (`npm run patchbay`). Never referenced by vite.config.ts/
// vite.lib.config.ts/vite.render-worker.config.ts, so `npm run build`/
// `build:lib` (what actually ships) can't accidentally pull any of this in.
export default defineConfig({
  root: 'tools/patchbay-editor',
  // The real project's public/ dir (worklets/feature-worklet.js,
  // render-worker.js — both built by `npm run build:worklet`/
  // `build:render-worker`, which `npm run patchbay` runs first) — NOT
  // tools/patchbay-editor/public/, which doesn't exist. Vite resolves
  // publicDir relative to `root` above, so this has to walk back out.
  publicDir: '../../public',
  plugins: [react(), patchbaySavePlugin()],
  worker: {
    format: 'es',
  },
  build: {
    target: 'es2022',
    outDir: '../../dist-patchbay-editor',
    emptyOutDir: true,
  },
})
