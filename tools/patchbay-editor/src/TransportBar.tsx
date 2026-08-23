import { useState } from 'react'
import type { PlaybackState } from './runtime-bridge'

function formatTime(sec: number): string {
  if (!Number.isFinite(sec) || sec < 0) return '–:––'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

interface TransportBarProps {
  playback: PlaybackState
  onTogglePlay: () => void
  onSeek: (sec: number) => void
  onFileChosen: (e: React.ChangeEvent<HTMLInputElement>) => void
  variant: 'demo' | 'corner'
}

// One control, two placements (see styles.css's .transport-bar-demo/-corner)
// — never two separate implementations to keep in sync. Local `scrub` state
// shadows the real playback.currentTime only while the user is actively
// dragging the range input, so the bar tracks the pointer smoothly instead
// of fighting incoming 'timeupdate' events (which would otherwise snap the
// thumb back mid-drag); committed via onSeek on pointer-up, matching how a
// real player's scrubber behaves.
export function TransportBar({ playback, onTogglePlay, onSeek, onFileChosen, variant }: TransportBarProps) {
  const [scrub, setScrub] = useState<number | null>(null)
  const duration = Number.isFinite(playback.duration) ? playback.duration : 0
  const shown = scrub ?? playback.currentTime

  return (
    <div className={`transport-bar transport-bar-${variant}`}>
      <button className="transport-play" onClick={onTogglePlay} title={playback.playing ? 'Pause' : 'Play'} disabled={duration === 0}>
        {playback.playing ? '⏸' : '▶'}
      </button>
      <span className="transport-time mono">{formatTime(shown)}</span>
      <input
        type="range"
        className="transport-seek"
        min={0}
        max={duration || 1}
        step={0.01}
        value={Math.min(shown, duration || 1)}
        disabled={duration === 0}
        onChange={(e) => setScrub(Number(e.target.value))}
        onPointerUp={(e) => {
          const v = Number((e.target as HTMLInputElement).value)
          onSeek(v)
          setScrub(null)
        }}
      />
      <span className="transport-time mono">{formatTime(duration)}</span>
      <label className="transport-file-btn" title="Load a track">
        📁
        <input type="file" accept="audio/*" onChange={onFileChosen} />
      </label>
    </div>
  )
}
