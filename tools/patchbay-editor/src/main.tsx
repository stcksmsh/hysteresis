import { createRoot } from 'react-dom/client'
import { App } from './App'
import './styles.css'

// Deliberately NOT wrapped in <StrictMode>: its dev-mode double-invoke of
// effects (mount -> cleanup -> mount, to catch non-idempotent effects)
// assumes an effect's resources can be cleanly torn down and re-acquired.
// RuntimeBridge's canvas.transferControlToOffscreen() is a genuine one-shot
// browser API — once a canvas is transferred there is no way to undo it, so
// no effect using it can ever survive a simulated remount (confirmed:
// "Cannot transfer control from a canvas for more than one time"). Same
// class of exception as WebGL contexts/WebSockets — StrictMode's assumption
// doesn't hold for a resource the platform itself only grants once.
createRoot(document.getElementById('root')!).render(<App />)
