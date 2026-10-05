// E2 — loopback throughput (12 §1 E2, 05 §5): Python → fetch → GPU texture, and streaming upload.
// Pass bar: ≥ 500 MB/s end-to-end into a GPU texture; 64 MB upload without buffering in Python.
import { Application, BufferImageSource, Sprite, Texture } from 'pixi.js'
import { E2_SERVER, log, report } from './report'

const MiB = 2 ** 20

export async function runE2(mount: HTMLElement, out: HTMLElement) {
  const res: Record<string, unknown> = {}
  const health = await fetch(`${E2_SERVER}/health`).then((r) => r.json()).catch(() => null)
  if (!health) { log(out, 'E2 server not reachable at ' + E2_SERVER); return report({ spike: 'e2', error: 'server down' }, out) }

  // 1. 200 MB float16 latent → ArrayBuffer
  let t0 = performance.now()
  const lat = await (await fetch(`${E2_SERVER}/latent`, { cache: 'no-store' })).arrayBuffer()
  let dt = (performance.now() - t0) / 1000
  res.latent = { mib: +(lat.byteLength / MiB).toFixed(1), seconds: +dt.toFixed(3), mib_per_s: +(lat.byteLength / MiB / dt).toFixed(0) }
  log(out, `latent 200 MB fetch: ${(res.latent as { mib_per_s: number }).mib_per_s} MiB/s`)

  // 1b. the same 200 MB as parallel Range requests (does loopback scale with connections?)
  for (const parts of [2, 4, 8]) try {
    const size = lat.byteLength, per = Math.ceil(size / parts)
    t0 = performance.now()
    const chunks = await Promise.all(Array.from({ length: parts }, (_, i) => {
      const s = i * per, e = Math.min(size, s + per) - 1
      return fetch(`${E2_SERVER}/latent`, { cache: 'no-store', headers: { Range: `bytes=${s}-${e}` } }).then((r) => r.arrayBuffer())
    }))
    dt = (performance.now() - t0) / 1000
    const got = chunks.reduce((a, c) => a + c.byteLength, 0)
    const joined = new Uint8Array(got); let o = 0
    for (const c of chunks) { joined.set(new Uint8Array(c), o); o += c.byteLength }
    const dtJoin = (performance.now() - t0) / 1000
    res[`latent_parallel${parts}`] = { ok: got === size, seconds: +dt.toFixed(3), mib_per_s: +(got / MiB / dt).toFixed(0), with_join_mib_per_s: +(got / MiB / dtJoin).toFixed(0) }
    log(out, `latent via ${parts} parallel ranges: ${(got / MiB / dt).toFixed(0)} MiB/s (${got === size ? 'complete' : 'INCOMPLETE'})`)
  } catch (e) {
    res[`latent_parallel${parts}`] = { error: String((e as Error).message ?? e) }
    log(out, `latent via ${parts} parallel ranges FAILED: ${(e as Error).message}`)
  }

  // 2. 8K raw RGBA → GPU texture (the zero-decode path)
  t0 = performance.now()
  const rawBuf = await (await fetch(`${E2_SERVER}/image8k.raw`, { cache: 'no-store' })).arrayBuffer()
  const tFetch = (performance.now() - t0) / 1000
  const app = new Application()
  await app.init({ preference: 'webgpu', width: 512, height: 512, background: 0x101010 })
  mount.replaceChildren(app.canvas)
  const renderer = (app.renderer as unknown as { name?: string }).name ?? 'unknown'
  t0 = performance.now()
  const src = new BufferImageSource({ resource: new Uint8Array(rawBuf), width: 8192, height: 8192, format: 'rgba8unorm' })
  const sp = new Sprite(new Texture({ source: src }))
  sp.width = 512; sp.height = 512
  app.stage.addChild(sp)
  app.render()
  const gpu = (app.renderer as unknown as { gpu?: { device?: GPUDevice } }).gpu
  if (gpu?.device) await gpu.device.queue.onSubmittedWorkDone()
  const tUpload = (performance.now() - t0) / 1000
  const total = tFetch + tUpload
  res.raw8k_to_texture = { renderer, mib: +(rawBuf.byteLength / MiB).toFixed(0), fetch_s: +tFetch.toFixed(3), upload_s: +tUpload.toFixed(3), end_to_end_mib_per_s: +(rawBuf.byteLength / MiB / total).toFixed(0) }
  log(out, `8K raw → ${renderer} texture: fetch ${tFetch.toFixed(2)} s + upload ${tUpload.toFixed(2)} s = ${(rawBuf.byteLength / MiB / total).toFixed(0)} MiB/s end-to-end`)

  // 3. 8K PNG → ImageBitmap (the decode path)
  t0 = performance.now()
  const blob = await (await fetch(`${E2_SERVER}/image8k.png`, { cache: 'no-store' })).blob()
  const tPng = (performance.now() - t0) / 1000
  t0 = performance.now()
  const bmp = await createImageBitmap(blob)
  const tDecode = (performance.now() - t0) / 1000
  res.png8k = { mib: +(blob.size / MiB).toFixed(1), fetch_s: +tPng.toFixed(3), decode_s: +tDecode.toFixed(3), size: [bmp.width, bmp.height] }
  bmp.close()
  log(out, `8K PNG: fetch ${tPng.toFixed(2)} s, decode ${tDecode.toFixed(2)} s`)

  // 4. 64 MB streaming upload with sha256 verification server-side
  const up = new Uint8Array(64 * MiB)
  for (let o = 0; o < up.length; o += 65536) crypto.getRandomValues(up.subarray(o, Math.min(o + 65536, up.length)))
  t0 = performance.now()
  const digest = await crypto.subtle.digest('SHA-256', up)
  const hex = [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('')
  const tHash = (performance.now() - t0) / 1000
  t0 = performance.now()
  const r = await fetch(`${E2_SERVER}/blobs/${hex}`, { method: 'PUT', body: up, headers: { 'Content-Type': 'application/octet-stream' } })
  const j = await r.json()
  const tUp = (performance.now() - t0) / 1000
  res.upload64 = { ok: j.ok, hash_s: +tHash.toFixed(3), seconds: +tUp.toFixed(3), mib_per_s: +(up.length / MiB / tUp).toFixed(0), server_mb_per_s: j.mb_per_s }
  log(out, `64 MB PUT: ${(up.length / MiB / tUp).toFixed(0)} MiB/s (server saw ${j.mb_per_s}), sha ok=${j.ok}`)

  const row = await report({ spike: 'e2', ...res }, out)
  app.destroy(true, { children: true, texture: true })
  return row
}
