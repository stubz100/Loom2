import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'

// A crash overlay: the WebView2 window has no console the author can see, so uncaught errors render on screen.
function showCrash(msg: string) {
  let el = document.getElementById('crash')
  if (!el) {
    el = document.createElement('pre')
    el.id = 'crash'
    el.style.cssText = 'position:fixed;left:8px;right:8px;top:8px;max-height:60vh;overflow:auto;z-index:9999;background:#3a1414;color:#ffd0d0;border:1px solid #e05a5a;border-radius:6px;padding:8px 12px;font:12px/1.4 Consolas,monospace;white-space:pre-wrap'
    el.title = 'click to dismiss'
    el.addEventListener('click', () => el?.remove())
    document.body.append(el)
  }
  el.textContent += (el.textContent ? '\n' : '') + msg
}
window.addEventListener('error', (e) => showCrash(`${e.message}\n${e.error?.stack ?? ''}`))
window.addEventListener('unhandledrejection', (e) => showCrash(`unhandled: ${(e.reason as Error)?.stack ?? String(e.reason)}`))

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
