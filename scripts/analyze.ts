#!/usr/bin/env node
import { writeFileSync } from 'node:fs'
import { basename, extname, resolve } from 'node:path'
import { decodeWavFile } from './wav'
import { analyzeMix } from './structure'

// Offline analysis tool (SINTEZA_VIZ.md §6): one WAV master in, one
// <slug>.sidecar.json out. This repo produces it; the host (IO page) serves
// it as a static asset and calls loadSidecar(url) on trackchange.
function main(): void {
  const [, , inputArg, outputArg] = process.argv
  if (!inputArg) {
    console.error('usage: analyze <path/to/master.wav> [output.sidecar.json]')
    process.exitCode = 1
    return
  }

  const inputPath = resolve(inputArg)
  const wav = decodeWavFile(inputPath)
  const sidecar = analyzeMix(wav)

  const slug = basename(inputArg, extname(inputArg))
  const outputPath = resolve(outputArg ?? `${slug}.sidecar.json`)
  writeFileSync(outputPath, JSON.stringify(sidecar))

  console.log(
    `wrote ${outputPath} — ${sidecar.tempo.toFixed(1)}bpm, ${sidecar.beats.length} beats, ` +
      `${sidecar.events.length} events, ${sidecar.onsets.length} onsets, ${sidecar.sections.length} sections, ` +
      `${sidecar.duration.toFixed(1)}s`,
  )
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main()
}
