import { useEffect, useState } from 'react'

// Placeholder screen until the dashboard is built (plan hours 11 to 17).
// It only checks that the browser can reach the backend through the Vite proxy.
function App() {
  const [backend, setBackend] = useState('checking…')

  useEffect(() => {
    fetch('/api/health')
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((body: { status: string }) => setBackend(body.status))
      .catch(() => setBackend('not reachable (start uvicorn on :8000)'))
  }, [])

  return (
    <main style={{ padding: 24 }}>
      <h1>SeaNerve</h1>
      <p>Backend: {backend}</p>
    </main>
  )
}

export default App
