// Mirror of backend/core/contracts.py. Change both together.
//
// Binary waterfall frame: 16-byte little-endian header (uint32 rows, uint32 cols,
// float64 stream time of the first row), then rows * cols uint8 cells, oldest row first.
// 128 means zero; values are signed and log-scaled.

export const FRAME_HEADER_BYTES = 16

export type EventClass = 'earthquake' | 'vessel' | 'anchor' | 'noise' | 'cable_threat'
export type Mode = 'scenario' | 'replay'

export interface LatLon {
  lat: number
  lon: number
}

export interface Epicentre extends LatLon {
  depth_km: number
}

export interface City extends LatLon {
  name: string
}

export interface Catalog {
  event_id: string | null
  event_time: string | null
  latitude: number | null
  longitude: number | null
  depth_km: number | null
  magnitude: number | null
  magnitude_type: string | null
}

export interface Hello {
  type: 'hello'
  session_id: string // a reconnect to the same session keeps the dashboard's state
  mode: Mode
  source: string
  title: string
  kind: 'synthetic' | 'real'
  duration_s: number
  rows_per_s: number
  cols: number
  channels_per_col: number
  km_per_col: number
  dx_m: number
  n_channels: number
  channel0_km: number
  cable_path: string | null
  cities: City[]
  catalog: Catalog | null
}

export interface Trigger {
  type: 'trigger'
  t_s: number
  passed: boolean
  reason: string
  coverage: number
  span_km: number
  apparent_velocity_kms: number | null
  inlier_fraction: number | null
  channels: [number, number] | null
  curve: [number, number][] // (channel, predicted P time)
  origin_time_s: number | null
  epicentre: Epicentre | null
  alt: LatLon | null
  ambiguous: boolean
}

export interface LocalEvent {
  type: 'local_event'
  t_s: number
  track_id: number
  class: 'vessel' | 'anchor' | 'noise'
  position_km: number
  width_m: number
  speed_ms: number
  threat: 'info' | 'watch' | 'alarm'
  lat: number | null
  lon: number | null
}

export interface GateSummary {
  coverage: number
  apparent_velocity_kms: number | null
  channels: [number, number]
}

export interface Picks {
  p_s: number
  s_s: number | null
  method: string
}

export interface Location {
  along_cable_km: number | null
  distance_km: number | null
  lat: number | null
  lon: number | null
  ambiguous: boolean
  alt: LatLon | null
}

export interface Magnitude {
  value: number
  quality: 'rough'
}

export interface CityWarning {
  city: string
  distance_km: number
  s_arrival_s: number
  land_station_alert_s: number
}

export interface Alert {
  type: 'alert'
  id: string
  rev: number
  status: 'preliminary' | 'updated' | 'final' | 'cancelled'
  mode: Mode
  source: string
  class: EventClass
  confidence: number | null
  classifier: 'rules' | 'resnet' | 'pending'
  detected_at_s: number
  origin_time_s: number | null
  gate: GateSummary | null
  picks: Picks | null
  location: Location | null
  magnitude: Magnitude | null
  warnings: CityWarning[]
  latency_ms: number | null
}

export interface Status {
  type: 'status'
  t_s: number
  speed: number
  paused: boolean
  latency_ms: number | null
  stage_ms: Record<string, number>
  data_kept_ratio: number | null
  ended: boolean
}

export type ServerMessage = Hello | Trigger | LocalEvent | Alert | Status
