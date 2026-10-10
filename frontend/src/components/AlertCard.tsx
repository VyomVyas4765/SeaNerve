import { fmtCountdown, fmtLatLon, pct } from '../lib/format'
import { currentAlert, streamNow, useStore } from '../store'
import type { Alert, CityWarning } from '../types'
import { useTicker } from '../useTicker'

const HEADLINE_CITY = 'Port Blair'

/** The city the big countdown follows: Port Blair while it's still ahead, else the next one. */
function headlineWarning(alert: Alert, now: number): CityWarning | null {
  const ahead = alert.warnings.filter((w) => w.s_arrival_s > now)
  return ahead.find((w) => w.city === HEADLINE_CITY) ?? ahead[0] ?? alert.warnings.find((w) => w.city === HEADLINE_CITY) ?? null
}

export function AlertCard() {
  useTicker(10)
  const alert = useStore(currentAlert)
  const hello = useStore((s) => s.hello)
  const now = streamNow()

  if (!alert) {
    return (
      <section className="panel alert-card idle">
        <div className="alert-head">
          <span className="sev" />
          <h2>Listening</h2>
        </div>
        <p className="muted">{hello ? 'No earthquake on the cable so far.' : 'Nothing playing yet.'}</p>
      </section>
    )
  }

  const head = headlineWarning(alert, now)
  const others = alert.warnings.filter((w) => w !== head && w.s_arrival_s > now - 15).slice(0, 5)
  const loc = alert.location
  const origin = alert.origin_time_s ?? alert.detected_at_s
  return (
    <section className={`panel alert-card ${alert.class}`}>
      <div className="alert-head">
        <span className="sev" />
        <h2>{alert.class === 'cable_threat' ? 'Cable threat' : 'Earthquake'}</h2>
        <span className={`pill ${alert.status}`}>{alert.status}</span>
      </div>

      {head && (
        <div className="hero">
          {head.s_arrival_s > now ? (
            <>
              <span className="hero-label">S waves reach {head.city} in</span>
              <span className="hero-value">{fmtCountdown(head.s_arrival_s - now)}</span>
            </>
          ) : (
            <>
              <span className="hero-label">S waves have reached</span>
              <span className="hero-value small">{head.city}</span>
            </>
          )}
        </div>
      )}

      <dl className="tiles">
        <div>
          <dt>Rough magnitude</dt>
          <dd>{alert.magnitude ? `M ${alert.magnitude.value.toFixed(1)}` : <span className="wait">waiting for S</span>}</dd>
        </div>
        <div>
          <dt>Distance</dt>
          <dd>
            {loc?.distance_km != null ? `${loc.distance_km.toFixed(0)} km` : '—'}
            <small>{alert.picks?.s_s != null ? 'from S–P gap' : 'from gate'}</small>
          </dd>
        </div>
        <div>
          <dt>Epicentre</dt>
          <dd className="small">
            {loc?.lat != null && loc.lon != null ? fmtLatLon(loc.lat, loc.lon) : '—'}
            {loc?.ambiguous && <small title="A cable can't fully tell left from right">or the other side</small>}
          </dd>
        </div>
        <div>
          <dt>Confidence</dt>
          <dd>
            {alert.confidence != null ? pct(alert.confidence) : '—'}
            <small>{alert.classifier}</small>
          </dd>
        </div>
      </dl>

      {others.length > 0 && (
        <ul className="cities">
          {others.map((w) => {
            const left = w.s_arrival_s - now
            const done = Math.min(1, Math.max(0, (now - origin) / (w.s_arrival_s - origin)))
            return (
              <li key={w.city} className={left <= 0 ? 'hit' : ''}>
                <span className="city">{w.city}</span>
                <span className="meter">
                  <i style={{ width: `${done * 100}%` }} />
                </span>
                <span className="left">{left > 0 ? fmtCountdown(left) : 'shaking'}</span>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
