import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useRef } from 'react'
import { fmtCountdown } from '../lib/format'
import { CablePath, channelKm, waveRadiusKm, type LatLng } from '../lib/geo'
import { currentAlert, streamNow, useStore } from '../store'
import type { Hello } from '../types'
import { FitIcon } from './icons'

// Offline map: no tiles, just land polygons on an ocean-coloured background.
const VIEW: L.LatLngBoundsExpression = [
  [6.3, 79.6],
  [13.7, 97.4],
]

interface Layers {
  map: L.Map
  paths: Map<string, CablePath>
  sensed: L.Polyline
  triggered: L.Polyline
  epicentre: L.CircleMarker
  alt: L.CircleMarker
  pRing: L.Circle
  sRing: L.Circle
  cities: Map<string, L.CircleMarker>
}

export function MapPanel() {
  const divRef = useRef<HTMLDivElement>(null)
  const layers = useRef<Layers | null>(null)
  const hello = useStore((s) => s.hello)

  useEffect(() => {
    const map = L.map(divRef.current!, { zoomControl: false, attributionControl: false, zoomSnap: 0.25 })
    map.fitBounds(VIEW)
    const hidden = { opacity: 0, fillOpacity: 0 }
    const l: Layers = {
      map,
      paths: new Map(),
      sensed: L.polyline([], { color: '#2cc5b8', weight: 4 }).addTo(map),
      triggered: L.polyline([], { color: '#b8fff6', weight: 7, opacity: 0.9 }).addTo(map),
      epicentre: L.circleMarker([0, 0], { radius: 7, color: '#fff', weight: 2, fillColor: '#e8603c', ...hidden }).addTo(map),
      alt: L.circleMarker([0, 0], { radius: 6, color: '#e8603c', weight: 1, dashArray: '3 3', ...hidden }).addTo(map),
      pRing: L.circle([0, 0], { radius: 1, color: '#f5b13d', weight: 2, fill: false, ...hidden }).addTo(map),
      sRing: L.circle([0, 0], { radius: 1, color: '#e8603c', weight: 3, fill: false, ...hidden }).addTo(map),
      cities: new Map(),
    }
    layers.current = l

    fetch('/geo/land.geojson')
      .then((r) => r.json())
      .then((land) => {
        L.geoJSON(land, {
          interactive: false,
          style: { color: '#3b5175', weight: 0.8, fillColor: '#1d2c45', fillOpacity: 1 },
        })
          .addTo(map)
          .bringToBack()
      })
    fetch('/geo/cani.geojson')
      .then((r) => r.json())
      .then((cables: GeoJSON.FeatureCollection<GeoJSON.LineString, { id: string }>) => {
        for (const f of cables.features) {
          const pts = f.geometry.coordinates.map(([lon, lat]) => [lat, lon] as LatLng)
          l.paths.set(f.properties.id, new CablePath(pts))
          L.polyline(pts, { color: '#2cc5b8', weight: 2, opacity: 0.45, dashArray: '5 5', interactive: false }).addTo(map)
        }
        placeSensedCable(l, useStore.getState().hello)
      })

    // Keep the whole region in view as the panel resizes, until someone pans or zooms by hand.
    const container = map.getContainer()
    const touched = () => (container.dataset.touched = '1')
    map.on('dragstart', touched)
    container.addEventListener('wheel', touched, { passive: true })
    container.addEventListener('dblclick', touched)
    const resize = new ResizeObserver(() => {
      map.invalidateSize()
      if (!container.dataset.touched) map.fitBounds(VIEW)
    })
    resize.observe(divRef.current!)

    let raf = 0
    let last = 0
    const animate = (now: number) => {
      raf = requestAnimationFrame(animate)
      if (now - last < 50) return
      last = now
      updateDynamic(l)
    }
    raf = requestAnimationFrame(animate)
    return () => {
      cancelAnimationFrame(raf)
      resize.disconnect()
      map.remove()
      layers.current = null
    }
  }, [])

  // A new session: city markers and the stretch of cable this recording covers.
  useEffect(() => {
    const l = layers.current
    if (!l) return
    l.cities.forEach((m) => m.remove())
    l.cities.clear()
    for (const c of hello?.cities ?? []) {
      const m = L.circleMarker([c.lat, c.lon], { radius: 4, color: '#fff', weight: 1.5, fillColor: '#0d1a2b', fillOpacity: 1 })
        // Island cities sit near the map's east edge: label them to the left, over open sea.
        .bindTooltip(c.name, {
          permanent: true,
          direction: c.lon > 90 ? 'left' : 'right',
          className: 'city-label',
          offset: c.lon > 90 ? [-6, 0] : [6, 0],
        })
        .addTo(l.map)
      l.cities.set(c.name, m)
    }
    placeSensedCable(l, hello)
  }, [hello])

  return (
    <section className="panel map-panel">
      <header className="panel-title">
        <span>Chennai–Andaman–Nicobar cable</span>
        <span className="legend">route approximate · offline map</span>
      </header>
      <div className="map-wrap">
        <div className="map" ref={divRef} />
        <button className="map-fit" title="Fit the view" aria-label="Fit the view" onClick={() => {
            const map = layers.current?.map
            if (!map) return
            delete map.getContainer().dataset.touched
            map.fitBounds(VIEW)
          }}>
          <FitIcon />
        </button>
        <ul className="map-legend">
          <li>
            <i className="k cable" /> sensing cable
          </li>
          <li className="route">
            <i className="k route" /> other CANI routes
          </li>
          <li>
            <i className="k p" /> P wave
          </li>
          <li>
            <i className="k s" /> S wave
          </li>
          <li>
            <i className="k epi" /> epicentre
          </li>
        </ul>
      </div>
    </section>
  )
}

function placeSensedCable(l: Layers, hello: Hello | null) {
  const path = hello?.cable_path ? l.paths.get(hello.cable_path) : undefined
  l.sensed.setLatLngs(path && hello ? path.between(hello.channel0_km, channelKm(hello, hello.n_channels - 1)) : [])
}

/** Rings, epicentre, the triggered stretch of cable and city countdowns, at stream time now. */
function updateDynamic(l: Layers) {
  const state = useStore.getState()
  const { hello, trigger } = state
  const alert = currentAlert(state)
  const now = streamNow()
  const path = hello?.cable_path ? l.paths.get(hello.cable_path) : undefined

  const busy = trigger && trigger.channels && trigger.t_s > now - 2 && path && hello
  l.triggered.setLatLngs(busy ? path.between(channelKm(hello, trigger.channels![0]), channelKm(hello, trigger.channels![1])) : [])

  const loc = alert?.location
  const show = (m: L.Path, on: boolean, opacity = 1) => m.setStyle({ opacity: on ? opacity : 0, fillOpacity: on ? 0.9 * opacity : 0 })
  if (alert && loc?.lat != null && loc.lon != null && alert.origin_time_s != null) {
    const at: LatLng = [loc.lat, loc.lon]
    l.epicentre.setLatLng(at)
    show(l.epicentre, true)
    if (loc.alt) l.alt.setLatLng([loc.alt.lat, loc.alt.lon])
    show(l.alt, !!loc.alt, 0.45)
    const dt = now - alert.origin_time_s
    for (const [ring, phase] of [
      [l.pRing, 'P'],
      [l.sRing, 'S'],
    ] as const) {
      const r = waveRadiusKm(dt, phase, 20)
      ring.setLatLng(at).setRadius(Math.max(r, 0.1) * 1000)
      ring.setStyle({ opacity: r > 0 && r < 2500 ? 0.9 : 0 })
    }
  } else {
    for (const m of [l.epicentre, l.alt, l.pRing, l.sRing]) show(m, false)
  }

  for (const w of alert?.warnings ?? []) {
    const marker = l.cities.get(w.city)
    if (!marker) continue
    const left = w.s_arrival_s - now
    const text = left > 0 ? `${w.city} · S in ${fmtCountdown(left)}` : left > -15 ? `${w.city} · shaking` : w.city
    marker.setTooltipContent(text)
    marker.setStyle({ fillColor: left <= 0 && left > -15 ? '#e8603c' : '#0d1a2b' })
  }
}
