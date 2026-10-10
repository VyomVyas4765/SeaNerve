import { create } from 'zustand'
import type { Alert, Hello, Mode, ServerMessage, Status, Trigger } from './types'

export interface Source {
  id: string
  title: string
  kind: 'synthetic' | 'real'
  duration_s: number
}

interface State {
  connected: boolean
  sources: Source[]
  mode: Mode
  sourceId: string | null
  hello: Hello | null
  status: Status | null
  statusAt: number // performance.now() when the last status arrived
  trigger: Trigger | null // the gate's latest verdict
  passedTrigger: Trigger | null // the gate's latest pass, for the waterfall overlay
  alerts: Record<string, Alert> // newest revision wins
  alertOrder: string[]
  selectedId: string | null // null means "follow the newest alert"
  speed: number // the speed the next Play or demo moment uses
  error: string | null

  setConnected: (connected: boolean) => void
  setSources: (sources: Source[]) => void
  setMode: (mode: Mode) => void
  setSourceId: (id: string | null) => void
  select: (id: string | null) => void
  setSpeed: (speed: number) => void
  setError: (error: string | null) => void
  receive: (msg: ServerMessage) => void
}

export const useStore = create<State>((set, get) => ({
  connected: false,
  sources: [],
  mode: 'scenario',
  sourceId: null,
  hello: null,
  status: null,
  statusAt: 0,
  trigger: null,
  passedTrigger: null,
  alerts: {},
  alertOrder: [],
  selectedId: null,
  speed: 2,
  error: null,

  setConnected: (connected) => set({ connected }),
  setSources: (sources) => set({ sources }),
  setMode: (mode) => set({ mode }),
  setSourceId: (sourceId) => set({ sourceId }),
  select: (selectedId) => set({ selectedId }),
  setSpeed: (speed) => set({ speed }),
  setError: (error) => set({ error }),
  receive: (msg) => {
    switch (msg.type) {
      case 'hello':
        // The socket reconnected to the session we already show: keep the waterfall and alerts.
        if (get().hello?.session_id === msg.session_id && msg.session_id) break
        set({
          hello: msg,
          mode: msg.mode,
          sourceId: msg.source,
          status: null,
          trigger: null,
          passedTrigger: null,
          alerts: {},
          alertOrder: [],
          selectedId: null,
        })
        break
      case 'status':
        set({ status: msg, statusAt: performance.now(), speed: msg.speed })
        break
      case 'trigger':
        set((s) => ({ trigger: msg, passedTrigger: msg.passed ? msg : s.passedTrigger }))
        break
      case 'alert':
        set((s) => ({
          alerts: { ...s.alerts, [msg.id]: msg },
          alertOrder: s.alertOrder.includes(msg.id) ? s.alertOrder : [...s.alertOrder, msg.id],
        }))
        break
      case 'local_event':
        break // the ship and anchor tracker comes in a later step
    }
  },
}))

/** Stream time now, moving smoothly between the once-a-second status messages. */
export function streamNow(): number {
  const { status, statusAt } = useStore.getState()
  if (!status) return 0
  if (status.paused) return status.t_s
  const ahead = ((performance.now() - statusAt) / 1000) * status.speed
  return status.t_s + Math.min(ahead, 1)
}

/** True while an earthquake is under way or just over: no "rejected" labels for its fading tail. */
export function eventRecent(alert: { detected_at_s: number } | null, now: number): boolean {
  return alert != null && now - alert.detected_at_s < 90
}

/** The alert the cards show: the one picked in the log, else the newest. */
export function currentAlert(s: Pick<State, 'alerts' | 'alertOrder' | 'selectedId'>): Alert | null {
  const id = s.selectedId ?? s.alertOrder[s.alertOrder.length - 1]
  return id ? (s.alerts[id] ?? null) : null
}
