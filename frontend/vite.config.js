import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { execSync } from 'child_process'

let commitHash = 'dev'
try { commitHash = execSync('git rev-parse --short HEAD').toString().trim() } catch (_) {}

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify('1.1.0'),
    __GIT_HASH__: JSON.stringify(commitHash),
  },
  plugins: [react()],
  server: {
    host: true,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true, rewrite: p => p.replace(/^\/api/, '') },
      '/ws':  { target: 'ws://localhost:8000',  ws: true, changeOrigin: true },
    },
  },
  build: {
    // Suppress the 500kB warning — Three.js is intentionally large
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks: {
          three: ['three'],
          react: ['react', 'react-dom'],
        },
      },
    },
  },
})
