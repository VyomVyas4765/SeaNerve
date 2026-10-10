import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In development the FastAPI server runs on :8000; Vite forwards API and WebSocket calls to it.
// For the demo, `npm run build` and FastAPI serves dist/ itself, so one process runs everything.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/geo': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
})
