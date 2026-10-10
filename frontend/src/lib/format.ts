export const fmtClock = (t: number) => {
  const m = Math.floor(t / 60)
  const s = t - m * 60
  return `T+${String(m).padStart(2, '0')}:${s.toFixed(1).padStart(4, '0')}`
}

export const fmtSeconds = (s: number) => (s >= 100 ? `${Math.round(s)} s` : `${s.toFixed(0)} s`)

export const fmtCountdown = (s: number) => {
  if (s < 60) return `${Math.max(0, Math.ceil(s))} s`
  const m = Math.floor(s / 60)
  return `${m} min ${String(Math.ceil(s - m * 60)).padStart(2, '0')} s`
}

export const fmtLatLon = (lat: number, lon: number) =>
  `${Math.abs(lat).toFixed(2)}°${lat >= 0 ? 'N' : 'S'} ${Math.abs(lon).toFixed(2)}°${lon >= 0 ? 'E' : 'W'}`

export const pct = (x: number) => `${Math.round(x * 100)}%`

export const titleCase = (s: string) => s.replace('_', ' ').toUpperCase()
