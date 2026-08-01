import type { AudioEngine } from '../audio/AudioEngine'
import { SCENE_OPTIONS, DEFAULT_SCENE_ID } from '../shared/scenes'

export function mountControls(
  container: HTMLElement,
  engine: AudioEngine,
  onSceneChange?: (sceneId: string) => void,
): void {
  const wrap = document.createElement('div')
  wrap.style.cssText = 'position:fixed;left:16px;bottom:16px;display:flex;gap:8px;align-items:center'

  const fileInput = document.createElement('input')
  fileInput.type = 'file'
  fileInput.accept = 'audio/*'
  fileInput.style.color = '#eee'

  const playPause = document.createElement('button')
  playPause.textContent = 'Pause'
  playPause.disabled = true

  fileInput.addEventListener('change', async () => {
    const file = fileInput.files?.[0]
    if (!file) return
    await engine.loadAndPlay(file)
    playPause.disabled = false
    playPause.textContent = 'Pause'
  })

  playPause.addEventListener('click', async () => {
    if (engine.isPlaying) {
      await engine.pause()
      playPause.textContent = 'Resume'
    } else {
      await engine.resume()
      playPause.textContent = 'Pause'
    }
  })

  wrap.appendChild(fileInput)
  wrap.appendChild(playPause)

  if (onSceneChange) {
    const scenePicker = document.createElement('select')
    scenePicker.setAttribute('aria-label', 'Visual scene')
    for (const option of SCENE_OPTIONS) {
      const el = document.createElement('option')
      el.value = option.id
      el.textContent = option.label
      scenePicker.appendChild(el)
    }
    scenePicker.value = DEFAULT_SCENE_ID
    scenePicker.addEventListener('change', () => onSceneChange(scenePicker.value))
    wrap.appendChild(scenePicker)
  }

  container.appendChild(wrap)
}
