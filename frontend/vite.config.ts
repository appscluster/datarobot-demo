import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { port: 43123, proxy: { '/api': 'http://localhost:54123', '/runs': 'http://localhost:54123' } },
  preview: { port: 43123 }
})
