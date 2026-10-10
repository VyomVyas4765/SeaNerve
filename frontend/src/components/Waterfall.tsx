import { useEffect, useRef } from 'react'
import { LUT } from '../lib/colormap'
import { fmtClock } from '../lib/format'
import { channelKm } from '../lib/geo'
import { currentAlert, eventRecent, useStore } from '../store'
import type { Hello } from '../types'
import { onFrame } from '../ws'
import { Welcome } from './Welcome'

const HISTORY_S = 60 // seconds kept on screen; newest at the bottom, so a quake's curve points up

const TEAL = '#2cc5b8'
const AMBER = '#f5b13d'
const CORAL = '#e8603c'
const MUTED = '#6b778c'
const EMPTY_CSS = '#0f1c30' // not yet received: the image fills in from the bottom

type Hover = { x: number; y: number } | null

export function Waterfall() {
  const hello = useStore((s) => s.hello)
  const wrapRef = useRef<HTMLDivElement>(null)
  const baseRef = useRef<HTMLCanvasElement>(null)
  const overlayRef = useRef<HTMLCanvasElement>(null)
  const bottomTime = useRef(0) // stream time at the bottom edge of the image
  const hover = useRef<Hover>(null)

  // Data-resolution image (cols x 600 rows) that frames scroll through, drawn scaled to the screen.
  useEffect(() => {
    if (!hello) return
    const off = document.createElement('canvas')
    off.width = hello.cols
    off.height = HISTORY_S * hello.rows_per_s
    const ctx = off.getContext('2d', { willReadFrequently: true })!
    ctx.fillStyle = EMPTY_CSS
    ctx.fillRect(0, 0, off.width, off.height)
    bottomTime.current = 0

    const paint = () => {
      const base = baseRef.current
      if (!base) return
      const b = base.getContext('2d')!
      b.imageSmoothingEnabled = false
      b.drawImage(off, 0, 0, base.width, base.height)
    }
    const resize = () => {
      const wrap = wrapRef.current
      if (!wrap || !baseRef.current || !overlayRef.current) return
      const dpr = window.devicePixelRatio || 1
      for (const c of [baseRef.current, overlayRef.current]) {
        c.width = Math.round(wrap.clientWidth * dpr)
        c.height = Math.round(wrap.clientHeight * dpr)
      }
      paint()
    }
    const observer = new ResizeObserver(resize)
    if (wrapRef.current) observer.observe(wrapRef.current)
    resize()

    const unsubscribe = onFrame((buf) => {
      const view = new DataView(buf)
      const rows = view.getUint32(0, true)
      const cols = view.getUint32(4, true)
      const t0 = view.getFloat64(8, true)
      if (cols !== off.width || rows === 0) return
      const cells = new Uint8Array(buf, 16, rows * cols)
      // Frames missed while the socket was down leave a blank gap, so older rows keep their time.
      const missed = bottomTime.current > 0 ? Math.round((t0 - bottomTime.current) * hello.rows_per_s) : 0
      const shift = Math.min(off.height, rows + Math.max(0, missed))
      const kept = ctx.getImageData(0, shift, cols, off.height - shift)
      ctx.putImageData(kept, 0, 0) // scroll up
      if (shift > rows) {
        ctx.fillStyle = EMPTY_CSS
        ctx.fillRect(0, off.height - shift, cols, shift - rows)
      }
      const img = ctx.createImageData(cols, rows)
      for (let i = 0; i < cells.length; i++) img.data.set(LUT.subarray(cells[i] * 4, cells[i] * 4 + 4), i * 4)
      ctx.putImageData(img, 0, off.height - rows)
      bottomTime.current = t0 + rows / hello.rows_per_s
      paint()
    })
    return () => {
      unsubscribe()
      observer.disconnect()
    }
  }, [hello])

  // Overlays (gate curve, P and S marks, axes) redraw every animation frame, pixels untouched.
  useEffect(() => {
    if (!hello) return
    let raf = 0
    const draw = () => {
      raf = requestAnimationFrame(draw)
      const c = overlayRef.current
      if (c) drawOverlay(c, hello, bottomTime.current, hover.current)
    }
    draw()
    return () => cancelAnimationFrame(raf)
  }, [hello])

  return (
    <section className="panel waterfall">
      <header className="panel-title">
        <span>Waterfall · distance along the cable × time</span>
        <span className="legend">
          <i className="sw pos" /> <i className="sw neg" /> strain rate (signed, log scale) · newest at the bottom · hover to read
        </span>
      </header>
      <div
        className="waterfall-canvas"
        ref={wrapRef}
        onPointerMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect()
          hover.current = { x: e.clientX - r.left, y: e.clientY - r.top }
        }}
        onPointerLeave={() => (hover.current = null)}
      >
        {!hello && <Welcome />}
        <canvas ref={baseRef} className="pixelated" />
        <canvas ref={overlayRef} />
      </div>
    </section>
  )
}

function drawOverlay(c: HTMLCanvasElement, hello: Hello, bottom: number, hover: Hover) {
  const ctx = c.getContext('2d')!
  const dpr = window.devicePixelRatio || 1
  const W = c.width
  const H = c.height
  ctx.clearRect(0, 0, W, H)
  ctx.save()
  ctx.scale(dpr, dpr)
  const w = W / dpr
  const h = H / dpr
  const x = (ch: number) => (ch / hello.channels_per_col / hello.cols) * w
  const y = (t: number) => h - ((bottom - t) / HISTORY_S) * h
  const label = (text: string, px: number, py: number, color: string, align: CanvasTextAlign = 'left') => {
    ctx.font = '600 13px "Inter Variable", system-ui, sans-serif'
    ctx.textAlign = align
    ctx.lineWidth = 4
    ctx.strokeStyle = 'rgba(243,239,233,0.9)'
    ctx.strokeText(text, px, py)
    ctx.fillStyle = color
    ctx.fillText(text, px, py)
  }

  const { trigger, passedTrigger, ...rest } = useStore.getState()
  const alert = currentAlert(rest)

  // A rejected disturbance: grey curve and the reason, while it's fresh.
  if (trigger && !trigger.passed && trigger.t_s > bottom - 3 && trigger.channels && !eventRecent(alert, bottom)) {
    const [lo, hi] = trigger.channels
    label(`gate: rejected (${trigger.reason.split(';')[0]})`, x((lo + hi) / 2), y(trigger.t_s) - 28, MUTED, 'center')
  }

  // The curve that convinced the gate: predicted P arrival along the cable.
  if (passedTrigger && passedTrigger.curve.length > 1 && passedTrigger.t_s > bottom - HISTORY_S - 30) {
    ctx.setLineDash([8, 6])
    ctx.lineWidth = 2.5
    ctx.strokeStyle = TEAL
    ctx.beginPath()
    passedTrigger.curve.forEach(([ch, t], i) => (i ? ctx.lineTo(x(ch), y(t) - 6) : ctx.moveTo(x(ch), y(t) - 6)))
    ctx.stroke()
    ctx.setLineDash([])
    const top = passedTrigger.curve.reduce((a, b) => (b[1] < a[1] ? b : a))
    const v = passedTrigger.apparent_velocity_kms
    label(`physics gate: coherent, ${v != null && v < 900 ? v.toFixed(1) : '>9'} km/s`, x(top[0]), y(top[1]) - 18, '#178f86', 'center')
  }

  // P and S at the channel the wave reached first.
  if (alert?.picks && alert.location?.along_cable_km != null) {
    const ch = ((alert.location.along_cable_km - hello.channel0_km) * 1000) / hello.dx_m
    const px = x(ch)
    const mark = (t: number, text: string, color: string) => {
      const py = y(t)
      if (py < 0 || py > h) return
      ctx.strokeStyle = color
      ctx.lineWidth = 3
      ctx.beginPath()
      ctx.moveTo(px - 14, py)
      ctx.lineTo(px + 14, py)
      ctx.stroke()
      label(text, px - 20, py + 5, color, 'right')
    }
    mark(alert.picks.p_s, 'P', AMBER)
    if (alert.picks.s_s != null) mark(alert.picks.s_s, 'S', CORAL)
  }

  // Axes: km along the cable at the bottom, seconds ago on the left.
  const AXIS = '#3a4558'
  for (let i = 0; i <= 4; i++) {
    const ch = (i / 4) * (hello.n_channels - 1)
    label(`${channelKm(hello, ch).toFixed(0)} km`, Math.min(Math.max(x(ch), 24), w - 24), h - 6, AXIS, 'center')
  }
  for (let s = 10; s < HISTORY_S; s += 10) {
    const py = h - (s / HISTORY_S) * h + 4
    if (bottom - s >= 0) {
      label(`−${s} s`, 6, py, AXIS)
    } else {
      ctx.font = '500 12px "Inter Variable", system-ui, sans-serif' // over the not-yet-filled area
      ctx.textAlign = 'left'
      ctx.fillStyle = '#5d6b82'
      ctx.fillText(`−${s} s`, 6, py)
    }
  }

  // Hover readout: where along the cable and when, under the pointer.
  const t = bottom - ((h - (hover?.y ?? 0)) / h) * HISTORY_S
  if (hover && bottom > 0 && t >= 0) {
    const ch = (hover.x / w) * hello.cols * hello.channels_per_col
    ctx.strokeStyle = 'rgba(15,28,48,0.55)'
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(hover.x + 0.5, 0)
    ctx.lineTo(hover.x + 0.5, h)
    ctx.moveTo(0, hover.y + 0.5)
    ctx.lineTo(w, hover.y + 0.5)
    ctx.stroke()
    const text = `${channelKm(hello, ch).toFixed(1)} km · ${(bottom - t).toFixed(1)} s ago · ${fmtClock(t)}`
    ctx.font = '600 12px "Inter Variable", system-ui, sans-serif'
    const tw = ctx.measureText(text).width + 16
    const bx = Math.min(hover.x + 12, w - tw - 4)
    const by = Math.max(hover.y - 32, 4)
    ctx.fillStyle = 'rgba(11,22,38,0.92)'
    ctx.beginPath()
    ctx.roundRect(bx, by, tw, 24, 6)
    ctx.fill()
    ctx.fillStyle = '#f4f7fb'
    ctx.textAlign = 'left'
    ctx.fillText(text, bx + 8, by + 16)
  }
  ctx.restore()
}
