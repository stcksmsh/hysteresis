import type { SaveResult } from '../serialize-config'

// Sibling to serialize-config.ts's saveToFile — a separate endpoint (not the
// same one) since shader files live in a different, real, checked-in
// directory (examples/isf/) with different filename rules (.hyst/.fs, not
// .ts) than the graph-config save path's src/render/conductor/patchbay/
// editor/saved/ sandbox. See vite.patchbay-editor.config.ts's
// patchbaySaveShaderPlugin for the matching server-side restriction.
export async function saveShaderToFile(filename: string, source: string): Promise<SaveResult> {
  try {
    const res = await fetch('/__patchbay-save-shader', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename, source }),
    })
    const text = await res.text()
    if (!res.ok) return { ok: false, message: text }
    const parsed = JSON.parse(text) as { ok: true; path: string }
    return { ok: true, path: parsed.path }
  } catch (err) {
    return { ok: false, message: err instanceof Error ? err.message : String(err) }
  }
}
