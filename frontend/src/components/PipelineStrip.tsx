import { pct } from '../lib/format'
import { currentAlert, eventRecent, streamNow, useStore } from '../store'
import { useTicker } from '../useTicker'
import { CheckIcon, CrossIcon } from './icons'

type Lit = 'idle' | 'active' | 'done' | 'rejected'

/** The five stages lighting up with their numbers: the explainability moment. */
export function PipelineStrip() {
  useTicker(4)
  const trigger = useStore((s) => s.trigger)
  const passed = useStore((s) => s.passedTrigger)
  const alert = useStore(currentAlert)
  const now = streamNow()
  const fresh = trigger != null && trigger.t_s > now - 2.5
  const rejected = fresh && !trigger.passed && !eventRecent(alert, now)
  const speed = (v: number | null | undefined) => (v != null && v < 900 ? `${v.toFixed(1)} km/s` : '>9 km/s')

  const stages: { name: string; lit: Lit; value: string }[] = [
    {
      name: 'Trigger',
      lit: fresh ? 'active' : alert ? 'done' : 'idle',
      value: fresh ? `${pct(trigger.coverage)} of cable` : alert ? `${pct(alert.gate?.coverage ?? 0)} of cable` : 'listening',
    },
    {
      name: 'Physics gate',
      lit: rejected ? 'rejected' : passed && alert ? 'done' : 'idle',
      value: rejected
        ? `rejected · ${trigger.reason.split(';')[0]}`
        : passed && alert
          ? `pass · ${speed(passed.apparent_velocity_kms)} · fit ${pct(passed.inlier_fraction ?? 0)}`
          : 'waiting',
    },
    {
      name: 'Classifier',
      lit: alert ? 'done' : 'idle',
      value: alert ? `${alert.class} · ${alert.classifier}` : '—',
    },
    {
      name: 'P & S picks',
      lit: alert ? (alert.picks?.s_s != null ? 'done' : 'active') : 'idle',
      value: alert?.picks
        ? `P ${alert.picks.p_s.toFixed(1)} s · S ${alert.picks.s_s != null ? `${alert.picks.s_s.toFixed(1)} s` : 'waiting'}`
        : '—',
    },
    {
      name: 'Alert',
      lit: alert ? (alert.status === 'final' ? 'done' : 'active') : 'idle',
      value: alert ? `${alert.status} · rev ${alert.rev}` : '—',
    },
  ]
  return (
    <ol className="pipeline" aria-label="Detection pipeline">
      {stages.map((s, i) => (
        <li key={s.name} className={s.lit}>
          <span className="step">{s.lit === 'done' ? <CheckIcon /> : s.lit === 'rejected' ? <CrossIcon /> : i + 1}</span>
          <span className="name">{s.name}</span>
          <span className="value" title={s.value}>
            {s.value}
          </span>
        </li>
      ))}
    </ol>
  )
}
