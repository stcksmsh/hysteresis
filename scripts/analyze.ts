#!/usr/bin/env node
import { writeFileSync, mkdtempSync, rmSync } from 'node:fs'
import { basename, extname, resolve, join } from 'node:path'
import { tmpdir } from 'node:os'
import { decodeWavFile } from './wav'
import { analyzeMix, computeStemPresence } from './structure'
import { runDemucsSeparation } from './demucs'

// Offline analysis tool (SINTEZA_VIZ.md §6): one WAV master in, one
// <slug>.sidecar.json out. This repo produces it; the host (IO page) serves
// it as a static asset and calls loadSidecar(url) on trackchange.
//
// --stems (AGENTS.md §4.3/§4.5 step 5, opt-in): also runs offline Demucs
// source separation and bakes vocalPresence/drumsPresence/bassPresence/
// otherPresence/leadPresence into a schema-3 sidecar. Needs a real
// Python + `demucs` install (`pip install demucs`) on the machine running
// this script — a manual, per-track, offline step, same posture as the
// rest of this tool; not part of the shipped browser package or CI.
function main(): void {
  const args = process.argv.slice(2)
  const stemsFlagIndex = args.indexOf('--stems')
  const withStems = stemsFlagIndex >= 0
  if (withStems) args.splice(stemsFlagIndex, 1)
  const [inputArg, outputArg] = args

  if (!inputArg) {
    console.error('usage: analyze <path/to/master.wav> [output.sidecar.json] [--stems]')
    process.exitCode = 1
    return
  }

  const inputPath = resolve(inputArg)
  const wav = decodeWavFile(inputPath)
  const sidecar = analyzeMix(wav)

  if (withStems) {
    const outDir = mkdtempSync(join(tmpdir(), 'sinteza-demucs-'))
    try {
      const stemPaths = runDemucsSeparation(inputPath, outDir)
      sidecar.stemPresence = computeStemPresence({
        vocals: decodeWavFile(stemPaths.vocals),
        drums: decodeWavFile(stemPaths.drums),
        bass: decodeWavFile(stemPaths.bass),
        other: decodeWavFile(stemPaths.other),
      })
    } finally {
      rmSync(outDir, { recursive: true, force: true })
    }
  }

  const slug = basename(inputArg, extname(inputArg))
  const outputPath = resolve(outputArg ?? `${slug}.sidecar.json`)
  writeFileSync(outputPath, JSON.stringify(sidecar))

  console.log(
    `wrote ${outputPath} — ${sidecar.tempo.toFixed(1)}bpm, ${sidecar.beats.length} beats, ` +
      `${sidecar.events.length} events, ${sidecar.onsets.length} onsets, ${sidecar.sections.length} sections, ` +
      `${sidecar.duration.toFixed(1)}s${sidecar.stemPresence ? ', with stem presence' : ''}`,
  )
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main()
}
