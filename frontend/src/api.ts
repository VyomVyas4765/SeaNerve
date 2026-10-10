import type { Source } from './store'

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const r = await fetch(path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!r.ok) throw new Error(`${method} ${path}: ${r.status} ${await r.text()}`)
  return (await r.json()) as T
}

export const api = {
  sources: () => call<Source[]>('GET', '/api/sources'),
  start: (source_id: string, speed: number) => call('POST', '/api/session', { source_id, speed }),
  pause: () => call('POST', '/api/session/pause'),
  resume: () => call('POST', '/api/session/resume'),
  speed: (speed: number) => call('POST', '/api/session/speed', { speed }),
  stop: () => call('DELETE', '/api/session'),
}
