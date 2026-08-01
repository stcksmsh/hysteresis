// What the REAPER export script writes into .visualizer/project.json — raw
// project structure and stem/mix paths, with no audio analysis in it yet.
// The compiler reads this plus the WAV files it points at and produces the
// analysed, baked Timeline (src/shared/timeline.ts).
export interface RawProjectTempoMarker {
  t: number
  bpm: number
  num: number
  den: number
}

export interface RawProjectMarker {
  t: number
  end?: number
  name: string
}

export interface RawProjectTrack {
  name: string
  pan: number // -1..1, exact project value — the reason this whole path exists
  stem: string // path relative to project.json, e.g. "stems/01_Kick.wav"
}

export interface RawProject {
  duration: number
  tempoMap: RawProjectTempoMarker[]
  markers: RawProjectMarker[]
  tracks: RawProjectTrack[]
  mix: string // path relative to project.json
}
