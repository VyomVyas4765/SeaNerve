import { pct } from '../lib/format'
import { useStore } from '../store'

export function Metrics() {
  const status = useStore((s) => s.status)
  const events = useStore((s) => s.alertOrder.length)
  return (
    <section className="panel metrics">
      <header className="panel-title">
        <span>Metrics</span>
      </header>
      <dl>
        <div>
          <dt>Processing</dt>
          <dd>{status?.latency_ms != null ? `${status.latency_ms.toFixed(0)} ms` : '—'}</dd>
          <small>per second of data</small>
        </div>
        <div>
          <dt>Data kept</dt>
          <dd>{status?.data_kept_ratio != null ? pct(status.data_kept_ratio) : '—'}</dd>
          <small>edge triggering</small>
        </div>
        <div>
          <dt>Events</dt>
          <dd>{events}</dd>
          <small>this recording</small>
        </div>
      </dl>
    </section>
  )
}
