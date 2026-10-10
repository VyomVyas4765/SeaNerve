import { useEffect } from 'react'
import './App.css'
import { AlertCard } from './components/AlertCard'
import { EventLog } from './components/EventLog'
import { Header, Progress } from './components/Header'
import { MapPanel } from './components/MapPanel'
import { Metrics } from './components/Metrics'
import { PipelineStrip } from './components/PipelineStrip'
import { WarningBars } from './components/WarningBars'
import { Waterfall } from './components/Waterfall'
import { controls } from './controls'

// Keyboard: Space play/pause, R restart, 1 2 3 the demo moments.
function useShortcuts() {
  useEffect(() => {
    const typing = (t: EventTarget | null) => t instanceof HTMLInputElement || t instanceof HTMLSelectElement
    const down = (e: KeyboardEvent) => {
      if (typing(e.target) || e.ctrlKey || e.metaKey || e.altKey) return
      if (e.key === ' ') {
        e.preventDefault() // also stops a focused button from being "clicked" by the same key
        controls.toggle()
      } else if (e.key === 'r' || e.key === 'R') {
        controls.restart()
      } else if (e.key === '1' || e.key === '2' || e.key === '3') {
        controls.demo(Number(e.key) - 1)
      }
    }
    const up = (e: KeyboardEvent) => e.key === ' ' && !typing(e.target) && e.preventDefault()
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    return () => {
      window.removeEventListener('keydown', down)
      window.removeEventListener('keyup', up)
    }
  }, [])
}

// One screen, no routing: waterfall on the left 60%, map with the alert card on the right,
// log and metrics along the bottom.
function App() {
  useShortcuts()
  return (
    <div className="app">
      <Header />
      <Progress />
      <PipelineStrip />
      <main className="main">
        <Waterfall />
        <div className="right">
          <MapPanel />
          <div className="cards">
            <AlertCard />
            <WarningBars />
          </div>
        </div>
      </main>
      <footer className="bottom">
        <EventLog />
        <Metrics />
      </footer>
    </div>
  )
}

export default App
