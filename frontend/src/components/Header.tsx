import { useEffect } from 'react'
import { api } from '../api'
import { controls, DEMO } from '../controls'
import { fmtClock } from '../lib/format'
import { streamNow, useStore } from '../store'
import { useTicker } from '../useTicker'
import { LogoIcon, PauseIcon, PlayIcon, RestartIcon } from './icons'

const SPEEDS = [1, 2, 5]

export function Header() {
  useTicker(10)
  const connected = useStore((s) => s.connected)
  const sources = useStore((s) => s.sources)
  const hello = useStore((s) => s.hello)
  const status = useStore((s) => s.status)
  const speed = useStore((s) => s.speed)
  const error = useStore((s) => s.error)
  const setSources = useStore((s) => s.setSources)

  useEffect(() => {
    api.sources().then(setSources).catch(() => setSources([]))
  }, [setSources, connected])

  const playing = hello != null && !status?.paused
  const now = hello ? streamNow() : 0
  const groups = [
    { label: 'Replay: real recordings', items: sources.filter((s) => s.kind === 'real') },
    { label: 'Scenario: simulated', items: sources.filter((s) => s.kind === 'synthetic') },
  ]

  return (
    <header className="topbar">
      <div className="brand">
        <LogoIcon />
        <span>SeaNerve</span>
      </div>

      <nav className="demo" aria-label="Demo moments">
        {DEMO.map((m, i) => {
          const source = m.pick(sources)
          return (
            <button
              key={m.key}
              className={hello && source && hello.source === source.id ? 'on' : ''}
              disabled={!source}
              title={source ? `${m.blurb} (key ${m.key})` : 'No real recordings yet: run tools/prep_quakeflow.py'}
              onClick={() => controls.demo(i)}
            >
              <kbd>{m.key}</kbd>
              {m.title}
            </button>
          )
        })}
      </nav>

      <select
        className="more"
        aria-label="All recordings"
        value={hello?.source ?? ''}
        onChange={(e) => e.target.value && controls.start(e.target.value)}
      >
        <option value="" disabled>
          All recordings…
        </option>
        {groups.map((g) => (
          <optgroup key={g.label} label={g.label}>
            {g.items.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title || s.id}
              </option>
            ))}
          </optgroup>
        ))}
      </select>

      <div className="transport">
        <button className="play" onClick={() => controls.toggle()} title="Play / pause (Space)">
          {playing ? <PauseIcon /> : <PlayIcon />}
          {!hello ? 'Play' : playing ? 'Pause' : 'Resume'}
        </button>
        <button className="icon" onClick={() => controls.restart()} disabled={!hello} title="Restart (R)" aria-label="Restart">
          <RestartIcon />
        </button>
        <div className="seg" role="group" aria-label="Replay speed">
          {SPEEDS.map((s) => (
            <button key={s} className={speed === s ? 'on' : ''} onClick={() => controls.setSpeed(s)}>
              {s}×
            </button>
          ))}
        </div>
      </div>

      <div className="clock-block">
        <span className="clock">{fmtClock(now)}</span>
        <span className="sub">
          {!hello ? 'idle' : status?.ended ? 'recording ended · clock running' : `of ${fmtClock(hello.duration_s).slice(2)}`}
        </span>
      </div>

      <span className="spacer" />
      {error && (
        <span className="error" title={error}>
          {error.slice(0, 70)}
        </span>
      )}
      <span className={`conn ${connected ? 'ok' : ''}`}>
        <i />
        {connected ? 'live' : 'reconnecting'}
      </span>
      {hello && <span className={`badge ${hello.kind}`}>{hello.kind === 'synthetic' ? 'SIMULATED' : 'REPLAY: REAL RECORDING'}</span>}
    </header>
  )
}

/** A thin bar under the header: how far through the recording we are. */
export function Progress() {
  useTicker(4)
  const hello = useStore((s) => s.hello)
  const ended = useStore((s) => s.status?.ended ?? false)
  const share = hello ? Math.min(1, streamNow() / hello.duration_s) : 0
  return (
    <div className="progress" aria-hidden="true">
      <div className={ended ? 'ended' : ''} style={{ width: `${share * 100}%` }} />
    </div>
  )
}
