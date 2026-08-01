#!/usr/bin/env node
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import type { Timeline, TimelineEvent, TimelineTrack } from '../../src/shared/timeline'
import { HYST_FORMAT_VERSION } from '../../src/shared/timeline'
import type { RawProject } from './project-schema'
import { decodeWavFile } from './wav'
import { analyzeStem } from './analyze'

function encodeEnvelope(bytes: Uint8Array): string {
  return Buffer.from(bytes.buffer, bytes.byteOffset, bytes.byteLength).toString('base64')
}

function readProject(projectPath: string): RawProject {
  const raw = JSON.parse(readFileSync(projectPath, 'utf8')) as RawProject
  if (!Array.isArray(raw.tracks) || typeof raw.duration !== 'number') {
    throw new Error(`${projectPath}: does not look like a project.json export`)
  }
  return raw
}

// Reads a REAPER export (project.json + stems, produced by the ReaScript) and
// bakes it into a single song.hyst timeline. Every stem is analysed in
// isolation, so loudness/tone/pan-timing here are exact where the realtime
// worklet can only ever infer them from the mixed signal.
export function compile(projectPath: string): Timeline {
  const project = readProject(projectPath)
  const projectDir = dirname(projectPath)

  const tracks: TimelineTrack[] = []
  const events: TimelineEvent[] = []
  let envelopeRate = 20
  const envelopeTracks: { level: string; tone: string }[] = []

  project.tracks.forEach((rawTrack, trackIndex) => {
    const stemPath = join(projectDir, rawTrack.stem)
    const wav = decodeWavFile(stemPath)
    const analysis = analyzeStem(wav)
    envelopeRate = analysis.envelopeRate

    tracks.push({
      name: rawTrack.name,
      pan: rawTrack.pan,
      tone: analysis.medianTone,
    })

    for (const hit of analysis.events) {
      events.push({
        t: hit.t,
        track: trackIndex,
        level: hit.level,
        tone: hit.tone,
        pan: rawTrack.pan,
      })
    }

    envelopeTracks.push({
      level: encodeEnvelope(analysis.envelopeLevel),
      tone: encodeEnvelope(analysis.envelopeTone),
    })
  })

  events.sort((a, b) => a.t - b.t)

  return {
    version: HYST_FORMAT_VERSION,
    duration: project.duration,
    tempoMap: project.tempoMap,
    markers: project.markers,
    tracks,
    events,
    envelopes: { rate: envelopeRate, tracks: envelopeTracks },
  }
}

function main(): void {
  const [, , inputArg, outputArg] = process.argv
  if (!inputArg) {
    console.error('usage: compile <path/to/.visualizer/project.json> [output.hyst]')
    process.exitCode = 1
    return
  }

  const projectPath = resolve(inputArg)
  const outputPath = resolve(outputArg ?? join(dirname(projectPath), 'song.hyst'))

  const timeline = compile(projectPath)
  writeFileSync(outputPath, JSON.stringify(timeline))

  const eventCount = timeline.events.length
  const trackCount = timeline.tracks.length
  console.log(`wrote ${outputPath} — ${trackCount} tracks, ${eventCount} events, ${timeline.duration.toFixed(1)}s`)
}

// Only run as a CLI, not when imported by tests.
if (import.meta.url === `file://${process.argv[1]}`) {
  main()
}
