// Every way to drive a session (header buttons, welcome cards, keyboard) goes through here.
import { api } from './api'
import { useStore, type Source } from './store'

export interface DemoMoment {
  key: string
  title: string
  blurb: string
  speed: number
  pick: (sources: Source[]) => Source | undefined
}

// The three moments of the pitch, in order (docs/build-spec.md, "What the judges see").
export const DEMO: DemoMoment[] = [
  {
    key: '1',
    title: 'Real quake',
    blurb: 'A real earthquake recorded on fibre, beside the USGS catalog',
    speed: 2,
    pick: (s) => s.find((x) => x.kind === 'real'),
  },
  {
    key: '2',
    title: 'India M7',
    blurb: 'A simulated M7.0 near Car Nicobar: rings, countdowns, warning gained',
    speed: 2,
    pick: (s) => s.find((x) => x.id === 'car_nicobar_m7'),
  },
  {
    key: '3',
    title: 'Anchor drag',
    blurb: 'A ship stops over the cable and drags its anchor',
    speed: 5,
    pick: (s) => s.find((x) => x.id === 'anchor_drag'),
  },
]

const run = (p: Promise<unknown>) =>
  p.then(() => useStore.getState().setError(null)).catch((e: Error) => useStore.getState().setError(e.message))

export const controls = {
  start(sourceId: string, speed = useStore.getState().speed) {
    useStore.getState().setSpeed(speed)
    useStore.getState().setSourceId(sourceId)
    return run(api.start(sourceId, speed))
  },
  demo(index: number) {
    const moment = DEMO[index]
    const source = moment?.pick(useStore.getState().sources)
    if (source) return controls.start(source.id, moment.speed)
  },
  toggle() {
    const { hello, status, sourceId, sources } = useStore.getState()
    if (!hello) {
      const id = sourceId ?? DEMO[1].pick(sources)?.id ?? sources[0]?.id
      return id ? controls.start(id) : undefined
    }
    return run(status?.paused ? api.resume() : api.pause())
  },
  restart() {
    const { hello } = useStore.getState()
    if (hello) return controls.start(hello.source)
  },
  setSpeed(speed: number) {
    useStore.getState().setSpeed(speed)
    if (useStore.getState().hello) return run(api.speed(speed))
  },
}
