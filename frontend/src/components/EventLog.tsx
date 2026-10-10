import { fmtClock, pct } from '../lib/format'
import { useStore } from '../store'

export function EventLog() {
  const alerts = useStore((s) => s.alerts)
  const order = useStore((s) => s.alertOrder)
  const selectedId = useStore((s) => s.selectedId)
  const select = useStore((s) => s.select)
  const latest = order[order.length - 1]
  return (
    <section className="panel log">
      <header className="panel-title">
        <span>Event log</span>
        {selectedId ? (
          <button className="link" onClick={() => select(null)}>
            Follow newest
          </button>
        ) : (
          order.length > 1 && <span className="legend">Click a row to reopen its card</span>
        )}
      </header>
      {order.length === 0 ? (
        <p className="muted empty-log">Events appear here as the pipeline raises them.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Detected</th>
              <th>Event</th>
              <th>Along cable</th>
              <th>Magnitude</th>
              <th>Confidence</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {[...order].reverse().map((id) => {
              const a = alerts[id]
              const active = (selectedId ?? latest) === id
              return (
                <tr
                  key={id}
                  className={active ? 'active' : ''}
                  tabIndex={0}
                  onClick={() => select(id === latest ? null : id)}
                  onKeyDown={(e) => e.key === 'Enter' && select(id === latest ? null : id)}
                >
                  <td>{fmtClock(a.detected_at_s)}</td>
                  <td>
                    <i className={`dot ${a.class}`} />
                    {a.class === 'cable_threat' ? 'cable threat' : a.class}
                  </td>
                  <td>{a.location?.along_cable_km != null ? `${a.location.along_cable_km.toFixed(1)} km` : '—'}</td>
                  <td>{a.magnitude ? `M ${a.magnitude.value.toFixed(1)}` : '—'}</td>
                  <td>{a.confidence != null ? `${pct(a.confidence)} · ${a.classifier}` : '—'}</td>
                  <td>
                    <span className={`pill ${a.status}`}>{a.status}</span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </section>
  )
}
