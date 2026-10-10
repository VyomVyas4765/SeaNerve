import { currentAlert, useStore } from '../store'

const CITY = 'Port Blair'

/** Seconds of warning before S waves: from the seabed cable vs a seismometer in the city. */
export function WarningBars() {
  const alert = useStore(currentAlert)
  const w = alert?.warnings.find((x) => x.city === CITY)
  if (!alert || !w) {
    return (
      <section className="panel bars idle">
        <h3>Warning before S waves reach {CITY}</h3>
        <p className="muted">Appears with the first earthquake alert.</p>
      </section>
    )
  }
  const cable = Math.max(0, w.s_arrival_s - alert.detected_at_s)
  const land = Math.max(0, w.s_arrival_s - w.land_station_alert_s)
  const max = Math.max(cable, land, 1)
  return (
    <section className="panel bars">
      <h3>Warning before S waves reach {CITY}</h3>
      <div className="bar-row">
        <span className="bar-label">Seabed cable</span>
        <span className="track">
          <i className="bar cable" style={{ width: `${(cable / max) * 100}%` }} />
          <strong>{cable.toFixed(0)} s</strong>
        </span>
      </div>
      <div className="bar-row">
        <span className="bar-label">Seismometer in {CITY}</span>
        <span className="track">
          <i className="bar land" style={{ width: `${(land / max) * 100}%` }} />
          <strong>{land.toFixed(0)} s</strong>
        </span>
      </div>
      {land > 0 && (
        <p className="gain">
          The cable gives <strong>{(cable / land).toFixed(1)}×</strong> the warning
        </p>
      )}
    </section>
  )
}
