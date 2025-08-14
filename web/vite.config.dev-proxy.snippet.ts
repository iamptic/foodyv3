// Use this snippet in your vite.config.ts (dev only) to proxy /api to backend
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_BACKEND_URL ?? 'https://backend-production-a417.up.railway.app',
        changeOrigin: true,
        secure: true
        // If your backend does NOT include '/api' prefix internally, enable rewrite:
        // , rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
})
