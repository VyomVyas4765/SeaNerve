// One WebSocket for everything. Text messages are JSON for the store; binary messages are
// waterfall frames that go straight to the canvas (10 a second would re-render React too often).
import { useStore } from './store'
import type { ServerMessage } from './types'

type FrameListener = (buf: ArrayBuffer) => void
const frameListeners = new Set<FrameListener>()

export function onFrame(listener: FrameListener): () => void {
  frameListeners.add(listener)
  return () => frameListeners.delete(listener)
}

export function connect(): void {
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${scheme}://${location.host}/ws`)
  ws.binaryType = 'arraybuffer'
  ws.onopen = () => useStore.getState().setConnected(true)
  ws.onmessage = (e) => {
    if (typeof e.data === 'string') {
      useStore.getState().receive(JSON.parse(e.data) as ServerMessage)
    } else {
      frameListeners.forEach((f) => f(e.data as ArrayBuffer))
    }
  }
  ws.onclose = () => {
    useStore.getState().setConnected(false)
    setTimeout(connect, 1000)
  }
}
