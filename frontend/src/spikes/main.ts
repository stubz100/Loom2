// loom2 frontend — M0 spike harness. Plain DOM for the spikes (React arrives with the real frame in M1).
// Routes: #e1 (WebGPU compositor) · #e1-webgl · #e2 (loopback transfer) · #e3 (brush) · #e6 (video scrub) · #e10 (stage passes, D74) · #e11 (stage shots, D74) · #e13 (timeline, D74) · #e14 (mesh views, D74) · #all · #e30 (a set from an image, D119 / E30)
import './spikes.css'
import { runE1 } from './e1Compositor'
import { runE2 } from './e2Transfer'
import { runE3 } from './e3Brush'
import { runE6 } from './e6Video'
import { runE10 } from './e10Stage'
import { runE11 } from './e11Shots'
import { runE13 } from './e13Timeline'
import { runE14 } from './e14Mesh'
import { runE30 } from './e30Set'
import { hostInfo } from './report'

const ORDER = ['e1', 'e1-webgl', 'e2', 'e3', 'e6']

function nav(): HTMLElement {
  const bar = document.createElement('nav')
  bar.innerHTML = `<b>loom2 spikes</b> ` + [...ORDER, 'all'].map((r) => `<a href="#${r}">${r}</a>`).join(' ') +
    ` <span class="host">${hostInfo().shell} · webgpu:${hostInfo().webgpu}</span>`
  return bar
}

async function route() {
  const root = document.getElementById('root')!
  root.replaceChildren(nav())
  const mount = document.createElement('main')
  const out = document.createElement('section')
  out.className = 'out'
  root.append(mount, out)
  // inside the Tauri window the dev URL has no hash → run the whole sequence automatically
  const hash = (location.hash || ('__TAURI_INTERNALS__' in window ? '#all' : '#')).slice(1)
  let queue: string[] = JSON.parse(sessionStorage.getItem('spikeQueue') ?? '[]')
  let current = hash
  if (hash === 'all') {
    queue = ORDER.slice(1) // (bug fixed 2026-10-05: the queue was read before being set, so #all stopped after e1)
    sessionStorage.setItem('spikeQueue', JSON.stringify(queue))
    current = ORDER[0]
  }
  try {
    if (current === 'e1') await runE1(mount, out, { preference: 'webgpu' })
    else if (current === 'e1-webgl') await runE1(mount, out, { preference: 'webgl' })
    else if (current === 'e2') await runE2(mount, out)
    else if (current === 'e3') await runE3(mount, out, { synthetic: true })
    else if (current === 'e6') await runE6(mount, out)
    else if (current === 'e10') await runE10(mount, out)
    else if (current === 'e11') await runE11(mount, out)
    else if (current === 'e13') await runE13(mount, out)
    else if (current === 'e14') await runE14(mount, out)
    else if (current === 'e30') await runE30(mount, out)
    else out.textContent = 'pick a spike above, or #all to run the sequence'
  } catch (e) {
    out.textContent = `FAILED: ${(e as Error).stack ?? e}`
    console.error(e)
  }
  if (hash === 'all' || queue.length) {
    const next = queue.shift()
    sessionStorage.setItem('spikeQueue', JSON.stringify(queue))
    if (next) setTimeout(() => { location.hash = next; location.reload() }, 1500)
    else {
      const d = document.createElement('h2'); d.textContent = 'ALL SPIKES DONE'; out.prepend(d)
      // drop the stale "#e6" so a later reload (HMR, restart) starts the full sequence again
      history.replaceState(null, '', location.pathname)
    }
  }
}

window.addEventListener('hashchange', () => location.reload())
route()
