import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5175,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // CV extraction / verify can exceed Vite's default proxy idle timeout
        // and surface as "Bad Gateway" even though the backend is fine.
        timeout: 3_600_000,
        proxyTimeout: 3_600_000,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
        changeOrigin: true,
        timeout: 0,
      },
    },
  },
})
