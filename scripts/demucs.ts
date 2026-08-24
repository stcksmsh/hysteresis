import { execFileSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { basename, extname, join } from 'node:path'

// AGENTS.md §4.3/§4.5 step 5 — offline source separation, shelled out to
// the real Python Demucs CLI (user's explicit choice: reuse the real,
// well-tested reference implementation rather than a JS port or an ONNX
// model bundle). This is a manual, per-track, offline tool run — NOT part
// of the shipped browser package, CI, or the production render path
// (`src/render/**`/`src/index.ts` never import this file) — so a hard,
// clear failure when Python/demucs aren't installed is correct, not a gap
// to silently work around. `scripts/analyze.ts --stems` is the only caller.
export interface DemucsStemPaths {
  vocals: string
  drums: string
  bass: string
  other: string
}

const STEM_NAMES: Array<keyof DemucsStemPaths> = ['vocals', 'drums', 'bass', 'other']
const DEMUCS_MODEL = 'htdemucs' // the standard 4-stem model (vocals/drums/bass/other)

// Runs `python3 -m demucs -n htdemucs -o <outDir> <inputWavPath>` and
// returns the 4 stem WAV paths Demucs writes to
// `<outDir>/htdemucs/<input-basename>/{vocals,drums,bass,other}.wav`
// (Demucs' own fixed output layout — not something this wrapper controls).
export function runDemucsSeparation(inputWavPath: string, outDir: string): DemucsStemPaths {
  try {
    execFileSync('python3', ['-m', 'demucs', '-n', DEMUCS_MODEL, '-o', outDir, inputWavPath], {
      stdio: 'inherit',
    })
  } catch (err) {
    const cause = err instanceof Error ? err.message : String(err)
    throw new Error(
      `--stems requires Python + Demucs installed and on PATH (tried "python3 -m demucs"). ` +
        `Install with: pip install demucs\nUnderlying error: ${cause}`,
    )
  }

  const trackSlug = basename(inputWavPath, extname(inputWavPath))
  const stemDir = join(outDir, DEMUCS_MODEL, trackSlug)
  const paths: DemucsStemPaths = {
    vocals: join(stemDir, 'vocals.wav'),
    drums: join(stemDir, 'drums.wav'),
    bass: join(stemDir, 'bass.wav'),
    other: join(stemDir, 'other.wav'),
  }

  for (const name of STEM_NAMES) {
    if (!existsSync(paths[name])) {
      throw new Error(`demucs ran but expected stem output is missing: ${paths[name]}`)
    }
  }
  return paths
}
