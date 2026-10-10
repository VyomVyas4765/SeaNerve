import { useEffect, useState } from 'react'

/** Re-render the calling component hz times a second (for countdowns and the clock). */
export function useTicker(hz = 10): void {
  const [, setTick] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 1000 / hz)
    return () => clearInterval(id)
  }, [hz])
}
