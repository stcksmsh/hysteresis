import { useEffect, useRef } from 'react'
import { EditorState, type Extension } from '@codemirror/state'
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { bracketMatching, indentOnInput, syntaxHighlighting, defaultHighlightStyle } from '@codemirror/language'
import { json } from '@codemirror/lang-json'
import { javascript } from '@codemirror/lang-javascript'
import { cpp } from '@codemirror/lang-cpp'
import { oneDark } from '@codemirror/theme-one-dark'

export type CodeLanguage = 'json' | 'javascript' | 'glsl'

// GLSL has no dedicated CodeMirror 6 grammar package — @codemirror/lang-cpp's
// C-like grammar (braces, semicolons, C-style keywords/numbers/types) is a
// close enough approximation for a shader body to be genuinely useful
// (bracket matching, indent-on-input, real token coloring for the parts of
// the language GLSL shares with C) without pulling in or hand-authoring a
// full GLSL grammar for one dev tool.
function langExtension(lang: CodeLanguage): Extension {
  switch (lang) {
    case 'json':
      return json()
    case 'javascript':
      return javascript()
    case 'glsl':
      return cpp()
  }
}

export interface CodeEditorProps {
  value: string
  onChange: (v: string) => void
  language: CodeLanguage
  readOnly?: boolean
  title?: string
}

// A real CodeMirror 6 instance (syntax highlighting, line numbers, bracket
// matching, undo/redo) wrapped for React — this project's own confirmed
// tradeoff: the one deliberate new dependency this redesign adds, since
// there's no native browser primitive for real code editing the way there
// is for e.g. `resize`/drag-and-drop, which this tool already leans on
// instead of a library elsewhere.
export function CodeEditor({ value, onChange, language, readOnly, title }: CodeEditorProps) {
  const hostRef = useRef<HTMLDivElement>(null)
  const viewRef = useRef<EditorView | null>(null)
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange

  useEffect(() => {
    if (!hostRef.current) return
    const state = EditorState.create({
      doc: value,
      extensions: [
        lineNumbers(),
        highlightActiveLine(),
        highlightActiveLineGutter(),
        history(),
        bracketMatching(),
        indentOnInput(),
        syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
        keymap.of([...defaultKeymap, ...historyKeymap, indentWithTab]),
        langExtension(language),
        oneDark,
        EditorView.editable.of(!readOnly),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) onChangeRef.current(update.state.doc.toString())
        }),
      ],
    })
    const view = new EditorView({ state, parent: hostRef.current })
    viewRef.current = view
    return () => view.destroy()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- switching `language` intentionally recreates the editor (a different tab = a fresh instance); `value` is deliberately not a dep here, see the sync effect below
  }, [language])

  // Syncs an externally-driven value change (switching files, loading a
  // template, tab-switch restoring saved text) into the already-live editor
  // without recreating it on every keystroke — the updateListener above is
  // what reports keystrokes back OUT via onChange, so re-applying them here
  // too would fight the user's own typing / reset cursor position constantly.
  useEffect(() => {
    const view = viewRef.current
    if (!view) return
    const current = view.state.doc.toString()
    if (current === value) return
    view.dispatch({ changes: { from: 0, to: current.length, insert: value } })
  }, [value])

  return <div ref={hostRef} className="ui-code-editor" title={title} />
}
