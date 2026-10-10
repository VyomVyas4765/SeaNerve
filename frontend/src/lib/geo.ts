// Cable path geometry and wave travel, mirroring backend/core/geo.py and config.travel_time.
import type { Hello } from '../types'

export type LatLng = [number, number]

const R = 6371
const rad = (d: number) => (d * Math.PI) / 180

export function haversineKm(a: LatLng, b: LatLng): number {
  const h =
    Math.sin(rad(b[0] - a[0]) / 2) ** 2 +
    Math.cos(rad(a[0])) * Math.cos(rad(b[0])) * Math.sin(rad(b[1] - a[1]) / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(h))
}

export class CablePath {
  readonly points: LatLng[]
  readonly vertexKm: number[]
  constructor(points: LatLng[]) {
    this.points = points
    this.vertexKm = [0]
    for (let i = 1; i < points.length; i++) {
      this.vertexKm.push(this.vertexKm[i - 1] + haversineKm(points[i - 1], points[i]))
    }
  }

  pointAt(km: number): LatLng {
    const v = this.vertexKm
    if (km <= 0) return this.points[0]
    for (let i = 1; i < v.length; i++) {
      if (km <= v[i]) {
        const f = (km - v[i - 1]) / (v[i] - v[i - 1])
        const [a, b] = [this.points[i - 1], this.points[i]]
        return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f]
      }
    }
    return this.points[this.points.length - 1]
  }

  /** The polyline between two distances along the path. */
  between(km0: number, km1: number): LatLng[] {
    const inside = this.points.filter((_, i) => this.vertexKm[i] > km0 && this.vertexKm[i] < km1)
    return [this.pointAt(km0), ...inside, this.pointAt(km1)]
  }
}

export const channelKm = (hello: Hello, channel: number) => hello.channel0_km + (channel * hello.dx_m) / 1000

// Wave speeds: crustal near the source, faster deep paths beyond FAR_KM (config.py).
const SPEEDS = { P: [6.5, 8.0], S: [3.5, 4.6] } as const
const FAR_KM = 200

/** How far along the surface a P or S wave has spread dt seconds after the origin. */
export function waveRadiusKm(dt: number, phase: 'P' | 'S', depthKm: number): number {
  if (dt <= 0) return 0
  const [near, far] = SPEEDS[phase]
  const r = dt * near <= FAR_KM ? dt * near : FAR_KM + (dt - FAR_KM / near) * far
  return r > depthKm ? Math.sqrt(r * r - depthKm * depthKm) : 0
}
