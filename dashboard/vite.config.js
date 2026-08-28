import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Proxy all API paths to FastAPI — eliminates CORS entirely in dev
      '/auth': 'http://127.0.0.1:8000',
      '/shorten': 'http://127.0.0.1:8000',
      '/stats': 'http://127.0.0.1:8000',
      '/ping': 'http://127.0.0.1:8000',
    }
  }
})
