import { controls, DEMO } from '../controls'
import { useStore } from '../store'

/** Shown in the waterfall before anything plays: the three demo moments, one click each. */
export function Welcome() {
  const sources = useStore((s) => s.sources)
  return (
    <div className="welcome">
      <h2>Pick a demo moment</h2>
      <p className="muted">Everything runs on this laptop, so Wi-Fi can be off.</p>
      <div className="moments">
        {DEMO.map((m, i) => {
          const source = m.pick(sources)
          return (
            <button key={m.key} className="moment" disabled={!source} onClick={() => controls.demo(i)}>
              <kbd>{m.key}</kbd>
              <strong>{m.title}</strong>
              <span>{source ? m.blurb : 'No real recordings yet. Run tools/prep_quakeflow.py first.'}</span>
              <em>
                {source?.kind === 'real' ? 'Real recording' : 'Simulated'} · {m.speed}×
              </em>
            </button>
          )
        })}
      </div>
      <p className="keys">
        <kbd>Space</kbd> play / pause · <kbd>R</kbd> restart · <kbd>1</kbd> <kbd>2</kbd> <kbd>3</kbd> demo moments
      </p>
    </div>
  )
}
