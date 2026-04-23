import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],

  // Resolve paths
  resolve: {
    alias: {
      '@': '/src',
    },
  },

  // Dev server configuration
  server: {
    port: 5173,
    // Proxy API requests to FastAPI — avoids CORS issues in development
    // All requests to /api/* are forwarded to FastAPI on port 8000
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },

  // Preview server (for testing production build locally)
  preview: {
    port: 4173,
  },
})
