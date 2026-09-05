import { useEffect, useRef, useState } from 'react'
import { CodeEditor } from '../ui/CodeEditor'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { Card } from '../ui/Card'
import { IconFolder, IconFile, IconSave, IconPlus, IconPlay } from '../ui/icons'
import { parseIsf } from '../../../../src/isf/parse-isf'
import type { IsfDocument } from '../../../../src/isf/types'
import { splitHystSource, buildHystSource, BLANK_HYST_DRAFT, BLANK_SCRIPT_TEMPLATE, type HystDraft } from './hyst-source'
import { saveShaderToFile } from './save-shader'
import juliaHystRaw from '../../../../examples/isf/julia.hyst?raw'
import juliaAutopilotHystRaw from '../../../../examples/isf/julia-autopilot.hyst?raw'

const TEMPLATES = [
  { name: 'julia.hyst', source: juliaHystRaw, blurb: 'Substrate + oscilloscope beam, no autopilot — the first-pass port.' },
  { name: 'julia-autopilot.hyst', source: juliaAutopilotHystRaw, blurb: 'The real thing: vortex-search navigation, spring-damped drift, perturbation-orbit deep zoom, via HYSTERESIS_SCRIPT.' },
]

type Tab = 'header' | 'glsl' | 'script'
type ParseState = { status: 'idle' } | { status: 'ok'; doc: IsfDocument } | { status: 'error'; message: string }
const PARSE_DEBOUNCE_MS = 300

export interface ShaderScreenProps {
  onApply: (source: string, fileName: string) => void
  onClear: () => void
  liveStatus: { state: 'empty' } | { state: 'loaded'; fileName: string; targets: unknown[] } | { state: 'error'; fileName: string; message: string }
}

// The centerpiece of this redesign: a real in-editor .hyst/HYSTERESIS_SCRIPT
// authoring flow. Before this, loading a shader was file-picker-only — no
// way to see or edit a shader's source, or author a HYSTERESIS_SCRIPT
// companion at all, without leaving the tool. See hyst-source.ts's own
// header comment for why the Header/GLSL/Script split is a pure text
// reshape, not a second parser — parseIsf() (the real one) is always the
// authority on whether a shader is actually valid.
export function ShaderScreen({ onApply, onClear, liveStatus }: ShaderScreenProps) {
  const [fileName, setFileName] = useState('untitled.hyst')
  const [draft, setDraft] = useState<HystDraft>(BLANK_HYST_DRAFT)
  const [tab, setTab] = useState<Tab>('header')
  const [parseState, setParseState] = useState<ParseState>({ status: 'idle' })
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveStatus, setSaveStatus] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  // Live parse feedback as you type, debounced — reuses parseIsf()'s own
  // real error messages (this format already has a "reject clearly, name
  // exactly what's wrong" discipline throughout parse-isf.ts; this just
  // surfaces it directly instead of paraphrasing it). Purely informational:
  // Apply below is gated only on the header actually being valid JSON (the
  // minimum needed to build ANY source text to send) — the real worker-side
  // parseIsf() call stays the authority on full semantic validity, exactly
  // like it already is for every other loading path in this tool.
  useEffect(() => {
    const handle = setTimeout(() => {
      const built = buildHystSource(draft)
      if (!built.ok) {
        setParseState({ status: 'error', message: built.error })
        return
      }
      try {
        const doc = parseIsf(built.source)
        setParseState({ status: 'ok', doc })
      } catch (err) {
        setParseState({ status: 'error', message: err instanceof Error ? err.message : String(err) })
      }
    }, PARSE_DEBOUNCE_MS)
    return () => clearTimeout(handle)
  }, [draft])

  function loadSource(name: string, source: string) {
    const split = splitHystSource(source)
    if ('error' in split) {
      setLoadError(`${name}: ${split.error}`)
      return
    }
    setLoadError(null)
    setFileName(name)
    setDraft(split)
    setTab('header')
  }

  function handleNew() {
    setLoadError(null)
    setFileName('untitled.hyst')
    setDraft(BLANK_HYST_DRAFT)
    setTab('header')
  }

  async function handleOpenFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    loadSource(file.name, await file.text())
  }

  function handleApply() {
    const built = buildHystSource(draft)
    if (!built.ok) return // button is disabled in this state anyway — see canApply below
    onApply(built.source, fileName)
  }

  async function handleSave() {
    const built = buildHystSource(draft)
    if (!built.ok) {
      setSaveStatus(`Save failed: ${built.error}`)
      return
    }
    const result = await saveShaderToFile(fileName, built.source)
    setSaveStatus(result.ok ? `Saved to ${result.path}` : `Save failed: ${result.message}`)
  }

  function enableScript() {
    setDraft((d) => ({ ...d, scriptText: BLANK_SCRIPT_TEMPLATE }))
    setTab('script')
  }

  const canApply = buildHystSource(draft).ok
  const hasScript = draft.scriptText.trim().length > 0

  return (
    <div className="screen screen-shaders">
      <aside className="shader-files">
        <Card title="File">
          <div className="shader-file-actions">
            <Button icon={<IconFile size={14} />} onClick={handleNew}>
              New
            </Button>
            <Button icon={<IconFolder size={14} />} onClick={() => fileRef.current?.click()}>
              Open…
            </Button>
            <input ref={fileRef} type="file" accept=".hyst,.fs,.glsl,.txt" style={{ display: 'none' }} onChange={handleOpenFile} />
          </div>
          <div className="shader-current-file mono">{fileName}</div>
          {loadError && <div className="banner banner-error">{loadError}</div>}
        </Card>

        <Card title="Templates" hint="Start from a real, checked-in example instead of a blank file.">
          <div className="shader-template-list">
            {TEMPLATES.map((t) => (
              <button key={t.name} className="shader-template" onClick={() => loadSource(t.name, t.source)}>
                <span className="shader-template-name mono">{t.name}</span>
                <span className="shader-template-blurb">{t.blurb}</span>
              </button>
            ))}
          </div>
        </Card>

        <Card title="Structure" hint="What the current draft actually declares, once it parses.">
          {parseState.status === 'ok' ? (
            <div className="shader-structure">
              <div className="shader-structure-row">
                <Badge tone="ok">valid</Badge>
                <span>
                  {parseState.doc.inputs.length} input(s) · {parseState.doc.passes.length} pass(es) · script{' '}
                  {parseState.doc.hysteresisScript ? 'yes' : 'no'}
                </span>
              </div>
              {parseState.doc.inputs.length > 0 && (
                <ul className="shader-structure-list">
                  {parseState.doc.inputs.map((i) => (
                    <li key={i.name} className="mono">
                      {i.name} <span className="shader-structure-type">{i.type === 'scriptOutput' ? `scriptOutput(${i.kind})` : i.type}</span>
                    </li>
                  ))}
                </ul>
              )}
              {parseState.doc.passes.length > 0 && (
                <ul className="shader-structure-list">
                  {parseState.doc.passes.map((p, i) => (
                    <li key={i} className="mono">
                      pass {i}: <span className="shader-structure-type">{p.kind}</span>
                      {p.target ? ` → ${p.target}` : ''}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : parseState.status === 'error' ? (
            <div className="banner banner-error" style={{ margin: 0 }}>
              {parseState.message}
            </div>
          ) : (
            <div className="empty-hint">Parsing…</div>
          )}
        </Card>
      </aside>

      <div className="shader-editor">
        <div className="shader-editor-toolbar">
          <div className="shader-tabs">
            <button className={tab === 'header' ? 'shader-tab active' : 'shader-tab'} onClick={() => setTab('header')}>
              Header
            </button>
            <button className={tab === 'glsl' ? 'shader-tab active' : 'shader-tab'} onClick={() => setTab('glsl')}>
              GLSL
            </button>
            <button className={tab === 'script' ? 'shader-tab active' : 'shader-tab'} onClick={() => setTab('script')}>
              Script{hasScript && <Badge tone="accent">on</Badge>}
            </button>
          </div>
          <div className="shader-editor-actions">
            <Button icon={<IconSave size={14} />} onClick={handleSave}>
              Save
            </Button>
            <Button variant="primary" icon={<IconPlay size={14} />} onClick={handleApply} disabled={!canApply} title={canApply ? 'Apply to the live preview (⌘/Ctrl+Enter)' : 'Fix the header JSON before applying'}>
              Apply
            </Button>
          </div>
        </div>
        {saveStatus && <div className="status-pill" style={{ alignSelf: 'flex-start' }}>{saveStatus}</div>}

        {tab === 'header' && <CodeEditor value={draft.headerText} onChange={(v) => setDraft((d) => ({ ...d, headerText: v }))} language="json" title="ISF/.hyst JSON header" />}
        {tab === 'glsl' && <CodeEditor value={draft.glslText} onChange={(v) => setDraft((d) => ({ ...d, glslText: v }))} language="glsl" title="Fullscreen pass GLSL body" />}
        {tab === 'script' &&
          (hasScript ? (
            <CodeEditor value={draft.scriptText} onChange={(v) => setDraft((d) => ({ ...d, scriptText: v }))} language="javascript" title="HYSTERESIS_SCRIPT" />
          ) : (
            <div className="shader-empty-script">
              <p className="empty-hint">No HYSTERESIS_SCRIPT on this shader — add one for anything a single-pass GLSL shader can't hold on its own (orbit tracking, target-seeking navigation, spring-damped drift).</p>
              <Button icon={<IconPlus size={14} />} onClick={enableScript}>
                Add HYSTERESIS_SCRIPT
              </Button>
            </div>
          ))}

        <div className="shader-live-status">
          {liveStatus.state === 'empty' && <span className="empty-hint">Nothing applied yet — the screen is still running its default scene.</span>}
          {liveStatus.state === 'loaded' && (
            <span>
              <Badge tone="ok">live</Badge> {liveStatus.fileName}
            </span>
          )}
          {liveStatus.state === 'error' && (
            <span>
              <Badge tone="error">rejected</Badge> {liveStatus.message}
            </span>
          )}
          {liveStatus.state !== 'empty' && (
            <Button variant="ghost" onClick={onClear}>
              Revert to Julia
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
